#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: анализ теста по PREREG. python3 analyze_ocrep_test.py OUT_DIR RESULT.json [--boot B] [--workers W]
OUT_DIR — вывод ocrep_extract_test.py (SPLIT = 'test'). Головы — HEADS_TEST (закреплён в PREREG по проверке метода на
пилоте). Оценщики — analyze_ocrep (код OCCOR-01 и OCMIX-01 без изменений).
Бутстреп — вложенный: выборка задач ID с возвращением (переподгонка NB-AGREE, LR-AGREE, NB-IND, MIX-LR и калибровки), затем
выборка задач OOD; B повторов (по умолчанию 10000), зерно 1401; выборки заранее, счёт в нескольких процессах (один поток
BLAS на процесс), результат от числа процессов не зависит. Интервал — BC; вердикт правил — по BC и процентильному вместе (совет 58).
Правила (уровень — LEVEL на сторону; ложное «подтверждено» по серии — не выше LEVEL · число правил):
  R1 (третий тест C-086): ИОИ(LR-AGREE) − ИОИ(AGREE). Подтверждено — верхняя граница ДИ < 0; опровергнуто — нижняя > 0;
     по совету 58 — только если это дают оба ДИ, BC и процентильный (verdict_conj; иначе «не решено (только BC)» и т. п.).
  R2 (контроль на неспецифичность): ИОИ(LR-AGREE) − ИОИ(NB-IND) — так же.
  R3 (вето; только если R3_ACTIVE — условие, закреплённое до пилота): самообман верхушки VETO − LR-AGREE — так же.
Правило с мощностью меньше 0,05 (power.json) при «не решено» читается как «не проверено».
Проверки метода (провал → все правила «не определено (проверка метода)»): загружены все головы HEADS_TEST; у каждой на ID и
на OOD не меньше 20 верных и 20 неверных; ответов без числа не больше 5 %; голов не меньше 6; logp конечен (assert).
Защита LR (LR-AGREE и MIX-LR, условие одно): повторов с одним классом у какой-то головы в выборке ID больше 1 % — все правила
(в каждом есть LR-AGREE) «не решено». Хвосты BC: число повторов за границами и интервалы по двум половинам повторов; если
половины дают разный вердикт — пометка «граница по Монте-Карло неустойчива» (вердикт не меняет).
Описательно (вес 0, без вердикта; ДИ BC 99 %): NB-AGREE, FAM-AGREE, MIX-LR, CONF против AGREE или LR-AGREE; разложение R1 и R2
на ΔT и ΔC; верхушка (top10_sel) против CONF; R3 — описательно, если не включён; поддержка выбранного ответа VETO (любой
головой, головой другой линии); кросс-подгонка (точка); доля задач OOD, где все головы неверны и согласны; счётчики по головам;
исключает ли ДИ R1 и R2 (уровень правил, оба ДИ — совет 58) эффекты прежних тестов C-086 и C-087 и половину наименьшего (PREREG §5)."""
import json
import multiprocessing as mp
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocrep as Q  # noqa: E402

# Головы теста (PREREG-OCREP-01 §2) — все девять прошли проверку метода на пилоте OCREP-01.
HEADS_TEST = ['pythia-1.4b', 'pythia-1.4b-deduped', 'pythia-2.8b', 'pythia-2.8b@step133000', 'pythia-2.8b@step123000',
              'pythia-2.8b@step113000', 'pythia-2.8b-deduped', 'pythia-6.9b', 'pythia-6.9b-deduped']
# Условие R3 (HYPOTHESIS) не выполнено: самообман верхушки AGREE на пилоте 0,046 ≤ 0,15 (power.json: r3_gate) → R3 описательно.
R3_ACTIVE = False
# Описательно (PREREG §5, до данных теста): исключает ли ДИ теста эффект прежних опытов. Числа — из их json.
PRIOR = {'R1': [('OCCOR-01 R1', '2026-11-14_OCCOR-01', 'R1'), ('OCMIX-01 R3', '2026-11-14_OCMIX-01', 'R3')],
         'R2': [('OCCOR-01 R3', '2026-11-14_OCCOR-01', 'R3')]}
LEVEL = 0.0025
DESCR_LEVEL = 0.005
MIN_EACH, MAX_NONE, MIN_HEADS = 20, 0.05, 6
SEED_B = 1401
LR_FAIL_MAX = 0.01
MIN_OUT = 5                # совет 58: за границей BC меньше 5 повторов — метка «граница BC не определена»
BOOT_EVALS = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF', 'VETO', 'MIX-LR')
ALL_RULES = {'R1': ('ioi', 'LR-AGREE', 'AGREE'), 'R2': ('ioi', 'LR-AGREE', 'NB-IND'), 'R3': ('top', 'VETO', 'LR-AGREE')}
DESCR = {'NB−AGREE': ('ioi', 'NB-AGREE', 'AGREE'), 'FAM−AGREE': ('ioi', 'FAM-AGREE', 'AGREE'), 'MIX−LR': ('ioi', 'MIX-LR', 'LR-AGREE'),
         'CONF−LR': ('ioi', 'CONF', 'LR-AGREE'), 'R1_dT': ('T', 'LR-AGREE', 'AGREE'), 'R1_dC': ('C', 'LR-AGREE', 'AGREE'),
         'R2_dT': ('T', 'LR-AGREE', 'NB-IND'), 'R2_dC': ('C', 'LR-AGREE', 'NB-IND'), 'AGREEtop−CONFtop': ('top', 'AGREE', 'CONF'),
         'LRtop−CONFtop': ('top', 'LR-AGREE', 'CONF'), 'VETOtop−CONFtop': ('top', 'VETO', 'CONF')}
U = 'не определено (проверка метода)'
UL = 'не решено (LR: один класс в выборке ID больше чем в 1 % повторов)'


def val(r, kind, e):
    return r[e]['top10_sel']['deception'] if kind == 'top' else r[e][kind]


def prior_effects():
    """Эффекты C-086 (R1) и C-087 (R2) прежних тестов — из run/analysis.json тех опытов; плюс половина наименьшего по модулю."""
    out = {}
    for k, lst in PRIOR.items():
        v = {}
        for name, d, rule in lst:
            v[name] = float(json.load(open(os.path.join(os.path.dirname(HERE), d, 'run', 'analysis.json'), encoding='utf-8'))[rule]['delta'])
        v['половина наименьшего'] = max(v.values()) / 2
        assert all(x < 0 for x in v.values()), 'прежний эффект не отрицателен'   # совет 58
        out[k] = v
    return out


def prior_descr(e, prior):
    """Совет 58: эффект x < 0 «исключён», если нижняя граница выше x и у ДИ BC, и у процентильного ДИ (уровень правил);
    ни у одного — «не исключён»; у одного — «неустойчиво». Строка устойчивости рядом — то же по каждой половине повторов."""
    out = {}
    for name, x in prior.items():
        bc, pc = bool(e['ci'][0] > x), bool(e['ci_percentile'][0] > x)
        hv = [bool(h[0] > x and hp[0] > x) for h, hp in zip(e['tails']['halves'], e['tails']['halves_percentile'])]
        status = 'исключён' if bc and pc else ('не исключён' if not (bc or pc) else 'неустойчиво')
        out[name] = dict(effect=x, status=status, excluded_bc=bc, excluded_percentile=pc, excluded_halves=hv, halves_agree=bool(hv[0] == hv[1]))
    return out


def verdict(lo, hi):
    return 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не решено')


def verdict_conj(bc, pct):
    """Совет 58: вывод выносится, только если его дают оба ДИ — BC и процентильный. Если только один —
    «не решено (только BC)» или «не решено (только процентильный)». Конъюнкция может отменить вывод, но не создать."""
    vb, vp = verdict(*bc), verdict(*pct)
    if vb == vp:
        return vb
    if vp == 'не решено':
        return 'не решено (только BC)'
    if vb == 'не решено':
        return 'не решено (только процентильный)'
    return 'не решено (ДИ противоречат)'


def ci_entry(boot, point, level):
    b = np.asarray(boot, float)
    (lo, hi), z0 = Q.bc_ci(b, point, level)
    pq = [float(x) for x in np.quantile(b, (level, 1 - level))]
    n_out = dict(bc=[int((b < lo).sum()), int((b > hi).sum())], percentile=[int((b < pq[0]).sum()), int((b > pq[1]).sum())])
    und = [n_out['bc'][0] < MIN_OUT, n_out['bc'][1] < MIN_OUT]      # совет 58: только метка, вердикт не меняет
    note = '; '.join(f'граница BC не определена ({w}: за ней {n} повт.)' for w, n, u in zip(('нижняя', 'верхняя'), n_out['bc'], und) if u)
    return dict(delta=float(point), ci=[lo, hi], ci_percentile=pq, z0=z0, boot_median=float(np.median(b)), share_below_0=float(np.mean(b < 0)),
                level=level, n_out=n_out, bc_undetermined=und, bc_note=note)


def tails(boot, point, level):
    b = np.asarray(boot, float)
    (lo, hi), _ = Q.bc_ci(b, point, level)
    h = len(b) // 2
    halves = [Q.bc_ci(b[:h], point, level)[0], Q.bc_ci(b[h:], point, level)[0]]
    halves_pct = [[float(x) for x in np.quantile(q, (level, 1 - level))] for q in (b[:h], b[h:])]
    vh = [verdict_conj(x, y) for x, y in zip(halves, halves_pct)]
    return dict(n_below_lo=int((b < lo).sum()), n_above_hi=int((b > hi).sum()), halves=halves, halves_percentile=halves_pct, verdict_halves=vh,
                unstable=bool(vh[0] != vh[1]))


_ST = {}


def _init(st):
    _ST.clear()
    _ST.update(st)


def _init_worker(st):
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)
    _init(st)


def _pmap(fn, items, st, workers):
    if workers <= 1:
        _init(st)
        return [fn(x) for x in items]
    with mp.get_context('fork').Pool(workers, initializer=_init_worker, initargs=(st,)) as pool:
        return pool.map(fn, items, chunksize=max(1, len(items) // (8 * workers)))


def _rep(fc):
    s = _ST
    r = Q.crowd(s['ag'], s['corr'], s['logp'], s['fam'], s['allh'], fc[0], fc[1], evals=BOOT_EVALS)
    out = {k: val(r, kind, a) - val(r, kind, b) for k, (kind, a, b) in s['pairs'].items()}
    out['lr_one_class'] = r['LR-AGREE']['lr_one_class']
    return out


def main(out_dir, dst, B=10000, heads_test=None, r3_active=None, workers=1):
    r3_active = R3_ACTIVE if r3_active is None else r3_active
    assert r3_active is not None, 'R3_ACTIVE не закреплён'
    rules = {k: v for k, v in ALL_RULES.items() if k != 'R3' or r3_active}
    descr = dict(DESCR, **({} if r3_active else {'R3_descr': ALL_RULES['R3']}))
    d, heads_all = Q.load(out_dir)
    want = heads_test or HEADS_TEST or [Q.label(h) for h in heads_all]
    by = {Q.label(h): h for h in heads_all}
    missing = [w for w in want if w not in by]
    heads = [by[w] for w in want if w in by]
    ans, corr, rid, logp = Q.arrays(d, heads)
    assert np.isfinite(logp).all(), 'неконечный logp'
    names = [Q.label(h) for h in heads]
    fam = [Q.family(h) for h in heads]
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    allh = list(range(len(heads)))
    res = dict(split=d.get('split'), n_id=int(len(idi)), n_ood=int(len(ood)), heads=names, missing=missing, level=LEVEL,
               descr_level=DESCR_LEVEL, B=B, r3_active=bool(r3_active), rules=list(rules), top10_main='top10_sel',
               errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h])
    counts = {}
    for k in allh:
        counts[names[k]] = dict(id_correct=int(corr[k][rid].sum()), id_wrong=int((~corr[k][rid]).sum()),
                                ood_correct=int(corr[k][~rid].sum()), ood_wrong=int((~corr[k][~rid]).sum()),
                                none_frac=float(np.mean([a is None for a in ans[k]])))
    method_ok = (not missing and len(heads) >= MIN_HEADS and all(min(v['id_correct'], v['id_wrong'], v['ood_correct'], v['ood_wrong']) >= MIN_EACH
                                                                and v['none_frac'] <= MAX_NONE for v in counts.values()))
    res['method'] = dict(ok=bool(method_ok), counts=counts, n_heads=len(heads))
    res['accuracy'] = {names[k]: dict(id=float(corr[k][rid].mean()), ood=float(corr[k][~rid].mean())) for k in allh}
    ag = Q.agree_matrix(ans)
    sup = Q.supported(ag, allh)
    res['head_counts'] = {names[k]: dict(no_number=int(sum(a is None for a in ans[k])), unsupported_id=int((~sup[k][idi]).sum())) for k in allh}
    full = Q.crowd(ag, corr, logp, fam, allh, idi, ood, auroc=True)
    res['evaluators'] = full
    pairs = {**rules, **descr}
    g = np.random.default_rng(SEED_B)
    draws = [(g.choice(idi, len(idi)), g.choice(ood, len(ood))) for _ in range(B)]
    reps = _pmap(_rep, draws, dict(ag=ag, corr=corr, logp=logp, fam=fam, allh=allh, pairs=pairs), workers)
    n_fail = sum(1 for r in reps if r['lr_one_class'] > 0)
    res['lr_one_class'] = dict(reps=n_fail, share=n_fail / B)
    lr_bad = n_fail > LR_FAIL_MAX * B
    for k, (kind, a, b) in pairs.items():
        bk = [r[k] for r in reps]
        e = ci_entry(bk, val(full, kind, a) - val(full, kind, b), LEVEL if k in rules else DESCR_LEVEL)
        if k in rules:
            e['tails'] = tails(bk, e['delta'], LEVEL)
            e['monte_carlo_note'] = 'граница по Монте-Карло неустойчива' if e['tails']['unstable'] else ''
            e['verdict_bc'], e['verdict_percentile'] = verdict(*e['ci']), verdict(*e['ci_percentile'])
            e['verdict'] = U if not method_ok else (UL if lr_bad else verdict_conj(e['ci'], e['ci_percentile']))
        res[k if k in rules else f'descr_{k}'] = e
    lin = [n.split('@')[0].replace('-deduped', '') for n in names]
    other = np.array([ag[k][[o for o in allh if lin[o] != lin[k]]].any(0) for k in allh])
    cal = Q.Z.T.calibrate(Q.scores(ag, corr, logp, allh, idi, fam, ('VETO',))['VETO'], corr, idi, ood)
    tied = np.abs(cal - cal.max(0)[None, :]) <= 1e-12
    res['support_other_lineage_descr'] = dict(VETO=float(np.mean((other[:, ood] & tied).sum(0) / tied.sum(0))))
    cf = Q.crowd(ag, corr, logp, fam, allh, idi, ood, S=Q.crossfit_scores(ag, corr, logp, fam, allh, idi, ood))
    res['crossfit_descr'] = dict(evaluators=cf, rules={k: val(cf, kind, a) - val(cf, kind, b) for k, (kind, a, b) in ALL_RULES.items()})
    A_ = np.array([[-1 if x is None else x for x in a] for a in ans])
    wrong_all = (~corr[:, ood]).all(0)
    same_all = (A_[:, ood] == A_[0, ood][None, :]).all(0) & (A_[0, ood] >= 0)
    res['all_wrong_ood_descr'] = dict(all_wrong=float(wrong_all.mean()), all_wrong_same=float((wrong_all & same_all).mean()))
    pe = prior_effects()
    res['prior_effect_descr'] = {k: prior_descr(res[k], pe[k]) for k in pe}
    res['verdicts'] = {k: res[k]['verdict'] for k in rules}
    res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    print('ИОИ:', {e: round(v['ioi'], 4) for e, v in full.items()})
    print('верхушка:', {e: round(v['top10_sel']['deception'], 4) for e, v in full.items()})
    for k in rules:
        print(f"{k}: Δ {res[k]['delta']:.4f} ДИ [{res[k]['ci'][0]:.4f}, {res[k]['ci'][1]:.4f}] {res[k]['monte_carlo_note']}")
    print('LR, один класс в выборке ID:', res['lr_one_class'])
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    B = int(a[a.index('--boot') + 1]) if '--boot' in a else 10000
    W = int(a[a.index('--workers') + 1]) if '--workers' in a else (os.cpu_count() or 1)
    r3 = (a[a.index('--r3') + 1] == '1') if '--r3' in a else None
    main(a[0], a[1], B, r3_active=r3, workers=W)
