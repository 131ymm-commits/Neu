# Схематичные «скриншоты» Factorio по состоянию игры (RCON) и видео из них (слова автора 06.10.2026:
# «Так же как ты разбираешь видео, ты можешь делать видео из скринов»). Спрайтов игры в серверной сборке нет — рисуем схему сверху.
#   снимок:   /tmp/claude-0/flevenv/bin/python tools/factorio_render.py shot <rcon_port> <out.png> [cx cy half]
#   таймлапс: /tmp/claude-0/flevenv/bin/python tools/factorio_render.py lapse <rcon_port> <папка> <каждые_с_реального_времени> [cx cy half]
#   видео:    /tmp/claude-0/vidvenv/bin/python tools/factorio_render.py video <папка> <out.mp4|out.gif> [кадров/с]
# Цвета: вода — синий, руда — по виду, постройки — по типу, враги — красный, персонаж — белый круг, ленты — жёлтые.
import json, os, sys, time, glob, subprocess
from PIL import Image, ImageDraw, ImageFont
try: FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
except Exception: FONT = None

ORE = {'iron-ore': (90, 110, 140), 'copper-ore': (170, 90, 50), 'coal': (35, 35, 35), 'stone': (150, 135, 100), 'crude-oil': (120, 40, 140), 'uranium-ore': (60, 160, 40)}
ENT = {'transport-belt': (230, 200, 40), 'underground-belt': (230, 200, 40), 'splitter': (230, 200, 40), 'inserter': (200, 160, 60), 'burner-inserter': (200, 160, 60),
       'long-handed-inserter': (200, 120, 60), 'fast-inserter': (80, 160, 220), 'assembling-machine': (90, 150, 200), 'furnace': (230, 120, 40), 'mining-drill': (150, 160, 170),
       'boiler': (200, 80, 60), 'generator': (220, 170, 70), 'offshore-pump': (60, 200, 220), 'pipe': (130, 130, 160), 'pipe-to-ground': (130, 130, 160), 'electric-pole': (160, 110, 60),
       'container': (150, 110, 60), 'lab': (230, 230, 120), 'ammo-turret': (40, 200, 90), 'wall': (200, 200, 200), 'chemical-plant': (120, 200, 120), 'oil-refinery': (180, 120, 200),
       'storage-tank': (130, 130, 200), 'pump': (130, 130, 200), 'rocket-silo': (255, 255, 255), 'radar': (100, 220, 180), 'solar-panel': (40, 60, 120), 'accumulator': (100, 100, 140)}
ENEMY = (230, 30, 30); BG = (58, 54, 48); WATER = (40, 90, 160)

def rc(port):
    import factorio_rcon
    return factorio_rcon.RCONClient('localhost', int(port), 'factorio')

def grab(r, cx, cy, half, static=None):
    a = f'{{{{{cx - half}, {cy - half}}}, {{{cx + half}, {cy + half}}}}}'
    if static is None:   # вода и руда меняются медленно — берём один раз
        q = ('/sc local s = game.surfaces[1] local o = {w = {}, r = {}} '
             f'for _, t in pairs(s.find_tiles_filtered{{area = {a}, name = {{"water", "deepwater", "water-green", "deepwater-green", "water-shallow", "water-mud"}}}}) do o.w[#o.w + 1] = {{t.position.x, t.position.y}} end '
             f'for _, e in pairs(s.find_entities_filtered{{area = {a}, type = "resource"}}) do o.r[#o.r + 1] = {{e.name, math.floor(e.position.x), math.floor(e.position.y)}} end '
             'rcon.print(helpers.table_to_json(o))')
        static = json.loads(r.send_command(q))
    q = ('/sc local s = game.surfaces[1] local o = {e = {}, x = {}, t = game.tick} '
         f'for _, e in pairs(s.find_entities_filtered{{area = {a}, force = "player"}}) do if e.type ~= "character" then local b = e.bounding_box; o.e[#o.e + 1] = {{e.type, b.left_top.x, b.left_top.y, b.right_bottom.x, b.right_bottom.y}} end end '
         f'for _, e in pairs(s.find_entities_filtered{{area = {a}, force = "enemy", type = {{"unit", "turret", "unit-spawner"}}}}) do o.x[#o.x + 1] = {{e.type, e.position.x, e.position.y}} end '
         'local c = storage.agent_characters and storage.agent_characters[1] if c and c.valid then o.c = {c.position.x, c.position.y, c.health} end '
         'rcon.print(helpers.table_to_json(o))')
    return static, json.loads(r.send_command(q))

def draw(static, dyn, cx, cy, half, px=4, title=''):
    S = int(2 * half * px); im = Image.new('RGB', (S, S), BG); d = ImageDraw.Draw(im)
    P = lambda x, y: ((x - (cx - half)) * px, (y - (cy - half)) * px)
    for x, y in static.get('w', []): d.rectangle([*P(x, y), *P(x + 1, y + 1)], fill=WATER)
    for n, x, y in static.get('r', []): d.rectangle([*P(x, y), *P(x + 1, y + 1)], fill=ORE.get(n, (100, 100, 100)))
    for t, x0, y0, x1, y1 in dyn.get('e', []):
        col = ENT.get(t, (180, 180, 180)); d.rectangle([*P(x0 + .1, y0 + .1), *P(x1 - .1, y1 - .1)], fill=col)
    for t, x, y in dyn.get('x', []):
        rr = {'unit-spawner': 2.5, 'turret': 1.2, 'unit': .6}[t] * px; X, Y = P(x, y); d.ellipse([X - rr, Y - rr, X + rr, Y + rr], fill=ENEMY)
    if dyn.get('c'):
        X, Y = P(dyn['c'][0], dyn['c'][1]); d.ellipse([X - 2.5 * px, Y - 2.5 * px, X + 2.5 * px, Y + 2.5 * px], outline=(255, 255, 255), width=2)
    d.text((6, 6), f'{title} tick {dyn.get("t", 0)}  построек {len(dyn.get("e", []))}  врагов {len(dyn.get("x", []))}', fill=(255, 255, 255), font=FONT)
    return im

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd in ('shot', 'lapse'):
        port = sys.argv[2]; out = sys.argv[3]
        rest = sys.argv[5:] if cmd == 'lapse' else sys.argv[4:]
        cx, cy, half = (float(rest[0]), float(rest[1]), float(rest[2])) if len(rest) >= 3 else (0, 0, 128)
        r = rc(port); static, dyn = grab(r, cx, cy, half)
        if cmd == 'shot':
            draw(static, dyn, cx, cy, half).save(out); print(out)
        else:
            os.makedirs(out, exist_ok=True); every = float(sys.argv[4]); k = len(glob.glob(os.path.join(out, 'fr_*.png')))
            while True:
                try:
                    static2, dyn = grab(r, cx, cy, half, static); draw(static, dyn, cx, cy, half, title=os.path.basename(out)).save(os.path.join(out, f'fr_{k:05d}.png')); k += 1
                    if k % 20 == 0: static, _ = grab(r, cx, cy, half)    # руда истощается — обновлять изредка
                except Exception as e:
                    print('ошибка снимка:', e, flush=True); time.sleep(5); r = rc(port)
                time.sleep(every)
    elif cmd == 'video':
        import imageio_ffmpeg
        FF = imageio_ffmpeg.get_ffmpeg_exe(); src, out = sys.argv[2], sys.argv[3]; fps = sys.argv[4] if len(sys.argv) > 4 else '8'
        if out.endswith('.gif'):
            subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-framerate', fps, '-i', os.path.join(src, 'fr_%05d.png'),
                            '-vf', 'scale=512:-1:flags=neighbor,split[a][b];[a]palettegen[p];[b][p]paletteuse', out], check=True)
        else:
            subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-framerate', fps, '-i', os.path.join(src, 'fr_%05d.png'),
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', out], check=True)
        print(out)
