# Neu

**Весы, которые можно купить, — не весы.** ИИ всё больше делает работу сам, и дорогим становится не сделать, а оценить. Neu — открытая лаборатория оценщиков, которых не обманывает давление отбора. Правда здесь считается кодом, выборы записываются до того, как посчитана правда, а каждый вывод проверяется повтором.

**Один проверенный результат — SELECT-01.**
- **Постановка.** Исполнитель (Claude) предлагает 8 планов для склада и к каждому пишет заявку «сколько он даст». Настоящую ценность считает симулятор; оценщики её не видят.
- **Кто выбирает лучше.** Пять голов с ролью независимого оценщика и правом ответить «не могу выбрать», большинством голосов. Они выбирают лучше, чем 12 голов вслепую, и лучше, чем выбор по заявке исполнителя. Так вышло в основной выборке (100 задач) и в повторе на 99 новых задачах, всё по предрегистрации и при меньшем числе токенов.
- **Цифры.** Регрет (0 — выбран лучший план, 1 — как наугад): 0,491 и 0,566 против 0,676 и 0,852 у двенадцати голов вслепую.
- **Что не установлено:** чем именно работает право отказа. Возможно, такие головы просто дольше думают; это проверяет опыт THINK-01. Подробно — `experiments/2026-10-07_SELECT-01/REPORT_final.md`.

**Проверьте нас за секунду:**
```
python3 experiments/2026-10-07_SELECT-01/check_final.py
```
Скрипт строит из данных 65 чисел и фраз отчёта и ищет их в тексте: `проверено фраз: 65; не найдено: 0`.

**Как присоединиться.**
- План «открытых весов» и первые задачи — `docs/2026-10-19_community_linux.md`. Лицензия MIT.
- Вопросы и возражения — в Issues, по-русски или по-английски. Рабочий язык репозитория — русский.
- Связанные проекты автора: Основание (Foundation-1.3) — сеть без центра, где судья — жизнь выпускников; Баланс (balance-github) — рекомендатель, которого нельзя купить.

---

**A scale you can buy is not a scale.** As AI does more of the work itself, the scarce thing is no longer doing but judging. Neu is an open lab for evaluators that selection pressure cannot fool. Truth is computed by code, choices are committed before the truth is computed, and every claim is replicated.

**One verified result — SELECT-01.**
- **Setup.** An executor model proposes 8 warehouse plans, each with a self-reported claim. A simulator computes the true value; the evaluators never see it.
- **Who picks better.** Five evaluator heads with an independent-judge role and the right to answer "cannot choose", by majority vote. They pick better plans than 12 blind heads and than picking by the executor's claim. This held in a main sample (100 tasks) and in a pre-registered replication (99 new tasks), at a lower token budget.
- **Numbers.** Normalized regret (0 = best plan, 1 = random): 0.491 and 0.566 vs 0.676 and 0.852 for the 12 blind heads.
- **Not established:** what exactly makes it work. It may simply be longer reasoning; the THINK-01 experiment is testing that.

**Check us in one second:** `python3 experiments/2026-10-07_SELECT-01/check_final.py` rebuilds 65 numbers and phrases of the report from the data.

**Join:**
- The "open scales" plan — `docs/2026-10-19_community_linux.md` (Russian for now). MIT license.
- Issues welcome in English or Russian.

---

## О программе подробно

Программа о том, как появляются и удерживаются уровни организации: в обучаемых моделях, в сообществах и в мире, который модели предсказывают. Здесь собраны в одном месте документы, предрегистрации, код, результаты и аудиты, которые раньше были разбросаны по чатам, архивам и десяткам репозиториев.

## Что где лежит

| Папка | Что внутри |
|---|---|
| `docs/2026-09-19_21/` | документы проекта: «Основание и уровни» (19.09), «Один проект: открытый ИИ по правилам Linux» (21.09) и материалы к играм |
| `experiments/2026-09-19_equiv_auto_bound_linux/` | предрегистрации PREREG-EQUIV, PREREG-EQUIV-B, PREREG-AUTO-01, PREREG-BOUND-01; код (eq01_*, auto_*, bound01*, eq02_*, psu_auto.py, psu2_pythia_colab*.py); результаты (*.json, *.csv, *.log); конвейеры по Linux и llama.cpp |
| `games/` | «Экономика форков» и «После вспышки»: собранные html и исходники |
| `archive/neu_archive_2026-09-16/` | архив программы Neu до 16.09: PREPROMPT (пять ворот), PREREG, PRIORITY, отчёты арок, код и результаты |
| `audit/` | АУДИТ-02 документа «Один проект» (22–24.09), полный реестр находок, скрипт проверки мостов Э1 и Э5 |
| `journal/` | весь чат с Claude, ошибки и предположения Claude, скрипт выгрузки чата |
| `proposals/` | предложение для Anthropic: исследование как общий журнал человека и ИИ (ru, en) |
| `template/` | универсальный шаблон «Реестр утверждений» для любого исследования; новый репозиторий — `template/init_research.sh`; инструменты `template/tools/`; что улучшено — `template/IMPROVEMENTS.md` |
| `PROTOCOL.md` | общий алгоритм: как вести исследование вместе с ИИ в одном репозитории |
| `recovered/UAF-6.0.1_Q46-Q48/` | эксперименты УАФ Q46–Q48, удалённые из UAF-6.0.1 15.06.2026 и восстановлены из истории git |

Не включены: чекпойнты моделей AUTO-01 (`*.pkl`, около 80 МБ; в папке `auto/` оставлены только `log.json` каждого прогона) и сырые МД-траектории архива Neu (`results/md_raw`).

## Чего пока нет нигде (ни здесь, ни на GitHub, ни в присланных архивах)

- результаты ПСУ-2 и ПСУ-3 на Pythia: таблицы Colab, psu3_pythia_colab.py;
- АУДИТ-01 (audit_toy.py, audit_bridges.py, read_psu3.py);
- бэктест игры (backtest_growth3.json, модель «Мир-2.1.2»);
- отчёты УАФ Q49–Q101 (K* ≈ 0,157, 68+ сетей, очередь на Higgs Twitter);
- версия Спектрального предиктора с MASE 0,776 / 1,224;
- весовая генетика (протокол B), СБОРКА, CTF.

Если эти файлы найдутся, им место в `experiments/` и `recovered/`.

## Старые репозитории (все в аккаунте 131ymm-commits)

| Ветка | Репозитории |
|---|---|
| Основание | Foundation-1.3 |
| Баланс | balance-github (канонический), balance-en (английское зеркало), Balance (ранняя копия) |
| Спектральный предиктор | SpectralPredictor |
| УАФ, текущая линия | uaf-v5.2-final (Q20–Q39), UAF-6.0 (Q40–41), UAF-6.0.1 (Q40–45; Q46–48 удалены, копия в `recovered/`), UAF-6.1.0 (данные Q90, Q97.2); UAF-6.2 и UAF-6.2.1 пусты |
| УАФ, ранние версии | UAF-Unified-Adaptive-Framework (v1.3 … v5), UAF-v-5.1, UAF-v-5.2, UAF-3.1, UAF-AUS, UHF-AUS-v3.1, UAF-LM, UAF-Quantum(_v_2), UAF-RIEMANN(_v_2), UAF-Economic-Theory-UET-, uaf-dirac-anomaly, uaf-molecular-optimization |
| Прочее | universal-hierarchy-formalism(-v-2), hsvd-framework, crystal-score-prime-sequences, holoworm-uhf, AlgoGenesis-Core-v0.2, algogenesis-evolution, Riman_vs_TRIZ, Structural-Break-Real-Time, XFamilia, XGrav |

## Как вести этот репозиторий дальше

Один репозиторий на программу, а не новый на каждую версию. Версии — это коммиты и теги (`v1.0`, `v1.1`), а не новые репозитории. Каждый эксперимент — своя папка `experiments/<дата>_<ID>/` с предрегистрацией, кодом и результатами. Предрегистрация коммитится до запуска, и отчёт ссылается на хеш этого коммита. Отрицательные результаты хранятся наравне с положительными.

## Лицензия

MIT (`LICENSE`), решение автора 19.10.2026: код, тексты и данные репозитория можно свободно брать, менять и распространять с сохранением строки об авторском праве. Материалы третьих лиц, которые процитированы или скопированы сюда, остаются под своими лицензиями.
