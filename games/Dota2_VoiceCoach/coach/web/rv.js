// Ящик игры вдвоём (решение Д14): найти свежую ссылку на пульт хоста. Пара к coach/voicecoach/rendezvous.py —
// тот же секрет, имя темы, шифр и подпись (HMAC-SHA256 через WebCrypto). Встраивается в файл соперника
// ДЛЯ_ДРУГА.html и подключается пультом (console.js) — чтобы после перезапуска игры хостом найти новый адрес.
(function (root) {
  'use strict';
  const te = new TextEncoder(), td = new TextDecoder();
  const SINCE = '10m';            // окно свежести по часам ntfy (хост повторяет ссылку раз в 5 мин): часы ПК не важны

  // запрос с пределом ожидания: зависший ответ не держит проверку дольше ms
  async function get(url, ms) {
    const ctl = root.AbortController ? new AbortController() : null;
    const timer = ctl ? setTimeout(() => ctl.abort(), ms) : 0;
    try {
      return await fetch(url, { cache: 'no-store', signal: ctl ? ctl.signal : undefined });
    } finally {
      clearTimeout(timer);
    }
  }

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
      if (nonce.length !== 16) return null;
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
  // самое новое подлинное сообщение за последние 10 минут: { url, fv } или { closed }, или null; нет связи — исключение
  async function find(base, secret) {
    const name = await topic(secret);
    const r = await get(String(base).replace(/\/$/, '') + '/' + name + '/json?poll=1&since=' + SINCE, 15000);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    let best = null;
    for (const line of (await r.text()).split('\n')) {
      let m;
      try { m = JSON.parse(line); } catch (e) { continue; }
      if (!m || m.event !== 'message' || typeof m.message !== 'string') continue;
      const obj = await unseal(secret, m.message);
      if (obj && (!best || obj.t > best.t)) best = obj;
    }
    return best;
  }
  // жив ли пульт по ссылке: он отвечает на /api/ping (туннель, который хост закрыл, отвечает страницей ошибки)
  async function alive(url) {
    try {
      const r = await get(String(url).replace(/\/?$/, '/') + 'api/ping', 8000);
      return r.ok && (await r.json()).ok === true;
    } catch (e) {
      return false;
    }
  }
  // ссылка на пульт: https-туннель Cloudflare или адрес этого ПК / домашней сети (только им отдаём секрет после #)
  function pultUrl(url) {
    const m = /^(https?):\/\/([^\/\s#?]+)(\/c\/[^\s#?]+)$/.exec(String(url || '').trim());
    if (!m) return null;
    const host = m[2].toLowerCase().replace(/:\d+$/, '');
    const ok = (m[1] === 'https' && /^[a-z0-9-]+\.trycloudflare\.com$/.test(host)) ||
      /^(127\.0\.0\.1|localhost|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$/.test(host);
    return ok ? m[1] + '://' + m[2] + m[3].replace(/\/?$/, '/') : null;
  }
  // параметры ящика из адреса пульта: «#rv=<секрет>&b=<адрес ящика>» (часть после # на сервер не уходит)
  function fromHash(hash) {
    const m = /(?:^#|&)rv=([^&]+)&b=([^&]+)/.exec(hash || '');
    return m ? { secret: decodeURIComponent(m[1]), base: decodeURIComponent(m[2]) } : null;
  }
  root.Rendezvous = { topic: topic, unseal: unseal, find: find, alive: alive, pultUrl: pultUrl, fromHash: fromHash,
                      FRIEND_VERSION: 2 };
})(window);
