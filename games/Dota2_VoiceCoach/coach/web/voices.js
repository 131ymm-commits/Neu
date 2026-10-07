// Голоса агентов в голосовом чате команды (решение Д12): синтетические голоса браузера (Web Speech API).
// У каждой позиции свой голос: один из русских голосов системы, своя высота и темп. Голоса реальных людей
// не клонируем (Д6). Очередь короткая: старые реплики выбрасываются, чтобы голос не отставал от игры.
(function (root) {
  'use strict';
  var PITCH = [1.0, 0.8, 1.2, 0.95, 1.35];      // позиции 1–5
  var RATE = [1.1, 1.0, 1.15, 1.05, 1.1];
  var MAX_QUEUE = 4;                            // больше — выбрасываем самые старые
  var MAX_AGE_MS = 12000;                       // реплика старше 12 с уже не нужна
  var STUCK_MS = 15000;                         // если браузер не прислал «конец речи» — не ждём вечно
  var queue = [], speaking = false, startedAt = 0, voices = [];

  function synth() { return root.speechSynthesis || null; }

  function loadVoices() {
    var s = synth();
    if (!s) return;
    var all = s.getVoices() || [];
    var ru = all.filter(function (v) { return /^ru/i.test(v.lang || ''); });
    voices = ru.length ? ru : [];
  }

  function voiceFor(pos) {
    var i = Math.max(0, (Number(pos) || 1) - 1) % 5;
    return { voice: voices.length ? voices[i % voices.length] : null, pitch: PITCH[i], rate: RATE[i] };
  }

  function next() {
    var s = synth();
    if (!s || !queue.length) return;
    if (speaking && Date.now() - startedAt < STUCK_MS) return;
    var now = Date.now();
    while (queue.length && now - queue[0].t > MAX_AGE_MS) queue.shift();
    if (!queue.length) return;
    var item = queue.shift();
    var u = new SpeechSynthesisUtterance(item.text);
    var v = voiceFor(item.pos);
    u.lang = 'ru-RU';
    if (v.voice) u.voice = v.voice;
    u.pitch = item.pos ? v.pitch : 1.0;
    u.rate = (item.pos ? v.rate : 1.0) * VC.speed;
    u.volume = VC.volume;
    speaking = true;
    startedAt = Date.now();
    u.onend = u.onerror = function () { speaking = false; next(); };
    s.speak(u);
  }

  var VC = {
    volume: 1.0,
    speed: 1.0,
    say: function (pos, text) {
      if (!text) return;
      queue.push({ pos: pos, text: String(text), t: Date.now() });
      while (queue.length > MAX_QUEUE) queue.shift();
      next();
    },
    voiceFor: voiceFor,
    reload: loadVoices,
    count: function () { return voices.length; },
    // браузер разрешает звук только после действия человека: первое «скажи» — по нажатию кнопки
    unlock: function () { VC.say(0, 'Голосовой чат включён'); },
  };

  if (synth()) {
    loadVoices();
    if ('onvoiceschanged' in synth()) synth().onvoiceschanged = loadVoices;
  }
  setInterval(next, 1000);                      // страховка, если «конец речи» потерялся
  root.VoiceChat = VC;
})(window);
