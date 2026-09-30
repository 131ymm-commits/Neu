"""Проверка прототипов мода по машиночитаемой документации Factorio (prototype-api.json той же версии).
Игра молча пропускает неизвестные ключи, поэтому опечатка вроде `crafting_speeed` загрузится без ошибки.
Здесь каждый ключ каждой таблицы (рекурсивно) сверяется со списком свойств типа, союзы перебираются по вариантам.
Вход: JSON-выгрузка data.raw (делает тестовый мод magnetics-tests на стадии data-final-fixes)."""
import json, sys

class API:
    def __init__(self, path):
        p = json.load(open(path))
        self.version = p['application_version']
        self.protos = {x['name']: x for x in p['prototypes']}
        self.by_typename = {x['typename']: x for x in p['prototypes'] if x.get('typename')}
        self.types = {x['name']: x for x in p['types']}
        self._props = {}

    def props(self, d, table):
        key = (table, d['name'])
        if key in self._props: return self._props[key]
        out, cur = {}, d
        while cur:
            for q in cur.get('properties', []):
                out.setdefault(q['name'], q)
                for alt in q.get('alt_name', []) if isinstance(q.get('alt_name'), list) else ([q['alt_name']] if q.get('alt_name') else []):
                    out.setdefault(alt, q)
            par = cur.get('parent')
            cur = (self.protos if table == 'p' else self.types).get(par) if par else None
        custom = d.get('custom_properties') is not None
        self._props[key] = (out, custom)
        return out, custom

BUILTIN_NUM = {'double', 'float', 'int8', 'int16', 'int32', 'uint8', 'uint16', 'uint32', 'uint64', 'number'}

def rank(errs):
    """Из вариантов союза выбираем тот, где меньше ошибок; при равенстве — где ошибка глубже (точнее указан путь)."""
    return (len(errs), -max(p.count('.') + p.count('[') for p, _ in errs))

class Checker:
    def __init__(self, api):
        self.api = api

    def check(self, v, t, path, depth=0):
        """Возвращает список ошибок (путь, сообщение)."""
        if depth > 60: return []
        a = self.api
        if isinstance(t, str):
            if t in BUILTIN_NUM:
                return [] if isinstance(v, (int, float)) and not isinstance(v, bool) else [(path, f'ожидалось число ({t}), получено {type(v).__name__}')]
            if t == 'boolean':
                return [] if isinstance(v, bool) else [(path, f'ожидалось boolean, получено {type(v).__name__}')]
            if t == 'string':
                return [] if isinstance(v, str) else [(path, f'ожидалась строка, получено {type(v).__name__}')]
            if t in ('table', 'DataExtendMethod'): return []
            d = a.types.get(t)
            if d is None: return []          # неизвестный тип — не судим
            dt = d.get('type')
            opts = dt.get('options', []) if isinstance(dt, dict) and dt.get('complex_type') == 'union' else None
            if isinstance(dt, dict) and dt.get('complex_type') == 'struct':
                opts = [dt]
            if opts is None:
                return self.check(v, dt, path, depth + 1)
            best = None
            for o in opts:
                if isinstance(o, dict) and o.get('complex_type') == 'struct':
                    if isinstance(v, list) and len(v) == 0: return []
                    if not isinstance(v, dict):
                        e = [(path, f'ожидалась таблица {t}, получено {type(v).__name__}')]
                    else:
                        props, custom = a.props(d, 't')
                        e = self.struct(v, props, custom, path, depth, t)
                else:
                    e = self.check(v, o, path, depth + 1)
                if not e: return []
                if best is None or rank(e) < rank(best): best = e
            return best or []
        ct = t.get('complex_type')
        if ct == 'type': return self.check(v, t['value'], path, depth + 1)
        if ct == 'literal':
            return [] if v == t['value'] else [(path, f'ожидалось {t["value"]!r}, получено {v!r}')]
        if ct == 'array':
            if isinstance(v, dict) and not v: return []
            if isinstance(v, dict):   # разреженный массив Lua
                v = list(v.values())
            if not isinstance(v, list): return [(path, f'ожидался массив, получено {type(v).__name__}')]
            errs = []
            for i, x in enumerate(v): errs += self.check(x, t['value'], f'{path}[{i+1}]', depth + 1)
            return errs
        if ct == 'dictionary':
            if isinstance(v, list): v = {str(i + 1): x for i, x in enumerate(v)}
            if not isinstance(v, dict): return [(path, 'ожидался словарь')]
            errs = []
            for k, x in v.items(): errs += self.check(x, t['value'], f'{path}.{k}', depth + 1)
            return errs
        if ct == 'tuple':
            if isinstance(v, dict) and all(k.isdigit() for k in v): v = [v[k] for k in sorted(v, key=int)]
            if not isinstance(v, list): return [(path, 'ожидался кортеж')]
            errs = []
            for i, (x, tt) in enumerate(zip(v, t['values'])): errs += self.check(x, tt, f'{path}[{i+1}]', depth + 1)
            return errs
        if ct == 'union':
            best = None
            for o in t['options']:
                e = self.check(v, o, path, depth + 1)
                if not e: return []
                if best is None or rank(e) < rank(best): best = e
            return best or []
        if ct == 'struct': return []
        return []

    def struct(self, v, props, custom, path, depth, tname):
        errs = []
        for k, x in v.items():
            q = props.get(k)
            if q is None:
                if not custom: errs.append((f'{path}.{k}', f'неизвестное свойство для {tname}'))
                continue
            errs += self.check(x, q['type'], f'{path}.{k}', depth + 1)
        for k, q in props.items():
            if not q.get('optional', True) and k not in v and not q.get('override'):
                pass   # обязательность проверяет сама игра при загрузке
        return errs

    def prototype(self, proto):
        d = self.api.by_typename.get(proto.get('type'))
        if d is None: return [(proto.get('name'), f'нет прототипа с typename {proto.get("type")}')]
        props, custom = self.api.props(d, 'p')
        return self.struct(proto, props, custom, f'{proto["type"]}/{proto["name"]}', 0, d['name'])

def err_key(path, msg):
    """Ключ ошибки без номеров и имён прототипов: (тип, ключ, сообщение)."""
    return (msg, path.rsplit('.', 1)[-1].split('[')[0])

def main(dump, api_path='/opt/factorio-api/prototype-api.json', prefix=None):
    api = API(api_path)
    ch = Checker(api)
    raw = json.load(open(dump))
    n, errs = 0, []
    for typ, lst in raw.items():
        for name, proto in lst.items():
            if prefix and not name.startswith(prefix): continue
            n += 1
            errs += ch.prototype(proto)
    return n, errs

def check_mod(dump, prefix, tolerated_path=None):
    """Ошибки прототипов мода, кроме шаблонов, которые встречаются в самой ванили 2.0.77 (vanilla_tolerated.json)."""
    import os
    tolerated_path = tolerated_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vanilla_tolerated.json')
    tol = {tuple(x) for x in json.load(open(tolerated_path))}
    n, errs = main(dump, prefix=prefix)
    hard = [(p, m) for p, m in errs if err_key(p, m) not in tol]
    return n, hard, len(errs) - len(hard)

if __name__ == '__main__':
    dump = sys.argv[1]; prefix = sys.argv[2] if len(sys.argv) > 2 else 'magnetics-'
    n, hard, soft = check_mod(dump, prefix)
    for p, m in hard: print(f'  {p}: {m}')
    print(f'прототипов проверено {n}, ошибок {len(hard)} (ещё {soft} — шаблоны, которые есть в самой ванили)')
    sys.exit(1 if hard else 0)
