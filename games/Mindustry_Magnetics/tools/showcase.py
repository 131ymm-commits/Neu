# Витрина всех моделей Magnetics (собирается так же, как рисует игра: база турели, крышки, ротор бура).
from PIL import Image, ImageDraw, ImageFont
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import spec
S = os.path.join(HERE, '..', 'magnetics', 'sprites'); OUT = os.path.join(HERE, '..', 'showcase.png')
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13); FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
def L(p): return Image.open(os.path.join(S, p)).convert('RGBA')
def ex(p): return os.path.exists(os.path.join(S, p))
def compose(n, b):
    if b['art'] == 'conveyor':
        im = Image.new('RGBA', (96, 32)); [im.alpha_composite(L(f'blocks/{n}-0-{k % 4}.png'), (32 * k, 0)) for k in range(3)]; return im
    im = L(f'blocks/{n}.png')
    if b['art'].startswith('turret'):
        base = Image.open(f"/tmp/claude-0/van/base{b['j']['size']}.png").convert('RGBA'); base.alpha_composite(im); im = base
    for suf in ('-rotator', '-top'):
        if ex(f'blocks/{n}{suf}.png') and b['art'] not in ('kiln', 'furnace', 'winder', 'cryo', 'resonator', 'separator', 'mhd', 'reactor'): im = im.copy(); im.alpha_composite(L(f'blocks/{n}{suf}.png'))
    return im
cells = [(v['ru'][0], 'предмет', L(f'items/{n}.png')) for n, v in spec.ITEMS.items()]
cells += [(b['ru'][0], f"{b['j'].get('size', 1)}×{b['j'].get('size', 1)}", compose(n, b)) for n, b in spec.B.items()]
for n, u in spec.UNITS.items():
    im = L(f'units/{n}.png'); cell = L(f'units/{n}-cell.png'); tint = Image.new('RGBA', cell.size, (255, 211, 127, 255)); cell = Image.composite(tint, cell, cell); im.alpha_composite(cell)
    cells.append((u['ru'][0], 'юнит', im))
CW, CH, cols = 190, 190, 7; rows = (len(cells) + cols - 1) // cols
img = Image.new('RGBA', (CW * cols, 70 + CH * rows), (30, 31, 38, 255)); d = ImageDraw.Draw(img)
d.text((16, 14), f'Magnetics 1.0 — все модели ({len(cells)})', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28), fill=(230, 236, 255))
d.text((18, 48), 'нарисованы кодом с нуля · юниты с цветом команды (жёлтый — Шардед)', font=F, fill=(140, 150, 180))
for k, (name, sub, im) in enumerate(cells):
    x0, y0 = (k % cols) * CW, 70 + (k // cols) * CH
    d.rounded_rectangle((x0 + 6, y0 + 6, x0 + CW - 6, y0 + CH - 6), 10, fill=(42, 44, 54))
    sc = max(1, min(4, 128 // max(im.size))); big = im.resize((im.width * sc, im.height * sc), Image.NEAREST)
    img.alpha_composite(big, (x0 + (CW - big.width) // 2, y0 + 14 + (128 - big.height) // 2))
    d.text((x0 + 14, y0 + 148), name if len(name) < 22 else name[:21] + '…', font=FB, fill=(230, 236, 255)); d.text((x0 + 14, y0 + 166), sub, font=F, fill=(140, 170, 230))
img.convert('RGB').save(OUT); print(OUT, img.size)
