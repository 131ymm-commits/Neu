"""Страница голосового чата команды (coach/web/voice.html, решение Д12) в настоящем Chromium.

Речь браузера подменена записью: проверяется, что страница берёт реплики своей команды с сервера тренера,
не зачитывает старые при открытии, говорит каждой позицией своим голосом и называет героя по-русски.
Нужен Playwright с Chromium (в окружении Claude — /opt/pw-browsers/chromium); без него тест пропускается."""
import json
import os
import threading
import time
import unittest
import urllib.request

from voicecoach import agents as A
from voicecoach.server import serve, voice_event

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                  # pragma: no cover
    sync_playwright = None

CHROMIUM = "/opt/pw-browsers/chromium"

STUB = """
window.__spoken = [];
const voices = [{name: 'ru-1', lang: 'ru-RU'}, {name: 'ru-2', lang: 'ru-RU'}, {name: 'en-1', lang: 'en-US'}];
function Utterance(text) { this.text = text; }
Object.defineProperty(window, 'SpeechSynthesisUtterance', {value: Utterance, configurable: true, writable: true});
Object.defineProperty(window, 'speechSynthesis', {configurable: true, value: {
  getVoices: () => voices,
  onvoiceschanged: null,
  speak: (u) => {
    window.__spoken.push({text: u.text, pitch: u.pitch, rate: u.rate, lang: u.lang, voice: u.voice ? u.voice.name : null});
    setTimeout(() => u.onend && u.onend(), 5);
  },
}});
"""


def obs(clock, pos, coach=()):
    return {"team": "radiant", "pos": pos, "hero": "sniper", "clock": clock, "alive": True, "hp": [500, 500],
            "abilities": [], "items": [{"name": "item_tango"}], "enemy_team": ["luna"], "coach": list(coach)}


@unittest.skipUnless(sync_playwright and os.path.exists(CHROMIUM), "нужен Playwright и Chromium")
class VoicePage(unittest.TestCase):
    def setUp(self):
        self.srv = serve("127.0.0.1", 0, lambda name: A.AgentHub(
            {"radiant": A.RulesBackend(), "dire": A.RulesBackend()}, sync=True))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]
        self.room = self.srv.hub.room("local")

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def tick(self, payload):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/local/tick", method="POST",
                                     data=json.dumps(payload).encode("utf-8"))
        return json.loads(urllib.request.urlopen(req, timeout=5).read())

    def test_speaks_own_team_with_voices(self):
        self.room.add_events("radiant", [voice_event({"from": 3, "hero": "axe", "text": "старая реплика", "to": []})])
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            page.add_init_script(STUB)
            page.goto(f"http://127.0.0.1:{self.port}/voice.html?team=radiant")
            page.click("#sound")                                   # звук включает человек (правило браузеров)
            page.wait_for_function("window.__spoken.length >= 1")
            # настоящий путь: приказ тренера → агент (правила) → реплика в чат → событие → страница
            self.tick({"heroes": [obs(-80, 1, [{"seq": 1, "ago": 0, "text": "1 пуш бот"}])]})
            self.room.add_events("radiant", [voice_event({"from": 2, "hero": "viper", "text": "иду к тебе", "to": [1]})])
            self.room.add_events("dire", [voice_event({"from": 1, "hero": "luna", "text": "чужая команда", "to": []})])
            page.wait_for_function("window.__spoken.length >= 3", timeout=15000)
            time.sleep(0.5)
            spoken = page.evaluate("window.__spoken")
            log = page.inner_text("#log")
            browser.close()
        texts = [s["text"] for s in spoken]
        self.assertEqual(texts[0], "Голосовой чат включён")
        self.assertEqual(texts[1:], ["Снайпер: Понял: 1 пуш бот", "Вайпер: иду к тебе"])
        self.assertEqual([(s["voice"], s["pitch"]) for s in spoken[1:]], [("ru-1", 1.0), ("ru-2", 0.8)])
        self.assertTrue(all(s["lang"] == "ru-RU" for s in spoken))
        self.assertNotIn("старая реплика", log)
        self.assertNotIn("чужая команда", log)
        self.assertIn("→ 1", log)

    def test_coach_page_speaks_voice_events_too(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script(STUB)
            page.goto(f"http://127.0.0.1:{self.port}/")
            page.wait_for_function("window.VoiceChat !== undefined")
            time.sleep(0.5)
            self.room.add_events("radiant", [voice_event({"from": 4, "hero": "lion", "text": "смок у меня", "to": []})])
            page.wait_for_function("window.__spoken.length >= 1", timeout=15000)
            spoken = page.evaluate("window.__spoken")
            browser.close()
        self.assertEqual(errors, [])
        self.assertEqual((spoken[-1]["text"], spoken[-1]["pitch"]), ("Лион: смок у меня", 0.95))


if __name__ == "__main__":
    unittest.main()
