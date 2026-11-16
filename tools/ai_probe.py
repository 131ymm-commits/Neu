#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба доступа к другим ИИ через GitHub Models с раннера GitHub Actions. Слово автора, 16.11.2026: «Ты думаешь. Внешние ресурсы
считают. Кстати ты можешь обращаться к другим ИИ? Попробуй их так то интегрировать в проект».
- Токен — GITHUB_TOKEN раннера с разрешением models: read (переменная GH_MODELS_TOKEN). Новых ключей нет. Токен не печатается и
  вычищается из всего, что пишется на диск.
- Это техническая проба, а не опыт:
  - каталог моделей;
  - по одному короткому запросу к нескольким моделям разных производителей (по одной на производителя, сначала из нижнего яруса квоты).
  Ответы ни в какой опыт не идут; вопрос — сложение, правду считает код (для проверки разбора ответа).
- Ответы моделей — только текст для записи; ничего из них не исполняется.
  python3 tools/ai_probe.py OUT_DIR [--max N]"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

OUT = sys.argv[1]
MAX = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 8
os.makedirs(OUT, exist_ok=True)
TOK = os.environ.get('GH_MODELS_TOKEN', '')
BASE = 'https://models.github.ai'
A, B = 347, 58
PROMPT = f'Reply with the number only. {A} + {B} ='
TIER_ORDER = {'low': 0, 'high': 1}


def scrub(x):
    s = json.dumps(x, ensure_ascii=False)
    if TOK:
        s = s.replace(TOK, '***')
    s = re.sub(r'gh[pousr]_[A-Za-z0-9]{20,}', '***', s)
    return json.loads(s)


def call(method, path, body=None, timeout=90):
    h = {'Accept': 'application/vnd.github+json', 'Authorization': f'Bearer {TOK}', 'X-GitHub-Api-Version': '2022-11-28'}
    data = None
    if body is not None:
        h['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            hdr = {k.lower(): v for k, v in resp.headers.items() if 'ratelimit' in k.lower() or k.lower() in ('x-request-id', 'date')}
            return resp.status, json.loads(resp.read().decode('utf-8', 'replace')), hdr, round(time.time() - t0, 2)
    except urllib.error.HTTPError as e:
        hdr = {k.lower(): v for k, v in (e.headers or {}).items() if 'ratelimit' in k.lower() or 'retry' in k.lower()}
        return e.code, {'error': e.read().decode('utf-8', 'replace')[:600]}, hdr, round(time.time() - t0, 2)
    except Exception as e:  # сеть, разбор
        return None, {'error': repr(e)[:300]}, {}, round(time.time() - t0, 2)


def main():
    res = dict(source='tools/ai_probe.py', prompt=PROMPT, truth=A + B, token_present=bool(TOK), catalog=None, calls=[])
    st, cat, hdr, dt = call('GET', '/catalog/models')
    models = cat if isinstance(cat, list) else (cat.get('models') or cat.get('data') or []) if isinstance(cat, dict) else []
    res['catalog'] = dict(status=st, seconds=dt, n=len(models), error=cat.get('error') if isinstance(cat, dict) else None,
                          models=[dict(id=m.get('id'), publisher=m.get('publisher'), tier=m.get('rate_limit_tier'),
                                       out=m.get('supported_output_modalities'), caps=m.get('capabilities')) for m in models])
    print(f'каталог: код {st}, моделей {len(models)}, {dt} с', flush=True)
    by_pub = {}
    for m in models:
        if 'text' not in (m.get('supported_output_modalities') or ['text']) or m.get('rate_limit_tier') not in TIER_ORDER:
            continue
        by_pub.setdefault(m.get('publisher') or '?', []).append(m)
    picks = []
    for pub, ms in sorted(by_pub.items()):
        ms.sort(key=lambda m: (TIER_ORDER[m.get('rate_limit_tier')], str(m.get('id'))))
        picks.append(ms[0])
    for m in picks[:MAX]:
        body = dict(model=m['id'], messages=[dict(role='user', content=PROMPT)], max_tokens=16)
        st, ans, hdr, dt = call('POST', '/inference/chat/completions', body)
        if st == 400 and 'max_tokens' in json.dumps(ans):            # у части моделей другое имя предела
            body.pop('max_tokens')
            body['max_completion_tokens'] = 256
            st, ans, hdr, dt = call('POST', '/inference/chat/completions', body)
        text = None
        try:
            text = ans['choices'][0]['message']['content']
        except Exception:
            pass
        num = re.findall(r'-?\d+', text or '')
        ok = bool(num) and int(num[-1]) == A + B
        res['calls'].append(dict(model=m['id'], publisher=m.get('publisher'), tier=m.get('rate_limit_tier'), status=st, seconds=dt,
                                 answer=(text or '')[:200], parsed=int(num[-1]) if num else None, correct=ok,
                                 usage=ans.get('usage') if isinstance(ans, dict) else None,
                                 error=ans.get('error') if isinstance(ans, dict) else None, ratelimit=hdr))
        print(f"{m['id']} ({m.get('publisher')}, {m.get('rate_limit_tier')}): код {st}, {dt} с, ответ {(text or '').strip()[:40]!r}, "
              f"верно {ok}", flush=True)
        time.sleep(6)                                               # нижний ярус — около 15 запросов в минуту
    json.dump(scrub(res), open(os.path.join(OUT, 'ai_probe.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    good = sum(c['status'] == 200 for c in res['calls'])
    print(f'итог: каталог {res["catalog"]["status"]}, вызовов {len(res["calls"])}, ответили {good}, верно {sum(c["correct"] for c in res["calls"])}')


if __name__ == '__main__':
    main()
