"""PLAY-01: драйвер игры. Единица работы (решение совета 24): загрузить сейв раунда → подать действия → прогнать тики →
сохранить → погасить сервер. Пароль RCON — случайный на каждый запуск сервера, только в памяти драйвера (не в файлах).
Сейвы закрыты sha256 (журнал chain.json): перед загрузкой хеш сверяется, подмена сейва = сбой партии."""
import hashlib, json, os, secrets, shutil, socket, struct, subprocess, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORIO = os.environ.get('FACTORIO', '/opt/factorio')
BIN = os.path.join(FACTORIO, 'bin/x64/factorio')
MOD = os.path.join(HERE, 'neu-play_1.0.0')

def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()

def hexs(obj):
    return json.dumps(obj, ensure_ascii=False).encode('utf-8').hex()

class Rcon:
    def __init__(self, port, pw):
        for _ in range(120):
            try:
                self.s = socket.create_connection(('127.0.0.1', port), timeout=600)
                break
            except OSError:
                time.sleep(0.25)
        self.n = 1
        self.s.send(self._pkt(1, 3, pw))
        while True:
            i, t, _ = self._recv()
            if t == 2:
                if i == -1: raise RuntimeError('RCON: неверный пароль')
                break
        self.raw('/sc rcon.print("ok")')   # первая Lua-команда сохранения не выполняется (предупреждение о достижениях)
    @staticmethod
    def _pkt(i, t, body):
        b = body.encode() + b'\x00\x00'
        return struct.pack('<iii', len(b) + 8, i, t) + b
    def _recv(self):
        hdr = b''
        while len(hdr) < 4: hdr += self.s.recv(4 - len(hdr))
        n = struct.unpack('<i', hdr)[0]; d = b''
        while len(d) < n: d += self.s.recv(n - len(d))
        i, t = struct.unpack('<ii', d[:8])
        return i, t, d[8:-2].decode('utf-8', errors='replace')
    def raw(self, cmd):
        self.n += 1
        self.s.send(self._pkt(self.n, 2, cmd))
        while True:
            i, t, body = self._recv()
            if i == self.n: return body.strip()
    def call(self, fn, arg=None):
        """remote.call("neu_play", fn, arg) — аргумент только шестнадцатеричная строка или число (без склейки текста в Lua)."""
        if arg is None: a = ''
        elif isinstance(arg, (int, float)): a = ', ' + repr(arg)
        else:
            assert all(c in '0123456789abcdef' for c in arg)
            a = ', "' + arg + '"'
        out = self.raw(f'/sc rcon.print(remote.call("neu_play", "{fn}"{a}))')
        return out

class Server:
    """Сервер Factorio на сейве: свои порт, каталог записи и пароль."""
    def __init__(self, workdir, save, port):
        self.work, self.save, self.port = workdir, save, port
        self.pw = secrets.token_hex(16)
        os.makedirs(os.path.join(workdir, 'mods'), exist_ok=True)
        os.makedirs(os.path.join(workdir, 'wd', 'saves'), exist_ok=True)
        md = os.path.join(workdir, 'mods')
        dst = os.path.join(md, 'neu-play_1.0.0')
        if not os.path.exists(dst): shutil.copytree(MOD, dst)
        json.dump({'mods': [{'name': 'base', 'enabled': True}] + [{'name': n, 'enabled': False} for n in ('elevated-rails', 'quality', 'space-age')]
                   + [{'name': 'neu-play', 'enabled': True}]}, open(os.path.join(md, 'mod-list.json'), 'w'))
        open(os.path.join(workdir, 'config.ini'), 'w').write(f'[path]\nread-data={FACTORIO}/data\nwrite-data={workdir}/wd\n')
        ss = json.load(open(os.path.join(FACTORIO, 'data/server-settings.example.json')))
        ss.update(visibility={'public': False, 'lan': False}, require_user_verification=False, auto_pause=False,
                  username='', token='', password='', autosave_interval=0)
        json.dump(ss, open(os.path.join(workdir, 'ss.json'), 'w'))
        self.base = [BIN, '-c', os.path.join(workdir, 'config.ini'), '--mod-directory', md]
    def start(self):
        # сервер работает на копии: при выходе Factorio пересохраняет загруженный файл, а входной сейв закрыт хешем
        logp = os.path.join(self.work, 'server.log')
        live = os.path.join(self.work, 'live.zip')
        shutil.copy(self.save, live)
        self.p = subprocess.Popen(self.base + ['--start-server', live, '--port', str(self.port + 1000),
                                               '--rcon-port', str(self.port), '--rcon-password', self.pw,
                                               '--server-settings', os.path.join(self.work, 'ss.json')],
                                  stdin=subprocess.PIPE, stdout=open(logp, 'w'), stderr=subprocess.STDOUT)
        for _ in range(240):
            time.sleep(0.25)
            if 'Starting RCON interface' in open(logp, errors='replace').read(): break
            if self.p.poll() is not None: raise RuntimeError('сервер упал: ' + open(logp, errors='replace').read()[-2000:])
        self.r = Rcon(self.port, self.pw)
        return self
    def run_ticks(self, n):
        """Прогнать n тиков (игра на паузе, ticks_to_run) и дождаться остановки на тике-цели."""
        st = json.loads(self.r.call('status'))
        assert st['paused'], 'игра не на паузе перед прогоном'
        target = st['tick'] + int(n)
        self.r.call('run', int(n))
        while True:
            st = json.loads(self.r.call('status'))
            if st['paused'] and st['ticks_to_run'] == 0 and st['tick'] >= target:
                assert st['tick'] == target, f'перебег: {st["tick"]} != {target}'
                return st['tick']
            time.sleep(0.02)
    def save_as(self, path):
        """Сохранить (на паузе) и скопировать сейв; гасить процесс можно только после «Saving finished» в логе."""
        name = 'neu_' + secrets.token_hex(4)
        logp = os.path.join(self.work, 'server.log')
        n0 = open(logp, errors='replace').read().count('Saving finished')
        out = json.loads(self.r.call('save', name.encode().hex()))
        assert out['ok'], out
        src = os.path.join(self.work, 'wd', 'saves', name + '.zip')
        for _ in range(1200):
            if open(logp, errors='replace').read().count('Saving finished') > n0 and os.path.exists(src): break
            time.sleep(0.05)
        else:
            raise RuntimeError('сейв не записан')
        shutil.copy(src, path)
        os.remove(src)
        return sha(path)
    def stop(self):
        try: self.r.raw('/quit')
        except Exception: pass
        try: self.p.wait(30)
        except Exception: self.p.kill()

PORTS = iter(range(27100, 28000))
LIST_FIELDS = ('crafting_queue', 'entities', 'resources_within_48', 'resources_far', 'last_actions', 'obstacles_near')

def norm_obs(o):
    """Пустая таблица Lua приходит как {}; поля-списки приводятся к []."""
    for k in LIST_FIELDS:
        if o.get(k) == {}: o[k] = []
    for k in ('researched', 'available'):
        if o.get('research', {}).get(k) == {}: o['research'][k] = []
    for r in o.get('resources_within_48', []):
        if r.get('patch_near') == {}: r['patch_near'] = []
    return o

def create_initial(seed, out_save, work, setup=None):
    """Исходный сейв зерна: карта по зерну без баз жуков (мирный режим), сервер на ней, setup (персонаж и стартовый
    набор freeplay), сохранение на паузе. Возвращает (sha256 сейва, ответ setup)."""
    os.makedirs(work, exist_ok=True)
    srv = Server(work, None, next(PORTS))
    mg = json.load(open(os.path.join(FACTORIO, 'data/map-gen-settings.example.json')))
    mg['autoplace_controls']['enemy-base'] = {'frequency': 0, 'size': 0}
    mg['peaceful_mode'] = True
    mg['cliff_settings'] = dict(mg.get('cliff_settings', {}), richness=0)   # без утёсов: поиска пути у персонажа нет
    mgp = os.path.join(work, 'mapgen.json')
    json.dump(mg, open(mgp, 'w'))
    raw0 = os.path.join(work, 'raw.zip')
    r = subprocess.run(srv.base + ['--create', raw0, '--map-gen-seed', str(seed), '--map-gen-settings', mgp],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0: raise RuntimeError(r.stdout[-2000:])
    srv.save = raw0
    srv.start()
    try:
        st = json.loads(srv.r.call('status'))
        if not st['paused']: srv.r.raw('/sc game.tick_paused = true')
        out = json.loads(srv.r.call('setup', hexs(setup or {})))
        h = srv.save_as(out_save)
    finally:
        srv.stop()
    return h, out

def round_unit(save_in, sha_in, actions, ticks, save_out, work, observe_after=True):
    """Единица работы совета 24: загрузить сейв раунда (хеш сверяется) → подать действия → прогнать тики → закончить
    раунд → сохранить → погасить сервер. Возвращает отчёт раунда (лог действий, наблюдение, хеш состояния, sha сейва)."""
    if sha(save_in) != sha_in: raise RuntimeError('сейв подменён: sha не совпадает с журналом')
    srv = Server(work, save_in, next(PORTS)).start()
    try:
        st = json.loads(srv.r.call('status'))
        if not st['paused']: raise RuntimeError('после загрузки игра не на паузе')
        tick0 = st['tick']
        snap0 = json.loads(srv.r.call('snapshot'))
        sub = json.loads(srv.r.call('submit', hexs(actions)))
        srv.run_ticks(ticks)
        end = json.loads(srv.r.call('end_round'))
        snap1 = json.loads(srv.r.call('snapshot'))
        obs = norm_obs(json.loads(srv.r.call('observe'))) if observe_after else None
        h = srv.r.call('hash')
        sha_out = srv.save_as(save_out)
    finally:
        srv.stop()
    return {'tick0': tick0, 'tick1': snap1['tick'], 'submit': sub, 'observe': obs, 'state_hash': h, 'sha': sha_out,
            'balance': balance(snap0, snap1), 'violations': snap1['violations']}

def _d(a, b):
    return {k: b.get(k, 0) - a.get(k, 0) for k in set(a) | set(b) if b.get(k, 0) != a.get(k, 0)}

def balance(s0, s1):
    """Сверка с нулевым допуском: по каждому предмету Δмир = Δпроизведено − Δпотреблено + Δручной крафт.
    Возвращает словарь расхождений (пустой — сверка прошла)."""
    dw, di, do, dh = _d(s0['world'], s1['world']), _d(s0['item_in'], s1['item_in']), _d(s0['item_out'], s1['item_out']), _d(s0['hand'], s1['hand'])
    out = {}
    for k in set(dw) | set(di) | set(do) | set(dh):
        r = dw.get(k, 0) - (di.get(k, 0) - do.get(k, 0) + dh.get(k, 0))
        if r != 0: out[k] = r
    return out

def s_auto(s0, s1, prices):
    """S_auto в Python (первичный счёт): Σ цена·(Δпроизведено − Δпотреблено) по предметам и жидкостям за окно."""
    s = 0.0
    for kind in ('item', 'fluid'):
        di, do = _d(s0[kind + '_in'], s1[kind + '_in']), _d(s0[kind + '_out'], s1[kind + '_out'])
        for k in sorted(set(di) | set(do)):
            s += prices.get(k, 0) * (di.get(k, 0) - do.get(k, 0))
    return s

def stock_value(world, prices, exclude=None):
    return sum(prices.get(k, 0) * v for k, v in sorted(world.items()) if k not in (exclude or {}))

def window(save_in, ticks, work, strip=False):
    """Окно W на копии сейва: заморозка, (для S′) снятие входных запасов, ticks тиков, снимки до и после."""
    srv = Server(work, save_in, next(PORTS)).start()
    try:
        fr = json.loads(srv.r.call('freeze'))
        st = json.loads(srv.r.call('strip_stock')) if strip else None
        prices = json.loads(srv.r.call('prices'))
        snap0 = json.loads(srv.r.call('snapshot'))
        srv.run_ticks(ticks)
        snap1 = json.loads(srv.r.call('snapshot'))
        lua = json.loads(srv.r.call('score'))
        tot = json.loads(srv.r.call('totals'))
        h = srv.r.call('hash')
    finally:
        srv.stop()
    return dict(queue_empty=fr['queue_empty'], stripped=st and st['removed'], prices=prices, snap0=snap0, snap1=snap1, lua=lua, totals=tot, state_hash=h)

def score_game(save_in, sha_in, ticks, work):
    """Счёт партии (решение совета 24, S′ — редакция до пилота, см. PREREG): S_auto — окно W с заморозкой;
    S′ — то же окно с того же сейва без входных запасов (топливо и выходы остаются). Обе суммы — в Python, сверка с Lua."""
    if sha(save_in) != sha_in: raise RuntimeError('сейв подменён: sha не совпадает с журналом')
    a = window(save_in, ticks, os.path.join(work, 'w'))
    b = window(save_in, ticks, os.path.join(work, 'w_strip'), strip=True)
    sa, sp = s_auto(a['snap0'], a['snap1'], a['prices']), s_auto(b['snap0'], b['snap1'], b['prices'])
    return {'queue_empty': a['queue_empty'], 's_auto': sa, 's_auto_lua': a['lua']['s_auto'], 's_prime': sp, 's_prime_lua': b['lua']['s_auto'],
            'stripped': b['stripped'], 'stock_gain': stock_value(a['snap1']['world'], a['prices']) - stock_value(a['snap0']['world'], a['prices']),
            'balance': balance(a['snap0'], a['snap1']), 'balance_strip': balance(b['snap0'], b['snap1']),
            'violations': a['snap1']['violations'], 'state_hash': a['state_hash'], 'totals': a['totals'], 'deltas': a['lua']['deltas']}

def freeze_window(save_in, sha_in, ticks, save_out, work):
    """Окно W: персонаж заморожен (очередь крафта отменена, ходьба и добыча сброшены), игра идёт ticks тиков.
    S_auto считается в Python по снимкам и сверяется с подсчётом мода; S′ = S_auto − max(0, V(запасы при заморозке) − V(в конце))."""
    if sha(save_in) != sha_in: raise RuntimeError('сейв подменён: sha не совпадает с журналом')
    srv = Server(work, save_in, next(PORTS)).start()
    try:
        fr = json.loads(srv.r.call('freeze'))
        prices = json.loads(srv.r.call('prices'))
        w0 = json.loads(srv.r.call('stock'))
        snap0 = json.loads(srv.r.call('snapshot'))
        srv.run_ticks(ticks)
        snap1 = json.loads(srv.r.call('snapshot'))
        w1 = json.loads(srv.r.call('stock'))
        lua = json.loads(srv.r.call('score'))
        tot = json.loads(srv.r.call('totals'))
        h = srv.r.call('hash')
        sha_out = srv.save_as(save_out)
    finally:
        srv.stop()
    sa = s_auto(snap0, snap1, prices)
    v0, v1 = stock_value(w0, prices), stock_value(w1, prices)
    return {'queue_empty': fr['queue_empty'], 's_auto': sa, 's_auto_lua': lua['s_auto'], 'stock_freeze': v0, 'stock_end': v1,
            's_prime': sa - max(0.0, v0 - v1), 'balance': balance(snap0, snap1), 'violations': snap1['violations'],
            'state_hash': h, 'sha': sha_out, 'totals': tot, 'deltas': lua['deltas']}
