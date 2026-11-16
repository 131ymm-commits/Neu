#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба открытых моделей других производителей на процессоре GitHub Actions. Слово автора, 16.11.2026: «Ты думаешь. Внешние
ресурсы считают. Кстати ты можешь обращаться к другим ИИ? Попробуй их так то интегрировать в проект».
- Без ключей: веса с Hugging Face, только модели без лицензионного замка.
- Техническая проба, а не опыт:
  - загрузка;
  - 12 задач сложения «трёхзначное + двузначное» (правду считает код);
  - время ответа и разбор ответа;
  - уверенность — сумма логарифмов вероятностей сгенерированных токенов.
  Ответы ни в какой опыт не идут; ничего из них не исполняется. Имена моделей — по памяти; проба покажет, верны ли.
  python3 tools/open_probe.py OUT_DIR"""
import gc
import json
import os
import re
import shutil
import sys
import tempfile
import time

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
MODELS = ['Qwen/Qwen2.5-0.5B-Instruct', 'HuggingFaceTB/SmolLM2-360M-Instruct', 'allenai/OLMo-2-0425-1B-Instruct',
          'ibm-granite/granite-3.1-1b-a400m-instruct', 'tiiuae/Falcon3-1B-Instruct', 'TinyLlama/TinyLlama-1.1B-Chat-v1.0']
rng = np.random.default_rng(20261116)
TASKS = [(int(a), int(b)) for a, b in zip(rng.integers(100, 1000, 12), rng.integers(10, 100, 12))]
torch.set_num_threads(os.cpu_count() or 4)


def prompt(tok, a, b):
    msg = f'What is {a} + {b}? Reply with the number only.'
    if getattr(tok, 'chat_template', None):
        return tok.apply_chat_template([{'role': 'user', 'content': msg}], tokenize=False, add_generation_prompt=True)
    return f'{a} + {b} ='


def parse(ans):
    tail = ans.split('=')[-1] if '=' in ans else ans                  # «347 + 58 = 405» → «405»
    num = re.findall(r'-?\d+', tail.replace(',', ''))
    return int(num[0]) if num else None


def run(name):
    r = dict(model=name)
    cache = tempfile.mkdtemp(prefix='hf_')
    t0 = time.time()
    try:
        tok = AutoTokenizer.from_pretrained(name, cache_dir=cache)
        model = AutoModelForCausalLM.from_pretrained(name, cache_dir=cache, dtype=torch.float32)
        model.eval()
    except Exception as e:
        shutil.rmtree(cache, ignore_errors=True)
        r.update(load_error=repr(e)[:400])
        return r
    r['load_s'] = round(time.time() - t0, 1)
    r['params_m'] = round(sum(p.numel() for p in model.parameters()) / 1e6, 1)
    rows = []
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    for a, b in TASKS:
        ids = tok(prompt(tok, a, b), return_tensors='pt', add_special_tokens=False)
        t1 = time.time()
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=8, do_sample=False, output_scores=True, return_dict_in_generate=True, pad_token_id=pad)
        gen = out.sequences[0, ids['input_ids'].shape[1]:].tolist()
        ans = tok.decode(gen, skip_special_tokens=True)
        lp = 0.0
        for step, tid in enumerate(gen):
            if step >= len(out.scores) or tid == tok.eos_token_id:
                break
            lp += float(torch.log_softmax(out.scores[step][0].float(), -1)[tid])
        p = parse(ans)
        rows.append(dict(a=a, b=b, answer=ans.strip()[:40], parsed=p, correct=p == a + b, logprob=round(lp, 4),
                         seconds=round(time.time() - t1, 2)))
    del model
    gc.collect()
    shutil.rmtree(cache, ignore_errors=True)
    r['rows'] = rows
    r['accuracy'] = sum(x['correct'] for x in rows) / len(rows)
    r['sec_per_answer'] = round(float(np.mean([x['seconds'] for x in rows])), 2)
    return r


def main():
    import transformers
    res = dict(source='tools/open_probe.py', tasks=TASKS, versions=dict(torch=torch.__version__, transformers=transformers.__version__),
               cpus=os.cpu_count(), models=[])
    for name in MODELS:
        r = run(name)
        res['models'].append(r)
        if 'load_error' in r:
            print(f'{name}: не загрузилась — {r["load_error"][:160]}', flush=True)
        else:
            print(f'{name}: {r["params_m"]} млн параметров, загрузка {r["load_s"]} с, верно {r["accuracy"]:.2f}, {r["sec_per_answer"]} с на ответ; '
                  f'пример {r["rows"][0]["answer"]!r}', flush=True)
        json.dump(res, open(os.path.join(OUT, 'open_probe.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = [m for m in res['models'] if 'rows' in m]
    print(f'итог: загрузились {len(ok)} из {len(MODELS)}')


if __name__ == '__main__':
    main()
