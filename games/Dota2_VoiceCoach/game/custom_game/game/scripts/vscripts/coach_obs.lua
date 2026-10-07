-- Наблюдение героя для его агента Claude (решение Д11). Чистая логика: Дота — через world (coach_world.lua).
--
-- Агент видит то же, что видел бы игрок за этим героем: себя, своих, врагов только в зоне видимости
-- (а невидимых — где и когда видели последний раз), крипов рядом, вышки, приказы тренера, события.
-- Числа округлены: точность до единиц агенту не нужна, а токены стоят денег.

local O = {}
O.CREEPS_R = 1200       -- «крипы рядом»
O.TOWER_R = 1800        -- «вышка рядом»

local function int(v)
  return math.floor((tonumber(v) or 0) + 0.5)
end

local function team_name(team)
  return team == DOTA_TEAM_GOODGUYS and "radiant" or "dire"
end

O.team_name = team_name

local function ability_row(ab, hero, world)
  local i = world.ability_info(ab, hero)
  local row = { name = i.name, lvl = i.level, use = i.behavior }
  if i.ult then row.ult = true end
  if i.level > 0 and i.behavior ~= "passive" then
    row.ready = i.ready and true or false
    if i.cooldown and i.cooldown > 0 then row.cd = int(i.cooldown) end
    if i.mana and i.mana > 0 then row.mana = int(i.mana) end
    if i.range and i.range > 0 then row.range = int(i.range) end
  end
  return row
end

local function near_block(hero, team, world)
  local my = world.pos(hero)
  local enemies = world.lane_creeps(hero, O.CREEPS_R, true)
  local weak = 0
  for _, c in ipairs(enemies) do
    if world.hp(c) <= world.damage(hero, c) then weak = weak + 1 end
  end
  local out = { enemy_creeps = #enemies, weak_enemy_creeps = weak,
                ally_creeps = #world.lane_creeps(hero, O.CREEPS_R, false) }
  local best, bd = nil, O.TOWER_R
  for _, t in ipairs(world.towers) do
    if t.team ~= team and IsValidEntity(t.unit) and t.unit:IsAlive() then
      local d = world.dist(t.pos, my)
      if d < bd then best, bd = t, d end
    end
  end
  if best then out.enemy_tower = string.format("Т%d %s, %d", best.tier, best.lane, int(bd)) end
  return out
end

-- ctx: { clock = игровые часы (с), now = время игры, st = состояние исполнителя, coach = {…}, events = {…},
--        statuses = { [pos] = что делает союзник } }
function O.build(ag, world, ctx)
  local hero, team = ag.hero, ag.team
  local alive = world.alive(hero)
  local st = ctx.st or {}
  local o = { team = team_name(team), pos = ag.pos, hero = world.short(world.name(hero)), clock = int(ctx.clock),
              alive = alive, lvl = world.level(hero), gold = int(world.gold(hero)),
              buyback = { cost = int(world.buyback_cost(hero)), can = world.can_buyback(hero) and true or false } }
  if alive then
    o.hp = { int(world.hp(hero)), int(world.max_hp(hero)) }
    o.mp = { int(world.mana(hero)), int(world.max_mana(hero)) }
    o.where = world.zone(team, world.pos(hero))
    o.attack = { dmg = int(world.attack_damage(hero)), range = int(world.attack_range(hero)) }
    o.near = near_block(hero, team, world)
  else
    o.respawn = int(world.respawn(hero))
  end
  o.stats = world.stats(hero)

  o.abilities = {}
  for _, ab in ipairs(world.abilities(hero)) do o.abilities[#o.abilities + 1] = ability_row(ab, hero, world) end
  o.points = world.ability_points(hero)
  if o.points > 0 then
    o.can_level = {}
    for _, ab in ipairs(world.can_level(hero)) do o.can_level[#o.can_level + 1] = world.ability_name(ab) end
  end
  o.items = {}
  for _, it in ipairs(world.items(hero)) do
    local i = world.ability_info(it.item, hero)
    local row = { name = i.name, slot = it.slot, use = i.behavior }
    if it.slot <= 5 and i.behavior ~= "passive" then row.ready = i.ready and true or false end
    if it.charges and it.charges > 0 then row.charges = it.charges end
    if it.slot >= 6 then row.backpack = true end
    o.items[#o.items + 1] = row
  end
  o.slots_free = world.free_slots(hero)
  o.in_shop = alive and world.in_shop(hero) and true or false

  o.doing = st.status or ""
  local casts = {}
  for _, c in ipairs(st.casts or {}) do casts[#casts + 1] = c.ability .. (c.target ~= "" and (" → " .. c.target) or "") end
  o.queue = { buy = st.buy or {}, level = st.level or {}, cast = casts }
  if st.saving then o.queue.saving_for = st.saving end
  o.notes = st.notes or {}

  local my = alive and world.pos(hero) or world.fountain(team)
  o.allies = {}
  for pos = 1, 5 do
    local ally = (world.agents[team] or {})[pos]
    if ally and ally ~= hero then
      local row = { pos = pos, hero = world.short(world.name(ally)), lvl = world.level(ally), alive = world.alive(ally) }
      if row.alive then
        row.hp = int(world.hp_pct(ally))
        row.where = world.zone(team, world.pos(ally))
        row.d = int(world.dist(world.pos(ally), my))
      end
      row.doing = (ctx.statuses or {})[pos]
      o.allies[#o.allies + 1] = row
    end
  end

  o.enemies, o.missing, o.enemy_team = {}, {}, {}
  for _, e in ipairs(world.enemy_heroes(team)) do
    local name = world.short(world.name(e))
    o.enemy_team[#o.enemy_team + 1] = name
    if world.alive(e) and world.visible(team, e) then
      o.enemies[#o.enemies + 1] = { hero = name, lvl = world.level(e), hp = { int(world.hp(e)), int(world.max_hp(e)) },
                                    where = world.zone(team, world.pos(e)), d = int(world.dist(world.pos(e), my)) }
    else
      local seen = world.last_seen(team, name)
      local row = { hero = name, dead = not world.alive(e) or nil }
      if seen then
        row.seen = world.zone(team, seen.pos)
        row.ago = int((ctx.now or 0) - seen.t)
      end
      o.missing[#o.missing + 1] = row
    end
  end
  table.sort(o.enemies, function(a, b) return a.d < b.d end)

  o.towers = { own = world.tower_tiers(team), enemy = world.tower_tiers(world.other(team)) }
  o.roshan = world.roshan() ~= nil
  o.coach = ctx.coach or {}
  o.events = ctx.events or {}
  return o
end

return O
