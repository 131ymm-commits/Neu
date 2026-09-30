# Спрайты мода: перекраска ванильных спрайтов Mindustry (GPL-3.0) в магнитную гамму + медные витки катушек.
import colorsys, os, sys
from PIL import Image, ImageDraw
VAN = os.environ.get('VAN', '/tmp/claude-0/van'); OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'magnetics', 'sprites')
def recolor(src, hue, sat_mul=1.0, sat_add=0.0, val_mul=1.0):
    im = Image.open(os.path.join(VAN, src)).convert('RGBA'); px = im.load()
    for x in range(im.width):
        for y in range(im.height):
            r, g, b, a = px[x, y]
            if a == 0: continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            s = min(1, s * sat_mul + sat_add); v = min(1, v * val_mul)
            r, g, b = colorsys.hsv_to_rgb(hue, s, v); px[x, y] = (int(r * 255), int(g * 255), int(b * 255), a)
    return im
def coils(im, n, box, color=(214, 133, 74, 255), dark=(140, 80, 45, 255)):
    """горизонтальные медные витки в прямоугольнике box = (x0, y0, x1, y1), только по непрозрачным пикселям"""
    px = im.load(); x0, y0, x1, y1 = box; step = max(3, (y1 - y0) // n)
    for k in range(n):
        yy = y0 + k * step
        for x in range(x0, x1):
            for dy, col in ((0, color), (1, dark)):
                if 0 <= yy + dy < im.height and px[x, yy + dy][3] > 0: px[x, yy + dy] = col
    return im
def save(im, rel):
    p = os.path.join(OUT, rel); os.makedirs(os.path.dirname(p), exist_ok=True); im.save(p); print(rel, im.size)
BLUE, CYAN = 0.62, 0.53
# предметы
save(recolor('item-titanium.png', BLUE, 1.6, 0.25, 1.05), 'items/magnet-alloy.png')
save(recolor('item-surge-alloy.png', CYAN, 1.2, 0.1, 1.15), 'items/superconductor.png')
# индукционная печь (2×2) — кремниевый плавильщик в синем, с витками
f = recolor('silicon-smelter.png', BLUE, 1.6, 0.35); save(coils(f, 3, (8, 44, 56, 58)), 'blocks/induction-furnace.png')
# криокамера (3×3) — плавильщик кинетического сплава в циане
save(recolor('surge-smelter.png', CYAN, 1.2, 0.1, 1.05), 'blocks/cryo-chamber.png')
# стены
save(coils(recolor('titanium-wall.png', BLUE, 1.5, 0.2), 2, (6, 12, 26, 20)), 'blocks/magnet-wall.png')
save(coils(recolor('titanium-wall-large.png', BLUE, 1.5, 0.2), 3, (10, 22, 54, 42)), 'blocks/magnet-wall-large.png')
# турель «Гаусс» — копейщик в синем, витки по стволу
g = recolor('lancer.png', BLUE, 1.4, 0.2); save(coils(g, 4, (28, 14, 36, 40)), 'blocks/gauss.png')
# сверхпроводящие узел и батарея
save(recolor('power-node-large.png', CYAN, 1.3, 0.15, 1.05), 'blocks/superconducting-node.png')
save(recolor('battery-large.png', CYAN, 1.3, 0.15), 'blocks/superconducting-battery.png')
save(recolor('battery-large-top.png', CYAN, 1.3, 0.15, 1.1), 'blocks/superconducting-battery-top.png')
# магнитная лента: 5 форм × 4 кадра
for a in range(5):
    for b in range(4): save(recolor(f'titanium-conveyor-{a}-{b}.png', BLUE, 1.6, 0.2), f'blocks/mag-conveyor-{a}-{b}.png')
