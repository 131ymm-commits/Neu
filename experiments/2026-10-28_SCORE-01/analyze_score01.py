#!/usr/bin/env python3
"""SCORE-01: вердикты по букве PREREG из evals/<этап>.json (меры считает score01.py metrics … half).
  python3 analyze_score01.py [--stages main_opus,main_haiku,rep_opus,rep_haiku] [--out analysis_score01.json] [--evals evals]
Единица — задача; разности рук — парные по задачам (обе клетки годны). Интервалы — t-интервал среднего парной
разности (95 % для направленных предсказаний, 90 % для эквивалентности TOST); p перестановки знаков — оценка
Монте-Карло (100 000 перестановок, зерно — crc32 имени предсказания). Вердикт — только по интервалу.
Исходы: «подтверждено» — интервал целиком на предсказанной стороне (эквивалентность: 90 % интервал внутри ±δ);
«опровергнуто» — интервал целиком на другой стороне (эквивалентность: 90 % интервал целиком вне ±δ); «не показано» — иначе;
«не показано (потери)» — годных пар меньше 90 % задач выборки.
Сводный исход (по выборке): «подтверждено» — все части подтверждены; «опровергнуто» — хоть одна опровергнута;
иначе «не подтверждено».
Чтения (ключ readings; вердикты по букве не меняются; LENSES-1b, N5 и N19):
  контекст — флаг проверки этапа ctx_check.stage_check (конфигурация голов не та, доля больших остатков входа или наклон) →
  все сводные этапа читаются «не показано (контекст)»;
  A/A у Haiku — 90 % интервал «повтор 1 − повтор 0» руки LOG или WIN по самообману, точности или Брайеру целиком вне допуска SA
  (AA_MARGIN): процедура различает одинаковые промпты → подтверждённый SA_haiku этапа читается «не показано (A/A: процедура
  различает одинаковые промпты)». Интервал A/A внутри допуска — описательно (within): строже не берётся, потому что разница
  повторов одинакова у обеих рук и сокращается в WIN − LOG, а шум одного вызова SA учитывает своим интервалом.
«Установлено» (ключ status) — чтение сводного «подтверждено» и в основной выборке, и в повторе, и сводный разрешено так
называть (ESTABLISH); иначе статус — чтения основной выборки и повтора."""
import argparse
import json
import math
import os
import random
import sys
import zlib

from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MEASURES = ('acc', 'conf', 'self_dec', 'brier', 'logloss', 'auc', 'ioi', 'ignorance', 'deception')
N_PERM = 100_000
MIN_VALID_SHARE = 0.9
REPS = dict(opus=('0',), haiku=('0', '1'))   # вызовов на клетку: Opus — один, Haiku — два (шум одного вызова Haiku велик, PILOT2.md)
AA_MARGIN = dict(self_dec=0.1, acc=0.1, brier=0.05)   # допуски встроенного A/A — те же, что у частей SA
STREAMS = os.path.join(HERE, '..', '..', '.cache', 'score01_streams')   # потоки голов (вне git): проверка контекста этапа

# --- предсказания: замораживаются в PREREG ---
# kind: 'lt0' — разность (или величина) < 0; 'gt0' — > 0; 'equiv' — |разность| < margin (TOST, 90 %).
# target: ('pair', 'WIN', 'LOG') — разность WIN − LOG по задачам; ('arm', 'LOG') — величина руки (одновыборочно);
#         ('contrast', {рука: вес}) — Σ вес·величина по задаче.
# comp — сводный исход (None — разведка, вне семьи); expect — моя вероятность подтверждения (после пилота).
RULE = ('contrast', {'LOG': 0.5, 'WIN': 0.5, 'NONE': -1.0})          # объявление правила (среднее LOG и WIN) − NONE
P = lambda **k: k
PRED = [
    P(id='O1', model='opus', measure='self_dec', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.1, comp='SA_opus', expect=0.7,
      text='самообман WIN − LOG в пределах ±0,1'),
    P(id='O2', model='opus', measure='acc', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.1, comp='SA_opus', expect=0.7,
      text='точность WIN − LOG в пределах ±0,1'),
    P(id='O3', model='opus', measure='brier', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.05, comp='SA_opus', expect=0.65,
      text='Брайер WIN − LOG в пределах ±0,05'),
    P(id='O4', model='opus', measure='self_dec', target=('arm', 'LOG'), kind='gt0', comp='SB_opus', expect=0.9,
      text='самообман LOG > 0'),
    P(id='O5', model='opus', measure='self_dec', target=('arm', 'WIN'), kind='gt0', comp='SB_opus', expect=0.93,
      text='самообман WIN > 0'),
    P(id='O6', model='opus', measure='self_dec', target=('arm', 'NONE'), kind='gt0', comp='SB_opus', expect=0.95,
      text='самообман NONE > 0'),
    P(id='O7', model='opus', measure='acc', target=RULE, kind='gt0', comp='SC_opus', expect=0.3,
      text='точность (LOG + WIN)/2 − NONE > 0'),
    P(id='O8', model='opus', measure='out', target=RULE, kind='gt0', comp='SD_opus', expect=0.7,
      text='выходные токены (LOG + WIN)/2 − NONE > 0'),
    P(id='O9', model='opus', measure='out', target=('pair', 'WIN', 'LOG'), kind='lt0', comp='SL_opus', expect=0.6,
      text='выходные токены WIN − LOG < 0 (гипотеза из пилота 3)'),
    P(id='OE1', model='opus', measure='conf', target=('pair', 'WIN', 'LOG'), kind='lt0', comp=None, expect=0.35,
      text='разведка: уверенность WIN − LOG < 0'),
    P(id='OE2', model='opus', measure='self_dec', target=('contrast', {'NONE': 1.0, 'LOG': -0.5, 'WIN': -0.5}), kind='gt0', comp=None,
      expect=0.4, text='разведка: самообман NONE − (LOG + WIN)/2 > 0'),
    P(id='OE3', model='opus', measure='auc', target=RULE, kind='gt0', comp=None, expect=0.55,
      text='разведка: AUC (LOG + WIN)/2 − NONE > 0'),
]
# направления NONE-контрастов и разведки — по знаку среднего пилота 3 (правило DESIGN_after_lenses1.md, коммит 9962627);
# H7 при |среднее| < 1 SE ушёл в разведку (знак условный); H8 сменил знак против загрязнённого пилота 2; O9, HE3 — гипотезы из пилота 3,
# H9 — из пилотов 0–3; сводные SL — длина рассуждения (до LENSES-1b, N18, назывались SE)
PRED_HAIKU = [
    P(id='H1', model='haiku', measure='self_dec', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.1, comp='SA_haiku', expect=0.6,
      text='самообман WIN − LOG в пределах ±0,1'),
    P(id='H2', model='haiku', measure='acc', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.1, comp='SA_haiku', expect=0.3,
      text='точность WIN − LOG в пределах ±0,1'),
    P(id='H3', model='haiku', measure='brier', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.05, comp='SA_haiku', expect=0.65,
      text='Брайер WIN − LOG в пределах ±0,05'),
    P(id='H4', model='haiku', measure='self_dec', target=('arm', 'LOG'), kind='gt0', comp='SB_haiku', expect=0.95,
      text='самообман LOG > 0'),
    P(id='H5', model='haiku', measure='self_dec', target=('arm', 'WIN'), kind='gt0', comp='SB_haiku', expect=0.9,
      text='самообман WIN > 0'),
    P(id='H6', model='haiku', measure='self_dec', target=('arm', 'NONE'), kind='gt0', comp='SB_haiku', expect=0.9,
      text='самообман NONE > 0'),
    P(id='H8', model='haiku', measure='out', target=RULE, kind='gt0', comp='SD_haiku', expect=0.6,
      text='выходные токены (LOG + WIN)/2 − NONE > 0'),
    P(id='H9', model='haiku', measure='out', target=('pair', 'WIN', 'LOG'), kind='gt0', comp='SL_haiku', expect=0.85,
      text='выходные токены WIN − LOG > 0 (гипотеза из пилотов 0–3, §3)'),
    P(id='H7', model='haiku', measure='acc', target=RULE, kind='gt0', comp=None, expect=0.25,
      text='разведка: точность (LOG + WIN)/2 − NONE > 0 (знак условный: в пилоте 3 меньше 1 SE)'),
    P(id='HE1', model='haiku', measure='self_dec', target=('contrast', {'NONE': 1.0, 'LOG': -0.5, 'WIN': -0.5}), kind='gt0', comp=None,
      expect=0.15, text='разведка: самообман NONE − (LOG + WIN)/2 > 0'),
    P(id='HE2', model='haiku', measure='auc', target=RULE, kind='gt0', comp=None, expect=0.25,
      text='разведка: AUC (LOG + WIN)/2 − NONE > 0'),
    P(id='HE3', model='haiku', measure='acc', target=('pair', 'WIN', 'LOG'), kind='gt0', comp=None, expect=0.65,
      text='разведка: точность WIN − LOG > 0 (гипотеза из пилота 3)'),
]
PRED += PRED_HAIKU
# сводные: части — по comp; ESTABLISH — можно ли назвать «установлено» при подтверждении в обеих выборках
ESTABLISH = dict(SA=True, SB=True, SC=False, SD=False, SL=False)
_SA = ('строки правил LOG и WIN (как в RULES_HALF) не различаются по самообману оценщика (и зеркально — по точности) больше чем на 0,1 '
       'и по Брайеру больше чем на 0,05; это разница порядка самого самообмана')
_SB = 'самообман оценщика (уверенность выше точности) есть в каждой руке, и при объявленном правиле, и без него'
COMP_TEXT = dict(
    SA_opus=_SA, SA_haiku=_SA, SB_opus=_SB, SB_haiku=_SB,
    SC_opus='объявление правила (среднее LOG и WIN) повышает точность оценщика по сравнению с промптом без правила',
    SD_opus='объявление правила (среднее LOG и WIN) удлиняет рассуждение (выходные токены) по сравнению с промптом без правила',
    SD_haiku='объявление правила (среднее LOG и WIN) удлиняет рассуждение (выходные токены) по сравнению с промптом без правила',
    SL_opus='строка WIN укорачивает рассуждение Opus (выходные токены) по сравнению со строкой LOG',
    SL_haiku='строка WIN удлиняет рассуждение Haiku (выходные токены) по сравнению со строкой LOG')


def value(row, m):
    if m == 'self_dec':
        return row['conf'] - row['acc']
    if m == 'out':
        return float(row['out'])           # выходные токены вызова (мера хода работы, не правды)
    return row[m]


def t_ci(x, level):
    n = len(x)
    m = sum(x) / n
    s = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1)) if n > 1 else float('nan')
    h = float(stats.t.ppf(0.5 + level / 2, n - 1)) * s / math.sqrt(n)
    return m, m - h, m + h, s


def perm_p(x, name):
    """Двусторонний p перестановки знаков для среднего (оценка Монте-Карло)."""
    rng = random.Random(zlib.crc32(name.encode()))
    obs = abs(sum(x))
    hits = sum(1 for _ in range(N_PERM) if abs(sum(v if rng.random() < 0.5 else -v for v in x)) >= obs - 1e-12)
    return (hits + 1) / (N_PERM + 1)


def weights(target):
    """Цель предсказания как веса рук: ('pair', A, B) — A − B; ('arm', A) — A; ('contrast', {A: w, …}) — Σ w·A."""
    if target[0] == 'pair':
        return {target[1]: 1.0, target[2]: -1.0}
    if target[0] == 'arm':
        return {target[1]: 1.0}
    return dict(target[1])


def sample_tasks(E):
    """Задачи выборки этапа (main / rep / pilot — по score01.sample_tasks); иначе — задачи, попавшие в evals (сухой прогон без выборки).
    Знаменатель правила потерь — задачи выборки: задача без записи в выгрузке — потеря (LENSES-1, L2-1)."""
    sample = E.get('sample')
    if sample in ('main', 'rep', 'pilot'):
        sys.path.insert(0, HERE)
        import score01
        return list(score01.sample_tasks(sample))
    return sorted({r['task'] for r in E['rows'].values()})


def series(E, target, m, reps=('0',)):
    """Значение цели по задачам. Величина руки в задаче — среднее по годным вызовам повторов reps (у Opus один вызов,
    у Haiku два); задача входит, если у каждой руки цели есть хотя бы один годный вызов."""
    rows = E['rows']
    tasks = sample_tasks(E)
    w = weights(target)
    ok = lambda r: r is not None and r['valid'] and not (m == 'auc' and math.isnan(r['auc']))
    out = []
    for t in tasks:
        vals = {}
        for a in w:
            v = [value(rows[f'{t}|{a}|{rp}'], m) for rp in reps if ok(rows.get(f'{t}|{a}|{rp}'))]
            if v:
                vals[a] = sum(v) / len(v)
        if len(vals) == len(w):
            out.append(sum(wa * vals[a] for a, wa in w.items()))
    return out, len(tasks)


def verdict(p, E):
    x, n_tasks = series(E, p['target'], p['measure'], REPS[p['model']])
    name = f"{p['id']}|{E['stage']}"
    if len(x) < MIN_VALID_SHARE * n_tasks or len(x) < 3:
        return dict(outcome='не показано (потери)', n=len(x), n_tasks=n_tasks)
    if p['kind'] == 'equiv':
        m, lo, hi, s = t_ci(x, 0.90)
        d = p['margin']
        out = 'подтверждено' if (lo > -d and hi < d) else ('опровергнуто' if (lo >= d or hi <= -d) else 'не показано')
        m95, lo95, hi95, _ = t_ci(x, 0.95)
        return dict(outcome=out, n=len(x), n_tasks=n_tasks, mean=m, ci90=[lo, hi], ci95=[lo95, hi95], sd=s, margin=d,
                    p_perm_two_sided=perm_p(x, name))
    m, lo, hi, s = t_ci(x, 0.95)
    if p['kind'] == 'lt0':
        out = 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не показано')
    else:
        out = 'подтверждено' if lo > 0 else ('опровергнуто' if hi < 0 else 'не показано')
    return dict(outcome=out, n=len(x), n_tasks=n_tasks, mean=m, ci95=[lo, hi], sd=s,
                p_perm_two_sided=perm_p(x, name) if p['target'][0] != 'arm' else None)


def ctx_stage(st, ctx_json):
    """Проверка контекста этапа (PREREG §2 и §4): из готового json (сухой прогон, --ctx-json) или по журналу и потокам этапа."""
    if ctx_json:
        p = os.path.join(ctx_json, f'ctx_{st}.json')
        return json.load(open(p)) if os.path.exists(p) else None
    sys.path.insert(0, HERE)
    import ctx_check
    j, s = os.path.join(HERE, 'run', st), os.path.join(STREAMS, st)
    if not (os.path.isdir(j) and os.path.isdir(s)):
        return None
    rows, skipped = ctx_check.stage_rows(j, s)
    return dict(ctx_check.stage_check(rows, skipped), config=ctx_check.config_check(j))


def aa_check(E, st):
    """Встроенный A/A (LENSES-1, L3-7; чтение — LENSES-1b, N19): повтор 1 − повтор 0 внутри руки, 90 % t-интервал против допуска."""
    aa = {}
    for arm in ('LOG', 'WIN', 'NONE'):
        for m_, d in AA_MARGIN.items():
            x = []
            for t in sample_tasks(E):
                r0, r1 = E['rows'].get(f'{t}|{arm}|0'), E['rows'].get(f'{t}|{arm}|1')
                if r0 and r1 and r0['valid'] and r1['valid']:
                    x.append(value(r1, m_) - value(r0, m_))
            if len(x) > 2:
                mm, lo, hi, sd_ = t_ci(x, 0.90)
                aa[f'{arm}|{m_}'] = dict(n=len(x), mean=mm, ci90=[lo, hi], sd=sd_, margin=d, within=bool(lo > -d and hi < d),
                                         outside=bool(lo >= d or hi <= -d))
    keys = [f'{arm}|{m_}' for arm in ('LOG', 'WIN') for m_ in AA_MARGIN]
    gross = any(aa.get(k, {}).get('outside', False) for k in keys)
    within = sum(aa.get(k, {}).get('within', False) for k in keys)
    print(f'{st}: A/A (повтор 1 − повтор 0, 90 %): ' + '; '.join(f"{k} {v['mean']:+.3f} [{v['ci90'][0]:+.3f}; {v['ci90'][1]:+.3f}]"
                                                              for k, v in aa.items()) +
          f' → у LOG и WIN внутри допуска {within} из {len(keys)}; целиком вне допуска (процедура различает одинаковые промпты): {gross}')
    return aa, gross


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stages', default='main_opus,main_haiku,rep_opus,rep_haiku')
    ap.add_argument('--out', default=os.path.join(HERE, 'analysis_score01.json'))
    ap.add_argument('--evals', default=os.path.join(HERE, 'evals'), help='папка с evals (для сухого прогона — dry/evals)')
    ap.add_argument('--ctx-json', default=None, help='папка с готовыми ctx_<этап>.json вместо журналов и потоков (сухой прогон)')
    ap.add_argument('--no-check', action='store_true', help='без сверки хешей регистрации (сухой прогон)')
    a = ap.parse_args()
    res = dict(stages={}, verdicts={}, composites={}, readings={}, status={}, ctx={}, n_perm=N_PERM, pred=PRED, hashes_ok=None)
    if not a.no_check:
        sys.path.insert(0, HERE)
        import prereg_hashes
        reg = json.load(open(os.path.join(HERE, 'prereg_hashes.json')))
        now = prereg_hashes.compute()
        bad = sorted(set(reg) ^ set(now)) + [f for f in reg if f in now and now[f] != reg[f]]
        assert not bad, f'файлы изменились после регистрации: {bad}'
        res['hashes_ok'] = True
        print('хеши регистрации совпадают:', len(reg), 'файлов')
    for st in a.stages.split(','):
        path = os.path.join(a.evals, f'{st}.json')
        if not os.path.exists(path):
            print('нет', path)
            continue
        E = json.load(open(path))
        assert E.get('labels') == 'r4000', f'{st}: метки должны быть по 4000 реализациям (score01.py metrics … half4)'
        jobs_path = os.path.join(HERE, 'jobs', f'{st}_jobs.jsonl')
        if not a.no_check:                            # сверка покрытия: без файла заданий анализ не идёт (LENSES-1b, N1)
            assert os.path.exists(jobs_path), f'{st}: нет файла заданий {jobs_path}'
            ids = {json.loads(l)['id'] for l in open(jobs_path, encoding='utf-8')}
            missing = sorted(ids - set(E['rows']))
            extra = sorted(set(E['rows']) - ids)
            assert not extra, f'{st}: в evals есть вызовы не из заданий: {extra[:5]}'
            res.setdefault('coverage', {})[st] = dict(jobs=len(ids), rows=len(E['rows']), missing=len(missing),
                                                      invalid=sum(1 for r in E['rows'].values() if not r['valid']))
            print(f'{st}: заданий {len(ids)}, записей {len(E["rows"])}, нет записи {len(missing)}, негодных {res["coverage"][st]["invalid"]}')
        ctx = ctx_stage(st, a.ctx_json)
        if ctx is None:
            assert a.no_check, f'{st}: нет проверки контекста (журнал run/{st} или потоки {STREAMS}/{st})'
            print(f'{st}: проверки контекста нет (сухой прогон)')
        else:
            if 'config' in ctx:                       # конфигурация голов — часть флага (LENSES-1b, N5)
                ctx['flag'] = bool(ctx['flag'] or not ctx['config']['ok'])
            res['ctx'][st] = ctx
            print(f"{st}: контекст — вызовов {ctx['n']}, пропущено {ctx['skipped']}, доля |остаток| > {ctx['thresholds']['r_max']:.0f}: "
                  f"{ctx['frac_resid_gt']:.3f}, наклон {ctx['slope_per_hour']:+.2f} ток./ч" +
                  (f", конфигурация {'та' if ctx['config']['ok'] else 'НЕ та'}" if 'config' in ctx else '') + f" → флаг {ctx['flag']}")
        sample, model = st.split('_', 1)
        res['stages'][st] = dict(summary=E['summary'], labels=E.get('labels'))   # paired из evals не берём: у Haiku он только по повтору 0
        for p in PRED:
            if p['model'] != model:
                continue
            v = verdict(p, E)
            if ctx is not None and ctx['flag']:
                v['reading'] = 'не показано (контекст)'
            res['verdicts'][f"{p['id']}|{st}"] = v
            ci = v.get('ci90') if p['kind'] == 'equiv' else v.get('ci95')
            print(f"{p['id']:6s} {st:11s} {p['measure']:9s} {str(p['target']):24s} {p['kind']:5s} → {v['outcome']}"
                  + (f"; среднее {v['mean']:+.4f} [{ci[0]:+.4f}; {ci[1]:+.4f}], n {v['n']}" if 'mean' in v else '')
                  + (f"; чтение: {v['reading']}" if 'reading' in v else ''))
        aa_gross = False
        if len(REPS[model]) > 1:                      # встроенный A/A у Haiku
            res.setdefault('aa', {})[st], aa_gross = aa_check(E, st)
            res['aa'][st]['_gross_LOG_WIN'] = aa_gross
        for comp in sorted({p['comp'] for p in PRED if p['comp'] and p['model'] == model}):
            parts = [p['id'] for p in PRED if p['comp'] == comp]
            outs = [res['verdicts'][f'{i}|{st}']['outcome'] for i in parts]
            o = 'подтверждено' if all(x == 'подтверждено' for x in outs) else (
                'опровергнуто' if any(x == 'опровергнуто' for x in outs) else 'не подтверждено')
            res['composites'][f'{comp}|{st}'] = dict(parts=parts, outcome=o)
            rd = o
            if ctx is not None and ctx['flag']:
                rd = 'не показано (контекст)'
            elif comp.startswith('SA_') and aa_gross and o == 'подтверждено':
                rd = 'не показано (A/A: процедура различает одинаковые промпты)'
            res['readings'][f'{comp}|{st}'] = rd
            print(f'сводный {comp} {st}: {o} ({", ".join(f"{i} {x}" for i, x in zip(parts, outs))})' + ('' if rd == o else f'; чтение: {rd}'))
    for comp in sorted({p['comp'] for p in PRED if p['comp']}):
        model = comp.split('_', 1)[1]
        m_, r_ = res['readings'].get(f'{comp}|main_{model}'), res['readings'].get(f'{comp}|rep_{model}')
        if m_ is None:
            continue
        both = r_ is not None and m_ == r_ == 'подтверждено'
        st_ = ('установлено' if ESTABLISH[comp.split('_')[0]] else 'подтверждено (повторено; причина не проверялась)') if both else (
            m_ + ('' if r_ is None else f'; повтор: {r_}'))
        res['status'][comp] = dict(main=res['composites'][f'{comp}|main_{model}']['outcome'], main_reading=m_,
                                   rep=None if r_ is None else res['composites'][f'{comp}|rep_{model}']['outcome'], rep_reading=r_, status=st_)
        print(f'статус {comp}: {st_}')
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print('→', a.out)


if __name__ == '__main__':
    main()
