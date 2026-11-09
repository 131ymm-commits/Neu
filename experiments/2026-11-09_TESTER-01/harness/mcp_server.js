#!/usr/bin/env node
// TESTER-01, MCP-сервер игры (stdio, JSON-RPC 2.0, без зависимостей кроме Playwright).
// Рука задаётся переменной TESTER_ARM: S — только снимок экрана и клики по пикселям; A — текстовый API; W — API и исходник игры.
// TESTER_GAME — файл игры; TESTER_SEED — зерно; TESTER_OUT — куда писать след и отчёты (вне видимости головы); TESTER_MAX_ACTS — лимит действий.
const fs = require('fs'), path = require('path'), readline = require('readline');
const { GameEnv, MAX_WAIT_S } = require('./env');
const ARM = (process.env.TESTER_ARM || 'A').toUpperCase(), GAME = process.env.TESTER_GAME, SEED = +(process.env.TESTER_SEED || 1);
const OUT = process.env.TESTER_OUT || null, MAX_ACTS = +(process.env.TESTER_MAX_ACTS || 150);
const CATS = ['crash', 'softlock', 'wrong_number', 'rule', 'ui', 'save_load', 'economy', 'text', 'performance', 'other'];
let env = null, acts = 0, restarts = 0; const log = [];
const src = () => (GAME ? fs.readFileSync(GAME, 'utf8').split('\n') : []);
const save = () => { if (!OUT) return; fs.mkdirSync(OUT, { recursive: true }); fs.writeFileSync(path.join(OUT, 'session.json'), JSON.stringify({ arm: ARM, game: GAME, seed: SEED, acts, restarts, segments: log, reports: env ? env.reports : [] }, null, 1)); };
async function ensure() { if (!env) { env = await GameEnv.open(GAME, { seed: SEED }); log.push({ restart: 0, trace: env.trace }); } return env; }

const ACT_A = { type: 'object', description: 'Одно действие. Ровно одно поле.', properties: {
  click: { type: 'string', description: 'номер элемента из последнего game_observe, например "b12"' },
  map: { type: 'array', items: { type: 'number' }, description: 'клик по клетке карты [x, y]; клетки объектов — в state.map' },
  button: { type: 'string', enum: ['left', 'right'] }, drag: { type: 'array', items: { type: 'number' }, description: '[x1,y1,x2,y2] — перетащить по карте, доли холста 0..1' },
  key: { type: 'string', description: 'клавиша, например "r", "Escape", "Space"' }, fill: { type: 'array', description: '["i3", "текст"] — ввести в поле' },
  select: { type: 'array', description: '["s2", "пункт"] — выбрать в списке' }, wait: { type: 'number', description: `подождать столько секунд игрового экрана (виртуальных), до ${MAX_WAIT_S}` } } };
const ACT_S = { type: 'object', description: 'Одно действие. Ровно одно поле.', properties: {
  click_xy: { type: 'array', items: { type: 'number' }, description: '[x, y] — клик по точке экрана 1280×800' }, drag: ACT_A.properties.drag,
  key: ACT_A.properties.key, wait: ACT_A.properties.wait } };
const REPORT = { type: 'object', required: ['title', 'category', 'expected', 'actual', 'confidence'], properties: {
  title: { type: 'string', description: 'кратко, что сломано' }, category: { type: 'string', enum: CATS },
  object: { type: 'string', description: 'чего касается: имя кнопки, станка, предмета, человека, числа — как в игре' },
  expected: { type: 'string' }, actual: { type: 'string' }, repro: { type: 'string', description: 'как повторить, своими словами' },
  confidence: { type: 'number', description: 'уверенность 0..1, что это настоящий баг игры, а не ваша ошибка' } } };
const TOOLS = [
  { name: 'game_observe', description: ARM === 'S' ? 'Снимок экрана игры (PNG 1280×800).' : 'Экран игры текстом: области экрана, номера кнопок и полей, состояние игры (сводка, объекты карты с клетками, люди, журнал), новые ошибки страницы.', inputSchema: { type: 'object', properties: {} } },
  { name: 'game_act', description: 'Выполнить действие в игре. После действия игра идёт ещё 0,4 с; номера кнопок обновляет только game_observe.', inputSchema: ARM === 'S' ? ACT_S : ACT_A },
  { name: 'game_restart', description: 'Начать игру заново с тем же зерном (тот же старт). Удобно, чтобы проверить, повторяется ли баг.', inputSchema: { type: 'object', properties: {} } },
  { name: 'report_bug', description: 'Записать найденный баг. Привязывается к текущему моменту игры: сообщайте сразу, как увидели.', inputSchema: REPORT },
];
if (ARM === 'W') TOOLS.push(
  { name: 'source_search', description: 'Поиск по исходному коду игры (регулярное выражение JavaScript). Возвращает до 30 строк с номерами.', inputSchema: { type: 'object', required: ['pattern'], properties: { pattern: { type: 'string' } } } },
  { name: 'source_read', description: 'Строки исходного кода игры с номерами, не больше 150 за раз.', inputSchema: { type: 'object', required: ['from'], properties: { from: { type: 'number' }, to: { type: 'number' } } } });

const text = (o, isError = false) => ({ content: [{ type: 'text', text: typeof o === 'string' ? o : JSON.stringify(o, null, 1) }], isError });
async function call(name, a = {}) {
  if (name === 'game_observe') {
    const e = await ensure();
    if (ARM === 'S') { e.trace.push({ op: 'observe' }); return { content: [{ type: 'image', data: await e.screenshot(), mimeType: 'image/png' }] }; }
    return text(await e.observe());
  }
  if (name === 'game_act') {
    const e = await ensure();
    if (acts >= MAX_ACTS) return text(`Лимит действий (${MAX_ACTS}) исчерпан. Запишите найденное через report_bug и закончите.`, true);
    const keys = Object.keys(a || {}).filter(k => k !== 'button');
    const allowed = ARM === 'S' ? ['click_xy', 'drag', 'key', 'wait'] : ['click', 'map', 'drag', 'key', 'fill', 'select', 'wait'];
    if (keys.length !== 1 || !allowed.includes(keys[0])) return text(`Нужно ровно одно действие из: ${allowed.join(', ')}`, true);
    acts++; const r = await e.act(a); save(); return text({ ...r, acts_left: MAX_ACTS - acts }, !r.ok);
  }
  if (name === 'game_restart') {
    if (env) { await env.close(); } restarts++; const old = env ? env.reports : [];
    env = await GameEnv.open(GAME, { seed: SEED }); env.reports = old; log.push({ restart: restarts, trace: env.trace }); save();
    return text({ ok: true, note: 'игра начата заново с тем же зерном' });
  }
  if (name === 'report_bug') {
    const e = await ensure(); const r = { ...a, segment: restarts, confidence: Math.max(0, Math.min(1, +a.confidence || 0)) };
    if (!CATS.includes(r.category)) r.category = 'other';
    const rec = e.report(r); save(); return text({ ok: true, id: e.reports.length, step: rec.step });
  }
  if (name === 'source_search' && ARM === 'W') {
    let re; try { re = new RegExp(String(a.pattern), 'i'); } catch (err) { return text('неверное выражение: ' + err.message, true); }
    const out = []; src().forEach((l, i) => { if (out.length < 30 && re.test(l)) out.push(`${i + 1}: ${l.slice(0, 220)}`); });
    return text(out.length ? out.join('\n') : 'ничего не найдено');
  }
  if (name === 'source_read' && ARM === 'W') {
    const L = src(), from = Math.max(1, +a.from || 1), to = Math.min(L.length, Math.max(from, +a.to || from + 79), from + 149);
    return text(L.slice(from - 1, to).map((l, i) => `${from + i}: ${l.slice(0, 300)}`).join('\n') + `\n(всего строк ${L.length})`);
  }
  return text('нет такого инструмента', true);
}

const rl = readline.createInterface({ input: process.stdin }); let chain = Promise.resolve();
const send = m => process.stdout.write(JSON.stringify(m) + '\n');
rl.on('line', line => { chain = chain.then(async () => {
  let m; try { m = JSON.parse(line); } catch (e) { return; }
  if (m.method === 'initialize') return send({ jsonrpc: '2.0', id: m.id, result: { protocolVersion: (m.params && m.params.protocolVersion) || '2025-06-18', capabilities: { tools: {} }, serverInfo: { name: 'tester01-game', version: '0.1.0' } } });
  if (m.method === 'tools/list') return send({ jsonrpc: '2.0', id: m.id, result: { tools: TOOLS } });
  if (m.method === 'tools/call') { let r; try { r = await call(m.params.name, m.params.arguments || {}); } catch (e) { r = text('сбой среды: ' + (e && e.message), true); } return send({ jsonrpc: '2.0', id: m.id, result: r }); }
  if (m.method === 'ping') return send({ jsonrpc: '2.0', id: m.id, result: {} });
  if (m.id !== undefined && m.method) return send({ jsonrpc: '2.0', id: m.id, error: { code: -32601, message: 'method not found' } });
}); });
rl.on('close', () => { chain.then(async () => { save(); if (env) await env.close(); process.exit(0); }); });
