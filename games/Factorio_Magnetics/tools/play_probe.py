"""Пробник «агент играет сам» (01.10.2026): запускает сервер Factorio в режиме игры (без проверки игроков и без
публикации — auth.factorio.com в сети среды закрыт и не нужен), включает RCON и через него управляет персонажем
без игрока-человека: ходьба, добыча руды руками, ручной крафт. Замер 01.10.2026 (base 2.0.77): прошёл 18 клеток
за 2 с, добыл руду, скрафтил 2 шестерни. Основа для будущего опыта «головы играют», см. NEXT.md.
Запуск: python3 tools/play_probe.py"""
import json, os, socket, struct, subprocess, sys, tempfile, time

FACTORIO = os.environ.get('FACTORIO', '/opt/factorio')
BIN = os.path.join(FACTORIO, 'bin/x64/factorio')
PORT, PW = 27015, 'pw'

def pkt(i, t, body):
    b = body.encode() + b'\x00\x00'
    return struct.pack('<iii', len(b) + 8, i, t) + b

class Rcon:
    """Протокол Source RCON: перед ответом на вход сервер может прислать пустой пакет — читаем до ответа с нашим id."""
    def __init__(self):
        self.s = socket.create_connection(('127.0.0.1', PORT)); self.n = 1
        self.s.send(pkt(1, 3, PW))
        while True:
            i, t, _ = self.recv()
            if t == 2:
                if i == -1: raise RuntimeError('RCON: неверный пароль')
                break
        # первая Lua-команда в сохранении не выполняется: игра только предупреждает, что консольные команды
        # отключают достижения, и ждёт повтора (замер 01.10.2026) — шлём холостую команду
        self.lua('rcon.print("ok")')
    def recv(self):
        n = struct.unpack('<i', self.s.recv(4))[0]; d = b''
        while len(d) < n: d += self.s.recv(n - len(d))
        i, t = struct.unpack('<ii', d[:8])
        return i, t, d[8:-2].decode(errors='replace')
    def lua(self, code):
        self.n += 1
        self.s.send(pkt(self.n, 2, '/sc ' + code))
        while True:
            i, t, body = self.recv()
            if i == self.n: return body.strip()

def start(work, mods=()):
    md = os.path.join(work, 'mods'); os.makedirs(md, exist_ok=True)
    json.dump({'mods': [{'name': 'base', 'enabled': True}] + [{'name': n, 'enabled': False} for n in ('elevated-rails', 'quality', 'space-age')]
               + [{'name': m, 'enabled': True} for m in mods]}, open(os.path.join(md, 'mod-list.json'), 'w'))
    open(os.path.join(work, 'config.ini'), 'w').write(f'[path]\nread-data={FACTORIO}/data\nwrite-data={work}/wd\n')
    ss = json.load(open(os.path.join(FACTORIO, 'data/server-settings.example.json')))
    ss.update(visibility={'public': False, 'lan': False}, require_user_verification=False, auto_pause=False, username='', token='', password='')
    json.dump(ss, open(os.path.join(work, 'ss.json'), 'w'))
    base = [BIN, '-c', os.path.join(work, 'config.ini'), '--mod-directory', md]
    subprocess.run(base + ['--create', os.path.join(work, 's.zip'), '--map-gen-seed', '1'], capture_output=True, check=True)
    p = subprocess.Popen(base + ['--start-server', os.path.join(work, 's.zip'), '--rcon-port', str(PORT), '--rcon-password', PW,
                                 '--server-settings', os.path.join(work, 'ss.json')], stdin=subprocess.PIPE,
                         stdout=open(os.path.join(work, 'server.log'), 'w'), stderr=subprocess.STDOUT)
    for _ in range(60):
        time.sleep(0.5)
        if 'Starting RCON interface' in open(os.path.join(work, 'server.log')).read(): return p
    p.kill(); raise RuntimeError('сервер не поднял RCON: ' + open(os.path.join(work, 'server.log')).read()[-1500:])

def main():
    work = tempfile.mkdtemp(prefix='mgn_play_')
    p = start(work)
    try:
        r = Rcon()
        # участок у точки появления может быть ещё не сгенерирован: сгенерировать до поиска места
        print(r.lua('local S=game.surfaces[1]; S.request_to_generate_chunks({0,0},4); S.force_generate_chunk_requests(); '
                    'local pos=S.find_non_colliding_position("character",{0,0},50,1); '
                    'storage.c=S.create_entity{name="character",position=pos,force="player"}; '
                    'storage.ore=S.find_entities_filtered{type="resource",name="iron-ore",position=pos,radius=300,limit=1}[1]; '
                    'rcon.print("персонаж создан, тик " .. game.tick)'))
        r.lua('storage.x0=storage.c.position.x; storage.c.walking_state={walking=true,direction=defines.direction.east}')
        time.sleep(2)
        print(r.lua('local c=storage.c; c.walking_state={walking=false}; rcon.print(string.format("прошёл %.1f клетки за ~2 с", c.position.x-storage.x0))'))
        print(r.lua('local c=storage.c; local o=storage.ore; c.teleport(c.surface.find_non_colliding_position("character",o.position,5,0.5)); '
                    'c.update_selected_entity(o.position); c.mining_state={mining=true,position=o.position}; rcon.print("копает " .. o.name)'))
        time.sleep(4)
        print(r.lua('rcon.print("руды в инвентаре: " .. storage.c.get_main_inventory().get_item_count("iron-ore"))'))
        r.lua('storage.c.insert{name="iron-plate",count=10}; storage.c.begin_crafting{recipe="iron-gear-wheel",count=2}')
        time.sleep(2.5)
        print(r.lua('rcon.print("шестерён: " .. storage.c.get_main_inventory().get_item_count("iron-gear-wheel") .. ", тик " .. game.tick)'))
    finally:
        p.terminate()

if __name__ == '__main__':
    main()
