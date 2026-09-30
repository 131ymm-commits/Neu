# Рисовальщик Magnetics: все спрайты с нуля, кодом, в одном стиле (контур, фаска, заклёпки, медные витки, синий сплав, голубой сверхпроводник).
# Исключение — формы ленты и моста: из ванильных спрайтов берутся только маски силуэта (где рельс, где полотно), цвет и детали свои.
from PIL import Image, ImageDraw
import math, os
VAN = '/tmp/claude-0/van'
def C(h, a=255): h = h.lstrip('#'); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
OUT, OUT2 = C('23252f'), C('3a3e4c')
MET = dict(l=C('b9c3d6'), m=C('8e98ae'), d=C('626b82'), dd=C('464d60'))
DARK = dict(l=C('6e7488'), m=C('515768'), d=C('3b4050'), dd=C('2b2f3b'))
BLUE = dict(l=C('9fb8ff'), m=C('5f82e8'), d=C('3a58c0'), dd=C('26398a'))
CYAN = dict(l=C('e6fbff'), m=C('9fe8ff'), d=C('4fc3e8'), dd=C('2a86a8'))
COP = dict(l=C('f0b07a'), m=C('d6854a'), d=C('a45f33'), dd=C('6e3e22'))
FER = dict(l=C('8a7680'), m=C('66545c'), d=C('4a3c43'), dd=C('33292f'))
VIO = dict(l=C('eadbff'), m=C('b58cff'), d=C('8458d6'), dd=C('5a3598'))
GLOW = dict(o=C('ffb35c'), y=C('ffe7a0'), g=C('8cffb0'), gd=C('3fbf6a'), p=C('ff7ad9'))
def new(w, h=None): return Image.new('RGBA', (w, h or w), (0, 0, 0, 0))
def rect(d, x0, y0, x1, y1, col): d.rectangle((x0, y0, x1, y1), fill=col)
def plate(d, x0, y0, x1, y1, p, outline=OUT, bevel=True):
    rect(d, x0, y0, x1, y1, outline); rect(d, x0 + 1, y0 + 1, x1 - 1, y1 - 1, p['m'])
    if bevel:
        rect(d, x0 + 1, y0 + 1, x1 - 1, y0 + 1, p['l']); rect(d, x0 + 1, y0 + 1, x0 + 1, y1 - 1, p['l'])
        rect(d, x0 + 1, y1 - 1, x1 - 1, y1 - 1, p['d']); rect(d, x1 - 1, y0 + 1, x1 - 1, y1 - 1, p['d'])
def bolt(d, x, y, p=MET): d.point((x, y), p['l']); d.point((x + 1, y + 1), p['dd']); d.point((x + 1, y), p['m']); d.point((x, y + 1), p['d'])
def frame(size, p=MET, inner=DARK, inset=3):
    s = 32 * size; im = new(s); d = ImageDraw.Draw(im)
    plate(d, 0, 0, s - 1, s - 1, p); plate(d, inset, inset, s - 1 - inset, s - 1 - inset, inner)
    for (x, y) in ((1, 1), (s - 4, 1), (1, s - 4), (s - 4, s - 4)): bolt(d, x + 0, y + 0, p)
    return im, d
def circle(d, cx, cy, r, fill, outline=OUT): d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=outline); d.ellipse((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), fill=fill)
def ring(d, cx, cy, r, w, p):
    circle(d, cx, cy, r, p['m']); d.arc((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), 150, 300, fill=p['l'], width=1); d.arc((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), 330, 120, fill=p['d'], width=1)
    circle(d, cx, cy, r - w, (0, 0, 0, 0), OUT)
def coil(d, x0, y0, x1, y1, turns=None, vertical=False):
    """медная обмотка: полосы с тёмными разделителями, блик сверху"""
    rect(d, x0, y0, x1, y1, OUT)
    n = (x1 - x0 if vertical else y1 - y0) - 1
    for k in range(n):
        col = COP['l'] if k % 3 == 0 else (COP['m'] if k % 3 == 1 else COP['dd'])
        if vertical: rect(d, x0 + 1 + k, y0 + 1, x0 + 1 + k, y1 - 1, col)
        else: rect(d, x0 + 1, y0 + 1 + k, x1 - 1, y0 + 1 + k, col)
def crystal(d, cx, cy, r, p):
    pts = [(cx, cy - r), (cx + r * 0.7, cy), (cx, cy + r), (cx - r * 0.7, cy)]
    d.polygon(pts, fill=OUT); pts2 = [(cx, cy - r + 1.5), (cx + r * 0.7 - 1.5, cy), (cx, cy + r - 1.5), (cx - r * 0.7 + 1.5, cy)]
    d.polygon(pts2, fill=p['m']); d.polygon([(cx, cy - r + 1.5), (cx - r * 0.7 + 1.5, cy), (cx, cy)], fill=p['l']); d.polygon([(cx, cy + r - 1.5), (cx + r * 0.7 - 1.5, cy), (cx, cy)], fill=p['d'])
def vents(d, x0, y0, x1, y1, step=3):
    for y in range(y0, y1, step): rect(d, x0, y, x1, y, OUT2)
def glowdot(im, cx, cy, r, col):
    d = ImageDraw.Draw(im)
    for k in range(r, 0, -1):
        a = int(255 * (1 - k / (r + 1)) ** 0.7); d.ellipse((cx - k, cy - k, cx + k, cy + k), fill=col[:3] + (a,))
def top_glow(size, r, col=GLOW['y']):
    s = 32 * size; im = new(s); glowdot(im, s // 2, s // 2, r, col); return im
# ---------------- предметы ----------------
def item(kind):
    im = new(32); d = ImageDraw.Draw(im)
    if kind == 'ferrite':
        for (cx, cy, r) in ((12, 18, 7), (21, 12, 6), (21, 22, 6)):
            circle(d, cx, cy, r, FER['m']); d.ellipse((cx - r + 2, cy - r + 2, cx - 1, cy - 1), fill=FER['l']); d.point((cx + 2, cy + 2), FER['dd'])
    elif kind == 'magnet-alloy':
        d.polygon([(4, 18), (16, 10), (28, 14), (16, 22)], fill=OUT); d.polygon([(4, 18), (16, 22), (16, 27), (4, 23)], fill=OUT); d.polygon([(16, 22), (28, 14), (28, 19), (16, 27)], fill=OUT)
        d.polygon([(6, 18), (16, 12), (26, 14), (16, 20)], fill=BLUE['l']); d.polygon([(5, 19), (15, 23), (15, 26), (5, 22)], fill=BLUE['m']); d.polygon([(17, 23), (27, 16), (27, 18), (17, 26)], fill=BLUE['d'])
        rect(d, 10, 16, 12, 16, COP['m']); rect(d, 18, 13, 20, 13, COP['m'])
    elif kind == 'coil':
        rect(d, 6, 7, 25, 10, OUT); rect(d, 6, 22, 25, 25, OUT); rect(d, 7, 8, 24, 9, MET['l']); rect(d, 7, 23, 24, 24, MET['d'])
        coil(d, 9, 10, 22, 22)
    elif kind == 'superconductor':
        d.polygon([(3, 20), (18, 9), (29, 13), (14, 25)], fill=OUT); d.polygon([(5, 20), (18, 11), (27, 13), (14, 23)], fill=CYAN['m'])
        d.line((8, 19, 18, 12), fill=CYAN['l']); d.line((12, 22, 24, 14), fill=CYAN['d']); rect(d, 4, 21, 13, 26, OUT); d.polygon([(5, 22), (13, 25), (14, 25), (5, 21)], fill=VIO['d'])
        for (x, y) in ((22, 6), (26, 22), (7, 12)): d.point((x, y), CYAN['l']); d.point((x - 1, y), CYAN['m']); d.point((x + 1, y), CYAN['m']); d.point((x, y - 1), CYAN['m']); d.point((x, y + 1), CYAN['m'])
    elif kind == 'flux-crystal':
        crystal(d, 16, 16, 14, VIO); crystal(d, 16, 17, 7, CYAN)
    return im
# ---------------- здания ----------------
def art_block(kind, size):
    s = 32 * size; extra = {}
    if kind == 'kiln':
        im, d = frame(2, FER, DARK); circle(d, 32, 32, 16, OUT); circle(d, 32, 32, 15, DARK['dd'])
        for x in range(21, 44, 4): rect(d, x, 22, x + 1, 42, FER['l'])
        vents(d, 6, 6, 20, 14); vents(d, 44, 50, 58, 58); extra['-top'] = top_glow(2, 12, GLOW['o'])
    elif kind == 'furnace':
        im, d = frame(2, MET, DARK); coil(d, 8, 12, 17, 52); coil(d, 46, 12, 55, 52)
        circle(d, 32, 32, 13, BLUE['dd']); circle(d, 32, 32, 9, OUT); extra['-top'] = top_glow(2, 9, C('8fb4ff'))
    elif kind == 'winder':
        im, d = frame(2, MET, DARK); circle(d, 32, 32, 17, COP['d']); 
        for r in range(16, 5, -3): d.ellipse((32 - r, 32 - r, 32 + r, 32 + r), outline=COP['l'] if r % 2 else COP['dd'])
        circle(d, 32, 32, 5, MET['m']); bolt(d, 31, 31); rect(d, 6, 28, 13, 36, MET['d']); rect(d, 51, 28, 58, 36, MET['d'])
        extra['-top'] = top_glow(2, 4, COP['l'])
    elif kind == 'cryo':
        im, d = frame(3, MET, DARK)
        for (x0, y0, x1, y1) in ((10, 44, 38, 51), (58, 44, 86, 51), (44, 10, 51, 38), (44, 58, 51, 86)): plate(d, x0, y0, x1, y1, CYAN)
        circle(d, 48, 48, 22, CYAN['dd']); circle(d, 48, 48, 19, CYAN['d']); d.ellipse((34, 32, 52, 48), fill=CYAN['m']); d.ellipse((38, 35, 46, 42), fill=CYAN['l'])
        for (x, y) in ((58, 58), (40, 60), (60, 38)): d.point((x, y), CYAN['l'])
        extra['-top'] = top_glow(3, 14, CYAN['l'])
    elif kind == 'resonator':
        im, d = frame(3, MET, DARK); ring(d, 48, 48, 30, 5, VIO)
        for (x, y) in ((48, 12), (12, 48), (84, 48), (48, 84)): coil(d, x - 6, y - 6, x + 6, y + 6)
        crystal(d, 48, 48, 18, VIO); crystal(d, 48, 49, 8, CYAN); extra['-top'] = top_glow(3, 20, VIO['l'])
    elif kind == 'separator':
        im, d = frame(3, MET, DARK); circle(d, 48, 48, 30, MET['d']); circle(d, 48, 48, 26, DARK['dd'])
        d.arc((26, 26, 70, 70), 200, 340, fill=C('e05555'), width=7); d.arc((26, 26, 70, 70), 20, 160, fill=BLUE['m'], width=7)
        circle(d, 48, 48, 8, MET['m']); bolt(d, 47, 47)
        for x in (14, 44, 74): rect(d, x, 84, x + 8, 90, COP['d'] if x == 14 else (DARK['l'] if x == 44 else MET['l']))
        extra['-top'] = top_glow(3, 6, BLUE['l'])
    elif kind == 'drill':
        im, d = frame(3, MET, DARK)
        for (x, y) in ((8, 8), (78, 8), (8, 78), (78, 78)): coil(d, x, y, x + 10, y + 10)
        rot = new(96); dr = ImageDraw.Draw(rot)
        for a in range(3):
            ang = a * 2 * math.pi / 3; pts = []
            for (r, da) in ((10, -0.5), (36, -0.18), (38, 0.12), (12, 0.5)): pts.append((48 + r * math.cos(ang + da), 48 + r * math.sin(ang + da)))
            dr.polygon(pts, fill=OUT); pts2 = [(48 + (x - 48) * 0.9, 48 + (y - 48) * 0.9) for x, y in pts]; dr.polygon(pts2, fill=MET['m'])
            dr.line([pts2[0], pts2[1]], fill=MET['l'])
        top = new(96); dt = ImageDraw.Draw(top); circle(dt, 48, 48, 12, BLUE['m']); circle(dt, 48, 48, 7, BLUE['d']); dt.point((45, 45), BLUE['l'])
        extra['-rotator'] = rot; extra['-top'] = top
    elif kind == 'junction':
        im, d = frame(1, MET, DARK, 3)
        for (x0, y0, x1, y1) in ((5, 14, 26, 17), (14, 5, 17, 26)): rect(d, x0, y0, x1, y1, BLUE['m'])
        rect(d, 13, 13, 18, 18, COP['m'])
    elif kind == 'router':
        im, d = frame(1, MET, DARK, 3); circle(d, 16, 16, 7, BLUE['d']); circle(d, 16, 16, 3, CYAN['m'])
        for (x, y) in ((16, 5), (16, 26), (5, 16), (26, 16)): rect(d, x - 1, y - 1, x + 1, y + 1, COP['m'])
    elif kind == 'bridge':
        im, d = frame(1, MET, DARK, 3); circle(d, 16, 16, 8, BLUE['d']); circle(d, 16, 16, 5, BLUE['m']); d.point((14, 14), BLUE['l'])
        end = new(32); de = ImageDraw.Draw(end); plate(de, 4, 24, 27, 31, BLUE)
        br = new(32); db = ImageDraw.Draw(br); rect(db, 0, 4, 31, 27, OUT); rect(db, 0, 5, 31, 26, DARK['d'])
        for x in range(0, 32, 4): rect(db, x, 5, x + 1, 26, BLUE['dd'])
        rect(db, 0, 5, 31, 6, BLUE['m']); rect(db, 0, 25, 31, 26, BLUE['m'])
        ar = new(32); da = ImageDraw.Draw(ar); da.polygon([(12, 8), (20, 16), (12, 24)], fill=CYAN['m'])
        extra.update({'-end': end, '-bridge': br, '-arrow': ar})
    elif kind in ('battery1', 'battery3'):
        sz = 1 if kind == 'battery1' else 3; im, d = frame(sz, MET, DARK, 2 if sz == 1 else 4); s = 32 * sz
        n = 2 if sz == 1 else 4; w = (s - 2 * (4 + sz * 2)) // n
        for k in range(n):
            x0 = 4 + sz * 2 + k * w; plate(d, x0 + 1, 6 + sz * 2, x0 + w - 2, s - 7 - sz * 2, CYAN if sz == 3 else BLUE)
        top = new(s); dt = ImageDraw.Draw(top)
        for k in range(n):
            x0 = 4 + sz * 2 + k * w; rect(dt, x0 + 1, 6 + sz * 2, x0 + w - 2, 8 + sz * 2, OUT); coil(dt, x0 + 1, 9 + sz * 2, x0 + w - 2, 12 + sz * 3)
        extra['-top'] = top
    elif kind == 'node':
        im = new(64); d = ImageDraw.Draw(im)
        oct_ = [(18, 1), (46, 1), (62, 18), (62, 46), (46, 62), (18, 62), (1, 46), (1, 18)]
        d.polygon(oct_, fill=OUT); d.polygon([(x * 0.94 + 2, y * 0.94 + 2) for x, y in oct_], fill=MET['m'])
        ring(d, 32, 32, 22, 6, CYAN); coil(d, 26, 26, 38, 38); crystal(d, 32, 32, 6, CYAN)
    elif kind == 'mhd':
        im, d = frame(2, MET, DARK); coil(d, 6, 8, 20, 56, vertical=False); coil(d, 44, 8, 58, 56)
        rect(d, 22, 6, 41, 57, OUT); rect(d, 23, 7, 40, 56, C('4a1d3d'))
        for y in range(8, 56, 6): rect(d, 25, y, 38, y + 2, GLOW['p'])
        extra['-top'] = top_glow(2, 10, GLOW['p'])
    elif kind == 'reactor':
        im, d = frame(3, DARK, MET, 5)
        for (x, y) in ((20, 20), (76, 20), (20, 76), (76, 76)): circle(d, x, y, 9, COP['m']); circle(d, x, y, 4, COP['dd'])
        circle(d, 48, 48, 24, OUT); circle(d, 48, 48, 22, DARK['dd']); crystal(d, 48, 48, 17, VIO); crystal(d, 48, 49, 7, CYAN)
        extra['-top'] = top_glow(3, 24, VIO['l'])
    elif kind.startswith('wall-'):
        p = {'wall-ferrite': FER, 'wall-magnet': BLUE, 'wall-super': CYAN}[kind]
        im = new(s); d = ImageDraw.Draw(im); plate(d, 0, 0, s - 1, s - 1, p)
        if kind == 'wall-ferrite':
            import random; rng = random.Random(size)
            for _ in range(6 * size * size): x, y = rng.randrange(3, s - 3), rng.randrange(3, s - 3); d.point((x, y), FER['l'] if rng.random() < .5 else FER['dd'])
            for y in range(s // 4, s, s // 4): rect(d, 2, y, s - 3, y, FER['d'])
        elif kind == 'wall-magnet':
            coil(d, 3, s // 2 - 3 * size, s - 4, s // 2 + 3 * size); plate(d, 5, 5, s - 6, s // 2 - 3 * size - 3, BLUE, bevel=True)
        else:
            for x in range(4, s - 4, 6): rect(d, x, 3, x, s - 4, CYAN['l'])
            for y in range(4, s - 4, 6): rect(d, 3, y, s - 4, y, CYAN['d'])
            crystal(d, s // 2, s // 2, 5 * size, VIO)
        for (x, y) in ((2, 2), (s - 4, 2), (2, s - 4), (s - 4, s - 4)): bolt(d, x, y, MET)
    elif kind == 'mend':
        im, d = frame(2, MET, DARK); ring(d, 32, 32, 20, 5, COP)
        top = new(64); dt = ImageDraw.Draw(top); rect(dt, 28, 20, 35, 43, GLOW['g']); rect(dt, 20, 28, 43, 35, GLOW['g']); extra['-top'] = top
    elif kind == 'shield':
        im, d = frame(3, MET, DARK)
        hexp = [(48 + 26 * math.cos(math.pi / 3 * k + math.pi / 6), 48 + 26 * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)]
        d.polygon(hexp, fill=OUT); d.polygon([(48 + (x - 48) * 0.88, 48 + (y - 48) * 0.88) for x, y in hexp], fill=BLUE['d'])
        for (x, y) in ((14, 14), (72, 14), (14, 72), (72, 72)): coil(d, x, y, x + 10, y + 10)
        top = new(96); dt = ImageDraw.Draw(top); dt.polygon([(48 + (x - 48) * 0.6, 48 + (y - 48) * 0.6) for x, y in hexp], fill=CYAN['m']); dt.polygon([(48 + (x - 48) * 0.35, 48 + (y - 48) * 0.35) for x, y in hexp], fill=CYAN['l'])
        extra['-top'] = top
    elif kind == 'factory':
        im, d = frame(3, MET, DARK); rect(d, 16, 16, 79, 79, OUT); rect(d, 17, 17, 78, 78, DARK['dd'])
        for k in range(17, 79, 8): rect(d, k, 17, k, 78, DARK['d']); rect(d, 17, k, 78, k, DARK['d'])
        for (x, y) in ((6, 40), (84, 40)): coil(d, x, y, x + 6, y + 16, vertical=True)
    elif kind.startswith('turret'):
        im = turret(kind)
    else: raise ValueError(kind)
    return im, extra
def turret(kind):
    """верх турели (база — ванильная «block-N» из самой игры)"""
    if kind == 'turret1':
        im = new(32); d = ImageDraw.Draw(im); plate(d, 9, 14, 22, 27, MET); rect(d, 14, 2, 17, 16, OUT); rect(d, 15, 3, 16, 15, MET['l'])
        coil(d, 12, 6, 19, 12); d.point((15, 20), BLUE['m']); d.point((16, 20), BLUE['m'])
    elif kind == 'turret2':
        im = new(64); d = ImageDraw.Draw(im); plate(d, 16, 32, 47, 58, MET); rect(d, 27, 2, 36, 36, OUT); rect(d, 28, 3, 35, 35, MET['m']); rect(d, 28, 3, 29, 35, MET['l'])
        for y in (8, 17, 26): coil(d, 25, y, 38, y + 5)
        rect(d, 30, 1, 33, 3, BLUE['l']); plate(d, 22, 40, 41, 52, BLUE)
    elif kind == 'turret2arc':
        im = new(64); d = ImageDraw.Draw(im); plate(d, 14, 30, 49, 58, MET); coil(d, 24, 18, 39, 40, vertical=False)
        circle(d, 32, 14, 10, CYAN['d']); circle(d, 32, 14, 7, CYAN['m']); d.ellipse((27, 8, 32, 13), fill=CYAN['l'])
    elif kind == 'turret2flak':
        im = new(64); d = ImageDraw.Draw(im); plate(d, 14, 30, 49, 58, MET)
        for x in (20, 36):
            rect(d, x, 4, x + 7, 34, OUT); rect(d, x + 1, 5, x + 6, 33, MET['m']); rect(d, x + 1, 5, x + 2, 33, MET['l']); coil(d, x - 1, 10, x + 8, 15); coil(d, x - 1, 20, x + 8, 25)
        plate(d, 24, 40, 39, 52, COP)
    elif kind == 'turret3':
        im = new(96); d = ImageDraw.Draw(im); plate(d, 22, 46, 73, 88, MET); plate(d, 30, 54, 65, 80, CYAN)
        for x in (34, 55):
            rect(d, x, 2, x + 6, 58, OUT); rect(d, x + 1, 3, x + 5, 57, DARK['l']); rect(d, x + 1, 3, x + 2, 57, MET['l'])
        rect(d, 41, 6, 54, 50, OUT); rect(d, 42, 7, 53, 49, CYAN['dd'])
        for y in range(9, 48, 5): rect(d, 43, y, 52, y + 1, CYAN['m'])
        for y in (14, 30): coil(d, 31, y, 64, y + 5)
    return im
# ---------------- лента: маски силуэта из ванили, своя раскраска ----------------
def conveyor(a, b):
    import colorsys
    src = Image.open(os.path.join(VAN, f'titanium-conveyor-{a}-{b}.png')).convert('RGBA'); px = src.load(); im = new(32); q = im.load()
    for x in range(32):
        for y in range(32):
            r, g, bb, al = px[x, y]
            if al == 0: continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, bb / 255)
            if s > 0.3 and 0.55 < h < 0.72:   # рельс
                q[x, y] = COP['m'] if (x + y) % 8 == 0 else (BLUE['l'] if v > 0.85 else BLUE['m'])
            elif v > 0.38:                    # шеврон
                q[x, y] = CYAN['m'] if v > 0.45 else CYAN['d']
            elif v < 0.12: q[x, y] = OUT
            else: q[x, y] = C('20222c') if (y // 2) % 2 else C('272a36')
    return im
# ---------------- юниты (вид сверху, нос вверх) ----------------
def mirror_poly(pts, cx): return pts + [(2 * cx - x, y) for x, y in reversed(pts)]
def unit(kind):
    if kind == 'unit-spark':
        s = 40; im = new(s); d = ImageDraw.Draw(im); cell = new(s); dc = ImageDraw.Draw(cell); cx = 20
        body = mirror_poly([(20, 2), (17, 12), (6, 26), (5, 32), (15, 30), (17, 36)], cx)
        d.polygon(body, fill=OUT); d.polygon([(cx + (x - cx) * 0.86, 3 + (y - 3) * 0.9) for x, y in body], fill=BLUE['m'])
        d.polygon([(20, 5), (18, 12), (9, 26), (15, 26)], fill=BLUE['l']); coil(d, 16, 16, 23, 22); rect(d, 8, 22, 9, 30, OUT); rect(d, 31, 22, 32, 30, OUT)
        dc.polygon([(20, 8), (18, 13), (22, 13)], fill=C('ffffff')); dc.rectangle((19, 24, 21, 30), fill=C('ffffff'))
    elif kind == 'unit-inductor':
        s = 56; im = new(s); d = ImageDraw.Draw(im); cell = new(s); dc = ImageDraw.Draw(cell); cx = 28
        body = mirror_poly([(28, 3), (20, 10), (8, 14), (4, 30), (10, 44), (20, 46), (24, 52)], cx)
        d.polygon(body, fill=OUT); d.polygon([(cx + (x - cx) * 0.88, 4 + (y - 4) * 0.9) for x, y in body], fill=MET['m'])
        ring(d, 28, 27, 13, 4, CYAN); circle(d, 28, 27, 6, CYAN['d']); d.point((26, 25), CYAN['l'])
        coil(d, 7, 22, 13, 36); coil(d, 43, 22, 49, 36)
        dc.ellipse((25, 24, 31, 30), fill=C('ffffff')); dc.polygon([(28, 6), (24, 11), (32, 11)], fill=C('ffffff'))
    else:
        s = 96; im = new(s); d = ImageDraw.Draw(im); cell = new(s); dc = ImageDraw.Draw(cell); cx = 48
        body = mirror_poly([(48, 3), (40, 14), (30, 22), (8, 40), (4, 60), (14, 70), (30, 66), (36, 84), (44, 92)], cx)
        d.polygon(body, fill=OUT); d.polygon([(cx + (x - cx) * 0.9, 4 + (y - 4) * 0.93) for x, y in body], fill=DARK['l'])
        d.polygon([(cx + (x - cx) * 0.6, 14 + (y - 14) * 0.7) for x, y in body], fill=BLUE['d'])
        for x in (26, 62):
            rect(d, x, 20, x + 7, 62, OUT); rect(d, x + 1, 21, x + 6, 61, MET['m']); rect(d, x + 1, 21, x + 2, 61, MET['l'])
            for y in (28, 40, 52): coil(d, x - 1, y, x + 8, y + 4)
        coil(d, 40, 60, 55, 72); crystal(d, 48, 36, 8, CYAN)
        dc.polygon([(48, 12), (42, 22), (54, 22)], fill=C('ffffff')); dc.rectangle((46, 74, 50, 86), fill=C('ffffff'))
    return im, cell
