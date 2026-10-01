"""PLAY-01, сухой прогон: «читер» с доступом к живому серверу и к сейвам должен быть пойман сверками.
(1) подмена сейва между раундами → sha256 не совпадает с журналом, раунд не начинается;
(2) запись через RCON во время раунда (выдать себе предметы) → сверка баланса находит расхождение;
(3) та же запись → повтор журнала с исходного сейва даёт другой хеш состояния."""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import game
st = json.load(open(os.path.join(HERE, 'runs/dry/state.json')))
c = st['chains']['cheat_s9101']
W = os.path.join(HERE, 'runs/dry/work/cheat_test'); os.makedirs(W, exist_ok=True)
out = {}
# (1) подмена сейва
fake = os.path.join(W, 'fake.zip'); shutil.copy(c['save'], fake); open(fake, 'ab').write(b'\0')
try: game.round_unit(fake, c['sha'], [], 60, os.path.join(W, 'x.zip'), os.path.join(W, 'w1')); out['tamper'] = 'НЕ пойман'
except RuntimeError as e: out['tamper'] = 'пойман: ' + str(e)
# (2) запись через RCON во время раунда
srv = game.Server(os.path.join(W, 'w2'), c['save'], next(game.PORTS)).start()
s0 = json.loads(srv.r.call('snapshot'))
srv.r.call('submit', game.hexs([{'a': 'wait', 'ticks': 30}]))
srv.r.raw('/sc __neu-play__ storage.c.insert{name="iron-plate",count=50}; rcon.print("ok")')
srv.run_ticks(60); srv.r.call('end_round')
s1 = json.loads(srv.r.call('snapshot')); h_live = srv.r.call('hash'); srv.stop()
out['balance'] = game.balance(s0, s1)
# (3) повтор того же раунда без записи
r = game.round_unit(c['save'], c['sha'], [{'a': 'wait', 'ticks': 30}], 60, os.path.join(W, 'y.zip'), os.path.join(W, 'w3'), observe_after=False)
out['replay_hash'], out['live_hash'], out['replay_caught'] = r['state_hash'], h_live, r['state_hash'] != h_live
shutil.rmtree(W, ignore_errors=True)
json.dump(out, open(os.path.join(HERE, 'runs/dry/cheat_check.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
