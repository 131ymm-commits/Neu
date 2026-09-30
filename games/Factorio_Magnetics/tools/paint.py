#!/usr/bin/env python3
"""Magnetics for Factorio 2.0 — every picture of the mod, drawn by code (FINAL_SPEC §10).

    python3 tools/paint.py            # regenerates everything, deterministic
    python3 tools/paint.py --only X   # only pictures whose file name contains X (sheets are skipped)

Writes
  magnetics/graphics/icons/<name>.png              64x64: 11 items, 2 fluids, 26 buildings (entity = item icon)
  magnetics/graphics/icons/recipe-<recipe>.png     64x64: 4 recipes with their own art
  magnetics/graphics/icons/ammo-category-<n>.png   64x64: 3 ammo categories
  magnetics/graphics/technology/<tech>.png         256x256: 14 technologies (tier halo §10.3)
  magnetics/graphics/entity/rail-tracer.png        512x440: 8 frames of 64x440 (§4.7)
  magnetics/thumbnail.png                          144x144: mod portal thumbnail
  showcase.png                                     every icon with en + ru names (spec G1, 60 tiles)
  cards.png                                        one card per entity: icon, vanilla base, tint (spec G2)

Names come from §9, tints and vanilla bases from §4, colours from §10. The tables below are the only
place in this script where they are typed; when tools/spec.py exists, `check_against_spec()` compares.
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iconkit import (Pic, hexc, mix, shade, alpha, to255, arc_pts, rot, star_pts, blur, FONT, FONT_BOLD)  # noqa: E402

GAME = os.path.normpath(os.path.join(HERE, '..'))
MOD = os.path.join(GAME, 'magnetics')
ICONS = os.path.join(MOD, 'graphics', 'icons')
TECH = os.path.join(MOD, 'graphics', 'technology')
ENTITY = os.path.join(MOD, 'graphics', 'entity')

# ---------------------------------------------------------------- palette (§10.1)
C = dict(
    ferrite='#5C4A52', ferrite_hi='#8A7580', ferrite_sp='#B39FA8',
    alloy='#6D86C9', N='#D9534F', S='#F2F2F2',
    copper='#D6854A', copper_dk='#8C4A22',
    sc='#9FE8FF', frost='#E8FBFF', sc_deep='#3AA6C9',
    flux='#B58CFF', flux_glow='#E4D4FF', flux_deep='#5B3BA8',
    grey='#8C8C99', grey_dk='#5A5A66',
    ff='#120F17', ff_sheen='#7A5CB8',
    ln2='#BFE6FF', ln2_mist='#F0FAFF',
    steel='#8E949E', steel_dk='#4A4F57',
    arc='#9FE8FF', heal='#66FF99',
    brass='#C9A04A', bolt='#FFD84A', fire='#FF8A3D', plasma='#6FC8FF',
    stone='#8A8A80', iron_ore='#6E7A8A', copper_ore='#C87533', white='#FFFFFF',
)

# ---------------------------------------------------------------- content tables: read from tools/spec.py
# spec.py is the project's single source of truth (FINAL_SPEC §0.2 rule 4): names (en/ru), prototype
# types, vanilla bases, tints and technology tiers are taken from it, never typed here.
import spec  # noqa: E402

PACK = {'automation-science-pack': 'A', 'logistic-science-pack': 'L', 'chemical-science-pack': 'C', 'military-science-pack': 'M',
        'production-science-pack': 'P', 'utility-science-pack': 'U'}
AMMO_KIND = {'magnetics-slug': 'coilgun', 'magnetics-gauss': 'gauss turret', 'magnetics-rail': 'rail cannon'}
# display-only extras for the sheets (footprints and art notes of §4; they are not prototype numbers)
SIZE = {'sintering-kiln': '2×2', 'coil-capacitor': '1×1', 'superconducting-accumulator': '2×2', 'superconducting-pylon': '2×2',
        'mhd-generator': '3×5', 'flux-dynamo': '3×5', 'maglev-transport-belt': '1×1', 'maglev-underground-belt': '1×1',
        'maglev-splitter': '2×1', 'mend-coil': '2×2', 'coilgun-turret': '2×2', 'gauss-turret': '2×2', 'arc-emitter': '2×2',
        'rail-cannon': '2×2'}
WALLS = ('ferrite-wall', 'magnet-wall', 'superconducting-wall', 'magnet-gate', 'superconducting-gate')
BASE_NOTE = {'burner-generator': ' (steam-engine art)', 'electric-energy-interface': ' (accumulator picture)'}
# technology subject (the main unlock drawn on the halo, §10.3); magnetic-power is the 3-object composition
TECH_SUBJECT = {
    'magnetics-ferrite-sintering': 'magnetics-ferrite', 'magnetics-electromagnetic-coils': 'magnetics-coil',
    'magnetics-coilgun': 'magnetics-coilgun-turret', 'magnetics-induction-smelting': 'magnetics-induction-furnace',
    'magnetics-magnetic-mining': 'magnetics-magnetic-drill', 'magnetics-magnetic-power': 'composition',
    'magnetics-magnetic-separation': 'magnetics-magnetic-separator', 'magnetics-magnetic-fortifications': 'magnetics-magnet-wall',
    'magnetics-arc-emitter': 'magnetics-arc-emitter', 'magnetics-superconductivity': 'magnetics-superconducting-cable',
    'magnetics-superconducting-power': 'magnetics-superconducting-pylon', 'magnetics-flux-energy': 'magnetics-flux-crystal',
    'magnetics-maglev-logistics': 'magnetics-maglev-transport-belt', 'magnetics-superconducting-defense': 'magnetics-rail-cannon',
}
TIER = dict(red='#D9534F', green='#5CB85C', blue='#5BC0DE', military='#E07AB8', purple='#9B59B6', yellow='#F0C419')  # §10.3


def _short(n):
    return n.replace('magnetics-', '', 1)


ITEMS = [(n, v['en'], v['ru'], 'item · fuel 100 MJ' if n == 'magnetics-flux-crystal' else 'item') for n, v in spec.ITEMS.items()]
ITEMS += [(n, v['en'], v['ru'], 'ammo · ' + AMMO_KIND.get(v.get('category', ''), 'turret')) for n, v in spec.AMMO.items()]
FLUIDS = [(n, v['en'], v['ru'], 'fluid') for n, v in spec.FLUIDS.items()]
RECIPES = [(n, v['en'], v['ru']) for n, v in spec.RECIPES.items() if v.get('own_icon')]
AMMO_CATEGORIES = [(n, v['en'], v['ru']) for n, v in spec.AMMO_CATEGORIES.items()]
ENTITIES = []  # name, en, ru, prototype type, vanilla base, size, tint
for _n, _v in spec.ENTITIES.items():
    _s = _short(_n)
    _size = SIZE.get(_s, '1×1' if _s in WALLS else '3×3')
    _base = _v['base'] + BASE_NOTE.get(_v['base'], '') + (' (art ×0.5)' if _s == 'coil-capacitor' else '')
    ENTITIES.append((_n, _v['en'], _v['ru'], _v['type'], _base, _size, tuple(_v['tint'][:3])))
TECHS = []  # tech, en, ru, tier, packs, subject
for _n, _v in spec.TECHS.items():
    TECHS.append((_n, _v['en'], _v['ru'], spec.TECH_TIER[_short(_n)], ' '.join(PACK.get(x, '?') for x in _v['packs']), TECH_SUBJECT[_n]))

# Approximate body colour of each vanilla base sprite, only for the "base x tint" preview swatch on cards.png.
# The headless server ships no PNGs, so these are estimates by eye, not samples (marked "≈" on the cards).
VANILLA_BODY_APPROX = {
    'stone-furnace': '#9C8A74', 'electric-furnace': '#8A8580', 'assembling-machine-2': '#7E8E9E',
    'chemical-plant': '#8E8E88', 'centrifuge': '#8C9488', 'assembling-machine-3': '#7F9486',
    'electric-mining-drill': '#8A8E7E', 'express-transport-belt': '#3F8FD8', 'express-underground-belt': '#3F8FD8',
    'express-splitter': '#3F8FD8', 'accumulator': '#8C8C90', 'big-electric-pole': '#8E8A84',
    'burner-generator': '#8A847A', 'solar-panel': '#4C5A78', 'stone-wall': '#9A968C', 'gate': '#8E8A7E',
    'electric-energy-interface': '#8C8C90', 'gun-turret': '#8A8272', 'laser-turret': '#80868C',
}


def tint_hex(t):
    # round half up on the decimal value (0.70 x 255 = 178.5 -> 179 = B3, as written in §10.2)
    return '#%02X%02X%02X' % tuple(int(v * 255 + 0.5 + 1e-6) for v in t)


TINT = {e[0]: tint_hex(e[6]) for e in ENTITIES}          # §10.2 body colour = tint x 255 (checked in selftest)

# ---------------------------------------------------------------- shape helpers
def U(*masks):
    out = masks[0].copy()
    for m in masks[1:]:
        np.maximum(out, m, out=out)
    return out


def minus(a, b):
    return np.clip(a - b, 0, 1)


def inter(a, b):
    return np.minimum(a, b)


def cyl_v(p, x0, x1, yt, yb, ry, col, top=None, lk=0.3, dk=-0.38, topk=0.3, edge=0.5):
    """vertical cylinder seen from the front-top; returns (body mask, top mask)"""
    body = U(p.mrect((x0, yt, x1, yb)), p.mell((x0, yb - ry, x1, yb + ry)))
    p.fill(body, col, 'cyl', lk, dk, edge=edge)
    t = p.mell((x0, yt - ry, x1, yt + ry))
    p.fill(t, top if top is not None else shade(col, topk), 'diag', 0.15, -0.15, edge=edge)
    return body, t


def band_v(p, x0, x1, y, h, ry, col, lk=0.3, dk=-0.4):
    """a ring band around a vertical cylinder (front half visible)"""
    m = U(p.mrect((x0, y, x1, y + h)), p.mell((x0, y + h - ry, x1, y + h + ry)))
    m = minus(m, p.mell((x0, y - ry, x1, y + ry)))
    p.fill(m, col, 'cyl', lk, dk)
    return m


def cyl_h(p, x0, x1, yt, yb, rx, col, cap=None, lk=0.3, dk=-0.4, capk=0.2):
    """horizontal cylinder, axis along x, left end cap visible"""
    body = U(p.mrect((x0, yt, x1, yb)), p.mell((x1 - rx, yt, x1 + rx, yb)))
    p.fill(body, col, 'cylh', lk, dk)
    c = p.mell((x0 - rx, yt, x0 + rx, yb))
    p.fill(c, cap if cap is not None else shade(col, capk), 'diag', 0.15, -0.2)
    return body, c


def box(p, x0, y0, x1, y1, d, col, r=2.5, topk=0.12, frontk=-0.28, mode='diag'):
    """a block seen from the front-top: top face (x0,y0)-(x1,y1-d), front face below it"""
    front = p.mrrect((x0, y0 + d, x1, y1), r)
    p.fill(front, shade(col, frontk), 'h', 0.12, -0.25)
    top = p.mrrect((x0, y0, x1, y1 - d), r)
    p.fill(top, shade(col, topk), mode)
    return top, front


def octa(p, cx, cy, w, h, cols, midx=-0.18, midy=0.1, edge=0.35):
    """faceted octahedron (flux crystal): cols = (upper-left, upper-right, lower-left, lower-right)"""
    T, B = (cx, cy - h), (cx, cy + h)
    Lp, R = (cx - w, cy), (cx + w, cy)
    M = (cx + midx * w, cy + midy * h)
    faces = [(T, Lp, M), (T, M, R), (Lp, M, B), (M, R, B)]
    ms = []
    for f, c in zip(faces, cols):
        m = p.mpoly(f)
        p.fill(m, c, 'diag', 0.12, -0.12, edge=edge, ek=-0.25)
        ms.append(m)
    return U(*ms)


def drop_pts(cx, cy, R, k=2.1):
    """tear drop: circle radius R at (cx,cy) with its tip k*R above the centre"""
    a = math.degrees(math.acos(1 / k))
    pts = arc_pts((cx - R, cy - R, cx + R, cy + R), -90 + a, 270 - a, 48)
    return [(cx, cy - k * R)] + pts


def horseshoe_pts(cx, cy, R, r, leg, ang=0.0):
    """U magnet opening upwards (before rotation), returns (body polygon, left tip, right tip)"""
    outer = arc_pts((cx - R, cy - R, cx + R, cy + R), 180, 0, 36)
    inner = arc_pts((cx - r, cy - r, cx + r, cy + r), 0, 180, 36)
    body = outer + [(cx + R, cy - leg), (cx + r, cy - leg)] + inner + [(cx - r, cy - leg), (cx - R, cy - leg)]
    tip = leg * 0.55
    lt = [(cx - R, cy - leg), (cx - r, cy - leg), (cx - r, cy - leg + tip), (cx - R, cy - leg + tip)]
    rt = [(cx + r, cy - leg), (cx + R, cy - leg), (cx + R, cy - leg + tip), (cx + r, cy - leg + tip)]
    return [rot(q, ang, cx, cy) for q in (body, lt, rt)]


def horseshoe(p, cx, cy, R, r, leg, ang=0.0, body=None, tips=None):
    b, lt, rt = horseshoe_pts(cx, cy, R, r, leg, ang)
    p.fill(p.mpoly(b), body or C['N'], 'diag', 0.3, -0.3)
    for t in (lt, rt):
        p.fill(p.mpoly(t), tips or C['S'], 'diag', 0.2, -0.35, edge=0.4)


def glyph(p):
    """the Magnetics badge on every building icon: a small red/white horseshoe, lower right (§10.1)"""
    with p.obj():
        horseshoe(p, 54.2, 52.6, 6.4, 2.8, 5.6, ang=-35)


def sparkle(p, cx, cy, r, col=None, glow=None):
    m = p.mpoly(star_pts(cx, cy, r, r * 0.22, 4))
    p.glow(m, glow or C['sc'], r * 0.5, 1.6)
    p.fx(m, col or C['frost'])


def lightning_pts(x0, y0, x1, y1, n=6, jag=4.0, seed=1):
    rnd = random.Random(seed)
    pts = [(x0, y0)]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    for i in range(1, n):
        t = i / n
        o = rnd.uniform(-jag, jag) * (1 if i % 2 else -1)
        pts.append((x0 + dx * t + nx * o, y0 + dy * t + ny * o))
    pts.append((x1, y1))
    return pts


def bolt_fx(p, pts, w=1.6, col=None, core='#FFFFFF', glow_r=2.4):
    m = p.mline(pts, w)
    p.glow(m, col or C['arc'], glow_r, 2.0)
    p.fx(m, col or C['arc'])
    p.fx(p.mline(pts, w * 0.45), core)


def field_arc_fx(p, pts, w, col, glow=None, a=1.0, glow_r=1.6):
    m = p.mline(pts, w)
    if glow:
        p.glow(m, glow, glow_r, 1.2)
    p.fx(m, col, a)


def dipole_pts(L, side=1, cx=32, cy=32, n=60, th0=8, th1=172, rmax=None):
    """a magnetic dipole field line r = L sin^2(theta), axis vertical, lobe to the right (side=1) or left"""
    pts = []
    for i in range(n + 1):
        th = math.radians(th0 + (th1 - th0) * i / n)
        r = L * math.sin(th) ** 2
        pts.append((cx + side * r * math.sin(th), cy - r * math.cos(th)))
    return pts


def speckle(p, m, n, col, seed, r=0.7, a=0.9):
    """random dots inside mask m (seeded, deterministic)"""
    rnd = random.Random(seed)
    ys, xs = np.nonzero(m > 0.9)
    if not len(xs):
        return
    dots = np.zeros_like(m)
    for _ in range(n):
        k = rnd.randrange(len(xs))
        X, Y = xs[k] / p.unit, ys[k] / p.unit          # identity transform inside callers
        s, dx, dy = p.tf
        ux, uy = (X - dx) / s, (Y - dy) / s
        rr = r * rnd.uniform(0.7, 1.3)
        dots = np.maximum(dots, p.mell((ux - rr, uy - rr, ux + rr, uy + rr)))
    p.fill(inter(dots, m), col, 'flat', edge=0, a=a)


def along(p0, p1, local):
    """map local (u along p0->p1 in units, v across) to picture coordinates"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    return [(p0[0] + ux * u + nx * v, p0[1] + uy * u + ny * v) for u, v in local]


def rock_pts(cx, cy, r, seed, n=9, jit=0.22, squash=0.85):
    rnd = random.Random(seed)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n + rnd.uniform(-0.2, 0.2)
        rr = r * (1 + rnd.uniform(-jit, jit))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a) * squash))
    return pts


# ================================================================ items (§10.2)
def art_ferrite(p):
    cx, cy, rx, ry, t = 32, 25, 25.5, 14, 12
    V = [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    V.append(V[0])
    with p.obj():
        sides = []
        for i, col, k in ((0, C['ferrite'], -0.3), (1, C['ferrite'], -0.08), (2, C['ferrite_hi'], -0.12)):
            a, b = V[i], V[i + 1]
            m = p.mpoly([a, b, (b[0], b[1] + t), (a[0], a[1] + t)])
            p.fill(m, shade(col, k), 'h', 0.08, -0.2)
            sides.append(m)
        top = p.mpoly(V[:-1])
        p.fill(top, C['ferrite_hi'], 'diag', 0.22, -0.18)
        # a shallow sintered dimple on the top face
        dim = p.mell((cx - 11, cy - 5.5, cx + 11, cy + 5.5))
        p.fill(dim, shade(C['ferrite_hi'], -0.12), 'diag', -0.15, 0.12, edge=0.4, ek=-0.3)
        speckle(p, top, 26, C['ferrite_sp'], 11, r=0.75)
        speckle(p, U(*sides), 14, C['ferrite_hi'], 12, r=0.7)
        speckle(p, top, 10, shade(C['ferrite'], -0.4), 13, r=0.6)


def art_coil(p):
    cx, cy = 32, 33
    ox, oy, ix, iy = 27, 19.5, 10.5, 6.8
    hole_c = (cx, cy - 1.2)
    with p.obj():
        outer = p.mell((cx - ox, cy - oy, cx + ox, cy + oy))
        hole = p.mell((hole_c[0] - ix, hole_c[1] - iy, hole_c[0] + ix, hole_c[1] + iy))
        ring = minus(outer, hole)
        # the tube's near side, seen below the top surface
        side = minus(p.mell((cx - ox, cy - oy + 5, cx + ox, cy + oy + 3.5)), outer)
        p.fill(side, shade(C['ferrite'], -0.25), 'h', 0.1, -0.3)
        p.fill(ring, C['ferrite'], 'rad', 0.35, -0.35)
        # the far inner wall, seen through the hole
        wall = minus(hole, p.mell((hole_c[0] - ix, hole_c[1] - iy + 4.2, hole_c[0] + ix, hole_c[1] + iy + 4.2)))
        p.fill(wall, shade(C['ferrite'], -0.35), 'v', 0.0, -0.3, edge=0)
        # six copper windings wrapped over the tube
        for k, th in enumerate((300, 0, 60, 120, 180, 240)):
            do, di = 12, 17
            pts = []
            for a in (th - do, th + do):
                pts.append((cx + ox * 1.04 * math.cos(math.radians(a)), cy + oy * 1.04 * math.sin(math.radians(a)) + (3.2 if 20 < a % 360 < 160 else 0)))
            for a in (th + di, th - di):
                pts.append((hole_c[0] + ix * 0.9 * math.cos(math.radians(a)), hole_c[1] + iy * 0.9 * math.sin(math.radians(a))))
            m = p.mpoly(pts)
            p.fill(m, C['copper'], 'diag', 0.3, -0.25, c1=None, edge=0.5, ek=-0.55)
            # turn lines inside the band
            for f in (-0.33, 0.33):
                a_o, a_i = th + do * f, th + di * f
                q = [(cx + ox * 1.0 * math.cos(math.radians(a_o)), cy + oy * 1.0 * math.sin(math.radians(a_o))),
                     (hole_c[0] + ix * 0.95 * math.cos(math.radians(a_i)), hole_c[1] + iy * 0.95 * math.sin(math.radians(a_i)))]
                p.fill(inter(p.mline(q, 0.7), m), C['copper_dk'], 'flat', edge=0, a=0.75)


def art_magnet_alloy(p):
    top = [(16, 15), (48, 15), (53, 28), (11, 28)]
    front = [(11, 28), (53, 28), (59, 46), (5, 46)]
    left = [(-5, -5), (26.5, -5), (26.5, 15), (24.2, 28), (21.6, 46), (21.6, 70), (-5, 70)]
    right = [(70, -5), (37.5, -5), (37.5, 15), (39.8, 28), (42.4, 46), (42.4, 70), (70, 70)]
    with p.obj():
        fm, tm = p.mpoly(front), p.mpoly(top)
        lm, rm = p.mpoly(left), p.mpoly(right)
        p.fill(fm, shade(C['alloy'], -0.12), 'h', 0.1, -0.3)
        p.fill(tm, shade(C['alloy'], 0.15), 'diag', 0.2, -0.15)
        p.fill(inter(fm, lm), shade(C['N'], -0.12), 'h', 0.1, -0.25, edge=0.4)
        p.fill(inter(tm, lm), shade(C['N'], 0.08), 'diag', 0.2, -0.15, edge=0.4)
        p.fill(inter(fm, rm), shade(C['S'], -0.2), 'h', 0.05, -0.2, edge=0.4)
        p.fill(inter(tm, rm), C['S'], 'diag', 0.1, -0.12, edge=0.4)
        p.fill(p.mtext('N', 19.5, 21.8, 10), '#FFFFFF', 'flat', edge=0, a=0.95)
        p.fill(p.mtext('S', 45, 21.8, 10), '#B03A36', 'flat', edge=0, a=0.95)


def art_superconducting_cable(p):
    cx, cy, R = 27, 29, 22
    with p.obj():  # tape end leaving the reel
        tail = [(cx + 4, cy + R - 5), (46, 53), (60, 50), (61.5, 55), (46, 58.5), (cx + 2, cy + R - 0.5)]
        p.fill(p.mpoly(tail), C['sc'], 'h', 0.25, -0.15, edge=0.45, ek=-0.4)
    with p.obj():
        side = p.mline([(cx, cy), (cx + 5, cy + 3)], 2 * R)
        p.fill(side, shade(C['sc_deep'], -0.35), 'diag', 0.1, -0.3)
        flange = p.mcirc(cx, cy, R)
        p.fill(flange, C['sc_deep'], 'rad', 0.25, -0.35)
        rim = minus(flange, p.mcirc(cx, cy, R - 2.6))
        p.fill(rim, C['frost'], 'diag', 0.0, -0.45, edge=0)
        tape = p.mcirc(cx, cy, R - 4.2)
        p.fill(tape, C['sc'], 'rad', 0.35, -0.2, edge=0.4, ek=-0.35)
        for r in (15.2, 12.2, 9.4):
            ringm = minus(p.mcirc(cx, cy, r + 0.45), p.mcirc(cx, cy, r - 0.45))
            p.fill(ringm, C['sc_deep'], 'flat', edge=0, a=0.55)
        hub = p.mcirc(cx, cy, 6.5)
        p.fill(hub, C['steel'], 'rad', 0.3, -0.4, edge=0.5, ek=-0.5)
        for a in (-90, 30, 150):
            hx, hy = cx + 3.4 * math.cos(math.radians(a)), cy + 3.4 * math.sin(math.radians(a))
            p.fill(p.mcirc(hx, hy, 1.3), C['steel_dk'], 'flat', edge=0)
    sparkle(p, 55, 10, 5.5)
    sparkle(p, 57.5, 34, 4)
    sparkle(p, 8, 55, 4.2)


def crystal(p, cx=32, cy=32, w=15.5, h=27, charged=True, arcs=True, glow=True):
    if charged:
        cols = (C['flux_glow'], C['flux'], shade(C['flux'], -0.18), C['flux_deep'])
    else:
        cols = (shade(C['grey'], 0.28), C['grey'], shade(C['grey'], -0.12), C['grey_dk'])
    k = h / 27
    if charged and arcs:
        for a0, a1 in ((112, 248), (-68, 68)):
            pts = arc_pts((cx - 24 * k, cy - 25 * k, cx + 24 * k, cy + 25 * k), a0, a1, 40)
            field_arc_fx(p, pts, 2.1 * k, C['flux_glow'], glow=C['flux'], glow_r=2.0 * k)
    if charged and glow:
        halo = p.mpoly([(cx, cy - h), (cx + w, cy), (cx, cy + h), (cx - w, cy)])
        p.glow(halo, C['flux'], 4.5 * k, 0.9)
    with p.obj():
        m = octa(p, cx, cy, w, h, cols)
        if not charged:  # one hairline crack across the upper-left facet
            crack = [(cx - 4 * k, cy - 20 * k), (cx - 2.2 * k, cy - 14 * k), (cx - 5.5 * k, cy - 9 * k), (cx - 3 * k, cy - 3 * k), (cx - 4.2 * k, cy + 1 * k)]
            p.fill(inter(p.mline(crack, 0.9 * k), m), '#34343C', 'flat', edge=0)
            crack2 = [(x + 0.9 * k, y + 0.3 * k) for x, y in crack]
            p.fill(inter(p.mline(crack2, 0.5 * k), m), shade(C['grey'], 0.45), 'flat', edge=0, a=0.8)
    if charged:
        core = p.mell((cx - 4.5 * k, cy - 6 * k, cx + 3 * k, cy + 6 * k))
        p.glow(core, '#FFFFFF', 3.2 * k, 1.5)
        p.fx(p.mell((cx - 2.6 * k, cy - 3.6 * k, cx + 1.4 * k, cy + 3.6 * k)), '#FFFFFF', 0.95)


def art_flux_crystal(p):
    crystal(p, charged=True)


def art_flux_crystal_uncharged(p):
    crystal(p, charged=False)


def slug_clip(p, body, tip=None, top=None, clip=None):
    xs = (12.5, 22.2, 31.9, 41.6, 51.3)
    r, yt, yb, ry = 4.3, 15, 44, 2.3
    with p.obj():
        for i, x in enumerate(xs):
            cyl_v(p, x - r, x + r, yt, yb, ry, body, top=top)
            if tip:
                band = U(p.mrect((x - r, yt, x + r, yt + 7)), p.mell((x - r, yt + 7 - ry, x + r, yt + 7 + ry)))
                p.fill(band, tip, 'cyl', 0.35, -0.35, edge=0.4)
                p.fill(p.mell((x - r, yt - ry, x + r, yt + ry)), shade(tip, 0.3), 'diag', 0.15, -0.1, edge=0.4)
        box(p, 6, 36, 58, 50, 5, clip or C['brass'], r=2, topk=0.2, frontk=-0.2)
        for x in (9.5, 54.5):
            p.fill(p.mcirc(x, 40, 1.4), shade(clip or C['brass'], -0.45), 'flat', edge=0)


def art_ferrite_slug(p):
    slug_clip(p, C['ferrite'], top=C['ferrite_hi'])


def art_magnet_slug(p):
    slug_clip(p, C['alloy'], tip=C['N'])


def heavy_bolt(p, p0, p1, w, col, ring=None):
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    body = along(p0, p1, [(0, -w * 0.5), (L * 0.74, -w * 0.5), (L, 0), (L * 0.74, w * 0.5), (0, w * 0.5)])
    p.fill(p.mpoly(body), col, 'diag', 0.3, -0.35)
    nose = along(p0, p1, [(L * 0.74, -w * 0.5), (L, 0), (L * 0.74, w * 0.5)])
    p.fill(p.mpoly(nose), shade(col, 0.25), 'diag', 0.25, -0.3, edge=0.4)
    tail = along(p0, p1, [(1.5, -w * 0.72), (6.5, -w * 0.72), (6.5, w * 0.72), (1.5, w * 0.72)])
    p.fill(p.mpoly(tail), shade(C['steel'], -0.1), 'diag', 0.25, -0.3, edge=0.4)
    stripe = along(p0, p1, [(L * 0.3, -w * 0.5), (L * 0.36, -w * 0.5), (L * 0.36, w * 0.5), (L * 0.3, w * 0.5)])
    p.fill(p.mpoly(stripe), ring or C['sc'], 'flat', edge=0, a=0.9)


def art_gauss_slug(p):
    with p.obj():
        heavy_bolt(p, (9, 55), (57, 7), 10, C['alloy'])
    with p.obj():
        heavy_bolt(p, (9, 9), (57, 57), 10, shade(C['alloy'], 0.1))
    ringm = minus(p.mell((17, 22, 47, 42)), p.mell((21.5, 25.8, 42.5, 38.2)))
    p.glow(ringm, C['sc'], 2.2, 1.4)
    with p.obj(ow=1.2):
        p.fill(ringm, C['sc'], 'diag', 0.4, -0.25, edge=0.4, ek=-0.35)


def rail_dart(p, core=False):
    p0, p1 = (7, 57), (58, 6)
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    for v in (-7.2, 7.2):
        pts = along(p0, p1, [(9, v), (L - 16, v)])
        # flux version: the rails glow violet as well, so the two slugs differ at 32 px
        field_arc_fx(p, pts, 1.7, C['flux_glow'] if core else C['sc'], glow=C['flux'] if core else C['sc'], glow_r=1.8)
    with p.obj():
        fins = along(p0, p1, [(0, -8), (12, -3.2), (12, 3.2), (0, 8), (3, 0)])
        p.fill(p.mpoly(fins), C['steel_dk'], 'diag', 0.25, -0.2)
        body = along(p0, p1, [(4, -3.4), (L - 13, -3.4), (L, 0), (L - 13, 3.4), (4, 3.4)])
        p.fill(p.mpoly(body), C['steel'], 'diag', 0.35, -0.35)
        nose = along(p0, p1, [(L - 13, -3.4), (L, 0), (L - 13, 3.4)])
        p.fill(p.mpoly(nose), shade(C['steel'], 0.3), 'diag', 0.2, -0.3, edge=0.4)
        for u in (16, 22):
            band = along(p0, p1, [(u, -3.5), (u + 2.2, -3.5), (u + 2.2, 3.5), (u, 3.5)])
            p.fill(p.mpoly(band), C['sc_deep'], 'flat', edge=0)
    if core:
        c = along(p0, p1, [(L * 0.52, 0)])[0]
        m = p.mpoly(along(p0, p1, [(L * 0.52 - 10, 0), (L * 0.52, -6.5), (L * 0.52 + 10, 0), (L * 0.52, 6.5)]))
        p.glow(m, C['flux'], 5.5, 1.8)
        with p.obj(ow=1.3):
            p.fill(m, C['flux'], 'diag', 0.45, -0.3, edge=0.4)
        p.glow(p.mcirc(c[0], c[1], 1.8), '#FFFFFF', 1.8, 1.5)
        p.fx(p.mcirc(c[0] - 0.4, c[1] - 0.4, 1.3), '#FFFFFF')


def art_rail_slug(p):
    rail_dart(p)


def art_flux_rail_slug(p):
    rail_dart(p, core=True)


# ================================================================ fluids
def art_ferrofluid(p):
    spikes = [(15.5, 23, 5.5), (23.5, 13, 6), (32, 6, 6.5), (40.5, 12, 6), (48.5, 22, 5.5)]
    with p.obj():
        parts = [p.mell((5, 27, 59, 60))]
        for x, ytop, w in spikes:
            parts.append(p.mpoly([(x - w, 38), (x - 0.9, ytop + 1.2), (x, ytop), (x + 0.9, ytop + 1.2), (x + w, 38)]))
        m = U(*parts)
        p.fill(m, '#2A2140', 'diag', 0.0, 1.0, c1=C['ff'], edge=0)
        # violet sheen: rim light on the upper-left edges and streaks on the spikes
        rim = inter(minus(m, erode_units(p, m, 1.6)), p.mpoly([(-5, -5), (60, -5), (-5, 60)]))
        p.fill(rim, C['ff_sheen'], 'flat', edge=0, a=0.85)
        for x, ytop, w in spikes:
            s = p.mpoly([(x - w * 0.55, 36), (x - 0.5, ytop + 3), (x - w * 0.15, 36)])
            p.fill(s, C['ff_sheen'], 'v', 0.35, -0.2, edge=0, a=0.8)
        p.fill(p.mell((12, 40, 26, 47)), C['ff_sheen'], 'diag', 0.4, -0.2, edge=0, a=0.55)
        p.fill(p.mell((14.5, 41.5, 19.5, 44.5)), '#E8DDFF', 'flat', edge=0, a=0.9)


def erode_units(p, m, w):
    from iconkit import erode
    return erode(m, w * p.unit * p.tf[0])


def ln2_drop(p, cx, cy, R, k=2.05):
    with p.obj():
        m = p.mpoly(drop_pts(cx, cy, R, k))
        p.fill(m, C['ln2'], 'rad', 0.45, -0.3)
        p.fill(p.mell((cx - R * 0.62, cy - R * 0.55, cx - R * 0.1, cy + R * 0.05)), C['ln2_mist'], 'diag', 0.4, -0.1, edge=0, a=0.9)
        p.fill(p.mell((cx + R * 0.25, cy + R * 0.35, cx + R * 0.6, cy + R * 0.62)), '#FFFFFF', 'flat', edge=0, a=0.55)
    return m


def art_liquid_nitrogen(p):
    ln2_drop(p, 30, 38, 18)
    for pts, w in ((arc_pts((38, 44, 60, 60), 200, 340) , 2.0), (arc_pts((2, 46, 22, 60), 190, 330), 1.8),
                   (arc_pts((44, 6, 62, 22), 150, 290), 1.6)):
        field_arc_fx(p, pts, w, C['ln2_mist'], glow=C['frost'], a=0.85)
    sparkle(p, 54, 30, 4.2, col='#FFFFFF', glow=C['ln2'])
    sparkle(p, 9, 22, 3.4, col='#FFFFFF', glow=C['ln2'])


# ================================================================ recipes with their own icon
def art_recipe_liquid_nitrogen(p):
    def wind(y, x1, r, flip=False):
        pts = [(3, y), (x1, y)] + arc_pts((x1 - r, y - 2 * r, x1 + r, y), 90, -180, 30)
        return pts
    with p.obj():
        for y, x1, r in ((17, 36, 5.5), (30, 46, 5), (44, 30, 4.5)):
            p.fill(p.mline(wind(y, x1, r), 3.2), '#FFFFFF', 'h', 0.0, -0.18, edge=0.4, ek=-0.25)
    ln2_drop(p, 43, 41, 14.5)
    sparkle(p, 58, 12, 3.6, col='#FFFFFF', glow=C['ln2'])


def art_recipe_flux_crystal_growth(p):
    with p.obj():
        p.fill(p.mell((5, 46, 59, 62)), shade(C['sc_deep'], -0.1), 'h', 0.15, -0.3)
        p.fill(p.mell((5, 42, 59, 57)), C['frost'], 'diag', 0.2, -0.25, edge=0.5, ek=-0.3)
        p.fill(minus(p.mell((10, 44, 54, 55)), p.mell((12, 45, 56, 57))), '#FFFFFF', 'flat', edge=0, a=0.8)
    crystal(p, 32, 29, 12.5, 21.5, charged=False)
    for cx, cy, R in ((10.5, 23, 4.2), (53.5, 18, 3.8)):
        with p.obj(ow=1.5):
            p.fill(p.mpoly(drop_pts(cx, cy, R, 2.0)), C['sc'], 'rad', 0.45, -0.3, edge=0.4)


def art_recipe_flux_crystal_charging(p):
    crystal(p, 27, 31, 14, 25, charged=True)
    bolt = [(10, 0), (0, 21), (8.5, 21), (3.5, 38), (21, 13), (12, 13), (18, 0)]
    q = [(x * 0.95 + 40, y * 0.95 + 24) for x, y in bolt]
    m = p.mpoly(q)
    p.glow(m, C['bolt'], 2.5, 1.2)
    with p.obj():
        p.fill(m, C['bolt'], 'diag', 0.4, -0.25, edge=0.5, ek=-0.4)


def art_recipe_stone_separation(p):
    with p.obj():
        for i, (cx, cy, r) in enumerate(((13, 47, 9.5), (27, 50, 8.2), (18, 33, 8.8), (8, 36, 6))):
            m = p.mpoly(rock_pts(cx, cy, r, 40 + i))
            p.fill(m, shade(C['stone'], 0.05 * (i % 2)), 'rad', 0.35, -0.35, edge=0.5, ek=-0.45)
            speckle(p, m, 5, shade(C['stone'], -0.35), 50 + i, r=0.6)
    with p.obj():
        arrow = [(26, 22), (36, 22), (36, 16.5), (46, 26), (36, 35.5), (36, 30), (26, 30)]
        p.fill(p.mpoly([(x, y - 4) for x, y in arrow]), '#F2F2F2', 'diag', 0.1, -0.2, edge=0.4)
    with p.obj():
        m = p.mpoly(rock_pts(51, 13, 8.5, 61, n=7, jit=0.3))
        p.fill(m, C['iron_ore'], 'rad', 0.45, -0.35)
        speckle(p, m, 6, shade(C['iron_ore'], 0.5), 62, r=0.8)
    with p.obj():
        m = p.mpoly(rock_pts(49, 44, 9.5, 71, n=7, jit=0.3))
        p.fill(m, C['copper_ore'], 'rad', 0.4, -0.35)
        speckle(p, m, 6, shade(C['copper_ore'], 0.5), 72, r=0.8)


# ================================================================ ammo categories: item motif on a round dark badge
def badge(p):
    with p.obj():
        m = p.mcirc(32, 32, 29.5)
        p.fill(m, '#2E2F38', 'rad', 0.12, -0.35, edge=0)
        p.fill(minus(m, p.mcirc(32, 32, 26.5)), C['steel_dk'], 'diag', 0.35, -0.3, edge=0)


def art_ammo_slug(p):
    badge(p)
    with p.at(0.74):
        art_ferrite_slug(p)


def art_ammo_gauss(p):
    badge(p)
    with p.at(0.74):
        art_gauss_slug(p)


def art_ammo_rail(p):
    badge(p)
    with p.at(0.78):
        art_rail_slug(p)


# ================================================================ buildings (§10.2): vanilla silhouette in the tint colour + glyph
def bricks(p, face, y_rows, x_step, col, off=0.0, w=0.8, a=0.7, y0=None):
    """mortar lines on a face mask"""
    lines = np.zeros_like(face)
    ys = list(y_rows)
    for y in ys:
        lines = np.maximum(lines, p.mline([(0, y), (64, y)], w, round_caps=False))
    prev = y0 if y0 is not None else ys[0] - (ys[1] - ys[0] if len(ys) > 1 else 8)
    for i, y in enumerate(ys + [ys[-1] + (ys[-1] - prev if len(ys) == 1 else ys[1] - ys[0])]):
        start = (off + (x_step / 2 if i % 2 else 0)) % x_step
        x = start
        while x < 64:
            lines = np.maximum(lines, p.mline([(x, prev), (x, y)], w, round_caps=False))
            x += x_step
        prev = y
    p.fill(inter(lines, face), col, 'flat', edge=0, a=a)


def art_sintering_kiln(p, g=True):
    col = TINT['magnetics-sintering-kiln']
    with p.obj():
        front = p.mrrect((5, 18, 59, 58), 8)
        p.fill(front, shade(col, -0.2), 'h', 0.12, -0.3)
        bricks(p, minus(front, p.mrect((0, 0, 64, 33))), (41, 49.5), 13, shade(col, -0.5), w=0.9, a=0.6, y0=33)
        top = p.mrrect((8, 8, 56, 34), 9)
        p.fill(top, shade(col, 0.1), 'diag', 0.22, -0.12)
        speckle(p, top, 14, shade(col, -0.35), 101, r=0.7, a=0.7)
        hole = p.mrrect((20, 13, 44, 27), 5)
        p.fill(hole, '#2B1D20', 'v', 0.0, 1.0, c1='#7A2E14', edge=0.5, ek=-0.2)
        mouth = U(p.mrrect((21, 36, 43, 58), 3), p.mell((21, 30, 43, 46)))
        p.fill(mouth, '#24181B', 'v', 0.0, 1.0, c1='#3A2020', edge=0.6, ek=0.15)
        fire = inter(U(p.mell((23, 44, 41, 62)), p.mpoly([(25, 50), (28, 40), (31, 46), (34, 37), (37, 46), (40, 41), (41, 52)])), mouth)
        p.fill(fire, C['fire'], 'v', 0.0, 1.0, c1='#FFD27A', edge=0)
    fm = inter(p.mell((22, 38, 42, 60)), p.mrect((0, 0, 64, 58)))
    p.glow(fm, C['fire'], 3.0, 0.5)
    p.glow(p.mrrect((22, 15, 42, 25), 4), C['fire'], 2.0, 0.35)
    if g:
        glyph(p)


def art_induction_furnace(p, g=True):
    col = TINT['magnetics-induction-furnace']
    with p.obj():
        top, front = box(p, 4, 26, 60, 58, 10, col)
        for x in (10, 16, 46, 52):
            p.fill(p.mrrect((x - 1.3, 50.5, x + 1.3, 56), 1), shade(col, -0.6), 'flat', edge=0)
        cyl_v(p, 18, 46, 12, 42, 5.5, shade(col, -0.05))
        for y in (16.5, 24.5, 32.5):
            band_v(p, 16, 48, y, 4.6, 5.8, C['copper'], 0.35, -0.4)
        rim = p.mell((18, 6.5, 46, 17.5))
        p.fill(rim, shade(col, 0.25), 'diag', 0.2, -0.3)
        melt = p.mell((21.5, 8.5, 42.5, 15.5))
        p.fill(melt, '#FFE08A', 'rad', 0.3, -0.1, c1=C['fire'], edge=0.4, ek=-0.3)
    p.glow(p.mell((22, 8, 42, 16)), C['fire'], 2.5, 0.8)
    if g:
        glyph(p)


def art_coil_winder(p, g=True):
    col = TINT['magnetics-coil-winder']
    with p.obj():
        top, front = box(p, 4, 10, 60, 58, 9, col)
        for (x0, y0) in ((6, 12), (49, 12), (6, 38), (49, 38)):
            p.fill(p.mrrect((x0, y0, x0 + 9, y0 + 9), 2), shade(col, -0.25), 'diag', 0.1, -0.2, edge=0.5)
        p.fill(p.mrrect((15, 17, 49, 45), 4), shade(col, -0.45), 'v', 0.0, 1.0, c1=shade(col, -0.6), edge=0.5)
    with p.obj():
        p.fill(p.mell((12, 15, 22, 45)), shade(C['steel'], -0.15), 'diag', 0.2, -0.3)
        body = p.mrect((17, 19, 47, 41))
        p.fill(body, C['copper'], 'cylh', 0.4, -0.45)
        for x in np.arange(19.5, 47, 2.6):
            p.fill(inter(p.mline([(x, 19), (x, 41)], 0.6, round_caps=False), body), C['copper_dk'], 'flat', edge=0, a=0.7)
        p.fill(p.mell((42, 15, 52, 45)), C['steel'], 'diag', 0.35, -0.3)
        p.fill(p.mell((44.5, 26, 49.5, 34)), C['steel_dk'], 'flat', edge=0.3)
    if g:
        glyph(p)


def tank(p, x0, x1, yt, yb, col, dome=8.0):
    ry = 4.5
    body = U(p.mrect((x0, yt, x1, yb)), p.mell((x0, yb - ry, x1, yb + ry)),
             inter(p.mell((x0, yt - dome, x1, yt + dome)), p.mrect((x0, yt - dome, x1, yt + 1))))
    p.fill(body, col, 'cyl', 0.35, -0.38)
    d = inter(p.mell((x0, yt - dome, x1, yt + dome)), p.mrect((x0, yt - dome, x1, yt + 0.5)))
    p.fill(d, shade(col, 0.12), 'rad', 0.4, -0.2, edge=0)
    return body


def art_cryo_chamber(p, g=True):
    col = TINT['magnetics-cryo-chamber']
    with p.obj():
        box(p, 4, 28, 60, 58, 9, shade(col, -0.22))
        p.fill(p.mrect((28, 35, 36, 40)), C['steel'], 'cylh', 0.3, -0.35, edge=0.4)
        for x0, x1 in ((8, 29), (35, 56)):
            tank(p, x0, x1, 18, 46, col)
            band_v(p, x0 - 0.8, x1 + 0.8, 30, 3.5, 4.6, shade(col, -0.35), 0.2, -0.35)
            # snow cap on the dome
            cx = (x0 + x1) / 2
            snow = p.mpoly([(x0 + 2.5, 15), (x0 + 5, 11.5), (cx - 2, 10.3), (cx + 3, 10.6), (x1 - 4, 12), (x1 - 2, 15),
                            (x1 - 5, 16.5), (cx + 1, 15.2), (cx - 4, 16.8)])
            p.fill(snow, '#FFFFFF', 'diag', 0.0, -0.12, edge=0)
            for k, xx in enumerate(np.linspace(x0 + 3, x1 - 3, 4)):
                L = 4.5 if k % 2 == 0 else 3
                p.fill(p.mpoly([(xx - 1.3, 33.6), (xx + 1.3, 33.6), (xx, 33.6 + L)]), C['frost'], 'v', 0.1, -0.25, edge=0)
    sparkle(p, 57, 10, 3.6)
    sparkle(p, 6.5, 22, 3.0)
    if g:
        glyph(p)


def art_flux_resonator(p, g=True):
    col = TINT['magnetics-flux-resonator']
    with p.obj():
        box(p, 6, 40, 58, 58, 7, shade(col, -0.3))
        cyl_v(p, 15, 49, 26, 50, 6.5, col)
        for y in (32, 41):
            band_v(p, 14.2, 49.8, y, 3.6, 6.7, shade(col, -0.38), 0.2, -0.35)
        p.fill(p.mell((25, 23, 39, 29)), shade(col, -0.35), 'v', -0.1, 0.1, edge=0.4)
    p.glow(p.mell((24, 22, 40, 30)), C['flux'], 2.5, 0.9)
    crystal(p, 32, 13.5, 7.2, 11, charged=True, arcs=False)
    for a0, a1 in ((120, 240), (-60, 60)):
        field_arc_fx(p, arc_pts((19, 3.5, 45, 24.5), a0, a1, 24), 1.3, C['flux_glow'], glow=C['flux'])
    if g:
        glyph(p)


def art_magnetic_separator(p, g=True):
    col = TINT['magnetics-magnetic-separator']
    with p.obj():
        box(p, 4, 8, 60, 58, 9, col)
        for (x0, y0) in ((6, 10), (49, 10), (6, 38), (49, 38)):
            p.fill(p.mrrect((x0, y0, x0 + 9, y0 + 9), 2), shade(col, -0.25), 'diag', 0.1, -0.2, edge=0.5)
        rim = p.mrrect((13, 14, 51, 45), 6)
        p.fill(rim, C['steel'], 'diag', 0.25, -0.35)
        bath = p.mrrect((16, 17, 48, 42), 4.5)
        p.fill(bath, '#2A2140', 'diag', 0.0, 1.0, c1=C['ff'], edge=0.6, ek=-0.5)
        for x, yt, w in ((26, 23, 4), (32, 19.5, 4.5), (38, 23.5, 4)):
            m = p.mpoly([(x - w, 35), (x, yt), (x + w, 35)])
            p.fill(m, C['ff'], 'flat', edge=0)
            p.fill(p.mpoly([(x - w * 0.6, 34), (x - 0.4, yt + 2.5), (x - w * 0.1, 34)]), C['ff_sheen'], 'v', 0.3, -0.2, edge=0, a=0.9)
        p.fill(p.mell((22, 33, 42, 38)), C['ff'], 'flat', edge=0)
        p.fill(minus(p.mrrect((17, 18, 47, 41), 4), p.mrrect((18.5, 19.5, 47, 41), 4)), C['ff_sheen'], 'flat', edge=0, a=0.7)
    with p.obj():
        for i, (cx, cy, r, c) in enumerate(((12.5, 12, 5, C['iron_ore']), (51.5, 12, 5, C['copper_ore']), (10.5, 45, 4.4, C['copper_ore']))):
            m = p.mpoly(rock_pts(cx, cy, r, 200 + i, n=7, jit=0.25))
            p.fill(m, c, 'rad', 0.4, -0.35, edge=0.4)
    if g:
        glyph(p)


def art_magnetic_drill(p, g=True):
    col = TINT['magnetics-magnetic-drill']
    with p.obj():
        box(p, 4, 24, 60, 58, 10, col)
        for x0 in (8, 46):
            p.fill(p.mrrect((x0, 28, x0 + 10, 44), 2), shade(col, -0.3), 'diag', 0.1, -0.2, edge=0.5)
            for y in (31, 35, 39):
                p.fill(p.mrect((x0 + 2, y, x0 + 8, y + 1.2)), shade(col, -0.6), 'flat', edge=0)
        bit = p.mpoly([(26, 47), (38, 47), (32, 61)])
        p.fill(bit, C['steel'], 'h', 0.4, -0.4)
        for y in (51, 55):
            p.fill(inter(p.mline([(24, y - 2), (40, y + 2)], 0.8), bit), C['steel_dk'], 'flat', edge=0)
        cyl_v(p, 21, 43, 18, 45, 5, shade(col, -0.08))
    with p.obj():
        horseshoe(p, 32, 17, 12.5, 6.2, 9, ang=180)
    if g:
        glyph(p)


def belt_strip(p, p0, p1, half, col, chev=True, start=0.0):
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    rail = C['steel_dk']
    whole = p.mpoly(along(p0, p1, [(0, -half), (L, -half), (L, half), (0, half)]))
    p.fill(whole, rail, 'diag', 0.25, -0.2)
    surf = p.mpoly(along(p0, p1, [(0.8, -half + 3.2), (L - 0.8, -half + 3.2), (L - 0.8, half - 3.2), (0.8, half - 3.2)]))
    p.fill(surf, col, 'diag', 0.2, -0.3, edge=0.4, ek=-0.4)
    if chev:
        w = half - 4.2
        u = start + 3
        while u < L - 3:
            q = along(p0, p1, [(u, -w), (u + 4.5, 0), (u, w), (u - 3, w), (u + 1.5, 0), (u - 3, -w)])
            p.fill(inter(p.mpoly(q), surf), shade(col, -0.35), 'flat', edge=0)
            u += 10.5
    return whole


def maglev_lines(p, p0, p1, half, a=1.0):
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    for v in (-half + 1.7, half - 1.7):
        pts = along(p0, p1, [(1.2, v), (L - 1.2, v)])
        field_arc_fx(p, pts, 1.35, '#F4FDFF', glow=C['sc'], glow_r=1.9, a=a)


def art_maglev_transport_belt(p, g=True):
    col = TINT['magnetics-maglev-transport-belt']
    p0, p1 = (10, 49), (55, 16)
    with p.obj():
        belt_strip(p, p0, p1, 12.5, col)
    maglev_lines(p, p0, p1, 12.5)
    if g:
        glyph(p)


def art_maglev_underground_belt(p, g=True):
    col = TINT['magnetics-maglev-underground-belt']
    with p.obj():
        top, front = box(p, 8, 5, 56, 44, 16, col)
        p.fill(p.mrect((10, 9, 54, 12)), shade(col, -0.25), 'flat', edge=0, a=0.8)
        p.fill(p.mrect((10, 17, 54, 20)), shade(col, -0.25), 'flat', edge=0, a=0.8)
        mouth = U(p.mrect((17, 34, 47, 44)), p.mell((17, 28, 47, 42)))
        p.fill(mouth, '#1E1A26', 'v', 0.0, 1.0, c1='#3A2F4A', edge=0)
        belt_strip(p, (32, 61), (32, 37), 12.5, col, start=1.5)
        p.fill(p.mrect((19, 36, 45, 42)), '#000000', 'v', 0.0, 1.0, c1='#000000', edge=0, a=0.45)
    maglev_lines(p, (32, 61), (32, 40), 12.5)
    if g:
        glyph(p)


def art_maglev_splitter(p, g=True):
    col = TINT['magnetics-maglev-splitter']
    with p.obj():
        for x in (17, 47):
            belt_strip(p, (x, 61), (x, 3), 11.5, col, start=2)
    for x in (17, 47):
        maglev_lines(p, (x, 61), (x, 3), 11.5)
    with p.obj():
        top, front = box(p, 2, 21, 62, 45, 8, col)
        for x in (17, 47):
            p.fill(p.mrrect((x - 7, 25, x + 7, 33), 2), shade(col, -0.35), 'diag', -0.1, 0.1, edge=0.4)
            q = [(x - 3.5, 31), (x, 26.5), (x + 3.5, 31)]
            p.fill(p.mline(q, 1.4), '#FFFFFF', 'flat', edge=0, a=0.9)
        p.fill(p.mrect((31, 23, 33, 36)), shade(col, -0.45), 'flat', edge=0)
    if g:
        glyph(p)


def art_coil_capacitor(p, g=True):
    col = TINT['magnetics-coil-capacitor']
    with p.obj():
        for x, cap in ((24, C['N']), (40, C['steel_dk'])):
            cyl_v(p, x - 3, x + 3, 9, 18, 1.6, C['steel'])
            p.fill(p.mell((x - 3, 7.4, x + 3, 10.6)), cap, 'diag', 0.3, -0.2, edge=0.3)
        cyl_v(p, 14, 50, 18, 51, 6.5, col)
        band = band_v(p, 13.4, 50.6, 27, 13, 6.6, C['copper'], 0.4, -0.45)
        for y in np.arange(28.8, 40.5, 2.2):
            q = arc_pts((13.4, y - 6.6, 50.6, y + 6.6), 180, 0, 30)
            p.fill(inter(p.mline(q, 0.55), band), C['copper_dk'], 'flat', edge=0, a=0.7)
    if g:
        glyph(p)


def art_superconducting_accumulator(p, g=True):
    col = TINT['magnetics-superconducting-accumulator']
    with p.obj():
        box(p, 4, 42, 60, 59, 6, shade(col, -0.35))
        for x0, x1 in ((8, 30), (34, 56)):
            cyl_v(p, x0, x1, 12, 50, 4.8, col, top=shade(col, -0.3))
            band_v(p, x0 - 0.7, x1 + 0.7, 27, 7, 5, C['frost'], 0.2, -0.3)
            cx = (x0 + x1) / 2
            p.fill(p.mell((cx - 5, 9.8, cx + 5, 14.2)), '#1D3440', 'flat', edge=0.3)
    for x0, x1 in ((8, 30), (34, 56)):
        cx = (x0 + x1) / 2
        m = p.mell((cx - 4, 10.2, cx + 4, 13.8))
        p.glow(m, C['sc'], 2.0, 1.4)
        p.fx(m, C['sc'])
    if g:
        glyph(p)


def art_superconducting_pylon(p, g=True):
    col = TINT['magnetics-superconducting-pylon']
    with p.obj():
        w = 3.0
        legs = [((13, 61), (27, 15)), ((51, 61), (37, 15))]
        parts = [p.mline(l, w) for l in legs]
        def xat(leg, y):
            (x0, y0), (x1, y1) = leg
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
        ys = (60, 45, 32, 21)
        for i in range(len(ys) - 1):
            ya, yb = ys[i], ys[i + 1]
            parts.append(p.mline([(xat(legs[0], ya), ya), (xat(legs[1], yb), yb)], 1.9))
            parts.append(p.mline([(xat(legs[1], ya), ya), (xat(legs[0], yb), yb)], 1.9))
            parts.append(p.mline([(xat(legs[0], yb), yb), (xat(legs[1], yb), yb)], 1.9))
        lattice = U(*parts)
        p.fill(lattice, col, 'diag', 0.3, -0.35, edge=0.3)
        arm = p.mrrect((4, 12.5, 60, 18.5), 1.5)
        p.fill(arm, col, 'v', 0.3, -0.35)
        p.fill(p.mpoly([(26, 13), (38, 13), (32, 4)]), shade(col, -0.1), 'diag', 0.3, -0.3)
        for x in (8.5, 20, 44, 55.5):
            p.fill(p.mrrect((x - 2, 18, x + 2, 25), 1), shade(C['sc_deep'], 0.1), 'cyl', 0.4, -0.3, edge=0.3)
    for x in (8.5, 20, 44, 55.5):
        m = p.mrrect((x - 1.3, 18.8, x + 1.3, 24.2), 1)
        p.glow(m, C['sc'], 2.2, 1.6)
        p.fx(m, '#E8FBFF', 0.9)
    if g:
        glyph(p)


def engine(p, col, window=None, stripe=None):
    """steam-engine silhouette: frame, horizontal cylinder, flywheel on the left"""
    with p.obj():
        box(p, 3, 38, 61, 59, 7, shade(col, -0.35))
        body, cap = cyl_h(p, 16, 52, 16, 44, 4.5, col)
        for x in (26, 40):
            m = inter(p.mrect((x, 16, x + 2.2, 44)), body)
            p.fill(m, shade(col, -0.35), 'cylh', 0.1, -0.3, edge=0)
        wheel = p.mell((4, 10, 20, 54))
        p.fill(wheel, shade(C['steel'], -0.05), 'diag', 0.3, -0.35)
        p.fill(p.mell((6.5, 14, 17.5, 50)), shade(C['steel_dk'], 0.1), 'diag', -0.1, 0.2, edge=0)
        for a in range(0, 180, 45):
            q = arc_pts((6.5, 14, 17.5, 50), a, a + 180, 2)
            p.fill(inter(p.mline([q[0], q[-1]], 1.4), p.mell((6.5, 14, 17.5, 50))), C['steel'], 'flat', edge=0)
        p.fill(p.mell((9.5, 27, 14.5, 37)), C['steel'], 'rad', 0.3, -0.3, edge=0.3)
        if stripe:
            p.fill(p.mrrect((20, 24.5, 55, 30.5), 3), '#16222E', 'flat', edge=0.3)
            p.fill(p.mrrect((21, 25.8, 54, 29.2), 2), stripe, 'h', 0.4, 0.0, edge=0)
        if window:
            p.fill(p.mcirc(34, 30, 8.8), C['steel'], 'diag', 0.35, -0.35)
            p.fill(p.mcirc(34, 30, 6.4), '#1B1426', 'rad', 0.2, -0.2, edge=0.4)
    if stripe:
        m = p.mrrect((21, 25.8, 54, 29.2), 2)
        p.glow(m, stripe, 2.5, 1.3)
        p.fx(p.mrrect((22, 26.8, 53, 28.2), 1), '#E8FBFF', 0.9)
    if window:
        crystal(p, 34, 30, 3.8, 5.6, charged=True, arcs=False)


def art_mhd_generator(p, g=True):
    engine(p, TINT['magnetics-mhd-generator'], stripe=C['plasma'])
    if g:
        glyph(p)


def art_flux_dynamo(p, g=True):
    engine(p, TINT['magnetics-flux-dynamo'], window=True)
    if g:
        glyph(p)


def art_geomagnetic_coil(p, g=True):
    col = TINT['magnetics-geomagnetic-coil']
    with p.obj():
        p.fill(p.mpoly([(4, 50), (60, 50), (58, 57), (6, 57)]), shade(col, -0.45), 'h', 0.1, -0.2)
        face = p.mpoly([(8, 7), (56, 7), (60, 51), (4, 51)])
        p.fill(face, shade(col, -0.05), 'diag', 0.2, -0.2)
        cells = np.zeros_like(face)
        for i in range(3):
            for j in range(3):
                def P(u, v):
                    y = 7 + 44 * v
                    xl = 8 + (4 - 8) * v
                    xr = 56 + (60 - 56) * v
                    return (xl + (xr - xl) * u, y)
                u0, u1 = 0.04 + i * 0.32, 0.04 + i * 0.32 + 0.28
                v0, v1 = 0.05 + j * 0.31, 0.05 + j * 0.31 + 0.27
                cells = np.maximum(cells, p.mpoly([P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1)]))
        p.fill(cells, shade(col, -0.42), 'diag', 0.1, -0.15, edge=0.3, ek=0.3)
    for L in (11, 17.5, 24):
        for side in (1, -1):
            pts = dipole_pts(L, side, 32, 29, th0=14, th1=166)
            field_arc_fx(p, pts, 1.6, shade(C['alloy'], -0.2), glow=C['alloy'], glow_r=0.9)
    with p.obj(ow=1.3):
        p.fill(p.mcirc(32, 29, 4.6), C['alloy'], 'rad', 0.5, -0.3, edge=0.3)
    if g:
        glyph(p)


def wall_block(p, col):
    with p.obj():
        top, front = box(p, 6, 7, 58, 58, 22, col, r=2.5, topk=0.15, frontk=-0.22)
        f = minus(front, top)
        bricks(p, f, (43, 50.5), 17, shade(col, -0.55), w=0.9, a=0.55, y0=36)
        bricks(p, top, (16, 25), 17, shade(col, -0.35), off=6, w=0.8, a=0.4, y0=8)
    return top, f


def art_ferrite_wall(p, g=True):
    col = TINT['magnetics-ferrite-wall']
    with p.obj():
        top, front = box(p, 6, 7, 58, 58, 22, col, r=2.5, topk=0.15, frontk=-0.22)
        f = minus(front, top)
        bricks(p, f, (43, 50.5), 17, shade(col, -0.55), w=0.9, a=0.55, y0=36)
        bricks(p, top, (16, 25), 17, shade(col, -0.35), off=6, w=0.8, a=0.4, y0=8)
        speckle(p, top, 22, C['ferrite_sp'], 301, r=0.7)
        speckle(p, f, 16, shade(col, 0.35), 302, r=0.6)
        speckle(p, U(top, f), 14, shade(col, -0.5), 303, r=0.6)
    if g:
        glyph(p)


def art_magnet_wall(p, g=True):
    col = TINT['magnetics-magnet-wall']
    wall_block(p, col)
    for r in (7, 12):
        pts = arc_pts((32 - r * 1.25, 30 - r, 32 + r * 1.25, 30 + r), 200, 340, 30)
        field_arc_fx(p, pts, 2.0, '#F6F9FF', glow=C['alloy'], glow_r=1.8)
    if g:
        glyph(p)


def art_superconducting_wall(p, g=True):
    col = TINT['magnetics-superconducting-wall']
    top, f = wall_block(p, col)
    with p.obj(outline=False, shadow=False, highlight=0):
        rim = minus(top, erode_units(p, top, 1.6))
        p.fill(rim, '#FFFFFF', 'flat', edge=0, a=0.9)
        for k, x in enumerate(np.arange(9, 57, 5.2)):
            L = (5.5, 3.2, 4.4, 2.6)[k % 4]
            p.fill(p.mpoly([(x - 1.5, 35), (x + 1.5, 35), (x, 35 + L)]), '#FFFFFF', 'v', 0.0, -0.2, edge=0, a=0.95)
    sparkle(p, 50, 14, 3.6)
    sparkle(p, 15, 46, 2.8)
    if g:
        glyph(p)


def gate(p, col, sc=False):
    with p.obj():
        p.fill(p.mrect((16, 16, 48, 21)), shade(C['steel'], -0.1), 'v', 0.3, -0.3)
        panel = p.mrect((17, 20, 47, 56))
        p.fill(panel, shade(col, -0.3), 'h', 0.15, -0.25)
        for x in (22.5, 28.5, 34.5, 40.5):
            p.fill(p.mrect((x - 1.2, 20, x + 1.2, 56)), shade(col, 0.15), 'cyl', 0.35, -0.3, edge=0.3)
        stripe = p.mrect((17, 32, 47, 38.5))
        p.fill(stripe, '#F0C419', 'flat', edge=0)
        for x in range(10, 56, 6):
            p.fill(inter(p.mpoly([(x, 38.5), (x + 3, 38.5), (x + 9.5, 32), (x + 6.5, 32)]), stripe), '#26262B', 'flat', edge=0)
        for x0 in (4, 45):
            box(p, x0, 9, x0 + 15, 59, 10, col, r=2)
            speckle(p, p.mrect((x0 + 1, 10, x0 + 14, 48)), 5, shade(col, -0.4), 400 + x0, r=0.6, a=0.6)
    if sc:
        with p.obj(outline=False, shadow=False, highlight=0):
            for x0 in (4, 45):
                t = p.mrrect((x0, 9, x0 + 15, 49), 2)
                p.fill(minus(t, erode_units(p, t, 1.4)), '#FFFFFF', 'flat', edge=0, a=0.9)
                for k, x in enumerate((x0 + 3, x0 + 7.5, x0 + 12)):
                    L = (4.5, 2.8, 3.8)[k]
                    p.fill(p.mpoly([(x - 1.3, 49), (x + 1.3, 49), (x, 49 + L)]), '#FFFFFF', 'flat', edge=0, a=0.95)
        sparkle(p, 32, 11, 3.2)
    else:
        for x0 in (4, 45):
            pts = arc_pts((x0 + 2.5, 22, x0 + 12.5, 34), 200, 340, 16)
            field_arc_fx(p, pts, 1.2, '#F2F6FF', glow=C['alloy'])


def art_magnet_gate(p, g=True):
    gate(p, TINT['magnetics-magnet-gate'])
    if g:
        glyph(p)


def art_superconducting_gate(p, g=True):
    gate(p, TINT['magnetics-superconducting-gate'], sc=True)
    if g:
        glyph(p)


def art_mend_coil(p, g=True):
    col = TINT['magnetics-mend-coil']
    for r in (9, 14, 19):
        pts = arc_pts((32 - r * 1.35, 22 - r, 32 + r * 1.35, 22 + r), 215, 325, 24)
        field_arc_fx(p, pts, 1.9, C['heal'], glow=C['heal'], glow_r=1.8)
    with p.obj():
        box(p, 6, 42, 58, 59, 6, shade(col, -0.45))
        cyl_v(p, 11, 53, 24, 50, 7.5, col, top=shade(col, 0.1))
        band_v(p, 10.4, 53.6, 27, 3, 7.6, shade(col, -0.45), 0.2, -0.3)
        cross = U(p.mrect((27.5, 32.5, 36.5, 52.5)), p.mrect((22, 38, 42, 47)))
        p.fill(cross, '#FFFFFF', 'diag', 0.0, -0.18, edge=0.5, ek=-0.35)
        p.fill(p.mell((25, 20, 39, 26)), shade(col, -0.5), 'flat', edge=0.3)
    m = p.mell((27, 21, 37, 25))
    p.glow(m, C['heal'], 2.0, 1.4)
    p.fx(m, C['heal'])
    if g:
        glyph(p)


def turret_base(p, col):
    cx, cy, rx, ry = 30, 45, 26, 13.5
    V = [(cx + rx * math.cos(math.radians(a + 22.5)), cy + ry * math.sin(math.radians(a + 22.5))) for a in range(0, 360, 45)]
    side = [(x, y + 5) for x, y in V]
    p.fill(U(p.mpoly(side), p.mpoly(V)), shade(col, -0.45), 'h', 0.15, -0.25)
    top = p.mpoly(V)
    p.fill(top, shade(col, -0.15), 'diag', 0.2, -0.2)
    for a in (22.5, 157.5, 202.5, 337.5):
        x, y = cx + rx * 0.78 * math.cos(math.radians(a)), cy + ry * 0.72 * math.sin(math.radians(a))
        p.fill(p.mcirc(x, y, 1.4), shade(col, -0.55), 'flat', edge=0)


def barrel(p, p0, p1, w, col):
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    m = p.mpoly(along(p0, p1, [(0, -w / 2), (L, -w / 2), (L, w / 2), (0, w / 2)]))
    p.fill(m, col, 'diag', 0.35, -0.4)
    return L


def rings(p, p0, p1, us, w, width, col):
    for u in us:
        q = along(p0, p1, [(u, -w / 2), (u + width, -w / 2), (u + width, w / 2), (u, w / 2)])
        p.fill(p.mpoly(q), col, 'diag', 0.4, -0.4, edge=0.4, ek=-0.5)


def art_coilgun_turret(p, g=True):
    col = TINT['magnetics-coilgun-turret']
    p0, p1 = (30, 36), (57, 9)
    with p.obj():
        turret_base(p, col)
        barrel(p, p0, p1, 7, C['steel'])
        rings(p, p0, p1, (15, 20.5, 26), 10.5, 3.6, C['copper'])
        q = along(p0, p1, [(34, -4.5), (38.5, -4.5), (38.5, 4.5), (34, 4.5)])
        p.fill(p.mpoly(q), C['steel_dk'], 'diag', 0.3, -0.3, edge=0.3)
        head = p.mrrect((15, 26, 43, 50), 9)
        p.fill(head, col, 'rad', 0.35, -0.35)
        p.fill(p.mrrect((19, 30, 30, 36), 2), shade(col, -0.35), 'flat', edge=0.3)
    if g:
        glyph(p)


def art_gauss_turret(p, g=True):
    col = TINT['magnetics-gauss-turret']
    p0, p1 = (30, 36), (58.5, 7.5)
    with p.obj():
        turret_base(p, col)
        barrel(p, p0, p1, 8.5, C['steel'])
        rings(p, p0, p1, (13, 18.5, 24, 29.5, 35), 12, 3.3, C['alloy'])
        head = p.mell((12, 23, 46, 53))
        p.fill(head, col, 'rad', 0.35, -0.38)
        p.fill(p.mell((20, 30, 36, 42)), shade(col, -0.3), 'diag', -0.1, 0.15, edge=0.3)
    if g:
        glyph(p)


def art_arc_emitter(p, g=True):
    col = TINT['magnetics-arc-emitter']
    p0, p1 = (30, 37), (48, 19)
    with p.obj():
        turret_base(p, col)
        barrel(p, p0, p1, 6.5, shade(C['steel'], 0.1))
        rings(p, p0, p1, (12,), 10, 3.2, C['sc_deep'])
        head = p.mell((14, 22, 46, 52))
        p.fill(head, col, 'rad', 0.4, -0.38)
        p.fill(minus(p.mell((14, 22, 46, 52)), p.mell((14, 18, 46, 46))), shade(col, -0.4), 'flat', edge=0, a=0.6)
    tip = (49.5, 17.5)
    tipm = p.mcirc(tip[0], tip[1], 3.4)
    p.glow(tipm, C['arc'], 3.0, 1.6)
    bolt_fx(p, lightning_pts(tip[0], tip[1], 61, 3, 5, 2.6, seed=3), 1.5)
    bolt_fx(p, lightning_pts(tip[0] + 2, tip[1] - 1, 62.5, 21, 4, 2.2, seed=8), 1.2)
    bolt_fx(p, lightning_pts(tip[0] - 1, tip[1] - 2, 43, 2.5, 4, 2.0, seed=5), 1.1)
    p.fx(p.mcirc(tip[0], tip[1], 2.2), '#FFFFFF')
    if g:
        glyph(p)


def art_rail_cannon(p, g=True):
    col = TINT['magnetics-rail-cannon']
    p0, p1 = (30, 36), (58, 8)
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    muzzle = along(p0, p1, [(L - 1, 0)])[0]
    with p.obj():
        turret_base(p, col)
        for v in (-4.2, 4.2):
            m = p.mpoly(along(p0, p1, [(0, v - 1.6), (L, v - 1.6), (L, v + 1.6), (0, v + 1.6)]))
            p.fill(m, shade(col, -0.05), 'diag', 0.35, -0.4, edge=0.4)
        for u in (14, 24, 34):
            q = along(p0, p1, [(u, -6.2), (u + 2.6, -6.2), (u + 2.6, 6.2), (u, 6.2)])
            p.fill(p.mpoly(q), C['steel_dk'], 'diag', 0.3, -0.3, edge=0.3)
        head = p.mrrect((14, 25, 44, 52), 5)
        p.fill(head, col, 'diag', 0.3, -0.35)
        p.fill(p.mrrect((18, 29, 40, 36), 2), shade(col, -0.4), 'flat', edge=0.3)
    inner = p.mpoly(along(p0, p1, [(12, -2.2), (L - 1, -2.2), (L - 1, 2.2), (12, 2.2)]))
    p.fx(inner, C['sc'], 0.55)
    mz = p.mcirc(muzzle[0], muzzle[1], 3.2)
    p.glow(mz, C['sc'], 3.4, 1.8)
    p.fx(p.mcirc(muzzle[0], muzzle[1], 1.8), '#FFFFFF')
    if g:
        glyph(p)


# ================================================================ registry of 64 px icons
def _fn(name):
    return globals()['art_' + name.replace('magnetics-', '').replace('-', '_')]


ICON_ART = {}
for _n, *_ in ITEMS + FLUIDS + [(e[0],) for e in ENTITIES]:
    ICON_ART[_n] = _fn(_n)
ICON_ART.update({
    'recipe-magnetics-liquid-nitrogen': art_recipe_liquid_nitrogen,
    'recipe-magnetics-flux-crystal-growth': art_recipe_flux_crystal_growth,
    'recipe-magnetics-flux-crystal-charging': art_recipe_flux_crystal_charging,
    'recipe-magnetics-stone-separation': art_recipe_stone_separation,
    'ammo-category-magnetics-slug': art_ammo_slug,
    'ammo-category-magnetics-gauss': art_ammo_gauss,
    'ammo-category-magnetics-rail': art_ammo_rail,
})
ENTITY_NAMES = {e[0] for e in ENTITIES}


def draw_subject(p, name):
    fn = ICON_ART[name]
    if name in ENTITY_NAMES:
        fn(p, g=False)
    else:
        fn(p)


ICON_SCALE = 0.95  # a 1.6-unit margin, so outlines and the badge are never cut by the 64 px frame


def icon(name):
    p = Pic(64)
    with p.at(ICON_SCALE):
        ICON_ART[name](p)
    return p.result()


# ================================================================ technologies (256 px, §10.3)
def halo(p, tier):
    col = TIER[tier]
    disk = p.mcirc(32, 32, 29.2)
    yy = (p.Y / p.unit - 32) / 29.2
    xx = (p.X / p.unit - 32) / 29.2
    d = np.clip(np.hypot(xx + 0.15, yy + 0.2), 0, 1)
    c0, c1 = np.array(hexc(shade(col, -0.45)))[:3], np.array(hexc(shade(col, -0.72)))[:3]
    rgb = c0 * (1 - d[..., None]) + c1 * d[..., None]
    p.paint_rgba(rgb.astype(np.float32), disk * 0.92)
    lines = np.zeros_like(disk)
    for L in (11, 19, 28, 40):
        for side in (1, -1):
            lines = np.maximum(lines, p.mline(dipole_pts(L, side, 32, 32, n=90, th0=3, th1=177), 0.75))
    lines = np.maximum(lines, p.mline([(32, 3), (32, 61)], 0.75))
    p.fill(inter(lines, p.mcirc(32, 32, 28)), shade(col, 0.25), 'flat', edge=0, a=0.5)
    ring = minus(p.mcirc(32, 32, 31), p.mcirc(32, 32, 28.4))
    p.glow(ring, col, 1.2, 0.8)
    with p.obj(highlight=0.3, ow=3):
        p.fill(ring, col, 'diag', 0.35, -0.3, edge=0.3)


def composition_power(p):
    with p.at(0.52, 42, 20):
        art_geomagnetic_coil(p, g=False)
    with p.at(0.62, 25, 34):
        art_mhd_generator(p, g=False)
    with p.at(0.46, 46, 45):
        art_coil_capacitor(p, g=False)


def tech_icon(t):
    name, en, ru, tier, packs, subject = t
    p = Pic(256)
    halo(p, tier)
    if subject == 'composition':
        composition_power(p)
    else:
        scale = 0.84 if subject in ENTITY_NAMES else 0.8
        with p.at(scale, 32, 32.5):
            draw_subject(p, subject)
    return p.result()


# ================================================================ rail tracer (512x440, 8 frames of 64x440, §4.7)
def rail_tracer():
    W, H, N = 64, 440, 8
    x = np.arange(W, dtype=np.float32) + 0.5
    d = np.abs(x - W / 2)                                   # distance from the beam axis, px
    core = np.clip(3.5 - d, 0, 1)                           # 6 px white core (soft 1 px rim)
    halo_a = np.exp(-np.clip(d - 3, 0, None) / 7.5) * np.clip((W / 2 - d) / 4, 0, 1)
    t = np.clip((d - 3) / 18, 0, 1)[:, None]
    vio, cya = np.array(hexc(C['flux'])[:3]), np.array(hexc(C['sc'])[:3])
    halo_rgb = vio * (1 - t) + cya * t                      # violet next to the core -> cyan outside
    y = np.arange(H, dtype=np.float32) + 0.5
    ends = np.clip(np.minimum(y, H - y) / 28, 0, 1) ** 1.5  # soft ends along the beam
    sheet = np.zeros((H, W * N, 4), np.float32)
    for i in range(N):
        f = 1.0 - i / (N - 1)                               # alpha 1.0 -> 0 across the frames
        a = np.clip(core + halo_a * (1 - core), 0, 1)
        rgb = (np.ones(3) * core[:, None] + halo_rgb * (halo_a * (1 - core))[:, None]) / np.maximum(a, 1e-6)[:, None]
        fa = (a[None, :] * ends[:, None] * f)
        sheet[:, i * W:(i + 1) * W, :3] = rgb[None, :, :]
        sheet[:, i * W:(i + 1) * W, 3] = fa
    arr = (np.clip(sheet, 0, 1) * 255 + 0.5).astype(np.uint8)
    arr[arr[..., 3] == 0] = 0
    return Image.fromarray(arr, 'RGBA')


# ================================================================ thumbnail (144 px)
def thumbnail():
    p = Pic(144, outline_px=4)
    bg = p.mrrect((1, 1, 63, 63), 9)
    yy = (p.Y / p.unit - 30) / 34
    xx = (p.X / p.unit - 32) / 34
    d = np.clip(np.hypot(xx, yy), 0, 1)
    c0, c1 = np.array(hexc('#3A2C5E'))[:3], np.array(hexc('#15161C'))[:3]
    p.paint_rgba((c0 * (1 - d[..., None]) + c1 * d[..., None]).astype(np.float32), bg)
    lines = np.zeros_like(bg)
    for L in (16, 26, 38, 54):
        for side in (1, -1):
            lines = np.maximum(lines, p.mline(dipole_pts(L, side, 32, 26, n=90, th0=3, th1=177), 0.6))
    p.fill(inter(lines, bg), C['flux'], 'flat', edge=0, a=0.35)
    # field lines between the poles
    for k, r in enumerate((8.5, 13)):
        pts = arc_pts((32 - r - 5, 17 - r, 32 + r + 5, 17 + r + 6), 200, 340, 30)
        field_arc_fx(p, pts, 1.3, C['sc'], glow=C['sc'], glow_r=1.6)
    with p.obj():
        horseshoe(p, 32, 33, 18, 8.8, 15, ang=0)
    crystal(p, 32, 25.5, 6.2, 10.5, charged=True, arcs=False)
    with p.at(0.36, 52.5, 52):
        art_coil(p)
    return p.result()


# ================================================================ sheets
def font(sz, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, sz)


def fit(d, text, f, w):
    if d.textlength(text, font=f) <= w:
        return text
    while text and d.textlength(text + '…', font=f) > w:
        text = text[:-1]
    return text + '…'


SLOT = (49, 48, 49, 255)


def wrap(d, text, f, w, n=2):
    """split text into at most n lines that fit width w (the last one is shortened with … if needed)"""
    words, lines, cur = text.split(' '), [], ''
    for wd in words:
        t = (cur + ' ' + wd).strip()
        if d.textlength(t, font=f) <= w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    if len(lines) > n:
        lines = lines[:n - 1] + [' '.join(lines[n - 1:])]
    return [fit(d, l, f, w) for l in lines]


def showcase(icons, techs, thumb):
    cols, CW, CH = 10, 198, 250
    sections = [
        ('Items (11)', [(n, en, ru, kind, icons[n]) for n, en, ru, kind in ITEMS]),
        ('Fluids (2) · recipes with their own icon (4) · ammo categories (3)',
         [(n, en, ru, kind, icons[n]) for n, en, ru, kind in FLUIDS] +
         [('recipe-' + n, en, ru, 'recipe ' + n.replace('magnetics-', ''), icons['recipe-' + n]) for n, en, ru in RECIPES] +
         [('ammo-category-' + n, en, ru, 'ammo category', icons['ammo-category-' + n]) for n, en, ru in AMMO_CATEGORIES]),
        ('Buildings (26) — entity and placeable item share the icon; vanilla silhouette in the tint colour + magnet badge',
         [(e[0], e[1], e[2], '%s · %s' % (e[5], e[3]), icons[e[0]]) for e in ENTITIES]),
        ('Technologies (14) — ring colour = tier: red, green, blue, military, purple, yellow',
         [(t[0], t[1], t[2], 'T%d · %s' % (i + 1, t[4]), techs[t[0]]) for i, t in enumerate(TECHS)]),
    ]
    n_tiles = sum(len(s[1]) for s in sections)
    rows = sum((len(s[1]) + cols - 1) // cols for s in sections)
    top, sec_h = 176, 40
    Wd, Hd = cols * CW + 20, top + rows * CH + len(sections) * sec_h + 44
    img = Image.new('RGBA', (Wd, Hd), (30, 31, 38, 255))
    d = ImageDraw.Draw(img)
    img.alpha_composite(thumb, (Wd - 144 - 24, 16))
    d.text((20, 18), f'Magnetics for Factorio 2.0 — every icon ({n_tiles})', font=font(32, True), fill=(230, 236, 255))
    d.text((22, 64), 'Магнетика для Factorio 2.0 — все иконки мода', font=font(20, True), fill=(200, 208, 235))
    d.text((22, 98), 'drawn by code: tools/paint.py (PIL) · 64 px icons shown 2× (nearest); small square = the real 32 px size on an inventory slot',
           font=font(15), fill=(140, 150, 180))
    d.text((22, 120), 'technologies: 256 px shown at 128 · names from tools/spec.py = FINAL_SPEC §9 (en / ru) · colours from §10 · mod thumbnail at the right',
           font=font(15), fill=(140, 150, 180))
    fe, fr, fk = font(13, True), font(12), font(11)
    y = top
    for title, cells in sections:
        d.text((22, y + 8), title, font=font(18, True), fill=(250, 214, 120))
        y += sec_h
        for k, (n, en, ru, kind, im) in enumerate(cells):
            x0, y0 = 10 + (k % cols) * CW, y + (k // cols) * CH
            d.rounded_rectangle((x0 + 4, y0 + 4, x0 + CW - 4, y0 + CH - 4), 10, fill=(42, 44, 54))
            big = im.resize((128, 128), Image.NEAREST if im.width == 64 else Image.LANCZOS)
            d.rounded_rectangle((x0 + 12, y0 + 12, x0 + 12 + 136, y0 + 12 + 136), 8, fill=(52, 54, 64))
            img.alpha_composite(big, (x0 + 16, y0 + 16))
            if im.width == 64:
                sx, sy = x0 + 155, y0 + 114
                d.rectangle((sx - 2, sy - 2, sx + 33, sy + 33), fill=SLOT, outline=(18, 18, 20))
                img.alpha_composite(im.resize((32, 32), Image.LANCZOS), (sx, sy))
            w = CW - 22
            ty = y0 + 154
            for line in wrap(d, en, fe, w):
                d.text((x0 + 12, ty), line, font=fe, fill=(235, 240, 255))
                ty += 17
            ty += 2
            for line in wrap(d, ru, fr, w):
                d.text((x0 + 12, ty), line, font=fr, fill=(205, 212, 235))
                ty += 16
            d.text((x0 + 12, y0 + CH - 24), fit(d, kind, fk, w), font=fk, fill=(130, 165, 230))
        y += ((len(cells) + cols - 1) // cols) * CH
    d.text((22, Hd - 34), 'Headless servers have no sprites: world views of the tinted entities come from /magnetics-showroom in the graphical client (PILOT-21).', font=font(13), fill=(120, 128, 150))
    return img.convert('RGB'), n_tiles


def cards(icons):
    cols, CW, CH = 4, 470, 178
    rows = (len(ENTITIES) + cols - 1) // cols
    top = 92
    Wd, Hd = cols * CW + 20, top + rows * CH + 60
    img = Image.new('RGBA', (Wd, Hd), (30, 31, 38, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 16), 'Magnetics — entity cards (26): icon, vanilla base, tint', font=font(28, True), fill=(230, 236, 255))
    d.text((22, 56), 'Every entity is a table.deepcopy of the vanilla base with a multiplicative tint on body layers (FINAL_SPEC §4.1).', font=font(14), fill=(140, 150, 180))
    for k, (n, en, ru, ptype, base, size, tint) in enumerate(ENTITIES):
        x0, y0 = 10 + (k % cols) * CW, top + (k // cols) * CH
        d.rounded_rectangle((x0 + 4, y0 + 4, x0 + CW - 4, y0 + CH - 4), 10, fill=(42, 44, 54))
        d.rounded_rectangle((x0 + 14, y0 + 14, x0 + 150, y0 + 150), 8, fill=(52, 54, 64))
        img.alpha_composite(icons[n].resize((128, 128), Image.NEAREST), (x0 + 18, y0 + 18))
        tx = x0 + 164
        w = CW - 176
        d.text((tx, y0 + 14), fit(d, en, font(16, True), w), font=font(16, True), fill=(235, 240, 255))
        d.text((tx, y0 + 36), fit(d, ru, font(14), w), font=font(14), fill=(205, 212, 235))
        bf = font(13) if d.textlength('vanilla base: ' + base, font=font(13)) <= w else font(11)
        d.text((tx, y0 + 60), fit(d, 'vanilla base: ' + base, bf, w), font=bf, fill=(250, 214, 120))
        d.text((tx, y0 + 80), fit(d, '%s · %s · %s' % (ptype, size, n), font(11), w), font=font(11), fill=(130, 165, 230))
        th = tint_hex(tint)
        d.text((tx, y0 + 104), 'tint (%.2f, %.2f, %.2f)  %s' % (tint + (th,)), font=font(13), fill=(220, 225, 240))
        d.rectangle((tx + w - 34, y0 + 100, tx + w - 4, y0 + 122), fill=to255(th), outline=(15, 15, 18))
        vb = VANILLA_BODY_APPROX.get(base.split(' ')[0])
        if vb:
            vr = to255(vb)
            res = tuple(int(round(vr[i] * tint[i])) for i in range(3)) + (255,)
            yy = y0 + 132
            d.text((tx, yy + 3), 'base ≈', font=font(12), fill=(170, 176, 196))
            d.rectangle((tx + 52, yy, tx + 76, yy + 20), fill=vr, outline=(15, 15, 18))
            d.text((tx + 82, yy + 3), '× tint', font=font(12), fill=(170, 176, 196))
            d.rectangle((tx + 124, yy, tx + 148, yy + 20), fill=to255(th), outline=(15, 15, 18))
            d.text((tx + 154, yy + 3), '=', font=font(12), fill=(170, 176, 196))
            d.rectangle((tx + 168, yy, tx + 208, yy + 20), fill=res, outline=(15, 15, 18))
            d.text((tx + 214, yy + 3), 'world preview', font=font(11), fill=(130, 136, 156))
    d.text((22, Hd - 44), '≈ base colour is an estimate by eye (the headless server ships no PNG); the true world look is judged in the graphical client', font=font(13), fill=(130, 136, 156))
    d.text((22, Hd - 24), 'with /magnetics-showroom (PILOT-21); tints are retuned in one place only.', font=font(13), fill=(130, 136, 156))
    return img.convert('RGB')


# ================================================================ self test
SPEC_10_2_BODY = {  # colours as written in FINAL_SPEC §10.2 (must equal tint x 255 of §4)
    'magnetics-sintering-kiln': '#CC9EA8', 'magnetics-induction-furnace': '#9EB8FF', 'magnetics-coil-winder': '#FFB880',
    'magnetics-cryo-chamber': '#B3F2FF', 'magnetics-flux-resonator': '#D1A3FF', 'magnetics-magnetic-separator': '#ADC7E0',
    'magnetics-magnetic-drill': '#99B8FF', 'magnetics-maglev-transport-belt': '#E69EFF', 'magnetics-maglev-underground-belt': '#E69EFF',
    'magnetics-maglev-splitter': '#E69EFF', 'magnetics-coil-capacitor': '#FFBF8C', 'magnetics-superconducting-accumulator': '#A6F2FF',
    'magnetics-superconducting-pylon': '#A6F2FF', 'magnetics-mhd-generator': '#FF9973', 'magnetics-flux-dynamo': '#CC99FF',
    'magnetics-geomagnetic-coil': '#D1BFFF', 'magnetics-ferrite-wall': '#9E8C99', 'magnetics-magnet-wall': '#99B3FF',
    'magnetics-superconducting-wall': '#B3F2FF', 'magnetics-magnet-gate': '#99B3FF', 'magnetics-superconducting-gate': '#B3F2FF',
    'magnetics-mend-coil': '#99FFB3', 'magnetics-coilgun-turret': '#FFB380', 'magnetics-gauss-turret': '#8CA6FF',
    'magnetics-arc-emitter': '#99F2FF', 'magnetics-rail-cannon': '#C78CFF',
}


def check_against_spec():
    """Every picture the prototypes of tools/spec.py reference has an art function (and nothing extra)."""
    want = set(spec.ITEMS) | set(spec.AMMO) | set(spec.FLUIDS) | set(spec.ENTITIES)
    want |= {'recipe-' + n for n, v in spec.RECIPES.items() if v.get('own_icon')}
    want |= {'ammo-category-' + n for n in spec.AMMO_CATEGORIES}
    have = set(ICON_ART)
    missing, extra = sorted(want - have), sorted(have - want)
    techs_missing = sorted(set(spec.TECHS) - set(TECH_SUBJECT))
    return missing + ['tech ' + t for t in techs_missing], extra


def selftest():
    problems = []
    assert len(ITEMS) == 11 and len(FLUIDS) == 2 and len(ENTITIES) == 26 and len(TECHS) == 14
    for n, want in SPEC_10_2_BODY.items():
        if TINT[n] != want:
            problems.append('%s: tint %s != §10.2 %s' % (n, TINT[n], want))
    missing, extra = check_against_spec()
    problems += ['no picture for ' + m for m in missing] + ['picture not in spec.py: ' + e for e in extra]
    exp = {}
    for n in ICON_ART:
        exp[os.path.join(ICONS, n + '.png')] = (64, 64)
    for t in TECHS:
        exp[os.path.join(TECH, t[0] + '.png')] = (256, 256)
    exp[os.path.join(ENTITY, 'rail-tracer.png')] = (512, 440)
    exp[os.path.join(MOD, 'thumbnail.png')] = (144, 144)
    for f, size in exp.items():
        if not os.path.exists(f):
            problems.append('missing ' + f)
            continue
        im = Image.open(f)
        if im.size != size or im.mode != 'RGBA':
            problems.append('%s: %s %s' % (f, im.size, im.mode))
        a = np.asarray(im)[..., 3]
        if a.max() == 0:
            problems.append('%s: empty' % f)
    return len(exp), problems


# ================================================================ main
def main(argv):
    only = None
    if '--only' in argv:
        only = argv[argv.index('--only') + 1]
    for d in (ICONS, TECH, ENTITY):
        os.makedirs(d, exist_ok=True)
    icons = {}
    for n in ICON_ART:
        if only and only not in n:
            continue
        icons[n] = icon(n)
        icons[n].save(os.path.join(ICONS, n + '.png'), optimize=True)
    techs = {}
    for t in TECHS:
        if only and only not in t[0]:
            continue
        techs[t[0]] = tech_icon(t)
        techs[t[0]].save(os.path.join(TECH, t[0] + '.png'), optimize=True)
    if only:
        print('wrote %d icons, %d techs (--only %s)' % (len(icons), len(techs), only))
        return 0
    rail_tracer().save(os.path.join(ENTITY, 'rail-tracer.png'), optimize=True)
    thumb = thumbnail()
    thumb.save(os.path.join(MOD, 'thumbnail.png'), optimize=True)
    sc, n_tiles = showcase(icons, techs, thumb)
    sc.save(os.path.join(GAME, 'showcase.png'), optimize=True)
    cards(icons).save(os.path.join(GAME, 'cards.png'), optimize=True)
    n_files, problems = selftest()
    print('icons 64 px: %d · technologies 256 px: %d · rail-tracer · thumbnail · showcase tiles: %d · cards: %d'
          % (len(icons), len(techs), n_tiles, len(ENTITIES)))
    if problems:
        print('SELFTEST FAILED:\n  ' + '\n  '.join(problems))
        return 1
    print('selftest ok: %d files, sizes and RGBA mode as §10.1 / S13; every icon spec.py references exists;'
          ' §10.2 colours = spec.py tints x 255' % n_files)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
