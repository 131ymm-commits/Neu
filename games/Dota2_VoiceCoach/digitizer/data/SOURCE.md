# Источник таблиц

Файлы `heroes_by_id.json`, `items.json`, `ability_ids.json`, `order_types.json`, `patch.json`
выписаны из npm-пакета `dotaconstants` 10.8.0 (OpenDota, лицензия MIT, опубликован 2026-03-25,
последний патч в списке — 7.41 от 2026-03-24). Из `heroes.json` и `items.json` оставлены только
нужные поля (имя, локализованное имя, роли, тип атаки; id, цена, отображаемое имя).
Обновлять: `npm pack dotaconstants` и тот же отбор полей.
