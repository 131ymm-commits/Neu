"""Файл друга ДЛЯ_ДРУГА.html и пульт (решение Д14) в настоящем Chromium, открытые как у соперника: файл с диска.

Ящик — локальный двойник ntfy (tests/test_play.FakeNtfy), пульт — настоящий сервер пульта. Проверяется: файл ждёт,
пока хост не запустил игру; находит ссылку в ящике и открывает пульт; подделку в ящике не слушает; на мёртвую ссылку
не уходит; когда хост перезапустил игру (новый адрес туннеля), открытый пульт сам переходит на новый адрес; без
ящика — ввод ссылки руками; без скриптов — объясняет, что делать.
Нужен Playwright с Chromium; без него тест пропускается."""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from voicecoach import agents as A
from voicecoach import console as C
from voicecoach import play as P
from voicecoach import rendezvous as RV
from voicecoach.server import serve

from tests.test_play import FakeNtfy
from tests.test_voice_page import CHROMIUM

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                  # pragma: no cover
    sync_playwright = None


@unittest.skipUnless(sync_playwright and os.path.exists(CHROMIUM), "нужен Playwright и Chromium")
class FriendPage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.box = FakeNtfy()
        self.srv = serve("127.0.0.1", 0, lambda name: A.AgentHub(
            {"radiant": A.RulesBackend(), "dire": A.RulesBackend()}, sync=True))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.key = C.load_keys(("dire",), path=Path(self.tmp.name) / "keys.json")["dire"]
        self.secret = RV.new_secret()
        self.consoles = []

    def console(self):
        con = C.serve_console(self.srv.hub, "127.0.0.1", 0, "local", {"dire": self.key}, rv_origin=self.box.base)
        threading.Thread(target=con.serve_forever, daemon=True).start()
        self.consoles.append(con)
        return con, C.console_url(f"http://127.0.0.1:{con.server_address[1]}", self.key)

    def tearDown(self):
        for s in self.consoles + [self.srv]:
            try:
                s.shutdown()
                s.server_close()
            except OSError:
                pass
        self.box.close()
        self.tmp.cleanup()

    def post(self, obj, secret=None):
        RV.publish(self.box.base, RV.topic(self.secret), RV.seal(secret or self.secret, {**obj, "t": time.time()}))

    def test_finds_game_ignores_forgery_follows_restart(self):
        friend = P.make_friend_file(Path(self.tmp.name) / "ДЛЯ_ДРУГА.html", self.secret, self.box.base)
        con_a, url_a = self.console()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            page.goto(friend.as_uri() + "?every=300")
            page.wait_for_function("document.getElementById('status').innerText.includes('ещё не запустил')")
            self.post({"url": "https://evil-site-x.trycloudflare.com/c/x/"}, secret=RV.new_secret())   # подделка
            page.wait_for_timeout(800)
            self.assertTrue(page.url.startswith("file://"))                    # подделку не слушает
            self.post({"url": url_a})                                          # хост запустил игру
            page.wait_for_url(url_a + "#rv=*", timeout=10000)
            page.wait_for_selector("#title:has-text('Тьма')", timeout=10000)
            self.assertIn("&b=", page.url)
            # хост перезапустил игру: у туннеля новый адрес, старый пульт пропал
            con_b, url_b = self.console()
            self.post({"url": url_b})
            con_a.shutdown()
            con_a.server_close()
            self.consoles.remove(con_a)
            page.wait_for_url(url_b + "#rv=*", timeout=25000)                  # пульт перешёл сам
            page.wait_for_selector("#title:has-text('Тьма')", timeout=10000)
            # хост закрыл игру — пульт говорит об этом
            self.post({"closed": True})
            con_b.shutdown()
            con_b.server_close()
            self.consoles.remove(con_b)
            page.wait_for_selector("#link:has-text('закрыл игру')", timeout=25000)   # под CSP пульта — селектор
            for _ in range(5):                                                 # надпись не затирается каждую секунду
                page.wait_for_timeout(600)
                self.assertIn("закрыл игру", page.inner_text("#link"))
            browser.close()

    def test_dead_link_is_not_opened(self):
        """Хост закрыл окно крестиком: в ящике осталась ссылка, но пульт по ней не отвечает — файл друга туда не
        уходит (раньше вкладка застревала на странице ошибки), а когда хост запускает игру снова — открывает пульт."""
        friend = P.make_friend_file(Path(self.tmp.name) / "ДЛЯ_ДРУГА.html", self.secret, self.box.base)
        dead_con, dead_url = self.console()
        dead_con.shutdown()
        dead_con.server_close()
        self.consoles.remove(dead_con)
        self.post({"url": dead_url, "fv": RV.FRIEND_VERSION + 1})             # и хост уже с новой версией файла
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            page.goto(friend.as_uri() + "?every=300")
            page.wait_for_selector("#status:has-text('не отвечает')", timeout=10000)
            page.wait_for_selector("#manual:not(.hidden)", timeout=10000)      # после трёх проверок — ручной ввод
            self.assertTrue(page.url.startswith("file://"))
            self.assertIn("новый файл", page.inner_text("#note"))
            con, url = self.console()
            self.post({"url": url})                                            # хост запустил игру снова
            page.wait_for_url(url + "#rv=*", timeout=10000)
            page.wait_for_selector("#title:has-text('Тьма')", timeout=10000)
            browser.close()

    def test_pult_does_not_follow_dead_address(self):
        """Рецензия 2: у пульта проверку «жив ли адрес» тесты не ловили. Хост перезапустил игру и сразу упал: в ящике
        новый адрес, но он мёртв — открытый пульт туда не уходит, а уходит на следующий живой."""
        friend = P.make_friend_file(Path(self.tmp.name) / "ДЛЯ_ДРУГА.html", self.secret, self.box.base)
        con_a, url_a = self.console()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            page.goto(friend.as_uri() + "?every=300")
            self.post({"url": url_a})
            page.wait_for_url(url_a + "#rv=*", timeout=10000)
            page.wait_for_selector("#title:has-text('Тьма')", timeout=10000)
            dead, dead_url = self.console()
            dead.shutdown()
            dead.server_close()
            self.consoles.remove(dead)
            self.post({"url": dead_url})
            con_a.shutdown()
            con_a.server_close()
            self.consoles.remove(con_a)
            page.wait_for_selector("#link:has-text('не отвечает')", timeout=15000)
            page.wait_for_timeout(6000)                                        # пульт уже спросил ящик хотя бы раз
            self.assertTrue(page.url.startswith(url_a), page.url)
            con_c, url_c = self.console()
            self.post({"url": url_c})
            page.wait_for_url(url_c + "#rv=*", timeout=25000)
            page.wait_for_selector("#title:has-text('Тьма')", timeout=10000)
            browser.close()

    def test_without_scripts_says_what_to_do(self):
        friend = P.make_friend_file(Path(self.tmp.name) / "ДЛЯ_ДРУГА.html", self.secret, self.box.base)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_context(java_script_enabled=False).new_page()
            page.goto(friend.as_uri())
            self.assertIn("скрипты выключены", page.inner_text("body"))
            self.assertFalse(page.is_visible("#status"))                       # не «Ищу игру…» навсегда
            browser.close()

    def test_manual_link_when_mailbox_unreachable(self):
        friend = P.make_friend_file(Path(self.tmp.name) / "ДЛЯ_ДРУГА.html", self.secret, "http://127.0.0.1:9")
        con, url = self.console()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            page.goto(friend.as_uri() + "?every=200")
            page.wait_for_selector("#manual:not(.hidden)", timeout=10000)
            self.assertEqual(page.evaluate("Rendezvous.pultUrl('https://a-b.trycloudflare.com/c/K?x=1#rv=z')"),
                             "https://a-b.trycloudflare.com/c/K/")              # хвост из адресной строки — мимо
            page.fill("#link", "javascript:alert(1)")
            page.click("#go")
            page.wait_for_timeout(500)                                         # ящик проверен ещё пару раз
            self.assertIn("не ссылка на пульт", page.inner_text("#err"))       # и сообщение не затёрто
            self.assertTrue(page.url.startswith("file://"))
            page.fill("#link", url.rstrip("/"))
            page.click("#go")
            page.wait_for_url(url + "#rv=*", timeout=10000)
            browser.close()


if __name__ == "__main__":
    unittest.main()
