export const meta = { name: 'level05-org', description: 'LEVEL-05 организации: вложенное дерево 5→10→20 листьев по 10 матриц 2×2 mod p (без защиты / проверка другим путём), цепочка, одиночка одним вызовом, одиночка с равным бюджетом; калибровка сборки', phases: [{ title: 'Калибровка' }, { title: 'Организации' }, { title: 'Контроли' }] }
// Один сценарий, генотип — в задании (JOBS). Код НЕ считает ответ: только раскладывает матрицы по промптам,
// переставляет элементы (транспонирование) и сравнивает ответы голов по точному равенству.
//   tree   {N, check:'none'|'tr', share?}  — N листьев (по 10 матриц, 1 голова) + N−1 сборок (1 голова: A·B mod p).
//          check 'tr': лист проверяется ДРУГИМ ПУТЁМ — вторая голова считает M10ᵀ·M9ᵀ·…·M1ᵀ (= (M1…M10)ᵀ; промежуточные
//          произведения — суффиксы, а не префиксы; голова не знает, что это транспонирование); код транспонирует обратно
//          и сравнивает. При расхождении решает третий путь — «половины»: (M1…M5) и (M6…M10) двумя вызовами + сборка.
//          Большинство 2 из 3; если все три разные — берётся путь «половины» (флаг unresolved).
//          share: id задания check 'tr' на той же задаче — листья без защиты = первичные вызовы того задания
//          («копия A из того же пула», решение совета 13); своими вызовами идут только сборки.
//   chain  {N}             — N голов по очереди: голова k умножает бегущее произведение на свои 10 матриц.
//   single {N}             — одна голова, один вызов на всех 10·N матрицах; промпт обязывает довести счёт.
//   self   {N, match, K?}  — «одиночка с равным бюджетом»: цепочка вызовов одного промпта, каждый получает свои прошлые
//                             записи (контрольные точки, заметки), K = число вызовов задания match на поддереве N.
//   prod   {from, to, variant:'lr'|'tr'} — калибровка: одно произведение матриц задачи.
const TASKS = {"A0":{"p":764826343,"matrices":[[[471606634,444733695],[367664888,418835874]],[[215933126,8899422],[238948887,19587651]]]},"A1":{"p":417666593,"matrices":[[[216579757,231804895],[213010456,308451773]],[[158463757,207465641],[173489201,148382174]]]},"A2":{"p":325080157,"matrices":[[[107035355,4827601],[82356474,90199529]],[[70684526,200155925],[54349042,68653712]]]},"A3":{"p":150684659,"matrices":[[[26436299,116547232],[38624701,60628777]],[[41291415,47155997],[14869524,113322685]]]},"A4":{"p":200680387,"matrices":[[[22477153,78824365],[26408394,102173886]],[[346701,194011656],[80963158,80408048]]]},"A5":{"p":754951469,"matrices":[[[85552504,639141767],[305252622,295354639]],[[543436527,276751133],[413258148,185229663]]]},"A6":{"p":779206147,"matrices":[[[492790023,172892060],[204559377,478815928]],[[412816437,699131312],[595065768,177568246]]]},"A7":{"p":831733633,"matrices":[[[192115592,448803674],[412884105,38433864]],[[155809684,351003194],[149113816,435231480]]]},"A8":{"p":167332741,"matrices":[[[53826879,9368715],[850832,163184648]],[[58422633,85043966],[97246275,44604687]]]},"A9":{"p":789882377,"matrices":[[[355213032,680312722],[628428584,288076937]],[[111504771,211258061],[427191215,505921962]]]},"A10":{"p":745234541,"matrices":[[[679105283,448506554],[446204836,484960482]],[[457279894,726964069],[114724634,309298826]]]},"A11":{"p":150940061,"matrices":[[[109025381,65412367],[59848445,43308565]],[[15592632,24846668],[121776542,92398561]]]},"A12":{"p":663158317,"matrices":[[[238851192,281549875],[462275824,182921660]],[[658901212,156779661],[389267833,161702779]]]},"A13":{"p":650449799,"matrices":[[[586493873,350308042],[433065561,540636393]],[[80322880,401254679],[219341455,298479678]]]},"A14":{"p":751858153,"matrices":[[[212837466,539792797],[482244923,425369980]],[[356272859,634172189],[400982076,496979304]]]},"A15":{"p":376951973,"matrices":[[[294340395,250138346],[318566405,131542385]],[[208828848,251671439],[372137899,318517331]]]},"A16":{"p":919637513,"matrices":[[[97302984,465783269],[219586776,104449079]],[[390415651,199915312],[307224063,482321543]]]},"A17":{"p":883965343,"matrices":[[[74022429,663619311],[161931049,767283585]],[[622061799,171154377],[329982222,364722788]]]},"A18":{"p":967915777,"matrices":[[[430372551,942690325],[753244514,889576300]],[[415654587,840876705],[430374819,754147770]]]},"A19":{"p":107294177,"matrices":[[[64086580,44844869],[34650694,68650568]],[[46517826,32237850],[95120971,84455392]]]},"T0":{"p":203130661,"matrices":[[[254,594],[898,412]],[[883,958],[752,49]],[[990,336],[776,502]],[[871,891],[935,109]],[[680,108],[407,154]],[[361,952],[466,448]],[[530,913],[719,863]],[[235,845],[50,409]],[[270,41],[463,162]],[[930,127],[111,653]]]},"T1":{"p":469244603,"matrices":[[[311,710],[87,737]],[[504,204],[24,535]],[[210,17],[317,287]],[[846,592],[213,587]],[[478,91],[22,919]],[[893,276],[885,86]],[[754,800],[550,303]],[[388,828],[817,871]],[[57,411],[607,344]],[[514,657],[652,6]]]},"T2":{"p":311697593,"matrices":[[[546,20],[648,704]],[[352,547],[982,510]],[[346,400],[86,96]],[[305,118],[435,587]],[[209,749],[273,269]],[[981,654],[481,380]],[[594,957],[405,533]],[[290,839],[245,311]],[[21,232],[540,845]],[[729,549],[876,545]]]},"T3":{"p":321575831,"matrices":[[[442,5],[272,508]],[[44,646],[763,817]],[[718,14],[450,751]],[[923,555],[621,634]],[[272,115],[401,238]],[[43,581],[924,380]],[[911,708],[683,738]],[[369,171],[661,461]],[[902,319],[433,534]],[[887,539],[953,267]]]},"T4":{"p":352824679,"matrices":[[[454,828],[76,522]],[[678,590],[19,351]],[[978,74],[247,983]],[[999,274],[389,175]],[[406,812],[581,383]],[[111,478],[90,125]],[[398,245],[309,631]],[[453,811],[366,404]],[[420,158],[576,587]],[[348,440],[414,247]]]},"T5":{"p":381325547,"matrices":[[[563,904],[949,35]],[[900,317],[14,794]],[[13,606],[968,352]],[[807,116],[836,365]],[[456,21],[943,67]],[[774,12],[252,192]],[[21,769],[724,830]],[[759,262],[440,129]],[[110,373],[139,142]],[[856,362],[846,799]]]},"T6":{"p":100657937,"matrices":[[[394,643],[620,472]],[[678,617],[744,680]],[[84,670],[436,774]],[[907,409],[746,10]],[[145,27],[371,86]],[[955,431],[512,5]],[[773,453],[711,241]],[[309,77],[898,333]],[[191,962],[20,226]],[[888,344],[868,340]]]},"T7":{"p":381148589,"matrices":[[[170,119],[933,446]],[[700,276],[317,508]],[[994,815],[138,395]],[[843,269],[242,653]],[[817,637],[926,388]],[[725,162],[984,263]],[[861,102],[380,582]],[[442,972],[72,782]],[[313,553],[873,567]],[[830,550],[122,800]]]},"T8":{"p":259689623,"matrices":[[[338,193],[146,337]],[[809,168],[713,398]],[[153,323],[468,813]],[[719,999],[799,563]],[[275,536],[382,324]],[[928,68],[272,292]],[[203,473],[418,301]],[[85,796],[685,348]],[[153,704],[318,562]],[[352,892],[610,645]]]},"T9":{"p":652107941,"matrices":[[[685,792],[37,103]],[[859,421],[447,201]],[[553,259],[954,34]],[[269,506],[854,890]],[[857,431],[296,653]],[[373,1],[113,191]],[[499,587],[316,121]],[[196,559],[699,424]],[[149,0],[0,640]],[[826,6],[903,792]]]},"T10":{"p":367553929,"matrices":[[[876,242],[14,142]],[[447,749],[134,985]],[[485,936],[940,336]],[[35,336],[321,636]],[[677,586],[698,991]],[[878,264],[143,390]],[[639,591],[847,802]],[[772,166],[53,877]],[[556,739],[917,785]],[[625,674],[917,93]]]},"T11":{"p":249783491,"matrices":[[[805,487],[90,973]],[[336,399],[419,870]],[[712,592],[596,297]],[[61,433],[550,717]],[[424,531],[155,220]],[[690,153],[537,607]],[[475,554],[151,636]],[[518,900],[282,158]],[[755,491],[699,94]],[[382,483],[943,27]]]},"F0":{"p":136241093,"matrices":[[[689,350],[612,110]],[[678,891],[882,358]],[[95,631],[553,420]],[[423,69],[743,796]],[[329,713],[160,950]]]},"F1":{"p":946023401,"matrices":[[[492,894],[275,742]],[[92,84],[680,628]],[[885,742],[560,876]],[[471,356],[42,908]],[[179,67],[464,616]]]},"F2":{"p":450148261,"matrices":[[[86,792],[261,499]],[[314,722],[922,290]],[[619,573],[850,845]],[[823,9],[937,406]],[[685,909],[605,748]]]},"F3":{"p":468049163,"matrices":[[[383,186],[371,138]],[[238,228],[817,431]],[[607,324],[177,737]],[[838,316],[802,959]],[[359,347],[215,3]]]},"F4":{"p":253949411,"matrices":[[[813,721],[216,151]],[[188,369],[970,233]],[[177,102],[303,909]],[[653,429],[387,101]],[[272,190],[332,117]]]},"F5":{"p":982379179,"matrices":[[[120,315],[269,463]],[[727,410],[566,145]],[[699,549],[562,5]],[[5,487],[242,916]],[[124,627],[770,546]]]},"F6":{"p":333840763,"matrices":[[[884,97],[197,680]],[[295,760],[272,145]],[[141,578],[925,779]],[[480,515],[993,725]],[[185,495],[841,746]]]},"F7":{"p":855176089,"matrices":[[[673,205],[382,324]],[[782,685],[8,664]],[[110,563],[640,197]],[[557,558],[419,537]],[[565,769],[259,362]]]},"F8":{"p":455292053,"matrices":[[[793,942],[181,168]],[[519,656],[360,443]],[[582,535],[104,934]],[[822,560],[304,855]],[[193,768],[220,164]]]},"F9":{"p":238429823,"matrices":[[[454,96],[370,154]],[[530,901],[146,236]],[[433,737],[947,113]],[[422,917],[628,119]],[[774,686],[742,684]]]},"F10":{"p":498056687,"matrices":[[[635,930],[623,935]],[[407,591],[826,871]],[[13,997],[753,14]],[[588,989],[344,963]],[[369,743],[611,823]]]},"F11":{"p":150764039,"matrices":[[[230,729],[92,822]],[[443,398],[188,716]],[[390,909],[725,146]],[[843,608],[867,107]],[[386,311],[581,450]]]}}   // {id: {p, matrices}}
const JOBS = [{"id":"asm-A0","kind":"prod","task":"A0","from":0,"to":2,"variant":"lr"},{"id":"asm-A1","kind":"prod","task":"A1","from":0,"to":2,"variant":"lr"},{"id":"asm-A2","kind":"prod","task":"A2","from":0,"to":2,"variant":"lr"},{"id":"asm-A3","kind":"prod","task":"A3","from":0,"to":2,"variant":"lr"},{"id":"asm-A4","kind":"prod","task":"A4","from":0,"to":2,"variant":"lr"},{"id":"asm-A5","kind":"prod","task":"A5","from":0,"to":2,"variant":"lr"},{"id":"asm-A6","kind":"prod","task":"A6","from":0,"to":2,"variant":"lr"},{"id":"asm-A7","kind":"prod","task":"A7","from":0,"to":2,"variant":"lr"},{"id":"asm-A8","kind":"prod","task":"A8","from":0,"to":2,"variant":"lr"},{"id":"asm-A9","kind":"prod","task":"A9","from":0,"to":2,"variant":"lr"},{"id":"asm-A10","kind":"prod","task":"A10","from":0,"to":2,"variant":"lr"},{"id":"asm-A11","kind":"prod","task":"A11","from":0,"to":2,"variant":"lr"},{"id":"asm-A12","kind":"prod","task":"A12","from":0,"to":2,"variant":"lr"},{"id":"asm-A13","kind":"prod","task":"A13","from":0,"to":2,"variant":"lr"},{"id":"asm-A14","kind":"prod","task":"A14","from":0,"to":2,"variant":"lr"},{"id":"asm-A15","kind":"prod","task":"A15","from":0,"to":2,"variant":"lr"},{"id":"asm-A16","kind":"prod","task":"A16","from":0,"to":2,"variant":"lr"},{"id":"asm-A17","kind":"prod","task":"A17","from":0,"to":2,"variant":"lr"},{"id":"asm-A18","kind":"prod","task":"A18","from":0,"to":2,"variant":"lr"},{"id":"asm-A19","kind":"prod","task":"A19","from":0,"to":2,"variant":"lr"},{"id":"p10-T0","kind":"prod","task":"T0","from":0,"to":10,"variant":"lr"},{"id":"tr10-T0","kind":"prod","task":"T0","from":0,"to":10,"variant":"tr"},{"id":"p10-T1","kind":"prod","task":"T1","from":0,"to":10,"variant":"lr"},{"id":"tr10-T1","kind":"prod","task":"T1","from":0,"to":10,"variant":"tr"},{"id":"p10-T2","kind":"prod","task":"T2","from":0,"to":10,"variant":"lr"},{"id":"tr10-T2","kind":"prod","task":"T2","from":0,"to":10,"variant":"tr"},{"id":"p10-T3","kind":"prod","task":"T3","from":0,"to":10,"variant":"lr"},{"id":"tr10-T3","kind":"prod","task":"T3","from":0,"to":10,"variant":"tr"},{"id":"p10-T4","kind":"prod","task":"T4","from":0,"to":10,"variant":"lr"},{"id":"tr10-T4","kind":"prod","task":"T4","from":0,"to":10,"variant":"tr"},{"id":"p10-T5","kind":"prod","task":"T5","from":0,"to":10,"variant":"lr"},{"id":"tr10-T5","kind":"prod","task":"T5","from":0,"to":10,"variant":"tr"},{"id":"p10-T6","kind":"prod","task":"T6","from":0,"to":10,"variant":"lr"},{"id":"tr10-T6","kind":"prod","task":"T6","from":0,"to":10,"variant":"tr"},{"id":"p10-T7","kind":"prod","task":"T7","from":0,"to":10,"variant":"lr"},{"id":"tr10-T7","kind":"prod","task":"T7","from":0,"to":10,"variant":"tr"},{"id":"p10-T8","kind":"prod","task":"T8","from":0,"to":10,"variant":"lr"},{"id":"tr10-T8","kind":"prod","task":"T8","from":0,"to":10,"variant":"tr"},{"id":"p10-T9","kind":"prod","task":"T9","from":0,"to":10,"variant":"lr"},{"id":"tr10-T9","kind":"prod","task":"T9","from":0,"to":10,"variant":"tr"},{"id":"p10-T10","kind":"prod","task":"T10","from":0,"to":10,"variant":"lr"},{"id":"tr10-T10","kind":"prod","task":"T10","from":0,"to":10,"variant":"tr"},{"id":"p10-T11","kind":"prod","task":"T11","from":0,"to":10,"variant":"lr"},{"id":"tr10-T11","kind":"prod","task":"T11","from":0,"to":10,"variant":"tr"},{"id":"p5-F0","kind":"prod","task":"F0","from":0,"to":5,"variant":"lr"},{"id":"p5-F1","kind":"prod","task":"F1","from":0,"to":5,"variant":"lr"},{"id":"p5-F2","kind":"prod","task":"F2","from":0,"to":5,"variant":"lr"},{"id":"p5-F3","kind":"prod","task":"F3","from":0,"to":5,"variant":"lr"},{"id":"p5-F4","kind":"prod","task":"F4","from":0,"to":5,"variant":"lr"},{"id":"p5-F5","kind":"prod","task":"F5","from":0,"to":5,"variant":"lr"},{"id":"p5-F6","kind":"prod","task":"F6","from":0,"to":5,"variant":"lr"},{"id":"p5-F7","kind":"prod","task":"F7","from":0,"to":5,"variant":"lr"},{"id":"p5-F8","kind":"prod","task":"F8","from":0,"to":5,"variant":"lr"},{"id":"p5-F9","kind":"prod","task":"F9","from":0,"to":5,"variant":"lr"},{"id":"p5-F10","kind":"prod","task":"F10","from":0,"to":5,"variant":"lr"},{"id":"p5-F11","kind":"prod","task":"F11","from":0,"to":5,"variant":"lr"}]    // [{id, kind, task, ...}]
const NO = 'Не используй никакие инструменты, не исполняй код и не открывай файлы: считай сам, в уме, опираясь только на текст ниже.'
const MAT = { a: { type: 'string' }, b: { type: 'string' }, c: { type: 'string' }, d: { type: 'string' } }
const CONF = { type: 'number', description: 'вероятность от 0 до 1, что все четыре числа точны' }
const OUT = { type: 'object', properties: { ...MAT, confidence: CONF }, required: ['a', 'b', 'c', 'd', 'confidence'] }
const OUT1 = { type: 'object', properties: { ...MAT, confidence: CONF, completed: { type: 'boolean', description: 'true — счёт доведён до конца; false — не довёл (тогда числа не засчитываются)' } }, required: ['a', 'b', 'c', 'd', 'confidence', 'completed'] }
const OUTS = { type: 'object', properties: {
  checkpoints: { type: 'array', description: 'новые или исправленные контрольные точки этого обращения', items: { type: 'object', properties: { k: { type: 'integer', description: 'сколько первых матриц перемножено' }, ...MAT }, required: ['k', 'a', 'b', 'c', 'd'] } },
  note: { type: 'string', description: 'заметка себе на следующее обращение (план, что перепроверить), 1–3 фразы' },
  answer: { type: 'object', description: 'итог M1·…·Mn mod p; пустые строки, если счёт не закончен', properties: MAT, required: ['a', 'b', 'c', 'd'] },
  done: { type: 'boolean', description: 'true — счёт закончен и перепроверен, дальнейшие обращения не нужны' },
  confidence: CONF }, required: ['checkpoints', 'note', 'answer', 'done', 'confidence'] }

const fmt = m => `[[${m[0][0]}, ${m[0][1]}], [${m[1][0]}, ${m[1][1]}]]`
const T = m => [[m[0][0], m[1][0]], [m[0][1], m[1][1]]]
const hash = s => { let h1 = 0xdeadbeef, h2 = 0x41c6ce57; for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 2654435761); h2 = Math.imul(h2 ^ c, 1597334677) } h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909); h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909); return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16) }
// строгий разбор: только цифры (пробелы по краям допускаются), значение < p; иначе — сбой формата. Ответ не чинится.
function parse(r, p) {
  if (!r) return { fmt: 'null' }
  const xs = [r.a, r.b, r.c, r.d]
  for (const s of xs) {
    if (typeof s !== 'string' || !/^[0-9]+$/.test(s.trim())) return { fmt: 'nonint' }
    if (BigInt(s.trim()) >= BigInt(p)) return { fmt: 'range' }
  }
  const v = xs.map(s => BigInt(s.trim()).toString())
  return { m: [[v[0], v[1]], [v[2], v[3]]], key: v.join(',') }
}
const call = (p, o) => agent(p, o).catch(() => agent(p, o).catch(() => null))
const records = []
const out = {}
function prodPrompt(ms, p) {
  const M = ms.length, tail = M > 2 ? `M1·M2·…·M${M}` : 'M1·M2'
  return `${NO}\n\nПеремножь по порядку ${M} матриц 2×2 по модулю ${p} (после каждого умножения бери остаток по модулю ${p}):\n${ms.map((m, i) => `M${i + 1} = ${fmt(m)}`).join('\n')}\n\nНайди ${tail} mod ${p} = [[a, b], [c, d]]. Верни a, b, c, d и confidence.`
}
// один вызов «перемножь по порядку»; ctx = {job, node, role}; возвращает разобранный результат {m, key} или {fmt}
async function prod(ms, p, ctx, phase) {
  const q = prodPrompt(ms, p), label = `${ctx.job}:${ctx.node}:${ctx.role}`
  const r = await call(q, { label, phase: phase || 'Организации', schema: OUT })
  const x = parse(r, p)
  records.push({ ...ctx, label, n: ms.length, h: hash(q), raw: r, key: x.key || null, fmt: x.fmt || null })
  return x
}
// детерминированные «отложенные» значения для обмена между заданиями (share, match)
const def = {}
const deferred = k => def[k] || (def[k] = (() => { let res; const pr = new Promise(r => { res = r }); return { pr, res } })())

const split = (lo, hi) => lo + Math.floor((hi - lo) / 2)
async function leaf(job, t, i) {
  const ms = t.matrices.slice(10 * i, 10 * i + 10), node = `L${i}`
  const ctx = role => ({ job: job.id, node, role, lo: i, hi: i + 1 })
  if (job.share) {                                               // лист без защиты = первичный вызов задания с проверкой
    const x = await deferred(`${job.share}:P${i}`).pr
    return { ...x, calls: 0, shared: true }
  }
  const pP = prod(ms, t.p, ctx('P'))
  if (job.check === 'tr') {
    pP.then(x => deferred(`${job.id}:P${i}`).res(x))
    const pR = prod(ms.map(T).reverse(), t.p, ctx('TR')).then(x => x.m ? { m: T(x.m), key: T(x.m).flat().join(',') } : x)
    const [P, R] = await Promise.all([pP, pR])
    if (P.key && P.key === R.key) return { ...P, calls: 2, path: 'P=TR' }
    const [H1, H2] = await Promise.all([prod(ms.slice(0, 5), t.p, ctx('H1')), prod(ms.slice(5), t.p, ctx('H2'))])
    let H = { fmt: 'child' }
    if (H1.m && H2.m) H = await prod([H1.m, H2.m], t.p, ctx('HC'))
    const calls = 2 + 2 + (H1.m && H2.m ? 1 : 0)
    if (H.key && H.key === P.key) return { ...P, calls, path: 'P=H' }
    if (H.key && H.key === R.key) return { ...R, calls, path: 'TR=H' }
    return { ...H, calls, path: 'unresolved' }                   // все три разные (или сбои) — берётся путь «половины»
  }
  const P = await pP
  return { ...P, calls: 1, path: 'P' }
}
async function node(job, t, lo, hi, nodes) {
  if (hi - lo === 1) { const x = await leaf(job, t, lo); nodes[`${lo}:${hi}`] = x; return x }
  const m = split(lo, hi)
  const [A, B] = await Promise.all([node(job, t, lo, m, nodes), node(job, t, m, hi, nodes)])
  let x = { fmt: 'child' }, calls = 0
  if (A.m && B.m) { x = await prod([A.m, B.m], t.p, { job: job.id, node: `S${lo}:${hi}`, role: 'A', lo, hi }); calls = 1 }
  nodes[`${lo}:${hi}`] = { ...x, calls }; return nodes[`${lo}:${hi}`]
}
const sub = (nodes, lo, hi) => Object.entries(nodes).filter(([k]) => { const [a, b] = k.split(':').map(Number); return a >= lo && b <= hi }).reduce((s, [, v]) => s + (v.calls || 0), 0)

async function runTree(job, t) {
  const nodes = {}
  const root = await node(job, t, 0, job.N, nodes)
  const calls = sub(nodes, 0, job.N)
  deferred(`${job.id}:calls`).res(Object.fromEntries([5, 10, 20].filter(n => n <= job.N).map(n => [n, sub(nodes, 0, n)])))
  return { key: root.key || null, fmt: root.fmt || null, calls, nodes: Object.fromEntries(Object.entries(nodes).map(([k, v]) => [k, { key: v.key || null, fmt: v.fmt || null, calls: v.calls, path: v.path, shared: v.shared }])) }
}
async function runChain(job, t) {
  let R = null, calls = 0; const links = []
  for (let k = 0; k < job.N; k++) {
    const ms = t.matrices.slice(10 * k, 10 * k + 10)
    const x = await prod(R ? [R, ...ms] : ms, t.p, { job: job.id, node: `C${k}`, role: 'link', lo: k, hi: k + 1 }); calls++
    links.push({ key: x.key || null, fmt: x.fmt || null })
    if (!x.m) return { key: null, fmt: x.fmt, calls, links }
    R = x.m
  }
  return { key: links[links.length - 1].key, fmt: null, calls, links }
}
async function runSingle(job, t) {
  const ms = t.matrices.slice(0, 10 * job.N)
  const q = `${prodPrompt(ms, t.p)}\n\nДоведи счёт до конца, все ${ms.length} умножений: оценка, частичный ответ или отказ не засчитываются. Если всё же не довёл счёт до конца — поставь completed = false.`
  const r = await call(q, { label: `${job.id}:single`, phase: 'Контроли', schema: OUT1 })
  const x = parse(r, t.p)
  const refused = !!r && r.completed === false
  records.push({ job: job.id, node: 'single', role: 'single', n: ms.length, h: hash(q), raw: r, key: x.key || null, fmt: x.fmt || null, refused })
  return { key: refused ? null : (x.key || null), fmt: x.fmt || null, refused, calls: 1 }
}
function selfPrompt(ms, p, K, j, cps, notes, ans) {
  const n = ms.length
  const cpt = Object.keys(cps).map(Number).sort((a, b) => a - b).map(k => `P_${k} = ${fmt(cps[k])}`).join('\n') || '— пока нет'
  const nt = notes.length ? notes.map((s, i) => `обращение ${i + 1}: ${s}`).join('\n') : '— пока нет'
  return `${NO}\n\nЗадача: перемножь по порядку ${n} матриц 2×2 по модулю ${p} (после каждого умножения бери остаток по модулю ${p}):\n${ms.map((m, i) => `M${i + 1} = ${fmt(m)}`).join('\n')}\n\nНайди M1·M2·…·M${n} mod ${p}.\n\n` +
    `Работа идёт по обращениям. Всего у тебя ${K} обращений; это обращение ${j} из ${K}. Между обращениями ты ничего не помнишь, кроме своих записей ниже (новой информации нет — только твои прошлые результаты).\n\n` +
    `Твои контрольные точки (P_k = M1·…·Mk mod ${p}):\n${cpt}\n\nТвои заметки:\n${nt}\n\nТвой последний данный ответ: ${ans ? fmt(ans) : '— пока нет'}\n\n` +
    `Что делать: продолжи счёт от последней контрольной точки, которой доверяешь; можно перепроверять прошлые точки (пересчитать отрезок заново или другим порядком) и исправлять их. Верни checkpoints (новые или исправленные точки этого обращения, k — сколько первых матриц перемножено), note (план на следующее обращение), answer (итог — только когда весь счёт закончен; иначе пустые строки), done и confidence.` +
    (j === K ? `\n\nЭто ПОСЛЕДНЕЕ обращение: answer обязателен.` : '')
}
async function runSelf(job, t) {
  let K = job.K
  if (job.match) { const c = await deferred(`${job.match}:calls`).pr; K = c[job.N] || job.K }
  const ms = t.matrices.slice(0, 10 * job.N), cps = {}, notes = [], trace = []
  let ans = null, ansKey = null, calls = 0, fmtFail = 0
  for (let j = 1; j <= K; j++) {
    const q = selfPrompt(ms, t.p, K, j, cps, notes, ans)
    const r = await call(q, { label: `${job.id}:self${j}`, phase: 'Контроли', schema: OUTS }); calls++
    const a = r && r.answer ? parse(r.answer, t.p) : { fmt: 'null' }
    const empty = r && r.answer && [r.answer.a, r.answer.b, r.answer.c, r.answer.d].every(s => typeof s === 'string' && s.trim() === '')
    const cpOut = []
    for (const c of (r && Array.isArray(r.checkpoints) ? r.checkpoints : [])) {
      const x = parse(c, t.p)
      if (x.m && Number.isInteger(c.k) && c.k >= 1 && c.k <= ms.length) { cps[c.k] = x.m; cpOut.push({ k: c.k, key: x.key }) } else { cpOut.push({ k: c && c.k, fmt: x.fmt || 'k' }); fmtFail++ }
    }
    if (!r) fmtFail++
    else if (!empty && !a.m) fmtFail++
    if (a.m) { ans = a.m; ansKey = a.key }
    if (r && typeof r.note === 'string') notes.push(r.note.slice(0, 400))
    trace.push({ j, h: hash(q), checkpoints: cpOut, answer: a.key || null, done: !!(r && r.done), confidence: r && r.confidence })
    records.push({ job: job.id, node: `self${j}`, role: 'self', n: ms.length, h: hash(q), raw: r, key: a.key || null, fmt: r ? (empty ? null : (a.fmt || null)) : 'null' })
    if (r && r.done && a.m) break                                // голова сама решила, что закончила (бюджет — потолок, не обязанность)
  }
  return { key: ansKey, fmt: ansKey ? null : 'noanswer', K, calls, fmt_fail_calls: fmtFail, trace }
}
async function runProd(job, t) {
  const ms = t.matrices.slice(job.from, job.to)
  const x = job.variant === 'tr' ? await prod(ms.map(T).reverse(), t.p, { job: job.id, node: 'cal', role: 'TR' }, 'Калибровка').then(x => x.m ? { m: T(x.m), key: T(x.m).flat().join(',') } : x)
    : await prod(ms, t.p, { job: job.id, node: 'cal', role: 'P' }, 'Калибровка')
  return { key: x.key || null, fmt: x.fmt || null, calls: 1 }
}
const RUN = { tree: runTree, chain: runChain, single: runSingle, self: runSelf, prod: runProd }
await parallel(JOBS.map(j => async () => {
  try { out[j.id] = { ...(await RUN[j.kind](j, TASKS[j.task])), kind: j.kind, task: j.task } }
  catch (e) {                                                    // сбой задания не должен подвесить связанные (share, match)
    out[j.id] = { error: String(e), kind: j.kind, task: j.task }; deferred(`${j.id}:calls`).res({})
    for (let i = 0; i < 20; i++) deferred(`${j.id}:P${i}`).res({ fmt: 'error' })
  }
}))
return { out, records }
