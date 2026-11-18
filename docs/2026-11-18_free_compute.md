# Бесплатные площадки для опытов Neu — поиск и проверка, 18.11.2026

**Задача автора (18.11.2026):** найти бесплатные площадки, где можно считать опыты Neu, и проверить условия по первоисточникам. Опыты: малые открытые языковые модели 0,3–1,7 млрд параметров на процессоре, 1–60 минут на задание, десятки заданий параллельно; иногда видеокарта T4, часы в неделю; анализ на numpy/scipy, минуты.

**Версия 2 (18.11.2026, вечер).** Первая версия писалась без доступа к документации. Теперь официальные страницы открылись. Что было и что стало — в разделе «Что было и что стало».

## Главное, что нужно знать до чтения

1. **Официальные страницы открылись.** Прочитаны тексты 13 из 15 площадок (Google Cloud — частично). Статус «официальная страница (прочитана 18.11.2026)» — у 13.
2. **Не открылись:** Cirrus CI (`cirrus-ci.org` — ответ 502 на CONNECT; `cirrus-ci.com/pricing/` — 403), Kaggle (`kaggle.com/docs` — 403), страница Google Cloud `free-cloud-features` (403). Для Cirrus и Kaggle статус прежний. Для Google Cloud взята другая официальная страница, на ней нет регионов и диска 30 ГБ.
3. **Главные изменения.** (а) Colab CLI больше не приоритет 1: правила бесплатного Colab запрещают удалённое управление (SSH, удалённый рабочий стол) и распределённые воркеры. Подпадает ли под это официальный Colab CLI, страница не говорит — не проверено; до проверки Colab — только вручную, в блокноте. (б) GitLab: 50 000 минут подтверждено, но только при условии, что все проекты группы открыты по лицензии. (в) Modal: бесплатный кредит $30 в месяц подтверждён. По списочной цене это около 51 часа T4 в месяц (расчёт, не цитата). Это новый кандидат для видеокарты. (г) Azure: «10 параллельных по заявке» не найдено; публичные проекты уходят с 2027 года. (д) HF Spaces: для вычислительных Spaces нужен PRO. (е) Codespaces: 120 часов, а не 60.
4. **Цитаты** даны на языке оригинала. Каждая проверена по сохранённому `.txt` (папка `scratchpad/compute_pages/`).

## Таблица площадок

Статусы: **официальная страница (прочитана 18.11.2026)** — текст страницы прочитан, цитата есть в `.txt`; **сниппет** — только выдача поиска; **по памяти** — не проверено; **не открылась (код)** — страница не получена.

| # | Площадка | Что даёт бесплатно | Доступ | Автоматизация кодом | Ограничения, риски | Источник и статус |
|---|---|---|---|---|---|---|
| 1 | **GitHub Actions, стандартные раннеры, публичный репозиторий** (уже используется) | Бесплатно на публичном репозитории. До 20 заданий одновременно (Free). Задание до 6 ч. Раннер `ubuntu-latest`: 4 vCPU, 16 GB RAM | Учётная запись GitHub | Да (`gha_jobs/`, `gha_par/`) | Большие раннеры платные даже в публичных репозиториях. Для нас не нужно: лимит 5 macOS-заданий | официальная страница (прочитана 18.11.2026): [limits](https://docs.github.com/en/actions/reference/limits), [billing](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions), [runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) |
| 2 | **GitLab CI, shared runners** | Free: 400 compute minutes в месяц на namespace. Программа для открытых проектов: 50 000 compute minutes; коэффициент 0,5 (1 compute-минута на 2 минуты задания). По нашему расчёту это около 100 000 минут задания | Учётная запись. Для программы — заявка; все проекты группы под открытой лицензией и публичны | Да, через `.gitlab-ci.yml`; нужна копия кода на GitLab | Без программы 400 минут — почти ничего. Условие про лицензии всей группы — см. «Что нужно от автора» | официальная страница (прочитана 18.11.2026): [compute minutes](https://docs.gitlab.com/ee/ci/pipelines/compute_minutes.html), [программа](https://about.gitlab.com/solutions/open-source/program/) |
| 3 | **Azure Pipelines** | Бесплатно: 1 задание, до 60 минут каждое, 1 800 минут в месяц — для приватных проектов. Публичные проекты переводятся в приватные с 2027 года | Учётная запись Microsoft | Да | Заявки на 10 параллельных заданий не найдено. Вторая параллель — платная. Новым организациям до 25 параллельных (платно) | официальная страница (прочитана 18.11.2026): [concurrent jobs](https://learn.microsoft.com/en-us/azure/devops/pipelines/licensing/concurrent-jobs) |
| 4 | **Bitbucket Pipelines** | Free: 50 build minutes в месяц на workspace. Academic (по академической почте): «unlimited academic plan». Community (для некоммерческих организаций): 500 минут | Учётная запись Atlassian | Да | 50 минут — мало. Докупить на бесплатном тарифе нельзя. Минут для открытых проектов на страницах не найдено | официальная страница (прочитана 18.11.2026): [pricing](https://www.atlassian.com/software/bitbucket/pricing), [licensing](https://www.atlassian.com/licensing/bitbucket) |
| 5 | **Codeberg, Woodpecker CI** (`ci.codeberg.org`) | Публичного лимита нет: «So there is no quota for valid use-cases!». Для больших CI-ресурсов сначала просят заявку | Заявка через форму; волонтёр проверяет; сборки включаются вручную по каждому репозиторию | Да (`.woodpecker.yml`) после одобрения | CI «as-is»: может ломаться без срока. Только `linux/amd64`. Код хранится у стороннего хоста | официальная страница (прочитана 18.11.2026): [docs.codeberg.org/ci](https://docs.codeberg.org/ci/), [FAQ](https://docs.codeberg.org/getting-started/faq/) |
| 6 | **Cirrus CI** | Не проверено | — | — | cirrus-ci.org не ответил (502), cirrus-ci.com — 403. Закрытие сервиса не проверено | сниппет (прежняя выдача); страница не открылась (502, 403) |
| 7 | **Google Colab** (`COMPUTE.md` §1) | Бесплатно. Блокнот — до 12 часов. Лимиты и типы GPU Google не публикует | Аккаунт Google | Вход интерактивный. Пакетный запуск через CLI правилами не разрешён явно и не запрещён явно | Бесплатный рантайм: «remote control such as SSH shells» и «running distributed computing workers» запрещены без баланса, могут остановить без предупреждения. Приоритет 1 снят | официальная страница (прочитана 18.11.2026): [FAQ](https://research.google.com/colaboratory/faq.html) |
| 8 | **Kaggle** (уже есть, основной GPU) | По нашему замеру по API: видеокарта 21 600 с в неделю (6 ч), ТПУ 72 000 с (`KAGGLE.md`) | Аккаунт и API-ключ | Да | Страница условий не открылась (403) | наш замер (`KAGGLE.md`); официальная страница не открылась (403) |
| 9 | **Hugging Face Spaces, CPU basic** | Статичные Spaces — бесплатно. CPU Basic: 2 vCPU, 16 GB, «no hourly cost». Gradio и Docker Spaces требуют PRO | Учётная запись; для Gradio/Docker — PRO | Нет: это веб-приложения, не пакетные задания | Засыпает без обращений, срок не указан. Число «48 ч» не подтверждено. Форумные противоречия не проверены | официальная страница (прочитана 18.11.2026): [Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview) |
| 10 | **Hugging Face Inference Providers** (как вывод, не вычисления) | Бесплатным пользователям кредитов нет; PRO — $2 в месяц | Учётная запись; токен | Да, API | Только вывод моделей, не процессор и не видеокарта для опытов | официальная страница (прочитана 18.11.2026): [pricing](https://huggingface.co/docs/inference-providers/pricing) |
| 11 | **Cloudflare Workers AI** | 10 000 Neurons в день бесплатно; сброс в 00:00 UTC; сверх — $0,011 за 1 000 на платном плане | Учётная запись Cloudflare | Да, API | Только вывод моделей. Часть моделей требует платный способ оплаты (список на странице) | официальная страница (прочитана 18.11.2026): [pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) |
| 12 | **Oracle Cloud Always Free** | Ampere A1 (Arm): 2 OCPU и 12 GB — бессрочно, пока жив аккаунт. Или до двух VM E2.1.Micro (AMD, 1/8 OCPU, 1 GB) | Регистрация; обычно нужны телефон и карта (по странице: «most users») | Да, после создания VM | VM простаивает (CPU, сеть и память ниже 20% за 7 дней) — Oracle может отобрать. «Out of host capacity» — нехватка в регионе | официальная страница (прочитана 18.11.2026): [Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm) |
| 13 | **Google Cloud Always Free** | 1 e2-micro в месяц. Новым клиентам — $300 кредитов | Аккаунт, карта | Да | Регионы и диск 30 ГБ на этой странице не найдены. Лимит «subject to change», срока уведомления нет | официальная страница (прочитана частично): [Free Tier](https://cloud.google.com/free) |
| 14 | **Modal** (`MODAL.md`) | Starter: $0 + compute в месяц, $30 кредитов в месяц; 100 контейнеров и 10 GPU одновременно. Цены: T4 $0,000164 в секунду; CPU $0,0000131 за ядро в секунду | Учётная запись; ключ в секретах | Да (API не читал) | По списочной цене $30 — около 51 ч T4 или около 636 ядро-часов CPU (расчёт). Условия использования не читал | официальная страница (прочитана 18.11.2026): [pricing](https://modal.com/pricing) |
| 15 | **GitHub Codespaces** | Личные аккаунты: 120 часов в месяц (таблица на странице). Организации бесплатной квоты не имеют | Личный аккаунт | Нет: интерактивная машина | Одна машина на человека, не пакетный режим | официальная страница (прочитана 18.11.2026): [billing](https://docs.github.com/en/billing/managing-billing-for-github-codespaces/about-billing-for-github-codespaces) |

Отброшено без нового поиска (уже в `COMPUTE.md`): Lightning AI (сменил тариф, источники расходятся), SageMaker Studio Lab (закрыт для новых), NAIRR (только для США), TPU Research Cloud (заявка автора).

## Проверка по первоисточникам (18.11.2026)

Каждая цитата — из текста страницы, на языке оригинала. Проверено по сохранённым `.txt`.

| # | Площадка | URL | Цитата (оригинал) | Статус | Что это значит для Neu |
|---|---|---|---|---|---|
| 1 | GitHub Actions | docs.github.com/en/actions/reference/limits; …/billing/managing-billing-for-github-actions/about-billing-for-github-actions | «Standard GitHub-hosted runners in public repositories» (billing). «Each job in a workflow can run for up to 6 hours of execution time.» (limits) | официальная страница | Процессор как сейчас: публичный репозиторий, 20 заданий, до 6 ч |
| 2 | GitLab | docs.gitlab.com/ee/ci/pipelines/compute_minutes.html; about.gitlab.com/solutions/open-source/program/ | «Free tier namespaces receive 400 compute minutes per month.» (docs). «including 50,000 compute minutes calculated at a program-specific cost factor» (программа). «every project in the applicant’s namespace must carry an OSI-approved open source license» (программа). «1 minute per 2 minutes of job time» (таблица, открытый проект в программе) | официальная страница | Пул процессора больше, но нужна открытая лицензия всех проектов группы |
| 3 | Azure Pipelines | learn.microsoft.com/en-us/azure/devops/pipelines/licensing/concurrent-jobs | «When you enable the free tier, for private projects you get one free job that runs for up to 60 minutes each time, with a monthly limit of 1,800 minutes (30 hours).» / «Public projects in Azure DevOps are retired. Starting in 2027, existing public projects convert to private.» / «New organizations have a maximum limit of 25 parallel jobs for Microsoft-hosted agents.» | официальная страница | Не подходит: одна параллель и 30 часов в месяц |
| 4 | Bitbucket | atlassian.com/software/bitbucket/pricing; atlassian.com/licensing/bitbucket | «You also get 1 GB file storage for LFS and 50 build minutes to get started with Pipelines.» / «For academic subscriptions: When you sign up with your academic email address, we’ll automatically convert your account to an unlimited academic plan.» / «On free plans, you cannot buy extra build minutes or LFS storage beyond your plan allowances.» | официальная страница | 50 минут мало. Academic — только если автор подходит по почте (его данные, не проверено) |
| 5 | Codeberg | docs.codeberg.org/ci/; docs.codeberg.org/getting-started/faq/ | «Onboarding requires a few manual steps, as to prevent the abuse of Codeberg's limited resources.» / «CI access is provided as-is and might break at any time» / «So there is no quota for valid use-cases!» / «You should request these resources first!» / «linux/amd64 is the sole build target on the Woodpecker CI deployment.» | официальная страница | Резервный процессор. Заявка, без срока гарантии, только x86-64 |
| 6 | Cirrus CI | cirrus-ci.org/pricing/ (502), cirrus-ci.com/pricing/ (403) | не получено | сниппет; не открылась (502, 403) | Не использовать, пока не проверено |
| 7 | Google Colab | research.google.com/colaboratory/faq.html | «In the version of Colab that is free of charge notebooks can run for at most 12 hours» / «The following are disallowed from managed Colab runtimes running free of charge, without a positive Colab compute unit balance, and may be terminated at any time without warning:» / «remote control such as SSH shells, remote desktops» / «running distributed computing workers» / «Colab does not publish these limits, in part because they can vary over time.» | официальная страница | Колаб — только вручную, в блокноте. Автоматический запуск — под вопросом |
| 8 | Kaggle | kaggle.com/docs/notebooks (403) | не получено | не открылась (403); квота — наш замер | Квота — по `KAGGLE.md`. Условия не проверены |
| 9 | Hugging Face Spaces | huggingface.co/docs/hub/en/spaces-overview | «Gradio and Docker Spaces run on compute and require a paid plan to create: PRO for personal accounts» / «The default CPU Basic hardware has no hourly cost» / «On free hardware, your Space will “go to sleep” and stop executing after a period of time if unused.» | официальная страница | Для опытов не подходит: вычисления — только с PRO |
| 10 | HF Inference Providers | huggingface.co/docs/inference-providers/pricing | «Free users can use Inference Providers by purchasing credits, or by upgrading to PRO» / «PRO users and Team or Enterprise organizations receive monthly credits to use with Inference Providers.» (таблица: бесплатным — None, PRO — $2.00) | официальная страница | Бесплатных кредитов нет. Не вычисления |
| 11 | Cloudflare Workers AI | developers.cloudflare.com/workers-ai/platform/pricing/ | «Our free allocation allows anyone to use a total of 10,000 Neurons per day at no charge.» / «All limits reset daily at 00:00 UTC.» / «Some models require a paid billing method.» | официальная страница | Вывод моделей, не опыты. Лимит общий на все модели |
| 12 | Oracle | docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm; …/freetier.htm | «For Always Free tenancies, this is equivalent to 2 OCPUs and 12 GB of memory.» / «All tenancies get up to two Always Free VM instances using the VM.Standard.E2.1.Micro shape, which has an AMD processor.» / «Idle Always Free compute instances may be reclaimed by Oracle.» / «this indicates a temporary lack of Always Free shapes in your home region» / «The Free Trial provides you with $300 of cloud credits that are valid for up to 30 days.» | официальная страница | Постоянный сервер, не пакетный пул. 2 OCPU — мало для десятков заданий |
| 13 | Google Cloud | cloud.google.com/free | «1 e2-micro instance per month» / «New customers get $300 in free credit to try Google Cloud products and build a proof of concept.» / «The free usage limit does not expire, but is subject to change.» | официальная страница (частично) | Одна маленькая VM. Регионы и срок кредита — не проверены |
| 14 | Modal | modal.com/pricing | «Starter: $0 + compute / month» / «$30 / month free credits» / «100 containers + 10 GPU concurrency» / «Nvidia T4 $0.000164» | официальная страница | Новый кандидат для видеокарты (расчёт выше). Условия использования — не читал |
| 15 | GitHub Codespaces | docs.github.com/en/billing/managing-billing-for-github-codespaces/about-billing-for-github-codespaces | «All GitHub personal accounts include a quota of free compute time and storage for GitHub Codespaces.» / «GitHub plans for organizations and enterprises do not include a free quota for GitHub Codespaces.» | официальная страница | Не для опытов: интерактивная машина |

## Что было и что стало (правки 18.11.2026)

| Площадка | Было в прежней версии | Стало после проверки |
|---|---|---|
| GitHub Actions | «конкурентность — сниппет» | 20 заданий (Free) подтверждено. 4 vCPU и 16 GB подтверждены |
| GitLab | 50 000 минут «только по выдаче»; «отдельные проекты не подходят (старый FAQ)» | 50 000 минут подтверждено. Условие про лицензии всей группы подтверждено |
| Azure | «10 параллельных заданий по заявке» | Не найдено. Free: 1 задание, 60 мин, 1 800 мин в месяц (для приватных). Публичные — в приватные с 2027 года |
| Bitbucket | 50 минут (сниппет) | 50 минут подтверждено. Academic и Community — новые пути (зависят от статуса). «Неограниченные минуты для открытых» — на страницах нет, отброшено |
| Codeberg | «квот нет; ограничения снимают по запросу» | «no quota for valid use-cases» подтверждено. Для больших ресурсов — сначала заявка. CI «as-is» — добавлено |
| Colab | CLI — приоритет 1 | Приоритет снят: правила бесплатного рантайма запрещают удалённое управление и распределённые воркеры; относится ли запрет к CLI — не проверено. «Простой ~90 мин» на странице не найдено (убрано). «T4» — страница типы GPU не называет |
| Hugging Face Spaces | «2 vCPU, 16 ГБ — официальная страница» (на деле была выдача); «засыпает после 48 ч» | Цифры 2 vCPU и 16 GB — с официальной страницы. Срок засыпания не указан, 48 ч не подтверждено. Для Gradio/Docker — PRO (подтверждено) |
| HF Inference | «$0,10 в месяц» (старая страница); противоречие | Бесплатным кредитов нет (подтверждено). PRO — $2 |
| Cloudflare | 10 000 Neurons в день (сниппет) | Подтверждено, сброс в 00:00 UTC. Часть моделей — только с платным способом оплаты |
| Oracle | «2 OCPU / 12 GB; было 4/24; даты июнь / 18.08.2026»; «нехватка по регионам» | 2 OCPU и 12 GB подтверждены. «Было 4/24» и даты на страницах не найдены (убрано). Добавлено: отбор простаивающих VM |
| Google Cloud | e2-micro в трёх регионах, диск 30 ГБ, $300 на 90 дней, уведомление за 30 дней | e2-micro в месяц и $300 подтверждены. Регионы, диск, 90 дней и уведомление за 30 дней на странице не найдены (убрано) |
| Modal | «$30 в месяц и посекундная оплата»; агрегаторы расходятся | Подтверждено: Starter $0 + compute, $30 кредитов в месяц; T4 $0,000164 в секунду. Добавлен расчёт: около 51 ч T4 в месяц |
| GitHub Codespaces | «120 core-часов» (таблица); агрегаторы: 60 | 120 часов в месяц подтверждено. Слово «core» на странице не стоит (единица «hrs»). 60 — не подтверждено |
| Cirrus CI, Kaggle | сниппет / наш замер | Без изменений: страницы не открылись |

## Рекомендация (поправлена 18.11.2026)

**Что изменилось.** Три вещи. (1) Colab CLI снят с приоритета 1: правила бесплатного Colab запрещают удалённое управление; разрешён ли под ними CLI, не проверено. (2) GitLab стал сильнее: 50 000 минут подтверждены, но нужно решение о лицензиях группы. (3) Modal — новый вариант для видеокарты: около 51 ч T4 в месяц по списку, при Kaggle около 26 ч в месяц (6 ч в неделю, расчёт).

Порядок:

1. **GitLab, программа для открытых проектов (процессор).** Около 100 000 минут задания (расчёт). Нужно: решение автора и проверка лицензии репозитория Neu (не проверено).
2. **Modal (видеокарта, и процессор по кредиту).** Новый кандидат. Нужны аккаунт и ключ (решение автора; ключ в секрете, не в чат). Сначала — прочитать условия использования Modal (не читались).
3. **Codeberg Woodpecker (процессор, резерв).** Заявка и сборки по запросу. Код хранится у стороннего хоста. Сервис может прерываться.
4. **Google Colab — только вручную, в блокноте.** CLI не рекомендую, пока Google не ответит по правилам.

Не рекомендую: Cirrus CI (не проверен); Bitbucket (50 минут; academic — только если подходит по почте); Azure (одна параллель, 30 часов в месяц); Hugging Face Spaces (вычисления — только с PRO, не пакетный режим); Oracle (2 OCPU, постоянный сервер — отдельное решение); Cloudflare (вывод моделей); Codespaces (интерактивная машина).

**Главный вывод.** Процессор: GitHub Actions даёт 20 параллельных заданий, и этого, вероятно, хватает. Узкое место — видеокарта. Kaggle около 26 ч в месяц; Modal по списку около 51 ч T4 в месяц, но сверх $30 платно.

## Что нужно от автора

1. **Хосты документации — сделано 18.11.2026** по слову «Добавь сколько нужно» (16 хостов). Не открылись: `cirrus-ci.org` (502), `cirrus-ci.com` (403), `kaggle.com` (403), `cloud.google.com/free/docs/free-cloud-features` (403). Добавлять ли их, решает автор.
2. **GitLab.** Подать заявку в программу? Условие: все проекты группы — с открытой лицензией и публичны. Рекомендую подать, если лицензия репозитория Neu и других проектов группы это допускает. Сначала проверить лицензию (мной не проверено).
3. **Modal.** Завести аккаунт и ключ? Рекомендую — после чтения условий использования Modal. Ключ — в секрете репозитория, в чат не выводить.
4. **Colab CLI.** Приоритет снят. Токен не сохранять, пока Google не ответит по правилам.
5. **Bitbucket.** Если у автора академическая почта, возможен план «unlimited academic» (по странице). Это его данные, я не проверял.

## Чего записка не утверждает

- **Cirrus CI:** ни закрыт, ни открыт. Сайт не открылся (502, 403).
- **Kaggle:** публичные условия не прочитаны (403). Квота — только наш замер.
- **Google Cloud:** регионы, диск 30 ГБ, срок $300 и срок уведомления об изменениях не проверены.
- **Colab:** простой «около 90 минут», список типов GPU, автоматический вход и CLI не проверены.
- **Codeberg:** лимиты не опубликованы. Что считается «большими» ресурсами, не сказано.
- **GitLab:** коэффициент 0,5 взят из таблицы в документации. На странице программы он прямо не назван.
- **Modal:** условия использования, API и лимиты для пакетных заданий не читались. Цены — только из списка.
- **Oracle:** даты изменения лимитов и «было 4/24» не найдены.
- **Hugging Face Spaces:** срок засыпания не указан.
- Не регистрировался, ничего не вводил, ключей не использовал. Задания не запускались. Не коммитилось и не пушилось.

**Вес опоры (по суждению, без записи в реестр).** Класс «официальная страница, текст прочитан» — множитель 1,0 (`tools/support_bits.py --classes`). «Сниппет» — 0,5. «По памяти» — 0. Для Cirrus и Kaggle (сниппет, наш замер) — по этим множителям. В `journal/support_bits.json` строки не добавлялись.
