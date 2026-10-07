# Промпт агента-разметчика B (PARSE-02, вторая разметка), дословно

Запущен 2026-10-07T08:28:40.117Z. Вход — тексты набора без разметки A (`texts.jsonl`: id, category, text).

```text
Ты помогаешь проекту «голосовой тренер Dota 2». Дословное сообщение автора проекта: «Привет. Делаем игру. Тренер доты. Голосовое управление 5 агентами с навыками известных игроков. Отцифровоть игроков в доту по по файлам или видео. В итоге это должна быть кастомка. В которой ты опосредовано, голосом управляет игроками. Но каждый агент свои Мусы делает сам я готов потратить на прожкт пару месяцев с норм подпиской. Не торопись сделай все с самого начала хорошо. ИИ в начале поиск в интернете. Помнивпо итогу Костромка на 2 игроков. Который каждый управляет своей командой звёзд. Или даже просто игроков в доту. Их тоже можно оцифровать любоготдаже на 2 ммр в репозиьарии создай отдельную папку». Последнее сообщение автора: «Продолжи».

Задача: НЕЗАВИСИМАЯ вторая разметка набора фраз тренера (PARSE-02). Другой человек уже разметил эти фразы; твоя разметка нужна, чтобы проверить саму разметку (где два разметчика расходятся — фраза спорная). Ты размечаешь смысл каждой фразы по протоколу ниже — как понял бы её игрок-исполнитель.

Вход: /tmp/claude-0/-home-user-Neu/c2746a83-5006-51b9-9f59-346f06e713bc/scratchpad/parse02_B/texts.jsonl — 80 строк вида {"id", "category", "text"}. Категория — замысел автора фразы: simple; multi (2–3 приказа); modal (отрицание, «потом», «срочно», исправление себя); hard (двусмысленные, сведения вместо приказа, необычные обороты); asr (в тексте ошибки распознавания речи — восстанови, что человек на самом деле сказал, и размечай задуманный смысл).

ЗАПРЕЩЕНО открывать, читать или искать что-либо в /home/user/Neu/ (код разборщика, тесты, первая разметка, отчёты) и где-либо ещё, кроме своего входного файла и своей рабочей папки /tmp/claude-0/-home-user-Neu/c2746a83-5006-51b9-9f59-346f06e713bc/scratchpad/parse02_B/. Интернет не нужен. Не подстраивайся ни под какой разборщик. Работай экономно: прочитай вход, напиши выходной файл одним проходом, проверь его коротким скриптом (запускай python3 -I).

Контекст матча (одинаковый для всех фраз): команда тренера — Dire (Тьма). Для Dire лёгкая линия (сейф) — top, сложная (оффлейн) — bot. Свои агенты: позиция 1 — «Петя», герой Juggernaut (джагг); позиция 2 — «Серёга», Storm Spirit (шторм); позиция 3 — «Лёха», Axe (акс); позиция 4 — «Дима», Rubick (рубик); позиция 5 — «Вова», Witch Doctor (вд, доктор). Враги: Anti-Mage (ам, антимаг), Invoker (инвокер, инвок), Mars (марс), Earthshaker (шейкер), Crystal Maiden (цмка, кристалка).

Язык команд (протокол v1). Фраза превращается в список команд; команда = action + agents (список позиций 1..5, кому приказ; по возрастанию) + params. Действия и параметры:
- farm {area: lane|jungle_own|jungle_enemy|ancients|auto, lane?: top|mid|bot} (если место не названо — area auto)
- push {lane: top|mid|bot|auto, tier?: 1..4}
- defend {lane или place: base, tier?}
- gank {lane?, enemy?: npc_dota_hero_*, enemy_pos?: 1..5}
- group {place?|lane?} — собраться
- roshan {} ; tormentor {}
- smoke {then?: gank, lane?, enemy?}
- retreat {place?: base}
- focus {enemy: npc_dota_hero_* или enemy_pos: 1..5}
- engage {enemy?}
- hold {what?: действие, которое запрещено}
- split {lane}
- ward {place?: rune|roshan|jungle_own|jungle_enemy|..., lane?, kind?: sentry}
- stack {place?: ancients}
- buy {item: item_*} ; use_item {item: item_*}
- buyback {} ; use_ult {enemy?} ; save_ult {}
- save {ally: позиция} ; follow {ally: позиция}
- tp {place|lane} ; move {place|lane}
- free {} (играйте сами) ; cancel {} (отмена) ; report {} (доклад)
Если адресат не назван: командные действия (push, defend, group, roshan, tormentor, smoke, retreat, focus, engage, hold, free, cancel, report) идут всем [1,2,3,4,5]; если глагол во множественном числе («фармите») — всем; иначе адресат неясен — тогда "clarify": true и agents: []. «Остальные» — все, кого ещё не назвали в этой фразе. Внутренние имена героев: npc_dota_hero_juggernaut, npc_dota_hero_storm_spirit, npc_dota_hero_axe, npc_dota_hero_rubick, npc_dota_hero_witch_doctor, npc_dota_hero_antimage, npc_dota_hero_invoker, npc_dota_hero_mars, npc_dota_hero_earthshaker, npc_dota_hero_crystal_maiden. Предметы: item_black_king_bar, item_blink, item_gem, item_dust, item_smoke_of_deceit, item_ward_observer, item_ward_sentry, item_tpscroll, item_force_staff, item_glimmer_cape, item_sphere, item_ultimate_scepter, item_aghanims_shard, item_manta, item_butterfly, item_monkey_king_bar, item_cyclone, item_sheepstick, item_blade_mail, item_pipe и т.п.
В params указывай только то, что точно следует из фразы. Если фраза — только сведения, а не приказ, expected — пустой список. Для фразы с переспросом — "clarify": true. Спорные толкования поясняй в note.

Выход: /tmp/claude-0/-home-user-Neu/c2746a83-5006-51b9-9f59-346f06e713bc/scratchpad/parse02_B/labels_B.jsonl — JSON Lines, ровно 80 строк в том же порядке, формат строки:
{"id": 1, "text": "<текст как во входе>", "expected": [{"action": "farm", "agents": [1], "params": {"area": "jungle_own"}}], "clarify": false, "note": ""}
Проверь: каждая строка — валидный JSON, id и тексты совпадают со входом, действия и параметры — из списка выше, agents по возрастанию. Не делай git commit и ничего не трогай в /home/user/Neu. Верни коротко: сколько строк, сколько с clarify, сколько с пустым expected, sha256 файла. Сами фразы в ответ не выписывай.
```
