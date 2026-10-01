"""PLAY-01: схематичное видео партии (вид сверху). У сервера без графики картинки нет, поэтому партия проигрывается
заново с исходного сейва по журналу действий (игра детерминирована — те же хеши, что в живой партии), каждые STEP тиков
снимается состояние (персонаж, постройки и их статус, инвентарь, текущее действие), кадры рисуются PIL и собираются ffmpeg.
   python3 video.py <этап> <цепочка>[,<цепочка>] <out.mp4> [--step 20] [--rounds 1-8]
Две цепочки — два кадра рядом (одно зерно, разные участники). Только чтение: состояние берётся командами в контексте мода."""
import argparse, json, math, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import game
from PIL import Image, ImageDraw, ImageFont

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
PX = 10                     # пикселей на клетку в основном виде
VW, VH = 72, 50             # клеток в основном виде
NAMES = {'A': 'A — одна голова, 1 вызов', 'A2': 'A2 — повтор A', 'B': 'B — одна голова, 4 вызова подряд', 'C': 'C — три роли + мозолистое тело',
         'H': 'H — haiku, 1 вызов', 'D': 'D — роли opus/sonnet/haiku + тело', 'bot': 'бот (порядок постройки)', 'rand': 'случайные действия'}
FRAME_LUA = ('/sc __neu-play__ local c=storage.c local s=game.surfaces.nauvis local o={t=game.tick,x=c.position.x,y=c.position.y,'
             'mi=c.mining_state.mining,cur=storage.cur and storage.cur.i or nil,nx=storage.next,q=c.crafting_queue_size,e={},g={}} '
             'for _,e in pairs(s.find_entities_filtered{force="player"}) do if e.type~="character" then o.e[#o.e+1]={e.name,e.position.x,e.position.y,e.status,e.direction} end end '
             'for _,e in pairs(s.find_entities_filtered{type="item-entity"}) do o.g[#o.g+1]={e.position.x,e.position.y} end '
             'local inv={} for _,it in pairs(c.get_main_inventory().get_contents()) do inv[it.name]=(inv[it.name] or 0)+it.count end o.inv=inv '
             'rcon.print(helpers.table_to_json(o))')
STATUS = {}


def capture(args):
    """Проиграть цепочку и снять кадры; вернуть кадры и статичную карту вокруг пути."""
    stage, ck, step, rounds, port = args
    game.PORTS = iter(range(port, port + 50))
    st = json.load(open(os.path.join(HERE, 'runs', stage, 'state.json')))
    c, cfg = st['chains'][ck], st['cfg']
    work = tempfile.mkdtemp(prefix='vid_')
    srv = game.Server(work, c['init_save'], next(game.PORTS)).start()
    frames = []
    try:
        st_enum = json.loads(srv.r.raw('/sc local t={} for k,v in pairs(defines.entity_status) do t[tostring(v)]=k end rcon.print(helpers.table_to_json(t))'))
        for h in c['hist']:
            if rounds and h['round'] not in rounds:
                srv.r.call('submit', game.hexs(h['actions'])); srv.run_ticks(cfg['round_ticks']); srv.r.call('end_round'); continue
            srv.r.call('submit', game.hexs(h['actions']))
            left = cfg['round_ticks']
            while left > 0:
                n = min(step, left)
                srv.run_ticks(n); left -= n
                f = json.loads(srv.r.raw(FRAME_LUA))
                f['round'] = h['round']
                i = f.get('cur') or f.get('nx')
                f['act'] = h['actions'][i - 1] if i and 0 < i <= len(h['actions']) else None
                f['e'] = [[e[0], e[1], e[2], st_enum.get(str(e[3]), ''), e[4]] for e in (f.get('e') or [])]
                f['g'] = f.get('g') or []
                frames.append(f)
            srv.r.call('end_round')
        xs = [f['x'] for f in frames] + [e[1] for f in frames[-1:] for e in f['e']]
        ys = [f['y'] for f in frames] + [e[2] for f in frames[-1:] for e in f['e']]
        box = [min(xs) - VW / 2 - 4, min(ys) - VH / 2 - 4, max(xs) + VW / 2 + 4, max(ys) + VH / 2 + 4]
        lua = ('/sc local s=game.surfaces.nauvis local a={{%f,%f},{%f,%f}} local o={r={},t={},w={}} '
               'for _,e in pairs(s.find_entities_filtered{area=a,type="resource"}) do o.r[#o.r+1]={e.name,e.position.x,e.position.y} end '
               'for _,e in pairs(s.find_entities_filtered{area=a,type={"tree","simple-entity"}}) do o.t[#o.t+1]={e.position.x,e.position.y,e.type} end '
               'for _,t in pairs(s.find_tiles_filtered{area=a,collision_mask="water_tile"}) do o.w[#o.w+1]={t.position.x,t.position.y} end '
               'rcon.print(helpers.table_to_json(o))') % tuple(box)
        static = json.loads(srv.r.raw(lua))
    finally:
        srv.stop(); shutil.rmtree(work, ignore_errors=True)
    for k in ('r', 't', 'w'):
        if static.get(k) == {}: static[k] = []
    return ck, frames, static, box


ORE = {'iron-ore': (104, 140, 175), 'copper-ore': (200, 117, 51), 'coal': (28, 28, 28), 'stone': (176, 154, 106), 'crude-oil': (60, 30, 60),
       'uranium-ore': (90, 200, 60)}
BLD = {'burner-mining-drill': (85, 85, 85), 'electric-mining-drill': (70, 90, 120), 'stone-furnace': (138, 90, 58), 'iron-chest': (150, 110, 70),
       'wooden-chest': (150, 110, 70), 'transport-belt': (200, 160, 32), 'burner-inserter': (210, 170, 48), 'inserter': (210, 170, 48),
       'boiler': (110, 110, 110), 'steam-engine': (120, 120, 140), 'small-electric-pole': (120, 80, 40), 'lab': (60, 110, 160),
       'assembling-machine-1': (110, 120, 110), 'offshore-pump': (80, 120, 140), 'pipe': (110, 110, 120)}
SIZE = {'burner-mining-drill': (2, 2), 'stone-furnace': (2, 2), 'electric-mining-drill': (3, 3), 'lab': (3, 3), 'assembling-machine-1': (3, 3),
        'assembling-machine-2': (3, 3), 'boiler': (3, 2), 'steam-engine': (3, 5)}
GOOD = (60, 220, 60); BAD = (224, 60, 60); WAIT = (224, 192, 60)


def status_color(s):
    if s in ('working', 'normal'): return GOOD
    if s.startswith('no_fuel') or s.startswith('no_power') or s == 'low_power' or s == 'no_minable_resources': return BAD
    if s: return WAIT
    return (170, 170, 170)


def base_map(static, box):
    W, H = int((box[2] - box[0]) * PX), int((box[3] - box[1]) * PX)
    im = Image.new('RGB', (W, H), (52, 50, 36))
    d = ImageDraw.Draw(im)
    tx = lambda x: (x - box[0]) * PX
    ty = lambda y: (y - box[1]) * PX
    for x, y in static['w']:
        d.rectangle([tx(x), ty(y), tx(x + 1), ty(y + 1)], fill=(31, 74, 110))
    for n, x, y in static['r']:
        col = ORE.get(n, (120, 120, 120))
        d.rectangle([tx(x - 0.5) + 1, ty(y - 0.5) + 1, tx(x + 0.5) - 1, ty(y + 0.5) - 1], fill=col)
    for x, y, t in static['t']:
        r = 0.45 * PX
        d.ellipse([tx(x) - r, ty(y) - r, tx(x) + r, ty(y) + r], fill=(40, 92, 40) if t == 'tree' else (120, 120, 112))
    return im


def act_text(a):
    if not a: return '—'
    k = a.get('a')
    if k == 'walk': return f'идёт к ({a.get("x")}, {a.get("y")})'
    if k == 'mine': return f'копает ({a.get("x")}, {a.get("y")}) ×{a.get("n", 1)}'
    if k == 'craft': return f'крафт {a.get("recipe")} ×{a.get("n", 1)}'
    if k == 'place': return f'ставит {a.get("item")} ({a.get("x")}, {a.get("y")})'
    if k == 'insert': return f'кладёт {a.get("item")} ×{a.get("n", "все")}'
    if k == 'take': return f'берёт {a.get("item")}'
    if k == 'wait': return f'ждёт {a.get("ticks")} тиков'
    return k


def panel(f, base, box, title, trail, fonts):
    W, H = VW * PX, VH * PX
    cx, cy = f['x'], f['y']
    ox, oy = int((cx - box[0] - VW / 2) * PX), int((cy - box[1] - VH / 2) * PX)
    im = base.crop((ox, oy, ox + W, oy + H))
    d = ImageDraw.Draw(im)
    tx = lambda x: (x - box[0]) * PX - ox
    ty = lambda y: (y - box[1]) * PX - oy
    for x, y in f['g']:
        d.rectangle([tx(x) - 2, ty(y) - 2, tx(x) + 2, ty(y) + 2], fill=(230, 230, 230))
    for n, x, y, s, dr in f['e']:
        w, h = SIZE.get(n, (1, 1))
        if dr in (4, 12) and (w, h) != (w, w): w, h = h, w      # восток/запад (2.0: 16 направлений)
        col = BLD.get(n, (150, 150, 150))
        d.rectangle([tx(x - w / 2) + 1, ty(y - h / 2) + 1, tx(x + w / 2) - 1, ty(y + h / 2) - 1], fill=col, outline=status_color(s), width=2)
        if n == 'stone-furnace' and s == 'working':
            d.ellipse([tx(x) - 4, ty(y) - 4, tx(x) + 4, ty(y) + 4], fill=(255, 150, 40))
    if len(trail) > 1:
        d.line([(tx(a), ty(b)) for a, b in trail], fill=(255, 255, 255), width=1)
    r = 6
    d.ellipse([tx(cx) - r, ty(cy) - r, tx(cx) + r, ty(cy) + r], fill=(250, 250, 250), outline=(0, 0, 0), width=2)
    if f.get('mi'):
        d.ellipse([tx(cx) - r - 4, ty(cy) - r - 4, tx(cx) + r + 4, ty(cy) + r + 4], outline=(255, 200, 0), width=2)
    # подписи
    d.rectangle([0, 0, W, 34], fill=(0, 0, 0))
    d.text((10, 6), title, font=fonts['b'], fill=(255, 255, 255))
    hud = Image.new('RGB', (W, 92), (18, 18, 18))
    hd = ImageDraw.Draw(hud)
    t = f['t'] / 60
    hd.text((10, 6), f'раунд {f["round"]}   время {int(t // 60)}:{int(t % 60):02d}   построек {len(f["e"])}   крафт в очереди {f.get("q", 0)}',
            font=fonts['s'], fill=(220, 220, 220))
    hd.text((10, 32), 'сейчас: ' + act_text(f.get('act')), font=fonts['s'], fill=(255, 220, 120))
    inv = sorted((f.get('inv') or {}).items(), key=lambda kv: -kv[1])[:6]
    hd.text((10, 58), 'инвентарь: ' + ', '.join(f'{k} {v}' for k, v in inv), font=fonts['xs'], fill=(180, 200, 220))
    out = Image.new('RGB', (W, H + 92))
    out.paste(im, (0, 0)); out.paste(hud, (0, H))
    return out


def render(stage, cks, out, step, rounds, fps=30):
    with ProcessPoolExecutor(len(cks)) as ex:
        res = list(ex.map(capture, [(stage, ck, step, rounds, 31000 + 100 * i) for i, ck in enumerate(cks)]))
    fonts = {'b': ImageFont.truetype(FONTB, 18), 's': ImageFont.truetype(FONT, 16), 'xs': ImageFont.truetype(FONT, 13)}
    bases = [base_map(s, b) for _, _, s, b in res]
    n = max(len(fr) for _, fr, _, _ in res)
    tmp = tempfile.mkdtemp(prefix='frames_')
    trails = [[] for _ in res]
    for i in range(n):
        tiles = []
        for j, (ck, fr, s, b) in enumerate(res):
            f = fr[min(i, len(fr) - 1)]
            trails[j].append((f['x'], f['y'])); trails[j] = trails[j][-90:]
            part = ck.split('_s')[0]
            tiles.append(panel(f, bases[j], b, f'{NAMES.get(part, part)}   (зерно {ck.split("_s")[1]})', trails[j], fonts))
        W = sum(t.width for t in tiles) + 6 * (len(tiles) - 1)
        im = Image.new('RGB', (W, tiles[0].height), (0, 0, 0))
        x = 0
        for t in tiles: im.paste(t, (x, 0)); x += t.width + 6
        im.save(os.path.join(tmp, f'{i:05d}.png'))
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', os.path.join(tmp, '%05d.png'), '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', '-crf', '24', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return n


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage'); ap.add_argument('chains'); ap.add_argument('out')
    ap.add_argument('--step', type=int, default=20); ap.add_argument('--rounds')
    a = ap.parse_args()
    rounds = None
    if a.rounds:
        lo, hi = map(int, a.rounds.split('-')); rounds = set(range(lo, hi + 1))
    n = render(a.stage, a.chains.split(','), a.out, a.step, rounds)
    print(f'{a.out}: {n} кадров')
