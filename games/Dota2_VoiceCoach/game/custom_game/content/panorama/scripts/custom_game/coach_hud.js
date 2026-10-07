// Интерфейс тренера: поле приказа (короткий формат), связь с агентами Claude, список героев и что каждый
// делает, журнал реплик агентов, шпаргалка. Камера — сверху и дальше обычного, панели героя скрыты: у тренера
// героя нет (Д10); героев ведут агенты Claude (Д11).
(function () {
  'use strict';
  var CAMERA_PITCH = 70;          // наклон камеры, градусы: «вид сверху» (проверить в игре)
  var acked = false, readyTries = 0;

  function setupCamera(distance) {
    GameUI.SetCameraDistance(distance || 1600);
    GameUI.SetCameraPitchMin(CAMERA_PITCH);
    GameUI.SetCameraPitchMax(CAMERA_PITCH);
  }

  function hideHeroUi() {
    var E = DotaDefaultUIElement_t;
    var hide = [E.DOTA_DEFAULT_UI_ACTION_PANEL, E.DOTA_DEFAULT_UI_INVENTORY_PANEL, E.DOTA_DEFAULT_UI_QUICK_STATS,
                E.DOTA_DEFAULT_UI_INVENTORY_QUICKBUY, E.DOTA_DEFAULT_UI_INVENTORY_COURIER,
                E.DOTA_DEFAULT_UI_SHOP_SUGGESTEDITEMS];
    for (var i = 0; i < hide.length; i++) GameUI.SetDefaultUIEnabled(hide[i], false);
  }

  function send() {
    var input = $('#CoachInput');
    var text = input.text;
    if (!text) return;
    GameEvents.SendCustomGameEventToServer('vc_command', { text: text });
    input.text = '';
  }

  function addLog(text, kind) {
    var log = $('#CoachLog');
    var line = $.CreatePanel('Label', log, '');
    line.text = text;
    line.AddClass('CoachLine');
    if (kind) line.AddClass('Reply_' + kind);
    while (log.GetChildCount() > 8) log.GetChild(0).DeleteAsync(0);
  }

  function onReply(ev) {
    var to = ev.to ? (' → ' + ev.to) : '';                 // голосовой чат: кому из союзников
    var who = ev.pos > 0 ? (ev.pos + ' ' + ev.hero + to + ': ') : '';
    addLog(who + ev.text, ev.kind);
  }

  // Голосовой чат команды вслух (Д12): скрытая веб-панель открывает страницу сервера тренера, та озвучивает
  // реплики своей команды голосами браузера. Работает ли речь внутри веб-панели Доты — не проверено;
  // надёжный путь — та же страница в браузере или на телефоне (game/custom_game/README.md).
  var VOICE_URL = 'http://127.0.0.1:8787/voice.html';
  var voiceStarted = false;
  function startVoice() {
    if (voiceStarted) return;
    voiceStarted = true;
    var team = Players.GetTeam(Players.GetLocalPlayer()) === DOTATeam_t.DOTA_TEAM_BADGUYS ? 'dire' : 'radiant';
    var panel = $.CreatePanel('DOTAHTMLPanel', $('#CoachRoot'), 'CoachVoice');
    panel.AddClass('CoachVoice');
    panel.SetURL(VOICE_URL + '?team=' + team + '&embed=1');
  }

  function onAgents(ev) {
    var mode = $('#CoachMode');
    mode.text = ev.mode || '';
    mode.SetHasClass('Offline', (ev.mode || '').indexOf('нет связи') === 0);
    var box = $('#CoachAgents');
    box.RemoveAndDeleteChildren();
    var agents = ev.agents || {};
    for (var k in agents) {                 // таблица Lua приходит объектом с ключами «1», «2», …
      var a = agents[k];
      var row = $.CreatePanel('Label', box, '');
      var think = a.agent === 'думает' ? ' · думает…' : '';
      row.text = a.pos + ' ' + a.hero + ' — ' + (a.alive ? (a.hp + '% · ') : 'мёртв · ') + a.status + think;
      row.AddClass('CoachAgent');
      row.SetHasClass('Dead', !a.alive);
      row.SetHasClass('Fallback', a.source === 'fallback');
    }
  }

  // ранние события клиента приходят на сервер с PlayerID = -1: шлём «готов», пока сервер не ответит
  function sendReady() {
    if (acked || readyTries >= 60) return;
    readyTries += 1;
    GameEvents.SendCustomGameEventToServer('vc_ready', {});
    $.Schedule(1.0, sendReady);
  }

  function focusInput() {
    $('#CoachInput').SetFocus();
  }

  GameEvents.Subscribe('vc_reply', onReply);
  GameEvents.Subscribe('vc_agents', onAgents);
  GameEvents.Subscribe('vc_ack', function (ev) { acked = true; setupCamera(ev.camera); startVoice(); });
  $('#CoachInput').SetPanelEvent('oninputsubmit', send);
  $('#CoachHelpButton').SetPanelEvent('onactivate', function () { $('#CoachSheet').ToggleClass('Hidden'); });
  Game.AddCommand('vc_coach_focus', focusInput, '', 0);
  Game.CreateCustomKeyBind('F2', 'vc_coach_focus');
  hideHeroUi();
  setupCamera(1600);
  addLog('Тренер: пишите приказы в поле внизу (F2 — к полю), «?» — шпаргалка; героев ведут агенты Claude', 'ack');
  sendReady();
})();
