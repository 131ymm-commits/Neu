"""Имена API в коде для игры сверяются с опубликованными описаниями, а не с памятью.

Игры здесь нет, поэтому опечатка в имени функции Valve всплыла бы только на компьютере
человека. Списки (game/data/, генератор gen_api_lists.py):
  vscripts_api.txt  — @moddota/dota-data 0.47.2 (сервер кастомки);
  panorama_api.txt  — @moddota/panorama-types 1.39.2 (интерфейс кастомки);
  botapi_names.txt  — API скриптов ботов по коду Open Hyper AI (работает в игре).
  events_api.txt    — игровые события и их поля, оттуда же (files/events.json).
Имя, которого нет в списке, допускается только из ALLOW с указанием источника.
"""
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
DATA = GAME / "data"
sys.path.insert(0, str(DATA))

from gen_api_lists import strip_lua  # noqa: E402

PROBE = GAME / "probe_addon"
VS = PROBE / "game" / "scripts" / "vscripts"
JS = PROBE / "content" / "panorama" / "scripts" / "custom_game" / "probe.js"
CG = GAME / "custom_game"                                      # каркас кастомки
CVS = CG / "game" / "scripts" / "vscripts"
CJS = CG / "content" / "panorama" / "scripts" / "custom_game" / "coach_hud.js"
# модули, которые установщик кладёт в vscripts под другим именем (game/custom_game/install_game.py)
INSTALLED = {"vc_intents": "coach_intents", "vc_voice": "coach_voice", "vc_text": "coach_text",
             "vc_text_data": "coach_text_data", "vc_json": "json"}

# Имена вне списков — с источником
ALLOW = {
    # событие веб-панели: в panorama-types 1.39.2 его нет; используется в api_html_proxy.js
    # Windy10v10AI (коммит 63d3246, 07.10.2026): $.RegisterEventHandler('HTMLTitle', panel, (src, title) => …)
    "HTMLTitle",
}
LUA_STD = {"print", "pcall", "require", "rawget", "tostring", "tonumber", "type", "ipairs", "pairs",
           "string", "table", "math", "os", "next", "select", "unpack", "error", "setmetatable",
           "getmetatable", "loadfile", "loadstring", "load", "io", "jit", "class", "assert"}
LUA_STRING_METHODS = {"gsub", "format", "sub", "find", "match", "gmatch", "lower", "upper", "len", "rep", "byte"}
# Глобальные объекты vscripts, которых нет в instance: (тип по api.json)
VS_TYPED = {
    "probe.lua": {"gm": "CDOTABaseGameMode", "e.hero": "CDOTA_BaseNPC_Hero", "h": "CDOTA_BaseNPC_Hero",
                  "buff": "CDOTA_Buff", "req": "CScriptHTTPRequest", "player": "CDOTAPlayerController"},
    "coach_bridge.lua": {"req": "CScriptHTTPRequest"},
    "coach_world.lua": {"tower": "CDOTA_BaseNPC", "f": "CBaseEntity", "hero": "CDOTA_BaseNPC_Hero",
                        "ab": "CDOTABaseAbility", "unit": "CDOTA_BaseNPC", "t.unit": "CDOTA_BaseNPC",
                        "u": "CDOTA_BaseNPC", "it": "CDOTA_Item"},
    "coach_game.lua": {"hero": "CDOTA_BaseNPC_Hero", "unit": "CDOTA_BaseNPC", "gm": "CDOTABaseGameMode",
                       "ab": "CDOTABaseAbility", "act.ability": "CDOTABaseAbility", "order.target": "CDOTA_BaseNPC",
                       "act.target": "CDOTA_BaseNPC", "a.ability": "CDOTABaseAbility", "killed": "CDOTA_BaseNPC",
                       "killer": "CDOTA_BaseNPC", "e": "CDOTA_BaseNPC"},
    "coach_obs.lua": {"t.unit": "CDOTA_BaseNPC"},
    "coach_link.lua": {"req": "CScriptHTTPRequest"},
}
# Переменные скриптов ботов, которые держат объекты API ботов
BOT_OBJECTS = {"bot", "a", "unit", "npcBot", "hero", "ability", "req"}


def load_vscripts():
    names, inst, ext = set(), {}, {}
    for line in (DATA / "vscripts_api.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("instance:"):
            k, v = line[len("instance:"):].split("=", 1)
            inst[k] = v
        elif line.startswith("extends:"):
            k, v = line[len("extends:"):].split("=", 1)
            ext[k] = v
        else:
            names.add(line)
    return names, inst, ext


def load_botapi():
    out = {"fn": set(), "method": set(), "const": set()}
    for line in (DATA / "botapi_names.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            kind, name = line.split(":", 1)
            out[kind].add(name)
    return out


NAMES, INST, EXT = load_vscripts()
METHODS_ANY = {n.split(".", 1)[1] for n in NAMES if "." in n}


def has_method(cls, method):
    seen = set()
    while cls and cls not in seen:
        if f"{cls}.{method}" in NAMES:
            return True
        seen.add(cls)
        cls = EXT.get(cls)
    return False


def defined_in(code):
    """Имена, которые код определяет сам: функции, методы, локальные и глобальные переменные."""
    d = set(re.findall(r"function\s+(?:[\w.]+[.:])?(\w+)\s*\(", code))
    for grp in re.findall(r"\blocal\s+([\w\s,]+?)\s*=", code):
        d |= {x.strip() for x in grp.split(",")}
    d |= set(re.findall(r"\blocal\s+function\s+(\w+)", code))
    d |= set(re.findall(r"^\s*(\w+)\s*=", code, re.M))
    d |= set(re.findall(r"_G\.(\w+)\s*=", code))
    return d


def lua(path):
    return strip_lua(path.read_text(encoding="utf-8"))


class VscriptsNames(unittest.TestCase):
    """Сервер кастомки: пробник и мост тренера."""

    # группы файлов, которые видят глобальные имена друг друга: пробник, каркас кастомки, мост
    GROUPS = [
        [VS / "probe.lua", VS / "addon_game_mode.lua", VS / "modifiers" / "modifier_voicecoach_probe.lua",
         VS / "modifiers" / "modifier_voicecoach_commander.lua"],
        [CVS / "coach_game.lua", CVS / "coach_world.lua", CVS / "coach_exec.lua", CVS / "coach_obs.lua",
         CVS / "coach_link.lua", CVS / "addon_game_mode.lua", CVS / "modifiers" / "modifier_voicecoach_commander.lua"],
        [GAME / "shared" / "coach_bridge.lua"],
    ]
    FILES = [p for g in GROUPS for p in g]

    def check_file(self, path, project=frozenset()):
        code = lua(path)
        own = defined_in(code) | project          # project: глобальные имена из соседних файлов аддона
        typed = VS_TYPED.get(path.name, {})
        bad = []
        # глобальные объекты: GameRules:X(), PlayerResource:X() …
        for obj, m in re.findall(r"(?<![\w.:])([A-Z]\w*)\s*:\s*(\w+)\s*\(", code):
            if obj in INST:
                if not has_method(INST[obj], m):
                    bad.append(f"{obj}:{m} ({INST[obj]})")
            elif obj not in own:
                bad.append(f"{obj}:{m} — неизвестный объект")
        # цепочка GameRules:GetGameModeEntity():X()
        for m in re.findall(r"GetGameModeEntity\(\)\s*:\s*(\w+)\s*\(", code):
            if not has_method("CDOTABaseGameMode", m):
                bad.append(f"GetGameModeEntity():{m}")
        # переменные известного типа
        for var, cls in typed.items():
            for m in re.findall(r"(?<![\w.])" + re.escape(var) + r"\s*:\s*(\w+)\s*\(", code):
                if not has_method(cls, m):
                    bad.append(f"{var}:{m} ({cls})")
        # прочие методы: имя должно быть методом хоть какого-то класса API или своим
        for recv, m in re.findall(r"([\w.\])]+)\s*:\s*(\w+)\s*\(", code):
            base = recv.split(".")[0]
            if base in INST or recv in typed or base in own and base[:1].isupper():
                continue
            if m not in METHODS_ANY and m not in own and m not in LUA_STRING_METHODS:
                bad.append(f"{recv}:{m} — нет ни в одном классе")
        # глобальные функции и конструкторы
        for f in re.findall(r"(?<![\w.:])([A-Z]\w*)\s*\(", code):
            if f in own or f in NAMES or f in EXT:      # EXT: классы-конструкторы (Vector)
                continue
            bad.append(f"{f}() — нет в списке функций")
        # константы
        for c in re.findall(r"(?<![\w.:])([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b", code):
            if c not in NAMES and c not in own:
                bad.append(f"{c} — нет в списке констант")
        # переопределения модификатора
        for cls, m in re.findall(r"function\s+(modifier_\w+)\s*:\s*(\w+)\s*\(", code):
            if not has_method("CDOTA_Modifier_Lua", m):
                bad.append(f"{cls}:{m} — нет у CDOTA_Modifier_Lua")
        return sorted(set(bad))

    def test_names_exist(self):
        for group in self.GROUPS:
            project = set()
            for path in group:                     # файлы одного аддона видят глобальные имена друг друга
                project |= set(re.findall(r"^(\w+)\s*=", lua(path), re.M))
            for path in group:
                with self.subTest(file=f"{path.parent.name}/{path.name}"):
                    self.assertEqual(self.check_file(path, frozenset(project)), [])

    def test_checker_catches_typos(self):
        # сам проверщик должен ловить опечатки — иначе пустой список ничего не значит
        tmp = HERE / "_tmp_typo.lua"
        tmp.write_text('GameRules:SetPreGameTim(30)\nTutorial:AddBott("x")\nCreateHTTPRequestScript("GET", "u")\n'
                       'local x = DOTA_TEAM_GOODGUY\nfunction modifier_x:IsHiden() return true end\n', encoding="utf-8")
        try:
            bad = self.check_file(tmp)
        finally:
            tmp.unlink()
        self.assertEqual(len(bad), 5, bad)


def load_events():
    out = {}
    for line in (DATA / "events_api.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, _, fields = line.partition(":")
            out[name.strip()] = set(fields.split())
    return out


class GameEvents(unittest.TestCase):
    """Игровые события кастомки: имя есть в описании Доты, обработчик читает только его поля."""

    EVENTS = load_events()

    def test_listened_events_and_fields(self):
        code = (CVS / "coach_game.lua").read_text(encoding="utf-8")       # с литералами: имена событий — строки
        pairs = re.findall(r'ListenToGameEvent\("(\w+)",\s*Dynamic_Wrap\(G,\s*"(\w+)"\)', code)
        self.assertEqual({e for e, _ in pairs}, {"game_rules_state_change", "npc_spawned", "player_chat", "entity_killed"})
        for event, handler in pairs:
            with self.subTest(event=event):
                self.assertIn(event, self.EVENTS)
                body = re.search(r"function G:" + handler + r"\((\w*)\)(.*?)\nend\n", code, re.S)
                self.assertIsNotNone(body, handler)
                arg, text = body.group(1), body.group(2)
                used = set(re.findall(r"\b" + re.escape(arg) + r"\.(\w+)", text)) if arg else set()
                self.assertLessEqual(used, self.EVENTS[event], (event, used - self.EVENTS[event]))

    def test_checker_catches_wrong_field(self):
        self.assertNotIn("killer_index", self.EVENTS["entity_killed"])
        self.assertIn("entindex_attacker", self.EVENTS["entity_killed"])


class BotApiNames(unittest.TestCase):
    """Скрипты ботов: модуль тренера для OHA и бот-пробник аддона."""

    API = load_botapi()
    FILES = [GAME / "prototype_oha" / "coach" / "coach_bot.lua", VS / "bots" / "mode_rune_generic.lua"]

    def check_file(self, path):
        code = lua(path)
        own = defined_in(code)
        bad = []
        for obj, m in re.findall(r"(?<![\w.:])(\w+)\s*:\s*(\w+)\s*\(", code):
            if obj in BOT_OBJECTS and m not in self.API["method"]:
                bad.append(f"{obj}:{m}")
        for f in re.findall(r"(?<![\w.:])([A-Z]\w*)\b", code):
            if f in own or f in self.API["fn"] or f in self.API["const"]:
                continue
            bad.append(f"{f} — нет в API ботов")
        return sorted(set(bad))

    def test_names_exist(self):
        for path in self.FILES:
            with self.subTest(file=path.name):
                self.assertEqual(self.check_file(path), [])

    def test_checker_catches_typos(self):
        tmp = HERE / "_tmp_typo_bot.lua"
        tmp.write_text("local bot = GetBott()\nbot:ActionImmediate_Chatt('x', true)\nlocal m = BOT_MODE_ROSHANN\n",
                       encoding="utf-8")
        try:
            bad = self.check_file(tmp)
        finally:
            tmp.unlink()
        self.assertEqual(len(bad), 3, bad)


class PanoramaNames(unittest.TestCase):
    """Интерфейс: probe.js (пробник) и coach_hud.js (каркас кастомки)."""

    NAMES = {l for l in (DATA / "panorama_api.txt").read_text(encoding="utf-8").splitlines()
             if l and not l.startswith("#")}

    def code(self, path=JS):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return re.sub(r"//[^\n]*", "", text)

    def used(self, code):
        used = set(re.findall(r"\$\.(\w+)\s*\(", code))
        used |= set(re.findall(r"\b(?:GameEvents|GameUI|Game|Players)\.(\w+)\s*\(", code))
        used |= set(re.findall(r"\bDOTATeam_t\.(\w+)", code))
        used |= set(re.findall(r"\b(?:panel|label|input|log|line|box|row|mode)\.(\w+)\s*[(=]", code))
        used |= set(re.findall(r"\$\('[^']+'\)\.(\w+)\s*[(=]", code))
        used |= set(re.findall(r"CreatePanel\(\s*'(\w+)'", code))
        used |= set(re.findall(r"RegisterEventHandler\(\s*'(\w+)'", code))
        used |= set(re.findall(r"SetPanelEvent\(\s*'(\w+)'", code))
        used |= set(re.findall(r"\bE\.(DOTA_DEFAULT_UI_\w+)", code))
        return used

    def test_names_exist(self):
        used = self.used(self.code())
        missing = sorted(n for n in used if n not in self.NAMES and n not in ALLOW)
        self.assertEqual(missing, [])
        self.assertIn("SetURL", used)
        self.assertIn("DOTAHTMLPanel", used)

    def test_hud_names_exist(self):
        used = self.used(self.code(CJS))
        missing = sorted(n for n in used if n not in self.NAMES and n not in ALLOW)
        self.assertEqual(missing, [])
        for n in ("SetCameraDistance", "SetDefaultUIEnabled", "oninputsubmit", "DOTA_DEFAULT_UI_ACTION_PANEL"):
            self.assertIn(n, used)

    def test_hud_voice_address_matches_agents_server(self):
        """Скрытая веб-панель голосового чата ходит на тот же сервер тренера, что и игра (Д12)."""
        raw_lua = (CVS / "coach_game.lua").read_text(encoding="utf-8")
        code = CJS.read_text(encoding="utf-8")
        game = re.search(r'G\.AGENTS_URL = "(http://[^/"]+)/', raw_lua).group(1)
        hud = re.search(r"var VOICE_URL = '(http://[^/']+)/voice\.html'", code).group(1)
        self.assertEqual(game, hud)
        for n in ("GetTeam", "GetLocalPlayer", "DOTA_TEAM_BADGUYS", "SetURL", "DOTAHTMLPanel"):
            self.assertIn(n, self.used(self.code(CJS)))

    def test_hud_events_match_server(self):
        code = self.code(CJS)
        raw = (CVS / "coach_game.lua").read_text(encoding="utf-8")
        to_server = set(re.findall(r"SendCustomGameEventToServer\(\s*'(\w+)'", code))
        self.assertEqual(to_server, {"vc_command", "vc_ready"})
        self.assertLessEqual(to_server, set(re.findall(r'RegisterListener\("(\w+)"', raw)))
        to_client = set(re.findall(r'Send_ServerTo(?:Player|Team)\([^,]+,\s*"(\w+)"', raw))
        self.assertEqual(to_client, {"vc_reply", "vc_ack", "vc_agents"})
        self.assertLessEqual(to_client, set(re.findall(r"GameEvents\.Subscribe\(\s*'(\w+)'", code)))

    def test_custom_events_match_server(self):
        """События клиента ↔ слушатели сервера, подтверждения сервера ↔ подписки клиента."""
        code = self.code()
        probe = lua(VS / "probe.lua")
        raw = (VS / "probe.lua").read_text(encoding="utf-8")
        to_server = set(re.findall(r"SendCustomGameEventToServer\(\s*'(\w+)'", code))
        listened = set(re.findall(r'RegisterListener\("(\w+)"', raw))
        self.assertTrue(to_server)
        self.assertLessEqual(to_server, listened)
        to_client = set(re.findall(r'Send_ServerToPlayer\([^,]+,\s*"(\w+)"', raw))
        subscribed = set(re.findall(r"GameEvents\.Subscribe\(\s*'(\w+)'", code))
        self.assertTrue(to_client)
        self.assertLessEqual(to_client, subscribed)
        self.assertIn("RegisterListener", probe)

    def test_server_address_matches(self):
        raw_lua = (VS / "probe.lua").read_text(encoding="utf-8")
        code = JS.read_text(encoding="utf-8")
        self.assertEqual(re.search(r'P\.SERVER = "([^"]+)"', raw_lua).group(1),
                         re.search(r"var SERVER = '([^']+)'", code).group(1))
        self.assertEqual(re.search(r'P\.ROOM = "([^"]+)"', raw_lua).group(1),
                         re.search(r"var ROOM = '([^']+)'", code).group(1))


class AddonLayout(unittest.TestCase):
    def test_files_referenced_exist(self):
        manifest = (PROBE / "content/panorama/layout/custom_game/custom_ui_manifest.xml").read_text(encoding="utf-8")
        for rel in re.findall(r"file://\{resources\}/([\w/.]+)", manifest):
            self.assertTrue((PROBE / "content/panorama" / rel).exists(), rel)
        layout = (PROBE / "content/panorama/layout/custom_game/probe.xml").read_text(encoding="utf-8")
        for rel in re.findall(r"file://\{resources\}/([\w/.]+)", layout):
            self.assertTrue((PROBE / "content/panorama" / rel).exists(), rel)

    def test_addoninfo_standard_map(self):
        info = (PROBE / "game/addoninfo.txt").read_text(encoding="utf-8")
        self.assertRegex(info, r'"maps"\s+"dota"')

    def test_lua_requires_exist(self):
        for path in VS.rglob("*.lua"):
            for mod in re.findall(r'require\("([\w/]+)"\)', path.read_text(encoding="utf-8")):
                self.assertTrue((VS / f"{mod}.lua").exists(), f"{path.name}: require {mod}")

    def test_custom_game_layout(self):
        info = (CG / "game/addoninfo.txt").read_text(encoding="utf-8")
        self.assertRegex(info, r'"maps"\s+"dota"')
        for xml in ("custom_ui_manifest.xml", "coach_hud.xml"):
            text = (CG / "content/panorama/layout/custom_game" / xml).read_text(encoding="utf-8")
            for rel in re.findall(r"file://\{resources\}/([\w/.]+)", text):
                self.assertTrue((CG / "content/panorama" / rel).exists(), rel)
        for path in CVS.rglob("*.lua"):
            for mod in re.findall(r'require\("([\w/]+)"\)', path.read_text(encoding="utf-8")):
                if mod in INSTALLED:
                    self.assertTrue((GAME / "shared" / f"{INSTALLED[mod]}.lua").exists(), mod)
                else:
                    self.assertTrue((CVS / f"{mod}.lua").exists(), f"{path.name}: require {mod}")


if __name__ == "__main__":
    unittest.main()
