"""Набор для рисования иконок Factorio кодом (PIL): рисуем в 4× размере и уменьшаем с LANCZOS — края гладкие.
Стиль Factorio: объёмные предметы с освещением сверху-слева, тёмный контур, насыщенные, но не кислотные цвета."""
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import math

SS = 4  # суперсэмплинг

def hexc(h, a=255):
    h = h.lstrip('#'); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

def mix(c1, c2, t):
    return tuple(int(round(c1[i] * (1 - t) + c2[i] * t)) for i in range(4))

def shade(c, k):
    """k>0 светлее, k<0 темнее."""
    if k >= 0: return mix(c, (255, 255, 255, c[3]), k)
    return mix(c, (0, 0, 0, c[3]), -k)

class Canvas:
    def __init__(self, size=64):
        self.size = size; self.S = size * SS
        self.img = Image.new('RGBA', (self.S, self.S), (0, 0, 0, 0))
    def p(self, v): return v * SS
    def layer(self):
        return Image.new('RGBA', (self.S, self.S), (0, 0, 0, 0))
    def paste(self, lay):
        self.img = Image.alpha_composite(self.img, lay)
    def mask_layer(self, draw_fn):
        m = Image.new('L', (self.S, self.S), 0); draw_fn(ImageDraw.Draw(m)); return m
    def fill_gradient(self, mask, c_top, c_bot, angle=135):
        """Заливка маски линейным градиентом (angle в градусах, 135 — свет сверху-слева)."""
        w = self.S
        g = Image.new('RGBA', (w, w))
        a = math.radians(angle); dx, dy = math.cos(a), math.sin(a)
        px = g.load()
        # быстрый градиент через линию
        grad = Image.linear_gradient('L').resize((w, w)).rotate(angle - 90, resample=Image.BICUBIC, expand=False)
        top = Image.new('RGBA', (w, w), c_top); bot = Image.new('RGBA', (w, w), c_bot)
        g = Image.composite(bot, top, grad)
        lay = self.layer(); lay.paste(g, (0, 0), mask); self.paste(lay)
    def outline(self, mask, color=(20, 20, 24, 255), width=1.2):
        r = max(1, int(width * SS))
        big = mask.filter(ImageFilter.MaxFilter(r * 2 + 1))
        ring = ImageChops.subtract(big, mask)
        lay = self.layer(); lay.paste(Image.new('RGBA', (self.S, self.S), color), (0, 0), ring)
        self.img = Image.alpha_composite(lay, self.img)
    def shadow(self, mask, offset=(1.5, 2), alpha=90, blur=1.5):
        sh = Image.new('RGBA', (self.S, self.S), (0, 0, 0, 0))
        m = mask.filter(ImageFilter.GaussianBlur(blur * SS))
        m = ImageChops.offset(m, int(offset[0] * SS), int(offset[1] * SS))
        m = m.point(lambda v: v * alpha // 255)
        sh.paste(Image.new('RGBA', (self.S, self.S), (0, 0, 0, 255)), (0, 0), m)
        self.img = Image.alpha_composite(sh, self.img)
    def glow(self, mask, color, radius=3, strength=1.0):
        m = mask.filter(ImageFilter.GaussianBlur(radius * SS)).point(lambda v: min(255, int(v * strength)))
        lay = self.layer(); lay.paste(Image.new('RGBA', (self.S, self.S), color), (0, 0), m)
        self.img = Image.alpha_composite(lay, self.img)
    def highlight(self, mask, strength=0.35, angle=135):
        """Блик: верхне-левая часть маски светлее."""
        w = self.S
        grad = Image.linear_gradient('L').resize((w, w)).rotate(angle - 90, resample=Image.BICUBIC)
        grad = grad.point(lambda v: max(0, 255 - v * 2))
        m = ImageChops.multiply(mask, grad).point(lambda v: int(v * strength))
        lay = self.layer(); lay.paste(Image.new('RGBA', (w, w), (255, 255, 255, 255)), (0, 0), m)
        self.paste(lay)
    def poly(self, pts, fill):
        lay = self.layer(); ImageDraw.Draw(lay).polygon([(self.p(x), self.p(y)) for x, y in pts], fill=fill); self.paste(lay)
    def line(self, pts, fill, width):
        lay = self.layer(); ImageDraw.Draw(lay).line([(self.p(x), self.p(y)) for x, y in pts], fill=fill, width=int(width * SS), joint='curve'); self.paste(lay)
    def ellipse(self, box, fill, outline=None, width=0):
        lay = self.layer(); ImageDraw.Draw(lay).ellipse([self.p(v) for v in box], fill=fill, outline=outline, width=int(width * SS)); self.paste(lay)
    def result(self):
        return self.img.resize((self.size, self.size), Image.LANCZOS)

def mask_poly(cv, pts):
    return cv.mask_layer(lambda d: d.polygon([(cv.p(x), cv.p(y)) for x, y in pts], fill=255))
def mask_ellipse(cv, box):
    return cv.mask_layer(lambda d: d.ellipse([cv.p(v) for v in box], fill=255))
def mask_rrect(cv, box, r):
    return cv.mask_layer(lambda d: d.rounded_rectangle([cv.p(v) for v in box], radius=cv.p(r), fill=255))
def mask_line(cv, pts, width):
    return cv.mask_layer(lambda d: d.line([(cv.p(x), cv.p(y)) for x, y in pts], fill=255, width=int(width * SS), joint='curve'))

def solid(cv, mask, base, light=0.35, dark=-0.35, outline=True, shadow=True):
    """Объёмная заливка: градиент от светлого к тёмному, блик, контур и мягкая тень."""
    if shadow: cv.shadow(mask)
    cv.fill_gradient(mask, shade(base, light), shade(base, dark))
    cv.highlight(mask, 0.25)
    if outline: cv.outline(mask)

def lightning(cv, start, end, color, width=2.2, jag=5, seed=1):
    import random
    rnd = random.Random(seed)
    n = 6; pts = [start]
    for i in range(1, n):
        t = i / n
        x = start[0] + (end[0] - start[0]) * t + rnd.uniform(-jag, jag)
        y = start[1] + (end[1] - start[1]) * t + rnd.uniform(-jag / 2, jag / 2)
        pts.append((x, y))
    pts.append(end)
    m = mask_line(cv, pts, width)
    cv.glow(m, color, radius=2.5, strength=1.6)
    lay = cv.layer(); lay.paste(Image.new('RGBA', (cv.S, cv.S), (255, 255, 255, 255)), (0, 0), m); cv.paste(lay)
    m2 = mask_line(cv, pts, width * 0.45)
    return pts

def save(img, path):
    img.save(path, optimize=True)
