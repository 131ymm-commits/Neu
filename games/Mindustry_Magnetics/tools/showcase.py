# Витрина спрайтов мода: всё, что нарисовано, крупно и с подписями (как в игре: турель на базе, батарея с крышкой).
from PIL import Image, ImageDraw, ImageFont
import os
S = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'magnetics', 'sprites'); OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'showcase.png')
F = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def L(p): return Image.open(os.path.join(S, p)).convert('RGBA')
def stack(*ims):
    out = Image.new('RGBA', ims[0].size, (0, 0, 0, 0))
    for im in ims: out.alpha_composite(im.resize(out.size))
    return out
turret = stack(Image.open('/tmp/claude-0/van/base2.png').convert('RGBA'), L('blocks/gauss.png'))
battery = stack(L('blocks/superconducting-battery.png'), L('blocks/superconducting-battery-top.png'))
belt = Image.new('RGBA', (32 * 6, 32), (0, 0, 0, 0))
for i in range(6): belt.alpha_composite(L('blocks/mag-conveyor-0-%d.png' % (i % 4)), (32 * i, 0))
cells = [
    ('Магнитный сплав', 'предмет', L('items/magnet-alloy.png'), 6),
    ('Сверхпроводник', 'предмет', L('items/superconductor.png'), 6),
    ('Индукционная печь', '2×2 · сплав', L('blocks/induction-furnace.png'), 3),
    ('Криокамера', '3×3 · сверхпроводник', L('blocks/cryo-chamber.png'), 2),
    ('«Гаусс»', 'турель 2×2 на базе', turret, 3),
    ('Магнитная стена', '1×1 · 640 прочности', L('blocks/magnet-wall.png'), 6),
    ('Большая магнитная стена', '2×2 · 2560', L('blocks/magnet-wall-large.png'), 3),
    ('Сверхпроводящий узел', '2×2 · 22 блока', L('blocks/superconducting-node.png'), 3),
    ('Сверхпроводящая батарея', '3×3 · 150 000', battery, 2),
]
CW, CH, cols = 330, 300, 3
rows = (len(cells) + cols - 1) // cols
W, H = CW * cols, 90 + CH * rows + 210
img = Image.new('RGBA', (W, H), (30, 31, 38, 255)); d = ImageDraw.Draw(img)
d.text((24, 22), 'Magnetics — все модели мода', font=ImageFont.truetype(FB, 34), fill=(230, 236, 255))
d.text((26, 62), 'Mindustry v146 · масштаб: пиксели увеличены', font=ImageFont.truetype(F, 16), fill=(140, 150, 180))
for k, (name, sub, im, sc) in enumerate(cells):
    x0, y0 = (k % cols) * CW, 90 + (k // cols) * CH
    d.rounded_rectangle((x0 + 10, y0 + 8, x0 + CW - 10, y0 + CH - 8), 14, fill=(42, 44, 54))
    big = im.resize((im.width * sc, im.height * sc), Image.NEAREST)
    img.alpha_composite(big, (x0 + (CW - big.width) // 2, y0 + 20 + (200 - big.height) // 2))
    d.text((x0 + 24, y0 + 228), name, font=ImageFont.truetype(FB, 19), fill=(230, 236, 255))
    d.text((x0 + 24, y0 + 256), sub, font=ImageFont.truetype(F, 15), fill=(140, 170, 230))
y0 = 90 + CH * rows
d.rounded_rectangle((10, y0 + 8, W - 10, H - 12), 14, fill=(42, 44, 54))
d.text((24, y0 + 22), 'Магнитная лента · 14,9 предмета/с', font=ImageFont.truetype(FB, 19), fill=(230, 236, 255))
bb = belt.resize((belt.width * 4, belt.height * 4), Image.NEAREST); img.alpha_composite(bb, ((W - bb.width) // 2, y0 + 58))
d.text((24, y0 + 200 - 12), 'кадры анимации 0–3 подряд', font=ImageFont.truetype(F, 15), fill=(140, 170, 230))
img.convert('RGB').save(OUT); print(OUT, img.size)
