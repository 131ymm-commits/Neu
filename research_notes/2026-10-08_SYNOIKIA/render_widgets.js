// JSX-схема виджета Claude Docs → статический SVG (светлая тема), для копии документа в репозитории.
// Нужен esbuild: npm i esbuild@0.24.0; запуск: node render_widgets.js economy.widget.jsx:economy.svg participation.widget.jsx:participation.svg
const esbuild = require('esbuild'), fs = require('fs');
const COL = {'--cds-chart-axis': '#8a8f98', '--cds-chart-categorical-1': '#2f6fdb', '--cds-text-primary': '#1f2328',
             '--cds-text-secondary': '#57606a', '--cds-chart-reference-tint': '#f1f3f6'};
const KEBAB = {fontSize: 'font-size', fontWeight: 'font-weight', textAnchor: 'text-anchor', strokeWidth: 'stroke-width',
               fillOpacity: 'fill-opacity', markerEnd: 'marker-end'};
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
const col = v => String(v).replace(/var\((--[\w-]+)\)/g, (_, k) => { if (!COL[k]) throw new Error('нет цвета ' + k); return COL[k]; });
function h(tag, props, ...kids) {
  const a = Object.entries(props || {}).filter(([k]) => !k.startsWith('data-claude'))
    .map(([k, v]) => ` ${KEBAB[k] || k}="${esc(col(v))}"`).join('');
  const body = kids.flat(Infinity).filter(x => x !== null && x !== undefined && x !== false)
    .map(x => (typeof x === 'string' && !x.startsWith('<')) ? esc(x) : x).join('');
  return `<${tag}${a}>${body}</${tag}>`;
}
for (const [src, dst] of process.argv.slice(2).map(x => x.split(':'))) {
  const code = esbuild.transformSync(fs.readFileSync(src, 'utf8'), {loader: 'jsx', jsxFactory: '__h', format: 'cjs'}).code;
  const m = {exports: {}}; new Function('module', 'exports', '__h', code)(m, m.exports, h);
  let svg = m.exports.default();
  const vb = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
  svg = svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" font-family="Helvetica, Arial, sans-serif" ')
           .replace(/(<svg[^>]*>)/, `$1<rect width="${vb[1]}" height="${vb[2]}" fill="#ffffff"/>`);
  fs.writeFileSync(dst, '<?xml version="1.0" encoding="UTF-8"?>\n' + svg + '\n'); console.log(dst, svg.length);
}
