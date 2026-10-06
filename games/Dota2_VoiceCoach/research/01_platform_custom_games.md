# 01. Платформа: кастомки Dota 2 (Workshop Tools, VScript Lua, Panorama)

Дата: 2026-10-06. Подготовил агент-исследователь (Claude) для игры «Тренер доты»: два человека, у каждого команда из 5 ИИ-героев, человек командует голосом и сам героев не кликает.

**Как читать статусы.**
- «полный текст» — файл или страницу я открыл и прочитал сам (git-клон, сырой файл).
- «полный текст, пересказ» — страница GitHub открыта через WebFetch. Этот инструмент возвращает пересказ малой моделью, поэтому дословность цитат не гарантирована.
- «сниппет» — видел только выдачу поиска.
- «по памяти» — мои знания, не проверены.

В скобках указан номер источника из списка в конце, например (полный текст, S4).

---

## Краткий итог

1. **Движок и API живы.** Инструменты обновлены 05.10.2026, дамп API — 23.04.2026, сообщество активно в 2026 году (S1–S4, S6, S10).
2. **Аркада осенью 2026 сломана.** Выделенных серверов нет, матч хостит ПК игрока; серверный HTTP в аркадных лобби не работает, `CreateHTTPRequestScriptVM` возвращает nil (S5a, S5b, S6). Ответа Valve не нашёл.
3. **10 ИИ-героев — проверенный путь.** `Tutorial:AddBot` + `SetBotThinkingEnabled(true)` на карте `dota`, поверх — свой ИИ через `ExecuteOrderFromTable` с «думанием» раз в 0.25–0.4 с. Так сделаны учебные аддоны Valve и Windy10v10AI, опубликованная в 2026 году (S4, S6).
4. **Нативный ИИ Valve** работает только со стандартными героями на карте dota (S2), а выключается сразу для обеих команд (S6).
5. **Стандартная карта:** строка `"maps" "dota"` в addoninfo (пример Valve «10v10», Windy); исходник `dota.vmap` входит в инструменты (S4).
6. **Голос в игру.** `$.AsyncWebRequest` удалён (S2, S4). Рабочий канал — скрытая `DOTAHTMLPanel` у клиента: только GET, ответ в заголовке страницы до 4096 символов (S6). Локальные каналы (клавиши, netcon) не проверены.
7. **Командир без героя:** функции в API есть (камера, выделение, раздача управления, фильтр приказов), готового примера не нашёл.
8. **Окружение:** инструменты только под Windows x64 (S4); игра и инструменты бесплатны (S3, по памяти).
9. **Риски.** Valve ломает инфраструктуру и API без ответов в трекере (май 2025, ноябрь 2025, август–сентябрь 2026; S5). Голосовой канал — недокументированный обход. На local host — преимущество хоста в пинге и штрафы за abandon (S5h). Правил об именах реальных игроков не нашёл; монетизация запрещена с 2023 года (сниппет, S15).
10. **Запасной путь:** обычное лобби Local Host со своими bot scripts — там есть HTTP на localhost и `InstallChatCallback` (S4, S7), и он не зависит от аркады.

---

## Ограничения этого исследования

- **Закрытые сайты.** Из контейнера недоступны (ни curl, ни WebFetch): developer.valvesoftware.com, moddota.com (статьи читал по исходникам на GitHub, S3), steamcommunity.com, reddit.com, dota2.com, liquipedia.net, steamdb.info, source2.wiki, web.archive.org, esports.gg, escorenews.com, luafun.readthedocs.io, fcalife.github.io. Если эти домены нужны, их можно добавить в настройках сетевого доступа облачного окружения: Network access → Custom → Allowed domains.
- **Лимит поиска.** Он общий на всех агентов хода (200 запросов) и закончился посреди работы. Вопросы 7 и 8 (правила Workshop, приватная публикация, своя MOBA) поэтому закрыты слабее остальных.
- **Отказы в доступе.**
  - Подключить репозиторий ValveSoftware/Dota2-Gameplay с доступом к API, чтобы прочитать комментарии к issue #35497, система разрешений не дала.
  - Клонировать OpenAngelArena/oaa, dota_imba и Legends-of-Dota-Redux система разрешений тоже не дала.
  - Как сделан ИИ в этих играх, я не проверил.

---

## 1. Жива ли платформа в 2025–2026

**Что говорит «за»**
- Инструменты обновляются вместе с игрой. Манифест депо 381450 (содержимое Workshop Tools) датирован 05.10.2026. В нём лежат `game\bin\win64\tools\hammer.dll`, `pet.dll`, `met.dll`, `modeldoc_editor.dll`, `sfm.dll`, `workshopmanager.dll` (полный текст, S4).
- API выгружается из живой игры. Заголовок дампа: `ProductName=dota2_workshop`, `VersionDate=Apr 23 2026` (полный текст, S2). Дамп обновляли под патчи:
  - 7.38 — 21.02.2025;
  - 7.39 — 25.05.2025;
  - 7.40 и 7.41 — 26–28.03.2026;
  - «Valve fixes» — 26.04.2026 (полный текст, S1).
- ModDota перевёл сайт на VitePress 07–08.03.2026, последний коммит — 28.03.2026 (полный текст, S3).
- Шаблоны:
  - TypeScriptAddonTemplate — последний коммит 08.02.2025 (полный текст, пересказ, S11).
  - x-template — последний коммит 23.05.2026; TypeScript + React-Panorama, шифрование Lua, OpenAPI-клиент к бэкенду, Node.js ≥ 16 (полный текст, S10).
- Активная опубликованная кастомка с ИИ-ботами — Windy10v10AI: коммиты идут в сентябре–октябре 2026 (полный текст, S6).
- Примеры Valve по-прежнему поставляются с игрой: manyplayer_example, tutorial_basics, tutorial_assist_game, npx_2019, overthrow, conquest, hero_demo, workshop_testbed, last_hit_trainer, addon_template (депо 373301, манифест 05.10.2026; полный текст, S4).

**Что говорит «против»: поломки и изменения**
- **Май 2025, патч 7.39.** Клиенты падают, если в команде кастомки больше 7 игроков; в 7.38 порог был больше 20. 12v12 и другие режимы временно урезали до 7 в команде (полный текст, пересказ, S5g). Dota 12v12 вернули к 12v12 «21 июня» (сниппет, S16; год в сниппете не указан, по контексту 2025).
- **Ноябрь 2025.** Новый тип `vectorws` сломал методы с векторами. В частности, сломаны `CDOTA_BaseNPC:MoveToPositionAggressive` и `SetExecuteOrderFilter`, а из `OnOrder` пропал параметр `new_pos` (полный текст, пересказ, S5e). В дампе апреля 2026 строки `vectorws` нет, и `MoveToPositionAggressive` принимает `Vector` (полный текст, S1, S2). Исправлено ли само поведение, я не проверял.
- **Июнь–июль 2026.** Одобренной (approved) новой кастомке не выделяется сервер, хотя локально она работает (полный текст, пересказ, S5d).
- **Август–сентябрь 2026.**
  - Неделями висит «Finding server», затем появляется сообщение «All dedicated servers are in use, one player's PC will host the match» (полный текст, пересказ, S5b, S5c).
  - Разработчик Windy10v10AI пишет в README (правка 02.10.2026): «Dota 2 不再给自定义游戏提供专用服务器，每一局都是玩家自己的机器当主机» — «Dota 2 больше не даёт кастомкам выделенных серверов, каждую игру хостит машина игрока» (полный текст, S6).
  - Заявления Valve не нашёл: комментарии к issue прочитать не смог.
- **Злоупотребления в аркаде.** Бот-лобби занимают серверы и накручивают онлайн (#31260, #33025, #35153, #35270; полный текст, пересказ, S5h).
- **Август 2023.** Юристы Valve потребовали прекратить любую монетизацию кастомок к 17 августа: сторонние платежи, пропуска, подписки, валюты, косметика (сниппет, S15).

**Только Windows? Нужно ли что-то покупать?**
- Инструменты работают только под Windows x64: в депо инструментов есть только `game\bin\win64` (полный текст, S4). У самой игры есть депо для macOS (`osx64`, 373304) и Linux (`linuxsteamrt64`, 373306) (полный текст, S4). Работают ли кастомки на Mac и Linux, не проверял. В 2015 году пользователи Linux писали, что инструментов под Linux нет (сниппет, S17).
- Инструменты ставятся как DLC: Steam → Dota 2 → «View Downloadable Content» → «Dota 2 Workshop Tools DLC» (полный текст, S3). Dota 2 и DLC бесплатны (по памяти).
- Нужна ли для публикации учётная запись Steam без ограничений (не limited), не выяснил. В выдаче поиска упоминалось требование «30 игр до доступа к Arcade» (сниппет, S15; первоисточник и дата неясны).

---

## 2. Как получить 10 ИИ-героев при 2 людях

**Функции.** Все есть в дампе апреля 2026 (полный текст, S1, S2):

| Функция | Что делает (описание из дампа) | Замечание |
|---|---|---|
| `Tutorial:AddBot(heroName, lane, difficulty, isGoodGuys) -> bool` | «Add a computer controlled bot» | путь Valve-туториала и Windy |
| `GameRules:AddBotPlayerWithEntityScript(heroName, playerName, team, entityScript, bool) -> hero` | «Spawn a bot player of the passed hero name, player name, and team» | своё имя бота и свой скрипт-мозг; смысл 5-го аргумента не выяснен, Valve передаёт `true` |
| `GameMode:SetBotThinkingEnabled(bool)` | «Enables/Disables bots in custom games. Note: this will only work with default heroes in the dota map.» | это описание самой Valve (сырой дамп, S2) |
| `SetBotsInLateGame`, `SetBotsAlwaysPushWithHuman`, `SetBotsMaxPushTier(-1 = off)`, `hero:SetBotDifficulty(int)` | настройки нативного ИИ | других «рычагов» влияния на нативных ботов в API не нашёл |
| `CreateHeroForPlayer(heroName, player)` | создаёт героя существующему игроку | для людей, а не для ботов |
| `GameRules:BotPopulate()` | «Fills all the teams with bots if cheat mode is enabled» | только с читами |
| консоль `dota_create_fake_clients` (cheat), `dota_bot_populate` (client_can_execute) | «Populates the remaining slots with fake clients / with bots» | средства разработки (полный текст, S4) |

По вики Valve, `dota_bot_populate` заполняет команды пассивными ботами до лимита. Если создать ботов больше лимита команды, сессия завершается (сниппет, S14).

**Как это сделано в работающем коде**
- **Valve, tutorial_assist_game.** Вызывает `SetBotThinkingEnabled(true)` и девять раз `Tutorial:AddBot("npc_dota_hero_…", "top|mid|bot", "passive", true|false)`. Сложность подстраивает через `hero:SetBotDifficulty(...)`. Аддон tutorial_basics устроен так же: `Tutorial:AddBot("npc_dota_hero_razor", "mid", "easy", false)` (полный текст, S4).
- **Valve, npx_2019.**
  1. Бот создаётся вызовом `GameRules:AddBotPlayerWithEntityScript(EntityName, BotName, Team, "ai/…/ai_sven.lua", true)`.
  2. Затем герою поднимают уровень (`HeroLevelUp`) и выдают предметы (`AddItemByName`).
  3. Скрипт сущности в `Spawn()` вызывает `thisEntity:SetContextThink("SvenThink", SvenThink, 0.25)`.
  4. Мозг возвращает следующий интервал (0.1–0.75 с) и отдаёт приказы через `ExecuteOrderFromTable` (полный текст, S4).
- **Windy10v10AI, опубликована, сентябрь 2026.**
  - Настройка: `SetCustomGameTeamMaxPlayers(GOODGUYS/BADGUYS, 10)`, `Convars.SetBool('dota_bot_mode', true)`, `Convars.SetBool('dota_bot_disable', false)`. Боты добавляются через `Tutorial.AddBot(heroName, '', 'unfair', isRadiant)` из жёсткого списка в 45 героев. Карты: `"maps" "dota hard custom"` (полный текст, пересказ, S6).
  - Гибрид:
    - На линии ходит и добивает нативный ИИ.
    - Точка перехода — сломано 1–2 башни, или средний уровень ботов выше порога, или прошло время: не раньше 4 минут, запасной порог 8–15 минут.
    - После точки перехода код вызывает `GameRules.GetGameModeEntity().SetBotThinkingEnabled(false)`, и дальше всем управляет свой ИИ: «мозг команды» раз в секунду, исполнитель героя раз в 0.4 с.
    - Комментарий в коде: «原生开关是全局的，一关两队的 bot 都关» — переключатель глобальный, выключает ботов обеих команд.
    - Причину гибрида код называет так: «добивание зависит от нативного ИИ» (полный текст, пересказ, S6).

**Подводные камни**
- **Нативный ИИ на других картах и героях.** С нестандартными героями и на других картах он не работает (S2).
- **Опубликованные игры, 2023 год.** Комбинация `AddBotPlayerWithEntityScript(..., "scripts/vscripts/bots/bot_generic.lua", true)` + `SetBotThinkingEnabled(true)` в Tools работала, а при запуске по ID из Workshop боты не думали. Issue закрыт как «stale» без исправления (полный текст, пересказ, S5f). Windy в 2026 году использует в опубликованной игре `Tutorial.AddBot` + `SetBotThinkingEnabled`, так что этот вариант рабочий (вывод из кода S6, сам не запускал).
- **Отключённый конвар в примерах Valve.** В hero_demo и workshop_testbed строка `SetBotThinkingEnabled(true)` закомментирована с пометкой «the ConVar is currently disabled in C++» (полный текст, S4). Когда написан комментарий, неизвестно.
- **Глобальный выключатель.** Нельзя оставить нативный ИИ одной команде и выключить другой (S6).
- **Экономика ботов.** Боты из `Tutorial.AddBot` — игроки (`PlayerResource:IsFakeClient` = true): золото, опыт, предметы и байбэк считаются как у людей. Windy ставит ботам цену байбэка через `PlayerResource:SetCustomBuybackCost`: 100000, пока работает нативный ИИ, потом формулу (полный текст, пересказ, S6). Нативные боты сами покупают предметы. Своему ИИ покупки нужно делать самому — у Windy для этого модуль `ai/build-item` (полный текст, пересказ, S6).
- **Герой из `CreateUnitByName`.** Такой герой «не управляем по умолчанию» (S1). Как у него с золотом, опытом и инвентарём, не проверял.
- **Лимиты игроков.** Константы: `DOTA_MAX_TEAM_PLAYERS = 24` (игроки без зрителей), `DOTA_MAX_PLAYERS = 64` (вместе со зрителями) (полный текст, S1). Есть баг 7.39 с больше чем 7 игроками в команде. Наша схема — человек + 5 ботов = 6 в команде.
- **Bot scripting API внутри кастомки.** Работают ли `bot_generic.lua`, `mode_*.lua`, `team_desires.lua` из аддона внутри кастомки, подтверждений не нашёл. Функции `InstallChatCallback` в API vscripts нет: это функция бот-API обычных лобби (полный текст, S1, S7). В кастомке чат ловится событием `player_chat` с полями `teamonly`, `userid`, `playerid`, `text` (полный текст, S1).
- **`dota_bot_allow_human_control`.** Конвар существует (cheat, по умолчанию false) (полный текст, S4); что он делает, не выяснил.

**Вывод.** По 5 ботов на команду через `Tutorial:AddBot` (или `AddBotPlayerWithEntityScript`, если нужны свои имена и скрипт-мозг) на карте dota, а поверх — свой ИИ по схеме Windy.

---

## 3. Управление юнитами из vscripts, производительность, примеры

- **Приказы.**
  - Основной способ: `ExecuteOrderFromTable({UnitIndex, OrderType, TargetIndex, AbilityIndex, Position, Queue})` — «Issue an order from a script table» (S1). Примеры: ModDota 2015 (S3), Valve npx_2019 (S4), Windy (S6).
  - Обёртки: `MoveToPosition`, `MoveToPositionAggressive` (attack-move), `CastAbilityOnTarget`, `CastAbilityOnPosition` (S1).
- **«Думание».**
  - Функции: `SetContextThink(name, fn, interval)`, `SetThink(...)` (S1).
  - Valve npx_2019: первый вызов через 0.25 с, дальше 0.1–0.75 с (S4).
  - Windy: модификатор с `StartIntervalThink` раз в 0.4 с на героя, команда — раз в 1 с (S6).
- **Подвох с атаками.** Если повторять ATTACK_MOVE или ATTACK_TARGET слишком часто (например, раз в 0.1 с), замах атаки всё время сбрасывается. Об этом пишет разработчик Windy в `src/vscripts/CLAUDE.md` (полный текст, пересказ, S6).
- **Производительность.**
  - Замеров вида «10 героев с думанием раз в 0.1–0.3 с» я не нашёл.
  - Практика: у Windy в опубликованной игре 10 и больше ИИ-героев думают раз в 0.4 с (S6).
  - dotaservice запускал игру с `-nowatchdog` и комментарием «WatchDog will quit the game if e.g. the lua api takes a few seconds» (полный текст, S8). Вывод: в Lua ничего нельзя блокировать, внешние запросы — только асинхронные.
- **Фильтр приказов.** `SetExecuteOrderFilter(fn, ctx)`: вернуть false — отменить приказ, изменить таблицу — подменить его (полный текст, S3, статья 2016). В ноябре 2025 сообщали, что фильтр сломан (S5e); работает ли он сейчас, не проверял.
- **Кастомки с ИИ-героями.**
  - Windy10v10AI: гибрид нативного ИИ и своего на TypeScript → Lua. Модули `ai/ability`, `action`, `build-item`, `hero`, `item`, `team`, `ward`. «Мозг команды» решает:
    - пушить одну линию или две;
    - драться всей командой или не драться;
    - строиться веером: ближний бой впереди, дальний по флангам;
    - идти на Рошана — только если сила половины команды больше силы Рошана;
    - как защищаться по ярусам: внешние башни можно отдать, базу держать (полный текст, пересказ, S6).
  - Valve npx_2019 — сценарные боты на скриптах сущностей; учебные аддоны Valve — нативные боты (полный текст, S4).
  - Holdout (пример Valve): ModDota для сложного ИИ юнитов советует смотреть «holdout_example's lua ai scripts» (полный текст, S3).
  - Overthrow: в текущих скриптах аддона кода ботов нет (полный текст, S4).
  - Angel Arena (OAA), Dota IMBA, Legends of Dota Redux, Custom Hero Chaos: как сделан ИИ, не проверено. Репозитории OAA, IMBA и LoD Redux есть в списке открытых игр ModDota (полный текст, S3).

---

## 4. Командир без своего героя

**Что есть в API** (полный текст, S1, S2)

Сервер:
- `PlayerResource:SetCameraTarget(pid, ent|nil)`;
- `PlayerResource:SetOverrideSelectionEntity(pid, ent)` и `GameMode:SetOverrideSelectionEntity(ent)` — «вместо героя игрока»;
- `unit:SetControllableByPlayer(pid, skip)`;
- `PlayerResource:SetUnitShareMaskForPlayer(pid, otherPid, flag, state)`;
- `GameMode:SetCustomGameForceHero(name)`;
- `PlayerResource:ReplaceHeroWith(pid, class, gold, xp)`;
- `AddFOWViewer`, `SetFogOfWarDisabled`.

Panorama:
- камера: `GameUI.SetCameraTarget`, `SetCameraTargetPosition(vec, lerp)`, `MoveCameraToEntity`, `SetCameraDistance`, `SetCameraYaw`;
- выделение и мышь: `GameUI.SelectUnit`, `GameUI.SetMouseCallback`, `GetScreenWorldPosition`, `FindScreenEntities`;
- `GameUI.PingMinimapAtLocation(vec3)` — «Create a minimap ping at the given location»;
- `Game.PrepareUnitOrders`, `Game.AddCommand`, `Game.ServerCmd`, `Players.IsSpectator(pid)`;
- `GameEvents.SendCustomGameEventToServer`.

**Кнопки приказов (запасной вариант к голосу).** Панель Panorama шлёт `GameEvents.SendCustomGameEventToServer`, сервер ловит `CustomGameEventManager:RegisterListener` — так сделано в tutorial_assist_game (полный текст, S4). Горячие клавиши задаются в `addoninfo.txt` → `Default_Keys` и ловятся через `Game.AddCommand(...)` в Panorama (полный текст, S3, 2015).

**Варианты роли человека** (готового примера кастомки с такой ролью не нашёл)
- **(а) Игрок с героем-пустышкой.** `ReplaceHeroWith` меняет героя на невидимого неуязвимого «командира», а `SetOverrideSelectionEntity` задаёт выделение. Приём распространённый (по памяти), нужен пилот.
- **(б) Игрок команды, который не управляет ботами напрямую.** Боты принадлежат бот-игрокам, и человек ими не управляет, пока ему не выдадут `SetControllableByPlayer` или `SetUnitShareMaskForPlayer`. Прямое управление «по желанию» включается выдачей доступа. Но свой ИИ на это время надо приостанавливать, иначе он перебьёт приказы человека (вывод, не проверено). Запретить прямые клики можно и фильтром приказов, но см. п. 3 о поломке в ноябре 2025.
- **(в) Зритель.** Зрители есть в константах и в Panorama (S1, S2). Может ли зритель слать custom events, не выяснил.
- **Пинги на миникарте.** Отдельного серверного события «пинг игрока» в дампе событий не нашёл. Пинг можно заменить кликом мыши, пойманным в Panorama (`SetMouseCallback` + `GetScreenWorldPosition`), и отправкой координат на сервер (вывод из API).

---

## 5. Связь с внешним миром (ключевое)

**Каналы и их состояние на октябрь 2026**

| Канал | Состояние | Статус, источник |
|---|---|---|
| `$.AsyncWebRequest` (Panorama, клиент) | Удалён. В дампе: «Make a web request (disabled)», в бинарнике panorama: «ERROR: AsyncWebRequest has been removed.» | полный текст, S2 (апр. 2026), S4 (окт. 2026) |
| `CreateHTTPRequestScriptVM` (серверный Lua) | Функция есть. В аркадных лобби возвращает nil, HTTP не уходит. README Windy: «游廊里开的对局服务端发不出 HTTP» — «сервер матча, открытого из аркады, не может слать HTTP» и «能不能发 HTTP 取决于启动方式，与单人多人无关» — «можно ли слать HTTP, зависит от способа запуска, а не от числа игроков». У трёх игр «1x1 … CUP» сломались рейтинги и лидерборды, разработчики подозревают белый список | полный текст, S6 (19.09–02.10.2026); полный текст, пересказ, S5a (19.09.2026) |
| То же при запуске из консоли (`dota_launch_custom_game`) или из Tools | HTTP работает, но другие игроки подключиться не могут | полный текст, S6 (таблица в README) |
| `GetDedicatedServerKey`, `V2`, `V3` | Функции есть, описание только «( version )». В x-template ключ получают внутриигровой командой `get_key_v3 [version]`; локальный тестовый ключ там — строка `Invalid_NotOnDedicatedServer`. Без выделенных серверов ключ теряет смысл | полный текст, S1, S2, S10 |
| Скрытая `DOTAHTMLPanel` в Panorama (клиент) | **Рабочий обход Windy (сентябрь 2026)**, подробности ниже | полный текст, S6 (README, PR #2438, #2446) |
| HTTP в бот-API обычных лобби | `CreateHTTPRequest(url)` — только localhost, `CreateRemoteHTTPRequest(url)` — удалённые адреса. В `server.dll` есть строки «Create a localhost HTTP request.» и «Create a remote HTTP request.» (`Script_CreateLocalHostHTTPRequestBotVM` и `…RemoteHTTPRequestBotVM`). Для кастомок не годится | полный текст, S7 (док OHA), S4 (строки бинарника) |
| WebSocket | В API Panorama и VScript не нашёл | полный текст, S2 (по отсутствию) |
| GSI (Game State Integration) | Работает только наружу: игра шлёт JSON POST на локальный HTTP. Во время игры отдаёт данные только своего игрока, в режиме зрителя — всех. Команды в игру не передаёт | полный текст, пересказ, S12 |
| Чат | Сервер получает событие `player_chat` (text, playerid, teamonly) | полный текст, S1 |
| Горячие клавиши | `Default_Keys` + `Game.AddCommand` работают. Принимает ли игра «нажатия» от внешней программы, не проверено | полный текст, S3; остальное — вывод |
| Сетевая консоль (netcon) | В `engine2.dll` есть `CNetConsoleMgr` и строка «Unable to open netconsole on port %d». Имени параметра запуска в строках нет. SourceBridge проверял `-netconport 2121` только на Portal 2, L4D2 и CS:GO | полный текст, S4; полный текст, пересказ, S13 |
| Консольные команды | `Convars:RegisterCommand` + `Convars:GetCommandClient` есть. Может ли клиент вызвать серверную команду в опубликованной игре, не проверено | полный текст, S1 |

**Как устроен канал через `DOTAHTMLPanel` у Windy**

Механика:
- Сервер выбирает готового игрока-человека и шлёт ему адрес запроса.
- Клиент создаёт панель: `$.CreatePanel('DOTAHTMLPanel', …)`, размер 1×1 px, прозрачность 0.01, затем `panel.SetURL(url)`.
- Бэкенд кладёт ответ в `<title>` страницы.
- Клиент ловит событие `HTMLTitle` и отправляет данные на сервер через `GameEvents.SendCustomGameEventToServer` (полный текст, пересказ, PR #2438; полный текст, README, S6).
- Строки `DOTAHTMLPanel`, `HTMLTitle` и `HTMLFinishRequest` есть в `client.dll` (полный текст, S4).

Ограничения (README Windy, полный текст, S6):
- только GET, заголовки запроса передать нельзя;
- ответ в заголовке — не больше 4096 символов;
- длина URL — до 7427 символов (ограничение CDN, а не движка);
- страница грузится браузерным движком, он учитывает заголовки ответа и кэширует, поэтому в каждый URL добавляют случайный параметр;
- таймаут одного запроса — 10 с (PR #2438);
- запись идёт как «GET с побочным эффектом», тело передаётся в query в base64url;
- API-ключ, упакованный в карту, может быть извлечён;
- для материкового Китая канал не работает: облако Tencent отдаёт `Content-Disposition: attachment`.

**Что реально используют кастомки с бэкендом**
- До августа 2026 — серверный HTTP к своему бэкенду: рейтинги, лидерборды, сохранения (S5a); x-template даёт OpenAPI-клиент и ключ сервера (S10).
- С сентября 2026 — клиентский ретранслятор через `DOTAHTMLPanel` (S6). Windy называет его «единственным каналом, который работает в сети, а не запасным».

**Схема голосового канала для нашей игры** (вывод, проверить пилотом)
1. Голос распознаётся на ПК или телефоне и уходит на наш облачный ретранслятор.
2. В клиенте каждого игрока скрытая `DOTAHTMLPanel` опрашивает ретранслятор, команда приходит в `<title>`.
3. Panorama отправляет её на сервер через `GameEvents`.
4. Серверный Lua передаёт команду ИИ своей пятёрки.

Запасной канал без сети: голосовое приложение на том же ПК «нажимает» клавиши, а `Default_Keys` / `Game.AddCommand` превращают их в команды.

Задержка ретранслятора — от долей секунды до секунд. Поэтому голосом передаются только макрокоманды («пушим верх», «все на Рошана»), а микро каждый герой делает сам внутри Lua — как и хочет автор. Состояние игры наружу (для слоя ИИ вне игры) можно отдавать тем же каналом: GET с параметрами, до ~7000 символов на запрос (вывод из S6).

**Что не выяснено по каналу:**
- может ли `DOTAHTMLPanel` открыть `http://localhost`;
- исполняется ли JavaScript на странице и обновляется ли заголовок без перезагрузки (long-poll внутри страницы);
- допустимая частота опроса;
- есть ли из панели доступ к микрофону.

---

## 6. Карта

- **Стандартная карта.** Достаточно строки `"maps" "dota"` в `addoninfo.txt`. Пример Valve — manyplayer_example («10v10 Mode Loaded!»):
  - `MaxPlayers 20`, `SetCustomGameTeamMaxPlayers(…, 10)` на обе команды;
  - фильтры золота и опыта;
  - `SetFreeCourierModeEnabled(true)`;
  - `GameRules:BotPopulate()` при запуске с ключом `-addon_bots` (полный текст, S4).
  
  Windy: `"maps" "dota hard custom"`, `MaxPlayers 10` (полный текст, пересказ, S6).
- **Исходник карты.** `content\dota\maps\dota.vmap` (63 351 821 байт) входит в Workshop Tools (депо 381450, 05.10.2026). Его можно скопировать в аддон и править. В игре лежат и прошлые версии карты: `dota_683.vpk`, `dota_685.vpk` … `dota_737.vpk` (полный текст, S4). Вики Valve упоминает примеры `dota_pvp.vmap` и `simple_dota_map_example.vmap` (сниппет, S14).
- **Стандартные герои, предметы, крипы, Рошан.** На карте dota они работают по обычным правилам: учебные аддоны Valve и Windy играют стандартную доту, у Windy есть логика Рошана для ИИ (полный текст, S4, S6). Что карта `dota` в кастомке всегда соответствует текущему патчу, я вывел, но не проверял.
- **Размер команды.**
  - `GameRules:SetCustomGameTeamMaxPlayers(team, n)`; в дампе у неё ошибочное описание «Set whether a team is selectable…» (S1).
  - `MaxPlayers` в addoninfo задаёт число людей на карту (S4).
  - Потолок — 24 игрока без зрителей (S1).
  - Баг 7.39 с больше чем 7 игроками в команде — см. п. 1.
- **Нативные боты работают только на карте dota** (S2) — ещё одна причина брать её.

---

## 7. Публикация, игра вдвоём, правила

- **Публикация.** В составе инструментов есть `workshopmanager.dll` (полный текст, S4); что публикуют именно им — по памяти.
- **Способы запуска** (таблица в README Windy, полный текст, S6):

| Как запущена игра | HTTP с сервера | Могут ли подключиться другие |
|---|---|---|
| Лобби в аркаде | нет | да |
| Консоль `dota_launch_custom_game` или Tools | да | нет |
| «Свой выделенный сервер в будущем» (строка из таблицы Windy) | да | да |

  Можно ли сейчас поднять свой выделенный сервер для кастомки, не проверено.
- **Что из этого следует.**
  - Сыграть вдвоём через интернет в неопубликованную кастомку штатно нельзя (вывод по S6).
  - Нужен опубликованный предмет Workshop и лобби в аркаде, где сейчас хостит ПК одного из игроков (S5b, S6).
  - В обычной доте друг подключается по LAN через `sv_lan 1` и `connect <IP>` (полный текст, пересказ, S7, #135); для кастомки это не проверял.
  - Видимость предмета «Friends-only» или «Hidden» и можно ли играть в скрытую кастомку, не выяснил.
  - У кастомок есть статус «одобренной» (S5d), процесс одобрения не выяснил.
- **Риски хостинга на ПК игрока** (полный текст, пересказ, S5h):
  - хост получает штраф за abandon, если гость не загрузился (#35522, 20.09.2026);
  - штраф начисляют и в local host кастомке (#35651, 30.09.2026);
  - local host лобби закрываются через несколько секунд после входа игрока (#35325, 10.09.2026);
  - хост играет с нулевым пингом, что нечестно в матче двух командиров (вывод).
- **Монетизация** запрещена с 17.08.2023 (сниппет, S15). В коде Windy есть модули оплаты (alipay) (полный текст, пересказ, S6); как это согласуется с запретом, не выяснял.
- **Внешние серверы** на практике использовались (S5a, S10). Письменных правил Valve о них не нашёл.
- **Реальные имена и образы известных игроков.** Правил Workshop или Valve по этому вопросу не нашёл: поиск закончился. Рекомендация: без согласия не использовать ники, лица и голоса; описывать агентов как стиль («агрессивный керри, оцифрованный по реплеям»), а реальные имена держать только в закрытой локальной сборке.

---

## 8. Запасные пути

**A. Обычное лобби Local Host + свои bot scripts** (полный текст, S7, S4)

Что известно:
- Open Hyper AI работает на 7.41/7.41a (последний коммит 02.04.2026), поддерживает 127 героев.
- Режим: Custom Lobby + Local Host.
- Есть команды в чате (`!pos`, `!pick`, `!ban`) через `InstallChatCallback` и ответ на пинги людей.
- HTTP из бот-скриптов: `CreateHTTPRequest` (localhost) и `CreateRemoteHTTPRequest`.
- Полный VScript подключается так: `sv_cheats 1; script_reload_code bots/fretbots` при включённой галке «Enable Cheats» (FretBots, #68). Через это FretBots шлёт HTTPS-запросы к чат-боту (`FretBots/Chat.lua`).
- Офлайн и LAN: `sv_lan 1`, `dota_bot_practice_script <id>`, `map dota` (#135).
- Структура бот-API (S7): `mode_*_generic.lua` (`GetDesire`/`Think`), `team_desires` (`TeamThink`), `ability_item_usage_*`, `item_purchase_*`, `bot_generic.lua` (`Think`, `MinionThink`).

Плюсы:
- вся Дота целиком: карта, герои, предметы, Рошан, текущий патч;
- голос подключается просто: приложение на ПК хоста поднимает HTTP на localhost, бот-скрипт его опрашивает;
- путь не зависит от аркадных серверов.

Минусы:
- работает только на локальном хосте;
- своего интерфейса Panorama и камеры командира нет: люди — зрители или игроки обычного лобби;
- бот-API беднее VScript;
- путь FretBots требует читов;
- голос второго игрока надо доставлять на ПК хоста через ретранслятор.

**B. ML-обвязка уровня dotaservice** (полный текст, S8; проект 2019 года)
- Состояние уходит наружу через сокеты: `-botworldstatetosocket_radiant/_dire`, `-botworldstatetosocket_frames`, `-botworldstatesocket_threaded`.
- Действия передаются Lua-файлами, которые бот-скрипт читает через `loadfile`.
- Плюс: полный контроль из Python.
- Минусы: только локально; работает ли в 2026 году, не проверено.

**C. Своя MOBA на другом движке** (по памяти)
- Плюсы: полный контроль над голосом, ИИ и сетью; нет зависимости от решений Valve.
- Минусы: месяцы только на базовые механики (поиск пути, сеть, способности, предметы); героев и карты Доты не будет из-за авторских прав, поэтому «звёзд» придётся переносить в свою механику, и сравнение «как в Доте» теряется.

**Рекомендация.**
- Основной путь — кастомка на карте dota: 10 ботов через `Tutorial:AddBot`, свой ИИ поверх (как у Windy), голос через клиентский канал.
- Параллельно — пилот пути A (лобби + bot scripts + HTTP на localhost). Он не зависит от сломанной аркадной инфраструктуры и быстрее даёт первую работающую игру на одном ПК.

---

## Что не удалось выяснить

1. Ответила ли Valve по поводу выделенных серверов и HTTP в кастомках: комментарии к #35497, #35302, #35085 не прочитаны.
2. Может ли `DOTAHTMLPanel` грузить `http://localhost`; работает ли на странице JavaScript и long-poll с обновлением заголовка; каковы задержка и допустимая частота; есть ли доступ к микрофону.
3. Работает ли в Dota 2 сетевая консоль (`-netconport`) и принимает ли Panorama нажатия клавиш от внешней программы.
4. Работает ли `AddBotPlayerWithEntityScript` + свой скрипт-мозг в опубликованной игре в 2026 году (проблема 2023 года касалась нативного думания).
5. Влияют ли bot scripts аддона (`mode_*.lua` и др.) на нативных ботов внутри кастомки; что делает `dota_bot_allow_human_control`.
6. Какие герои поддерживаются нативным ИИ Valve. У Windy список из 45 героев, причина не проверена.
7. Как правильно сделать человека без героя (пустышка, зритель, свой юнит); может ли зритель слать custom events.
8. Работает ли сейчас `SetExecuteOrderFilter` после жалобы ноября 2025.
9. Замеры нагрузки: 10 героев с думанием раз в 0.1–0.3 с на ПК хоста.
10. Приватная публикация (Friends-only / Hidden), процесс одобрения кастомок, можно ли играть вдвоём в неопубликованную кастомку через интернет.
11. Правила Workshop и Valve о реальных именах игроков и о внешних серверах; текущий текст правил монетизации.
12. Требование «30 игр для Arcade»: актуально ли оно в 2026 году.
13. Как сделан ИИ в OAA, IMBA, LoD Redux, Custom Hero Chaos.
14. Как устроен процесс публикации через Workshop Manager — описываю по памяти.

## Что проверить пилотом до проектирования (предложение)

1. Опубликовать скрытый тестовый предмет. Запустить лобби вдвоём (local host): 6 + 6 игроков, 10 ботов через `Tutorial:AddBot`, `SetBotThinkingEnabled` в обе стороны.
2. Проверить `DOTAHTMLPanel` с нашим URL: задержку команды «голос → действие героя», частоту, localhost, работу JavaScript.
3. Проверить виртуальные клавиши → `Default_Keys` / `Game.AddCommand` → событие на сервере.
4. Запустить с `-netconport` и подключиться по telnet.
5. Сделать командира-пустышку: `ReplaceHeroWith` или `SetCustomGameForceHero` + `SetOverrideSelectionEntity` + камера Panorama.
6. Проверить `SetExecuteOrderFilter`: блокировку прямых кликов и выдачу управления по опции.
7. Замерить нагрузку на ПК хоста: 10 героев с думанием раз в 0.1, 0.2 и 0.4 с.

---

## Источники

| № | Источник | Дата | Статус |
|---|---|---|---|
| S1 | ModDota/dota-data: README; `files/vscripts/api.json`, `enums.json`, `files/events.json`; история коммитов. https://github.com/ModDota/dota-data | последний коммит 26.04.2026 (5a6b445) | полный текст (git-клон) |
| S2 | ModDota/dota-data, `dumper/dump` — сырой дамп из игры (`script_reload`, `cl_panorama_typescript_declarations`), заголовок `ProductName=dota2_workshop`, `VersionDate=Apr 23 2026`. https://github.com/ModDota/dota-data/blob/master/dumper/dump | 23.04.2026 | полный текст |
| S3 | ModDota/moddota.github.io — исходники moddota.com: getting-started (22.02.2015), units/adding-a-very-simple-ai-to-units (27.07.2015), scripting/using-dota-filters (26.06.2016), panorama/keybindings (24.07.2015), tools/useful-console-commands (22.02.2015), tools/github-repos-and-search. https://github.com/ModDota/moddota.github.io | последний коммит 28.03.2026 | полный текст |
| S4 | SteamDatabase/GameTracking-Dota2, коммит 36e1e3d: `DumpSource2/commands.txt`, `convars.txt`; строки бинарников `server`, `client`, `engine2`, `panorama`, `tier0`; манифесты депо 373301, 373303, 373304, 373306, 381450; аддоны Valve в `game/dota_addons/*`. https://github.com/SteamDatabase/GameTracking-Dota2 | 05.10.2026 | полный текст |
| S5a | ValveSoftware/Dota2-Gameplay #35497 «[Custom Games] External HTTP requests stopped working in all our custom games». https://github.com/ValveSoftware/Dota2-Gameplay/issues/35497 | 19.09.2026 | полный текст, пересказ (без комментариев) |
| S5b | там же, #35302 «Dedicated servers are down, forcing Local Host…». https://github.com/ValveSoftware/Dota2-Gameplay/issues/35302 | 09.09.2026 | полный текст, пересказ |
| S5c | там же, #35085 «Please provide an official update — … Dedicated Server allocation is still broken»; #35151. https://github.com/ValveSoftware/Dota2-Gameplay/issues/35085 | 30.08.2026; 01.09.2026 | полный текст, пересказ |
| S5d | там же, #33276 и #33945 «Approved custom game never gets a dedicated server». https://github.com/ValveSoftware/Dota2-Gameplay/issues/33276 | 26.06.2026; 27.07.2026 | полный текст, пересказ |
| S5e | там же, #29281 «Many issues within workshop tools/custom game». https://github.com/ValveSoftware/Dota2-Gameplay/issues/29281 | 16.11.2025 | полный текст, пересказ |
| S5f | там же, #13919 «SetBotThinkingEnabled does not work when Custom Game is launched from dota». https://github.com/ValveSoftware/Dota2-Gameplay/issues/13919 | 29.11.2023 | полный текст, пересказ |
| S5g | там же, #25846 и #26044 «Adding/Assigning more than 7 players to a team crashes clients». https://github.com/ValveSoftware/Dota2-Gameplay/issues/26044 | 23.05.2025; 27.05.2025 | полный текст, пересказ |
| S5h | там же, списки поиска по трекеру: #35325, #35522, #35651, #34354, #31260, #33025, #35153, #35270, #33958, #27612, #27626, #29189, #25971, #12628 | просмотрено 06.10.2026 | полный текст, пересказ (только заголовки и даты) |
| S6 | windy10v10ai/game («10v10 AI custom by windy», Workshop 2307479570): `src/vscripts/api/README.md` — сырой файл, правка 02.10.2026, **полный текст**. Пересказ: issue #2435 (19.09.2026), PR #2438 (20.09.2026), PR #2446 (21.09.2026), `content/panorama/scripts/custom_game/api_html_proxy.js`, `src/vscripts/ai/team/README.md`, `bot-team.ts`, `takeover.ts`, `ai/hero/bot-base.ts`, `modules/GameConfig.ts`, `modules/hero/hero-pick.ts`, `hero-buyback.ts`, `game/addoninfo.txt`, `src/vscripts/CLAUDE.md`. https://github.com/windy10v10ai/game | сентябрь–октябрь 2026 | README — полный текст; остальное — полный текст, пересказ |
| S7 | forest0xia/dota2bot-OpenHyperAI: README, `docs/BOT_API_REFERENCE.md`, `bots/hero_selection.lua`, `bots/ability_item_usage_generic.lua`, `bots/FretBots/Chat.lua`, `bots/ts_libs/utils/http_utils/http_req.lua`. Discussions #68 (24.05.2025, последний комментарий 09.05.2026) и #135 (02.04.2026). https://github.com/forest0xia/dota2bot-OpenHyperAI | коммит cb814c6, 02.04.2026 | файлы — полный текст (клон); discussions — полный текст, пересказ |
| S8 | TimZaman/dotaservice: `dotaservice/dotaservice.py`, `lua/bot_generic.lua`, README. https://github.com/TimZaman/dotaservice | 18.07.2019 | полный текст |
| S9 | Nostrademous/Dota2-WebAI: README, `webserver_out.lua`, `web_config.lua` (HTTP из бот-скриптов на 127.0.0.1:2222). Issue #25 о `CreateHTTPRequestScriptVM`, равном nil в бот-VM. https://github.com/Nostrademous/Dota2-WebAI | 28.09.2017; issue 17.08.2017 | полный текст; issue — полный текст, пересказ |
| S10 | XavierCHN/x-template: README (сырой файл); страница коммитов (последний 23.05.2026; 28.04.2026 — «replace IsInToolsMode() with steamid whitelist for get_key_v3/v2»). https://github.com/XavierCHN/x-template | 2026 | README — полный текст; коммиты — полный текст, пересказ |
| S11 | ModDota/TypeScriptAddonTemplate: страница репозитория и коммиты. https://github.com/ModDota/TypeScriptAddonTemplate | последний коммит 08.02.2025 | полный текст, пересказ |
| S12 | antonpup/Dota2GSI, README. https://github.com/antonpup/Dota2GSI | дата не видна | полный текст, пересказ |
| S13 | DaryeDev/SourceBridge, README (NetCon проверялся на Portal 2, L4D2, CS:GO). https://github.com/DaryeDev/SourceBridge | дата не видна | полный текст, пересказ |
| S14 | Valve Developer Community (из контейнера закрыт): «Creating A Dota-Style Map», «Simulating Players During Development», «Using CreateHTTPRequest», «CDOTATutorial.AddBot». https://developer.valvesoftware.com/wiki/Dota_2_Workshop_Tools | даты не видны | сниппет |
| S15 | Запрет монетизации, 2023: esports.gg «Valve to stop all forms of monetization in the Dota 2 Arcade»; Steam-обсуждение «The Dota 2 Arcade Is Being Forced To Shut Down»; xfire. В той же выдаче — упоминание «30 игр до доступа к Arcade». https://esports.gg/news/dota-2/valve-to-stop-all-forms-of-monetization-in-the-dota-2-arcade/ | август 2023 | сниппет |
| S16 | Журнал изменений Dota 12v12 (Steam Workshop 1576297063): 7v7 после 7.39, возврат к 12v12 «21 июня». https://steamcommunity.com/sharedfiles/filedetails/changelog/1576297063 | год не указан (по контексту 2025) | сниппет |
| S17 | GamingOnLinux, комментарии к «Dota 2 Reborn now officially supports Linux» (инструментов под Linux нет). https://www.gamingonlinux.com/2015/06/dota-2-reborn-now-officially-supports-linux-early-look/ | июнь 2015 | сниппет |
