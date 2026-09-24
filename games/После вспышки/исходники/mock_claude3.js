// Имитация платформы для проверки общего мира: db (документы в localStorage + BroadcastChannel), user, downloads.
(function () {
  const uid = new URLSearchParams(location.search).get('uid') || 'u_alice';
  const P = 'mockdb3:', L = 'mocklease3:';
  const bc = new BroadcastChannel('mockdb3');
  const listeners = new Set();
  const deepFreeze = o => { if (o && typeof o === 'object') { Object.freeze(o); Object.values(o).forEach(deepFreeze); } return o; };
  const read = path => { const v = localStorage.getItem(P + path); return v == null ? null : JSON.parse(v); };
  const segs = p => p.split('/');
  function notify(path) { listeners.forEach(f => f(path)); }
  bc.onmessage = e => notify(e.data);
  function write(path, obj) { if (obj == null) localStorage.removeItem(P + path); else localStorage.setItem(P + path, JSON.stringify(obj)); setTimeout(() => { notify(path); bc.postMessage(path); }, 5); }
  function snap(path) { const d = read(path); return { id: segs(path).pop(), exists: d != null, data: () => d == null ? undefined : deepFreeze(d), metadata: { fromCache: false, hasPendingWrites: false } }; }
  function merge(t, s) { for (const k in s) { const v = s[k]; if (v && typeof v === 'object' && !Array.isArray(v) && t[k] && typeof t[k] === 'object' && !Array.isArray(t[k])) merge(t[k], v); else t[k] = v; } return t; }
  const delay = () => new Promise(r => setTimeout(r, 2 + Math.random() * 8));
  function docRef(path) {
    if (segs(path).length % 2) throw new TypeError('bad doc path ' + path);
    return {
      id: segs(path).pop(), path,
      async get() { await delay(); return snap(path); },
      async set(d) { await delay(); if (!d || typeof d !== 'object' || Array.isArray(d)) throw { code: 'invalid_argument', message: 'body' }; if (JSON.stringify(d).length > 256 * 1024) throw { code: 'invalid_argument', message: 'too big ' + path + ' ' + JSON.stringify(d).length }; write(path, JSON.parse(JSON.stringify(d))); },
      async update(d) { await delay(); const cur = read(path); if (cur == null) throw { code: 'invalid_argument', message: 'missing ' + path }; const n = merge(cur, JSON.parse(JSON.stringify(d))); if (JSON.stringify(n).length > 256 * 1024) throw { code: 'invalid_argument', message: 'too big' }; write(path, n); },
      async delete() { await delay(); write(path, null); },
      async acquire(o) { await delay(); const now = Date.now(); const l = JSON.parse(localStorage.getItem(L + path) || 'null'); if (l && l.exp > now && l.holder !== o.holder) return { acquired: false, expiresAt: new Date(l.exp).toISOString() }; const exp = now + (o.ttlMs || 30000); localStorage.setItem(L + path, JSON.stringify({ holder: o.holder, exp })); return { acquired: true, holder: o.holder, expiresAt: new Date(exp).toISOString(), version: 1 }; },
      onSnapshot(next, err) { let last; const f = p => { if (p !== path) return; next(snap(path)); }; listeners.add(f); setTimeout(() => next(snap(path)), 3); return () => listeners.delete(f); },
      collection(sub) { return collRef(path + '/' + sub); }
    };
  }
  function collRef(path, q) {
    q = q || { order: null, dir: 'asc', lim: null, w: [] };
    q.w = q.w || [];
    const n = segs(path).length;
    function docs() {
      const out = [];
      for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (!k.startsWith(P + path + '/')) continue; const rest = k.slice(P.length); if (segs(rest).length !== n + 1) continue; out.push(snap(rest)); }
      out.sort((a, b) => a.id < b.id ? -1 : 1);
      const flt = q.w.length ? out.filter(x => q.w.every(([f, op, v]) => { const d = x.data() || {}; return op === '==' ? d[f] === v : op === '!=' ? d[f] !== v : op === '>' ? d[f] > v : op === '<' ? d[f] < v : true; })) : out.slice();
      out.length = 0; flt.forEach(x => out.push(x));
      if (q.order) out.sort((a, b) => { const x = a.data()[q.order], y = b.data()[q.order]; return (x < y ? -1 : x > y ? 1 : 0) * (q.dir === 'desc' ? -1 : 1); });
      return q.lim ? out.slice(0, q.lim) : out;
    }
    const api = {
      path,
      doc(id) { return docRef(path + '/' + (id || Math.random().toString(36).slice(2))); },
      async add(d) { const r = api.doc(); await r.set(d); return r; },
      orderBy(f, dir) { return collRef(path, Object.assign({}, q, { order: f, dir: dir || 'asc' })); },
      limit(k) { return collRef(path, Object.assign({}, q, { lim: k })); },
      where(f, op, v) { return collRef(path, Object.assign({}, q, { w: q.w.concat([[f, op, v]]) })); },
      async get() { await delay(); const d = docs(); return { docs: d, size: d.length, empty: !d.length, docChanges: () => d.map((x, i) => ({ type: 'added', doc: x, oldIndex: -1, newIndex: i })), metadata: {} }; },
      onSnapshot(next, err) {
        let prev = new Map();
        const emit = () => { const d = docs(); const cur = new Map(d.map(x => [x.id, x])); const ch = [];
          d.forEach((x, i) => { const p = prev.get(x.id); if (!p) ch.push({ type: 'added', doc: x, newIndex: i, oldIndex: -1 }); else if (JSON.stringify(p.data()) !== JSON.stringify(x.data())) ch.push({ type: 'modified', doc: x, newIndex: i, oldIndex: -1 }); });
          prev.forEach((x, id) => { if (!cur.has(id)) ch.push({ type: 'removed', doc: x, newIndex: -1, oldIndex: 0 }); });
          prev = cur; if (ch.length || !emit.once) { emit.once = true; next({ docs: d, size: d.length, empty: !d.length, docChanges: () => ch, metadata: {} }); } };
        const f = p => { if (p.startsWith(path + '/') && segs(p).length === n + 1) emit(); };
        listeners.add(f); setTimeout(emit, 3); return () => listeners.delete(f);
      }
    };
    return api;
  }
  const db = Object.freeze({ doc: docRef, collection: collRef });
  const NAMES = { u_alice: 'Алиса', u_bob: 'Борис' };
  const user = Object.freeze({
    isOwner: async () => uid === 'u_alice', canEdit: async () => uid === 'u_alice', can: async n => n === 'data.write' ? true : false,
    id: async () => uid, me: async () => ({ id: uid, name: NAMES[uid] || '', avatarUrl: '', color: uid === 'u_alice' ? '#c2410c' : '#0e7490', email: null, isOwner: uid === 'u_alice', canEdit: uid === 'u_alice' }),
    profiles: async ids => { const o = {}; [].concat(ids).forEach(i => o[i] = { id: i, name: NAMES[i] || '', avatarUrl: '', color: i === 'u_alice' ? '#c2410c' : '#0e7490', email: null, isMe: i === uid }); return o; },
    name: async () => NAMES[uid] || '', search: async () => []
  });
  const downloads = Object.freeze({ save: async r => { window.__saved = r; return { status: 'saved' }; } });
  // ИИ: разбирает данные из запроса и отвечает решениями новой модели
  function aiAnswer(input) {
    let ctx = null; try { ctx = JSON.parse(input.split('\n\n').find(x => x.trim().startsWith('{"month_index"'))); } catch (e) { }
    const ai = ((ctx && ctx.ai_countries) || []).map(c => c.iso);
    const pol = {};
    ai.slice(0, 6).forEach(iso => { pol[iso] = { prC: 0.45, prW: 0.35, prG: 0.1, prL: 0.1, ration: 0.75 }; });
    if (ai.includes('CHN')) pol.CHN = { prC: 0.2, prW: 0.2, prG: 0.5, prL: 0.1, ration: 0.7, exportT: 0.6, aidF: { PAK: 20 }, aidR: { BGD: 2 } };
    return { policies: pol, news: [{ title: 'Китай возобновил выпуск трансформаторов на трёх заводах', text: 'Первые единицы уйдут в Пакистан и Бангладеш.', iso: ['CHN', 'PAK', 'BGD'] }, { title: 'Радиолюбители связали Африку', text: 'КВ-сеть накрыла двадцать стран.', iso: ['NGA', 'KEN'] }] };
  }
  const sample = async (input, opts) => ({ text: JSON.stringify(aiAnswer(input)), truncated: false, modelTierApplied: 'default' });
  sample.json = async (input, opts) => { window.__aiCalls = (window.__aiCalls || 0) + 1; window.__aiPrompt = input; await new Promise(r => setTimeout(r, 400)); if (opts && opts.signal && opts.signal.aborted) throw { code: 'cancelled', message: 'x' }; return aiAnswer(input); };
  sample.limits = async () => ({ maxPromptBytes: 65536 });
  const withSample = new URLSearchParams(location.search).get('ai') !== '0';
  // комната: присутствие всех открытых вкладок через BroadcastChannel
  const roomOn = new URLSearchParams(location.search).get('room') !== '0';
  const RB = new BroadcastChannel('mockroom3'), PEER = 'peer_' + Math.random().toString(36).slice(2, 10);
  let myPres = {}, peersMap = new Map(), peerHandlers = new Set(), evHandlers = new Set(), lastSnap = [];
  const mkPeer = (peer, pres, isMe) => Object.freeze({ peer, by: null, isMe, sameTab: peer === PEER, kind: 'viewer', presence: Object.freeze(Object.assign({}, pres)), updatedAt: Date.now() });
  function snapPeers() { const arr = [mkPeer(PEER, myPres, true)]; peersMap.forEach((v, k) => { arr.push(mkPeer(k, v.pres, v.uid === uid)); }); lastSnap = Object.freeze(arr); return lastSnap; }
  function deliver(joined, left, updated) { const peers = snapPeers(); peerHandlers.forEach(f => { try { f({ peers, joined: Object.freeze(joined || []), left: Object.freeze(left || []), updated: Object.freeze(updated || []) }); } catch (e) { console.error(e); } }); }
  RB.onmessage = e => {
    const m = e.data; if (!m || m.peer === PEER) return;
    if (m.t === 'pres') { const had = peersMap.has(m.peer); peersMap.set(m.peer, { pres: m.pres, at: Date.now(), uid: m.uid }); if (!had) RB.postMessage({ t: 'pres', peer: PEER, pres: myPres, uid }); deliver(had ? [] : [mkPeer(m.peer, m.pres, false)], [], had ? [mkPeer(m.peer, m.pres, false)] : []); }
    else if (m.t === 'bye') { const p = peersMap.get(m.peer); peersMap.delete(m.peer); deliver([], p ? [mkPeer(m.peer, p.pres, false)] : [], []); }
    else if (m.t === 'ev') { evHandlers.forEach(([topic, f]) => { if (topic === m.topic) f({ topic: m.topic, data: m.data, peer: m.peer, by: null, isMe: false, sameTab: false, kind: 'viewer' }); }); }
  };
  addEventListener('pagehide', () => RB.postMessage({ t: 'bye', peer: PEER }));
  const room = Object.freeze({
    async presence(patch) { for (const k in patch) { if (patch[k] == null) delete myPres[k]; else myPres[k] = patch[k]; } RB.postMessage({ t: 'pres', peer: PEER, pres: myPres, uid }); deliver([], [], [mkPeer(PEER, myPres, true)]); },
    peers() { return lastSnap.length ? lastSnap : snapPeers(); },
    onPeers(f) { peerHandlers.add(f); setTimeout(() => { RB.postMessage({ t: 'pres', peer: PEER, pres: myPres, uid }); deliver(snapPeers().slice(), [], []); }, 5); return () => peerHandlers.delete(f); },
    async emit(topic, data) { RB.postMessage({ t: 'ev', topic, data, peer: PEER }); evHandlers.forEach(([tp, f]) => { if (tp === topic) f({ topic, data, peer: PEER, by: null, isMe: true, sameTab: true, kind: 'viewer' }); }); },
    on(topic, f) { const e = [topic, f]; evHandlers.add(e); return () => evHandlers.delete(e); },
    connected() { return true; }, onConnection(f) { setTimeout(() => f(true), 1); return () => { }; }
  });
  window.claude = Object.freeze({ use: async name => ({ db, user, downloads, sample: withSample ? sample : null, room: roomOn ? room : null })[name] || null });
})();
