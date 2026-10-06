# ROCKET-02 (ваниль: исследования с нуля, стартовый набор обычной игры): демон кампании. Один постоянный мир на весь путь до запуска ракеты; эпизоды голов подключаются по очереди.
# Мир не сбрасывается между эпизодами (FLE сбрасывает карту только при создании подключения — оно одно на всю кампанию).
#   python campaign_daemon.py <slot> <logdir>
import json, os, re, resource, socket, sys, time, traceback
# предел памяти процесса 3 ГБ: огромный ответ FLE (get_entities по большой области) раньше раздувал демон до 10,8 ГБ, и система убивала его и соседние серверы (ERRORS № 66)
resource.setrlimit(resource.RLIMIT_AS, (3 * 1024 ** 3, 3 * 1024 ** 3))
from fle.env.instance import FactorioInstance
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import combat
slot, logdir = int(sys.argv[1]), sys.argv[2]; os.makedirs(logdir, exist_ok=True)
SOCK = f'/tmp/claude-0/fact/slot{slot}.sock'; NOTES = os.path.join(logdir, 'NOTES.md')
BANNED = re.compile(r'(\bimport\b|__|\brcon|\binstance\b|\bexec\b|\beval\b|\bopen\s*\(|\bglobals\b|\blocals\b|\bgetattr\b|\bsetattr\b|\bvars\b|\bcompile\b|lua|/sc|/c\b)', re.I)
START_INV = {"iron-plate": 8, "wood": 1, "pistol": 1, "firearm-magazine": 10, "burner-mining-drill": 1, "stone-furnace": 1}  # стартовый набор freeplay Factorio 2.0
ATTACH = os.environ.get('NEU_ATTACH') == '1'   # переподключиться к живому миру БЕЗ сброса (после падения демона)
class AttachInstance(FactorioInstance):
    # initialise FLE без _reset: _reset вызывает reset_game_state, force.reset() (стирает исследования), регенерацию руды и очистку построек
    def initialise(self, fast=True, all_technologies_researched=True, clear_entities=True):
        self.rcon_client.send_command(f"/sc storage.fast = {str(fast).lower()}")
        self.first_namespace._create_agent_characters(self.num_agents)
        for script_name in ["lualib_util", "utils", "alerts", "connection_points", "recipe_fluid_connection_mappings", "serialize", "serialize_direction_fix"]:
            self.lua_script_manager.load_init_into_game(script_name)
        self._generate_chunks(center_x=0, center_y=0, chunk_radius=25)
        self.first_namespace._clear_collision_boxes()
if ATTACH:
    inst = AttachInstance(address='localhost', tcp_port=27100 + slot, fast=True, all_technologies_researched=False)
else:
    inst = FactorioInstance(address='localhost', tcp_port=27100 + slot, fast=True, all_technologies_researched=False)
    inst.initial_inventory = START_INV; inst.reset(all_technologies_researched=False)
LOG = open(os.path.join(logdir, 'campaign.jsonl'), 'a')
def log(**k): LOG.write(json.dumps(dict(t=time.time(), **k), ensure_ascii=False) + '\n'); LOG.flush()
MILE = ['iron-plate', 'copper-plate', 'steel-plate', 'stone-brick', 'plastic-bar', 'sulfur', 'electronic-circuit', 'advanced-circuit', 'processing-unit', 'engine-unit',
        'electric-engine-unit', 'low-density-structure', 'solid-fuel', 'rocket-fuel', 'concrete', 'rocket-silo', 'rocket-part',
        'lab', 'automation-science-pack', 'logistic-science-pack', 'military-science-pack', 'chemical-science-pack', 'production-science-pack', 'utility-science-pack']
def milestones():
    q = '/sc local st = game.forces.player.get_item_production_statistics(game.surfaces[1]); local o = {tick = game.tick, rockets = game.forces.player.rockets_launched, silos = #game.surfaces[1].find_entities_filtered{name="rocket-silo"}}\nlocal f = game.forces.player; local n = 0; for _, t in pairs(f.technologies) do if t.researched then n = n + 1 end end; o.techs_researched = n; o.research = f.current_research and f.current_research.name or ""; o.silo_tech = f.technologies["rocket-silo"].researched\n' + \
        ''.join(f'o["{k}"] = st.get_input_count("{k}")\n' for k in MILE) + 'rcon.print(helpers.table_to_json(o))'
    return json.loads(inst.rcon_client.send_command(q).strip())
inst.rcon_client.send_command('/sc rcon.print(1)')
ep = None; steps = 0; max_steps = 0
log(event='campaign_start', milestones=milestones())
if os.path.exists(SOCK): os.remove(SOCK)
srv = socket.socket(socket.AF_UNIX); srv.bind(SOCK); srv.listen(1); print('READY', flush=True)
while True:
    c, _ = srv.accept(); data = b''
    while not data.endswith(b'\n\x00'):
        part = c.recv(65536)
        if not part: break
        data += part
    req = json.loads(data[:-2].decode()); cmd = req.get('cmd')
    if cmd == 'begin':      # начало эпизода (только оркестратор)
        ep, steps, max_steps = req['ep'], 0, int(req['max_steps']); out = dict(ok=True); log(event='begin', ep=ep, max_steps=max_steps, milestones=milestones())
    elif cmd == 'end':
        out = dict(ep=ep, steps=steps, milestones=milestones()); log(event='end', **out); ep = None
    elif cmd == 'status':
        out = dict(ep=ep, steps_used=steps, max_steps=max_steps, milestones=milestones())
    elif cmd == 'notes':
        out = dict(notes=open(NOTES).read()[-20000:] if os.path.exists(NOTES) else '(пусто)')
    elif cmd == 'note':
        txt = req.get('code', '').strip()[:4000]
        with open(NOTES, 'a') as f: f.write(f"\n\n## [{ep}] {time.strftime('%H:%M')}\n{txt}\n")
        out = dict(ok=True); log(event='note', ep=ep, text=txt)
    elif cmd == 'step':
        code = req.get('code', '')
        if ep is None: out = dict(error='эпизод не начат')
        elif steps >= max_steps: out = dict(error=f'лимит шагов эпизода {max_steps} исчерпан')
        elif BANNED.search(code): out = dict(error='запрещённая конструкция: ' + BANNED.search(code).group(0)); log(event='banned', ep=ep, code=code)
        else:
            steps += 1
            try: r = inst.eval(code, agent_idx=0, timeout=300); res = r[2] if isinstance(r, tuple) and len(r) > 2 else str(r)
            except MemoryError: res = 'ошибка: шаг потребовал больше 3 ГБ памяти (слишком большой запрос: сузь радиус и типы в get_entities)'
            except Exception as e: res = 'ошибка: ' + ''.join(traceback.format_exception_only(type(e), e))[-1500:]
            m = milestones(); out = dict(step=steps, steps_left=max_steps - steps, output=str(res)[-6000:], milestones=m)
            log(event='step', ep=ep, step=steps, code=code, output=str(res)[-6000:], milestones=m)
    elif cmd in ('fight', 'scan', 'arm'):   # бой персонажа (combat.py): fight — шаг эпизода; scan и arm — без шага
        try: prm = json.loads(req.get('code') or '{}')
        except Exception as e: prm = None; out = dict(error=f'параметры — JSON: {e}')
        if prm is not None:
            if ep is None: out = dict(error='эпизод не начат')
            elif cmd == 'scan':
                try: out = combat.scan(inst.rcon_client, prm.get('x'), prm.get('y'), min(float(prm.get('radius', 60)), 200))
                except Exception as e: out = dict(error=str(e)[-500:])
            elif cmd == 'arm':
                out = dict(guns_ammo=combat.arm(inst.rcon_client))
            elif steps >= max_steps: out = dict(error=f'лимит шагов эпизода {max_steps} исчерпан')
            else:
                steps += 1
                keys = ('cx', 'cy', 'r', 'mode', 'seconds', 'retreat', 'side', 'clear_radius', 'shoot_range', 'priority', 'home', 'wiggle', 'fish_hp')
                try: out = combat.fight(inst.rcon_client, **{k: prm[k] for k in keys if k in prm})
                except Exception as e: out = dict(error=str(e)[-500:])
                out.update(step=steps, steps_left=max_steps - steps)
            log(event=cmd, ep=ep, params=prm, out=out)
    else: out = dict(error='неизвестная команда')
    try: c.sendall(json.dumps(out, ensure_ascii=False).encode()); c.close()
    except OSError as e: log(event='client_gone', error=str(e))   # клиент оборвался (тайм-аут) — демон живёт дальше
