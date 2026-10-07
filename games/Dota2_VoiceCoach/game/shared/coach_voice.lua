-- Голос агента: короткие ответы тренеру с характером. Чистый Lua 5.1 / LuaJIT.
--
-- Тон берётся из профиля игрока (digitizer/twin/agent_params.py → voice.tone):
--   calm   — спокойный (по умолчанию);
--   hype   — заводной (высокая агрессия);
--   grumpy — ворчун (низкое послушание).
-- Выбор фразы детерминирован номером команды (seq): один и тот же приказ — один ответ,
-- соседние приказы — разные слова. Фразы придуманы Claude; правятся здесь же.

local V = {}

V.ACK = {
  calm = {
    farm = { "Фармлю", "Пошёл фармить" },
    push = { "Иду пушить", "Давлю линию" },
    defend = { "Иду защищать", "Дефаю" },
    gank = { "Иду на ганг", "Пошёл ганкать" },
    group = { "Иду к своим", "Собираюсь" },
    roshan = { "Иду на Рошана", "На Рошана, понял" },
    tormentor = { "Иду на Торментора" },
    smoke = { "Смок, иду", "Под смоком иду" },
    retreat = { "Отхожу", "Понял, назад" },
    focus = { "Бью цель", "Фокус, понял" },
    engage = { "Захожу", "Начинаю" },
    hold = { "Жду", "Стою, жду" },
    split = { "Сплитую", "Ушёл в сплит" },
    ward = { "Иду ставить вард", "Поставлю вард" },
    stack = { "Стакну", "Стакаю" },
    follow = { "Иду с тобой", "Иду рядом" },
    move = { "Иду", "Двигаюсь" },
    save = { "Иду спасать", "Спасаю" },
    save_ult = { "Держу ульту" },
    buy = { "Куплю", "Собираю" },
    buyback = { "Выкупаюсь" },
    use_ult = { "Ульту понял" },
    use_item = { "Понял" },
    tp = { "Тпшусь", "Тп, иду" },
    free = { "Играю сам" },
    cancel = { "Отбой" },
    default = { "Понял", "Принял" },
  },
  hype = {
    farm = { "Сейчас нафармлю", "Фарм — моё всё" },
    push = { "Ломаем!", "Погнали пушить" },
    gank = { "Сейчас убьём", "Иду убивать" },
    roshan = { "Рошан наш!", "Забираем Рошана" },
    retreat = { "Ладно, отхожу", "Уходим" },
    focus = { "Он труп", "Валю его" },
    engage = { "Го!", "Захожу первым" },
    default = { "Го!", "Сделаю" },
  },
  grumpy = {
    farm = { "Ну фармлю", "Опять фарм" },
    push = { "Ладно, пушу", "Иду, иду" },
    roshan = { "Ну пошли на Рошана", "Опять Рошан…" },
    retreat = { "Отхожу, отхожу" },
    group = { "Ладно, иду" },
    default = { "Ладно", "Ну ок" },
  },
}

V.REFUSE = {
  dead = "Я мёртв, приду после возрождения",
  dead_s = "Я мёртв, ещё %d с",
  no_buyback = "Нет байбэка",
  alive = "Я жив, байбэк не нужен",
  ult_cd = "Ульта в откате, %d с",
  no_ult = "Нет ульты",
  busy = "Через %d с, дофармлю",
  short_gold = "Куплю, не хватает %d золота",
  cant = "Не могу",
}

function V.tone(persona)
  if type(persona) == "table" and V.ACK[persona.tone or ""] then return persona.tone end
  return "calm"
end

local function pick(list, seed)
  if type(list) ~= "table" or #list == 0 then return nil end
  local i = (math.floor(tonumber(seed) or 0) % #list) + 1
  return list[i]
end

-- ответ «принято» на действие
function V.ack(persona, action, seed)
  local t = V.ACK[V.tone(persona)]
  return pick(t[action], seed) or pick(V.ACK.calm[action], seed) or pick(t.default, seed)
    or pick(V.ACK.calm.default, seed)
end

-- отказ или оговорка: kind из V.REFUSE, value — число для %d
function V.refuse(kind, value)
  local f = V.REFUSE[kind] or V.REFUSE.cant
  if string.find(f, "%%d") then
    return string.format(f, math.max(0, math.floor((tonumber(value) or 0) + 0.5)))
  end
  return f
end

return V
