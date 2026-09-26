export const meta = {
  name: 'hive-leg0',
  description: 'HIVE-01: один шаг самоуправляемых ульев — «ответ» (головы отвечают на вопросы без правды) или «законодательство» (критика, сгущение, пересмотр личных правил, бюллетень, голосование; предметные поправки отсеиваются кодом)',
  phases: [{ title: 'Шаг' }],
}
const ARGS = {"mode": "legislate", "hives": {"A": {"laws": ["Сначала оценивай независимо, не подстраиваясь под чужие ответы.", "Всегда проверяй оценку вторым, другим способом и сравни результаты.", "Не выдавай интервал уже, чем позволяет твоя реальная уверенность: промах хуже широкого интервала.", "Итог улья — медиана независимых оценок, а не мнение самого уверенного."], "roles": ["аналитик: оценивает через формулы и асимптотики", "вычислитель: считает точно малые случаи и экстраполирует", "скептик: ищет, почему оценки других неверны, и расширяет интервал при сомнении"], "delphi": false, "agg": "median", "personal": [[], [], []]}, "B": {"laws": ["Сначала оценивай независимо, не подстраиваясь под чужие ответы.", "Всегда проверяй оценку вторым, другим способом и сравни результаты.", "Не выдавай интервал уже, чем позволяет твоя реальная уверенность: промах хуже широкого интервала.", "Итог улья — медиана независимых оценок, а не мнение самого уверенного."], "roles": ["аналитик: оценивает через формулы и асимптотики", "вычислитель: считает точно малые случаи и экстраполирует", "скептик: ищет, почему оценки других неверны, и расширяет интервал при сомнении"], "delphi": false, "agg": "median", "personal": [[], [], []]}}, "feedback": {"A": "[COL3-1000] правда 480; итог 480 [470; 490] — попал, ошибка 0.0 %\n[COL3-1001] правда 36; итог 36 [36; 36] — попал, ошибка 0.0 %\n[PART-1000] правда 181810744; итог 1.817e+08 [1.78e+08; 1.855e+08] — попал, ошибка 0.1 %\n[PART-1001] правда 10327156; итог 1.0325e+07 [1.01e+07; 1.055e+07] — попал, ошибка 0.0 %\n[TWIN-1000] правда 322; итог 335 [308; 362] — попал, ошибка 4.0 %\n[TWIN-1001] правда 1050; итог 1047 [1000; 1095] — попал, ошибка 0.3 %\n[SUB5-1000] правда 603; итог 603 [590; 615] — попал, ошибка 0.0 %\n[SUB5-1001] правда 5907; итог 5908 [5700; 6100] — попал, ошибка 0.0 %\n[COLLATZ-1000] правда 274; итог 295 [220; 390] — попал, ошибка 7.7 %\n[COLLATZ-1001] правда 191; итог 245 [190; 350] — попал, ошибка 28.3 %\nСредний интервальный балл улья 0.167 (меньше — лучше), покрытие 100 %.", "B": "[COL3-1000] правда 480; итог 480 [480; 480] — попал, ошибка 0.0 %\n[COL3-1001] правда 36; итог 36 [36; 36] — попал, ошибка 0.0 %\n[PART-1000] правда 181810744; итог 1.82e+08 [1.79e+08; 1.85e+08] — попал, ошибка 0.1 %\n[PART-1001] правда 10327156; итог 1.033e+07 [1.01e+07; 1.055e+07] — попал, ошибка 0.0 %\n[TWIN-1000] правда 322; итог 335 [312; 358] — попал, ошибка 4.0 %\n[TWIN-1001] правда 1050; итог 1047 [1005; 1090] — попал, ошибка 0.3 %\n[SUB5-1000] правда 603; итог 603 [601; 603] — попал, ошибка 0.0 %\n[SUB5-1001] правда 5907; итог 5907 [5750; 6100] — попал, ошибка 0.0 %\n[COLLATZ-1000] правда 274; итог 297 [190; 400] — попал, ошибка 8.4 %\n[COLLATZ-1001] правда 191; итог 245 [160; 340] — попал, ошибка 28.3 %\nСредний интервальный балл улья 0.186 (меньше — лучше), покрытие 100 %."}, "others": {"A": ["Голова 1:\n[COL3-1000] 480 [470; 490] — Exact hand count: pendant vertex 7 (x2), degree-2 paths via K3 walk counts (A^3: 2 same/3 diff), core 1,10,11 with 5,8 in {a,b}: 6*40*2=480; cycle-ratio heuristic gave ~450 as a check\n[COL3-1001] 36 [36; 36] — Chain of triangles forces the core to be unique up to 6 color permutations; isolated vertex 9 (x3) and pendant 10 (x2) give 36\n[PART-1000] 1.819e+08 [1.795e+08; 1.84e+08] — Asymptotic q(n)~exp(pi*sqrt(n/3))/(4*3^(1/4)*n^(3/4))=1.843e8 with ratio correction ~0.987 calibrated on q(100), q(200)\n[PART-1001] 1.033e+07 [1.02e+07; 1.046e+07] — Same asymptotic 1.049e7 times calibrated correction ~0.985\n[TWIN-1000] 335 [305; 365] — Hardy-Littlewood 2*C2*L/ln^2 p with C2=0.6602, ln p=19.86\n[TWIN-1001] 1047 [990; 1105] — Hardy-Littlewood 2*C2*L/ln^2 p, ln p=19.45, L=300000\n[SUB5-1000] 603 [590; 615] — Reduced to partitions of 35 into 5 parts with largest <=21: p(30,<=5)=674 minus 71; Edgeworth-normal check gives ~599\n[SUB5-1001] 5908 [5830; 5990] — Partitions of 79 into 5 parts (~15258) minus those with largest >=32 (~9350) via quasi-polynomial formulas; normal+Edgeworth check ~5925\n[COLLATZ-1000] 297 [230; 370] — Random-model mean steps ~10.43*ln n (ln n=28.5); high variance\n[COLLATZ-1001] 245 [190; 310] — n=2^8*7570886601: 8 halvings plus ~10.43*ln(7.57e9)~237", "Голова 2:\n[COL3-1000] 480 [480; 480] — Exact by hand: leaf 7 gives x2, vertex 4 is forced (x1), triangle 1-10-11 gives 6, the length-4 path 1-8-6-9-5 gives 5 and the cases for 5 and 12 give 8; 6*8*5*2 = 480.\n[COL3-1001] 36 [36; 36] — Exact by hand: the triangle 2-3-8 (6 colorings) forces every other connected vertex; isolated vertex 9 gives x3 and leaf 10 gives x2; 6*3*2 = 36.\n[PART-1000] 1.817e+08 [1.76e+08; 1.88e+08] — Asymptotic q(n) ~ exp(pi*sqrt(n/3)) / (4*3^(1/4)*n^(3/4)), scaled from the recalled values q(100)=444793 and q(200)=487067745; the two give 180.9M and 181.9M.\n[PART-1001] 1.032e+07 [1.005e+07; 1.06e+07] — Same asymptotic ratio method scaled from recalled q(100) and q(200); the two give 10.30M and 10.35M.\n[TWIN-1000] 335 [310; 360] — Hardy-Littlewood density 2*C2/(ln x)^2 at x=4.21e8, times an interval length of 100000.\n[TWIN-1001] 1047 [1000; 1095] — Hardy-Littlewood density 2*C2/(ln x)^2 at x=2.8e8, times an interval length of 300000.\n[SUB5-1000] 603 [603; 603] — Exact: shift to partitions of 30 into at most 5 parts, p=674, minus the 71 with a part above 20, giving 603.\n[SUB5-1001] 5950 [5700; 6200] — Normal approximation for sums of 5 of 35 without replacement: C(35,5)=324632, sd=21.2 gives about 6100 near the centre; an Edgeworth correction for negative kurtosis lowers it to about 5950.\n[COLLATZ-1000] 295 [220; 390] — Heuristic mean of about 10.43*ln(n), assuming each odd step is followed by 2 halvings on average; the spread is taken from typical variation.\n[COLLATZ-1001] 293 [215; 390] — Heuristic of about 10.43*ln(n); n is divisible by 2^8 only, so it is not a special case.", "Голова 3:\n[COL3-1000] 480 [450; 510] — Точный разбор вручную: треугольники 1-4-10 и 1-10-11 дают 4=11; перебор по цвету вершины 5 даёт 40 при фиксированных 1 и 10; умножаем на 3·2 и на 2 за лист 7.\n[COL3-1001] 36 [30; 42] — Треугольники 2-3-8 и 2-3-4 однозначно задают цвета всех остальных вершин (6 способов), изолированная вершина 9 даёт ×3, лист 10 даёт ×2.\n[PART-1000] 1.817e+08 [1.78e+08; 1.855e+08] — Асимптотика q(n)~exp(pi*sqrt(n/3))/(4*3^(1/4)*n^(3/4)) с поправкой около -1.3%, откалиброванной по известным q(100) и q(200).\n[PART-1001] 1.0325e+07 [1.01e+07; 1.055e+07] — Та же асимптотика для q(141) с поправкой около -1.5%, интерполированной между n=100 и n=200.\n[TWIN-1000] 335 [308; 362] — Харди-Литтлвуд: 2*C2*длина/ln^2(x) = 1.3203*1e5/394.4; разброс примерно пуассоновский.\n[TWIN-1001] 1047 [1000; 1095] — Харди-Литтлвуд: 1.3203*3e5/378.4; разброс примерно пуассоновский.\n[SUB5-1000] 603 [590; 615] — Точный подсчёт: разбиения 30 не более чем на 5 частей (674) минус случаи с наибольшей частью не меньше 21 (71), по таблицам p(n,<=4).\n[SUB5-1001] 5850 [5600; 6100] — Нормальное приближение к распределению суммы (C(35,5)=324632, sd=21.2) с поправкой на эксцесс; сверено с грубым подсчётом разбиений (около 5770).\n[COLLATZ-1000] 295 [200; 410] — Эвристика случайного блуждания: около 10.43*ln(n) шагов, ln n = 28.5; стандартное отклонение около 80 шагов, распределение скошено вправо.\n[COLLATZ-1001] 245 [165; 350] — n = 2^8*7570886601: 8 делений плюс около 10.43*ln(7.57e9) = 237 шагов; широкий разброс, как у случайного блуждания."], "B": ["Голова 1:\n[COL3-1000] 480 [480; 480] — Exact count: remove leaf 7 (x2) and vertex 4 (x1), fix triangle 1-10-11 (6 ways), case split on vertex 5 with walk counts for path 1-8-6-9-5: 6*40*2 = 480. Cross-check: tree bound times cycle factors gives about 700.\n[COL3-1001] 36 [36; 36] — Exact count: triangle 2-3-8 forces the colouring of the core uniquely (6 ways), times 3 for isolated vertex 9 and 2 for leaf 10 = 36.\n[PART-1000] 1.82e+08 [1.78e+08; 1.86e+08] — Asymptotic exp(pi*sqrt(n/3))/n^(3/4), scaled from remembered q(200) of about 4.87e8; the same method checked against q(100) = 444793 was off by about 0.7%.\n[PART-1001] 1.033e+07 [1.01e+07; 1.06e+07] — Same asymptotic ratio from q(200), corrected by the error seen at q(100).\n[TWIN-1000] 335 [312; 358] — Hardy-Littlewood: 1.3203*N/ln^2(p), N = 100001, with interval of about +-1.3*sqrt(count).\n[TWIN-1001] 1047 [1005; 1090] — Hardy-Littlewood: 1.3203*N/ln^2(p), N = 300001.\n[SUB5-1000] 603 [603; 603] — Exact count: partitions of 30 into at most 5 parts, each at most 20: 674 - 71 = 603, found by recursion. Normal approximation gives about 572-594.\n[SUB5-1001] 5930 [5700; 6150] — Near-central coefficient of the Gaussian binomial [35 choose 5] (sd 21.2), normal approximation with an Edgeworth kurtosis correction of about -3%, calibrated on SUB5-1000.\n[COLLATZ-1000] 297 [215; 400] — Mean total stopping time of about 10.4*ln(n), where ln(n) is about 28.5; the spread is wide.\n[COLLATZ-1001] 245 [180; 340] — n = 2^8 * 7570886601: 8 halvings plus about 10.4*ln(7.57e9).", "Голова 2:\n[COL3-1000] 480 [480; 480] — Точный разбор: треугольник 1-10-11 (6 способов), висячая 7 (x2), 4 вынуждена, путь 1-8-6-9-5 даёт 5, перебор цветов 5 и 12 даёт 8; итого 6*8*5*2=480.\n[COL3-1001] 36 [36; 36] — Треугольник 2-3-8 (6 способов) вынуждает цвета всех остальных вершин; изолированная 9 даёт x3, висячая 10 даёт x2; итого 36.\n[PART-1000] 1.82e+08 [1.79e+08; 1.85e+08] — Асимптотика q(n)~exp(pi*sqrt(n/3))/(4*3^(1/4)*n^(3/4)), масштабирование от известного q(200)=487067745 с поправкой, проверенной на паре q(100)/q(200).\n[PART-1001] 1.032e+07 [1.01e+07; 1.05e+07] — Отношение асимптотик к известному q(100)=444793 с малой эмпирической поправкой.\n[TWIN-1000] 335 [312; 358] — Харди-Литтлвуд: 2*C2/ln^2(x) при x~4.21e8 на отрезке длиной 1e5; разброс порядка пуассоновского.\n[TWIN-1001] 1047 [1005; 1090] — Харди-Литтлвуд: 2*C2/ln^2(x) при x~2.8e8 на отрезке длиной 3e5; разброс порядка пуассоновского.\n[SUB5-1000] 601 [601; 601] — Точно: разбиения 30 не более чем на 5 частей (672) минус 71 разбиение с частью >20; проверено разложением Эджворта (~601).\n[SUB5-1001] 5900 [5750; 6050] — Нормальное приближение около центра (C(35,5)=324632, sd=21.2) с поправкой Эджворта на эксцесс, выверенной на SUB5-1000.\n[COLLATZ-1000] 198 [150; 260] — Среднее число шагов около 6.95*ln n при n~2.44e12; разброс большой.\n[COLLATZ-1001] 166 [125; 220] — n=2^8*7570886601: 8 делений на 2 плюс около 6.95*ln(7.57e9) шагов; разброс большой.", "Голова 3:\n[COL3-1000] 240 [230; 250] — Ручной разбор: вершину 1 красим фиксированно, 10 — одним из двух цветов, 4 и 11 вынуждены, лист 7 даёт x2, путь 1-8-6-9-5 даёт 5 вариантов, итого 40*3*2*2=240.\n[COL3-1001] 12 [12; 12] — Цепочка треугольников (2-3-4, 2-3-8, 3-8-11, 7-8-11, 5-7-11) задаёт цвета почти всех вершин, свободна только висячая 10: 6*2=12.\n[PART-1000] 1.818e+08 [1.79e+08; 1.85e+08] — Асимптотика q(n)~exp(pi*sqrt(n/3))/(4*3^{1/4}n^{3/4}), отсчитанная от q(200)=487067745 и q(100)=444793; обе опоры дают 181-182 млн.\n[PART-1001] 1.034e+07 [1.015e+07; 1.055e+07] — Та же асимптотика с опорами q(100) и q(200): получается 10.30 и 10.36 млн.\n[TWIN-1000] 335 [305; 365] — Харди-Литтлвуд: 1.3203*1e5/ln^2(4.21e8) ~ 335, пуассоновский разброс около ±18.\n[TWIN-1001] 1047 [990; 1105] — Харди-Литтлвуд: 1.3203*3e5/ln^2(2.8e8) ~ 1047, пуассоновский разброс.\n[SUB5-1000] 603 [595; 612] — Сдвиг сводит задачу к разбиениям 35 на 5 частей <=21: p(30,<=5)=674 минус 71 разбиение со слишком большой частью; нормальное приближение даёт около 570.\n[SUB5-1001] 5907 [5750; 6100] — Разбиения 79 на 5 частей <=31: 15257-9350 (ручной подсчёт по формуле p(n,<=4)); нормальное приближение даёт около 6100.\n[COLLATZ-1000] 297 [190; 450] — Эвристика: в среднем ln n/0.096 шагов при ln n ~ 28.5; разброс длины траектории большой.\n[COLLATZ-1001] 245 [160; 390] — n=2^8*7570886601: 8 делений на 2 плюс эвристика ln(7.57e9)/0.096 ~ 237; разброс большой."]}, "no_tools": "Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.", "max_laws": 8}
// ARGS.mode = 'answer': {questions:[{id,text}], hives:{name: state}, digests:{name: text}, no_tools}
// ARGS.mode = 'legislate': {hives:{name: state}, feedback:{name: text}, others:{name: [text по головам]}, no_tools, max_laws}
// state: {laws, roles, delphi, agg, personal}
const A = ARGS
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (props, req) => ({ type: 'object', properties: props, required: req })
const BATCH = obj({ items: { type: 'array', items: obj({ id: { type: 'string' }, estimate: { type: 'number' }, lo: { type: 'number' }, hi: { type: 'number' },
  note: { type: 'string' } }, ['id', 'estimate', 'lo', 'hi', 'note']) } }, ['items'])
const AMENDS = { type: 'array', items: obj({ kind: { type: 'string', enum: ['добавить закон', 'заменить закон', 'удалить закон', 'протокол'] },
  law_number: { type: 'integer' }, text: { type: 'string' }, why: { type: 'string' } }, ['kind', 'law_number', 'text', 'why']) }
const CRIT = obj({ critiques: { type: 'array', items: obj({ head: { type: 'integer' }, score: { type: 'integer', minimum: 1, maximum: 10 },
  point: { type: 'string' }, text: { type: 'string' } }, ['head', 'score', 'point', 'text']) }, amendments: AMENDS }, ['critiques', 'amendments'])
const BALLOT = obj({ ballot: { type: 'array', items: obj({ kind: { type: 'string', enum: ['добавить закон', 'заменить закон', 'удалить закон', 'протокол'] },
  law_number: { type: 'integer' }, text: { type: 'string' }, summary: { type: 'string' } }, ['kind', 'law_number', 'text', 'summary']) },
  concentrated: { type: 'array', items: obj({ head: { type: 'integer' }, point: { type: 'string' }, critics: { type: 'integer' } }, ['head', 'point', 'critics']) } },
  ['ballot', 'concentrated'])
const VOTES = obj({ votes: { type: 'array', items: obj({ n: { type: 'integer' }, vote: { type: 'string', enum: ['за', 'против'] } }, ['n', 'vote']) } }, ['votes'])
const REVISE = obj({ personal: { type: 'array', items: { type: 'string' } }, response: { type: 'string' } }, ['personal', 'response'])
const records = []
async function call(label, prompt, schema, check) {
  let last = null
  for (let a = 0; a < 2; a++) {  // не больше одного технического повтора
    let res = null, err = null
    try { res = await agent(prompt, { label: a ? `${label}#retry${a}` : label, phase: 'Шаг', schema }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(res))
    records.push({ label, attempt: a, retry: a > 0, t: now(), prompt, response: res, problem })
    if (res != null) last = res
    if (!problem) return res
  }
  return last
}
// Код-фильтр предметного содержания (решение совета): цифры, формулы, названия семейств, привязанные методы.
const SUBJ = new RegExp([
  '[0-9^≈√π∑∫]', '\\bln\\b', '\\blog', '\\bexp', 'sqrt', 'раскраск', 'разбиени', 'слагаем', 'близнец', 'подмножеств', 'коллатц', 'граф', 'прост(ое|ых|ые|ым)\\b',
  'харди', 'литтлвуд', 'рамануджан', 'асимптотик', 'сумм[аы] цифр', 'решет', 'нормальн(ое|ым) приближ', 'пуассон', 'кэли', 'эйлер',
  // поправка заседания 6: числительные словами и описательные формулы
  '\\bнол[ьяю]', '\\bнул[ьяю]', '\\bодин\\b', '\\bодн[аоиу]\\b', '\\bдв[ау]\\b', '\\bдвух\\b', '\\bтр[иёе]х?\\b', '\\bчетыр', '\\bпят[ьи]', '\\bшест[ьи]', '\\bсем[ьи]\\b',
  '\\bвосем', '\\bдевят', '\\bдесят', 'надцат', 'дцат', '\\bсорок', '\\bсто\\b', '\\bсот', 'тысяч', 'миллион', 'миллиард', 'половин', '\\bтрет[ьи]', 'вдвое', 'втрое', 'полтор',
  'десяток', 'порядка', 'квадрат', '\\bкуб', 'логарифм', 'экспонент', 'корен', 'корн[яе]'].join('|'), 'i')
const subjective = t => SUBJ.test(String(t || ''))
const okBatch = ids => r => { const m = new Map((r.items || []).map(x => [x.id, x]))
  return ids.every(i => { const x = m.get(i); return x && [x.estimate, x.lo, x.hi].every(v => typeof v === 'number' && isFinite(v)) }) ? null : 'формат пачки' }
const lawsText = h => h.laws.length ? 'Законы улья, в котором ты работаешь (соблюдай их):\n' + h.laws.map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const persText = (h, k) => (h.personal && h.personal[k] && h.personal[k].length) ? 'Твои личные правила (выработаны после критики коллег):\n' + h.personal[k].map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const protoText = h => h.roles.length > 1 ? `Протокол улья: ${h.roles.length} головы; пересмотр после знакомства с оценками других — ${h.delphi ? 'да' : 'нет'}; итог — ${h.agg === 'callosum' ? 'мозолистое тело' : 'медиана оценок голов'}.\n\n` : ''
const roleText = r => r ? `Твоя роль в улье: ${r}\n\n` : ''
const ASK = 'Для каждого вопроса нужна оценка, точный подсчёт не требуется. Для каждого ID верни: estimate — лучшая оценка (число); lo и hi — границы интервала, в который правильный ответ попадает с вероятностью 80 %; note — метод одной фразой.'

async function answer(name, h, qs, digest) {
  const ids = qs.map(q => q.id), qt = qs.map(q => `[${q.id}] ${q.text}`).join('\n')
  const D = digest ? `Сводка прошлых вопросов того же рода (правда и ошибки эталонного улья):\n${digest}\n\n` : ''
  const first = await parallel(h.roles.map((role, k) => () => call(`${name}:h${k + 1}`,
    `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}${persText(h, k)}${D}Вопросы:\n${qt}\n\n${ASK}`, BATCH, okBatch(ids))))
  let second = null
  if (h.delphi && h.roles.length > 1) {
    const fmt = b => (b?.items || []).map(x => `[${x.id}] ${x.estimate} [${x.lo}; ${x.hi}] — ${x.note}`).join('\n')
    second = await parallel(h.roles.map((role, k) => () => call(`${name}:h${k + 1}r`,
      `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}${persText(h, k)}${D}Твои первые оценки:\n${fmt(first[k])}\n\nПервые оценки других голов:\n` +
      first.map((b, j) => j === k ? '' : `Голова ${j + 1}:\n${fmt(b)}`).filter(Boolean).join('\n\n') + `\n\nПересмотри свои оценки, если доводы других тебя убеждают.\nВопросы:\n${qt}\n\n${ASK}`, BATCH, okBatch(ids))))
  }
  const heads = second || first
  let cal = null
  if (h.agg === 'callosum' && h.roles.length > 1) {
    const all = heads.map((b, j) => `Голова ${j + 1}:\n` + (b?.items || []).map(x => `[${x.id}] ${x.estimate} [${x.lo}; ${x.hi}] — ${x.note}`).join('\n')).join('\n\n')
    cal = await call(`${name}:cal`, `${A.no_tools}\n\n${lawsText(h)}Ты — мозолистое тело улья: сводишь оценки голов в итог улья.\n\n${all}\n\nВопросы:\n${qt}\n\n${ASK}`, BATCH, okBatch(ids))
  }
  return { first, second, cal }
}

async function legislate(name, h, fb, others) {
  const n = h.roles.length
  const props = await parallel(h.roles.map((role, k) => () => call(`${name}:crit${k + 1}`,
    `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}${persText(h, k)}Ты — голова ${k + 1} улья. Улей только что ответил на вопросы. Правда и ваши ответы:\n${fb}\n\n` +
    `Ответы других голов подробно:\n${others.filter((_, j) => j !== k).join('\n\n')}\n\n` +
    '1) Оцени каждую другую голову от 1 до 10 и покритикуй её: одно конкретное место, где она ошибается или может ошибиться на новых вопросах.\n' +
    `2) Предложи до двух поправок к законам или протоколу улья для НОВЫХ вопросов того же рода. Законы — только о том, как головы работают и взаимодействуют: без чисел, формул, названий типов задач и приёмов счёта для конкретного типа задач (такие поправки отклоняются автоматически). Законов не больше ${A.max_laws}. Поправки к протоколу: «пересмотр вкл», «пересмотр выкл», «итог медиана», «итог мозолистое тело».`,
    CRIT, r => Array.isArray(r.critiques) && Array.isArray(r.amendments) ? null : 'формат')))
  const rejected = [], passed = []
  props.forEach((p, k) => (p?.amendments || []).slice(0, 2).forEach(a => ((a.kind !== 'протокол' && subjective(a.text)) ? rejected : passed).push({ head: k + 1, ...a })))
  const critText = props.flatMap((p, k) => (p?.critiques || []).filter(c => c.head !== k + 1 && c.head >= 1 && c.head <= n).map(c => `Голова ${k + 1} о голове ${c.head}: оценка ${c.score}; место: «${c.point}» — ${c.text}`)).join('\n')
  const b = await call(`${name}:ballot`, `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}Ты — мозолистое тело улья. Поправки голов (прошли фильтр):\n` +
    (passed.map(a => `Голова ${a.head}: ${a.kind}${a.law_number ? ' №' + a.law_number : ''}: «${a.text}» — ${a.why}`).join('\n') || '(нет)') +
    '\n\nСведи их в бюллетень: объедини совпадающие, убери дубли, не больше 4 пунктов; сохрани формулировки голов, не добавляй своих.\n\n' +
    `Критика голов друг о друге:\n${critText || '(нет)'}\n\nОтметь в concentrated каждую голову, на которой сошлась критика: не меньше двух критиков указывают на одно и то же место (по смыслу). Иначе — пустой список.`,
    BALLOT, r => Array.isArray(r.ballot) && Array.isArray(r.concentrated) ? null : 'формат')
  const ballot = (b?.ballot || []).filter(x => x.kind === 'протокол' || !subjective(x.text)).slice(0, 4)
  const concAll = (b?.concentrated || []).filter(c => c.head >= 1 && c.head <= n && c.critics >= 2)
  // поправка заседания 6: за поколение пересматривает правила не больше одной головы — с наибольшим числом совпавших критиков, при равенстве меньший номер
  const conc = concAll.slice().sort((x, y) => y.critics - x.critics || x.head - y.head).slice(0, 1)
  const personal = (h.personal || h.roles.map(() => [])).map(x => [...x])
  const revisions = await parallel(conc.map(c => () => call(`${name}:rev${c.head}`,
    `${A.no_tools}\n\n${lawsText(h)}${persText(h, c.head - 1)}Ты — голова ${c.head} улья. Критика коллег сошлась на одном месте твоей работы: «${c.point}».\nВся критика о тебе:\n` +
    props.flatMap((p, k) => (p?.critiques || []).filter(x => x.head === c.head && k + 1 !== c.head).map(x => `— оценка ${x.score}; «${x.point}»: ${x.text}`)).join('\n') +
    `\n\nПравда и ответы улья:\n${fb}\n\nИзмени свои личные правила (не больше 4), чтобы исправить это место на НОВЫХ вопросах. Правила — о том, как работать: без чисел, формул, названий типов задач и приёмов для конкретного типа задач. Если считаешь критику неверной, объясни в response и верни прежние правила.`,
    REVISE, r => Array.isArray(r.personal) ? null : 'формат').then(r => ({ head: c.head, r }))))
  const rejectedPersonal = []
  for (const x of revisions) if (x?.r?.personal) {
    const ok = x.r.personal.filter(t => !subjective(t)); rejectedPersonal.push(...x.r.personal.filter(t => subjective(t)).map(t => ({ head: x.head, text: t })))
    personal[x.head - 1] = ok.slice(0, 4)
  }
  let votes = [], adopted = []
  if (ballot.length) {
    const bt = ballot.map((x, i) => `${i + 1}. ${x.kind}${x.law_number ? ' №' + x.law_number : ''}: «${x.text}» (${x.summary})`).join('\n')
    votes = await parallel(h.roles.map((role, k) => () => call(`${name}:vote${k + 1}`,
      `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}Итоги последних ответов улья:\n${fb}\n\nБюллетень поправок:\n${bt}\n\nПроголосуй по каждому пункту «за» или «против». Принимается пункт, за который не меньше двух голов.`,
      VOTES, r => Array.isArray(r.votes) ? null : 'формат')))
    ballot.forEach((x, i) => { const za = votes.filter(v => (v?.votes || []).some(y => y.n === i + 1 && y.vote === 'за')).length; if (za >= 2) adopted.push({ ...x, za }) })
  }
  let laws = h.laws.map(x => x)
  for (const x of adopted) if (x.kind === 'заменить закон' && x.law_number >= 1 && x.law_number <= laws.length) laws[x.law_number - 1] = x.text
  const del = new Set(adopted.filter(x => x.kind === 'удалить закон').map(x => x.law_number))
  laws = laws.filter((_, i) => !del.has(i + 1))
  for (const x of adopted) if (x.kind === 'добавить закон' && laws.length < A.max_laws) laws.push(x.text)
  const nh = { ...h, laws, personal }
  for (const x of adopted) if (x.kind === 'протокол') {
    if (/пересмотр вкл/.test(x.text)) nh.delphi = true
    if (/пересмотр выкл/.test(x.text)) nh.delphi = false
    if (/итог медиана/.test(x.text)) nh.agg = 'median'
    if (/мозолист/.test(x.text)) nh.agg = 'callosum'
  }
  return { proposals: props, rejected, ballot, concentrated: concAll, revising: conc, revisions, rejectedPersonal, votes, adopted, hive: nh }
}

let out = {}
if (A.mode === 'answer') {
  const names = Object.keys(A.hives)
  const res = await parallel(names.map(nm => () => answer(nm, A.hives[nm], A.questions, A.digests[nm] || '')))
  names.forEach((nm, i) => out[nm] = res[i])
} else {
  const names = Object.keys(A.hives)
  const res = await parallel(names.map(nm => () => legislate(nm, A.hives[nm], A.feedback[nm], A.others[nm])))
  names.forEach((nm, i) => out[nm] = res[i])
}
return { mode: A.mode, out, records }
