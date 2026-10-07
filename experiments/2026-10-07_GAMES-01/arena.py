# GAMES-01: сборка табличной политики из программы-стратегии головы и точная правда (NashConv) — решение совета 27.
# Программа головы — файл Python с функцией strategy(obs: str, legal: list[int], player: int) -> dict[int, float].
# obs — строка информационного состояния игры (information_state_string), legal — допустимые ходы. Без своего ГСЧ, без open_spiel.
# Исполнение — в отдельном процессе-песочнице: лимит CPU C_HEAD (с), память MEM, без сети (запрет импорта socket/open_spiel и т.д.),
# сам код головы не видит правды. Падение (исключение / недопустимый ход / не уложился) хотя бы в одном состоянии →
# NashConv кандидата = max(NashConv равномерной, NashConv с подстановкой равномерной) (правило совета).
#   python3 arena.py truth <game_string> <strategy.py>   — печатает JSON {nashconv, crashed, n_infosets, uniform, norm_strength?}
#   python3 arena.py smoke                                — дымовой тест на kuhn_poker (равномерная, «всегда пас», ошибочная, CFR)
import json, os, resource, subprocess, sys, tempfile
C_HEAD = 60; MEM = 2 << 30
BANNED = ('open_spiel', 'pyspiel', 'socket', 'subprocess', 'urllib', 'http', 'requests', 'ctypes', 'multiprocessing')

RUNNER = r'''
import json, sys, builtins, resource
resource.setrlimit(resource.RLIMIT_CPU, (%d, %d)); resource.setrlimit(resource.RLIMIT_AS, (%d, %d))
BANNED = %r
_imp = builtins.__import__
def guard(name, *a, **k):
    if name.split('.')[0] in BANNED: raise ImportError('запрещено: ' + name)
    return _imp(name, *a, **k)
builtins.__import__ = guard
src = open(sys.argv[1]).read(); ns = {}
exec(compile(src, 'strategy.py', 'exec'), ns)
qs = json.load(open(sys.argv[2])); out = {}
for key, (obs, legal, player) in qs.items():
    try:
        d = ns['strategy'](obs, legal, player); d = {int(a): float(p) for a, p in d.items()}
        if not d or any(a not in legal for a in d) or any(p < 0 or p != p for p in d.values()) or sum(d.values()) <= 0: raise ValueError('недопустимое распределение')
        s = sum(d.values()); out[key] = {a: p / s for a, p in d.items()}
    except Exception as e:
        out[key] = {'error': type(e).__name__ + ': ' + str(e)[:100]}
json.dump(out, open(sys.argv[3], 'w'))
''' % (C_HEAD, C_HEAD, MEM, MEM, BANNED)

def infosets(game):
    import pyspiel
    from open_spiel.python import policy as P
    tp = P.TabularPolicy(game); qs = {}
    def walk(s):
        if s.is_terminal(): return
        if s.is_chance_node():
            for a, _ in s.chance_outcomes(): walk(s.child(a))
            return
        p = s.current_player(); key = s.information_state_string(p)
        if key not in qs: qs[key] = (key, s.legal_actions(p), p)
        for a in s.legal_actions(): walk(s.child(a))
    walk(game.new_initial_state()); return tp, qs

def truth(game_string, strat_path):
    import pyspiel
    from open_spiel.python import policy as P
    from open_spiel.python.algorithms import exploitability
    g = pyspiel.load_game(game_string); tp, qs = infosets(g)
    uni = exploitability.nash_conv(g, P.UniformRandomPolicy(g))
    with tempfile.TemporaryDirectory(prefix='arena_') as d:
        open(f'{d}/run.py', 'w').write(RUNNER); json.dump(qs, open(f'{d}/q.json', 'w'))
        try:
            p = subprocess.run([sys.executable, '-I', f'{d}/run.py', os.path.abspath(strat_path), f'{d}/q.json', f'{d}/a.json'],
                               cwd=d, capture_output=True, text=True, timeout=C_HEAD * 2, env={'PATH': '/usr/bin:/bin'})
            ans = json.load(open(f'{d}/a.json')) if p.returncode == 0 else None
            err = None if p.returncode == 0 else (p.stderr[-300:] or f'код {p.returncode}')
        except subprocess.TimeoutExpired:
            ans, err = None, 'таймаут'
    crashed = ans is None or any('error' in v for v in ans.values())
    for key, (_, legal, player) in qs.items():
        row = tp.policy_for_key(key); row[:] = 0
        v = (ans or {}).get(key)
        if v is None or 'error' in v:
            for a in legal: row[a] = 1 / len(legal)
        else:
            for a, pr in v.items(): row[int(a)] = pr
    nc_fill = exploitability.nash_conv(g, tp)
    nc = max(uni, nc_fill) if crashed else nc_fill
    n_err = len(qs) if ans is None else sum('error' in v for v in ans.values())
    return dict(nashconv=nc, nashconv_fill=nc_fill, crashed=crashed, n_err=n_err, error=err, n_infosets=len(qs), uniform=uni)

if __name__ == '__main__':
    if sys.argv[1] == 'truth':
        print(json.dumps(truth(sys.argv[2], sys.argv[3]), ensure_ascii=False))
    elif sys.argv[1] == 'smoke':
        d = tempfile.mkdtemp(prefix='smoke_')
        S = {'uniform': 'def strategy(obs, legal, player):\n    return {a: 1 for a in legal}\n',
             'always_first': 'def strategy(obs, legal, player):\n    return {legal[0]: 1}\n',
             'buggy': 'def strategy(obs, legal, player):\n    if "1" in obs: raise RuntimeError("x")\n    return {legal[0]: 1}\n',
             'illegal': 'def strategy(obs, legal, player):\n    return {99: 1}\n',
             'cheat_import': 'import pyspiel\ndef strategy(obs, legal, player):\n    return {legal[0]: 1}\n',
             'kuhn_nash': ('def strategy(obs, legal, player):\n'
                           '    # равновесие Kuhn (alpha = 0: J не блефует, K первым не ставит, 3·alpha = 0): карта J=0, Q=1, K=2; ходы 0 — пас/сброс, 1 — ставка/колл\n'
                           '    card = int(obs[0]); hist = obs[1:]\n'
                           '    if player == 0 and hist == "": return {0: 1, 1: 0}\n'
                           '    if player == 1 and hist == "p": return {0: 2/3, 1: 1/3} if card == 0 else ({0: 1, 1: 0} if card == 1 else {0: 0, 1: 1})\n'
                           '    if player == 1 and hist == "b": return {0: 1, 1: 0} if card == 0 else ({0: 2/3, 1: 1/3} if card == 1 else {0: 0, 1: 1})\n'
                           '    if player == 0 and hist == "pb": return {0: 1, 1: 0} if card == 0 else ({0: 2/3, 1: 1/3} if card == 1 else {0: 0, 1: 1})\n'
                           '    return {a: 1 for a in legal}\n')}
        for k, src in S.items():
            p = f'{d}/{k}.py'; open(p, 'w').write(src); r = truth('kuhn_poker', p)
            print(k, json.dumps({x: (round(v, 4) if isinstance(v, float) else v) for x, v in r.items()}, ensure_ascii=False))
