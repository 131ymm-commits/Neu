#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: сухой прогон всей цепочки на заглушках (формат answers.json — как у ocshift_extract.py, MODE = 'test';
среды и задачи — настоящая раскладка теста: 10 сред по 2200 задач; ответы голов — синтетические).
  python3 dry_ocshift.py OUT_DIR [--boot B]
Ожидания записаны до запуска:
  crowd    — девять независимых голов равной точности (ID 0,75, OOD 0,60), неверные ответы почти не совпадают.
             Согласие находит верный ответ → толпа сильнее одной головы → R1 «опровергнуто»; среды одинаковы → R4 «не решено».
  one      — одна сильная голова (ID 0,75, OOD 0,70); остальные на ID хороши (0,60), вне диапазона ломаются (0,15),
             ошибаются одинаково и уверенно → выбор уходит к сломанным → R1 «подтверждено».
  fail     — как crowd, но в трёх средах у четырёх голов на ID почти нет верных ответов → эти среды негодны
             (годных 7 из 10 < 8) → все правила «не определено (проверка метода)».
  badcheck — как crowd, но в блоке сверки изменён один ответ → сверка не проходит → все правила «не определено».
Блок сверки берётся из закоммиченного вывода пилота OCREP-01 (первые 96 задач), поэтому в crowd, one и fail сверка проходит."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['OCSHIFT_IMPORT_ONLY'] = '1'
sys.path.insert(0, HERE)
import ocshift_extract as X  # noqa: E402
import analyze_ocshift as S  # noqa: E402

OFFS = np.array([-100, -20, -11, -10, -9, -2, -1, 1, 2, 9, 10, 11, 20, 100])


def head_cols(g, probs, acc_id, acc_ood, common_wrong, p_common, conf_wrong_ood):
    """Синтетическая голова: верна с вероятностью acc; неверный ответ — общий для сломанных голов (с вер. p_common) или свой."""
    n = len(probs)
    truth = np.array([p['sum'] for p in probs])
    is_id = np.array([p['range'] == 'ID' for p in probs])
    ok = g.random(n) < np.where(is_id, acc_id, acc_ood)
    own = truth + g.choice(OFFS, n)
    wrong = np.where(g.random(n) < p_common, common_wrong, own)
    ans = np.where(ok, truth, wrong)
    lp = np.where(ok, g.normal(-0.4, 0.4, n), g.normal(-1.6, 0.7, n))
    if conf_wrong_ood:                                                     # вне диапазона ошибается так же уверенно, как отвечает верно
        lp = np.where(~ok & ~is_id, g.normal(-0.4, 0.4, n), lp)
    lp = np.minimum(lp, -1e-3)
    return dict(answer=[int(a) for a in ans], correct=[int(a == t) for a, t in zip(ans, truth)], logp=[float(x) for x in lp],
                n_tok=[1] * n, text_none={})


def build(kind, seed):
    envs = X.environments('test')
    ref = json.load(open(S.OCREP_PILOT, encoding='utf-8'))
    g = np.random.default_rng(seed)
    heads = []
    common = {e['name']: np.array([p['sum'] for p in e['problems']]) + g.choice(OFFS, len(e['problems'])) for e in envs}
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
            if kind == 'one':
                strong = k == 6
                cols[e['name']] = head_cols(g, e['problems'], 0.75 if strong else 0.60, 0.70 if strong else 0.15, common[e['name']],
                                            0.0 if strong else 0.8, not strong)
            else:
                broken = kind == 'fail' and j <= 3 and k < 4                 # среды 1–3 (после блока сверки), четыре головы
                cols[e['name']] = head_cols(g, e['problems'], 0.005 if broken else 0.75, 0.60, common[e['name']], 0.0, False)
        heads.append(dict(model=repo.split('/')[-1], repo=repo, revision=rev, where='stub', worker=0, seconds=0.0, seconds_env={}, cols=cols))
    return dict(info=dict(mode='test', stub=kind), mode='test', design=dict(stub=kind), envs=envs, heads=heads, seconds=0.0)


EXPECT = {'crowd': dict(R1='опровергнуто', R4='не решено'), 'one': dict(R1='подтверждено'),
          'fail': {k: 'не определено (проверка метода)' for k in ('R1', 'R2', 'R3', 'R4')},
          'badcheck': {k: 'не определено (проверка метода)' for k in ('R1', 'R2', 'R3', 'R4')}}


def main(out_dir, B):
    os.makedirs(out_dir, exist_ok=True)
    summary, bad = {}, []
    for i, kind in enumerate(EXPECT):
        d = os.path.join(out_dir, kind)
        os.makedirs(d, exist_ok=True)
        json.dump(build(kind, 7_640_000 + i), open(os.path.join(d, 'answers.json'), 'w'), ensure_ascii=False)
        dst = os.path.join(out_dir, f'{kind}_analysis.json')
        subprocess.run([sys.executable, os.path.join(HERE, 'analyze_ocshift_test.py'), dst, '--boot', str(B), f'new:{d}'], check=True)
        os.remove(os.path.join(d, 'answers.json'))                          # заглушки в репозиторий не кладём: восстанавливаются по зерну
        os.rmdir(d)
        r = json.load(open(dst, encoding='utf-8'))
        got = r['verdicts']
        okk = all(got[k] == v for k, v in EXPECT[kind].items())
        summary[kind] = dict(verdicts=got, expected=EXPECT[kind], as_expected=okk, method=r['method'], check_ok=r['check_ok'], seconds=r.get('seconds'),
                             R1=None if 'R1' not in r else dict(delta=r['R1']['delta'], ci=r['R1']['ci']))
        if not okk:
            bad.append(kind)
        print(f"{kind}: {got} | ожидалось {EXPECT[kind]} | {'как ожидалось' if okk else 'НЕ КАК ОЖИДАЛОСЬ'}", flush=True)
    json.dump(summary, open(os.path.join(out_dir, 'dry_summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('сухой прогон:', 'все четыре — как ожидалось' if not bad else f'не как ожидалось: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    a = sys.argv[1:]
    sys.exit(main(a[0], int(a[a.index('--boot') + 1]) if '--boot' in a else 60))
