#!/bin/bash
# Создаёт новый исследовательский репозиторий по протоколу «Реестр утверждений».
# Использование: ./init_research.sh <папка> "<название исследования>"
set -e
DEST="$1"; TITLE="${2:-Исследование}"
[ -z "$DEST" ] && { echo "укажите папку"; exit 1; }
[ -e "$DEST" ] && { echo "$DEST уже существует — ничего не трогаю"; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DEST"
(cd "$SRC" && tar cf - --exclude=init_research.sh --exclude=ИСПОЛЬЗОВАНИЕ.md --exclude=IMPROVEMENTS.md .) | (cd "$DEST" && tar xf -)
sed -i "s|<Название исследования>|$TITLE|" "$DEST/README.md"
cd "$DEST"; git init -q -b main; git config core.hooksPath .githooks; : > claims.jsonl; python3 tools/ledger.py render; git add -A
git -c user.name="${GIT_AUTHOR_NAME:-Claude}" -c user.email="${GIT_AUTHOR_EMAIL:-noreply@anthropic.com}" commit -q -m "Каркас исследования «$TITLE» по протоколу «Реестр утверждений»"
echo "готово: $DEST ($(git log --oneline | head -1))"
echo "дальше: создайте пустой репозиторий на GitHub и выполните: git -C $DEST remote add origin <url> && git -C $DEST push -u origin main"
