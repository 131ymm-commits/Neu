# Обвязка: сервер Mindustry (headless, v146) с модом; команды консоли по очереди; чистый вывод.
#   python3 mdt.py [--mod DIR] [--wait N] "команда" ...    (js-команды: "js ...")
import subprocess, sys, os, re, time, shutil, threading
SRV = os.environ.get('MDT_DIR', '/tmp/claude-0/mdt')
def run(cmds, mod=None, wait=8, gap=1.5, tail=3):
    mods = os.path.join(SRV, 'config', 'mods'); shutil.rmtree(mods, ignore_errors=True); os.makedirs(mods)
    if mod: shutil.copytree(mod, os.path.join(mods, os.path.basename(os.path.abspath(mod))))
    p = subprocess.Popen(['java', '-jar', 'server.jar'], cwd=SRV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = []
    t = threading.Thread(target=lambda: [out.append(l) for l in p.stdout]); t.start()
    time.sleep(wait)
    for c in cmds:
        if c.startswith('sleep '): time.sleep(float(c[6:])); continue
        try: p.stdin.write(c + '\n'); p.stdin.flush()
        except BrokenPipeError: out.append('!! сервер завершился'); break
        time.sleep(gap)
    time.sleep(tail)
    try: p.stdin.write('exit\n'); p.stdin.flush()
    except BrokenPipeError: pass
    try: p.wait(20)
    except Exception: p.kill()
    t.join(5)
    return [re.sub(r'\x1b\[[0-9;]*m', '', l).rstrip() for l in out if 'JAVA_TOOL' not in l]
if __name__ == '__main__':
    a = sys.argv[1:]; mod = None; wait = 8
    while a and a[0].startswith('--'):
        if a[0] == '--mod': mod = a[1]; a = a[2:]
        elif a[0] == '--wait': wait = float(a[1]); a = a[2:]
    print('\n'.join(run(a, mod, wait)))
