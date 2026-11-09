// Сухой прогон на заглушке (без головы): тестировщик-сценарий ходит через MCP-сервер, как голова, и пишет отчёты.
//   node stub_tester.js <рука A|W> <файл игры> <out> '<JSON: [{label}|{map}|{wait}|{report:{...}}]>'
const { spawn } = require('child_process'); const path = require('path');
const [arm, game, out, plan] = [process.argv[2], path.resolve(process.argv[3]), process.argv[4], JSON.parse(process.argv[5])];
const p = spawn('node', [path.join(__dirname, 'mcp_server.js')], { env: { ...process.env, TESTER_ARM: arm, TESTER_GAME: game, TESTER_OUT: out } });
let buf = '', id = 0; const wait = {}; p.stdout.on('data', d => { buf += d; let i; while ((i = buf.indexOf('\n')) >= 0) { const m = JSON.parse(buf.slice(0, i)); buf = buf.slice(i + 1); if (wait[m.id]) { wait[m.id](m); delete wait[m.id]; } } });
p.stderr.on('data', d => process.stderr.write(d));
const rpc = (method, params) => new Promise(res => { const k = ++id; wait[k] = res; p.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: k, method, params }) + '\n'); });
const call = async (name, args) => JSON.parse((await rpc('tools/call', { name, arguments: args })).result.content[0].text);
(async () => {
  await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'stub', version: '0' } });
  for (const st of plan) {
    if (st.report) { console.log('report', JSON.stringify(await call('report_bug', st.report))); continue; }
    if (st.label) { const o = await call('game_observe', {}); const h = o.controls.find(c => c.slice(c.indexOf(':') + 1).includes(st.label) && (!st.region || c.split(' ')[1].replace(':', '') === st.region)); if (!h) { console.log('нет', st.label); continue; } await call('game_act', { click: h.split(' ')[0] }); continue; }
    await call('game_observe', {}); await call('game_act', st);
  }
  p.stdin.end();
})();
