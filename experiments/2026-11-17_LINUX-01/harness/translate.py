#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-01: переводы запечатанными головами. Каждая голова — отдельный вызов «claude -p --tools ""» (инструментов нет вовсе),
из папки вне репозитория (нет CLAUDE.md и снимка git), поручение — файл prompts/<модуль>.md дословно через stdin.
Пишет translations/<голова>/<модуль>.rs (блок ```rust из ответа) и translations/<голова>/<модуль>.json (ответ, расход, модель).
  python3 harness/translate.py SEALED_CWD [--heads haiku,sonnet,opus] [--modules ...] [--workers 6]"""
import concurrent.futures as cf
import hashlib
import json
import os
import re
import subprocess
import sys
import time

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = {'haiku': 'claude-haiku-5-5', 'sonnet': 'claude-sonnet-5-5', 'opus': 'claude-opus-5-5'}
MODULES = ['int_pow', 'int_sqrt', 'gcd', 'rational', 'int_log', 'cmdline']


def one(head, mod, cwd):
    prompt = open(os.path.join(X, 'prompts', f'{mod}.md'), encoding='utf-8').read()
    t0 = time.time()
    p = subprocess.run(['claude', '-p', '--tools', '', '--model', MODELS[head], '--output-format', 'json'],
                       input=prompt, capture_output=True, text=True, cwd=cwd, timeout=1800)
    rec = dict(head=head, module=mod, model_target=MODELS[head], prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
               seconds=round(time.time() - t0, 1), returncode=p.returncode, cwd_outside_repo=not os.path.abspath(cwd).startswith('/home/user/Neu'),
               tools_flag='--tools ""')
    try:
        d = json.loads(p.stdout)
    except json.JSONDecodeError:
        rec.update(error='ответ не JSON', stdout_tail=p.stdout[-800:], stderr_tail=p.stderr[-800:])
        return rec, None
    rec.update(is_error=d.get('is_error'), result=d.get('result'), usage=d.get('usage'), total_cost_usd=d.get('total_cost_usd'),
               model_usage=d.get('modelUsage'), num_turns=d.get('num_turns'), duration_ms=d.get('duration_ms'))
    m = re.findall(r'```rust\s*\n(.*?)```', d.get('result') or '', flags=re.S)
    code = m[0] if m else None
    rec['code_extracted'] = code is not None
    rec['models_used'] = sorted((d.get('modelUsage') or {}).keys())
    return rec, code


def main(a):
    cwd = a[0]
    heads = a[a.index('--heads') + 1].split(',') if '--heads' in a else list(MODELS)
    mods = a[a.index('--modules') + 1].split(',') if '--modules' in a else MODULES
    workers = int(a[a.index('--workers') + 1]) if '--workers' in a else 6
    os.makedirs(cwd, exist_ok=True)
    jobs = [(h, m) for h in heads for m in mods]
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(one, h, m, cwd): (h, m) for h, m in jobs}
        for f in cf.as_completed(futs):
            h, m = futs[f]
            try:
                rec, code = f.result()
            except Exception as e:                      # сбой вызова — записывается, перевода нет
                rec, code = dict(head=h, module=m, error=repr(e)), None
            d = os.path.join(X, 'translations', h)
            os.makedirs(d, exist_ok=True)
            json.dump(rec, open(os.path.join(d, f'{m}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            if code is not None:
                open(os.path.join(d, f'{m}.rs'), 'w', encoding='utf-8').write(code)
            u = rec.get('usage') or {}
            print(h, m, '| код', rec.get('code_extracted'), '| модели', rec.get('models_used'), '| вход', u.get('input_tokens'),
                  '| выход', u.get('output_tokens'), '| $', rec.get('total_cost_usd'), '|', rec.get('seconds'), 'с', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
