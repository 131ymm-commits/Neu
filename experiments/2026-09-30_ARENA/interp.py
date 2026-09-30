# «Арена»: интерпретатор правил задачи — подмножество Python, исполнение по AST с белым списком узлов.
# Семантика (опубликована нападающим): целые произвольной длины; деление только // (вниз) и % (знак делителя, как в Python);
# обновления последовательные; float, '/', импорты, ввод-вывод, lambda, классы, try, глобальные переменные запрещены.
# Правила — одна функция  def f(p): ... return <int>,  p — словарь целых/списков целых. Вспомогательные функции разрешены,
# рекурсия — с общим пределом глубины. Лимит: MAX_STEPS шагов (каждый узел-оператор и каждая итерация цикла — шаг).
import ast, sys, json

MAX_STEPS = 10_000_000
MAX_DEPTH = 200
BUILTINS = {'range', 'len', 'min', 'max', 'abs', 'sum', 'list', 'dict', 'sorted', 'reversed', 'enumerate', 'zip', 'int', 'bool', 'set', 'tuple', 'any', 'all', 'pow', 'divmod'}
METHODS = {'append', 'pop', 'insert', 'extend', 'index', 'count', 'get', 'keys', 'values', 'items', 'add', 'remove', 'discard', 'copy', 'sort', 'reverse', 'setdefault'}
ALLOWED = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For, ast.While, ast.If,
           ast.Break, ast.Continue, ast.Pass, ast.Expr, ast.Name, ast.Load, ast.Store, ast.Del, ast.Delete, ast.Constant, ast.BinOp, ast.UnaryOp,
           ast.BoolOp, ast.Compare, ast.Call, ast.Attribute, ast.Subscript, ast.Slice, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.IfExp,
           ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension, ast.keyword,
           ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
           ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.BitAnd, ast.BitOr, ast.BitXor,
           ast.LShift, ast.RShift, ast.Invert, ast.Starred)

class Reject(Exception): pass      # правила вне подмножества
class Limit(Exception): pass       # превышен лимит шагов/глубины

def check(src):
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if not isinstance(n, ALLOWED): raise Reject(f'запрещённый узел {type(n).__name__} (строка {getattr(n, "lineno", "?")})')
        if isinstance(n, ast.Constant) and not isinstance(n.value, (int, bool, type(None), str)): raise Reject('разрешены только целые константы')
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and not isinstance(getattr(n, '_parent', None), ast.Expr): pass
        if isinstance(n, ast.Attribute) and n.attr not in METHODS: raise Reject(f'запрещённый атрибут .{n.attr}')
        if isinstance(n, ast.Attribute) and n.attr.startswith('_'): raise Reject('запрещён доступ к _атрибутам')
        if isinstance(n, ast.Name) and n.id.startswith('__'): raise Reject('запрещены __имена')
        if isinstance(n, ast.FunctionDef) and (n.decorator_list or n.args.vararg or n.args.kwarg): raise Reject('декораторы и *args запрещены')
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    if 'f' not in names: raise Reject('нет функции f(p)')
    if any(not isinstance(n, (ast.FunctionDef, ast.Expr)) for n in tree.body): raise Reject('на верхнем уровне — только функции')
    return tree

class _Ret(Exception):
    def __init__(self, v): self.v = v
class _Brk(Exception): pass
class _Cnt(Exception): pass

class Interp:
    def __init__(self, tree, max_steps=MAX_STEPS):
        self.funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}; self.steps = 0; self.max = max_steps; self.depth = 0
    def tick(self, k=1):
        self.steps += k
        if self.steps > self.max: raise Limit('лимит шагов')
    def call_user(self, name, args, kw):
        fn = self.funcs[name]; self.depth += 1
        if self.depth > MAX_DEPTH: raise Limit('лимит глубины')
        env = {}
        ps = fn.args.args; defaults = fn.args.defaults
        for i, a in enumerate(ps):
            if i < len(args): env[a.arg] = args[i]
            elif a.arg in kw: env[a.arg] = kw[a.arg]
            else:
                j = i - (len(ps) - len(defaults))
                if j < 0: raise Reject(f'не хватает аргумента {a.arg}')
                env[a.arg] = self.ev(defaults[j], env)
        try:
            for st in fn.body: self.ex(st, env)
            r = None
        except _Ret as e: r = e.v
        self.depth -= 1; return r
    def ex(self, s, env):
        self.tick()
        t = type(s)
        if t is ast.Expr: self.ev(s.value, env)
        elif t is ast.Return: raise _Ret(self.ev(s.value, env) if s.value else None)
        elif t is ast.Assign:
            v = self.ev(s.value, env)
            for tg in s.targets: self.assign(tg, v, env)
        elif t is ast.AnnAssign:
            if s.value is not None: self.assign(s.target, self.ev(s.value, env), env)
        elif t is ast.AugAssign:
            cur = self.ev(ast.fix_missing_locations(self._load(s.target)), env); self.assign(s.target, self.binop(s.op, cur, self.ev(s.value, env)), env)
        elif t is ast.If:
            for st in (s.body if self.ev(s.test, env) else s.orelse): self.ex(st, env)
        elif t is ast.For:
            it = self.ev(s.iter, env)
            for v in it:
                self.tick(); self.assign(s.target, v, env)
                try:
                    for st in s.body: self.ex(st, env)
                except _Brk: break
                except _Cnt: continue
            else:
                for st in s.orelse: self.ex(st, env)
        elif t is ast.While:
            while self.ev(s.test, env):
                self.tick()
                try:
                    for st in s.body: self.ex(st, env)
                except _Brk: break
                except _Cnt: continue
            else:
                for st in s.orelse: self.ex(st, env)
        elif t is ast.Break: raise _Brk()
        elif t is ast.Continue: raise _Cnt()
        elif t is ast.Pass: pass
        elif t is ast.Delete:
            for tg in s.targets:
                if isinstance(tg, ast.Subscript): del self.ev(tg.value, env)[self.ev(tg.slice, env)]
                elif isinstance(tg, ast.Name): del env[tg.id]
        elif t is ast.FunctionDef: raise Reject('вложенные функции запрещены')
        else: raise Reject(f'оператор {t.__name__}')
    def _load(self, tg):
        n = ast.parse(ast.unparse(tg), mode='eval').body; return n
    def assign(self, tg, v, env):
        if isinstance(tg, ast.Name): env[tg.id] = v
        elif isinstance(tg, (ast.Tuple, ast.List)):
            vs = list(v)
            if len(vs) != len(tg.elts): raise Reject('распаковка: не то число значений')
            for a, b in zip(tg.elts, vs): self.assign(a, b, env)
        elif isinstance(tg, ast.Subscript):
            obj = self.ev(tg.value, env)
            if isinstance(tg.slice, ast.Slice): obj[self.slice(tg.slice, env)] = v
            else: obj[self.ev(tg.slice, env)] = v
        else: raise Reject('недопустимая цель присваивания')
    def slice(self, s, env):
        return slice(*(self.ev(x, env) if x is not None else None for x in (s.lower, s.upper, s.step)))
    def binop(self, op, a, b):
        t = type(op)
        if t is ast.Add: r = a + b
        elif t is ast.Sub: r = a - b
        elif t is ast.Mult:
            if isinstance(a, list) or isinstance(b, list):
                n = b if isinstance(a, list) else a; self.tick(max(0, n) // 64)
            r = a * b
        elif t is ast.FloorDiv: r = a // b
        elif t is ast.Mod: r = a % b
        elif t is ast.Pow:
            if isinstance(b, int) and b > 4096: raise Limit('слишком большая степень (используйте pow(a, b, m))')
            r = a ** b
        elif t is ast.BitAnd: r = a & b
        elif t is ast.BitOr: r = a | b
        elif t is ast.BitXor: r = a ^ b
        elif t is ast.LShift:
            if b > 100000: raise Limit('слишком большой сдвиг')
            r = a << b
        elif t is ast.RShift: r = a >> b
        else: raise Reject('операция')
        if isinstance(r, float): raise Reject('получилось нецелое')
        return r
    def cmp(self, op, a, b):
        t = type(op)
        return {ast.Eq: lambda: a == b, ast.NotEq: lambda: a != b, ast.Lt: lambda: a < b, ast.LtE: lambda: a <= b, ast.Gt: lambda: a > b,
                ast.GtE: lambda: a >= b, ast.In: lambda: a in b, ast.NotIn: lambda: a not in b, ast.Is: lambda: a is b, ast.IsNot: lambda: a is not b}[t]()
    def comp(self, gens, env, emit):
        def rec(i, env):
            if i == len(gens): emit(env); return
            g = gens[i]
            for v in self.ev(g.iter, env):
                self.tick(); e2 = dict(env); self.assign(g.target, v, e2)
                if all(self.ev(c, e2) for c in g.ifs): rec(i + 1, e2)
        rec(0, env)
    def ev(self, e, env):
        t = type(e)
        if t is ast.Constant: return e.value
        if t is ast.Name:
            if e.id in env: return env[e.id]
            if e.id in ('True', 'False', 'None'): return {'True': True, 'False': False, 'None': None}[e.id]
            raise Reject(f'неизвестное имя {e.id}')
        if t is ast.BinOp: return self.binop(e.op, self.ev(e.left, env), self.ev(e.right, env))
        if t is ast.UnaryOp:
            v = self.ev(e.operand, env)
            return {ast.USub: lambda: -v, ast.UAdd: lambda: +v, ast.Not: lambda: not v, ast.Invert: lambda: ~v}[type(e.op)]()
        if t is ast.BoolOp:
            if isinstance(e.op, ast.And):
                v = True
                for x in e.values:
                    v = self.ev(x, env)
                    if not v: return v
                return v
            v = False
            for x in e.values:
                v = self.ev(x, env)
                if v: return v
            return v
        if t is ast.Compare:
            a = self.ev(e.left, env)
            for op, c in zip(e.ops, e.comparators):
                b = self.ev(c, env)
                if not self.cmp(op, a, b): return False
                a = b
            return True
        if t is ast.IfExp: return self.ev(e.body, env) if self.ev(e.test, env) else self.ev(e.orelse, env)
        if t is ast.List: return [self.ev(x, env) for x in e.elts]
        if t is ast.Tuple: return tuple(self.ev(x, env) for x in e.elts)
        if t is ast.Set: return {self.ev(x, env) for x in e.elts}
        if t is ast.Dict: return {self.ev(k, env): self.ev(v, env) for k, v in zip(e.keys, e.values)}
        if t is ast.Subscript:
            obj = self.ev(e.value, env)
            if isinstance(e.slice, ast.Slice):
                r = obj[self.slice(e.slice, env)]; self.tick(len(r) // 64); return r
            return obj[self.ev(e.slice, env)]
        if t is ast.ListComp:
            out = []; self.comp(e.generators, env, lambda en: out.append(self.ev(e.elt, en))); return out
        if t is ast.SetComp:
            out = set(); self.comp(e.generators, env, lambda en: out.add(self.ev(e.elt, en))); return out
        if t is ast.GeneratorExp:
            out = []; self.comp(e.generators, env, lambda en: out.append(self.ev(e.elt, en))); return out
        if t is ast.DictComp:
            out = {}; self.comp(e.generators, env, lambda en: out.__setitem__(self.ev(e.key, en), self.ev(e.value, en))); return out
        if t is ast.Call:
            args = []
            for a in e.args:
                if isinstance(a, ast.Starred): args.extend(self.ev(a.value, env))
                else: args.append(self.ev(a, env))
            kw = {k.arg: self.ev(k.value, env) for k in e.keywords}
            if isinstance(e.func, ast.Name):
                n = e.func.id
                if n in self.funcs: return self.call_user(n, args, kw)
                if n in BUILTINS:
                    if n in ('sum', 'sorted', 'list', 'set', 'tuple', 'min', 'max', 'any', 'all', 'dict') and args and hasattr(args[0], '__len__'): self.tick(len(args[0]) // 64)
                    if n == 'range':
                        r = range(*args)
                        return r
                    if n == 'pow' and len(args) == 2 and isinstance(args[1], int) and args[1] > 4096: raise Limit('слишком большая степень')
                    if n == 'int' and args and not isinstance(args[0], (int, bool)): raise Reject('int() только от целых')
                    fn = {'len': len, 'min': min, 'max': max, 'abs': abs, 'sum': sum, 'list': list, 'dict': dict, 'sorted': sorted, 'reversed': reversed,
                          'enumerate': enumerate, 'zip': zip, 'int': int, 'bool': bool, 'set': set, 'tuple': tuple, 'any': any, 'all': all, 'pow': pow, 'divmod': divmod}[n]
                    if n == 'sorted' and 'key' in kw: raise Reject('sorted(key=...) запрещён')
                    return fn(*args, **kw)
                raise Reject(f'вызов {n}')
            if isinstance(e.func, ast.Attribute):
                obj = self.ev(e.func.value, env); m = e.func.attr
                if m == 'sort' and kw: raise Reject('sort(key=...) запрещён')
                if hasattr(obj, '__len__'): self.tick(len(obj) // 256 if m in ('index', 'count', 'copy', 'sort', 'remove', 'insert', 'pop', 'extend') else 0)
                return getattr(obj, m)(*args, **kw)
            raise Reject('вызов')
        if t is ast.Starred: raise Reject('*выражение')
        raise Reject(f'выражение {t.__name__}')

def run(src, p, max_steps=MAX_STEPS):
    """→ ('ok', int, шаги) | ('reject', сообщение) | ('limit', сообщение) | ('error', сообщение)"""
    try:
        tree = check(src); it = Interp(tree, max_steps); r = it.call_user('f', [json.loads(json.dumps(p))], {})
        if isinstance(r, bool) or not isinstance(r, int): return ('error', f'f вернула не целое: {type(r).__name__}')
        return ('ok', r, it.steps)
    except Reject as e: return ('reject', str(e))
    except Limit as e: return ('limit', str(e))
    except RecursionError: return ('limit', 'лимит глубины Python')
    except Exception as e: return ('error', f'{type(e).__name__}: {e}')

if __name__ == '__main__':
    src = open(sys.argv[1]).read(); p = json.loads(sys.argv[2]); print(run(src, p))
