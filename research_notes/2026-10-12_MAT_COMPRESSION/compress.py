# Коэффициент сжатия = слогов в развёрнутом толковании / слогов в сжатом выражении.
# Русские слоги — по гласным; английские — ручной счёт (указан в данных). Толкования: [сн.] — из поисковой выдачи, [пам.] — мои по памяти.
import re, statistics as st
V = 'аеёиоуыэюя'
def syl_ru(s): return sum(ch in V for ch in s.lower())
DATA = [
 # (группа, сжатое, слоги сжатого, толкование, слоги толкования, статус)
 ('позывной/бревити', 'Bingo', 2, 'minimum fuel state needed to return to base', 12, 'сн.'),
 ('позывной/бревити', 'Joker', 2, 'fuel state above Bingo at which separation, bugout or event termination should begin', 25, 'сн.'),
 ('позывной/бревити', 'Winchester', 3, 'no ordnance remaining', 6, 'сн., слабый источник'),
 ('флот', 'линкор', None, 'линейный корабль', None, 'сн.'),
 ('флот', 'лягушка', None, 'дизельная подводная лодка с крылатыми ракетами проекта шестьсот шестьдесят пять', None, 'сн.'),
 ('флот/команда', 'Отдать швартовы!', None, 'отвязать и выбрать на борт концы, которыми судно крепится к причалу', None, 'пам.'),
 ('армия/команда', 'Отбой!', None, 'команда отменяется, прекратить действие и вернуться в исходное положение', None, 'пам.'),
 ('мат', 'пиздец', None, 'положение стало безнадёжным, всё окончательно рухнуло', None, 'пам.'),
 ('мат', 'похуй', None, 'мне это совершенно безразлично', None, 'пам.'),
 ('мат', 'охуеть', None, 'прийти в крайнее изумление', None, 'пам.'),
 ('мат', 'заебал', None, 'ты мне надоел до крайней степени', None, 'пам.'),
 ('мат', 'распиздяй', None, 'безответственный неорганизованный человек', None, 'пам.'),
 ('мат', 'наебнулся', None, 'упал и сильно ударился', None, 'пам.'),
]
rows = []
for g, short, sshort, full, sfull, status in DATA:
    a = sshort if sshort is not None else syl_ru(short); b = sfull if sfull is not None else syl_ru(full)
    rows.append((g, short, a, b, b / a, status))
for g, short, a, b, r, s in rows: print(f'{g:18s} {short:18s} {a:2d} → {b:2d} слогов  ×{r:4.1f}  [{s}]')
by = {}
for g, short, a, b, r, s in rows: by.setdefault(g.split('/')[0], []).append(r)
print({k: round(st.median(v), 1) for k, v in by.items()}, 'медиана по всем:', round(st.median([r for *_, r, s in rows]), 1))
