// Проверка MCP-сервера без головы: initialize → tools/list → observe → act → report_bug (рука из аргумента).
const { spawn } = require('child_process'); const path = require('path');
const arm = process.argv[2] || 'A', game = path.resolve(process.argv[3] || '../games/baeckerei/index.html');
const p = spawn('node', [path.join(__dirname, 'mcp_server.js')], { env: { ...process.env, TESTER_ARM: arm, TESTER_GAME: game, TESTER_OUT: '/tmp/claude-0/tester01_smoke_' + arm } });
let buf = '', id = 0; const wait = {}; p.stdout.on('data', d => { buf += d; let i; while ((i = buf.indexOf('\n')) >= 0) { const m = JSON.parse(buf.slice(0, i)); buf = buf.slice(i + 1); if (wait[m.id]) { wait[m.id](m); delete wait[m.id]; } } });
p.stderr.on('data', d => process.stderr.write(d));
const rpc = (method, params) => new Promise(res => { const k = ++id; wait[k] = res; p.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: k, method, params }) + '\n'); });
(async () => {
  const ini = await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'smoke', version: '0' } }); console.log('initialize:', JSON.stringify(ini.result.serverInfo));
  const tl = await rpc('tools/list', {}); console.log('tools:', tl.result.tools.map(t => t.name).join(', '));
  const ob = await rpc('tools/call', { name: 'game_observe', arguments: {} }); const c = ob.result.content[0]; console.log('observe:', c.type, c.type === 'text' ? c.text.length + ' знаков' : c.data.length + ' байт base64');
  const ac = await rpc('tools/call', { name: 'game_act', arguments: arm === 'S' ? { click_xy: [640, 400] } : { wait: 2 } }); console.log('act:', ac.result.content[0].text.replace(/\s+/g, ' '));
  const rb = await rpc('tools/call', { name: 'report_bug', arguments: { title: 'проба', category: 'other', expected: '-', actual: '-', confidence: 0.1 } }); console.log('report:', rb.result.content[0].text.replace(/\s+/g, ' '));
  if (arm === 'W') { const ss = await rpc('tools/call', { name: 'source_search', arguments: { pattern: 'MIN_PER_SEC = ' } }); console.log('search:', ss.result.content[0].text.slice(0, 160)); }
  p.stdin.end();
})();
