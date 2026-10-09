// Ящик игры вдвоём (решение Д14): найти свежую ссылку на пульт хоста. Пара к coach/voicecoach/rendezvous.py —
// тот же секрет, имя темы, шифр и подпись (HMAC-SHA256 через WebCrypto). Встраивается в файл соперника
// ДЛЯ_ДРУГА.html и подключается пультом (console.js) — чтобы после перезапуска игры хостом найти новый адрес.
(function (root) {
  'use strict';
  const te = new TextEncoder(), td = new TextDecoder();
  const MAX_AGE = 12 * 3600;

  function b64d(s) {
    s = String(s).replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    const bin = atob(s), out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function b64e(bytes) {
    let s = '';
    for (const x of bytes) s += String.fromCharCode(x);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function cat(a, b) {
    const o = new Uint8Array(a.length + b.length);
    o.set(a, 0);
    o.set(b, a.length);
    return o;
  }
  async function hmac(key, data) {
    const k = await crypto.subtle.importKey('raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    return new Uint8Array(await crypto.subtle.sign('HMAC', k, data));
  }
  function same(a, b) {
    if (a.length !== b.length) return false;
    let d = 0;
    for (let i = 0; i < a.length; i++) d |= a[i] ^ b[i];
    return d === 0;
  }
  async function topic(secret) {
    return 'dcoach-' + b64e(await hmac(b64d(secret), te.encode('topic'))).slice(0, 32);
  }
  async function unseal(secret, text) {
    try {
      const p = String(text).trim().split('.');
      if (p.length !== 4 || p[0] !== 'vc1') return null;
      const k = b64d(secret);
      const kEnc = await hmac(k, te.encode('enc')), kMac = await hmac(k, te.encode('mac'));
      const nonce = b64d(p[1]), ct = b64d(p[2]), tag = b64d(p[3]);
      if (!same(tag, await hmac(kMac, cat(nonce, ct)))) return null;       // подделка или чужое — мимо
      const pt = new Uint8Array(ct.length);
      for (let i = 0, blk = 0; i < ct.length; blk++) {
        const n = new Uint8Array([(blk >>> 24) & 255, (blk >>> 16) & 255, (blk >>> 8) & 255, blk & 255]);
        const ks = await hmac(kEnc, cat(nonce, n));
        for (let j = 0; j < ks.length && i < ct.length; j++, i++) pt[i] = ct[i] ^ ks[j];
      }
      const obj = JSON.parse(td.decode(pt));
      return obj && typeof obj.t === 'number' ? obj : null;
    } catch (e) {
      return null;
    }
  }
  // самое свежее подлинное сообщение не старше 12 ч: { url } или { closed }, или null; нет связи — исключение
  async function find(base, secret) {
    const name = await topic(secret);
    const r = await fetch(String(base).replace(/\/$/, '') + '/' + name + '/json?poll=1&since=12h', { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const now = Date.now() / 1000;
    let best = null;
    for (const line of (await r.text()).split('\n')) {
      let m;
      try { m = JSON.parse(line); } catch (e) { continue; }
      if (!m || m.event !== 'message' || typeof m.message !== 'string') continue;
      const obj = await unseal(secret, m.message);
      if (obj && now - obj.t <= MAX_AGE && obj.t <= now + 300 && (!best || obj.t > best.t)) best = obj;
    }
    return best;
  }
  // параметры ящика из адреса пульта: «#rv=<секрет>&b=<адрес ящика>» (часть после # на сервер не уходит)
  function fromHash(hash) {
    const m = /(?:^#|&)rv=([^&]+)&b=([^&]+)/.exec(hash || '');
    return m ? { secret: decodeURIComponent(m[1]), base: decodeURIComponent(m[2]) } : null;
  }
  root.Rendezvous = { topic: topic, unseal: unseal, find: find, fromHash: fromHash };
})(window);
