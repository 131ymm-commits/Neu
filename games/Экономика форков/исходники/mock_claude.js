// Имитация платформы для проверки общего мира: db (документы в localStorage + BroadcastChannel), user, downloads.
(function () {
  const uid = new URLSearchParams(location.search).get('uid') || 'u_alice';
  const P = 'mockdb:', L = 'mocklease:';
  const bc = new BroadcastChannel('mockdb');
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
    q = q || { order: null, dir: 'asc', lim: null };
    const n = segs(path).length;
    function docs() {
      const out = [];
      for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (!k.startsWith(P + path + '/')) continue; const rest = k.slice(P.length); if (segs(rest).length !== n + 1) continue; out.push(snap(rest)); }
      out.sort((a, b) => a.id < b.id ? -1 : 1);
      if (q.order) out.sort((a, b) => { const x = a.data()[q.order], y = b.data()[q.order]; return (x < y ? -1 : x > y ? 1 : 0) * (q.dir === 'desc' ? -1 : 1); });
      return q.lim ? out.slice(0, q.lim) : out;
    }
    const api = {
      path,
      doc(id) { return docRef(path + '/' + (id || Math.random().toString(36).slice(2))); },
      async add(d) { const r = api.doc(); await r.set(d); return r; },
      orderBy(f, dir) { return collRef(path, Object.assign({}, q, { order: f, dir: dir || 'asc' })); },
      limit(k) { return collRef(path, Object.assign({}, q, { lim: k })); },
      where() { return api; },
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
  window.claude = Object.freeze({ use: async name => ({ db, user, downloads })[name] || null });
})();
