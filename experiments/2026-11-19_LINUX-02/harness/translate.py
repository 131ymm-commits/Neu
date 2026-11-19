#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: переводы запечатанными головами — как в LINUX-01 (harness/translate.py там же). Каждая голова — отдельный вызов
«claude -p --tools ""» (инструментов нет вовсе) из пустой папки вне репозитория (нет CLAUDE.md и снимка git). Поручение —
prompts/<модуль>.md (фаза test — prompts/test/<модуль>.md) дословно через stdin. Новое: фазы (pilot / test), повторы и счётчик трат с остановкой.
Пишет translations/<фаза>/<голова>/<модуль>_r<повтор>.rs (блок ```rust из ответа) и .json (ответ, расход, модель, хеш поручения).
Счётчик: перед каждым вызовом складывается total_cost_usd всех уже записанных .json фазы (вместе с прежними запусками);
если сумма не меньше предела, новые вызовы не начинаются. Вызовы в полёте (не больше --workers) могут превысить предел на свою цену.
Уже готовые переводы (есть .json без ошибки) не повторяются: продолжение с места остановки.
  python3 harness/translate.py SEALED_CWD --phase pilot|test --limit USD [--heads haiku,sonnet,opus] [--modules ...] [--reps N]
                               [--workers 6]"""
import concurrent.futures as cf
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = {'haiku': 'claude-haiku-5-5', 'sonnet': 'claude-sonnet-5-5', 'opus': 'claude-opus-5-5'}
MODULES = ['errseq', '842_decompress', 'md5', 'random32', 'min_heap', 'string_helpers']
LOCK = threading.Lock()


def prompt_path(phase, mod):
    """Пилот — prompts/<модуль>.md (хеши пилота); тест — prompts/test/<модуль>.md (новая версия, DEVIATIONS п. 8)."""
    return os.path.join(X, 'prompts', *(['test'] if phase == 'test' else []), f'{mod}.md')


def spent(phase):
    tot = 0.0
    for f in glob.glob(os.path.join(X, 'translations', phase, '*', '*.json')):
        c = json.load(open(f, encoding='utf-8')).get('total_cost_usd')
        tot += c if isinstance(c, (int, float)) else 0.0
    return tot


def done(path):
    if not os.path.exists(path):
        return False
    r = json.load(open(path, encoding='utf-8'))
    return r.get('returncode') == 0 and r.get('is_error') is False and r.get('code_extracted')


def one(head, mod, rep, cwd, phase):
    prompt = open(prompt_path(phase, mod), encoding='utf-8').read()
    t0 = time.time()
    p = subprocess.run(['claude', '-p', '--tools', '', '--model', MODELS[head], '--output-format', 'json'],
                       input=prompt, capture_output=True, text=True, cwd=cwd, timeout=3600)
    rec = dict(phase=phase, head=head, module=mod, rep=rep, model_target=MODELS[head],
               prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), seconds=round(time.time() - t0, 1), returncode=p.returncode,
               cwd_outside_repo=not os.path.abspath(cwd).startswith('/home/user/Neu'), tools_flag='--tools ""')
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
    opt = lambda k, dflt: a[a.index(k) + 1] if k in a else dflt   # noqa: E731
    phase, limit = opt('--phase', None), float(opt('--limit', 'nan'))
    assert phase in ('pilot', 'test') and limit == limit, 'нужны --phase pilot|test и --limit'
    heads = opt('--heads', ','.join(MODELS)).split(',')
    mods = opt('--modules', ','.join(MODULES)).split(',')
    reps = int(opt('--reps', '1'))
    workers = int(opt('--workers', '6'))
    os.makedirs(cwd, exist_ok=True)
    assert os.listdir(cwd) == [], 'папка вызова должна быть пустой'
    jobs = [(h, m, r) for r in range(1, reps + 1) for m in mods for h in heads
            if not done(os.path.join(X, 'translations', phase, h, f'{m}_r{r}.json'))]
    print('к переводу:', len(jobs), '| потрачено в фазе до старта, $:', round(spent(phase), 4), '| предел, $:', limit, flush=True)
    stopped = []

    def guarded(h, m, r):
        with LOCK:
            s = spent(phase)
            if s >= limit:
                stopped.append((h, m, r))
                return None
        return one(h, m, r, cwd, phase)

    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(guarded, h, m, r): (h, m, r) for h, m, r in jobs}
        for f in cf.as_completed(futs):
            h, m, r = futs[f]
            try:
                res = f.result()
            except Exception as e:                      # сбой вызова — записывается, перевода нет
                res = (dict(phase=phase, head=h, module=m, rep=r, error=repr(e)), None)
            if res is None:
                continue
            rec, code = res
            d = os.path.join(X, 'translations', phase, h)
            with LOCK:
                os.makedirs(d, exist_ok=True)
                json.dump(rec, open(os.path.join(d, f'{m}_r{r}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                if code is not None:
                    open(os.path.join(d, f'{m}_r{r}.rs'), 'w', encoding='utf-8').write(code)
            u = rec.get('usage') or {}
            print(h, m, f'r{r}', '| код', rec.get('code_extracted'), '| модели', rec.get('models_used'), '| вход', u.get('input_tokens'),
                  '| выход', u.get('output_tokens'), '| $', rec.get('total_cost_usd'), '|', rec.get('seconds'), 'с', flush=True)
    print('итого в фазе, $:', round(spent(phase), 4), '| не начато из-за предела:', len(stopped), stopped, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
