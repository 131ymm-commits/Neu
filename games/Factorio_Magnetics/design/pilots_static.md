# Пилоты и находки: статические тесты (S1–S16, G3)

Дата: 30.09.2026. Сервер Factorio 2.0.77 headless, конфигурации base / bq / be / sa (FINAL_SPEC §11.1).
Файлы: `tools/magnetics-tests/cells/static.lua` (S4, S5, S6 со стороной времени игры, S8, S9, S10, S14, S15, S16, G3),
`tools/magnetics-tests/showroom.lua` (витрина §6.3), `tools/tests.py` (оркестратор; S1, S2, S3, S7, S10, S11, S12, S13,
S4 по выгрузке data.raw и S4 против таблиц FINAL_SPEC.md). Запуск: `python3 tools/tests.py` (около 50 с на 4 ядрах).

Пилоты шли на отдельных прогонах (отдельные ячейки-пилоты в копии стенда в scratchpad), а не в зарегистрированных тестах.

## 1. Пилоты: вопрос, опыт, измерено

| пилот | вопрос | опыт | измерено (base и sa одинаково, если не сказано иное) |
|---|---|---|---|
| PILOT-5 (прототипы) | единицы чисел `prototypes.*` | прочитать ванильные образцы с известными значениями из данных | `energy_usage` AM1 = **1250** (75 кВт → Дж/тик); `get_max_energy_usage()` = 1250; сток AM2 = **83.333** (5 кВт); буфер аккумулятора = **5 000 000** Дж; вход/выход аккумулятора = **5000** Дж/тик (300 кВт); `get_max_power_output()` паровой машины = 15 000 (900 кВт); `get_max_energy_production()` солнечной панели = 1000 (60 кВт); `fuel_value` угля = 4 000 000 Дж; `heating_energy` (sa): пулемётная турель 833.33 (50 кВт), AM2 1666.67 (100 кВт), экспресс-подземка 2500 (150 кВт); `research_unit_energy` automation = **600** (10 с × 60); `resistances.percent` — доля: каменная стена физика 0.20000000298 (20 %, float32) |
| PILOT-5 (EEI) | единицы `LuaEntity.power_usage` | источник `magnetics-test-source` с `power_production = 0` и буфером 1e9 Дж, нагрузка `magnetics-test-load` с `power_usage = 1e6/60`; убыль буфера источника за тики 60…660 | **9 999 999.99998 Дж за 600 тиков** = 1.000 МВт: `power_usage` в Дж/тик |
| PILOT-5 (загрязнение) | как из `emissions_per_joule` получить «в минуту» | калибровка на ванили | потребитель: `epj × energy_usage × 3600` — AM2 **3.0**, каменная печь **2.0** (как в данных). Генератор на топливе: делитель — `max_power_output`, а не топливо: у ванильного `burner-generator` (1 МВт, КПД 0.5, 10 в мин) `epj × 16666.67 × 3600` = **10.0** |
| PILOT-22 | свойства поверхности без планеты | `get_property` для всех `prototypes.surface_property` на `create_surface`, на лаборатории стенда, на Nauvis | новые поверхности: magnetic-field **90**, pressure **1000**, gravity 10, solar-power 100, day-night-cycle 300 (= значения по умолчанию); Nauvis: day-night-cycle 25 200, остальное то же |
| PILOT-1 | грузится ли Magnetics после data.lua Space Age | порядок строк `Loading mod … (data.lua)` в логе sa; выгрузка data.raw sa | в sa: base → elevated-rails → quality → space-age → **magnetics** (тест PILOT-1 в results); `express-*.next_upgrade` остаётся `turbo-*` (S6, S7), `turbo-*.next_upgrade` = маглев |
| PILOT-2 | грузятся и крафтят ли печи-копии как сборочные машины | тип прототипа во всех 4 конфигурациях (S4); витрина: печь на угле с ferrite, индукционная печь на magnet-alloy, 600 тиков | тип `assembling-machine` в base/bq/be/sa; **3 крафта** каждой за 600 тиков (3.2 с на крафт) во всех 4 конфигурациях (тест PILOT-2 в results). Запасной вариант не нужен |
| PILOT-12 (загрузка) | грузится ли `solar_coefficient_property = "magnetic-field"` в base | прочитать прототип | грузится в base/bq/be/sa: свойство `magnetic-field`, день/ночь 1/1, номинал 333.33 Дж/тик = 20 кВт. Масштаб H1/H2 — тест E7 (не эта область) |
| PILOT-13 (загрузка) | отрицательная температура по умолчанию без SA | прочитать прототип | жидкий азот −196 °C в base/bq/be/sa |
| PILOT-16 (часть) | `fixed_recipe` у печи на топливе и у резонатора; поведение без исследования | прочитать прототипы; витрина на силе без исследований (первый прогон) | `fixed_recipe` = magnetics-ferrite / magnetics-flux-crystal-charging; обе машины **работают без исследования рецепта** (status working), машины без `fixed_recipe` — `recipe_not_researched`. Совпадает с API: `disabled_when_recipe_not_researched` «defaults to true if fixed_recipe is not given». Обхода нет: печь и феррит открывает одна T1, резонатор и зарядку — одна T12 |
| PILOT-25 | метит ли планировщик улучшений постройки по связям `next_upgrade` | ячейка S6R: планировщик с 11 отображениями (8 связей §7.2 + стены/ворота внутри Magnetics), `LuaSurface.upgrade_area`; отрицательный контроль AM2 → намоточный станок | все 11 помечены в нужную цель во всех 4 конфигурациях (в sa — с `turbo-*`); AM2 не помечен (отображение принято, но не применено) |

## 2. Факты API, от которых зависят метрики (установлены пилотом)

1. У аккумуляторов `usage_priority = "tertiary"` из данных читается в игре как `"managed-accumulator"` (у ванильного так же). В игре ожидание берётся с ванильного аккумулятора; буквальное `tertiary` проверяется по выгрузке data.raw.
2. Рамки хранятся с шагом 1/256: `collision_box` конденсатора −0.4 читается как −0.3984375. Допуск рамок — 1/256.
3. Ингредиенты рецептов и пакеты технологий движок возвращает в своём порядке (не в порядке данных) — сравнение множеств.
4. У эффекта `nested-result` в игре нет поля `type`; `attack_reaction[i].action` — массив (в описании API — одиночный TriggerItem).
5. `allow_productivity` / `allow_quality` рецепта видны только как `allowed_effects.productivity` / `.quality` (проверено на iron-gear-wheel и stone-furnace).
6. В API времени игры нет: `auto_recycle`, `auto_barrel`, `rotation_speed` турели, `energy_per_shot`, `gui_mode`, `piercing_damage`, `direction_only`, `force_condition`, урон цепи, трассер, `main_product = ""`. Они проверяются по выгрузке data.raw (tests.py, записи «S4 dump §…», S10).
7. У сборочных машин в `crafting_categories` всегда есть `parameters` (движок добавляет сам) — из сравнения исключается.
8. `require` работает только при разборе control.lua, не в обработчиках.
9. `factorio --dump-data` пишет `script-output/data-raw-dump.json` — data.raw после всех стадий всех модов; им заменён временный мод-выгрузчик (S2, S3, S7, S12, S13). `--dump-prototype-locale` с `[general] locale=ru|de` в config.ini даёт имена так, как их видит игра (S11). Немецкие описания игра берёт из английских (измерено).
10. Прогон ячеек: tests.py запускает `--benchmark` с потолком 1 000 000 тиков и останавливает сервер, как только стенд записал `magnetics-done.txt`; знать `check_at` модулей заранее не нужно (сейчас весь стенд кончается на тике 3421).

## 3. Отклонения

**Мод против спецификации: 0** в статической части во всех четырёх конфигурациях (последний прогон: base 2696/0, bq 2711/0, be 2696/0, sa 2810/0 проверок моей области, файлы 721/0).

Что ноль провалов не означает слепоту тестов — отрицательные контроли на испорченных копиях мода (в scratchpad):
- ячейки: HP печи 200→201, электросопротивление ферритовой стены 30→35 %, медный кабель в катушке 4→5, подогрев станка 100→150 кВт (sa), убрана предпосылка repair-pack у T8, убрана связь gate → magnet gate, убрано зеркало бонуса для рельсовой пушки — пойманы все 7 (S4, S5 с достижимостью «mend-coil ← repair-pack», S6, S8, S14);
- Python-часть: правка ванильного AM2, прототип без префикса, опечатка ключа, окрашенные тени, снятый `auto_barrel = false`, удалённая и уменьшенная иконка, удалённый ключ ru и лишний ключ de, SA-имя вне охраны, `rotation_speed` 0.015→0.02 — пойманы все (S2, S3, S5, S7, S10, S11, S12, S13, S4 dump, S8-grep).

**Ошибка общего стенда (не мой файл, `tools/magnetics-tests/lib.lua`, строки 69 и 89 — `L.topup`, `L.drain`):**
`local proto = p[1] or p` падает с `bad argument #2 of 3 to '__index' (string expected, got number)`, когда
`fluidbox.get_prototype(i)` возвращает один `LuaFluidBoxPrototype` (userdata), а не массив. Измерено: падает на
assembling-machine-2, assembling-machine-3 и magnetics-magnetic-separator (копия AM3); работает на chemical-plant и
криокамере (там массив). Задевает любые ячейки, которые кормят жидкостью или снимают жидкость с машин на основе AM2/AM3
(P7 сепаратор, рецепты маглев-лент). Исправление в обеих функциях:
`local proto = (type(p) == "table") and p[1] or p`. В витрине (showroom.lua) это уже сделано локально.

**Риск для E4 / PILOT-18 (не моя область, только наблюдение):** `emissions_per_minute` генератора на топливе движок
делит на `max_power_output` (калибровка на ванильном burner-generator, п. 1). У МГД-генератора `epj` = 100 / (5.4 МВт × 60 с).
Если движок начисляет загрязнение на джоуль сожжённого топлива (6 МВт при полной нагрузке), фактическое будет
100 / 0.9 = **111 в минуту**, а не 100 (§4.4, E4). Решает прогон E4; если так, в spec.py МГД нужно
`emissions_per_minute = 90`, чтобы вышло 100 на 6 МВт топлива.

## 4. Решения, принятые при кодировании ожиданий (для проверки советом)

1. **S9, набор рецептов переработки.** В spec.py списка нет; он выведен в static.lua из правил `quality/prototypes/recycling.lua`
   ([C §11.3]) и §7.5: 31 рецепт по рецептам (катушка, 4 болванки, 26 построек) + самопереработка предметов без своей
   переработки и без `item.auto_recycle = false`: **magnetics-ferrite, magnetics-magnet-alloy, magnetics-flux-rail-slug** —
   итого **34** (в bq и sa совпало). Самопереработка возвращает сам предмет с вероятностью 25 % (как у ванильных пластин),
   кристалла в ней нет — правило S9 выполнено. Если автор не хочет и её, нужно `auto_recycle = False` у этих трёх
   предметов в spec.py (ITEMS/AMMO) — вопрос к автору.
2. **S2, «нет имён из names_base.tsv / names_sa.tsv».** Сравнение идёт со свежей выгрузкой той же конфигурации без мода
   (то же, но без устаревания tsv).
3. **S12, оттенки.** Оттенок каждой постройки берётся из таблиц §4 FINAL_SPEC (у ремонтной катушки — из текста §4.5) и
   дополнительно сверяется с spec.py; «окрашенный нами» лист — лист с этим оттенком. Кроме §11.2 проверено: 0 таких листов
   в пропускаемых поддеревьях §4.1 шаг 7 (circuit_connector, water_reflection, frozen_patch, belt_reader,
   connector_frame_sprites, icons, визуализации с apply_recipe_tint/apply_tint).
4. **S4, два пути к правде.** (а) expected.lua (spec.py); (б) числа, набранные вручную из FINAL_SPEC §2, §4, §11.2 (DOC в
   static.lua) и таблицы §2.1, §2.3, §3.1–§3.3, §5.1, разбираемые tests.py прямо из FINAL_SPEC.md, против чисел,
   прочитанных в игре (magnetics-static-export.json). Расхождений spec.py ↔ FINAL_SPEC не найдено.

## 5. Открытые вопросы

- G3 проверяет только расстановку (как в §11.10); состояния построек витрины пишутся справочно в note записи
  «statuses»: через 600 тиков все машины работают, бур — «waiting_for_space_in_destination» (руда на землю).
- Витрина включает показательные рецепты силе, на которой строит (в тесте — отдельная сила `magnetics-showroom-test`;
  в игре автора — сила игрока). Снимки — только в графическом клиенте (headless: 0, проверено).
- Регистрация консольной команды — 3 строки в `tools/magnetics-tests/control.lua` (после `local L = require("lib")`):
  ```lua
  local showroom = require("showroom")
  commands.add_command("magnetics-showroom", "Magnetics: витрина 26 построек рядом с ванильными основами (FINAL_SPEC §6.3)", function(cmd)
    local p = cmd.player_index and game.get_player(cmd.player_index); local r = showroom.build { player_index = cmd.player_index, force = p and p.force or "player", teleport = true }; (p or game).print("magnetics-showroom: построек " .. r.count .. "/26, основ " .. r.base_count .. "/26, ошибок " .. #r.errors .. ", снимков " .. r.screenshots) end)
  ```
