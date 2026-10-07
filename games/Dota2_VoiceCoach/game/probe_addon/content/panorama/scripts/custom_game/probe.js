// Пробник канала аркады: скрытая DOTAHTMLPanel опрашивает сервер тренера, ответ приходит
// в заголовке страницы («номер|JSON»), клиент пересылает его серверу кастомки игровым событием.
// Механизм — как в опубликованной кастомке Windy10v10AI (README их api, сентябрь 2026);
// код написан заново.
(function () {
  'use strict';
  var SERVER = 'http://127.0.0.1:8787';
  var ROOM = 'probe';
  var TEAM = 'radiant';
  var POLL_SECONDS = 1.0;
  var TIMEOUT_SECONDS = 10;
  var lastSeq = 0, rid = 0, ok = 0, fail = 0, inflight = false;

  function setStatus(text) {
    var label = $('#ProbeStatus');
    if (label) label.text = text;
  }

  function report(key, good, detail) {
    GameEvents.SendCustomGameEventToServer('vc_probe_report', { key: key, ok: good ? 1 : 0, detail: String(detail) });
  }

  function request() {
    inflight = true;
    rid += 1;
    var myRid = String(rid) + '_' + Math.floor(Math.random() * 1000000000);
    var url = SERVER + '/api/' + ROOM + '/commands?team=' + TEAM + '&after=' + lastSeq + '&fmt=title&rid=' + myRid;
    var t0 = Date.now();
    var done = false;
    var panel = $.CreatePanel('DOTAHTMLPanel', $.GetContextPanel(), 'VCProbe_' + rid);
    panel.style.width = '1px';
    panel.style.height = '1px';
    panel.style.opacity = '0.01';

    function finish() {
      if (done) return;
      done = true;
      inflight = false;
      if (panel && panel.IsValid()) panel.DeleteAsync(0);
    }

    $.RegisterEventHandler('HTMLTitle', panel, function (_source, title) {
      if (done || typeof title !== 'string') return;
      var sep = title.indexOf('|');
      if (sep < 0 || title.substr(0, sep) !== myRid) return;
      var data = title.substr(sep + 1);
      var ms = Date.now() - t0;
      finish();
      ok += 1;
      try {
        var parsed = JSON.parse(data);
        if (parsed.commands && parsed.commands.length) {
          lastSeq = parsed.commands[parsed.commands.length - 1].seq;
        }
      } catch (e) {
        report('json_parse', false, e);
      }
      setStatus('Пробник, веб-панель: ответов ' + ok + ', таймаутов ' + fail + ', последний за ' + ms + ' мс');
      GameEvents.SendCustomGameEventToServer('vc_probe_title', { rid: myRid, data: data, ms: ms });
    });

    panel.SetURL(url);

    $.Schedule(TIMEOUT_SECONDS, function () {
      if (done) return;
      finish();
      fail += 1;
      setStatus('Пробник, веб-панель: ответов ' + ok + ', таймаутов ' + fail + ' (сервер тренера запущен?)');
      if (fail === 1 || fail % 10 === 0) report('html_panel_timeout', false, 'таймаутов ' + fail + ', длина адреса ' + url.length);
    });
  }

  function poll() {
    if (!inflight) request();
    $.Schedule(POLL_SECONDS, poll);
  }

  // Скрипт грузится раньше, чем игроку назначен слот: первые события уходят с PlayerID = -1.
  // Шлём «ui_loaded», пока сервер не подтвердит (как api_html_proxy.js в Windy10v10AI).
  var acked = false, readyTries = 0;
  function sendReady() {
    if (acked || readyTries >= 60) return;
    readyTries += 1;
    report('ui_loaded', true, 'Panorama-скрипт пробника работает, попытка ' + readyTries);
    $.Schedule(1.0, sendReady);
  }
  GameEvents.Subscribe('vc_probe_ack', function () { acked = true; });

  $.Msg('[ПРОБНИК-UI] интерфейс пробника загружен');
  sendReady();
  poll();
})();
