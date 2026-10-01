-- Обёртка модуля mend_tests.lua (ремонтная катушка, §11.7, R1–R11 и пилоты 10/19/24) под интерфейс ячеек стенда.
-- Модулю нужен свой квадрат 512×512 и запуск из on_init, поэтому участок — отдельный, вдали от сетки ячеек
-- (ячейки ревью 01.10.2026 — на своей поверхности "mend-review", её создаёт сам модуль).
-- kind записи (lib.lua L.check): "mod" по умолчанию, "harness" — самопроверка стенда и пилоты движка.
local M = require("mend_tests")
local ORIGIN = { x = 1024, y = 1024 }

local function mctx(ctx)
  storage.mend = storage.mend or { data = {}, results = {} }
  return {
    surface = ctx.S, origin = ORIGIN, data = storage.mend.data, source = "magnetics-test-source",
    config_changed = storage.config_changed == true,
    check = function(group, name, ok, got, expected, note, kind)
      local r = storage.mend.results
      r[#r + 1] = { group = group, name = name, ok = ok and true or false, got = got, expected = expected, note = note,
                    kind = kind }
    end,
  }
end

local function flush(ctx)
  for _, r in ipairs(storage.mend.results) do ctx.L.check(r.group, r.name, r.ok, r.got, r.expected, r.note, r.kind) end
  storage.mend.results = {}
end

return {
  { id = "MEND", check_at = M.END_TICK,
    init = function(ctx)
      ctx.S.request_to_generate_chunks({ ORIGIN.x + 256, ORIGIN.y + 256 }, 9)
      ctx.S.force_generate_chunk_requests()
      M.setup(mctx(ctx))
    end,
    tick = function(ctx, rel)
      local c = mctx(ctx)
      M.tick(c, game.tick)
      if game.tick == M.END_TICK then M.check(c) end
    end,
    check = function(ctx) flush(ctx) end },
}
