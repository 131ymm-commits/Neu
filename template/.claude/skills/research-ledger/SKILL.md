---
name: research-ledger
description: Ведение любого исследования в репозитории по принципу «реестр утверждений» — каждое утверждение со статусом и опорой; PLAN до действия, REPORT после; журнал разговора человека и ИИ, решения и ошибки ИИ. Use when starting or continuing any research, importing materials, before any study, when writing conclusions, and at the end of every session.
---

# Реестр утверждений

Полный протокол — `PROTOCOL.md`. Короткая памятка:

- **Новый материал** → в `sources/`, строка в `sources/SOURCES.md` (что, откуда, когда). Упомянутое, но не найденное — в «Чего не хватает».
- **Новое утверждение** (в разговоре, в тексте, в выводах) → строка в `CLAIMS.md` со статусом. Без опоры — «по памяти».
- **Перед исследованием** → `studies/<ГГГГ-ММ-ДД>_<ID>/PLAN.md` по шаблону `studies/_TEMPLATE/`; commit + push до начала.
- **После** → `REPORT.md` с хешем PLAN (`git log --format=%h -1 -- PLAN.md`), вердикт по букве, пост-хок отдельно; статус в `CLAIMS.md` новой строкой истории.
- **Итоговый текст** → каждое утверждение сверить с `CLAIMS.md`; расхождения назвать человеку.
- **Конец сессии** → `python3 journal/export_chat.py <transcript.jsonl> journal/CHAT_<дата>.md`; `journal/ERRORS.md`; `journal/DECISIONS.md`; README; commit + push.
- **Нельзя:** переписывать запушенную историю; выдавать «по памяти» за «подтверждено»; удалять или публиковать без явного слова человека.
