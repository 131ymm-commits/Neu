// Сборка одной страницы: стили, разметка, данные, библиотеки, код
const fs = require('fs'), zlib = require('zlib');
const A = '/tmp/game/app/', V = '/tmp/game/vendor/', Bd = '/tmp/game/build/';
const safe = s => s.replace(/<\/(script)/gi, '<\\/$1');
const countries = fs.readFileSync(Bd + 'countries.json', 'utf8');
const topo110 = fs.readFileSync(Bd + 'topo110m.json', 'utf8');
const blobJson = JSON.stringify({ topo50: JSON.parse(fs.readFileSync(Bd + 'topo50m.json', 'utf8')), places: JSON.parse(fs.readFileSync(Bd + 'places.json', 'utf8')) });
const blob = zlib.gzipSync(Buffer.from(blobJson), { level: 9 }).toString('base64');
const d3 = fs.readFileSync(V + 'd3.min.js', 'utf8'), tj = fs.readFileSync(V + 'topojson-client.min.js', 'utf8');
if (/<\/script/i.test(d3 + tj)) throw new Error('</script> в библиотеке');
const sim = fs.readFileSync('/tmp/game/sim.js', 'utf8'), eng = fs.readFileSync('/tmp/game/engine.js', 'utf8');
const app = ['core.js', 'map.js', 'ui.js', 'boot.js'].map(f => fs.readFileSync(A + f, 'utf8')).join('\n');
const html = `<title>Экономика форков</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Unbounded:wght@500;600&display=swap" rel="stylesheet">
<style>
${fs.readFileSync(A + 'style.css', 'utf8')}
</style>
${fs.readFileSync(A + 'body.html', 'utf8')}
<script id="d-countries" type="application/json">${safe(countries)}</script>
<script id="d-topo110" type="application/json">${safe(topo110)}</script>
<script id="d-blob" type="text/plain">${blob}</script>
<script>${d3}</script>
<script>${tj}</script>
<script>${sim}
${eng}</script>
<script>${app}</script>
`;
fs.writeFileSync('/tmp/game/ekonomika-forkov.html', html);
fs.writeFileSync('/tmp/game/preview.html', '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui;background:#fafaf9}img{max-width:100%}[hidden]{display:none!important}</style></head><body>' + html + '</body></html>');
console.log('страница:', (html.length / 1024 / 1024).toFixed(2), 'МБ; данные городов (gzip+base64):', (blob.length / 1024 / 1024).toFixed(2), 'МБ');
