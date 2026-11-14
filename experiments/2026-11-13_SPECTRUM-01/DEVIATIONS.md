# SPECTRUM-01 — отклонения от PREREG (2e0295ca)

Отклонений нет.

Не отклонения, записываю для прозрачности:
- `facts_spectrum01.py` (сбор чисел отчёта) написан после прогона. Ожидания §7 он считает по букве PREREG, вердикты не меняет: их ставит зарегистрированный `analyze_spectrum01.py`.
- `run/results.json` (17,9 МБ) хранится сжатым: `run/results.json.gz`, sha256 несжатого — `run/results.json.sha256`. Для повтора анализа: `gunzip -k run/results.json.gz`.
