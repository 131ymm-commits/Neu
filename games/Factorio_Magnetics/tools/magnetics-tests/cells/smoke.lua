-- Проверка самого стенда: сборщик-2 на шестернях (известно из пилота: 1,5 крафта/с).
return {
  { id = "H0", check_at = 1200,
    setup = function(ctx)
      local o = ctx.origin
      ctx.L.power(ctx.S, o, 20)
      local a = ctx.S.create_entity { name = "assembling-machine-2", position = { o.x + 5.5, o.y + 5.5 }, force = "player", recipe = "iron-gear-wheel" }
      ctx.state.a = a; ctx.state.count = {}
    end,
    tick = function(ctx, t)
      local s = ctx.state
      if t % 30 == 0 then ctx.L.topup(s.a); ctx.L.drain(s.a, s.count) end
      if t == 600 then s.c600 = s.count["iron-gear-wheel"] or 0 end
    end,
    check = function(ctx)
      local s = ctx.state
      ctx.L.drain(s.a, s.count)
      local n = (s.count["iron-gear-wheel"] or 0) - s.c600
      ctx.L.eq("harness", "H0 AM2 gears per 600 ticks", n, 15, 0, 1)
    end },
}
