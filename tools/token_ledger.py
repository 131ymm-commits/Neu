#!/usr/bin/env python3
"""Куда уходят токены: главный цикл, подагенты и головы опытов — по usage из транскриптов и журналов драйвера.

  python3 tools/token_ledger.py --session <транскрипт.jsonl> [--journal <журнал драйвера>]... --out journal/token_ledger.json

Цена — по прейскуранту API (не по лимиту подписки: как лимит взвешивает модели и кеш, не проверено).
Цены за 1 млн токенов: навык claude-api, кеш таблицы 2026-11-03 — вход, выход и чтение кеша.
Запись кеша — множители 1,25 (5 минут) и 2 (1 час) к цене входа: по памяти, в навыке для этих моделей не названы.
Для голов опытов берётся cost_usd из CLI (его собственный расчёт), а не этот прейскурант.
"""
import argparse, collections, glob, json, os

PRICE = {  # $ за 1 млн: вход, выход, чтение кеша
    'claude-opus-5-5': (4.0, 20.0, 0.20),
    'claude-sonnet-5-5': (2.0, 10.0, 0.10),
    'claude-haiku-5-5': (0.10, 0.50, None),  # чтение кеша для Haiku 5.5 в навыке не названо — берётся 0,1 входа (допущение)
}
W5, W1H = 1.25, 2.0


def usd(model, u):
    p = PRICE.get(model)
    if not p: return None
    i, o, cr = p; cr = cr if cr is not None else 0.1 * i
    cc = u.get('cache_creation') or {}
    w5 = cc.get('ephemeral_5m_input_tokens', 0); w1 = cc.get('ephemeral_1h_input_tokens', 0)
    rest = max(0, u.get('cache_creation_input_tokens', 0) - w5 - w1)  # без разбивки — как 5 минут
    return (u.get('input_tokens', 0) * i + u.get('output_tokens', 0) * o + u.get('cache_read_input_tokens', 0) * cr
            + (w5 + rest) * i * W5 + w1 * i * W1H) / 1e6


def tally(paths):
    by = collections.defaultdict(lambda: collections.Counter()); seen = set(); first = last = None
    for path in paths:
        for line in open(path, errors='ignore'):
            try: d = json.loads(line)
            except ValueError: continue
            if d.get('type') != 'assistant': continue
            m = d.get('message') or {}; u = m.get('usage') or {}; mid = m.get('id'); model = m.get('model')
            if not u or mid in seen or model in (None, '<synthetic>'): continue
            seen.add(mid); ts = d.get('timestamp'); first = min(first, ts) if first else ts; last = max(last, ts) if last else ts
            c = by[model]; c['msgs'] += 1
            for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'): c[k] += u.get(k, 0)
            v = usd(model, u)
            if v is not None: c['usd_e6'] += round(v * 1e6)
    out = {}
    for model, c in by.items():
        cost = c.pop('usd_e6', 0) / 1e6; i, o, cr = PRICE.get(model, (0, 0, 0)); cr = cr if cr is not None else 0.1 * i
        parts = {'output': c['output_tokens'] * o / 1e6, 'cache_read': c['cache_read_input_tokens'] * cr / 1e6}
        out[model] = dict(c, usd=round(cost, 2), share_output=round(parts['output'] / cost, 3) if cost else None,
                          share_cache_read=round(parts['cache_read'] / cost, 3) if cost else None)
    return {'first': first, 'last': last, 'by_model': out}


def journal(path):
    t = collections.Counter(); n = 0
    for p in glob.glob(os.path.join(path, '*.jsonl')):
        if p.endswith('run_log.jsonl'): continue
        for line in open(p, encoding='utf-8'):
            r = json.loads(line); u = r.get('usage') or {}; n += 1
            t['inp'] += u.get('inp') or 0; t['out'] += u.get('out') or 0; t['usd_cli'] += u.get('cost_usd') or 0
    return {'calls': n, 'inp': t['inp'], 'out': t['out'], 'usd_cli': round(t['usd_cli'], 2),
            'share_out_tokens': round(t['out'] / (t['inp'] + t['out']), 4) if n else None}


ap = argparse.ArgumentParser()
ap.add_argument('--session', required=True); ap.add_argument('--journal', action='append', default=[]); ap.add_argument('--out')
a = ap.parse_args()
sub = sorted(glob.glob(os.path.join(a.session[:-len('.jsonl')], '**', '*.jsonl'), recursive=True))
res = {'prices_per_mtok': PRICE, 'cache_write_multipliers': {'5m': W5, '1h': W1H, 'status': 'по памяти'},
       'main_loop': tally([a.session]), 'subagents_and_workflows': tally(sub), 'subagent_files': len(sub),
       'heads': {os.path.basename(os.path.normpath(j)): journal(j) for j in a.journal}}
s = json.dumps(res, ensure_ascii=False, indent=1)
if a.out: open(a.out, 'w', encoding='utf-8').write(s + '\n')
print(s)
