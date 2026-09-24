"""S2: «Алиса в стране чудес» на многих языках — меры и проверки строго по PLAN.md (коммит 954a110).
Запуск: python3 s2.py [каталог_глав]  (по умолчанию ~/alice_chapters; главы делает extract.py).
Пишет s2_results.json; печать — в s2.log (python3 s2.py > s2.log)."""
import json, os, re, sys, unicodedata
from collections import Counter
from statistics import median
import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
# слово — как в S1, плюс макаф и гереш иврита внутри слова (PLAN, «Меры»)
WORD = re.compile(r"[^\W\d_]+(?:[-'’־׳״][^\W\d_]+)*")
WORD_SPLIT_APOS = re.compile(r"[^\W\d_]+(?:[-־׳״][^\W\d_]+)*")   # E3: апостроф разделяет слова

LANGS = {   # язык -> тексты (коды manifest.json)
    'en': ['en'], 'de': ['de'], 'fr': ['fr_bue', 'fr_papy'], 'it': ['it'], 'es': ['es_1', 'es_2'],
    'eo': ['eo'], 'fi': ['fi'], 'ru': ['ru_dem', 'ru_nes'], 'cs': ['cs'], 'bg': ['bg'], 'he': ['he'],
}
CHAR_ONLY = ['ja', 'zh']            # без пробелов: только знаки
REFERENCE_ONLY = ['ru_zakh']        # пересказ: вне зачёта, только справка
PRIOR_RANK = {'fi': 1, 'hu': 2, 'et': 3, 'tr': 4, 'la': 5, 'ru': 6, 'pl': 7, 'cs': 8, 'uk': 9, 'is': 10, 'de': 11,
              'eo': 12, 'sv': 13, 'nl': 14, 'da': 15, 'it': 16, 'es': 17, 'pt': 18, 'en': 19, 'fr': 20}
ARTICLES = {
    'en': {'the', 'a', 'an'},
    'de': {'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einen', 'einem', 'einer', 'eines'},
    'fr': {'le', 'la', 'les', 'un', 'une', 'des'},
    'it': {'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una'},
    'es': {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas'},
    'eo': {'la'},
}
QA_LO, QA_HI = 0.5, 1.6


def norm(t):
    t = unicodedata.normalize('NFC', t)
    t = ''.join(ch for ch in t if unicodedata.category(ch) != 'Mn')   # огласовки, знаки ударения
    return t.lower()


def toks(t, rx=WORD):
    return rx.findall(norm(t))


def letters(t):
    return sum(1 for ch in norm(t) if unicodedata.category(ch).startswith('L'))


def zipf_alpha(tokens, R=100):
    f = np.array(sorted(Counter(tokens).values(), reverse=True)[:R], float)
    x = np.log10(np.arange(1, len(f) + 1)); y = np.log10(f)
    return float(-np.polyfit(x, y, 1)[0])


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/alice_chapters')
    load = lambda c: json.load(open(os.path.join(src, f'{c}.json')))
    texts = {c: load(c) for cs in LANGS.values() for c in cs}
    ch_toks = {c: [toks(ch) for ch in chs] for c, chs in texts.items()}
    W = {c: sum(map(len, t)) for c, t in ch_toks.items()}
    Wk = {c: [len(t) for t in ts] for c, ts in ch_toks.items()}
    r = {c: W[c] / W['en'] for c in texts}
    rk = {c: [a / b for a, b in zip(Wk[c], Wk['en'])] for c in texts}

    # --- отбор по PLAN: 12 глав и r_k в [0,5; 1,6]
    qa = {c: (len(texts[c]) == 12 and all(QA_LO <= v <= QA_HI for v in rk[c])) for c in texts}
    print('== Отбор (12 глав, r_k в [0,5; 1,6])')
    for c in texts:
        print(f'  {c:8s} {"в зачёте" if qa[c] else "ИСКЛЮЧЁН"}  r_k от {min(rk[c]):.3f} до {max(rk[c]):.3f}')
    ok = {c for c in texts if qa[c]}
    lang_texts = {L: [c for c in cs if c in ok] for L, cs in LANGS.items()}
    lang_texts = {L: cs for L, cs in lang_texts.items() if cs}

    # --- меры
    N = min(W[c] for c in ok)
    all_toks = {c: [w for t in ch_toks[c] for w in t] for c in texts}
    ttr = {c: len(set(all_toks[c][:N])) / N for c in ok}
    alpha = {c: zipf_alpha(all_toks[c]) for c in ok}
    let = {c: letters(' '.join(texts[c])) for c in texts}
    noart = {}
    for c in ok:
        L = next(L for L, cs in LANGS.items() if c in cs)
        if L in ARTICLES:
            noart[c] = sum(1 for w in all_toks[c] if w not in ARTICLES[L]) / W['en']
    med = lambda L, d: median(d[c] for c in lang_texts[L])
    R_ = {L: med(L, r) for L in lang_texts}
    T_ = {L: med(L, ttr) for L in lang_texts}
    A_ = {L: med(L, alpha) for L in lang_texts}
    LET_ = {L: med(L, {c: let[c] / let['en'] for c in texts}) for L in lang_texts}

    print(f'\n== Меры по текстам (N для TTR = {N})')
    print('  текст     W       r      TTR_N   α      буквы/en  r_без_артиклей')
    for c in sorted(ok, key=lambda c: r[c]):
        print(f'  {c:8s} {W[c]:6d}  {r[c]:.3f}  {ttr[c]:.4f}  {alpha[c]:.3f}  {let[c]/let["en"]:.3f}   {noart.get(c, float("nan")):.3f}')
    print('\n== По языкам (медиана переводов)')
    for L in sorted(R_, key=R_.get):
        print(f'  {L}  r={R_[L]:.3f}  TTR_N={T_[L]:.4f}  α={A_[L]:.3f}  буквы/en={LET_[L]:.3f}  переводы={lang_texts[L]}')

    res = {'N_ttr': N, 'qa': qa, 'W': W, 'r': r, 'r_k': rk, 'ttr_N': ttr, 'alpha': alpha,
           'letters': let, 'r_no_articles': noart, 'lang': {L: {'r': R_[L], 'ttr_N': T_[L], 'alpha': A_[L],
           'letters_rel': LET_[L], 'texts': lang_texts[L]} for L in R_}}

    # --- P4 (C-004)
    Ls = [L for L in R_ if L in PRIOR_RANK]
    rho4 = spearmanr([R_[L] for L in Ls], [PRIOR_RANK[L] for L in Ls]).statistic
    v4 = 'подтверждено' if rho4 >= 0.6 else ('опровергнуто' if rho4 < 0.3 else 'разницы нет')
    print(f'\n== P4 (C-004): Спирмен r ~ априорный ранг, n = {len(Ls)} ({",".join(Ls)}): ρ = {rho4:.3f} → {v4}')
    res['P4'] = {'n': len(Ls), 'langs': Ls, 'rho': rho4, 'verdict': v4}

    # --- P5 (C-005)
    Lmax = max(R_, key=R_.get); Lmin = min(R_, key=R_.get)
    v5 = 'подтверждено' if (Lmax in ('fr', 'en') and Lmin == 'fi') else 'опровергнуто'
    print(f'== P5 (C-005): самый болтливый {Lmax} (r = {R_[Lmax]:.3f}), самый краткий {Lmin} (r = {R_[Lmin]:.3f}) → {v5}; n = {len(R_)}')
    res['P5'] = {'max': Lmax, 'min': Lmin, 'n': len(R_), 'verdict': v5}

    # --- P6 (C-006)
    L6 = list(R_)
    rho6 = spearmanr([R_[L] for L in L6], [T_[L] for L in L6]).statistic
    v6 = 'подтверждено' if rho6 <= -0.6 else ('опровергнуто' if rho6 > -0.3 else 'разницы нет')
    print(f'== P6 (C-006): Спирмен r ~ TTR_N, n = {len(L6)}: ρ = {rho6:.3f} → {v6}')
    res['P6'] = {'n': len(L6), 'rho': rho6, 'verdict': v6}

    # --- P7 (C-007)
    Rru = R_['ru']
    art_L = [L for L in R_ if L in ARTICLES]
    NA_ = {L: median(noart[c] for c in lang_texts[L]) for L in art_L}
    a_rows = []
    for L in art_L:
        if R_[L] > Rru:
            a_rows.append((L, R_[L], NA_[L], abs(NA_[L] - Rru) < abs(R_[L] - Rru)))
    a = all(x[3] for x in a_rows)
    b = NA_['en'] > Rru
    v7 = 'подтверждено' if (a and b) else ('опровергнуто' if not b else 'частично')
    print(f'== P7 (C-007): R(ru) = {Rru:.3f}; en без артиклей = {NA_["en"]:.3f}')
    for L, rr, na, closer in a_rows:
        print(f'     {L}: r {rr:.3f} → без артиклей {na:.3f}; ближе к ru: {closer}')
    per_ru = {c: NA_['en'] > r[c] for c in lang_texts['ru']}
    print(f'     (a) {a}; (b) {b}; (b) против каждого русского перевода: {per_ru} → {v7}')
    res['P7'] = {'R_ru': Rru, 'no_art': NA_, 'a_rows': a_rows, 'a': a, 'b': b, 'b_per_ru_text': per_ru, 'verdict': v7}

    # --- P8 (C-008)
    lang_rk = {L: [median(rk[c][k] for c in lang_texts[L]) for k in range(12)] for L in R_}
    signs = [lang_rk[Lmax][k] - lang_rk[Lmin][k] for k in range(12)]
    npos = sum(s > 0 for s in signs)
    v8 = 'подтверждено' if npos == 12 else ('разницы нет' if npos >= 10 else 'опровергнуто')
    print(f'== P8 (C-008): {Lmax} длиннее {Lmin} в {npos} из 12 глав → {v8}')
    res['P8'] = {'pair': [Lmin, Lmax], 'n_pos': npos, 'diffs': signs, 'verdict': v8}

    # --- разведочно
    print('\n== E1 переводчик против языка')
    e1 = {L: (lang_texts[L], [r[c] for c in lang_texts[L]]) for L in R_ if len(lang_texts[L]) > 1}
    for L, (cs, rs) in e1.items():
        print(f'  {L}: ' + ', '.join(f'{c} {v:.3f}' for c, v in zip(cs, rs)) + f'  разброс {max(rs) - min(rs):.3f}')
    vals = sorted(R_.values())
    print(f'  между языками: размах медиан {vals[-1] - vals[0]:.3f}; межквартильный {np.percentile(vals, 75) - np.percentile(vals, 25):.3f}')
    res['E1'] = {L: dict(zip(cs, rs)) for L, (cs, rs) in e1.items()}
    res['E1_between'] = {'range': vals[-1] - vals[0], 'iqr': float(np.percentile(vals, 75) - np.percentile(vals, 25))}

    print('\n== E2 самые частые слова (доля от всех слов текста)')
    top = {}
    for c in list(ok) + [x for x in REFERENCE_ONLY]:
        tk = all_toks[c] if c in all_toks else [w for ch in load(c) for w in toks(ch)]
        cnt = Counter(tk).most_common(5)
        top[c] = [(w, n, n / len(tk)) for w, n in cnt]
        print(f'  {c:8s} ' + '  '.join(f'{w} {n} ({n / len(tk):.1%})' for w, n, _ in top[c]))
    res['E2_top'] = top

    print('\n== E2 знаки: японский и китайский, справка — пересказ Заходера')
    ref = {}
    for c in CHAR_ONLY:
        chs = load(c)
        ref[c] = {'letters': letters(' '.join(chs)), 'letters_rel_en': letters(' '.join(chs)) / let['en'], 'chapters': len(chs)}
        print(f'  {c}: знаков письма {ref[c]["letters"]}, к буквам английского {ref[c]["letters_rel_en"]:.3f}')
    for c in REFERENCE_ONLY:
        chs = load(c); w = sum(len(toks(ch)) for ch in chs)
        ref[c] = {'W': w, 'r': w / W['en'], 'chapters': len(chs)}
        print(f'  {c}: W {w}, r {w / W["en"]:.3f}, глав {len(chs)} (пересказ, вне зачёта)')
    res['E2_ref'] = ref

    print('\n== E3 апостроф разделяет слова (fr, it)')
    e3 = {}
    for c in [x for x in ('fr_bue', 'fr_papy', 'it') if x in ok]:
        w2 = sum(len(toks(ch, WORD_SPLIT_APOS)) for ch in texts[c])
        e3[c] = {'W_split': w2, 'r_split': w2 / W['en'], 'r': r[c]}
        print(f'  {c}: r {r[c]:.3f} → {w2 / W["en"]:.3f}')
    res['E3'] = e3

    print('\n== Главы, отклонённые от медианы языка больше чем на 15 %')
    flags = []
    for L in R_:
        m = median(lang_rk[L])
        for k, v in enumerate(lang_rk[L], 1):
            if abs(v / m - 1) > 0.15:
                flags.append((L, k, v, m)); print(f'  {L} глава {k}: r_k {v:.3f} при медиане {m:.3f}')
    res['chapter_flags'] = flags

    json.dump(res, open(os.path.join(HERE, 's2_results.json'), 'w'), ensure_ascii=False, indent=1, default=float)


if __name__ == '__main__':
    main()
