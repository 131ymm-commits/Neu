// Сборка: одна страница для артефакта (без doctype — его добавляет площадка)
// и полный html-документ для открытия файлом в браузере.  node build/assemble.js
const fs = require('fs'), path = require('path');
const SRC = path.join(__dirname, '..'), APP = path.join(SRC, 'app'), OUT = path.join(SRC, '..');
const safe = s => { if (/<\/script/i.test(s)) throw new Error('</script> внутри кода'); return s; };
const read = f => fs.readFileSync(f, 'utf8');
const fonts = 'https://fonts.googleapis.com/css2?family=Russo+One&family=Oswald:wght@500;600;700&family=IBM+Plex+Sans+Condensed:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap';
const page = `<title>Бронеколода</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="${fonts}" rel="stylesheet">
<style>
${read(path.join(APP, 'style.css'))}
</style>
${read(path.join(APP, 'body.html'))}
<script>
${safe(read(path.join(SRC, 'engine.js')))}
</script>
<script>
${safe(read(path.join(APP, 'art.js')))}
${safe(read(path.join(APP, 'ui.js')))}
</script>
`;
const full = `<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
${page.replace(/<\/style>\n[\s\S]*$/, '</style>')}
</head>
<body>
${page.slice(page.indexOf('</style>') + 9)}</body>
</html>
`;
fs.mkdirSync(path.join(SRC, 'build', 'out'), { recursive: true });
fs.writeFileSync(path.join(OUT, 'bronekoloda.html'), full);
fs.writeFileSync(path.join(SRC, 'build', 'out', 'artifact.html'), page);
console.log('bronekoloda.html:', (full.length / 1024).toFixed(1), 'КБ; страница артефакта:', (page.length / 1024).toFixed(1), 'КБ');
