# 04. ИИ героев: микро и макро агента, стиль игрока

Дата: 06.10.2026. Автор: Claude (агент-исследователь). Тема: как сделать, чтобы каждый из 5 агентов сам играл героем (ласт-хиты, кайт, скиллы, отступление, покупки), а человек задавал голосом только намерение, и как подмешать к этому «стиль» оцифрованного игрока.

**Статусы фактов** (в скобках после факта): **ПТ** — «полный текст» (я открыл страницу или файл); **ПТ\*** — «полный текст» копии на GitHub, оригинал недоступен; **С** — «сниппет» (только выдача поиска); **П** — «по памяти». Пометка **вывод** означает моё заключение из перечисленных фактов. Это не факт из источника. Ссылки вида [S5] ведут в список источников в конце.

**Ограничения поиска.** Прокси закрыл developer.valvesoftware.com, docs.moddota.com, moddota.com, steamcommunity.com, arxiv.org (и зеркала: export.arxiv, alphaxiv, huggingface, semanticscholar, openreview), cdn.openai.com, en.wikipedia.org, habr.com, reddit.com, leagueoflegends.com, gameaipro.com. Поэтому вики Valve и статья OpenAI Five читались по копиям на GitHub (ПТ\*). Steam и arXiv дали только сниппеты. Под конец работы закончился общий лимит WebSearch. Последние проверки делались только через GitHub.

---

## Краткий итог

1. API ботов Valve (Lua, с 7.00, декабрь 2016 (С)) устроен как утилитарный ИИ в три уровня: командные «желания» → режимы с `GetDesire()` → действия. Любой уровень можно переопределить файлом (ПТ\*). Скрипты видят только то, что видит команда; приказы отдаются только своим юнитам (ПТ\*).
2. Valve API почти не развивает. Новые боты из Workshop запускаются только в лобби «Local Host» или как «Local Dev Script» (ПТ [S5][S7]). Обновления Dota 2024–2026 несколько раз ломали загрузку и поведение скриптов (ПТ, issues OHA [S4]). Встроенная C++-логика помечена флагом `BotImplemented=1` только у 39 из 127 героев (ПТ, мой подсчёт [S46]).
3. Лучшая открытая база — **Open Hyper AI** (MIT, 127 героев, патч 7.41/7.41a) (ПТ). Живы также Tinkering ABout (127 героев, 7.41f, коммит 26.09.2026, **без лицензии**) и Fretbots (MIT, vscripts-надстройка) (ПТ). VUL-FT (MIT, full takeover) заброшен с 2023 года (ПТ). У OHA в предках есть проект под GPL-3 и проекты без лицензии, так что копировать его код в свой продукт рискованно (вывод).
4. Lua-скрипты из папки `bots` в опубликованной кастомке, по единственному найденному свидетельству, не работают: только при локальном запуске аддона, источник 2017 года (ПТ [S15]). Встроенные боты Valve в кастомке возможны только со «стандартными героями на карте dota» (ПТ [S12]). Поштучно ими не управляют, есть лишь грубые рычаги вроде `SetBotDifficulty` и `SetBotsMaxPushTier` (ПТ [S13]).
5. Для итоговой кастомки нужен **свой ИИ на vscripts**: бот-игроки через `GameRules:AddBotPlayerWithEntityScript` и приказы `ExecuteOrderFromTable`. Так делают Valve в обучении NPE 2019 (`ai_laning.lua`), x_hero_siege (2026, около 23 тыс. строк) и dota_duel (Apache-2.0) (ПТ).
6. Обучать RL «как OpenAI Five» без кластера невозможно: 770±50 PFlops/s-days, 51 200 CPU, 17 героев из 117 (ПТ\*). Реально подгонять параметры стиля по реплеям и, возможно, имитировать макро (вывод).
7. LLM годится только для макро и общения (разбор команды, план, реплики). Реальное время она не держит: Cradle ставит RDR2 на паузу на время ответа GPT-4o, игра TextStarCraft II идёт около 7 часов, LLM-PySC2 для отладки без ключа эмулирует ответ модели в 5 с (ПТ). Микро — только скрипт: OpenAI Five действует каждый 4-й кадр, реакция в среднем 217 мс (ПТ\*).
8. «Стиль игрока» хорошо ложится на параметры слоёв. Есть готовые образцы: skill×type у Valve в `ai_laning.lua` (ПТ), 53 параметра «сложности» в x_hero_siege (реакция, точность, лимит приказов, агрессия, отступление) (ПТ) и задержки и шум ласт-хита в уровнях сложности Valve (ПТ\*).
9. Канал «vscripts → bot scripts» общей памяти не имеет: это разные Lua-окружения (ПТ, вывод). Кандидаты: модификаторы со stack count, чат, пинги, localhost HTTP, файлы. **Ни один не проверен в паре «Lua-код кастомки → бот»**, нужен пилот (раздел 7).

---

## 1. API ботов Valve

### 1.1 Устройство

Уровни принятия решений (ПТ\* [S1]):
- **Team Level**: «how much the overall team wants to push each lane, defend each lane, farm each lane, or kill Roshan». Это желания, а не приказы.
- **Mode Level**: «Modes are the high-level desires that individual bots are constantly evaluating, with the highest-scoring mode being their currently active mode».
- **Action Level**: «moving to a location, or attacking a unit, or using an ability, or purchasing an item».

Скрипты лежат в `game/dota/scripts/vscripts/bots`, в Workshop загружается эта папка (ПТ\* [S1]). Вызовы привязаны к именам файлов:

| Файл | Функции | Частота (по вики) | Что переопределяет |
|---|---|---|---|
| `bot_generic.lua` / `bot_<hero>.lua` | `Think()`; `MinionThink(hMinionUnit)` | «every frame» | Полный захват: «no team-level or mode-level thinking will happen» (ПТ\*) |
| `mode_<mode>_generic.lua` / `mode_<mode>_<hero>.lua` | `GetDesire()`, `OnStart()`, `OnEnd()`, `Think()` | `GetDesire` «every ~300ms», `Think` «every frame while this is the active mode» | Один режим из 21: laning, attack, roam, retreat, secret_shop, side_shop, rune, push_tower_top/mid/bot, defend_tower_top/mid/bot, assemble, team_roam, farm, defend_ally, evasive_maneuvers, roshan, item, ward (ПТ\*) |
| `ability_item_usage_generic.lua` / `_<hero>.lua` | `AbilityUsageThink`, `ItemUsageThink`, `CourierUsageThink`, `BuybackUsageThink`, `AbilityLevelUpThink` | «every frame» | Нереализованное падает в C++ (ПТ\*) |
| `item_purchase_generic.lua` / `_<hero>.lua` | `ItemPurchaseThink()` | «every frame» | Покупки (ПТ\*) |
| `team_desires.lua` | `TeamThink`, `UpdatePushLaneDesires`, `UpdateDefendLaneDesires`, `UpdateFarmLaneDesires`, `UpdateRoamDesire` (желание + цель), `UpdateRoshanDesire` | «every frame» | Командные желания (ПТ\*) |
| `hero_selection.lua` | `Think`, `UpdateLaneAssignments`, `GetBotNames` | «every frame» / один раз | Пик и линии (ПТ\*) |

- Пример Valve (файлы игры): `team_desires.lua` возвращает константы `{0.0, 0.5, 1.0}`, Roam — `{0.5, GetTeamMember(1)}`. В `ability_item_usage_lina.lua` для каждого скилла есть функция `Consider*()`, которая возвращает (желание, цель), и выбирается максимум. В `item_purchase_lina.lua` стоит список предметов и `SetNextItemPurchaseValue` (ПТ [S2]).
- Доступно также: `GetUnitPotentialValue` — вероятность героя в тумане, 0–255, заливка со скоростью героя (ПТ\*); `GetHeroLastSeenInfo`, `GetIncomingTrackingProjectiles`, `GetExtrapolatedLocation`, `FindAoELocation`, `GetEstimatedDamageToTarget`, «Hero Power» (ПТ\*). Во встроенном дампе API есть `GetLinearProjectiles`, `AddAvoidanceZone`, `GeneratePath`, `GetIncomingTeleports` (ПТ [S47], дата дампа неизвестна).
- Отладка: `dota_bot_debug_team` (желания, режимы, время исполнения), `dota_bot_select_debug` и др. (ПТ\*).
- Lua в ботах — 5.1 / LuaJIT 2.0.4 (ПТ [S25], 2018–2019).
- Счёт частот (вывод): движок идёт с 30 кадрами в секунду (ПТ\* [S28]), значит `Think` вызывается примерно 30 раз в секунду, а `GetDesire` по вики — примерно 3 раза. В справке OHA написано иначе: «GetDesire() is called every frame for ALL modes» (ПТ [S3]). Противоречие не проверено, нужен лог.

### 1.2 Что можно и чего нельзя

- Нельзя видеть юнитов в тумане и командовать чужими юнитами (ПТ\*): «units in FoW can't be queried, commands can't be issued to units the script doesn't control».
- `GetNearbyHeroes/Creeps/Towers…`: «nRadius must be less than 1600» (ПТ\*).
- Боты под полным захватом всё равно получают задержки своей сложности (ПТ\*): «Bots that have been completely taken over still respect the difficulty modifiers».
- `Action_MoveToLocation` квантуется и не двигает героя на короткие дистанции, примерно меньше 250 юнитов (ПТ [S25], 2018–2019). Для кайта это важно (вывод).
- `package.path` не монтирует ничего вне `vscripts` (ПТ [S25]). `CreateRemoteHTTPRequest` не работал при выключенном Steam (ПТ [S25]). По справке OHA, `CreateHTTPRequest` ходит только на localhost (ПТ [S3], не проверял).
- Full takeover не подбирает часть рун (нижние водные и речные bounty). Обходится частичным захватом (ПТ [S7], VUL-FT 2023).
- Девять героев «сломаны со стороны Valve»: Muerta, Marci, медведь Lone Druid, Primal Beast, Dark Willow, Elder Titan, Hoodwink, IO, Kez (ПТ, `BuggyHeroesDueToValveTooLazy` в OHA [S3]). У ryndrb в том же списке 8 героев (ПТ [S5]).
- Встроенная C++-логика: в файлах героев флаг `"BotImplemented" "1"` есть у 39 героев, у Hoodwink, Kez, Marci, Muerta и Riki стоит явный `0` (ПТ, мой подсчёт по снимку игры от 05.10.2026 [S46]). Вывод: это список героев, для которых у Valve есть своя логика. Документации о смысле флага не нашёл.

### 1.3 Уровни сложности Valve: что именно меняется (ПТ\* [S1])

| Уровень | Изменения |
|---|---|
| Passive | Не использует способности, предметы и курьер; всегда в режиме лайнинга; оценка момента ласт-хита случайно сдвигается на 0.4 с (по союзным крипам — на 0.2 с) |
| Easy | Задержка способностей и предметов 0.5–1.0 с; каждые 8 с — запрет на 6 с; после каждого применения — запрет на 6 с; шум ласт-хита 0.4 с, денай 0.2 с |
| Medium | Задержка 0.3–0.6 с; каждые 10 с — запрет на 3 с; после применения — запрет на 3 с; шум 0.2 / 0.1 с |
| Hard | Задержка 0.1–0.2 с |
| Unfair | Задержка 0.075–0.15 с; +25 % к опыту и золоту |
| New Player | На вики описания нет |

Сложностью можно управлять и из vscripts: обучение Valve вызывает `hero:SetBotDifficulty(n)` на лету для каждого героя (ПТ [S13]).

### 1.4 Поддерживает ли Valve API в 2024–2026

- Официальных изменений API за 2024–2026 не нашёл (поиск ограничен, см. «Что не удалось выяснить»).
- Ручная установка вместо Workshop:
  - ryndrb (README, коммит 26.09.2026): «Since Valve hasn't fixed the workshop bug yet, bot scripts … are only playable through `Local Host` lobby». Там же: «Valve making bot scripts run on their servers again is the ultimate solution» (ПТ [S5]).
  - VUL-FT (2023): «will not work via subscription. It will revert to the default bots» (ПТ [S7]).
  - Steam: «Valve allegedly only supports the top 3 bot AI scripts in the workshop» (С [S11]).
- Поломки после обновлений Dota (issues OHA, ПТ [S4]):

  | Issue | Дата | Что сломалось |
  |---|---|---|
  | #18 | 09.09.2024 | Скрипт не находится |
  | #32 | 08.10.2024 | 7.37d: сломался `require` |
  | #53 | 19.10.2024 | Пик случайный «since 7.37» |
  | #93 | 03.10.2025 | Руны «since last update» |
  | #102 | 14.11.2025 | Имена и бан-лист |
  | #104 | 21.11.2025 | «almost indistinguishable from the default bots» |
  | #115 | 23.12.2025 | «stopped working after DOTA was updated» |
  | #153 | 25.06.2026 | «A DOTA update has made this script no longer function» |

- PhalanxBot (ноябрь 2024): обновление «Monster Hunter» «broke a couple of functions within the bot API, causing bots to freeze» (С [S11]).
- Вывод: API заморожен. Каждый патч Dota может сломать бота, и починка ложится на авторов скриптов.

---

## 2. Открытые наборы ботов 2023–2026

| Проект | Лицензия | Герои / патч | Свежесть | Сила (что заявлено) | Годится ли как основа нашего микро |
|---|---|---|---|---|---|
| **Open Hyper AI (OHA)**, forest0xia [S3] | MIT, © 2024 Mingyou Xia (ПТ) | 127 героев, 7.41/7.41a (ПТ) | Последний коммит в `main` — 03.04.2026 (ПТ); issues до 06.2026 (ПТ) | Только качественно: лейнят, ганкают, пушат, Рошан; режим FretBots даёт «unfair bonuses» (ПТ). Сравнений с людьми по MMR нет | Для прототипа — да, как запускаемый движок. Для копирования кода — осторожно: в кредитах Ranked Matchmaking AI (GPL-3.0), Tinkering About (без лицензии), New Beginner AI (ПТ) (вывод: чистота MIT не гарантирована). Проект ведётся с Claude Code (ПТ) |
| **Tinkering ABo(u)t**, ryndrb [S5] | Файла лицензии нет (ПТ: LICENSE/COPYING — 404) | 127/127, 8 «bugged due to Valve», 7.41f (ПТ) | Коммит 26.09.2026 (ПТ) | Автор: «if there are multiple decent human players vs bots, it won't really matter much» (ПТ) | Код без лицензии брать нельзя, все права у автора (П). Только как образец |
| **Fretbots**, fretmute [S6] | MIT, © 2021 Jason Cross (ПТ) | Не бот, а vscripts-надстройка: бонусы GPM/XPM по ролям, бонусы при смерти, нейтралки, голосование сложности 0–10; нужны cheats и `script_reload_code fretbots` (ПТ) | Коммит 10.03.2025 (ПТ) | Сложность за счёт ресурсов (ПТ) | Образец связки «vscripts рядом с ботами» |
| **VUL-FT**, Yewchi [S7] | MIT, © 2022 (ПТ) | Full takeover; 7.34c; в «Play VS Bots» «not all heroes are implemented» (ПТ) | Коммит 20.09.2023 (ПТ): заброшен | «Alpha», «Overly aggressive», орб-волк, динамический ретрит (ПТ) | Образец своего микро на MIT. Устарел на несколько патчей |
| **BOT Experiment** (Furiouspuppy) [S10] | На GitHub `arzon4dt/bot-experiment`: LICENSE не найден (ПТ); связь с Furiouspuppy не подтверждена | — | — | Пользователь OHA: «were also very good until their developer completely screwed them over» (ПТ, #120, 26.01.2026) | Нет |
| **PhalanxBot** [S11] | Неизвестна. Неофициальные копии на GitHub без лицензии (`Zacknetic/phalynx_bot`, 3 коммита) (ПТ) | Workshop 2873408973; changelog с улучшениями под 7.39 (С) | Обновлялся до 2024–2025 (С) | «the only bot script that works» — мнение из комментариев (С) | Нет: исходники и лицензия неясны |
| **Ranked Matchmaking AI**, adamqqq [S8] | GPL-3.0 (ПТ) | «Support 100+ heroes» (ПТ) | Даты не смотрел | — | Только если весь наш код будет под GPL-3 (вывод) |
| **ExtremePush**, insraq [S9] | Нет (ПТ) | Версии 2017 года (ПТ) | Заброшен | — | Нет |
| Боты Valve (примеры) [S2] | Лицензия не указана (файлы игры) | Lina, Sven (примеры) | В зеркале игры путь менялся 19.02.2025 (ПТ) | — | Как учебный образец |

Вывод по лицензиям. Чисто брать код можно у VUL-FT (MIT), Fretbots (MIT), dota_duel (Apache-2.0), bota (Apache-2.0) и, с оговоркой о происхождении, у OHA (MIT). Из x_hero_siege (GPL-2.0), adamqqq (GPL-3.0), ryndrb и ExtremePush (без лицензии) код не копировать, брать только идеи.

---

## 3. Bot scripts внутри кастомки и своё микро на vscripts

### 3.1 Работают ли боты в custom game

- **Встроенные (C++) боты Valve** в аддоне работают. Валвовские обучающие аддоны `tutorial_assist_game` и `tutorial_basics` вызывают `SetBotThinkingEnabled(true)` и `Tutorial:AddBot("npc_dota_hero_dazzle", "bot", "passive", true)` (ПТ [S13]).
- Рычаги из vscripts: `SetBotsMaxPushTier`, `SetBotsInLateGame`, `SetBotsAlwaysPushWithHuman`, `hero:SetBotDifficulty` (ПТ [S13]).
- Ограничение из дампа API: «SetBotThinkingEnabled — Enables/Disables bots in custom games. Note: this will only work with default heroes in the dota map» (ПТ, файл ModDota/API от 29.08.2016 [S12]). Координатор видел ту же строку в @moddota/dota-data 0.47.2 (апрель 2026).
- В OAA: «Should we have bots act like they would in Dota? (This requires 3 lanes, normal items, etc)» (ПТ [S15]).
- В `hero_demo` и `workshop_testbed` у Valve: `--GameMode:SetBotThinkingEnabled( true ) -- the ConVar is currently disabled in C++` (ПТ [S13]). Это противоречит обучающим аддонам. Дата комментария неизвестна.
- Legends of Dota Redux (опубликованная кастомка, карта `custom_bot`) добавляла ботов через `Tutorial:AddBot('', '', 'unfair', true)` и давала им только героев с `BotImplemented == 1`. Для отдельных способностей были свои модификаторы-ИИ, например `modifier_slark_shadow_dance_ai` (ПТ [S16], последний коммит develop 06.04.2021).
- **Lua-скрипты из папки `bots` в аддоне.** У Open Angel Arena в аддоне лежат `game/scripts/vscripts/bots/mode_*_generic.lua` (RamonNZ, 2017; правки до 20.01.2025) (ПТ [S15]). Readme: «this will not work on games that have been uploaded to Valve via Dota Workshop. It will only work on games that are launched from your \addons\ directory via the "dota_launch_custom_game oaa aaa" console command» (ПТ [S15]). Сниппет Steam: «bot script does not load and the bots will not pick» в кастомных режимах (С [S11]). Свежих (2024–2026) подтверждений в ту или другую сторону нет.

### 3.2 Своё микро на vscripts: как это делают

- **Создание бот-игрока.** `GameRules:AddBotPlayerWithEntityScript(hero, name, team, entityScript, …)`. Так делают:
  - Valve NPE 2019: `spawner.lua`, сценарий `scenario_mid_1v1` → `ai/ai_sf_mid_1v1.lua` (ПТ [S14]);
  - шаблон Overthrow (ПТ [S17]);
  - dota_duel (ПТ [S18]);
  - x_hero_siege: «Entity script used only to obtain a real Dota bot player slot. The XHS manager owns all decision making; no vanilla lane bot logic runs here» (ПТ [S19]).
- **Цикл мышления.**
  - `SetContextThink(..., 0.25)` в Valve NPE для SF (ПТ [S14]);
  - модификатор с `StartIntervalThink(0.2)` в Overthrow (ПТ [S17]);
  - `think_interval` 0.55 с (easy) или 0.28 с (normal) в XHS (ПТ [S19]);
  - тик раз в 1 с в учебнике ModDota (ПТ [S20]);
  - `thinkDuration = 3` в holdout `ai_core.lua` (ПТ [S16]).
- **Приказы.** `ExecuteOrderFromTable{UnitIndex, OrderType=DOTA_UNIT_ORDER_*, …}`, `MoveToPosition`, `CastAbilityOnTarget` (ПТ [S16][S17][S20]).
- **Прямое управление героем.** Overthrow запрещает людям управлять бот-героем: `SetControllableByPlayer(ID, false)` (ПТ [S17]). Для «опосредованного управления» это и нужно (вывод).
- **Честность.** У vscripts полный доступ к миру (вывод из устройства API). dota_duel фильтрует наблюдения через `CanEntityBeSeenByMyTeam` (ПТ [S18]).
- **Шаблоны.**
  - Valve `ai_core.lua` (holdout): `CreateBehaviorSystem`, у каждого поведения `Evaluate()` → максимум, затем `Begin/Continue/End/Think` (ПТ [S16]). Утилитарный ИИ, как режимы ботов.
  - Valve NPE `ai_laning.lua`: универсальный лайнинг (ласт-хит, денай, харасс, подход, ретрит к башне, банки и танго), параметры skill×type (раздел 5.2) (ПТ [S14]).
  - Overthrow `bot_main.lua`: «общий» кастер скиллов по флагам поведения (UNIT_TARGET, POINT, NO_TARGET, TOGGLE) из KV (ПТ [S17]).
  - ModDota `Dota2AIFramework` (2015–2016): песочница, которая обёртывает API под «видимость как у человека», и `AIManager:AttachAI('ai_name', unit)` (ПТ [S21]).
- **AABS, Custom Hero Chaos, Dota IMBA.** Исходников ИИ героев на GitHub не нашёл: репозитории AABS и CHC поиском не находятся. IMBA вызывает `SetBotThinkingEnabled(false)` (ПТ).
- **Внешний мозг для кастомки.**
  - Framework lightbringer/dota2ai: «a proxy between the game and a web service through JSON objects» (ПТ [S22], 2016–2024).
  - 5v5dota2ai-addon: Python-клиент управляет одной командой, против неё встроенные боты; запуск `dota_launch_custom_game dota2ai dota` в Tools (ПТ [S23]).

### 3.3 Сколько работы на 10–20 героев

Опорные размеры (ПТ, мой подсчёт строк):

| Код | Строк |
|---|---|
| OHA, файлы героев: Juggernaut / Axe / Sniper / Lina / CM / Invoker | 580 / 589 / 692 / 852 / 1034 / 1937 |
| OHA, ядро: `jmz_func.lua` + `ability_item_usage_generic.lua` + `item_purchase_generic.lua` | 6 743 + 8 429 + 1 298 (поверх C++-логики Valve) |
| Valve `ai_laning.lua` | 853 |
| x_hero_siege, всё на vscripts (19 файлов) | 23 066 |
| Overthrow, универсальный бот | 1 022 |

Вывод (оценка, не измерение):
- своё ядро на vscripts — порядка 10–20 тыс. строк Lua;
- на героя — 300–1000+ строк;
- на «пару месяцев» реалистично 10 героев, если взять схемы Valve NPE `ai_laning`, функции `Consider*` и логику скиллов из MIT-источников;
- 20 героев за этот срок — под вопросом.

---

## 4. Обучаемый ИИ

### 4.1 OpenAI Five (ПТ\* [S28], разобранная копия статьи arXiv:1912.06680)

- Наблюдение через Valve Bot API: «~16,000 total values» за шаг. Действие на каждый 4-й кадр при 30 кадрах в секунду, то есть «7.5 steps per second». Реакция в среднем 217 мс.
- Ограничения:
  - 17 героев из 117;
  - убраны предметы, дающие несколько юнитов (Illusion Rune, Helm of the Dominator, Manta, Necronomicon).
- Скриптами (не нейросетью) делались:
  - порядок прокачки способностей;
  - покупки предметов, включая расходники;
  - выбор предметов в рюкзак;
  - курьер — «state-machine based logic».
- Обучение шло с 30.06.2018 по 22.04.2019, «770 ± 50 PFlops/s-days».
- Инфраструктура в какой-то момент: 57 600 rollout-воркеров на 51 200 CPU, 512 GPU прямого прохода и 512 GPU оптимизатора. Rollout-игры шли «approximately 1/2 real time». Python-код говорил по gRPC с Go-сервером в Docker, где жил движок Dota со «Scripting API (Lua)».
- Результаты: 13.04.2019 OG 2:0; Arena 18–21.04.2019 — 7 257 игр, 99.4 % побед, причём 3 140 из 7 215 побед — брошенные людьми игры.
- Повторный прогон (Rerun) занял 2 месяца и «150 ± 5 PFlops/s-days».
- Опыт с размером пула: 80 героев учатся в начале примерно на 20 % медленнее, чем 17.
- Публичного API или кода агента OpenAI не нашёл (вывод: интерфейс закрыт).

### 4.2 Окружения и проекты

- **dotaservice / dotaclient** (TimZaman) [S25] — мёртвы: последний коммит dotaservice 18.07.2019 (ПТ).
  - Dota как gRPC-сервис: `reset` около 5 с, `step` — «between 10 and 30 ms» (ПТ).
  - Выделенный сервер на Linux: `dota.sh -dedicated … -fill_with_bots -botworldstatetosocket_radiant … -botworldstatetosocket_frames 5 … +host_timescale 1` (ПТ). Headless-Dota около 250 МБ RAM (ПТ).
  - Игра пытается загрузить `bots/botcpp_radiant.so` с `Init/Observe/Act/Shutdown` (ПТ, 2018–2019).
  - dotaclient: K8s, «40 agents per optimizer», «around 1000 steps/s» на оптимизатор; видео self-play 1v1 за 2019 год (ПТ).
- **LuaFun / dota2env** (Delaunay, BSD-3, 2021) [S26] — мёртв. «Full Hero take over», «No scripted logic». Известные проблемы: под Windows теряются состояния, «Bots do not control their illusions/minions» (ПТ).
- **bota** (Apache-2.0, сентябрь 2025) [S27]: GPT-OSS-20B через vLLM без дообучения играет 1v1 mid.
  - Состояние приходит через сокет (`-botworldstatetosocket_radiant 8100 …`, Ubuntu 22.04, `+map start gamemode 21`), действия Python пишет в Lua-файл `bots/action_<team>`, бот читает его через `loadfile` (ПТ).
  - Комментарий в коде: при `host_timescale` > 8 часть игроков пропускает `Think` (ПТ).
  - Вывод: механизм `-botworldstatetosocket` и Lua-боты работали в 2025 году.
- **rampagebot** (2024, магистерская работа, RLlib DQN/PPO, GPL-3.0 по README) через 5v5dota2ai-addon (ПТ [S23]).
- **Ускорение времени.**
  - ryndrb тестирует с `sv_cheats 1; host_force_frametime_to_equal_tick_interval 1; host_timescale 4` (ПТ [S5]);
  - dotaservice видел, что timescale «sometimes runs 2x faster than it should» (ПТ).
  - Вывод: при ускорении ×4 одна 40-минутная игра идёт около 10 минут реального времени.
- **Honor of Kings Arena / hok_env** (Tencent, Apache-2.0, NeurIPS D&B 2022, arXiv:2209.08483) [S29] (ПТ):
  - режимы 1v1 и 3v3;
  - gamecore только под Windows или wine, лицензию на него нужно запрашивать;
  - в README перечислены 19 героев, в аннотации — «twenty target heroes»;
  - «baseline results for RL-based methods with feasible computing resources».
- **Tencent HoK 2020**: 95.2 % побед в 42 матчах с профи, 97.7 % в 642 047 матчах с топ-игроками, пул 40 героев (С [S32]).
- **HMS** (AAAI 2019): макро-модель предсказывает «attention on the game map» по фазам игры, у агентов есть межагентная коммуникация; 48 % побед против команд из топ-1 % (С [S31]).
- **TiG** (Tencent, arXiv:2508.21365, 29.08.2025): 40 макро-действий («Push top lane», «Secure dragon», «Defend base»); LLM выбирает действие и объясняет. Qwen3-14B после 2000 шагов GRPO даёт 90.9 % верных решений, DeepSeek-R1 — 86.7 % (С [S30]).
- Работа arXiv:2409.19363 «Learning Strategy Representation for Imitation Learning in Multi-Agent Games» (2024) (С). Относится ли она к Dota, не проверил: кончился лимит поиска.

### 4.3 Что реально обучить без кластера (вывод)

- Полный RL 5v5 недоступен: даже 1v1 у dotaclient шёл на K8s.
- Реально:
  - подгонять веса утилит, пороги и параметры стиля под статистику конкретного игрока из реплеев, без RL;
  - учить макро «куда идти и когда собираться» по реплеям, как HMS или TiG, если хватит данных (оцифровка — тема другого отчёта);
  - ставить узкие RL-задачи на микро (ласт-хит, кайт 1v1) в локальном движке с ускорением ×4: долго, но возможно на одной машине.
- Всё это не проверено.

---

## 5. Иерархия управления и «стиль игрока»

### 5.1 Подходы и примеры

- **Desire / утилитарный ИИ** (Valve): командные желания → режимы с `GetDesire` → действия (ПТ\* [S1]). Тот же приём в vscripts — holdout `ai_core.lua` (ПТ [S16]).
- **IAUS** (Infinite Axis Utility System): каждое соображение — «single input → response curve», баллы перемножаются, текущее поведение получает «inertia bonus» против метаний (ПТ [S42], вики ProjectBorealis). Утилитарную теорию на GDC продвигали Dave Mark и Kevin Dill (доклады 2010 и 2012); IAUS Dave Mark показал вместе с Mike Lewis на GDC 2015 (С).
- **Behavior Trees**: Damian Isla, Halo 2, GDC 2005 (С [S43]). Riot перевела ботов LoL на «new Behavior Tree system»: боты лесничат, ганкают, берут драконов и «can scale to match player skill» (С [S44]).
- **GOAP**: Jeff Orkin, F.E.A.R., GDC 2006. FSM из трёх состояний, A\* планирует действия к целям (С [S40]).
- **HTN**: Fluid HTN (MIT) — составные задачи (Selector/Sequencer) и примитивы с условиями и эффектами, перепланирование при изменении мира (ПТ [S41]). Troy Humphreys, «Exploring HTN Planners through Example», Game AI Pro; применяли в Killzone, Transformers, Horizon Zero Dawn (С).
- **Иерархии в MOBA и RTS.**
  - Dota2-WebAI (Nostrademous, MIT, 2017): «the web-based system might tell the bot "farm BOT_LANE"… will not tell the bot how to last hit, when to last hit, when to deny» (ПТ [S24]). Ровно наша схема «намерение сверху, микро в Lua».
  - x_hero_siege: brain / team_director / executor / world_model / danger_registry / hero_profiles (ПТ [S19]).
  - SwarmBrain (StarCraft II): LLM-макро плюс быстрый state machine для реакций «due to the inherent latency in LLM processing» (С [S34]).
  - MCC (Tencent, ICLR 2023): люди дают агентам «meta-commands», агент оценивает их ценность и выбирает (С [S33]).
- Вывод: для нас лучше всего подходит **утилитарный ИИ на макро** (знаком по Valve, легко параметризуется весами), **скрипты и короткие деревья на микро** и **закрытый словарь намерений сверху**. GOAP и HTN избыточны, разве что для «плана на 30–60 с» вроде «смок → ганг → Рошан».

### 5.2 Как стиль параметризует слои: готовые образцы

- **Valve NPE `ai_laning.lua`** (ПТ [S14]):
  - `LAST_HIT_AI_SKILL` = EASY / MEDIUM / HARD;
  - `LAST_HIT_AI_TYPE` = BALANCED / LAST_HIT_FOCUSED / DENY_FOCUSED / HARASS_FOCUSED;
  - они меняют `nHealthPctDifferentialPct` (75 / 65 / 30), `nHarassPct` (4 / 8 / 16), `nHarassPctBonusPerAttack` (10 / 20 / 30) и `nDenyWeightPct` (15; 35 при DENY_FOCUSED; 5 при LAST_HIT_FOCUSED);
  - HARASS_FOCUSED делит порог на 2 и удваивает харасс.
- **x_hero_siege `config.lua`** (ПТ [S19]). Пресеты easy и normal, около 50 параметров (мой подсчёт — 53 в пресете easy):

  | Параметр | easy | normal |
  |---|---|---|
  | `think_interval` | 0.55 | 0.28 |
  | `reaction_min…max` | 0.80…1.40 | 0.25…0.60 |
  | `target_commitment` | 2.50 | 1.25 |
  | `perception_radius` | 1850 | 2150 |
  | `ability_use_chance` | 0.62 | 0.88 |
  | `order_jitter` | 90 | 45 |
  | `max_orders_per_second` | 1 | 2 |
  | `max_chase_distance` | 1050 | 1400 |
  | `maximum_retreat_health` | 0.62 | 0.70 |
  | `human_follow_weight` | 0.20 | 0.65 |

  Также `director_replan_interval`, пороги банок и др. Отдельно `hero_profiles.lua` хранит «аффинити» героя: right_click, caster, frontline, survival… (ПТ).
- **Сложности Valve**: задержка способностей, окна запрета, шум оценки ласт-хита, бонус ресурсов (ПТ\*, раздел 1.3).
- **Fretbots**: сложность 0–10 = бонусы GPM/XPM по роли относительно игрока-человека, а не поведение (ПТ [S6]).
- **Сборки.** OpenAI Five: фиксированные расписания предметов и скиллов, слегка рандомизированные в обучении (ПТ\*). VUL-FT: «DotaBuff parser for averaged out of 5 game skill build, roles and an item build from Divine - Immortal players that week» (ПТ [S7]).
- **AlphaStar**: политика обусловлена статистикой z — первые 20 построек и юнитов плюс накопленная статистика из человеческой игры (С [S39]). Это научный аналог «вектора стиля».

Вектор стиля по слоям (вывод):

| Слой | Параметры стиля | Откуда брать (тема оцифровки) |
|---|---|---|
| Пик и роли | Пул героев, позиции и линии | Реплеи и профиль игрока |
| Сборки | Порядок предметов и скиллов, время ключевых предметов | Реплеи (как у VUL-FT и OpenAI Five) |
| Макро (утилиты) | Веса farm / push / roam / defend / rune / roshan; склонность к сплит-пушу; частота ротаций | Доли времени по зонам карты, время первых ротаций |
| Риск | Пороги ретрита по HP, глубина нырков, `max_chase_distance`, `target_commitment` | Смерти, позиции в момент смерти |
| Лайнинг | skill × type (как в NPE): харасс, денай, ласт-хит | LH/DN к 10-й минуте |
| «Руки» | Реакция (min/max), джиттер приказов, APM-лимит, шум ласт-хита | По реплею частично (APM); реакция плохо наблюдаема |

Стиль и «навык» стоит держать раздельно: стиль отвечает на вопрос «что предпочитает», навык — «насколько точно и быстро» (вывод). Тогда можно получить «Miracle на уровне 2 MMR» и наоборот.

---

## 6. LLM как «мозг» агента

- **bota (2025)**: LLM напрямую выбирает действия героя в 1v1 — «move the hero, attack, use items as well as abilities» — и печатает рассуждение в чат (ПТ [S27]). Цифр задержки и силы в README нет. Код меряет «Inference time» (ПТ).
- **Cradle** (BAAI, arXiv:2403.03186): «RDR2 … requires real-time combat, so we need to pause the game to wait for GPT-4o's response and then unpause» (ПТ [S37]).
- **TextStarCraft II** (arXiv:2312.11865): «approximately 7 hours for a single game»; LLM-агенты обыгрывают встроенный ИИ уровня 5 (Harder): GPT-3.5-Turbo-16k — 5/10, дообученная Qwen — 6/10 (ПТ [S35], страница GitHub).
- **LLM-PySC2** (arXiv:2411.05348): макро и микро, мультиагентность; для отладки `config.LLM_SIMULATION_TIME = 5` — «simulate a 5-second response large model» (ПТ [S36]).
- **SwarmBrain**: gpt-3.5-turbo ведёт макро, микро — state machine из-за задержки LLM (С [S34]).
- **TiG**: LLM для макро-решений из закрытого списка из 40 действий (С [S30]).
- **PokeLLMon** (arXiv:2402.01118, 2024): пошаговые бои Pokémon Showdown через API OpenAI (README — ПТ [S38]). Заявления о «паритете с людьми» — П. Реального времени там нет.
- **OHA**: чат-бот FretBots отправляет чат игроков на внешний бэкенд и отвечает от имени бота через `Say(bot, aiText, false)` (ПТ [S3]). В OHA есть и заготовка HTTP-слоя для «backend services enpowered with machine learning AI» (ПТ). Автор OHA пишет: «We need ML/LLM bots like OpenAI Five!» (ПТ).
- Нижняя граница для микро: OpenAI Five действует 7.5 раза в секунду с реакцией около 217 мс (ПТ\*).

Вывод:
- LLM полезна в трёх ролях: (а) разбор свободной речи командира в закрытый словарь намерений, если не хватает грамматики; (б) командный план и объяснения раз в несколько секунд или по событию; (в) голоса и реплики героев.
- Всё, что быстрее примерно 0.3 с (ласт-хит, кайт, прерывания, уклонения, комбо), — только скрипт.
- Частоту вызова LLM выбрать пилотом по замеру задержки нашего «мотора». Сам я задержку не мерил.

---

## 7. Канал vscripts → bot scripts (вопрос координатора)

Общей памяти нет (вывод из трёх фактов):
- вики: «Each of the following scripting elements has its own script scope» (ПТ\* [S1]);
- в окружении ботов `CreateHTTPRequestScriptVM` равен `nil` — «attempt to call global 'CreateHTTPRequestScriptVM' (a nil value)» (ПТ [S24], issue #25, 17.08.2017);
- во встроенном дампе API ботов (`CDOTA_TeamCommander`) нет CustomNetTables, игровых событий и convars (ПТ [S47]).

Даже Lua-библиотеки ботов vscripts грузит как отдельный код: ryndrb `Buff` делает `require('bots/FunLib/aba_role')` (ПТ [S5]).

| Канал | Что есть в API бота | Что есть в vscripts | Проверено ли «кастомка → бот» |
|---|---|---|---|
| **(а) Модификаторы со stack count** | `HasModifier(name)`, `GetModifierByName(name)` → индекс, `NumModifiers()`, `GetModifierName(i)`, `GetModifierStackCount(i)`, `GetModifierRemainingDuration(i)`, `GetModifierAuxiliaryUnits(i)` (ПТ\* [S1]); `GetModifierList()` есть в дампе и в живом коде Rage-Trigger (ПТ [S47]) | `AddNewModifier`, `SetStackCount` (дамп, ПТ [S12]); FretBots вешает ботам модификаторы, включая свой Lua-модификатор `modifier_seasonal_party_hat` (ПТ [S3]) | **Нет.** Кода, где бот читает Lua-модификатор, повешенный кастомкой, не нашёл. Боты исполняются на сервере, «at the server level» (ПТ\*), поэтому видимость вероятна (вывод), но это не проверено |
| **(б) Чат** | `InstallChatCallback(fn)`: OHA получает `attr.player_id`, `attr.string`, `attr.team_only` и разбирает команды людей `!pos`, `!pick` (ПТ [S3]); VUL-FT читает чат человека (ПТ [S7]); `ActionImmediate_Chat` (ПТ\*) | `Say(entity, msg, teamOnly)` (дамп, ПТ [S12]); FretBots говорит от имени бота через `Say(bot, …)` (ПТ [S3]) | **Нет.** Сообщения людей до бота доходят (ПТ). Доходит ли серверный `Say()` до `InstallChatCallback`, не выяснено |
| **(в) Пинги** | `unit:GetMostRecentPing()` → `{time, location, normal_ping}` (ПТ\*); VUL-FT читает пинг человека, чтобы получить ответ на вопрос бота (ПТ [S7]); `ActionImmediate_Ping` (ПТ\*). OAA 2017: «bots will … respond to pings now, albeit badly» (ПТ [S15]) | `GameRules:ExecuteTeamPing(team, x, y, entity, type)` (по данным координатора) | **Нет.** Становится ли пинг из `ExecuteTeamPing` чьим-то `GetMostRecentPing`, неизвестно |
| **(г) Папка `bots` внутри аддона** | — | — | Только при локальном запуске аддона (`dota_launch_custom_game`), не для опубликованных (ПТ [S15], 2017). Свежих данных нет |
| **(д) Предметы и состояние союзника** | Бот видит инвентарь и позиции союзников (`GetTeamMember`) (ПТ\*) | Можно выдавать и перекладывать предметы | OAA V3: «If you hold a smoke in the first slot of your backpack, all your bots will follow you…; second slot … only heroes» (ПТ [S15]). Работает только «человек → бот», хак |
| **(е) HTTP через локальный ретранслятор** | `CreateHTTPRequest` (по справке OHA — только localhost), `CreateRemoteHTTPRequest` (ПТ [S3][S47]); OHA ходит на `http://127.0.0.1:5000/` (ПТ) | `CreateHTTPRequest("POST", url)` (FretBots, ПТ [S3]) | **Нет** (вывод: технически обе стороны умеют HTTP). Только при локальном хосте; при выключенном Steam `CreateRemoteHTTPRequest` отказывал (ПТ [S25]) |
| **(ж) Файлы** | `loadfile/require` внутри `vscripts`; bota читает `bots/action_<team>` (ПТ [S27]) | Записи файлов в vscripts не знаю (П) | Канал «внешний процесс → бот» работает (bota, ПТ). Канал «кастомка → бот» — нет |
| **(з) Прямые приказы из vscripts** | — | ryndrb `Buff/Spells.lua` из vscripts кастует за бота `bot:CastAbilityOnTarget` — способности, которые «can't be implemented using the regular bot api (ie Visage Familiars)» (ПТ [S5]) | Это не передача намерения, а перехват управления. Работает (ПТ) |

Примеров кастомок, которые передавали боту намерение через модификатор, чат или пинг, **не нашёл**. Есть только лобби-связки «bot scripts + vscripts через `script_reload_code`» (Fretbots, ryndrb Buff) и «человек → бот» через пинги и чат (VUL-FT, OHA, OAA) (ПТ).

Вывод для архитектуры:
- для прототипа в локальном лобби канал из vscripts не нужен: голосовое приложение пишет намерения прямо боту (файл, как bota, или localhost HTTP);
- в итоговой кастомке ИИ сам живёт в vscripts, и канал тоже не нужен;
- тест (а)–(в) нужен, только если выберем гибрид «боты Valve в кастомке».

---

## Рекомендация: архитектура ИИ агента

**Принцип.** Голос и LLM задают намерение раз в несколько секунд. Всё быстрее примерно 0.3 с делает детерминированный скрипт. Стиль игрока — вектор параметров на каждом слое, навык — отдельный вектор (вывод из разделов 1, 5, 6).

### Слои и частоты (вывод; частоты — по образцам Valve, NPE и XHS)

| Слой | Что делает | Частота | Механизм | Образец |
|---|---|---|---|---|
| L0 Командир | Голос → намерение из закрытого словаря: кто, что, где, приоритет, срок. Примеры: «пуш топ», «все на Рошана», «дефай мид», «ганг Лину», «отступаем», «смок», «агрессивнее» | По событию | Грамматика, LLM как запасной разбор, голосовое подтверждение | TiG (40 макро-действий), MCC |
| L1 Директор команды | Намерение + состояние → назначения героям | ~1 Гц | Утилиты (аналог `team_desires`) | Valve team desires, XHS `team_director` (`director_replan_interval` 0.85–1.35 с) |
| L2 Макро героя | Выбор режима: laning, farm, push, defend, roam, retreat, rune, roshan, shop, ward | ~3 Гц | `desire = база(состояние) × вес_стиля + бонус_намерения`, инерция | Режимы Valve (`GetDesire` ~300 мс), IAUS |
| L3 Микро героя | Ласт-хит, денай, харасс, кайт и орб-волк, комбо, уклонение, предметы, ретрит | 4–30 Гц | Скрипт: общий модуль плюс модуль героя (`Consider*`) | NPE `ai_laning`, Valve `Consider*`, OHA BotLib, VUL-FT |
| L4 Исполнитель | Задержка реакции, джиттер, лимит приказов, шум ласт-хита — это «навык» | Каждый приказ | Очередь приказов | Сложности Valve, XHS `executor` и параметры |

### Что берём и что пишем сами

1. **Прототип, 2–4 недели, лобби «Local Host».**
   - Движок героев — OHA как есть: MIT, 127 героев. Мы только запускаем его и правим под себя, не распространяем.
   - Наш модуль намерений: смещения в `team_desires` и `GetDesire` режимов. Голосовое приложение пишет намерения в файл или localhost HTTP, боты читают их раз в 0.25–1 с, как bota и OHA `http_req`.
   - Метрики «правды» берём из игры: LH/DN к 10-й минуте, смерти, выполнено ли намерение за T секунд.
   - Цель прототипа — проверить, что «командование голосом» вообще играбельно. Минусы: ручная установка, поломки от патчей, 9 «сломанных» героев.
2. **Продукт: кастомка на 2 игроков × 5 агентов.**
   - Свой ИИ на vscripts. Боты создаются через `AddBotPlayerWithEntityScript`, людям запрещено прямое управление (`SetControllableByPlayer(false)`).
   - Наблюдения фильтруются по видимости команды (`CanEntityBeSeenByMyTeam`).
   - Пул на старте — 10 героев с простыми скиллами, дальше расширять.
   - Чужого берём схемы, а код только из MIT и Apache: VUL-FT, dota_duel, bota и OHA с проверкой происхождения фрагмента. Плюс учебные файлы Valve (NPE `ai_laning`, `bots_example`) — их лицензия не указана.
3. **Пишем сами:** L0–L2 целиком, исполнитель L4, вектор стиля и его подгонку по реплеям, модули героев L3 и тесты силы на метриках из игры.
4. **Не делаем:** RL «как OpenAI Five»; LLM на микро; копирование кода из GPL-проектов (x_hero_siege, adamqqq) и из проектов без лицензии (ryndrb, ExtremePush) в закрытый продукт.

### Пилоты до решения (по воротам CLAUDE.md: пилот, затем решение)

1. Тест каналов 7(а)–(в) в локальном лобби (вывод: около 1 дня). vscripts вешает герою `modifier_intent` со stack=N, говорит `Say()` и делает `ExecuteTeamPing`; бот логирует, что увидел. Нужен, только если всерьёз рассматриваем гибрид с ботами Valve.
2. Тест 7(г): папка `bots` в аддоне при `dota_launch_custom_game` и в закрытой Workshop-публикации.
3. Замер задержки «речь → интент» и «LLM → план» на нашем «моторе». По нему выбрать частоту L0 и L1.
4. Сила микро: OHA против нашего vscripts-бота на 2–3 героях в одинаковых условиях (LH/DN за 10 мин, смерти, урон), правда — из игры.
5. Лог частоты `GetDesire`: ~300 мс по вики или каждый кадр по справке OHA.

---

## Что не удалось выяснить

- Оригинал вики Valve (Dota_Bot_Scripting) заблокирован. Использована копия викитекста от 01.04.2026, дата ревизии на вики неизвестна.
- Официальные изменения или исправления bot API от Valve в 2024–2026. Причины поломок из issues OHA не установлены.
- Работают ли сегодня Lua-скрипты из папки `bots` внутри опубликованной кастомки. Есть только свидетельство OAA 2017 года — «нет».
- Видны ли боту Lua-модификаторы кастомки; доходят ли до `InstallChatCallback` серверный `Say()` и пинги из `ExecuteTeamPing`.
- Что именно значит флаг `BotImplemented` в движке. Моя трактовка — герои со встроенной логикой.
- Сила OHA, Phalanx и ryndrb против людей в цифрах (MMR, винрейт). Измерений не нашёл.
- Исходники и лицензия PhalanxBot.
- Работает ли сейчас `-dedicated` сервер Dota на Linux: bota в 2025 году запускал обычный клиент.
- Задержка LLM в реальных Dota-проектах: bota не публикует цифры.
- Текущий номер патча на 06.10.2026. В README ryndrb на 26.09.2026 указан 7.41f.
- Исходники ИИ Angel Arena Black Star и Custom Hero Chaos не найдены.
- Статьи TiG, HMS, MCC, SwarmBrain, AlphaStar и 2409.19363 — только сниппеты (arXiv заблокирован). Под конец закончился лимит WebSearch, поэтому часть сниппетов не перепроверена.
- Задержку Claude как «мотора» для L0 и L1 не мерил.

Предположения этого отчёта, которые стоит записать в `journal/ERRORS.md` как непроверенные:
- трактовка `BotImplemented`;
- «бот видит Lua-модификаторы кастомки»;
- оценка 10–20 тыс. строк на ядро;
- частоты слоёв L1–L3.

---

## Источники (доступ 06.10.2026)

- S1. Valve Developer Community, «Dota Bot Scripting». Оригинал https://developer.valvesoftware.com/wiki/Dota_Bot_Scripting заблокирован. Читал копию викитекста https://github.com/p6668/dota2bot-and-fretbots/blob/main/BOT_API.md (коммит 01.04.2026) — ПТ\*.
- S2. Примеры ботов Valve (файлы игры) в зеркале: https://github.com/SteamTracking/GameTracking-Dota2/tree/master/game/dota/scripts/vscripts/bots_example (путь изменён 19.02.2025) — ПТ.
- S3. Open Hyper AI: https://github.com/forest0xia/dota2bot-OpenHyperAI — README, LICENSE (MIT 2024), docs/BOT_API_REFERENCE.md, docs/ARCHITECTURE.md, CLAUDE.md, bots/FunLib/utils.lua, bots/hero_selection.lua, bots/ability_item_usage_generic.lua, bots/FretBots/Chat.lua, bots/FretBots/modifiers/Modifier.lua, typescript/…/http_req.ts, страница коммитов (03.04.2026) — ПТ.
- S4. Issues OHA #18, #32, #53, #89, #93, #102, #104, #115, #120, #153: https://github.com/forest0xia/dota2bot-OpenHyperAI/issues — ПТ.
- S5. Tinkering ABo(u)t: https://github.com/ryndrb/dota2bot — README, Buff/README.md, Buff/Spells.lua, Buff/SpellsMore.lua, коммиты (26.09.2026) — ПТ.
- S6. Fretbots: https://github.com/fretmute/fretbots — README, LICENSE (MIT 2021), коммиты (10.03.2025) — ПТ.
- S7. VUL-FT: https://github.com/Yewchi/vulft — README, LICENSE (MIT 2022), lib_job/modules/communication.lua, коммиты (20.09.2023) — ПТ.
- S8. Ranked Matchmaking AI: https://github.com/adamqqqplay/dota2ai — README, LICENSE (GPL-3.0) — ПТ.
- S9. ExtremePush: https://github.com/insraq/dota2bots — README; LICENSE отсутствует — ПТ.
- S10. https://github.com/arzon4dt/bot-experiment и https://github.com/Zacknetic/phalynx_bot — страницы репозиториев — ПТ.
- S11. Steam Workshop: обсуждения и changelog PhalanxBot (2873408973), VUL-FT (2872725543), OHA (3246316298), 837040016, 855965029 — С (steamcommunity.com заблокирован).
- S12. Дамп API vscripts: https://github.com/ModDota/API/blob/master/dump/script_help2.lua (файл от 29.08.2016) — ПТ.
- S13. Аддоны Valve в зеркале: game/dota_addons/{tutorial_assist_game, tutorial_basics, hero_demo, workshop_testbed}/scripts/vscripts/addon_game_mode.lua в https://github.com/SteamTracking/GameTracking-Dota2 — ПТ.
- S14. Valve NPE 2019: game/dota_addons/npx_2019/scripts/vscripts/{spawner.lua, scenarios/scenario_mid_1v1.lua, ai/ai_sf_mid_1v1.lua, ai/ai_laning.lua} (в зеркале с 25.03.2021); около 71 AI-скрипта в ai/ — ПТ.
- S15. Open Angel Arena: https://github.com/OpenAngelArena/oaa — game/scripts/vscripts/bots/*, bots/docs/readme.md, bots/docs/AAO Bot.txt, components/devcheats/commands.lua, settings.lua, internal/gamemode.lua; история папки bots с 23.03.2017 по 20.01.2025 — ПТ.
- S16. Legends of Dota Redux: https://github.com/darklordabc/Legends-of-Dota-Redux — src/game/scripts/vscripts/pregame.lua, abilities/dota2horde/ai_core.lua (develop: 06.04.2021) — ПТ.
- S17. Шаблон Overthrow: https://github.com/Snoresville/dota2buttemplate_overthrow — overthrow_bot_module/bot_main.lua, bot_hero.lua — ПТ.
- S18. Dota Duel: https://github.com/pengowen123/dota_duel — README (Apache-2.0, Workshop 933598755), bot/bot.lua, bot/observations/observations.lua; коммит 27.01.2025 — ПТ.
- S19. X Hero Siege: https://github.com/EarthSalamander42/x_hero_siege/tree/master/game/scripts/vscripts/components/xhs_bots — config.lua, hero_profiles.lua, entity_script.lua, provisioner.lua и др.; LICENSE (GPL-2.0); коммиты 28.07–14.08.2026 — ПТ.
- S20. ModDota, «Adding a Very Simple AI to Units» (wigguno, 27.07.2015): https://github.com/ModDota/moddota.github.io/blob/source/_articles/units/adding-a-very-simple-ai-to-units.md — ПТ.
- S21. https://github.com/ModDota/Dota2AIFramework — README; коммиты 04.10.2015–11.11.2016 — ПТ.
- S22. https://github.com/lightbringer/dota2ai — README, addon_game_mode.lua; коммиты 05.07.2016–28.12.2024 — ПТ.
- S23. https://github.com/tbumi/5v5dota2ai-addon (README, vscripts) и https://github.com/tbumi/rampagebot (README, 2024) — ПТ.
- S24. https://github.com/Nostrademous/Dota2-WebAI — README, LICENSE (MIT 2017), коммиты до 28.09.2017, issue #25 (17.08.2017) — ПТ.
- S25. https://github.com/TimZaman/dotaservice (README, NOTES.md; коммит 18.07.2019) и https://github.com/TimZaman/dotaclient (README) — ПТ.
- S26. https://github.com/Delaunay/dota2env (LuaFun) — README, LICENSE (BSD-3), коммиты 08.04–15.05.2021 — ПТ.
- S27. https://github.com/AmandineFlachs/bota — README, bot_generic.lua, run_dota2.py, run_agent.py, dota_sh.patch (сентябрь 2025), LICENSE (Apache-2.0) — ПТ.
- S28. OpenAI, «Dota 2 with Large Scale Deep Reinforcement Learning», arXiv:1912.06680 (2019). Оригинал заблокирован. Читал разобранную копию https://github.com/visual-snow/seshat/blob/main/parsed/openai/1912_06680.md — ПТ\*. Фрагмент блога OpenAI Five 2018 («observes every fourth frame… via Valve's Bot API») — в копиях на GitHub (ai-native-engineer/openai-mirror и др.) — ПТ\*.
- S29. https://github.com/tencent-ailab/hok_env — README (Apache-2.0; NeurIPS D&B 2022, arXiv:2209.08483) — ПТ.
- S30. Think in Games (TiG), arXiv:2508.21365 (29.08.2025) — С.
- S31. Hierarchical Macro Strategy Model for MOBA Game AI, AAAI 2019, arXiv:1812.07887 — С.
- S32. Tencent, система HoK 2020 (цифры побед) — С (wnhub.io, the-decoder).
- S33. «Towards Effective and Interpretable Human-Agent Collaboration in MOBA Games» (MCC), ICLR 2023, arXiv:2304.11632 — С.
- S34. SwarmBrain, arXiv:2401.17749 — С.
- S35. TextStarCraft II: https://github.com/sc2musa/Large-Language-Models-play-StarCraftII (arXiv:2312.11865) — ПТ (страница GitHub).
- S36. LLM-PySC2: https://github.com/NKAI-Decision-Team/LLM-PySC2 (README; arXiv:2411.05348) — ПТ.
- S37. Cradle: https://github.com/BAAI-Agents/Cradle (README; arXiv:2403.03186) — ПТ.
- S38. PokeLLMon: https://github.com/git-disl/PokeLLMon — README ПТ (только установка); статья arXiv:2402.01118 — П.
- S39. AlphaStar, условие на статистику z (Nature 2019) — С.
- S40. J. Orkin, «Three States and a Plan: The AI of F.E.A.R.», GDC 2006 — С.
- S41. Fluid HTN: https://github.com/ptrefall/fluid-hierarchical-task-network (README, MIT) — ПТ; T. Humphreys, «Exploring HTN Planners through Example», Game AI Pro — С.
- S42. IAUS: https://github.com/ProjectBorealis/IAUS/wiki — ПТ; доклады Dave Mark и Kevin Dill (GDC 2010, 2012) и IAUS (GDC 2015) — С.
- S43. D. Isla, «Handling Complexity in the Halo 2 AI», GDC 2005 — С.
- S44. Riot, «/dev: Leveling Up Bots» (behavior tree для ботов LoL) — С.
- S45. Dota 2 7.00 (декабрь 2016): бот-скрипты в Workshop — С (gamingonlinux).
- S46. Снимок файлов игры d2vpkr: https://github.com/dotabuff/d2vpkr (коммит «Client 6944», 05.10.2026), dota/scripts/npc/heroes/*.txt — ПТ, подсчёт мой.
- S47. Встроенный дамп API ботов в https://github.com/zmcmcc/Simple-AI/blob/master/FunLib/jmz_func.lua (дата дампа неизвестна); `GetModifierList` в живом коде https://github.com/PCMRShutnik/Rage-Trigger/blob/master/utilities.lua — ПТ.
- S48. «Learning Strategy Representation for Imitation Learning in Multi-Agent Games», arXiv:2409.19363 (2024) — С, содержание не проверено.
