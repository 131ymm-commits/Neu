# Предварительная подготовка видео для просмотра головой Claude: в разы меньше токенов (слова автора 06.10.2026:
# «Придумай механизм предварительной подготовки. Чтобы ты ел в 5 раз меньше токенов. Оптимизируй процесс.»)
#   /tmp/claude-0/vidvenv/bin/python tools/video_prep.py <папка с кадрами f/*.jpg> <fps кадров> [порог новизны, 6.0] [кадров на лист, 16]
# Шаги (всё без модели, токены не тратятся):
#   1) числа по каждому кадру: яркость, движение (разница с предыдущим), рамка движения;
#   2) отсев повторов: кадр берётся, только если отличается от последнего ВЗЯТОГО больше порога (или прошло ≥ 10 с — «пульс»);
#   3) обрезка: общий прямоугольник, где хоть что-то двигалось, — фон вне него не показывается;
#   4) листы 4×4 миниатюр (одна картинка ≈ стоимость одного кадра) + текстовая шкала времени timeline.txt;
#   5) бюджет: оценка токенов наивного просмотра (1 кадр/с, каждый отдельной картинкой ~1092 px) против подготовленного.
# Цена картинки у Claude ≈ ширина × высота / 750 токенов (документация Anthropic, «Vision»; длинная сторона ужимается до ~1568 px).
import glob, json, os, sys
import numpy as np
from PIL import Image
D = sys.argv[1]; FPS = float(sys.argv[2]); THR = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0; PER = int(sys.argv[4]) if len(sys.argv) > 4 else 16
files = sorted(glob.glob(os.path.join(D, 'f', '*.jpg')))
tok = lambda w, h: (lambda s: int(w * s * h * s / 750))(min(1.0, 1568 / max(w, h), (1.15e6 / (w * h)) ** 0.5))
small = lambda f: np.asarray(Image.open(f).convert('L').resize((96, 54)), dtype=np.float32)

# 1–2) числа и отсев
keep, rows, last, prev = [], [], None, None
acc = np.zeros((54, 96), bool)
for i, f in enumerate(files):
    a = small(f); t = i / FPS
    motion = float(np.abs(a - prev).mean()) if prev is not None else 0.0
    if prev is not None: acc |= np.abs(a - prev) > 20
    novelty = float(np.abs(a - last[1]).mean()) if last is not None else 1e9
    if novelty > THR or t - (last[0] if last else -1e9) >= 10:
        keep.append((t, f, round(novelty if novelty < 1e8 else 0, 1))); last = (t, a)
    rows.append((round(t, 2), round(motion, 2)))
    prev = a

# 3) рамка движения (в долях кадра), с полем 5 %
ys, xs = np.where(acc)
if len(xs):
    x0, x1, y0, y1 = max(0, xs.min() / 96 - .05), min(1, (xs.max() + 1) / 96 + .05), max(0, ys.min() / 54 - .05), min(1, (ys.max() + 1) / 54 + .05)
else:
    x0, x1, y0, y1 = 0, 1, 0, 1

# 4) листы и шкала
W0, H0 = Image.open(files[0]).size
box = (int(x0 * W0), int(y0 * H0), int(x1 * W0), int(y1 * H0)); cw, ch = box[2] - box[0], box[3] - box[1]
cols = 4; tw = 1092 // cols; th = int(tw * ch / cw)
os.makedirs(os.path.join(D, 'prep'), exist_ok=True)
sheets = []
for k in range(0, len(keep), PER):
    grp = keep[k:k + PER]; rws = (len(grp) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rws * th))
    for j, (t, f, nv) in enumerate(grp):
        sheet.paste(Image.open(f).crop(box).resize((tw, th)), ((j % cols) * tw, (j // cols) * th))
    p = os.path.join(D, 'prep', f'sheet_{k // PER + 1:03d}.jpg'); sheet.save(p, quality=80); sheets.append((p, grp[0][0], grp[-1][0], sheet.size))
mot = np.array([m for _, m in rows]); sec = [float(mot[int(s * FPS):int((s + 1) * FPS)].mean()) for s in range(int(len(rows) / FPS))]
with open(os.path.join(D, 'prep', 'timeline.txt'), 'w') as fh:
    fh.write(f'кадров {len(files)} ({len(files) / FPS:.1f} с), взято {len(keep)} (порог новизны {THR}, пульс 10 с), рамка движения x {x0:.2f}–{x1:.2f}, y {y0:.2f}–{y1:.2f}\n')
    fh.write('движение по секундам (средняя разница кадров ×10):\n' + ' '.join(str(int(v * 10)) for v in sec) + '\n\nлисты:\n')
    for p, a, b, sz in sheets: fh.write(f'{os.path.basename(p)}: {a:7.1f}–{b:7.1f} с\n')
    fh.write('\nвзятые кадры (время, новизна):\n' + ' '.join(f'{t:.1f}({nv})' for t, f, nv in keep) + '\n')

# 5) бюджет
naive = int(len(files) / FPS) * tok(1092, int(1092 * H0 / W0))
prep = sum(tok(*sz) for _, _, _, sz in sheets) + len(open(os.path.join(D, 'prep', 'timeline.txt')).read()) // 3
b = dict(frames=len(files), kept=len(keep), sheets=len(sheets), crop=[round(x0, 2), round(x1, 2), round(y0, 2), round(y1, 2)],
         naive_tokens_1fps=naive, prepared_tokens=prep, ratio=round(naive / max(prep, 1), 1))
json.dump(b, open(os.path.join(D, 'prep', 'budget.json'), 'w'), ensure_ascii=False)
print(json.dumps(b, ensure_ascii=False))
