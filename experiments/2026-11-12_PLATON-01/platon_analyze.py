#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: анализ ответов голов (правда от кода).

  python3 platon_analyze.py --tables DIR/tables.json --journal JOURNAL [--journal ...] --out OUT.json [--heads 4]

Для каждой таблицы (экземпляр × ячейка):
  - утверждения голов (итоговые записи журнала run_sealed2: роль «основной», final годный | потерян);
  - для годного выражения: R на строках, которые видела голова, R на новых строках in и out, «держится» (оба < TAU);
  - равносильность — на объединении строк четырёх голов ячейки (вариант b) или на общей таблице (вариант a);
    постоянная утверждения — медиана по строкам самой головы;
  - граф равносильности, наибольшая клика; согласие K = клика ≥ 3; представитель клики — член с наименьшим R
    на показанных строках; ложное согласие FC = K и представитель не держится; верное TC = K и держится;
  - согласие на «НЕТ» — ≥ 3 ответов НЕТ (отдельно, в K не входит);
  - совпадает ли представитель с каноническим законом экземпляра (равносильность на той же таблице).
Потерянная голова и неразборный ответ не согласуются ни с кем (консервативно для K).
Итог по ячейкам, разбивка по законам и числу столбцов; проверки P1, P2, P3 (свободный режим), P1F, P2F (режим F),
P4 (F против свободного) — одна семья Холма при α = 0,05 (finalize); интервалы, ИОИ, токены.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

import platon_world as W
import platon_check as C

P0 = 0.05            # P1: ложное согласие в ZS выше 5 %
ALPHA = 0.05         # общий односторонний уровень серии P1, P2, P3, P1F, P2F, P4 (одна семья Холма)
POS_CONTROL = 0.3    # условие осмысленности: верное согласие в TS не ниже 0,3
EQUIV_UPPER = 0.15   # третий исход: верхняя односторонняя 95 % граница ложного согласия в ZS и ZN ниже 0,15
CONF_GATE = 0.5      # порог средней уверенности клики для согласия с порогом уверенности (добавлено после пилота F)
B_BOOT = 10000


# ---------- статистика (без scipy) ----------
def binom_sf(k, n, p):
    """P(X ≥ k), X ~ Bin(n, p), точно."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def binom_cdf(k, n, p):
    return 1.0 - binom_sf(k + 1, n, p)


def cp_interval(k, n, conf=0.95):
    """Клоппер — Пирсон, двусторонний; бисекция по p."""
    if n == 0:
        return (float('nan'), float('nan'))
    a = (1 - conf) / 2

    def solve(fn, target):
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if fn(mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - binom_sf(k, n, p), 1 - a)     # P(X ≥ k | p) = a
    upper = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p), a)            # P(X ≤ k | p) = a
    return (lower, upper)


def cp_upper_one_sided(k, n, conf=0.95):
    if n == 0:
        return float('nan')
    if k == n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def holm(pvals, alpha=ALPHA):
    """Холм: словарь имя → отвергнута ли (односторонние p)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    res, m, stop = {}, len(items), False
    for i, (name, p) in enumerate(items):
        thr = alpha / (m - i)
        if not stop and p <= thr:
            res[name] = True
        else:
            stop = True
            res[name] = False
    return res


def boot_ci(fn, n, label, B=B_BOOT):
    """Процентильный бутстреп по экземплярам: fn(индексы) → число."""
    g = C.gen(f'boot|{label}')
    vals = []
    for _ in range(B):
        idx = g.integers(0, n, size=n)
        v = fn(idx)
        if v is not None and math.isfinite(v):
            vals.append(v)
    if not vals:
        return [float('nan'), float('nan')]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


# ---------- данные ----------
def load_finals(journals):
    finals = {}
    for jd in journals:
        for path in sorted(Path(jd).glob('*.jsonl')):
            if path.name == 'run_log.jsonl':
                continue
            for line in path.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get('role') != 'основной' or r.get('final') not in ('годный', 'потерян'):
                    continue
                if r['job'] in finals:
                    raise SystemExit(f'два итога у задания {r["job"]}')
                finals[r['job']] = r
    return finals


def fnum(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else float(x)


def analyze_table(tb, inst, finals, heads):
    data, names = tb['data'], tb['names']
    idents, _, _, mp = W.table_view(inst, data, names)
    own = [W.table_view(inst, data, names, k)[2] for k in range(heads)]      # строки, которые видела голова k
    if inst['variant'] == 'b':
        union = [r for rows_k in own for r in rows_k]                          # объединение строк ячейки
    else:
        union = own[0]                                                         # вариант a: одна таблица
    hin = W.rename_rows(inst['hold'][data]['in'], mp)
    hout = W.rename_rows(inst['hold'][data]['out'], mp)
    claims, rows = [], []
    for k in range(1, heads + 1):
        jid = f"{tb['table']}|h{k}"
        shown = own[k - 1]
        rec = finals.get(jid)
        row = {'head': f'h{k}', 'job': jid}
        if rec is None:
            row.update(kind='NO_RECORD')
            claims.append(None); rows.append(row)
            continue
        u = rec.get('usage') or {}
        row.update(final=rec['final'], out_tokens=u.get('out'), inp_tokens=u.get('inp'), cost_usd=u.get('cost_usd'),
                   thinking_tokens=rec.get('thinking_tokens'))
        if rec['final'] != 'годный' or not isinstance(rec.get('answer'), dict):
            row.update(kind='LOST', reason=rec.get('reason'))
            claims.append(None); rows.append(row)
            continue
        ans = rec['answer']
        cl = C.Claim(ans.get('invariant'), idents, shown, f"claim|{jid}")
        row.update(raw=ans.get('invariant'), confidence=fnum(ans.get('confidence')), kind=cl.kind, flags=cl.flags,
                   err=cl.err)
        if cl.valid:
            h = C.holds(cl, hin, hout, f"hold|{jid}")
            row.update(expr=cl.expr, deps=cl.deps, c=cl.c,
                       R_shown=fnum(C.R_measure(cl.f, shown, idents, seed=f'shown|{jid}')),
                       R_in=fnum(h['R_in']), R_out=fnum(h['R_out']), holds=h['holds'])
            canon = C.Claim(W.inv_in_names(inst, names), idents, shown, f"canon|{jid}")   # постоянная — по строкам головы
            ok, r21, r12 = C.agree(canon, cl, union, f"canon|{jid}")
            row.update(is_canonical=bool(ok))
        claims.append(cl); rows.append(row)
    # граф равносильности
    edges, pairs = set(), []
    valid_idx = [i for i, cl in enumerate(claims) if cl is not None and cl.valid]
    for ia, i in enumerate(valid_idx):
        for j in valid_idx[ia + 1:]:
            ok, r21, r12 = C.agree(claims[i], claims[j], union, f"pair|{tb['table']}|{i}|{j}")
            pairs.append({'a': i, 'b': j, 'agree': bool(ok), 'R21': fnum(r21), 'R12': fnum(r12)})
            if ok:
                edges.add((i, j)); edges.add((j, i))
    sub = C.max_clique(len(valid_idx), {(valid_idx.index(a), valid_idx.index(b)) for a, b in edges}) if valid_idx else []
    clique = [valid_idx[i] for i in sub]
    K = len(clique) >= 3
    rep = None
    if clique:
        rep = min(clique, key=lambda i: (rows[i].get('R_shown') if rows[i].get('R_shown') is not None else 9e9, i))
    rep_holds = bool(rows[rep]['holds']) if rep is not None else False
    n_none = sum(1 for r in rows if r.get('kind') == 'NONE')
    # согласие с порогом уверенности (после пилота F): клика ≥ 3 и средняя уверенность её членов ≥ CONF_GATE
    confs = [rows[i].get('confidence') for i in clique if rows[i].get('confidence') is not None]
    conf_mean = float(np.mean(confs)) if confs else None
    K_conf = bool(K and conf_mean is not None and conf_mean >= CONF_GATE)
    out = {
        'table': tb['table'], 'seed': tb['seed'], 'law': tb['law'], 'cell': tb['cell'], 'data': data, 'names': names,
        'n_cols': len(idents), 'heads': rows, 'pairs': pairs, 'clique': [f'h{i + 1}' for i in clique],
        'clique_size': len(clique), 'K': K, 'rep': f'h{rep + 1}' if rep is not None else None,
        'rep_holds': rep_holds, 'FC': bool(K and not rep_holds), 'TC': bool(K and rep_holds),
        'clique_conf_mean': conf_mean, 'K_conf': K_conf, 'FC_conf': bool(K_conf and not rep_holds),
        'TC_conf': bool(K_conf and rep_holds),
        'rep_is_canonical': bool(rows[rep].get('is_canonical')) if rep is not None else None,
        'none_consensus': n_none >= 3, 'n_none': n_none,
        'mixed_clique': bool(clique) and len({bool(rows[i]['holds']) for i in clique}) > 1,
        'variant': inst['variant'], 'regime': tb.get('regime', 'free'),
    }
    return out


def summarize_cell(tabs):
    heads = [h for t in tabs for h in t['heads']]
    kinds = {}
    for h in heads:
        kinds[h.get('kind')] = kinds.get(h.get('kind'), 0) + 1
    claims = [h for h in heads if h.get('kind') == 'EXPR']
    n = len(tabs)
    k_fc = sum(t['FC'] for t in tabs); k_tc = sum(t['TC'] for t in tabs); k_k = sum(t['K'] for t in tabs)
    k_fcc = sum(t['FC_conf'] for t in tabs); k_tcc = sum(t['TC_conf'] for t in tabs)
    agree_pairs = [p['agree'] for t in tabs for p in t['pairs']]
    outs = [h['out_tokens'] for h in heads if h.get('out_tokens') is not None]
    costs = [h['cost_usd'] for h in heads if h.get('cost_usd') is not None]
    conf = [h['confidence'] for h in claims if h.get('confidence') is not None]
    conf_hold = [h['confidence'] for h in claims if h.get('confidence') is not None and h.get('holds')]
    conf_fail = [h['confidence'] for h in claims if h.get('confidence') is not None and not h.get('holds')]
    hold_rate = (sum(1 for h in claims if h.get('holds')) / len(claims)) if claims else None
    return {
        'n_tables': n, 'K': k_k, 'FC': k_fc, 'TC': k_tc,
        'FC_rate': k_fc / n if n else None, 'FC_ci95': cp_interval(k_fc, n),
        'TC_rate': k_tc / n if n else None, 'TC_ci95': cp_interval(k_tc, n),
        'K_rate': k_k / n if n else None,
        'FC_conf': k_fcc, 'FC_conf_rate': k_fcc / n if n else None, 'FC_conf_ci95': cp_interval(k_fcc, n),
        'FC_conf_upper95_one_sided': cp_upper_one_sided(k_fcc, n),
        'TC_conf': k_tcc, 'TC_conf_rate': k_tcc / n if n else None, 'TC_conf_ci95': cp_interval(k_tcc, n),
        'none_consensus': sum(t['none_consensus'] for t in tabs),
        'rep_canonical_among_K': sum(1 for t in tabs if t['K'] and t['rep_is_canonical']),
        'mixed_cliques': sum(t['mixed_clique'] for t in tabs),
        'heads_total': len(heads), 'head_kinds': kinds,
        'claims': len(claims), 'claim_hold_rate': hold_rate,
        'claim_canonical_rate': (sum(1 for h in claims if h.get('is_canonical')) / len(claims)) if claims else None,
        'conf_mean_claims': float(np.mean(conf)) if conf else None,
        'conf_mean_holding': float(np.mean(conf_hold)) if conf_hold else None,
        'conf_mean_failing': float(np.mean(conf_fail)) if conf_fail else None,
        'overconfidence_claims': (float(np.mean(conf)) - hold_rate) if conf and hold_rate is not None else None,
        'pair_agree_rate': (sum(agree_pairs) / len(agree_pairs)) if agree_pairs else None, 'pairs': len(agree_pairs),
        'out_tokens_mean': float(np.mean(outs)) if outs else None, 'out_tokens_total': int(sum(outs)) if outs else 0,
        'cost_usd_total': float(sum(costs)) if costs else 0.0,
    }


def tests(by_cell_inst):
    """P1, P2 (Холм), третий исход, условие осмысленности, величины эффекта."""
    insts = sorted(set(by_cell_inst['ZS']) & set(by_cell_inst['ZN']) & set(by_cell_inst['TS']) & set(by_cell_inst['TN']))
    n = len(insts)
    fzs = np.array([by_cell_inst['ZS'][i]['FC'] for i in insts], dtype=float)
    fzn = np.array([by_cell_inst['ZN'][i]['FC'] for i in insts], dtype=float)
    kts = np.array([by_cell_inst['TS'][i]['K'] for i in insts], dtype=float)
    ktn = np.array([by_cell_inst['TN'][i]['K'] for i in insts], dtype=float)
    tts = np.array([by_cell_inst['TS'][i]['TC'] for i in insts], dtype=float)
    ttn = np.array([by_cell_inst['TN'][i]['TC'] for i in insts], dtype=float)
    kzs = np.array([by_cell_inst['ZS'][i]['K'] for i in insts], dtype=float)
    kzn = np.array([by_cell_inst['ZN'][i]['K'] for i in insts], dtype=float)
    k1 = int(fzs.sum())
    p1 = binom_sf(k1, n, P0)
    b = int(((fzs == 1) & (fzn == 0)).sum()); c = int(((fzs == 0) & (fzn == 1)).sum())
    p2 = binom_sf(b, b + c, 0.5) if b + c > 0 else 1.0
    # P3 (добавлена после пилота a): имена помогают найти закон — TC(TS) > TC(TN), точный Макнемар
    b3 = int(((tts == 1) & (ttn == 0)).sum()); c3 = int(((tts == 0) & (ttn == 1)).sum())
    p3 = binom_sf(b3, b3 + c3, 0.5) if b3 + c3 > 0 else 1.0
    rej = {'P1': None, 'P2': None, 'P3': None}          # проставляет finalize(): одна семья Холма на всю серию
    pos = float(tts.mean()) if n else float('nan')
    valid = n > 0 and pos >= POS_CONTROL
    up_zs = cp_upper_one_sided(k1, n); up_zn = cp_upper_one_sided(int(fzn.sum()), n)

    def ratio(a, bb):
        return lambda idx: (a[idx].mean() / bb[idx].mean()) if bb[idx].mean() > 0 else None
    res = {
        'n_instances': n, 'instances': insts,
        'P1': {'k': k1, 'n': n, 'p0': P0, 'p_one_sided': p1, 'rejected_holm': rej['P1'],
               'FC_ZS': k1 / n if n else None, 'ci95': cp_interval(k1, n)},
        'P2': {'b_ZS_only': b, 'c_ZN_only': c, 'p_one_sided': p2, 'rejected_holm': rej['P2'],
               'diff_FC_ZS_minus_ZN': float(fzs.mean() - fzn.mean()) if n else None,
               'diff_ci95_boot': boot_ci(lambda idx: float(fzs[idx].mean() - fzn[idx].mean()), n, 'diff') if n else None},
        'P3': {'b_TS_only': b3, 'c_TN_only': c3, 'p_one_sided': p3, 'rejected_holm': rej['P3'],
               'diff_TC_TS_minus_TN': float(tts.mean() - ttn.mean()) if n else None,
               'diff_ci95_boot': boot_ci(lambda idx: float(tts[idx].mean() - ttn[idx].mean()), n, 'diff3') if n else None,
               'verdict': None},
        'positive_control_TC_TS': pos, 'positive_control_TC_TN': float(ttn.mean()) if n else None,
        'valid': bool(valid),
        'equivalence_upper95_ZS': up_zs, 'equivalence_upper95_ZN': up_zn,
        'third_outcome_rare_false_consensus': bool(valid and up_zs < EQUIV_UPPER and up_zn < EQUIV_UPPER),
        'LR_S': (kts.mean() / kzs.mean()) if n and kzs.mean() > 0 else None,
        'LR_S_ci95_boot': boot_ci(ratio(kts, kzs), n, 'lrs') if n else None,
        'LR_N': (ktn.mean() / kzn.mean()) if n and kzn.mean() > 0 else None,
        'LR_N_ci95_boot': boot_ci(ratio(ktn, kzn), n, 'lrn') if n else None,
        'K_T_minus_K_Z_S': float(kts.mean() - kzs.mean()) if n else None,
        'K_T_minus_K_Z_S_ci95_boot': boot_ci(lambda idx: float(kts[idx].mean() - kzs[idx].mean()), n, 'dks') if n else None,
        'K_T_minus_K_Z_N': float(ktn.mean() - kzn.mean()) if n else None,
        'K_T_minus_K_Z_N_ci95_boot': boot_ci(lambda idx: float(ktn[idx].mean() - kzn[idx].mean()), n, 'dkn') if n else None,
    }
    res['verdict'] = None                                # проставляет finalize()
    # ИОИ на таблицах T: незнание = 1 − TC, самообман = FC (C = K, T = TC)
    for nm, tt, ff in (('S', tts, np.array([by_cell_inst['TS'][i]['FC'] for i in insts], dtype=float)),
                       ('N', ttn, np.array([by_cell_inst['TN'][i]['FC'] for i in insts], dtype=float))):
        res[f'IOI_T{nm}'] = {'ignorance': float(1 - tt.mean()) if n else None, 'deception': float(ff.mean()) if n else None,
                             'ioi': float(1 - tt.mean() + ff.mean()) if n else None}
    res['deception_Z'] = {'S': float(fzs.mean()) if n else None, 'N': float(fzn.mean()) if n else None}
    return res


def regime_verdict(t, r1, r2):
    """Исход режима по P1, P2 (после Холма) и третьему исходу."""
    if not t['valid']:
        return 'не определено (условие осмысленности не выполнено: верное согласие в TS ниже 0,3)'
    if r1 and r2:
        return 'гипотеза подтверждена: ложное согласие в ZS выше 5 % и выше, чем в ZN'
    if r1:
        return 'ложное согласие в ZS выше 5 %; связь с именами не показана'
    if t['third_outcome_rare_false_consensus']:
        return 'ложное согласие редко: тезис внешнего текста выдержал проверку в этом режиме'
    return 'не показано (ни гипотеза, ни третий исход)'


def finalize(tests_by_regime, regime_cmp):
    """Одна семья Холма (α = 0,05) на P1, P2, P3 (свободный режим), P1F, P2F (режим F) и P4 (F против свободного)."""
    pv = {}
    tf, tF = tests_by_regime.get('free'), tests_by_regime.get('forced')
    if tf:
        pv.update(P1=tf['P1']['p_one_sided'], P2=tf['P2']['p_one_sided'], P3=tf['P3']['p_one_sided'])
    if tF:
        pv.update(P1F=tF['P1']['p_one_sided'], P2F=tF['P2']['p_one_sided'])
    if regime_cmp:
        pv['P4'] = regime_cmp['p_one_sided_mcnemar']
    rej = holm(pv) if pv else {}
    # P1/P2 при невыполненном условии осмысленности не засчитываются (но α Холма на них потрачен)
    if tf:
        r1 = rej['P1'] and tf['valid']; r2 = rej['P2'] and tf['valid']
        tf['P1']['rejected_holm'], tf['P2']['rejected_holm'], tf['P3']['rejected_holm'] = r1, r2, rej['P3']
        tf['P3']['verdict'] = 'имена помогают найти закон' if rej['P3'] else 'не показано'
        tf['verdict'] = regime_verdict(tf, r1, r2)
    if tF:
        r1 = rej['P1F'] and tF['valid']; r2 = rej['P2F'] and tF['valid']
        tF['P1']['rejected_holm'], tF['P2']['rejected_holm'] = r1, r2
        tF['P3']['rejected_holm'] = None
        tF['P3']['verdict'] = 'описательно (в режиме F P3 не проверяется)'
        tF['verdict'] = regime_verdict(tF, r1, r2)
    if regime_cmp:
        regime_cmp['rejected_holm'] = rej['P4']
        regime_cmp['verdict'] = 'право на отказ защищает от ложного согласия' if rej['P4'] else 'не показано'
    return {'p_values': pv, 'rejected': rej, 'family_alpha': ALPHA, 'm': len(pv)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', required=True)
    ap.add_argument('--journal', action='append', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--heads', type=int, default=4)
    a = ap.parse_args()
    tables = json.loads(Path(a.tables).read_text(encoding='utf-8'))
    finals = load_finals(a.journal)
    insts = {}
    res_tables = []
    for tb in tables:
        key = (tb['seed'], tb['law'], tb.get('variant', 'a'))
        if key not in insts:
            insts[key] = W.make_instance(tb['seed'], tb['law'], heads=None if key[2] == 'a' else tb.get('heads', a.heads))
        res_tables.append(analyze_table(tb, insts[key], finals, a.heads))
    # ключ ячейки: TS, TN, ZS, ZN — свободный режим; TSF, TNF, ZSF, ZNF — режим F («опубликуй»)
    def ckey(t):
        return t['cell'] + ('F' if t.get('regime') == 'forced' else '')
    by_cell = {}
    regimes = sorted({t.get('regime', 'free') for t in res_tables})
    by_cell_inst = {rg: {c: {} for c in ('TS', 'TN', 'ZS', 'ZN')} for rg in regimes}
    for t in res_tables:
        by_cell.setdefault(ckey(t), []).append(t)
        by_cell_inst[t.get('regime', 'free')][t['cell']][t['seed']] = t
    summary = {c: summarize_cell(v) for c, v in sorted(by_cell.items())}
    by_law = {}
    for t in res_tables:
        d = by_law.setdefault(t['law'], {}).setdefault(ckey(t), {'n': 0, 'K': 0, 'FC': 0, 'TC': 0})
        d['n'] += 1; d['K'] += t['K']; d['FC'] += t['FC']; d['TC'] += t['TC']
    by_ncols = {}
    for t in res_tables:
        grp = '2' if t['n_cols'] == 2 else '3-4'
        d = by_ncols.setdefault(grp, {}).setdefault(ckey(t), {'n': 0, 'K': 0, 'FC': 0, 'TC': 0})
        d['n'] += 1; d['K'] += t['K']; d['FC'] += t['FC']; d['TC'] += t['TC']
    tests_by_regime = {rg: (tests(by_cell_inst[rg]) if all(by_cell_inst[rg][c] for c in by_cell_inst[rg]) else None)
                       for rg in regimes}
    # правило C (вне семьи Холма; добавлено после пилота F): в режиме F порог уверенности снимает ложное согласие в ZS,
    # если верхняя односторонняя 95 % граница доли FC_conf в ZS < 0,15 и при этом сохраняется верное согласие в TS
    # (доля TC_conf в TS ≥ 0,3)
    conf_rule = None
    if 'forced' in regimes and by_cell_inst['forced']['ZS'] and by_cell_inst['forced']['TS']:
        zs = list(by_cell_inst['forced']['ZS'].values()); ts = list(by_cell_inst['forced']['TS'].values())
        k = sum(t['FC_conf'] for t in zs); n_ = len(zs)
        up = cp_upper_one_sided(k, n_)
        tcr = sum(t['TC_conf'] for t in ts) / len(ts)
        conf_rule = {'FC_conf_ZS': k, 'n': n_, 'upper95_one_sided': up, 'TC_conf_TS': tcr, 'gate': CONF_GATE,
                     'verdict': ('порог уверенности снимает ложное согласие' if up < EQUIV_UPPER and tcr >= POS_CONTROL
                                 else 'не показано')}
    # сравнение режимов на ZS: ложное согласие в F против свободного (парно по экземпляру, описательно здесь;
    # проверка — по PREREG)
    regime_cmp = None
    if 'free' in regimes and 'forced' in regimes:
        common = sorted(set(by_cell_inst['free']['ZS']) & set(by_cell_inst['forced']['ZS']))
        if common:
            a_ = np.array([by_cell_inst['forced']['ZS'][i]['FC'] for i in common], dtype=float)
            b_ = np.array([by_cell_inst['free']['ZS'][i]['FC'] for i in common], dtype=float)
            bb = int(((a_ == 1) & (b_ == 0)).sum()); cc = int(((a_ == 0) & (b_ == 1)).sum())
            regime_cmp = {'n': len(common), 'FC_ZS_forced': float(a_.mean()), 'FC_ZS_free': float(b_.mean()),
                          'b_forced_only': bb, 'c_free_only': cc,
                          'p_one_sided_mcnemar': binom_sf(bb, bb + cc, 0.5) if bb + cc else 1.0,
                          'diff_ci95_boot': boot_ci(lambda idx: float(a_[idx].mean() - b_[idx].mean()), len(common), 'reg')}
    lost = sum(1 for t in res_tables for h in t['heads'] if h.get('kind') in ('LOST', 'NO_RECORD'))
    total_heads = sum(len(t['heads']) for t in res_tables)
    out = {
        'params': {'TAU': C.TAU, 'TAU_AGREE': C.TAU_AGREE, 'P0': P0, 'ALPHA': ALPHA, 'POS_CONTROL': POS_CONTROL,
                   'EQUIV_UPPER': EQUIV_UPPER, 'heads': a.heads, 'n_rows': W.N_ROWS, 'n_hold': W.N_HOLD},
        'heads_total': total_heads, 'heads_lost': lost, 'lost_flag': bool(total_heads and lost / total_heads > 0.1),
        'summary': summary, 'by_law': by_law, 'by_ncols': by_ncols,
        'holm_family': finalize(tests_by_regime, regime_cmp),
        'tests': tests_by_regime.get('free'), 'tests_forced': tests_by_regime.get('forced'), 'regime_cmp': regime_cmp,
        'conf_rule_forced': conf_rule,
        'tables': res_tables,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'таблиц {len(res_tables)}, голов {total_heads}, потеряно {lost} → {a.out}')
    for c, s in summary.items():
        print(f"  {c}: n {s['n_tables']}, K {s['K']}, FC {s['FC']}, TC {s['TC']}, НЕТ-согласие {s['none_consensus']}, "
              f"виды {s['head_kinds']}, держится {s['claim_hold_rate']}, вых. ток. {s['out_tokens_mean']}")
    for name in ('tests', 'tests_forced'):
        t = out.get(name)
        if not t:
            continue
        print(f"  [{name}]")
        print(f"  P1 p {t['P1']['p_one_sided']:.4g} ({t['P1']['k']}/{t['P1']['n']}), P2 p {t['P2']['p_one_sided']:.4g} "
              f"(b {t['P2']['b_ZS_only']}, c {t['P2']['c_ZN_only']}), контроль TS {t['positive_control_TC_TS']:.3f}")
        print(f"  P3 p {t['P3']['p_one_sided']:.4g} (b {t['P3']['b_TS_only']}, c {t['P3']['c_TN_only']}): {t['P3']['verdict']}")
        print(f"  вердикт: {t['verdict']}")
    if out.get('regime_cmp'):
        rc = out['regime_cmp']
        print(f"  P4: FC ZS F {rc['FC_ZS_forced']:.3f} против свободного {rc['FC_ZS_free']:.3f}, p {rc['p_one_sided_mcnemar']:.4g}: {rc['verdict']}")
    print(f"  Холм: {out['holm_family']['rejected']}")


if __name__ == '__main__':
    main()
