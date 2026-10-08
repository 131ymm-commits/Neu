"""Страница пульта второго тренера (coach/web/console.html, решение Д13) в настоящем Chromium.

Сервер тренера и пульт — настоящие (порты 0), игра подменена запросами /tick. Речь браузера подменена записью.
Проверяется: страница по ссылке с ключом показывает свою команду, рисует карту, отдаёт приказ, который игра
получает в ответе на /tick, зачитывает голосовой чат только своей команды; на экране телефона нет прокрутки вбок;
политика безопасности страницы (CSP) ничего не блокирует. Нужен Playwright с Chromium; без него тест пропускается."""
import http.server
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from voicecoach import agents as A
from voicecoach import console as C
from voicecoach.server import serve, voice_event

from tests.test_console import payload
from tests.test_voice_page import CHROMIUM, STUB

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                  # pragma: no cover
    sync_playwright = None

SHOTS = os.environ.get("VC_SHOTS")                   # папка для снимков экрана (по желанию)


@unittest.skipUnless(sync_playwright and os.path.exists(CHROMIUM), "нужен Playwright и Chromium")
class ConsolePage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.srv = serve("127.0.0.1", 0, lambda name: A.AgentHub(
            {"radiant": A.RulesBackend(), "dire": A.RulesBackend()}, sync=True))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.key = C.load_keys(("dire",), path=Path(self.tmp.name) / "keys.json")["dire"]
        self.con = C.serve_console(self.srv.hub, "127.0.0.1", 0, "local", {"dire": self.key})
        threading.Thread(target=self.con.serve_forever, daemon=True).start()
        self.port, self.cport = self.srv.server_address[1], self.con.server_address[1]
        self.room = self.srv.hub.room("local")

    def tearDown(self):
        for s in (self.con, self.srv):
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def tick(self, p):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/local/tick", method="POST",
                                     data=json.dumps(p).encode("utf-8"))
        return json.loads(urllib.request.urlopen(req, timeout=5).read())

    def test_console_in_browser(self):
        first = self.tick(payload())
        problems, csp = [], []
        url = f"http://127.0.0.1:{self.cport}/c/{self.key}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            # 1) политика безопасности страницы: с ней страница работает и ничего не блокируется
            #    (ожидания Playwright, которые вычисляют строки, CSP запрещает, — здесь только селекторы)
            strict = browser.new_page()
            strict.on("console", lambda m: csp.append(m.text))
            strict.on("pageerror", lambda e: csp.append(str(e)))
            strict.goto(url)
            strict.wait_for_selector("#heroes:has-text('Луна')")
            strict.fill("#text", "все фарм")
            strict.press("#text", "Enter")
            strict.wait_for_selector("#answer:has-text('Принято')")
            strict.close()
            # 2) работа страницы (здесь CSP обходим: ожидания Playwright вычисляют строки)
            ctx = browser.new_context(viewport={"width": 1200, "height": 900}, bypass_csp=True)
            page = ctx.new_page()
            page.add_init_script(STUB)
            page.on("console", lambda m: m.type == "error" and problems.append(m.text))
            page.on("pageerror", lambda e: problems.append(str(e)))
            page.goto(url)
            page.wait_for_function("document.getElementById('heroes').innerText.includes('Луна')")
            self.assertIn("Тьма", page.title())
            self.assertEqual(page.inner_text("#score"), "Свет 3 : 5 Тьма")
            self.assertEqual(page.inner_text("#link"), "игра на связи")
            heroes = page.inner_text("#heroes")
            self.assertIn("Лина", heroes)
            self.assertIn("мёртв, 12 с", heroes)
            enemies = page.inner_text("#enemies")
            self.assertIn("Снайпер", enemies)
            self.assertIn("Вайпер — 40 с назад, мид", enemies)
            self.assertNotIn("7777", page.content())                          # золото Света сюда не попадает
            # карта: красный кружок своего героя и вышки нарисованы
            red = page.evaluate("""() => {
                const c = document.getElementById('map'), g = c.getContext('2d');
                const d = g.getImageData(0, 0, c.width, c.height).data;
                let n = 0;
                for (let i = 0; i < d.length; i += 4) if (d[i] > 200 && d[i+1] < 110 && d[i+2] < 100) n++;
                return n; }""")
            self.assertGreater(red, 50)
            if SHOTS:
                page.screenshot(path=os.path.join(SHOTS, "console_desktop.png"), full_page=True)
            # приказ: поле → сервер → игра (в ответе на её /tick)
            page.fill("#text", "все назад")
            page.press("#text", "Enter")
            page.wait_for_function("document.getElementById('answer').innerText.includes('Принято')")
            r = self.tick(payload(cmd_ack=0, cmd_run=first["run"]))
            self.assertEqual([c["text"] for c in r["commands"]], ["все фарм", "все назад"])
            page.click("button[data-cmd='все сбор мид']")                     # кнопка — заготовка, не приказ
            self.assertEqual(page.input_value("#text"), "все сбор мид")
            self.assertEqual(len(self.room.remote), 2)
            page.evaluate("document.getElementById('answer').textContent = ''")
            page.press("#text", "Enter")
            page.wait_for_function("document.getElementById('answer').innerText.includes('Принято')")
            self.assertEqual(len(self.room.remote), 3)
            page.fill("#text", "1 летать")
            page.press("#text", "Enter")
            page.wait_for_function("document.getElementById('answer').innerText.includes('Не понял')")
            # голосовой чат: своя команда звучит, чужая — нет
            page.click("#sound")
            page.wait_for_function("window.__spoken.length >= 1")
            self.room.add_events("radiant", [voice_event({"from": 1, "hero": "sniper", "text": "секрет Света", "to": []})])
            self.room.add_events("dire", [voice_event({"from": 2, "hero": "lina", "text": "иду на мид", "to": [1]})])
            self.room.add_events("dire", [{"pos": 0, "kind": "order", "text": "→ 12345: все назад"}])
            self.room.add_events("dire", [voice_event({"from": 3, "hero": "bristleback",
                                                       "text": '<img src=x onerror="window.__xss=1">', "to": []})])
            page.wait_for_function("window.__spoken.some(s => s.text.includes('иду на мид'))", timeout=15000)
            page.wait_for_function("document.getElementById('feed').innerText.includes('12345')")
            page.wait_for_function("document.getElementById('feed').innerText.includes('<img')")
            self.assertIsNone(page.evaluate("window.__xss"))                    # разметка не исполнилась
            # сервер перезапущен: номера событий снова с 1 — страница не молчит
            with self.room.lock:
                self.room.run, self.room.seq = "новый запуск", 0
                self.room.events = {"radiant": [], "dire": []}
            self.room.add_events("dire", [voice_event({"from": 5, "hero": "jakiro", "text": "после перезапуска",
                                                       "to": []})])
            page.wait_for_function("document.getElementById('feed').innerText.includes('после перезапуска')",
                                   timeout=30000)
            # метки врагов на карте различимы
            labs = page.evaluate("labels(['Лион', 'Лина', 'Луна', 'Лион'])")
            self.assertEqual(len(set(labs.values())), 3)
            self.assertNotEqual(labs["Лион"], labs["Лина"])
            spoken = [s["text"] for s in page.evaluate("window.__spoken")]
            self.assertIn("Лина: иду на мид", spoken)
            self.assertFalse(any("секрет" in s for s in spoken))
            self.assertNotIn("секрет", page.inner_text("#feed"))
            # телефон: всё в ширину экрана, без прокрутки вбок
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(300)
            wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            if SHOTS:
                page.screenshot(path=os.path.join(SHOTS, "console_phone.png"), full_page=True)
            order_y = page.evaluate("document.getElementById('text').getBoundingClientRect().top")
            feed_y = page.evaluate("document.getElementById('feed').getBoundingClientRect().top")
            map_y = page.evaluate("document.getElementById('map').getBoundingClientRect().top")
            self.assertLess(order_y, feed_y)
            self.assertLess(feed_y, map_y)                                     # ответы — сразу под приказом
            self.assertEqual(page.evaluate("getComputedStyle(document.getElementById('text')).fontSize"), "16px")
            seen_problems = list(problems)                                      # дальше 404 — нарочно
            page.route("**/api/view", lambda route: route.fulfill(status=404, body="{}"))
            page.wait_for_function("document.getElementById('link').innerText.includes('устарела')")
            browser.close()
        self.assertLessEqual(wide, 0)
        self.assertEqual(seen_problems, [])
        self.assertEqual(csp, [])                                             # ни ошибок, ни отказов CSP


    def test_foreign_site_in_host_browser(self):
        """Страница чужого сайта (например, по ссылке соперника), открытая в браузере хоста, не читает приказы и чат
        Света с порта игры и не отдаёт приказ — ни чтением ответа (CORS), ни «простым» POST (сервер: 403).
        Чужой сайт здесь — http://localhost:<порт> (другой сайт для браузера, но тоже этот ПК: настоящий внешний
        адрес Chromium сам не пускает к 127.0.0.1 без разрешения человека — запрос висит, проверить сервер нельзя)."""
        self.room.say_short("radiant", "все назад", "page")
        before = len(self.room.commands_after("radiant", 0))
        target = f"http://127.0.0.1:{self.port}"
        evil = f"""<!doctype html><script>
          window.__result = {{}};
          fetch('{target}/api/local/events?team=radiant&after=0')
            .then(r => r.text()).then(t => window.__result.read = t).catch(e => window.__result.read = 'blocked');
          fetch('{target}/api/local/say', {{method: 'POST', mode: 'no-cors', headers: {{'Content-Type': 'text/plain'}},
                body: JSON.stringify({{team: 'radiant', text: '12345 назад', mode: 'short'}})}})
            .then(() => window.__result.post = 'sent').catch(() => window.__result.post = 'blocked');
        </script>""".encode("utf-8")

        class Evil(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(evil)))
                self.end_headers()
                self.wfile.write(evil)

        bad = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Evil)
        threading.Thread(target=bad.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=CHROMIUM)
                page = browser.new_page()
                page.goto(f"http://localhost:{bad.server_address[1]}/")
                page.wait_for_function("window.__result.read && window.__result.post", timeout=15000)
                result = page.evaluate("window.__result")
                browser.close()
        finally:
            bad.shutdown()
            bad.server_close()
        self.assertEqual(result["read"], "blocked")                            # ответ чужому сайту не отдан
        self.assertEqual(len(self.room.commands_after("radiant", 0)), before)   # приказ не прошёл (403)

if __name__ == "__main__":
    unittest.main()
