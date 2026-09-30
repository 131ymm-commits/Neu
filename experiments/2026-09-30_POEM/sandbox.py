# «Арена»: второй исполнитель — CPython в песочнице (отдельный процесс, лимит CPU и памяти, без сети, пустой каталог).
#   run_py(src, p, cpu_s=10, mem_mb=512) → ('ok', int) | ('limit', msg) | ('error', msg)
import json, os, subprocess, tempfile, resource, sys

RUNNER = r'''
import json, sys
src = open(sys.argv[1]).read(); p = json.loads(open(sys.argv[2]).read())
g = {}
exec(compile(src, 'rules', 'exec'), g)
r = g['f'](p)
if isinstance(r, bool) or not isinstance(r, int): print(json.dumps({'err': 'не целое'}))
else: print(json.dumps({'ok': str(r)}))
'''
def _limits(cpu_s, mem_mb):
    def f():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
        os.setsid()
    return f
def run_py(src, p, cpu_s=10, mem_mb=512, allow_imports=False):
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, 'rules.py'); b = os.path.join(d, 'p.json'); r = os.path.join(d, 'run.py')
        open(a, 'w').write(src); open(b, 'w').write(json.dumps(p)); open(r, 'w').write(RUNNER)
        env = {'PATH': '/usr/bin:/bin', 'PYTHONHASHSEED': '0', 'HOME': d, 'no_proxy': '*', 'NO_PROXY': '*'}
        try:
            cp = subprocess.run([sys.executable, '-I', r, a, b], cwd=d, env=env, capture_output=True, text=True,
                                timeout=cpu_s * 3 + 5, preexec_fn=_limits(cpu_s, mem_mb))
        except subprocess.TimeoutExpired: return ('limit', 'время по часам')
        if cp.returncode != 0:
            if cp.returncode in (-9, -24) or 'MemoryError' in cp.stderr: return ('limit', f'код {cp.returncode}: {cp.stderr[-200:]}')
            return ('error', cp.stderr[-300:])
        try: o = json.loads(cp.stdout.strip().splitlines()[-1])
        except Exception: return ('error', 'нет вывода')
        return ('ok', int(o['ok'])) if 'ok' in o else ('error', o.get('err'))

RUNNER_CHECK = r"""
import json, sys
sys.path.insert(0, sys.argv[3])
import poemlib
src = open(sys.argv[1]).read(); poem = open(sys.argv[2]).read()
g = dict(poemlib.LIB)
exec(compile(src, 'check', 'exec'), g)
r = g['check'](poem)
print(json.dumps({'ok': r} if isinstance(r, bool) else {'err': 'не bool'}))
"""
def run_check_py(src, poem, libdir, cpu_s=20, mem_mb=1024):
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, 'check.py'); b = os.path.join(d, 'poem.txt'); r = os.path.join(d, 'run.py')
        open(a, 'w').write(src); open(b, 'w').write(poem); open(r, 'w').write(RUNNER_CHECK)
        env = {'PATH': '/usr/bin:/bin', 'PYTHONHASHSEED': '0', 'HOME': d}
        try:
            cp = subprocess.run([sys.executable, r, a, b, libdir], cwd=d, env=env, capture_output=True, text=True, timeout=cpu_s * 3 + 5, preexec_fn=_limits(cpu_s, mem_mb))
        except subprocess.TimeoutExpired: return ('limit', 'время')
        if cp.returncode != 0: return ('error', cp.stderr[-300:])
        try: o = json.loads(cp.stdout.strip().splitlines()[-1])
        except Exception: return ('error', 'нет вывода')
        return ('ok', o['ok']) if 'ok' in o else ('error', o.get('err'))
