#!/bin/bash
# Проверка ключа API Anthropic из секрета репозитория — без трат: только список моделей (токены не расходуются).
# Ключ не печатается; печатается лишь, есть ли он и какие модели видны.
set -euo pipefail
OUT="$1"
echo "начало: $(date -u +%H:%M:%S)" | tee "$OUT/probe.txt"
python3 -m pip install -q anthropic
python3 - <<'PY' | tee -a "$OUT/probe.txt"
import os
import anthropic
print('версия SDK:', anthropic.__version__)
if not os.environ.get('ANTHROPIC_API_KEY'):
    print('ключ в окружении: нет (секрет ANTHROPIC_API_KEY не задан)')
else:
    print('ключ в окружении: есть')
    try:
        ids = [m.id for m in anthropic.Anthropic().models.list()]
        print('моделей видно:', len(ids))
        print('нужные:', {m: (m in ids) for m in ('claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5')})
    except anthropic.AuthenticationError:
        print('ключ не принят (ошибка входа)')
    except anthropic.APIStatusError as e:
        print('ошибка API:', e.status_code)
    except anthropic.APIConnectionError:
        print('нет соединения с API')
PY
echo "конец: $(date -u +%H:%M:%S)" | tee -a "$OUT/probe.txt"
