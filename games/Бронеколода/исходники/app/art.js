// Бронеколода — рисунки: силуэты техники, значки приказов, эмблемы штабов. Всё — векторные строки SVG.
const Art = (() => {
  'use strict';
  const f = n => Math.round(n * 10) / 10;
  const G = 68; // линия земли
  const pts = a => a.map(p => f(p[0]) + ',' + f(p[1])).join(' ');
  const poly = (cls, a) => `<polygon class="${cls}" points="${pts(a)}"/>`;
  const rect = (cls, x, y, w, h, rx) => `<rect class="${cls}" x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}"${rx ? ` rx="${f(rx)}"` : ''}/>`;
  const circ = (cls, cx, cy, r) => `<circle class="${cls}" cx="${f(cx)}" cy="${f(cy)}" r="${f(r)}"/>`;
  const line = (cls, x1, y1, x2, y2, w) => `<line class="${cls}" x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke-width="${w || 2}"/>`;
  const shadow = (cx, w) => `<ellipse class="shd" cx="${f(cx)}" cy="${G + 1.5}" rx="${f(w / 2)}" ry="2.6"/>`;

  function tracks(x0, x1, h, wheels) {
    let s = rect('trk', x0, G - h, x1 - x0, h, h / 2);
    const r = h * 0.3, cy = G - h / 2;
    for (let i = 0; i < wheels; i++) {
      const cx = x0 + h / 2 + (x1 - x0 - h) * (wheels === 1 ? 0.5 : i / (wheels - 1));
      s += circ('whl', cx, cy, r);
    }
    return s;
  }
  function turret(tx, base, o) {
    const tw = o.tw, tH = o.th, ty = base - tH, cal = o.cal || 3;
    let s = poly('tur', [[tx - tw / 2, base + 0.5], [tx - tw / 2 + (o.tbs ?? 3), ty], [tx + tw / 2 - (o.tfs ?? 6), ty], [tx + tw / 2, ty + tH * 0.5], [tx + tw / 2, base + 0.5]]);
    const gy = ty + tH * 0.45;
    s += rect('gun', tx + tw / 2 - 1, gy - cal / 2, o.gun, cal);
    if (o.brake) s += rect('gun', tx + tw / 2 + o.gun - 4, gy - cal * 0.95, 4.5, cal * 1.9, 0.6);
    s += rect('tur', tx + tw / 2 - 3, gy - cal * 1.1, 5, cal * 2.2, 1);
    if (o.cup !== false) s += rect('tur', tx - tw / 2 + tw * 0.22, ty - 2.6, Math.max(4, tw * 0.22), 3.2, 1.2);
    return s;
  }
  // Гусеничная машина, смотрит вправо
  function tank(o) {
    const L = o.len, x0 = 60 - L / 2 + (o.dx || 0), x1 = x0 + L, th = o.trackH || 12;
    const bot = G - th + 2, hh = o.h, top = G - th - hh + 2;
    const fs = o.frontSlope ?? 10, bs = o.backSlope ?? 4;
    let s = shadow(60 + (o.dx || 0), L + 6) + tracks(x0, x1, th, o.wheels || 5);
    s += poly('hull', [[x0 - 1, bot], [x0 + bs - 1, top], [x1 - fs, top], [x1 + 2, top + hh * 0.72], [x1 + 1, bot]]);
    if (o.skirt) s += rect('hull', x0 + 3, G - th - 0.5, L - 8, th * 0.42);
    if (o.tw) s += turret(60 + (o.tdx || 0) + (o.dx || 0), top, o);
    if (o.extra) s += o.extra(x0, x1, top, bot);
    return s;
  }

  const K = {
    light: () => tank({ len: 54, h: 9, trackH: 11, wheels: 5, tw: 20, th: 8, gun: 18, cal: 2.4, tdx: 2 }),
    light2: () => tank({ len: 60, h: 9, trackH: 12, wheels: 4, tw: 22, th: 9, gun: 20, cal: 2.4, frontSlope: 15, backSlope: 7, tdx: 3 }),
    tankette: () => tank({ len: 40, h: 7, trackH: 9, wheels: 4, frontSlope: 5, extra: (x0, x1, top) =>
      rect('tur', 60, top - 6, 10, 6.5, 1) + rect('gun', 69, top - 4, 9, 1.6) }),
    medium: () => tank({ len: 70, h: 11, trackH: 13, wheels: 5, tw: 28, th: 10, gun: 30, cal: 3, frontSlope: 16, backSlope: 8, tdx: 4 }),
    medium2: () => tank({ len: 72, h: 12, trackH: 13, wheels: 8, tw: 26, th: 11, gun: 32, cal: 3, frontSlope: 6, skirt: true, tfs: 3 }),
    sherman: () => tank({ len: 68, h: 14, trackH: 13, wheels: 6, tw: 26, th: 12, gun: 26, cal: 3, frontSlope: 14, tfs: 9, tbs: 5 }),
    matilda: () => tank({ len: 68, h: 13, trackH: 16, wheels: 6, tw: 22, th: 10, gun: 12, cal: 2, skirt: true, frontSlope: 4 }),
    panther: () => tank({ len: 76, h: 12, trackH: 14, wheels: 8, tw: 26, th: 11, gun: 42, cal: 3, brake: true, frontSlope: 18, backSlope: 10, dx: -6 }),
    kv: () => tank({ len: 76, h: 15, trackH: 14, wheels: 6, tw: 32, th: 14, gun: 26, cal: 3.4, frontSlope: 8, tfs: 4, tbs: 2, dx: -2 }),
    tiger: () => tank({ len: 80, h: 14, trackH: 15, wheels: 8, tw: 34, th: 13, gun: 40, cal: 3.8, brake: true, frontSlope: 4, tfs: 2, tbs: 2, dx: -8 }),
    kingtiger: () => tank({ len: 84, h: 15, trackH: 15, wheels: 9, tw: 36, th: 13, gun: 46, cal: 3.8, brake: true, frontSlope: 20, tfs: 11, dx: -10 }),
    is2: () => tank({ len: 80, h: 14, trackH: 14, wheels: 6, tw: 30, th: 13, gun: 40, cal: 4.2, brake: true, frontSlope: 16, tfs: 10, tbs: 6, dx: -8 }),
    ace: () => tank({ len: 72, h: 11, trackH: 13, wheels: 5, tw: 32, th: 12, gun: 36, cal: 3.2, frontSlope: 16, backSlope: 8, tdx: 2, dx: -4 }),
    maus: () => tank({ len: 98, h: 20, trackH: 17, wheels: 10, tw: 40, th: 15, gun: 38, cal: 5, frontSlope: 12, tfs: 12, tbs: 6, skirt: true, dx: -8 }),
    t35: () => tank({ len: 98, h: 11, trackH: 14, wheels: 9, tw: 24, th: 11, gun: 20, cal: 3, frontSlope: 8, dx: -4, extra: (x0, x1, top) =>
      rect('tur', x0 + 8, top - 6, 13, 6.5, 2) + rect('gun', x0 + 20, top - 4, 9, 1.8) +
      rect('tur', x1 - 26, top - 6, 13, 6.5, 2) + rect('gun', x1 - 14, top - 4, 11, 1.8) }),
    td: () => tank({ len: 74, h: 11, trackH: 13, wheels: 5, frontSlope: 4, extra: (x0, x1, top) =>
      poly('tur', [[x0 + 8, top + 1], [x0 + 12, top - 10], [x1 - 26, top - 10], [x1 - 4, top + 1]]) +
      rect('gun', x1 - 18, top - 7, 34, 3, 0) + rect('tur', x1 - 20, top - 9, 6, 7, 1.5) }),
    su152: () => tank({ len: 78, h: 12, trackH: 14, wheels: 6, frontSlope: 4, dx: -4, extra: (x0, x1, top) =>
      poly('tur', [[x0 + 2, top + 1], [x0 + 6, top - 13], [x1 - 22, top - 13], [x1 - 4, top + 1]]) +
      rect('gun', x1 - 16, top - 9.5, 26, 5) + rect('gun', x1 + 7, top - 11, 5, 8, 1) + rect('tur', x1 - 20, top - 12, 8, 10, 2) }),
    arv: () => tank({ len: 72, h: 11, trackH: 13, wheels: 5, frontSlope: 10, extra: (x0, x1, top) =>
      line('gun', x0 + 18, top, x0 + 40, top - 26, 2.6) + line('gun', x0 + 30, top, x0 + 40, top - 26, 2.2) +
      line('gun', x0 + 40, top - 26, x1 - 2, top - 14, 2.4) + line('gun', x1 - 2, top - 14, x1 - 2, top + 2, 1) +
      rect('tur', x1 - 5, top + 2, 6, 3, 1) + rect('tur', x0 + 4, top - 7, 14, 7, 1.5) }),

    car: () => {
      let s = shadow(60, 64);
      s += poly('hull', [[34, 58], [38, 44], [50, 38], [72, 38], [84, 46], [88, 58]]);
      s += rect('trk', 32, 55, 58, 4, 1.5);
      s += poly('tur', [[55, 39], [57, 31], [68, 31], [70, 39]]) + rect('gun', 68, 33, 14, 1.6);
      s += circ('trk', 44, 61, 7.5) + circ('whl', 44, 61, 3.4) + circ('trk', 78, 61, 7.5) + circ('whl', 78, 61, 3.4);
      return s;
    },
    halftrack: () => {
      let s = shadow(60, 84);
      s += rect('trk', 20, 56, 48, 12, 6);
      for (let i = 0; i < 5; i++) s += circ('whl', 26 + i * 9, 62, 3.4);
      s += poly('hull', [[18, 56], [20, 38], [72, 38], [86, 46], [96, 50], [96, 58], [18, 58]]);
      s += circ('trk', 88, 61, 7) + circ('whl', 88, 61, 3);
      s += rect('gun', 44, 33, 3, 6) + rect('gun', 45, 33, 16, 1.6);
      return s;
    },
    truck: () => {
      let s = shadow(60, 84);
      s += rect('hull', 18, 32, 52, 24, 2);
      s += poly('tur', [[72, 56], [72, 36], [86, 36], [94, 46], [96, 56]]);
      s += rect('trk', 16, 54, 82, 5, 1.5);
      s += circ('trk', 32, 61, 7.5) + circ('whl', 32, 61, 3.2) + circ('trk', 50, 61, 7.5) + circ('whl', 50, 61, 3.2) + circ('trk', 86, 61, 7.5) + circ('whl', 86, 61, 3.2);
      s += rect('shd', 30, 39, 20, 9, 1);
      return s;
    },
    rocket: () => {
      let s = K.truck().replace(/<rect class="hull"[^>]*>/, '').replace(/<rect class="shd"[^/]*\/>/, '');
      s += `<g transform="rotate(-24 62 48)">${rect('gun', 14, 40, 54, 3)}${rect('gun', 14, 45, 54, 3)}${rect('gun', 14, 50, 54, 3)}</g>`;
      s += rect('hull', 26, 50, 42, 6, 1) + rect('hull', 50, 40, 6, 14);
      return s;
    },
    howitzer: () => {
      let s = shadow(56, 84);
      s += line('gun', 22, 66, 56, 52, 3) + line('gun', 28, 68, 56, 54, 2.4);
      s += `<g transform="rotate(-28 58 46)">${rect('gun', 46, 43, 56, 4.6)}${rect('gun', 42, 41, 18, 9, 2)}</g>`;
      s += poly('tur', [[60, 34], [72, 31], [74, 56], [62, 58]]);
      s += circ('trk', 60, 59, 9) + circ('whl', 60, 59, 4);
      return s;
    },
    atgun: () => {
      let s = shadow(56, 86);
      s += line('gun', 18, 67, 52, 56, 2.6) + line('gun', 26, 68, 52, 58, 2);
      s += rect('gun', 52, 47, 54, 3) + rect('gun', 102, 46, 4.5, 5, 0.8);
      s += poly('tur', [[50, 36], [64, 34], [66, 60], [52, 61]]);
      s += circ('trk', 56, 60, 8) + circ('whl', 56, 60, 3.4);
      s += `<path class="net" d="M8 68 C 12 52, 26 48, 34 56 C 40 44, 58 40, 64 50 C 70 42, 86 44, 88 56 C 96 52, 106 58, 110 68 Z"/>`;
      return s;
    },
    bunker: () => {
      let s = `<path class="trk" d="M6 68 C 10 58, 22 54, 30 54 L 92 54 C 100 54, 110 58, 114 68 Z"/>`;
      s += `<path class="hull" d="M24 60 C 26 34, 94 34, 96 60 Z"/>`;
      s += rect('shd', 46, 44, 30, 4.5, 2) + rect('gun', 70, 45, 22, 2.6);
      s += `<path class="tur" d="M30 40 C 44 30, 76 30, 90 40" fill="none" stroke-width="2"/>`;
      return s;
    },
    hedgehog: () => {
      let s = shadow(60, 60);
      s += line('gun', 36, 68, 80, 26, 6) + line('gun', 84, 68, 40, 26, 6) + line('hull', 60, 70, 60, 22, 6);
      s += line('trk', 30, 54, 90, 54, 2);
      return s;
    },
    moto: () => {
      let s = shadow(60, 64);
      s += circ('trk', 40, 60, 9) + circ('whl', 40, 60, 4) + circ('trk', 82, 60, 9) + circ('whl', 82, 60, 4);
      s += poly('hull', [[40, 60], [50, 46], [74, 46], [82, 60], [70, 54], [52, 54]]);
      s += line('gun', 76, 46, 82, 36, 2.4);
      s += poly('tur', [[56, 46], [60, 28], [68, 28], [70, 40], [78, 38], [78, 42], [66, 46]]);
      s += circ('tur', 63, 23, 5) + rect('tur', 57, 18.5, 12, 3, 1.5);
      return s;
    },
    inf: () => {
      const man = (x, sc) => {
        const h = 32 * sc, y = G - h;
        return poly('hull', [[x - 5 * sc, G], [x - 4 * sc, y + 12 * sc], [x - 6 * sc, y + 22 * sc], [x - 3.5 * sc, y + 8 * sc], [x + 4 * sc, y + 8 * sc], [x + 6 * sc, y + 20 * sc], [x + 4 * sc, y + 12 * sc], [x + 5 * sc, G], [x + 1, G], [x, y + 22 * sc], [x - 1, G]]) +
          circ('tur', x, y + 4 * sc, 3.6 * sc) + `<path class="tur" d="M${f(x - 6 * sc)} ${f(y + 3.2 * sc)} Q ${f(x)} ${f(y - 5 * sc)} ${f(x + 6 * sc)} ${f(y + 3.2 * sc)} Z"/>` +
          line('gun', x + 2 * sc, y + 20 * sc, x + 14 * sc, y + 4 * sc, 1.6 * sc);
      };
      return shadow(60, 76) + man(40, 0.95) + man(62, 1.1) + man(84, 0.9);
    },
    atr: () => {
      let s = shadow(60, 90);
      s += poly('hull', [[18, 66], [22, 58], [58, 56], [62, 62], [58, 67]]);
      s += circ('tur', 64, 56, 4.4) + `<path class="tur" d="M58 55 Q 64 46 71 55 Z"/>`;
      s += rect('gun', 52, 56, 56, 2.4) + rect('gun', 104, 55, 5, 4.4, 0.8) + line('gun', 92, 58, 96, 68, 1.4) + line('gun', 92, 58, 88, 68, 1.4);
      s += poly('hull', [[14, 68], [18, 62], [40, 62], [42, 68]]) + circ('tur', 44, 61, 3.6);
      return s;
    },
    spotter: () => {
      let s = shadow(60, 70);
      s += poly('hull', [[48, 68], [49, 44], [44, 58], [46, 40], [60, 40], [62, 54], [58, 46], [58, 68], [54, 68], [53, 54], [52, 68]]);
      s += circ('tur', 53, 35, 4.6) + `<path class="tur" d="M46 34 Q 53 24 60 34 Z"/>` + rect('gun', 56, 33, 9, 4, 1.2);
      s += rect('hull', 70, 50, 16, 18, 1.5) + line('gun', 82, 50, 92, 14, 1.2) + circ('tur', 92, 14, 1.6);
      s += line('gun', 60, 44, 70, 56, 1.4);
      return s;
    },

    // приказы
    shell: () => `<g transform="rotate(-62 60 42)">${rect('gun', 28, 36, 40, 13, 1)}${`<path class="tur" d="M68 36 L 84 36 Q 98 42.5 84 49 L 68 49 Z"/>`}${rect('trk', 24, 34, 5, 17, 1)}${rect('hull', 58, 36, 4, 13)}</g>` +
      `<path class="fx" d="M18 66 L 34 52 M10 58 L 30 46 M28 72 L 40 58" stroke-width="2"/>`,
    track: () => {
      let s = '';
      for (let i = 0; i < 6; i++) s += `<g transform="rotate(${-8 + i * 7} 60 120)">${rect('trk', 14 + i * 13.5, 40 + Math.abs(i - 2.5) * 2, 11, 9, 1.2)}${rect('whl', 18 + i * 13.5, 43 + Math.abs(i - 2.5) * 2, 3, 3)}</g>`;
      return s + `<path class="fx" d="M60 18 L 64 34 L 74 26 L 70 40 L 84 40 L 70 48" stroke-width="2.2"/>` + shadow(60, 90);
    },
    wedge: () => {
      const ch = (y, sc, cls) => `<path class="${cls}" d="M${30} ${y} L ${60} ${y - 22 * sc} L ${90} ${y} L ${80} ${y} L ${60} ${y - 12 * sc} L ${40} ${y} Z"/>`;
      return ch(70, 1, 'trk') + ch(54, 1, 'hull') + ch(38, 1, 'tur');
    },
    blast: () => {
      let p = [];
      for (let i = 0; i < 18; i++) { const a = i / 18 * Math.PI * 2, r = i % 2 ? 14 : 32; p.push([60 + Math.cos(a) * r * 1.3, 44 + Math.sin(a) * r]); }
      return poly('fxfill', p) + circ('tur', 60, 44, 9) + `<path class="trk" d="M0 70 L 30 62 L 46 68 L 74 60 L 90 66 L 120 60 L 120 80 L 0 80 Z"/>`;
    },
    barrage: () => {
      let s = '';
      [[22, 14], [52, 6], [82, 18], [38, 30], [70, 34]].forEach(([x, y]) => {
        s += `<g transform="rotate(20 ${x} ${y})">${rect('gun', x - 3, y, 6, 14, 1)}<path class="tur" d="M${x - 3} ${y + 14} L ${x + 3} ${y + 14} L ${x} ${y + 20} Z"/></g>` + line('fx', x - 8, y - 14, x - 3, y - 2, 1.2);
      });
      [[30, 66], [62, 64], [94, 67]].forEach(([x, y]) => { s += `<path class="fxfill" d="M${x - 12} ${y} L ${x - 6} ${y - 10} L ${x - 2} ${y - 4} L ${x + 2} ${y - 14} L ${x + 6} ${y - 5} L ${x + 12} ${y} Z"/>`; });
      return s + rect('trk', 0, 67, 120, 13);
    },
    plane: () => `<g transform="rotate(-10 60 40)">${poly('hull', [[16, 42], [30, 38], [92, 38], [104, 41], [92, 44], [30, 46]])}${poly('tur', [[50, 40], [44, 12], [54, 12], [66, 40]])}${poly('tur', [[50, 42], [44, 70], [54, 70], [66, 42]])}${poly('tur', [[22, 40], [16, 30], [22, 30], [30, 40]])}${poly('tur', [[22, 42], [16, 52], [22, 52], [30, 42]])}${rect('gun', 102, 33, 2, 16)}</g>` +
      `<path class="fx" d="M6 70 L 30 64 M14 76 L 46 70" stroke-width="1.4"/>`,
    impact: () => {
      let s = `<path class="fxfill" d="M60 8 L 66 34 L 88 22 L 72 44 L 100 50 L 70 54 L 76 66 L 60 58 L 44 66 L 50 54 L 20 50 L 48 44 L 32 22 L 54 34 Z"/>`;
      return s + `<path class="trk" d="M0 66 C 30 56, 44 74, 60 62 C 76 74, 92 56, 120 66 L 120 80 L 0 80 Z"/>` + `<g transform="rotate(8 60 6)">${rect('gun', 57, -8, 6, 12, 1)}</g>`;
    },
    trench: () => {
      let s = `<path class="trk" d="M0 52 L 120 52 L 120 80 L 0 80 Z"/>`;
      s += `<path class="hull" d="M0 60 L 18 60 L 26 70 L 44 70 L 52 60 L 70 60 L 78 70 L 96 70 L 104 60 L 120 60 L 120 64 L 106 64 L 98 74 L 76 74 L 68 64 L 54 64 L 46 74 L 24 74 L 16 64 L 0 64 Z"/>`;
      for (let i = 0; i < 9; i++) s += rect('tur', 4 + i * 13, 46 - (i % 2) * 2, 11, 7, 2);
      return s;
    },
    canister: () => {
      let s = shadow(60, 46);
      s += `<path class="hull" d="M42 24 L 72 24 L 80 32 L 80 68 L 40 68 L 40 26 Z"/>`;
      s += rect('tur', 46, 18, 10, 8, 1) + rect('gun', 62, 16, 12, 5, 1.5);
      s += `<path class="trk" d="M44 34 L 76 62 M76 34 L 44 62" stroke-width="3" fill="none"/>`;
      return s;
    }
  };

  const cache = {};
  // vb — кадрирование: на фишках поля техника крупнее
  function svg(kind, vb) {
    const key = kind + '|' + (vb || '');
    if (!cache[key]) cache[key] = `<svg class="sil" viewBox="${vb || '0 0 120 80'}" preserveAspectRatio="xMidYMax meet" aria-hidden="true">${(K[kind] || K.medium)()}</svg>`;
    return cache[key];
  }

  // Эмблемы штабов
  function emblem(d) {
    let inner = '';
    if (d === 'A') inner = `<g transform="translate(0 6)">${K.medium().replace(/class="shd"[^>]*>/, 'class="shd" rx="0" ry="0"/>')}</g>`;
    if (d === 'B') inner = `<g transform="rotate(-30 60 44)">${rect('gun', 16, 40, 88, 6)}${rect('gun', 98, 38, 8, 10, 1)}</g><g transform="rotate(30 60 44)">${rect('gun', 16, 40, 88, 6)}${rect('gun', 98, 38, 8, 10, 1)}</g>` + circ('trk', 60, 58, 12) + circ('whl', 60, 58, 5);
    if (d === 'C') inner = `<path class="hull" d="M60 8 L 92 18 L 90 46 C 88 62, 74 72, 60 78 C 46 72, 32 62, 30 46 L 28 18 Z"/><path class="trk" d="M60 18 L 82 25 L 80 46 C 78 58, 70 64, 60 69 Z"/>` + line('gun', 44, 30, 76, 62, 3.4) + line('gun', 76, 30, 44, 62, 3.4);
    return `<svg class="sil" viewBox="0 0 120 80" aria-hidden="true">${inner}</svg>`;
  }

  // Мелкие значки
  const ICONS = {
    atk: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 21h6v-9l-3-8-3 8z" /><rect x="8" y="19" width="8" height="3" rx="1"/></svg>',
    hp: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l8 3v7c0 5-4 8.5-8 10-4-1.5-8-5-8-10V5z"/></svg>',
    fuel: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h9l4 4v13H5V5z"/><rect x="7" y="1.5" width="4" height="3" rx="0.8"/></svg>',
    gear: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8a4 4 0 100 8 4 4 0 000-8zm8.5 4l2-1.6-2-3.4-2.4.8-1.8-1L16 4h-4l-.4 2.6-1.8 1-2.4-.8-2 3.4 2 1.6v2l-2 1.6 2 3.4 2.4-.8 1.8 1L12 20h4l.4-2.6 1.8-1 2.4.8 2-3.4-2-1.6z" fill-rule="evenodd"/></svg>',
    cross: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19" stroke-width="4" stroke="currentColor"/></svg>',
    deck: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="3" width="13" height="17" rx="2"/><rect x="3" y="5" width="13" height="17" rx="2" opacity=".6"/></svg>'
  };

  return { svg, emblem, ICONS, kinds: Object.keys(K) };
})();
if (typeof window !== 'undefined') window.Art = Art;
