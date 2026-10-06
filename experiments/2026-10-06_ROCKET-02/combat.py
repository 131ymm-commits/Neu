# ROCKET-02: бой персонажа (слова автора 06.10: «Учись стрейфоваться персонажем»).
# В FLE нет инструмента стрельбы, а move_to в быстром режиме телепортирует. Здесь — честная механика игры:
# каждый тик персонаж получает walking_state (обычная ходьба) и shooting_state (обычная стрельба из своего оружия своими патронами).
# Режимы: strafe — круг вокруг цели на радиусе r, стреляя по ближайшему врагу; kite — держать дистанцию r от ближайшего врага, отходя;
# при здоровье ниже retreat — отход от цели. Никакой телепортации, урона, бессмертия или выдачи предметов.
import json, time

INSTALL = r'''/sc local _ = 0
local function d8(dx, dy) local a = math.atan2(dx, -dy); return (math.floor(a / (2 * math.pi) * 8 + 0.5) % 8) * 2 end
local function ammo_count(c) local n = 0; local inv = c.get_inventory(defines.inventory.character_ammo); for i = 1, #inv do if inv[i].valid_for_read then n = n + inv[i].count end end; return n end
script.on_nth_tick(1, function(e)
  local s = storage.cb; if not s or not s.active then return end
  local c = s.char
  if not (c and c.valid) then s.active = false; s.result = "персонаж погиб"; return end
  local function stop(why) s.active = false; s.result = why; c.walking_state = {walking = false}; c.shooting_state = {state = defines.shooting.not_shooting} end
  if game.tick >= s.until_tick then return stop("время вышло") end
  local p = c.position; local hp = c.health / c.max_health; s.min_hp = math.min(s.min_hp, hp)
  local tgt = nil
  for _, ty in ipairs(s.prio) do
    local best, bd = nil, 1e9
    for _, e in pairs(c.surface.find_entities_filtered{position = p, radius = s.shoot_range, force = "enemy", type = ty}) do
      local dd = (e.position.x - p.x) ^ 2 + (e.position.y - p.y) ^ 2; if dd < bd then best, bd = e, dd end end
    if best then tgt = best; break end
  end
  if tgt then c.shooting_state = {state = defines.shooting.shooting_enemies, position = tgt.position} else c.shooting_state = {state = defines.shooting.not_shooting} end
  if ammo_count(c) == 0 and not s.no_ammo then s.no_ammo = true; s.retreating = true end
  local rx, ry = p.x - s.cx, p.y - s.cy; local d = math.sqrt(rx * rx + ry * ry) + 1e-6; rx, ry = rx / d, ry / d
  if hp < s.retreat then s.retreating = true end
  local mx, my
  if s.hx and (s.retreating or s.mode == "kite") then
    -- к своим турелям: вектор на точку home плюс боковая составляющая от ближайшего врага
    local hx, hy = s.hx - p.x, s.hy - p.y; local dh = math.sqrt(hx * hx + hy * hy) + 1e-6
    if s.retreating and dh < 3 then return stop(s.no_ammo and "кончились патроны, отошёл к своим" or "отошёл к своим по здоровью") end
    mx, my = hx / dh, hy / dh
    s.homing = dh < 6
    if not s.retreating then
      -- выманивание: идти к цели, пока кусака не окажется в радиусе стрельбы (выстрел её злит); потом к турелям;
      -- у турелей стоять, пока рядом есть кусаки; стало тихо (нет кусак в 30 клетках) — снова идти выманивать
      local near = c.surface.find_entities_filtered{position = p, radius = 17, force = "enemy", type = "unit", limit = 1}[1]
      local any30 = c.surface.find_entities_filtered{position = p, radius = 30, force = "enemy", type = "unit", limit = 1}[1]
      if near then s.lured = true end
      if s.lured then
        if dh < 2.5 then mx, my = 0, 0; if not any30 then s.lured = false end end
      else
        mx, my = -rx, -ry
      end
    end
  elseif s.retreating then
    s.homing = false
    mx, my = rx, ry
    if d > s.r + 25 then return stop(s.no_ammo and "кончились патроны, отошёл" or "отошёл по здоровью") end
  elseif s.mode == "kite" and tgt then
    local ex, ey = p.x - tgt.position.x, p.y - tgt.position.y; local de = math.sqrt(ex * ex + ey * ey) + 1e-6
    local k = (s.r - de) / s.r
    mx, my = ex / de * k - ey / de * s.side * 0.7, ey / de * k + ex / de * s.side * 0.7
  else
    local k = (s.r - d) / s.r * 2
    mx, my = -ry * s.side + rx * k, rx * s.side + ry * k
  end
  -- рыба: при здоровье ниже fish_hp съесть сырую рыбу (лечит 80, у рыбы своя перезарядка)
  if hp < s.fish_hp and game.tick >= (s.fish_next or 0) then
    local m = c.get_main_inventory()
    if m.get_item_count("raw-fish") > 0 and c.cursor_stack and not c.cursor_stack.valid_for_read then
      local ok = pcall(function() c.cursor_stack.set_stack{name = "raw-fish", count = 1}; m.remove{name = "raw-fish", count = 1}; c.use_from_cursor(c.position) end)
      if c.cursor_stack.valid_for_read then m.insert(c.cursor_stack); c.cursor_stack.clear() else s.fish = (s.fish or 0) + 1 end
      s.fish_next = game.tick + 30
    end
  end
  -- рывки у червей и плевак (worm wiggle): внутри 27 клеток от червя или рядом с плевакой — wig_on тиков идти, wig_off стоять/менять сторону
  if s.wiggle > 0 then
    local danger = c.surface.count_entities_filtered{position = p, radius = 27, force = "enemy", type = "turret"} > 0
      or c.surface.count_entities_filtered{position = p, radius = 16, force = "enemy", name = {"small-spitter", "medium-spitter", "big-spitter", "behemoth-spitter"}} > 0
    if danger then
      local ph = game.tick % s.wiggle
      if ph >= s.wiggle - s.wig_off then
        if (math.floor(game.tick / s.wiggle) % 2) == 0 then mx, my = 0, 0 else mx, my = -my, mx end
      end
    end
  end
  -- застревание (деревья, скалы, постройки): за 10 тиков сдвинулся меньше 0,3 — сменить сторону обхода и на 30 тиков отвернуть на 90°
  if game.tick % 10 == 0 then
    if s.lx and not s.idle and not s.homing and (p.x - s.lx) ^ 2 + (p.y - s.ly) ^ 2 < 0.09 then s.side = -s.side; s.turn_until = game.tick + 30; s.stuck = (s.stuck or 0) + 1 end
    s.lx, s.ly = p.x, p.y
  end
  if s.turn_until and game.tick < s.turn_until and not s.homing then mx, my = -my * s.side, mx * s.side end
  s.idle = (mx == 0 and my == 0)
  if s.idle then c.walking_state = {walking = false} else c.walking_state = {walking = true, direction = d8(mx, my)} end
  if game.tick % 30 == 0 then
    local left = c.surface.count_entities_filtered{position = {s.cx, s.cy}, radius = s.clear_radius, force = "enemy", type = {"unit", "turret", "unit-spawner"}}
      + c.surface.count_entities_filtered{position = p, radius = 25, force = "enemy", type = {"unit", "turret", "unit-spawner"}}
    if left == 0 then return stop("зачищено") end
  end
end)
rcon.print("ok")'''

AC = 'local function ac(c) local n = 0; local inv = c.get_inventory(defines.inventory.character_ammo); for i = 1, #inv do if inv[i].valid_for_read then n = n + inv[i].count end end; return n end '

def lua_char():
    return 'local c = storage.agent_characters and storage.agent_characters[1]'

def arm(rcon):
    """Переложить оружие и патроны из основного инвентаря в слоты оружия (то, что игрок делает руками)."""
    q = '/sc ' + lua_char() + r''' local m = c.get_main_inventory(); local g = c.get_inventory(defines.inventory.character_guns); local a = c.get_inventory(defines.inventory.character_ammo)
for _, n in pairs({"submachine-gun", "pistol"}) do local k = m.get_item_count(n); if k > 0 and g.can_insert{name = n, count = 1} then local ins = g.insert{name = n, count = 1}; if ins > 0 then m.remove{name = n, count = ins} end end end
for _, n in pairs({"piercing-rounds-magazine", "firearm-magazine"}) do local k = m.get_item_count(n); if k > 0 then local ins = a.insert{name = n, count = k}; if ins > 0 then m.remove{name = n, count = ins} end end end
local s = "" for i = 1, #g do if g[i].valid_for_read then s = s .. g[i].name .. " " end end; s = s .. "| " for i = 1, #a do if a[i].valid_for_read then s = s .. a[i].name .. "x" .. a[i].count .. " " end end; rcon.print(s)'''
    return rcon.send_command(q).strip()

def scan(rcon, x=None, y=None, radius=60):
    """Враги в радиусе: гнёзда, черви, кусаки — с координатами (как на карте игрока)."""
    pos = f'{{{x}, {y}}}' if x is not None else 'c.position'
    if rcon.send_command('/sc ' + lua_char() + ' rcon.print((c and c.valid) and "1" or "0")').strip() != '1':
        return dict(me=None, health=0, enemies=[], error='персонаж мёртв')
    q = '/sc ' + lua_char() + f''' local o = {{}} for _, e in pairs(c.surface.find_entities_filtered{{position = {pos}, radius = {radius}, force = "enemy", type = {{"unit", "turret", "unit-spawner"}}}}) do o[#o + 1] = {{name = e.name, x = math.floor(e.position.x * 10) / 10, y = math.floor(e.position.y * 10) / 10, hp = math.floor(e.health)}} end
rcon.print(helpers.table_to_json({{me = c.position, health = c.health, enemies = o}}))'''
    return json.loads(rcon.send_command(q).strip())

def fight(rcon, cx, cy, r=20, mode='strafe', seconds=30, retreat=0.4, side=1, clear_radius=None, shoot_range=None, priority=None, home=None, wiggle=24, fish_hp=0.5):
    """Бой: персонаж ходит (strafe — по кругу вокруг (cx,cy) радиусом r; kite — держит дистанцию r от ближайшего врага) и стреляет.
    seconds — игровых секунд; retreat — доля здоровья для отхода; side — 1 по часовой, -1 против;
    home — {x, y} своих турелей: kite и отход ведут туда; wiggle — период рывков у червей в тиках (0 — без рывков); fish_hp — доля здоровья, ниже которой есть рыбу;
    priority — порядок целей по типам, по умолчанию ["unit", "turret", "unit-spawner"] (кусаки, черви, гнёзда)."""
    prio = [t for t in (priority or ['unit', 'turret', 'unit-spawner']) if t in ('unit', 'turret', 'unit-spawner')] or ['unit', 'turret', 'unit-spawner']
    r = max(4.0, min(float(r), 40.0)); seconds = max(1.0, min(float(seconds), 180.0)); retreat = max(0.05, min(float(retreat), 0.95))
    clear_radius = float(clear_radius or r + 10); shoot_range = float(shoot_range or 30)
    homelua = f'hx = {float(home["x"])}, hy = {float(home["y"])},' if home else ''
    rcon.send_command(INSTALL)
    pre = scan(rcon, cx, cy, clear_radius)
    q = '/sc ' + AC + lua_char() + f''' local g = c.get_inventory(defines.inventory.character_guns); local has = false; for i = 1, #g do if g[i].valid_for_read then has = true end end
if not has then rcon.print("нет оружия в слотах — вызови arm") return end
storage.cb = {{active = true, char = c, cx = {cx}, cy = {cy}, r = {r}, mode = "{'kite' if mode == 'kite' else 'strafe'}", side = {1 if side >= 0 else -1}, retreat = {retreat},
  clear_radius = {clear_radius}, shoot_range = {shoot_range}, wiggle = {int(max(0, min(int(wiggle), 120)))}, wig_off = {max(1, int(wiggle) // 3)}, fish_hp = {max(0.0, min(float(fish_hp), 0.95))}, {homelua} prio = {{{', '.join(repr(t).replace(chr(39), chr(34)) for t in prio)}}}, until_tick = game.tick + {int(seconds * 60)}, min_hp = 1, ammo0 = ac(c), hp0 = c.health}}
rcon.print("start")'''
    st = rcon.send_command(q).strip()
    if st != 'start': return dict(error=st)
    t0 = time.time()
    while time.time() - t0 < 300:
        time.sleep(0.5)
        done = rcon.send_command('/sc rcon.print(storage.cb.active and "1" or "0")').strip()
        if done == '0': break
    else:
        rcon.send_command('/sc storage.cb.active = false')
    res = rcon.send_command('/sc ' + AC + 'local s = storage.cb; local c = s.char; local alive = c and c.valid; rcon.print(helpers.table_to_json({result = s.result or "прервано по времени", min_health_frac = s.min_hp, '
                            'stuck_events = s.stuck or 0, fish_eaten = s.fish or 0, health = alive and c.health or 0, ammo_used = alive and (s.ammo0 - ac(c)) or s.ammo0, ammo_left = alive and ac(c) or 0}))').strip()
    out = json.loads(res)
    post = scan(rcon, cx, cy, clear_radius) if 'погиб' not in out['result'] else dict(enemies=[])
    kinds = lambda L: {n: sum(1 for e in L if e['name'] == n) for n in sorted({e['name'] for e in L})}
    out.update(enemies_before=kinds(pre['enemies']), enemies_after=kinds(post['enemies']), position=post.get('me'))
    return out
