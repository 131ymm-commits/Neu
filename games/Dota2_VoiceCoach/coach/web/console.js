// Пульт второго тренера (решение Д13): страница console.html, данные — API пульта под ключом из адреса.
// Отдельным файлом: политика безопасности страницы запрещает встроенные скрипты (защита от внедрения).
'use strict';
const $ = id => document.getElementById(id);
const COLORS = { radiant: '#59c36a', dire: '#e05a4f' };
let view = null, soundOn = false, lastEvent = -1, lastRun = null, viewFails = 0, wakeLock = null;
let hostNote = '';                // что известно из ящика игры, пока сервер хоста молчит (Д14)

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function mmss(c) {
  if (c == null) return '';
  const n = Math.round(Math.abs(c));
  return (c < 0 ? '-' : '') + Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');
}
function other(team) { return team === 'radiant' ? 'dire' : 'radiant'; }

// метки врагов на карте: две буквы, разные у всех пятерых (Лион — «Ли», Лина — «Лн»)
function labels(names) {
  const out = {}, used = new Set();
  for (const n of names) {
    const w = (n || '?').replace(/[^A-Za-zА-Яа-яЁё]/g, '') || '?';
    let lab = w.slice(0, 2);
    for (let i = 2; used.has(lab) && i < w.length; i++) lab = w[0] + w[i];
    for (let d = 2; used.has(lab); d++) lab = w[0] + d;
    used.add(lab);
    out[n] = lab[0].toUpperCase() + lab.slice(1).toLowerCase();
  }
  return out;
}

// --- карта ---
function lanePoints(v, lane) {
  const t = (team) => v.towers.filter(x => x.team === team && x.lane === lane);
  const r = t('radiant').sort((a, b) => b.tier - a.tier), d = t('dire').sort((a, b) => a.tier - b.tier);
  const avg = (list, k) => list.reduce((s, x) => s + x[k], 0) / list.length;
  const pts = [];
  if (v.fountains.radiant) pts.push(v.fountains.radiant);
  r.forEach(x => pts.push([x.x, x.y]));
  if (r.length && d.length && lane === 'top') pts.push([avg(r, 'x'), avg(d, 'y')]);   // угол топа
  if (r.length && d.length && lane === 'bot') pts.push([avg(d, 'x'), avg(r, 'y')]);   // угол бота
  d.forEach(x => pts.push([x.x, x.y]));
  if (v.fountains.dire) pts.push(v.fountains.dire);
  return pts;
}
function outer(v, team, lane) {
  return v.towers.filter(x => x.team === team && x.lane === lane).sort((a, b) => a.tier - b.tier)[0];
}
function drawMap() {
  const cv = $('map'), dpr = window.devicePixelRatio || 1, size = Math.max(200, cv.clientWidth);
  if (cv.width !== Math.round(size * dpr)) { cv.width = cv.height = Math.round(size * dpr); }
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = '#18241a';
  g.fillRect(0, 0, size, size);
  if (!view) return;
  let b = view.bounds;
  if (!b || b.length !== 4) {
    const xs = view.towers.map(t => t.x), ys = view.towers.map(t => t.y);
    b = xs.length ? [Math.min(...xs) - 1500, Math.min(...ys) - 1500, Math.max(...xs) + 1500, Math.max(...ys) + 1500]
                  : [-8300, -8300, 8300, 8300];
  }
  const span = Math.max(b[2] - b[0], b[3] - b[1]) || 1;
  const P = (x, y) => [(x - b[0]) / span * size, size - (y - b[1]) / span * size];
  const line = (pts, color, width) => {
    if (pts.length < 2) return;
    g.strokeStyle = color; g.lineWidth = width; g.lineJoin = 'round'; g.lineCap = 'round';
    g.beginPath();
    pts.forEach((p, i) => { const q = P(p[0], p[1]); if (i) g.lineTo(q[0], q[1]); else g.moveTo(q[0], q[1]); });
    g.stroke();
  };
  // река: через середины между внешними вышками линий
  const mids = ['top', 'mid', 'bot'].map(l => {
    const r = outer(view, 'radiant', l), d = outer(view, 'dire', l);
    return r && d ? [(r.x + d.x) / 2, (r.y + d.y) / 2] : null;
  }).filter(Boolean);
  line(mids, 'rgba(70,130,190,0.45)', size / 28);
  ['top', 'mid', 'bot'].forEach(l => line(lanePoints(view, l), 'rgba(205,190,150,0.35)', size / 70));
  for (const team of ['radiant', 'dire']) {
    const f = view.fountains[team];
    if (!f) continue;
    const q = P(f[0], f[1]);
    g.fillStyle = COLORS[team] + '55';
    g.beginPath(); g.arc(q[0], q[1], size / 18, 0, Math.PI * 2); g.fill();
  }
  const s = size / 60;
  for (const t of view.towers) {
    const q = P(t.x, t.y);
    g.strokeStyle = COLORS[t.team]; g.lineWidth = 2;
    if (t.alive) { g.fillStyle = COLORS[t.team]; g.fillRect(q[0] - s, q[1] - s, 2 * s, 2 * s); }
    else g.strokeRect(q[0] - s, q[1] - s, 2 * s, 2 * s);
  }
  const placed = [];
  const dot = (xy, color, label, k) => {
    if (!xy) return;
    const r = size / 40 * k;
    let q = P(xy[0], xy[1]);
    // кружки в одной точке (у фонтана, в драке) раздвигаем по кругу, чтобы были видны все
    const near = placed.filter(p => Math.hypot(p[0] - q[0], p[1] - q[1]) < r * 1.4).length;
    if (near) { const a = near * 2.1; q = [q[0] + Math.cos(a) * r * 1.5, q[1] + Math.sin(a) * r * 1.5]; }
    placed.push(q);
    g.fillStyle = color; g.strokeStyle = '#0b0c0e'; g.lineWidth = 2;
    g.beginPath(); g.arc(q[0], q[1], r, 0, Math.PI * 2); g.fill(); g.stroke();
    g.fillStyle = '#0b0c0e'; g.font = `bold ${Math.round(r * 1.1)}px system-ui, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText(label, q[0], q[1] + 1);
  };
  const lab = labels([...view.enemies, ...view.missing].map(e => e.hero_ru || e.hero));
  for (const h of view.heroes) if (h.alive) dot(h.xy, COLORS[view.team], String(h.pos), 1);
  for (const e of view.enemies) dot(e.xy, COLORS[other(view.team)], lab[e.hero_ru || e.hero], 0.85);  // поверх своих
}

// --- герои и враги ---
function renderView() {
  const v = view;
  document.title = `Пульт тренера — ${v.team_ru}`;
  $('title').textContent = `Пульт тренера: ${v.team_ru}`;
  $('title').style.color = COLORS[v.team];
  $('clock').textContent = v.game.clock != null ? mmss(v.game.clock) : '';
  $('score').textContent = v.score ? `Свет ${v.score.radiant} : ${v.score.dire} Тьма` : '';
  $('backend').textContent = v.backend ? `героев ведут: ${v.backend}` : '';
  const link = $('link');
  link.className = 'link ' + (v.game.linked ? 'on' : 'off');
  link.textContent = v.game.linked ? 'игра на связи'
    : (v.game.ago_s != null ? `игра молчит ${Math.round(v.game.ago_s)} с` : 'игра ещё не началась');
  const rows = v.heroes.map(h => {
    const hp = h.hp ? Math.round(100 * h.hp[0] / Math.max(1, h.hp[1])) : 0;
    const st = h.agent || '';
    const trouble = /^(ошибка|лимит|пауза|сбой)/.test(st) ? ` · <span class="trouble">агент: ${esc(st.slice(0, 60))}</span>` : '';
    const think = st === 'думает' ? ' · думает…' : '';
    const life = h.alive ? `${hp}% здоровья` : `мёртв${h.respawn != null ? ', ' + esc(h.respawn) + ' с' : ''}`;
    const k = h.stats || {};
    return `<div class="hero${h.alive ? '' : ' dead'}"><span class="num" style="background:${COLORS[v.team]}">${esc(h.pos)}</span>` +
      `<div><b>${esc(h.hero_ru)}</b> · ур. ${esc(h.lvl)} · ${life} · ${esc(h.gold)} золота` +
      (k.k != null ? ` · ${esc(k.k)}/${esc(k.d)}/${esc(k.a)}` : '') + `</div>` +
      `<div class="muted">${esc(h.doing || 'ждёт')}${think}${trouble}` +
      (h.alive ? `<div class="bar"><i style="width:${hp}%"></i></div>` : '') + `</div></div>`;
  });
  $('heroes').innerHTML = rows.join('') || '<span class="muted">жду данных игры…</span>';
  const seen = v.enemies.map(e => `${esc(e.hero_ru)}${e.hp ? ' ' + Math.round(100 * e.hp[0] / Math.max(1, e.hp[1])) + '%' : ''}` +
    (e.where ? ` (${esc(e.where)})` : ''));
  const lost = v.missing.map(m => `${esc(m.hero_ru)}${m.dead ? ' — мёртв' : (m.ago != null ? ` — ${esc(m.ago)} с назад${m.seen ? ', ' + esc(m.seen) : ''}` : ' — не видели')}`);
  $('enemies').innerHTML = `<div><b>Враги видны:</b> ${seen.join(', ') || 'никого'}</div>` +
    `<div class="muted"><b>Пропали:</b> ${lost.join('; ') || 'никто'}</div>` +
    (v.events.length ? `<div class="muted"><b>События:</b> ${v.events.slice(-4).map(esc).join(' · ')}</div>` : '');
  drawMap();
}

async function refreshView() {
  try {
    const r = await fetch('api/view', { cache: 'no-store' });
    if (r.status === 404) {
      $('link').className = 'link off';
      $('link').textContent = 'ссылка устарела или неверна — попросите у хоста новую';
      return;
    }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    view = await r.json();
    viewFails = 0;
    hostNote = '';
    renderView();
  } catch (e) {
    viewFails += 1;
    if (viewFails >= 3) { $('link').className = 'link off'; $('link').textContent = hostNote || 'сервер тренера не отвечает'; }
    if (viewFails >= 3 && viewFails % 10 === 3) follow();   // через 3 с без связи и дальше раз в 10 с
  }
}

// игра вдвоём (Д14): пульт открыт из файла друга — в адресе после «#» секрет ящика игры (на сервер он не уходит).
// Хост перезапустил игру — у туннеля новый адрес: находим его в ящике и переходим туда сами.
const RV = window.Rendezvous ? Rendezvous.fromHash(location.hash) : null;
async function follow() {
  if (!RV) return;
  try {
    const msg = await Rendezvous.find(RV.base, RV.secret);
    const url = msg && Rendezvous.pultUrl(msg.url);
    if (url && url !== location.href.split('#')[0] && await Rendezvous.alive(url)) {   // мёртвый адрес не берём
      hostNote = 'друг перезапустил игру — перехожу на новый адрес…';
      $('link').textContent = hostNote;
      location.replace(url + location.hash);
    } else {
      hostNote = msg && msg.closed ? 'друг закрыл игру — жду, когда запустит снова' : '';
    }
  } catch (e) { /* ящик недоступен — попробуем позже */ }
}

// --- лента и голос ---
function feed(cls, html) {
  const box = $('feed'), div = document.createElement('div');
  if (box.firstElementChild && !box.firstElementChild.classList.contains('line')) box.innerHTML = '';
  div.className = 'line ' + cls;
  div.innerHTML = `<span class="muted">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span> ${html}`;
  box.appendChild(div);
  while (box.children.length > 80) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}
function showEvent(ev) {
  const who = ev.pos ? `<span class="who">${esc(ev.pos)} ${esc(ev.hero_ru || ev.hero || '')}</span>` : '<span class="who">игра</span>';
  const to = ev.to && ev.to.length ? ` <span class="to">→ ${esc(ev.to.join(','))}</span>` : '';
  if (ev.kind === 'voice') {
    feed('voice', `${who}${to}: ${esc(ev.text)}`);
    if (soundOn && window.VoiceChat) {
      const name = $('names').checked && (ev.hero_ru || ev.hero) ? `${ev.hero_ru || ev.hero}: ` : '';
      VoiceChat.say(ev.pos, name + ev.text);
    }
  } else if (ev.kind !== 'ptt') {
    feed(ev.kind === 'error' ? 'error' : 'game', `${who}${to}: ${esc(ev.text)}`);
  }
}
async function poll() {
  for (;;) {
    try {
      // при открытии старые события не показываем: сначала узнаём номер последнего
      const first = lastEvent < 0;
      const r = await fetch(`api/events?after=${Math.max(lastEvent, 0)}&wait=${first ? 0 : 20}`, { cache: 'no-store' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const res = await r.json();
      if (lastRun !== null && res.run !== lastRun) {   // сервер перезапущен: его номера событий снова с 1
        lastRun = res.run;
        lastEvent = 0;
        continue;
      }
      lastRun = res.run;
      for (const ev of res.events || []) {
        lastEvent = Math.max(lastEvent, ev.seq);
        if (!first) showEvent(ev);
      }
      if (first) lastEvent = Math.max(lastEvent, 0);
    } catch (e) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }
}

// --- приказы ---
async function send(text) {
  text = (text || '').trim();
  if (!text) return;
  const ans = $('answer');
  ans.innerHTML = '<span class="muted">отправляю…</span>';
  try {
    const r = await fetch('api/say', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                       body: JSON.stringify({ text }) });
    const res = await r.json();
    if (!r.ok) { ans.innerHTML = `<span class="bad">${esc(res.error || ('ошибка ' + r.status))}</span>`; return; }
    if (res.errors && res.errors.length) {
      let html = `<span class="bad">Не понял: ${esc(res.errors.join('; '))}</span>`;
      if (res.suggestion) html += ` · может, так: <b>${esc(res.suggestion)}</b><button type="button" id="usesug">взять</button>`;
      ans.innerHTML = html;
      const b = $('usesug');
      if (b) b.onclick = () => { $('text').value = res.suggestion; $('text').focus(); };
      return;
    }
    const human = (res.commands || []).map(c => c.human).filter(Boolean).join('; ');
    ans.innerHTML = `<span class="ok">Принято: ${esc(human || text)}</span>` +
      (res.game_linked ? '' : ' <span class="muted">— игра не на связи: приказ дойдёт, если она ответит в ближайшие 30 с</span>');
    feed('me', `<span class="who">вы</span>: ${esc(text)}`);
    $('text').value = '';
  } catch (e) {
    ans.innerHTML = '<span class="bad">сервер тренера не отвечает — приказ не ушёл</span>';
  }
}

$('order').addEventListener('submit', ev => { ev.preventDefault(); send($('text').value); });
$('chips').addEventListener('click', ev => {         // заготовка в поле: промах пальцем не отдаёт приказ
  const cmd = ev.target && ev.target.getAttribute('data-cmd');
  if (cmd) { $('text').value = cmd; $('text').focus(); }
});
$('helpbtn').addEventListener('click', () => $('help').classList.toggle('hidden'));
$('volume').addEventListener('input', () => { if (window.VoiceChat) VoiceChat.volume = Number($('volume').value); });
// экран телефона не гаснет, пока включён звук (иначе опрос и голос останавливаются); нужен https — туннель
async function keepAwake(on) {
  try {
    if (on && navigator.wakeLock && !wakeLock) {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } else if (!on && wakeLock) {
      await wakeLock.release();
      wakeLock = null;
    }
  } catch (e) { wakeLock = null; }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && soundOn) keepAwake(true); });
$('sound').addEventListener('click', () => {
  soundOn = !soundOn;
  $('sound').classList.toggle('on', soundOn);
  $('sound').textContent = soundOn ? 'Выключить звук' : 'Включить звук';
  if (soundOn && window.VoiceChat) VoiceChat.unlock();
  keepAwake(soundOn);
});
window.addEventListener('resize', drawMap);
refreshView();
setInterval(refreshView, 1000);
poll();
drawMap();
