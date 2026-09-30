"""iconkit: a small vector-to-raster kit for drawing Factorio icons in code (PIL + numpy).

Model
-----
* A `Pic` is drawn in a 64-unit design space (0..64 on both axes), whatever its pixel size
  (64 px items, 144 px thumbnail, 256 px technologies). It is rasterised `ss`x supersampled and
  box-filtered down at the end, so edges are smooth and the result is deterministic.
* Pixels are kept premultiplied (float32 RGBA), so compositing and downsampling give no dark fringes.
* Solid things are drawn inside `with pic.obj():`. Each object gets the house style of FINAL_SPEC §10.1:
  a dark outline #1A1A1F (2 px at 64, 6 px at 256), one top-left highlight, and it joins the icon's
  soft drop shadow (black, alpha 0.35, offset 2 px at 64).
* Glows, sparkles and beams are drawn outside objects: they are never outlined and cast no shadow.
* `with pic.at(scale, cx, cy):` re-uses a whole 64-unit drawing at another place and size
  (technology icons, compositions). Outline width stays fixed in output pixels.
"""
from contextlib import contextmanager
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUTLINE = '#1A1A1F'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


# ---------------------------------------------------------------- colours (floats 0..1, RGBA)
def hexc(h, a=1.0):
    if isinstance(h, tuple):
        return h if len(h) == 4 else tuple(h) + (a,)
    h = h.lstrip('#')
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def mix(c1, c2, t):
    c1, c2 = hexc(c1), hexc(c2)
    return tuple(c1[i] * (1 - t) + c2[i] * t for i in range(4))


def shade(c, k):
    """k > 0: towards white, k < 0: towards black (alpha kept)."""
    c = hexc(c)
    if k >= 0:
        return mix(c, (1, 1, 1, c[3]), k)
    return mix(c, (0, 0, 0, c[3]), -k)


def alpha(c, a):
    c = hexc(c)
    return (c[0], c[1], c[2], a)


def to255(c):
    c = hexc(c)
    return tuple(int(round(v * 255)) for v in c)


# ---------------------------------------------------------------- mask morphology (numpy, no scipy)
def dilate(a, r):
    """Grey dilation of a 0..1 mask by a disc of radius r pixels (soft rim, so the result stays anti-aliased)."""
    if r <= 0:
        return a.copy()
    ri = int(math.ceil(r + 0.5))
    H, W = a.shape
    p = np.pad(a, ri)
    out = a.copy()
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            d = math.hypot(dx, dy)
            w = min(1.0, r + 0.5 - d)
            if w <= 0 or (dx == 0 and dy == 0):
                continue
            sl = p[ri + dy:ri + dy + H, ri + dx:ri + dx + W]
            if w >= 1:
                np.maximum(out, sl, out=out)
            else:
                np.maximum(out, sl * w, out=out)
    return out


def erode(a, r):
    return 1.0 - dilate(1.0 - a, r)


def blur(a, r):
    """Gaussian blur of a 0..1 mask (radius in pixels) via PIL on 16-bit precision."""
    if r <= 0:
        return a.copy()
    im = Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8), 'L')
    im = im.filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, dtype=np.float32) / 255.0


def shift(a, dx, dy):
    """Shift a 2-D array by whole pixels, filling with 0."""
    out = np.zeros_like(a)
    H, W = a.shape
    xs, xd = (0, dx) if dx >= 0 else (-dx, 0)
    ys, yd = (0, dy) if dy >= 0 else (-dy, 0)
    w, h = W - abs(dx), H - abs(dy)
    if w > 0 and h > 0:
        out[yd:yd + h, xd:xd + w] = a[ys:ys + h, xs:xs + w]
    return out


def over(dst, src):
    """Premultiplied 'over': src over dst, in place on dst (H,W,4)."""
    dst *= (1.0 - src[..., 3:4])
    dst += src
    return dst


# ---------------------------------------------------------------- the picture
class Pic:
    def __init__(self, size=64, ss=None, outline_px=None, shadow=True):
        self.size = size
        self.ss = ss or (4 if size <= 64 else (3 if size <= 160 else 2))
        self.S = size * self.ss
        self.unit = self.S / 64.0                      # supersampled pixels per design unit
        self.px = self.ss                              # supersampled pixels per output pixel
        self.opx = outline_px if outline_px is not None else {64: 2, 144: 4, 256: 6}.get(size, max(2, round(size / 32)))
        self.img = np.zeros((self.S, self.S, 4), np.float32)
        self.solid = np.zeros((self.S, self.S), np.float32)
        self.cur = None
        self.tf = (1.0, 0.0, 0.0)                      # x' = x*s + dx (units)
        self.want_shadow = shadow
        yy, xx = np.mgrid[0:self.S, 0:self.S].astype(np.float32)
        self.X, self.Y = xx + 0.5, yy + 0.5

    # ---- transforms
    def T(self, x, y):
        s, dx, dy = self.tf
        return ((x * s + dx) * self.unit, (y * s + dy) * self.unit)

    def L(self, v):
        """a length in units -> supersampled pixels"""
        return v * self.tf[0] * self.unit

    @contextmanager
    def at(self, scale, cx=32, cy=32):
        """Draw the 64-unit design scaled by `scale` with its centre (32,32) at (cx,cy)."""
        old = self.tf
        s, dx, dy = old
        ns = s * scale
        # x_new_units = (x-32)*scale + cx, then old transform
        self.tf = (ns, s * (cx - 32 * scale) + dx, s * (cy - 32 * scale) + dy)
        try:
            yield
        finally:
            self.tf = old

    # ---- masks (numpy float32 0..1 at S x S)
    def _mask(self, fn):
        m = Image.new('L', (self.S, self.S), 0)
        fn(ImageDraw.Draw(m))
        return np.asarray(m, dtype=np.float32) / 255.0

    def mpoly(self, pts):
        q = [self.T(x, y) for x, y in pts]
        return self._mask(lambda d: d.polygon(q, fill=255))

    def mell(self, box):
        x0, y0 = self.T(box[0], box[1]); x1, y1 = self.T(box[2], box[3])
        return self._mask(lambda d: d.ellipse([x0, y0, x1, y1], fill=255))

    def mcirc(self, cx, cy, r):
        return self.mell((cx - r, cy - r, cx + r, cy + r))

    def mrect(self, box):
        x0, y0 = self.T(box[0], box[1]); x1, y1 = self.T(box[2], box[3])
        return self._mask(lambda d: d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255))

    def mrrect(self, box, r):
        x0, y0 = self.T(box[0], box[1]); x1, y1 = self.T(box[2], box[3])
        rr = max(0, int(self.L(r)))
        return self._mask(lambda d: d.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=rr, fill=255))

    def mline(self, pts, w, round_caps=True):
        q = [self.T(x, y) for x, y in pts]
        ww = max(1, int(round(self.L(w))))

        def fn(d):
            d.line(q, fill=255, width=ww, joint='curve')
            if round_caps:
                for (x, y) in (q[0], q[-1]):
                    d.ellipse([x - ww / 2, y - ww / 2, x + ww / 2, y + ww / 2], fill=255)
        return self._mask(fn)

    def marc(self, box, a0, a1, w):
        """arc stroke of an ellipse box, angles in degrees (PIL: 0 = east, clockwise)"""
        pts = arc_pts(box, a0, a1)
        return self.mline(pts, w)

    def mtext(self, text, cx, cy, size, font=FONT_BOLD):
        f = ImageFont.truetype(font, max(4, int(self.L(size))))
        X, Y = self.T(cx, cy)
        return self._mask(lambda d: d.text((X, Y), text, font=f, fill=255, anchor='mm'))

    # ---- painting
    def _field(self, m, c0, c1, mode, lk, dk):
        """colour field for a part: light/dark gradient over the part's bounding box"""
        c = np.array(hexc(c0), np.float32)
        if mode == 'flat':
            rgb = np.broadcast_to(c[:3], m.shape + (3,)).copy()
            return rgb, c[3]
        ys, xs = np.nonzero(m > 0.02)
        if len(xs) == 0:
            return np.zeros(m.shape + (3,), np.float32), c[3]
        x0, x1 = xs.min(), xs.max() + 1
        y0, y1 = ys.min(), ys.max() + 1
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        u = np.clip((self.X - x0) / w, 0, 1)
        v = np.clip((self.Y - y0) / h, 0, 1)
        if mode == 'diag':
            t = (u + v) / 2
            b = lk + (dk - lk) * t
        elif mode == 'v':
            b = lk + (dk - lk) * v
        elif mode == 'h':
            b = lk + (dk - lk) * u
        elif mode == 'cyl':      # vertical cylinder: bright band at 30 % from the left
            b = np.where(u < 0.3, dk * 0.35 + (lk - dk * 0.35) * (u / 0.3), lk + (dk - lk) * (np.clip(u - 0.3, 0, None) / 0.7) ** 0.9)
        elif mode == 'cylh':     # horizontal cylinder: bright band at 30 % from the top
            b = np.where(v < 0.3, dk * 0.35 + (lk - dk * 0.35) * (v / 0.3), lk + (dk - lk) * (np.clip(v - 0.3, 0, None) / 0.7) ** 0.9)
        elif mode == 'rad':      # sphere-ish: light spot top-left
            d = np.hypot(u - 0.32, v - 0.3) / 0.95
            b = lk + (dk - lk) * np.clip(d, 0, 1)
        else:
            raise ValueError(mode)
        base = c[:3]
        if c1 is not None:       # explicit second colour: plain two-colour gradient over t in 0..1
            c1a = np.array(hexc(c1), np.float32)[:3]
            t = (b - lk) / (dk - lk) if dk != lk else np.zeros_like(b)
            rgb = base * (1 - t[..., None]) + c1a * t[..., None]
            return rgb, c[3]
        bb = b[..., None]
        rgb = np.where(bb >= 0, base + (1 - base) * bb, base * (1 + bb))
        return rgb.astype(np.float32), c[3]

    def fill(self, m, color, mode='diag', lk=0.28, dk=-0.32, edge=0.5, ek=-0.45, a=1.0, c1=None, into=None):
        """Paint mask m. edge = width (output px) of a darker inner rim that separates parts."""
        rgb, ca = self._field(m, color, c1, mode, lk, dk)
        if edge and edge > 0:
            # edge is given in pixels of a 64 px icon; it grows with the outline on bigger pictures
            e = np.clip(m - erode(m, edge * self.px * self.opx / 2), 0, 1)
            ec = np.array(shade(color, ek), np.float32)[:3]
            rgb = rgb * (1 - e[..., None]) + ec * e[..., None]
        al = (m * ca * a)[..., None]
        src = np.concatenate([rgb * al, al], axis=-1).astype(np.float32)
        tgt = into if into is not None else (self.cur if self.cur is not None else self.img)
        over(tgt, src)
        return m

    def paint_rgba(self, rgb, al, into=None):
        """paint a free colour field (H,W,3) with alpha (H,W)"""
        src = np.concatenate([rgb * al[..., None], al[..., None]], axis=-1).astype(np.float32)
        tgt = into if into is not None else (self.cur if self.cur is not None else self.img)
        over(tgt, src)

    def glow(self, m, color, r=3.0, k=1.0):
        """soft glow around mask m (r in units), drawn on the picture (never outlined)"""
        g = np.clip(blur(m, self.L(r)) * k, 0, 1)
        self.fill(g, color, mode='flat', edge=0, into=self.img)

    def fx(self, m, color, a=1.0):
        """flat unoutlined paint straight on the picture (sparkles, beams, cores)"""
        self.fill(m, color, mode='flat', edge=0, a=a, into=self.img)

    @contextmanager
    def obj(self, outline=True, highlight=0.22, shadow=True, ow=None):
        prev = self.cur
        lay = np.zeros_like(self.img)
        self.cur = lay
        try:
            yield
        finally:
            self.cur = prev
        a = lay[..., 3].copy()
        if highlight:
            ys, xs = np.nonzero(a > 0.02)
            if len(xs):
                x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
                t = ((self.X - x0) / max(1, x1 - x0) + (self.Y - y0) / max(1, y1 - y0)) / 2
                h = (np.clip(1 - t / 0.55, 0, 1) ** 1.5 * highlight)[..., None]
                # 'atop': the highlight only lightens what is there (premultiplied white = alpha)
                lay[..., :3] = lay[..., :3] * (1 - h) + a[..., None] * h
        full = a
        if outline:
            w = (self.opx if ow is None else ow) * self.px
            ring = np.clip(dilate(a, w) - a, 0, 1)
            oc = np.array(hexc(OUTLINE), np.float32)
            ol = np.zeros_like(lay)
            ol[..., :3] = oc[:3] * ring[..., None]
            ol[..., 3] = ring
            over(ol, lay)
            lay = ol
            full = lay[..., 3]
        over(self.cur if self.cur is not None else self.img, lay)
        if shadow:
            np.maximum(self.solid, full, out=self.solid)

    # ---- output
    def result(self):
        out = self.img.copy()
        if self.want_shadow and self.solid.max() > 0:
            off = int(round(self.opx * self.px))
            sh = blur(self.solid, 1.2 * self.px * self.opx / 2)
            sh = shift(sh, off, off) * 0.35
            shl = np.zeros_like(out)
            shl[..., 3] = sh
            over(shl, out)
            out = shl
        n, s = self.size, self.ss
        small = out.reshape(n, s, n, s, 4).mean(axis=(1, 3))
        a = small[..., 3:4]
        rgb = np.where(a > 1e-6, small[..., :3] / np.maximum(a, 1e-6), 0)
        arr = np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)], -1)
        arr = (arr * 255 + 0.5).astype(np.uint8)
        # fully transparent pixels get rgb 0 (smaller, deterministic PNGs)
        arr[arr[..., 3] == 0] = 0
        return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------- geometry helpers
def arc_pts(box, a0, a1, n=None):
    """points on an ellipse box from angle a0 to a1 (degrees, 0 = east, clockwise as in PIL)"""
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    n = n or max(8, int(abs(a1 - a0) / 4))
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rot(pts, ang, cx, cy):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def star_pts(cx, cy, r, r2=None, n=4, ang=-90):
    r2 = r2 if r2 is not None else r * 0.3
    pts = []
    for i in range(2 * n):
        rr = r if i % 2 == 0 else r2
        a = math.radians(ang + i * 180 / n)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def save(img, path):
    img.save(path, optimize=True)
