#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01: сухой прогон всей цепочки на заглушках (формат answers.json — как у ocpost_extract.py; среды и задачи —
настоящая раскладка теста: 5 сред по 2200 задач и блок сверки; ответы голов — синтетические, dry_ocshift.head_cols).
  python3 dry_ocpost.py OUT_DIR [--boot B]
Ожидания записаны до запуска:
  select   — девять независимых голов равной точности (ID 0,45, OOD 0,30), заявки одинаково шумны → отбор по наибольшей
             заявке завышает её на ID: P0 «подтверждено»; вторая калибровка снимает завышение вне диапазона: P1 «подтверждено»;
             выбор по заявке находит верные ответы чаще одной головы: P2 «подтверждено»; P3 и N — «подтверждено» или «не решено»
             (их ширина при 5 средах близка к полосе ±0,02).
  fail     — как select, но в двух средах у четырёх голов на ID почти нет верных ответов → годных 3 из 5 < 4 → все правила
             «не определено (проверка метода)».
  badcheck — как select, но в блоке сверки изменён один ответ → сверка не проходит → все правила «не определено (проверка метода)».
  nofixed  — как select, но в одной среде голова FIXED (pythia-2.8b-deduped) на ID почти не отвечает верно → вне толпы →
             N «не определено (голова FIXED вне толпы в годной среде)»; P0 «подтверждено».
Блок сверки берётся из закоммиченного вывода пилота OCREP-01 (первые 96 задач), поэтому в select, fail и nofixed сверка проходит."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['OCPOST_IMPORT_ONLY'] = '1'
sys.path.insert(0, HERE)
import ocpost_extract as X  # noqa: E402
import ocpost as P  # noqa: E402
import dry_ocshift as D  # noqa: E402  (head_cols, OFFS)

S = P.S
EITHER = ('подтверждено', 'не решено')
U = P.U
EXPECT = {'select': dict(P0='подтверждено', P1='подтверждено', P2='подтверждено', P3=EITHER, N=EITHER),
          'fail': {k: U for k in P.RULES},
          'badcheck': {k: U for k in P.RULES},
          'nofixed': dict(P0='подтверждено', N=P.UF)}


def build(kind, seed):
    envs = X.environments('test')
    ref = json.load(open(S.OCREP_PILOT, encoding='utf-8'))
    g = np.random.default_rng(seed)
    common = {e['name']: np.array([p['sum'] for p in e['problems']]) + g.choice(D.OFFS, len(e['problems'])) for e in envs}
    heads = []
    for k, (repo, rev) in enumerate(X.HEADS):
        cols = {}
        for j, e in enumerate(envs):
            if e['kind'] == 'check':
                rh = next(h for h in ref['heads'] if h['repo'] == repo and h['revision'] == rev)
                rows = rh['rows'][:len(e['problems'])]
                cols[e['name']] = dict(answer=[r['answer'] for r in rows], correct=[int(r['correct']) for r in rows], logp=[r['logp'] for r in rows],
                                       n_tok=[r['n_tok'] for r in rows], text_none={})
                if kind == 'badcheck' and k == 0:
                    cols[e['name']]['answer'][0] = (cols[e['name']]['answer'][0] or 0) + 1
                    cols[e['name']]['correct'][0] = int(cols[e['name']]['answer'][0] == e['problems'][0]['sum'])
                continue
            broken = (kind == 'fail' and j <= 2 and k < 4) or (kind == 'nofixed' and j == 1 and k == 6)
            cols[e['name']] = D.head_cols(g, e['problems'], 0.005 if broken else 0.45, 0.30, common[e['name']], 0.0, False)
        heads.append(dict(model=repo.split('/')[-1], repo=repo, revision=rev, where='stub', worker=0, seconds=0.0, seconds_env={}, cols=cols))
    return dict(info=dict(mode='test', stub=kind), mode='test', design=dict(stub=kind), envs=envs, heads=heads, seconds=0.0)


def ok_v(got, want):
    return got in want if isinstance(want, tuple) else got == want


def main(out_dir, B):
    os.makedirs(out_dir, exist_ok=True)
    summary, bad = {}, []
    for i, kind in enumerate(EXPECT):
        d = os.path.join(out_dir, kind)
        os.makedirs(d, exist_ok=True)
        json.dump(build(kind, 7_850_000 + i), open(os.path.join(d, 'answers.json'), 'w'), ensure_ascii=False)
        dst = os.path.join(out_dir, f'{kind}_analysis.json')
        subprocess.run([sys.executable, os.path.join(HERE, 'ocpost.py'), 'test', dst, '--boot', str(B), f'new:{d}'], check=True)
        os.remove(os.path.join(d, 'answers.json'))                          # заглушки в репозиторий не кладём: восстанавливаются по зерну
        os.rmdir(d)
        r = json.load(open(dst, encoding='utf-8'))
        got = r['verdicts']
        okk = all(ok_v(got[k], v) for k, v in EXPECT[kind].items())
        summary[kind] = dict(verdicts=got, expected={k: list(v) if isinstance(v, tuple) else v for k, v in EXPECT[kind].items()},
                             as_expected=okk, method=r['method'], check_ok=r['check_ok'], seconds=r.get('seconds'),
                             points={k: dict(delta=r[k]['delta'], ci=r[k]['ci']) for k in P.RULES if k in r})
        if not okk:
            bad.append(kind)
        print(f"{kind}: {got} | ожидалось {EXPECT[kind]} | {'как ожидалось' if okk else 'НЕ КАК ОЖИДАЛОСЬ'}", flush=True)
    json.dump(summary, open(os.path.join(out_dir, 'dry_summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('сухой прогон:', 'все четыре — как ожидалось' if not bad else f'не как ожидалось: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    a = sys.argv[1:]
    sys.exit(main(a[0], int(a[a.index('--boot') + 1]) if '--boot' in a else 200))
