# Прогоны Neu на Modal — только бесплатные кредиты

**Слова автора, 14.11.2026:** «давай модал но там только бесплатные прогоны».

## Правило
- На Modal идут только прогоны за счёт бесплатных кредитов плана Starter: $30 в месяц по странице цен Modal и выдаче поиска.
- **Способ оплаты в аккаунт Modal не добавляется.** По выдаче поиска (сторонние сайты; страница Modal о биллинге не прочитана), без способа оплаты Modal ничего не списывает: когда кредиты кончаются, задания останавливаются. Если Modal когда-нибудь потребует карту, прогоны на Modal прекращаются до слова автора.
- **Каждое задание** задаёт `timeout` у своих функций и самую дешёвую подходящую видеокарту. Workflow ограничен 60 минутами.
- **Перед большим прогоном** в PREREG записывается оценка стоимости по тарифу Modal. Она должна быть заметно меньше остатка кредитов месяца. Остаток автор видит в панели Modal (Usage).

## Как устроено
- Задания — `modal_jobs/<имя>.py`: приложение Modal с `@app.local_entrypoint() def main(out: str)`.
- **Workflow** `.github/workflows/neu-modal.yml`:
  1. запускается пушем изменённого задания;
  2. выполняет `modal run modal_jobs/<имя>.py --out modal_out/<имя>` на раннере GitHub;
  3. коммитит результаты в ту же ветку.
- **Ключи** — секреты репозитория GitHub `MODAL_TOKEN_ID` и `MODAL_TOKEN_SECRET`. Добавляет их автор, в чат и в код они не попадают. Без ключей workflow ничего не делает.
- **Почему через GitHub, а не из этой сессии.** Клиент Modal говорит по gRPC и передаёт ключ в двух заголовках. Защищённая форма сессии хранит один заголовок на хост, а один из этих заголовков она не принимает. Раннер GitHub ходит в сеть напрямую.

## Подключение (делает автор, один раз)
1. **modal.com → Sign up**, войти через GitHub или Google. Способ оплаты **не добавлять**.
2. **В Modal: Settings → API Tokens → New Token.** Появятся Token ID и Token Secret; секрет показывается один раз.
3. **На GitHub:** репозиторий Neu → Settings → Secrets and variables → Actions → New repository secret.
   - имя `MODAL_TOKEN_ID`, значение — Token ID;
   - второй секрет: имя `MODAL_TOKEN_SECRET`, значение — Token Secret.
4. **Написать Claude «готово».** Я запущу пробу `modal_jobs/probe.py`: несколько секунд процессора и видеокарты T4.

## Источники (выдача поиска, 14.11.2026)
- [Modal pricing](https://modal.com/pricing).
- [Modal: Continuous deployment](https://modal.com/docs/guide/continuous-deployment) — токен как секрет GitHub Actions, переменные MODAL_TOKEN_ID и MODAL_TOKEN_SECRET.
- [Modal: Run CI on Modal](https://modal.com/docs/examples/ci-on-modal).
- [Modal free tier 2026 (сторонний обзор)](https://aicreditmart.com/ai-credits-providers/modal-free-tier-how-to-get-30-month-in-compute-credits-2026/) — без способа оплаты задания останавливаются; не сверено с документацией Modal.
