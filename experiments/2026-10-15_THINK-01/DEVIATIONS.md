# THINK-01 — отклонения от PREREG

**После регистрации (коммит 9dcc8a1) отклонений нет.** Код прогона и анализа совпадает с PREREG §15 байт в байт (sha256 проверен 21.10.2026): harness_think.py, analyze_think.py, prompts_think.py, dryrun_think.py, run_think01.sh, seeds_main.json. Коммитов к этим файлам после 9dcc8a1 нет.

**Почему `ledger.py check` пометил prompts_think.py.**
- Проверка считает первым прогоном пилот: файлы `run/pilot_*`, коммит 88860ea, 15.10 09:29 UTC.
- Правка prompts_think.py в 9dcc8a1 сделана после пилота и до регистрации, по совету 34: в CONF_SCHEMA у p_best появились границы 0 и 1.
- Это ворота 4 CLAUDE.md: «пилоты и всё, что изменилось после них, записать в PREREG». В PREREG правка записана: §3, рука H_c, «p_best ∈ [0, 1]»; §6, «p_best вне [0, 1] — недействительна» (Н10 → `prompts_think.CONF_SCHEMA`).

**Добавлено после основного прогона** — только производные числа и сверка текста, вердикт они не меняют: report_facts_think.py и check_main_think.py (коммит 975efbd; дополнены по совету 35).
