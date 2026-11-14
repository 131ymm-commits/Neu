# Где считать опыты Neu — итог поиска (14.11.2026)

**Слова автора, 14.11.2026:** «поищи в сети где еще можем делать эксперементы, нужно сразу закрыть этот вопрос чтобы не возвращятся к нему».

**Статус данных.** Числа о чужих платформах — из выдачи поиска (сниппет): тарифы меняются, перед большим прогоном их надо сверять на странице поставщика. Пометка «проверено нами» — наш собственный замер.

## Решение
| задача | где | как запускается | состояние |
|---|---|---|---|
| процессор: короткие и средние прогоны | эта облачная сессия | сам | работает (SPECTRUM-01: 90 групп за 31 мин) |
| процессор: долгие прогоны и развёртки | **GitHub Actions** | сам, пушем задания | работает, проверено нами (§3) |
| видеокарта — основное | **Kaggle** (`docs/KAGGLE.md`) | сам, через API | работает, проверено нами |
| видеокарта — запас | **Colab** (`docs/COLAB.md`) | клик автора | работает, проверено нами |
| видеокарта — если Kaggle и Colab мало | **Modal**, только бесплатные кредиты (`docs/MODAL.md`) | сам, через GitHub Actions | подключается: ждём ключи в секретах GitHub |
| много видеокарт за деньги | Vast.ai, RunPod | сам, по API | только при бюджете, одобренном автором |

- **Kaggle, проверено нами:** квота по API — видеокарта 21 600 с в неделю (6 ч), ТПУ 72 000 с (20 ч), обновление 21.11.2026. В выдаче поиска чаще пишут «около 30 ч в неделю»; разницу с нашей квотой не проверяли. Сессия — до 12 ч (по выдаче).
- **Colab:** Google не публикует пределы бесплатного тарифа. По выдаче — сессия до 12 ч, отключение после 90 мин простоя, обычно T4.
- **Modal:** по выдаче — бесплатный план Starter с кредитами $30 в месяц и посекундная оплата сверх. Часть сайтов-агрегаторов пишет «бесплатного тарифа нет»; сверять на modal.com/pricing.
- **Аренда видеокарт** (снимки 2026, по выдаче, цены плавают): RTX 4090 — от $0,14 в час (Vast.ai) и $0,34 (RunPod Community); A100 80GB — около $1,39; H100 — около $2–4.

## Отброшено
- **Lightning AI:** в сентябре 2026 бесплатный тариф, по выдаче, сменился с ежемесячных кредитов на разовый грант. Источники расходятся.
- **SageMaker Studio Lab:** по обзору сентября 2026, закрыт для новых пользователей.
- **Hugging Face ZeroGPU:** около 5 минут видеокарты в день у бесплатного аккаунта — только для показов.
- **NAIRR:** для исследователей США.
- **TPU Research Cloud:** бесплатные ТПУ Google по заявке исследователей. Оставлено на случай большого опыта на ТПУ; заявку подаёт автор.

## 1. Colab: новое в 2026 году
Google выпустил официальную консольную программу Colab (июнь 2026, `github.com/googlecolab/google-colab-cli`, лицензия Apache 2.0; README прочитан нами).
- `colab run --gpu T4 script.py` выделяет машину, запускает скрипт, забирает файлы и освобождает машину. Программа сделана и для агентов в терминале.
- Вход — аккаунтом Google: ссылка, затем одноразовый код, который вставляют в программу. Токен хранится в системном хранилище ключей. В облачной сессии такого хранилища нет, а контейнер временный, поэтому код пришлось бы вводить каждый новый сеанс. Значит, здесь Colab остаётся «в один клик».
- Если автор будет вести Neu через Claude Code на своём компьютере, Colab там может запускаться сам.

## 2. Почему не всё сразу
- Каждая новая площадка — это аккаунт, ключ и свои ограничения.
- Наши опыты пока малы. SPECTRUM-01 занял 31 минуту на процессоре, а для шагов с видеокартой (PYTHIA-01, ОЦЕНЩИК-ГЕОМЕТРИЯ) хватает 6 часов Kaggle в неделю.
- Modal и аренда — когда Kaggle и Colab станет мало.

## 3. GitHub Actions — подключено (слово автора 14.11.2026: «да, GitHub Action»)
- **Что даёт.** Для открытых репозиториев стандартные раннеры GitHub бесплатны и без ограничения минут (документация GitHub, по выдаче). Задание — до 6 ч, машина `ubuntu-latest` — 4 ядра и 16 ГБ (по выдаче). Можно запускать несколько заданий параллельно.
- **Как устроено.** Я пушу файл задания, GitHub прогоняет его и коммитит результаты в ту же ветку.
- **Сначала не было подключено.** Это файл `.github/workflows/neu-run.yml` с правом записи в репозиторий. Система разрешений сессии не дала добавить его без явного согласия автора; после слова автора файл добавлен.
- **Как запускать.**
  1. Кладу или меняю `gha_jobs/<имя>.sh` и пушу.
  2. GitHub выполняет задание. Первым аргументом оно получает папку `gha_out/<имя>/` и пишет туда результаты.
  3. Workflow коммитит результаты обратно в ту же ветку от имени Claude, а я подтягиваю их через `git pull`.
- **Проверка, 14.11.2026.** Задание `gha_jobs/probe.sh` выполнено, результат — `gha_out/probe/probe.json`.

| машина (проверено нами) | процессоров | память | умножение 2000 × 2000 |
|---|---|---|---|
| GitHub Actions, `ubuntu-latest` | 4 | 16 365 628 кБ | 0,101 с |
| Kaggle | 4 | — | 0,292 с |
| Colab, среда по умолчанию | 2 | — | 0,951 с |

## Источники (выдача поиска, 14.11.2026)
- GitHub: [How use of GitHub Actions is measured](https://docs.github.com/en/billing/concepts/product-billing/github-actions); [Limits in GitHub Actions](https://docs.github.com/en/actions/reference/actions-limits); [Pricing changes for GitHub Actions](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/).
- Colab CLI: [Introducing the Google Colab CLI](https://developers.googleblog.com/introducing-the-google-colab-cli/); [googlecolab/google-colab-cli](https://github.com/googlecolab/google-colab-cli); [InfoQ](https://infoq.com/news/2026/06/google-colab-cli/).
- Обзоры бесплатных видеокарт: [Free Cloud GPUs in 2026: What Works and What Closed](https://gpuperhour.com/blog/free-cloud-gpus-and-credits); [AIMultiple: free cloud GPU](https://aimultiple.com/free-cloud-gpu); [Spheron: Colab alternatives 2026](https://www.spheron.network/blog/google-colab-alternatives-8-gpu-clouds-compared-2026/).
- Modal: [Modal Labs Pricing 2026](https://www.activepieces.com/blog/modal-labs-pricing-2026-gpu-rates-plans-and-credits.md); [Modal Free Plan 2026](https://www.costbench.com/software/ai-gpu-cloud/modal/free-plan/).
- Lightning: [Lightning AI 2026-09-21 rate card](https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice).
- Hugging Face: [Spaces ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu).
- Аренда: [Cloud GPU Pricing in 2026](https://neurohive.io/en/guides/cloud-gpu-pricing/); [Northflank: cheapest cloud GPU providers](https://northflank.com/blog/cheapest-cloud-gpu-providers).
- Программы для исследователей: [TPU Research Cloud](https://sites.research.google/trc/about/); [AI Compute Grants in 2026](https://grantedai.com/blog/ai-compute-grants-gpu-credits-guide).
