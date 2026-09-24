# S1: TTR при равной длине и наклон Ципфа, ru против en, 16 пар глав «Основания 1.3». Строго по PLAN.md.
import re, json, glob, os, math
from collections import Counter
import numpy as np

SRC = os.path.join(os.path.dirname(__file__), '..', '..', 'sources', 'foundation_1.3')
WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")


def tokens(path):
    t = open(path, encoding='utf-8').read()
    t = re.sub(r'```.*?```', ' ', t, flags=re.S)             # блоки кода
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)           # ссылки markdown -> текст
    t = re.sub(r'`[^`]*`', ' ', t)                            # имена файлов в `...`
    return WORD.findall(t.lower())


def zipf_alpha(toks, R=100):
    f = np.array(sorted(Counter(toks).values(), reverse=True), float)
    r = min(R, len(f))
    x, y = np.log10(np.arange(1, r + 1)), np.log10(f[:r])
    return float(-np.polyfit(x, y, 1)[0]), r


names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SRC, 'en', '*.md')))
pairs = [n for n in names if os.path.exists(os.path.join(SRC, 'ru', n)) and not n.startswith('15_')]
rows = []
for n in pairs:
    ru, en = tokens(os.path.join(SRC, 'ru', n)), tokens(os.path.join(SRC, 'en', n))
    N = min(len(ru), len(en))
    ttr_ru, ttr_en = len(set(ru[:N])) / N, len(set(en[:N])) / N
    a_ru, r_ru = zipf_alpha(ru); a_en, r_en = zipf_alpha(en)
    rows.append(dict(chapter=n, tokens_ru=len(ru), tokens_en=len(en), len_ratio=round(len(ru) / len(en), 3), N=N,
                     ttr_ru=round(ttr_ru, 4), ttr_en=round(ttr_en, 4), alpha_ru=round(a_ru, 4), alpha_en=round(a_en, 4),
                     ranks_ru=r_ru, ranks_en=r_en))
    print(rows[-1], flush=True)

k1 = sum(r['ttr_ru'] > r['ttr_en'] for r in rows); k2 = sum(r['alpha_ru'] < r['alpha_en'] for r in rows)
verdict = lambda k: 'подтверждено' if k >= 13 else ('опровергнуто' if k <= 8 else 'разницы нет')
tail = lambda k: sum(math.comb(16, m) for m in range(k, 17)) / 2 ** 16

# P3 разведочно: весь корпус
RU = sum((tokens(os.path.join(SRC, 'ru', n)) for n in pairs), []); EN = sum((tokens(os.path.join(SRC, 'en', n)) for n in pairs), [])
N = min(len(RU), len(EN))
heaps = {lang: [(m, len(set(T[:m]))) for m in (1000, 2000, 5000, 10000, 20000, 40000, N) if m <= len(T)] for lang, T in (('ru', RU), ('en', EN))}
top = {lang: Counter(T).most_common(10) for lang, T in (('ru', RU), ('en', EN))}
out = dict(n_pairs=len(rows), P1=dict(k=k1, of=16, verdict=verdict(k1), p_one_sided=tail(k1)),
           P2=dict(k=k2, of=16, verdict=verdict(k2), p_one_sided=tail(k2)),
           P3=dict(tokens_ru=len(RU), tokens_en=len(EN), N=N, ttr_ru=len(set(RU[:N])) / N, ttr_en=len(set(EN[:N])) / N,
                   alpha_ru=zipf_alpha(RU)[0], alpha_en=zipf_alpha(EN)[0], heaps=heaps, top10=top),
           rows=rows)
json.dump(out, open(os.path.join(os.path.dirname(__file__), 's1_results.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ('rows',)}, ensure_ascii=False, indent=1))
