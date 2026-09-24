"""S2, ПОСТ-ХОК (дополнен после адверсарного ревью 24.09: точное p, E3 симметрично, флаги по переводам, удвоенные буквы, иврит, E1 в относительных единицах)
S2, ПОСТ-ХОК (после вердиктов, вердикты не меняет): устойчивость к выбору переводчика и точные p для ρ.
Перебираются все сочетания «по одному переводу на язык» (fr 2 × es 2 × ru 2 = 8) и пересчитываются P4–P6, P8.
Читает s2_results.json; пишет s2_posthoc.json."""
import itertools, json, os
import numpy as np
from scipy.stats import spearmanr
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 's2_results.json')))
PRIOR = {'fi': 1, 'ru': 6, 'cs': 8, 'de': 11, 'eo': 12, 'it': 16, 'es': 17, 'en': 19, 'fr': 20}
langs = {L: v['texts'] for L, v in R['lang'].items()}
multi = [L for L, cs in langs.items() if len(cs) > 1]

def exact_p(rho, n, side):
    # точное p: распределение суммы d² по всем n! перестановкам (динамика по маскам), без Монте-Карло
    from collections import defaultdict
    dp = {0: {0: 1}}
    for i in range(n):
        nxt = defaultdict(lambda: defaultdict(int))
        for mask, dist in dp.items():
            for j in range(n):
                if not mask >> j & 1:
                    for s2, c in dist.items():
                        nxt[mask | 1 << j][s2 + (i - j) ** 2] += c
        dp = nxt
    dist = dp[(1 << n) - 1]; tot = sum(dist.values())
    rho_of = lambda s2: 1 - 6 * s2 / (n * (n * n - 1))
    hit = sum(c for s2, c in dist.items() if (rho_of(s2) >= rho - 1e-12 if side == 'ge' else rho_of(s2) <= rho + 1e-12))
    return hit / tot

out = {'p_exact': {}}
p4 = R['P4']; p6 = R['P6']
out['p_exact']['P4'] = exact_p(p4['rho'], p4['n'], 'ge')
out['p_exact']['P6'] = exact_p(p6['rho'], p6['n'], 'le')
print(f"точное p: P4 ρ={p4['rho']:.3f}, n={p4['n']}: p={out['p_exact']['P4']:.5f};  P6 ρ={p6['rho']:.3f}, n={p6['n']}: p={out['p_exact']['P6']:.5f}")

rows = []
for combo in itertools.product(*[langs[L] for L in multi]):
    pick = {L: (dict(zip(multi, combo))[L] if L in multi else langs[L][0]) for L in langs}
    r = {L: R['r'][c] for L, c in pick.items()}
    t = {L: R['ttr_N'][c] for L, c in pick.items()}
    Ls = [L for L in r if L in PRIOR]
    rho4 = spearmanr([r[L] for L in Ls], [PRIOR[L] for L in Ls]).statistic
    rho6 = spearmanr(list(r.values()), [t[L] for L in r]).statistic
    lmax = max(r, key=r.get); lmin = min(r, key=r.get)
    d = [R['r_k'][pick[lmax]][k] - R['r_k'][pick[lmin]][k] for k in range(12)]
    row = {'выбор': {L: pick[L] for L in multi}, 'rho4': rho4, 'rho6': rho6, 'max': lmax, 'min': lmin,
           'P5': lmax in ('fr', 'en') and lmin == 'fi', 'P8_n': sum(x > 0 for x in d),
           'top3': sorted(r, key=r.get, reverse=True)[:3], 'bottom3': sorted(r, key=r.get)[:3]}
    rows.append(row)
    print(f"{row['выбор']}: ρ4={rho4:.3f} ρ6={rho6:.3f} болтливее всех {lmax}, короче всех {lmin}, P5={row['P5']}, P8 {row['P8_n']}/12; топ-3 {row['top3']}")
out['combos'] = rows
out['summary'] = {'P4_confirmed': sum(r['rho4'] >= 0.6 for r in rows), 'P5_confirmed': sum(r['P5'] for r in rows),
                  'P6_confirmed': sum(r['rho6'] <= -0.6 for r in rows), 'P8_12of12': sum(r['P8_n'] == 12 for r in rows), 'n': len(rows),
                  'max_counts': {L: sum(r['max'] == L for r in rows) for L in set(r['max'] for r in rows)},
                  'min_counts': {L: sum(r['min'] == L for r in rows) for L in set(r['min'] for r in rows)}}
print('итог по 8 сочетаниям:', out['summary'])
json.dump(out, open(os.path.join(HERE, 's2_posthoc.json'), 'w'), ensure_ascii=False, indent=1, default=float)

# ---------- дополнения после адверсарного ревью (вердикты не меняют) ----------
import re, sys, unicodedata
from collections import Counter
from statistics import median
sys.path.insert(0, HERE)
import s2
CH = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/alice_chapters')
texts = {c: json.load(open(os.path.join(CH, f'{c}.json'))) for c in R['W']}
rev = {}

# E3 симметрично: апостроф делит слова во ВСЕХ текстах, включая английский знаменатель
Wsplit = {c: sum(len(s2.toks(ch, s2.WORD_SPLIT_APOS)) for ch in texts[c]) for c in texts}
rev['E3_symmetric'] = {c: Wsplit[c] / Wsplit['en'] for c in texts}
print('\nE3 симметрично (все тексты, и английский):', {c: round(v, 3) for c, v in rev['E3_symmetric'].items() if c in ('en', 'fr_bue', 'fr_papy', 'it', 'es_1', 'fi')})
print('  английский: слов с апострофом', Wsplit['en'] - R['W']['en'])

# флаги глав по каждому переводу (против медианы самого перевода)
flags = []
for c, rk in R['r_k'].items():
    m = median(rk)
    for k, v in enumerate(rk, 1):
        if abs(v / m - 1) > 0.15:
            flags.append((c, k, v, m))
rev['chapter_flags_per_text'] = flags
print('флаги глав по переводам (>15 % от медианы перевода):', [(c, k, round(v, 3), round(m, 3)) for c, k, v, m in flags])

# английская глава X без стихов изданий 1886 года: насколько это объясняет «короткую» гл. X у ранних переводов
import importlib
en_mod = importlib.import_module('extractors.en')
en_mod.KEEP_LATER_EDITION_VERSES = False
man = json.load(open(os.path.join(HERE, 'manifest.json')))
cache = os.path.expanduser('~/alice_cache') if not os.path.isdir('/home/user/ext/cache') else '/home/user/ext/cache'
en_1865 = en_mod.chapters([os.path.join(cache, p['file']) for p in man['en']])
w10_1865 = len(s2.toks(en_1865[9])); w10 = len(s2.toks(texts['en'][9]))
rev['en_ch10_1886_verses_words'] = w10 - w10_1865
rev['ch10_rk_vs_1865'] = {c: len(s2.toks(texts[c][9])) / w10_1865 for c in ('de', 'fr_bue', 'it', 'fi', 'he')}
print(f'стихи 1886 г. в англ. гл. X: {w10 - w10_1865} слов; r_k гл. X к тексту без них:', {c: round(v, 3) for c, v in rev["ch10_rk_vs_1865"].items()})

# финский: удвоенные буквы (долгие гласные и согласные) — если считать их за одну
def letters_collapsed(t):
    t = ''.join(ch for ch in s2.norm(t) if unicodedata.category(ch).startswith('L') or ch == ' ')
    return len(re.sub(r'(.)\1', r'\1', t).replace(' ', ''))
lc = {c: letters_collapsed(' '.join(texts[c])) for c in ('fi', 'en', 'de', 'fr_bue', 'it')}
rev['letters_doubles_collapsed_rel_en'] = {c: v / lc['en'] for c, v in lc.items()}
dbl = {c: len(re.findall(r'(\w)\1', ' '.join(s2.toks(' '.join(texts[c]))))) for c in ('fi', 'en')}
rev['doubled_pairs'] = dbl
print('буквы, удвоенные считаются за одну, к англ.:', {c: round(v, 3) for c, v in rev['letters_doubles_collapsed_rel_en'].items()}, '; удвоений fi/en:', dbl)

# иврит: сколько раз названа Алиса и сколько раз «она» — против английского
he_t = [w for ch in texts['he'] for w in s2.toks(ch)]
en_t = [w for ch in texts['en'] for w in s2.toks(ch)]
rev['he_alice'] = {'bare': he_t.count('עליסה'), 'with_prefix': sum(1 for w in he_t if w.endswith('עליסה')), 'hi': he_t.count('היא')}
rev['en_alice'] = {'alice': en_t.count('alice'), "alice's": sum(1 for w in en_t if w in ("alice's", 'alice’s')), 'she': en_t.count('she')}
rev['alice_count_all'] = {c: sum(1 for w in (x for ch in texts[c] for x in s2.toks(ch)) if w.startswith(('alic', 'алис', 'алиц', 'alenk', 'liis', 'alis'))) for c in texts}
print('иврит:', rev['he_alice'], ' английский:', rev['en_alice'])

# E1 в относительных единицах и типичная разница между языками
rel = {L: max(d.values()) / min(d.values()) - 1 for L, d in R['E1'].items()}
Lr = [v['r'] for v in R['lang'].values()]
pair = [abs(a - b) for i, a in enumerate(Lr) for b in Lr[i + 1:]]
rev['E1_relative'] = rel
rev['E1_pairwise_lang'] = {'mean': float(np.mean(pair)), 'median': float(np.median(pair)), 'share_below_0.09': float(np.mean([p < 0.09 for p in pair]))}
rev['E1_max_over_min_lang'] = max(Lr) / min(Lr) - 1
print('E1 относительно:', {k: round(v, 3) for k, v in rel.items()}, 'пары языков:', {k: round(v, 3) for k, v in rev['E1_pairwise_lang'].items()}, 'макс/мин:', round(rev['E1_max_over_min_lang'], 3))

# P7 против каждого русского перевода для всех языков с артиклями
rev['P7_noart_vs_each_ru'] = {L: {c: R['P7']['no_art'][L] > R['r'][c] for c in R['lang']['ru']['texts']} for L in R['P7']['no_art']}
print('без артиклей длиннее каждого русского перевода:', rev['P7_noart_vs_each_ru'])

# французские инверсии через дефис (dit-elle) — сколько слов добавило бы разделение
inv = re.compile(r"-(?:t-)?(?:elle|elles|il|ils|je|tu|nous|vous|on|ce|moi|toi|lui|leur|le|la|les)$")
rev['fr_inversions'] = {c: sum(1 for ch in texts[c] for w in s2.toks(ch) if inv.search(w)) for c in ('fr_bue', 'fr_papy')}
print('французские инверсии через дефис:', rev['fr_inversions'])

# ничьи: у кого разница меньше наибольшего разброса переводчиков (0,09 англ. длины)
spread = max(max(d.values()) - min(d.values()) for d in R['E1'].values())
order = sorted(R['lang'], key=lambda L: R['lang'][L]['r'])
rev['ties_below_translator_spread'] = [(a, b, R['lang'][b]['r'] - R['lang'][a]['r']) for a, b in zip(order, order[1:]) if R['lang'][b]['r'] - R['lang'][a]['r'] < spread]
print('соседи ближе, чем разброс переводчиков', round(spread, 3), ':', [(a, b, round(d, 3)) for a, b, d in rev['ties_below_translator_spread']])

# разрывы для текста отчёта: краткие против болтливых, отрыв финского, французская медиана при симметричном E3
lr = {L: v['r'] for L, v in R['lang'].items()}
rev['gap_short_vs_talkative'] = lr['de'] - max(lr['fi'], lr['he'], lr['cs'])
rev['fi_lead'] = {'he': lr['he'] - lr['fi'], 'cs': lr['cs'] - lr['fi']}
rev['E3_symmetric_fr_median'] = median([rev['E3_symmetric']['fr_bue'], rev['E3_symmetric']['fr_papy']])
print('разрыв краткие–болтливые:', round(rev['gap_short_vs_talkative'], 3), 'отрыв финского:', {k: round(v, 3) for k, v in rev['fi_lead'].items()}, 'fr медиана E3 симм.:', round(rev['E3_symmetric_fr_median'], 3))

out['review'] = rev
json.dump(out, open(os.path.join(HERE, 's2_posthoc.json'), 'w'), ensure_ascii=False, indent=1, default=float)
