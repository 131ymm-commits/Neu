// Сборка одной страницы «После вспышки»: стили, разметка, данные, библиотеки, модель, код
const fs = require('fs'), zlib = require('zlib');
const A = '/tmp/game3/app/', V = '/tmp/game/vendor/', B1 = '/tmp/game/build/', B3 = '/tmp/game3/build/';
const safe = s => s.replace(/<\/(script)/gi, '<\\/$1');
const countries = fs.readFileSync(B1 + 'countries.json', 'utf8');
const topo110 = fs.readFileSync(B1 + 'topo110m.json', 'utf8');
const blobJson = JSON.stringify({ topo50: JSON.parse(fs.readFileSync(B1 + 'topo50m.json', 'utf8')), places: JSON.parse(fs.readFileSync(B1 + 'places.json', 'utf8')) });
const blob = zlib.gzipSync(Buffer.from(blobJson), { level: 9 }).toString('base64');
const world = fs.readFileSync(B3 + 'world3.json', 'utf8');
const d3 = fs.readFileSync(V + 'd3.min.js', 'utf8'), tj = fs.readFileSync(V + 'topojson-client.min.js', 'utf8');
if (/<\/script/i.test(d3 + tj)) throw new Error('</script> в библиотеке');
const model = fs.readFileSync('/tmp/game3/world3.js', 'utf8');
const app = ['core.js', 'map.js', 'ui.js', 'ui2.js', 'ui3.js', 'mp.js', 'boot.js'].map(f => fs.readFileSync(A + f, 'utf8')).join('\n');
const html = `<title>После вспышки</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Unbounded:wght@500;600&display=swap" rel="stylesheet">
<style>
${fs.readFileSync(A + 'style.css', 'utf8')}
</style>
${fs.readFileSync(A + 'body.html', 'utf8')}
<script id="d-countries" type="application/json">${safe(countries)}</script>
<script id="d-topo110" type="application/json">${safe(topo110)}</script>
<script id="d-world" type="application/json">${safe(world)}</script>
<script id="d-blob" type="text/plain">${blob}</script>
<script>${d3}</script>
<script>${tj}</script>
<script>${safe(model)}</script>
<script>${safe(app)}</script>
`;
fs.writeFileSync('/tmp/game3/posle-vspyshki.html', html);
fs.writeFileSync('/tmp/game3/preview.html', '<!doctype html><html lang="ru" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>:root{color-scheme:dark;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui;background:#0B1219}img{max-width:100%}[hidden]{display:none!important}</style></head><body>' + html + '</body></html>');
const mock = fs.readFileSync('/tmp/game3/mock_claude3.js', 'utf8');
const pv = fs.readFileSync('/tmp/game3/preview.html', 'utf8'), i = pv.lastIndexOf('<script>');
fs.writeFileSync('/tmp/game3/preview_mock.html', pv.slice(0, i) + '<script>' + mock + '</script>\n' + pv.slice(i));
console.log('страница:', (html.length / 1024 / 1024).toFixed(2), 'МБ; мир:', (world.length / 1024).toFixed(0), 'КБ; города:', (blob.length / 1024 / 1024).toFixed(2), 'МБ');
