#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: проверка утверждений голов кодом (правда от кода, без судьи-LLM).

1. Разбор ответа: нормализация записи (Юникод, ^, «=», неявное умножение), белый список узлов ast, только имена
   столбцов ячейки, числа, pi, e и функции sqrt, log, ln, log10, exp, sin, cos, tan, abs.
2. Мера сохранения R(E; строки) = IQR(E на строках) / IQR(E на тех же строках с независимо перемешанными столбцами).
   R ≈ 0 — выражение держит связь строк; R ≈ 1 — связи нет. Выражение одного столбца даёт R = 1 точно.
   «Держится» — R < TAU и на новых строках в диапазоне (in), и вне его (out).
3. Тривиальное — постоянно на всём ящике значений (например a - a). Зависимость от столбца — численно.
4. Равносильность двух утверждений (одна и та же связь): утверждение E — поверхность {E = c}, c — медиана E на показанных
   строках (13 строк: медиана — порядковая статистика). E1 ~ E2, если E2 почти постоянно на точках поверхности E1 и наоборот:
   max(R(E2 | S1), R(E1 | S2)) < TAU_AGREE, где R(E2 | S1) = IQR(E2 на S1) / IQR(E2 на точках Q). Q — показанные строки
   с независимо перемешанными столбцами (то же опорное распределение, что в R); точки S1 строятся из точек Q решением
   одной переменной и берутся только внутри области данных [min/1,5; 1,5·max] по каждому столбцу.
   Следствие (консервативно для ложного согласия): функции одного выражения (отношение, обратное, логарифм) согласуются
   всегда; формы «отношение» и «разность» одного закона (U/(I*R) и U - I*R) согласуются, только когда медианные
   константы соответствуют друг другу, то есть в T, но не в Z.
5. Согласие таблицы — наибольшая клика равносильных годных утверждений; согласие = клика ≥ 3 из 4.
Все случайные потоки — numpy Generator от sha256 строки-метки.
"""
import ast
import hashlib
import math
import re

import numpy as np

TAU = 0.1            # порог «держится» для R
TAU_AGREE = 0.1      # порог равносильности
N_PERM_SHOWN = 300   # перестановок для показанных строк
N_PERM_HOLD = 20     # перестановок для новых строк (400 строк × 20)
N_BASE = 600         # опорных точек для равносильности и тривиальности
MIN_SURF = 100       # минимум точек на поверхности, иначе равносильность «не определена» (= нет)

FUNCS = {'sqrt': np.sqrt, 'log': np.log, 'ln': np.log, 'log10': np.log10, 'exp': np.exp,
         'sin': np.sin, 'cos': np.cos, 'tan': np.tan, 'abs': np.abs}
CONSTS = {'pi': math.pi, 'e': math.e}
NONE_RE = re.compile(r'^\s*(нет|none|no|n/?a|отсутствует)\b', re.I)


def gen(label):
    return np.random.default_rng(int.from_bytes(hashlib.sha256(str(label).encode('utf-8')).digest()[:8], 'big'))


# ---------- разбор ----------

class ParseError(Exception):
    pass


def normalize(text, idents):
    """Строка ответа → (вид, выражение, флаги). Вид: 'NONE' | 'EXPR'. Ошибка разбора — ParseError."""
    flags = []
    s = str(text or '').strip()
    s = s.strip('`').strip()
    if s.startswith(('"', "'", '«')) and s.endswith(('"', "'", '»')):
        s = s[1:-1].strip()
    if not s or NONE_RE.match(s):
        return 'NONE', None, flags
    rep = [('−', '-'), ('–', '-'), ('—', '-'), ('·', '*'), ('×', '*'), ('⋅', '*'), ('∙', '*'), ('÷', '/'),
           ('²', '**2'), ('³', '**3'), ('⁴', '**4'), ('π', 'pi'), ('^', '**'), ('，', ','), (' ', ' ')]
    for a, b in rep:
        if a in s:
            s = s.replace(a, b)
            flags.append(f'замена {a}')
    s = re.sub(r'√\s*\(', 'sqrt(', s)
    s = re.sub(r'√\s*([A-Za-z_][A-Za-z_0-9]*|\d+\.?\d*)', r'sqrt(\1)', s)
    # «=»: если одна сторона без столбцов — берётся другая; если обе со столбцами — (лев) - (прав)
    if '=' in s.replace('==', '='):
        parts = [x.strip() for x in s.replace('==', '=').split('=') if x.strip()]
        has = [bool(set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', x)) & set(idents)) for x in parts]
        flags.append('знак =')
        if len(parts) == 2 and has[0] and has[1]:
            s = f'({parts[0]}) - ({parts[1]})'
        elif any(has):
            s = parts[has.index(True)]
        else:
            raise ParseError('в выражении со знаком = нет столбцов')
    # неявное умножение: число перед именем или скобкой; ) перед ( или именем
    # число (с экспонентой целиком: 1e12 не режется на 1*e12 — ошибка, найденная пилотом b) перед именем или скобкой
    s2 = re.sub(r'(?<![A-Za-z_0-9.])(\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)(?![\d.]|[eE][-+]?\d)\s*([A-Za-z_(])', r'\1*\2', s)
    s2 = re.sub(r'\)\s*([A-Za-z_(])', r')*\1', s2)
    if s2 != s:
        flags.append('неявное умножение')
        s = s2
    return 'EXPR', s, flags


_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Call, ast.Load,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)


def compile_expr(expr, idents):
    """Выражение → функция f(точки) → массив значений. точки: dict имя → np.array (одной формы)."""
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ParseError(f'синтаксис: {e.msg}')
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ParseError(f'недопустимый узел {type(node).__name__}')
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ParseError('недопустимая константа')
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS or len(node.args) != 1 or node.keywords:
                raise ParseError('недопустимый вызов функции')
        if isinstance(node, ast.Name):
            if node.id not in idents and node.id not in CONSTS and node.id not in FUNCS:
                raise ParseError(f'неизвестное имя {node.id}')
    code = compile(tree, '<inv>', 'eval')

    def f(points):
        ns = dict(FUNCS)
        ns.update(CONSTS)
        for k in idents:
            if k in points:
                ns[k] = np.asarray(points[k], dtype=float)
        with np.errstate(all='ignore'):
            v = eval(code, {'__builtins__': {}}, ns)   # узлы проверены выше: только арифметика и функции из списка
            v = np.asarray(v, dtype=float)
            arrs = [ns[k] for k in idents if k in points]
            shape = arrs[0].shape if arrs else ()
            if v.shape != shape:                       # выражение без столбцов или с меньшей формой
                v = np.broadcast_to(v, shape).astype(float)
            v = np.where(np.isfinite(v), v, np.nan)
        return v
    f.expr = expr
    f.idents = list(idents)
    return f


def rows_to_points(rows, idents):
    return {k: np.array([r[k] for r in rows], dtype=float) for k in idents}


# ---------- мера сохранения ----------

def iqr(v):
    v = v[np.isfinite(v)]
    if v.size < 4:
        return float('nan')
    q75, q25 = np.percentile(v, [75, 25])
    return float(q75 - q25)


def R_measure(f, rows, idents, seed, n_perm=None):
    """R = IQR(E на строках) / IQR(E на строках с независимо перемешанными столбцами). nan — нельзя посчитать."""
    n = len(rows)
    n_perm = n_perm or (N_PERM_SHOWN if n < 100 else N_PERM_HOLD)
    pts = rows_to_points(rows, idents)
    vals = f(pts)
    if np.mean(np.isfinite(vals)) < 0.8:
        return float('nan')
    g = gen(f'R|{seed}')
    perm = {k: np.concatenate([g.permutation(pts[k]) for _ in range(n_perm)]) for k in idents}
    pv = f(perm)
    den = iqr(pv)
    if not math.isfinite(den) or den <= 0:
        return float('nan')
    return iqr(vals) / den


# ---------- опорные точки, тривиальность, зависимость ----------

def base_points(shown_rows, idents, label, n=N_BASE):
    """Опорные точки: каждый столбец независимо; половина — значения столбца с лог-шумом ±30 %, половина —
    лог-равномерно в [min/2, 2·max]. Значения столбцов положительны (все законы мира — с положительными величинами)."""
    g = gen(f'base|{label}')
    pts = {}
    for k in idents:
        col = np.array([r[k] for r in shown_rows], dtype=float)
        lo, hi = col.min() / 2, col.max() * 2
        a = g.choice(col, size=n) * np.exp(g.uniform(-0.3, 0.3, size=n))
        b = np.exp(g.uniform(math.log(lo), math.log(hi), size=n))
        pts[k] = np.where(g.random(n) < 0.5, a, b)
    return pts


def depends_on(f, base, idents):
    """Столбцы, от которых выражение зависит численно (умножение столбца на 1,37 в 60 опорных точках)."""
    sub = {k: v[:60] for k, v in base.items()}
    e0 = f(sub)
    dep = []
    for k in idents:
        s2 = dict(sub)
        s2[k] = sub[k] * 1.37
        e1 = f(s2)
        ok = np.isfinite(e0) & np.isfinite(e1)
        if ok.any() and np.max(np.abs(e1[ok] - e0[ok]) / (np.abs(e0[ok]) + 1e-12)) > 1e-9:
            dep.append(k)
    return dep


# ---------- поверхность уровня и равносильность ----------

def surface_points(f, c, base, idents, deps, shown_rows, n_grid=400, iters=60):
    """Точки на {f = c}: из каждой опорной точки решается одна переменная (по кругу из deps) на лог-сетке
    [min/4, 4·max] столбца, корень ближайший к исходному значению, затем бисекция в логарифмах."""
    if not deps:
        return None
    K = len(next(iter(base.values())))
    out = {k: np.full(K, np.nan) for k in idents}
    for jj, j in enumerate(deps):
        rows_k = np.arange(jj, K, len(deps))
        if rows_k.size == 0:
            continue
        col = np.array([r[j] for r in shown_rows], dtype=float)
        lt = np.linspace(math.log(col.min() / 4), math.log(col.max() * 4), n_grid)
        X = {k: np.repeat(base[k][rows_k][:, None], n_grid, axis=1) for k in idents}
        X[j] = np.repeat(np.exp(lt)[None, :], rows_k.size, axis=0)
        gv = f(X) - c
        s = np.sign(gv)
        ch = (s[:, :-1] * s[:, 1:] < 0) & np.isfinite(gv[:, :-1]) & np.isfinite(gv[:, 1:])
        x0 = np.log(base[j][rows_k])
        dist = np.abs((lt[:-1] + lt[1:]) / 2 - x0[:, None])
        dist = np.where(ch, dist, np.inf)
        idx = np.argmin(dist, axis=1)
        okr = np.isfinite(dist[np.arange(rows_k.size), idx])
        lo = lt[idx].copy(); hi = lt[idx + 1].copy()
        glo = gv[np.arange(rows_k.size), idx]
        P = {k: base[k][rows_k].copy() for k in idents}
        for _ in range(iters):
            mid = (lo + hi) / 2
            P[j] = np.exp(mid)
            gm = f(P) - c
            same = np.sign(gm) == np.sign(glo)
            lo = np.where(same, mid, lo); glo = np.where(same, gm, glo)
            hi = np.where(same, hi, mid)
        P[j] = np.exp((lo + hi) / 2)
        for k in idents:
            out[k][rows_k] = np.where(okr, P[k], np.nan)
    good = np.all([np.isfinite(out[k]) for k in idents], axis=0)
    return {k: out[k][good] for k in idents}


class Claim:
    """Утверждение одной головы в одной таблице."""

    def __init__(self, raw, idents, shown_rows, label):
        self.raw = raw
        self.idents = idents
        self.kind = None          # NONE | EXPR | PARSE_ERR | TRIVIAL | INVALID
        self.flags = []
        self.f = None
        self.deps = []
        self.c = None
        self.err = None
        try:
            kind, expr, fl = normalize(raw, idents)
            self.flags = fl
            if kind == 'NONE':
                self.kind = 'NONE'
                return
            self.expr = expr
            self.f = compile_expr(expr, idents)
        except ParseError as e:
            self.kind = 'PARSE_ERR'
            self.err = str(e)
            return
        self.base = base_points(shown_rows, idents, label)
        bv = self.f(self.base)
        sv = self.f(rows_to_points(shown_rows, idents))
        if np.mean(np.isfinite(bv)) < 0.5 or np.mean(np.isfinite(sv)) < 0.8:
            self.kind = 'INVALID'
            self.err = 'выражение не определено на большей части значений'
            return
        spread = iqr(bv)
        if not math.isfinite(spread) or spread <= 1e-12 * (abs(np.nanmedian(bv)) + 1e-300):
            self.kind = 'TRIVIAL'
            return
        self.kind = 'EXPR'
        self.deps = depends_on(self.f, self.base, idents)
        svf = sv[np.isfinite(sv)]
        self.c = float(np.median(svf)) if svf.size % 2 == 1 else float(np.sort(svf)[svf.size // 2])

    @property
    def valid(self):
        return self.kind == 'EXPR'


def cond_R(f2, surf, base):
    """R(E2 | S1) = IQR(E2 на точках поверхности S1) / IQR(E2 на опорных точках)."""
    if surf is None or len(next(iter(surf.values()))) < MIN_SURF:
        return float('nan')
    den = iqr(f2(base))
    if not math.isfinite(den) or den <= 0:
        return float('nan')
    return iqr(f2(surf)) / den


def q_points(shown_rows, idents, label, n=N_BASE):
    """Точки Q: показанные строки с независимо перемешанными столбцами (значения столбцов с лог-шумом ±5 %)."""
    g = gen(f'q|{label}')
    pts = {}
    for k in idents:
        col = np.array([r[k] for r in shown_rows], dtype=float)
        pts[k] = g.choice(col, size=n) * np.exp(g.uniform(-0.05, 0.05, size=n))
    return pts


def in_box(pts, shown_rows, idents, widen=1.5):
    """Оставить точки внутри области данных [min/widen; widen·max] по каждому столбцу."""
    if pts is None:
        return None
    keep = np.ones(len(next(iter(pts.values()))), dtype=bool)
    for k in idents:
        col = np.array([r[k] for r in shown_rows], dtype=float)
        keep &= (pts[k] >= col.min() / widen) & (pts[k] <= col.max() * widen)
    return {k: v[keep] for k, v in pts.items()}


def agree(c1, c2, shown_rows, label):
    """Равносильны ли два годных утверждения. Возвращает (да/нет, R21, R12). nan → «не определено» = нет."""
    if not (c1.valid and c2.valid):
        return False, float('nan'), float('nan')
    q = q_points(shown_rows, c1.idents, f'agree|{label}')
    s1 = in_box(surface_points(c1.f, c1.c, q, c1.idents, c1.deps, shown_rows), shown_rows, c1.idents)
    s2 = in_box(surface_points(c2.f, c2.c, q, c2.idents, c2.deps, shown_rows), shown_rows, c2.idents)
    r21 = cond_R(c2.f, s1, q)
    r12 = cond_R(c1.f, s2, q)
    ok = math.isfinite(r21) and math.isfinite(r12) and max(r21, r12) < TAU_AGREE
    return ok, r21, r12


def all_max_cliques(n, edges):
    """Все клики наибольшего размера (перебор подмножеств; n ≤ 6)."""
    best, size = [], 0
    for mask in range(1, 1 << n):
        mem = [i for i in range(n) if mask >> i & 1]
        if len(mem) < size:
            continue
        if all((a, b) in edges for ia, a in enumerate(mem) for b in mem[ia + 1:]):
            if len(mem) > size:
                best, size = [mem], len(mem)
            else:
                best.append(mem)
    return best


def max_clique(n, edges, key=None):
    """Наибольшая клика. Ничья между кликами одного размера (совет 42, правка 7): по ключу представителя
    key(i) — у представителя наименьший key среди членов; между кликами — наименьший key представителя, затем номер
    представителя, затем лексикографически. Без key — лексикографически первая."""
    cl = all_max_cliques(n, edges)
    if not cl:
        return []
    if key is None:
        return cl[0]
    def rank(mem):
        rep = min(mem, key=lambda i: (key(i), i))
        return (key(rep), rep, mem)
    return min(cl, key=rank)


def holds(claim, hold_rows_in, hold_rows_out, label):
    """R на новых строках в диапазоне и вне его; держится — оба меньше TAU."""
    if not claim.valid:
        return {'R_in': None, 'R_out': None, 'holds': False}
    ri = R_measure(claim.f, hold_rows_in, claim.idents, seed=f'in|{label}')
    ro = R_measure(claim.f, hold_rows_out, claim.idents, seed=f'out|{label}')
    ok = math.isfinite(ri) and math.isfinite(ro) and ri < TAU and ro < TAU
    return {'R_in': ri, 'R_out': ro, 'holds': bool(ok)}
