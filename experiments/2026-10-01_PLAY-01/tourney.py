"""PLAY-01: турнир (дубликат) — цепочки сейвов на пару «участник, зерно», головы через workflow, ход игры в пуле процессов.
   python3 tourney.py init <этап> --seeds 101,102 --parts A,B,C,H,D,bot,rand --R 6 --round 3 --W 5
   python3 tourney.py heads <этап>                 → runs/<этап>/r<k>/seed<s>.js (по workflow на зерно; головы без сервера)
   python3 tourney.py ingest <этап> <out.json>...  → решения голов раунда k (файлы tasks/<id>.output workflow)
   python3 tourney.py play <этап>                  → раунд k для всех цепочек (боты считают решение сами)
   python3 tourney.py score <этап>                 → окно W: S_auto, S′ (контрфактическое окно), сверки
   python3 tourney.py replay <этап>                → журнал действий заново с исходного сейва, хеши на границах раундов
   python3 tourney.py status <этап>
Сейвы лежат вне git (runs/<этап>/saves/, .gitignore); в git — state.json с sha256 каждого сейва и хешами состояния."""
import argparse, json, multiprocessing as mp, os, random, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import game, bots, prompts as P

HEADS = ('A', 'A2', 'B', 'C', 'H', 'D')     # A2 — повтор A (пилот: разброс двух повторов одной конфигурации)
D_MODELS = ('sonnet', 'opus', 'haiku')       # роли D: логистика, добыча и энергия, исследования; тело — opus
WORKERS = 4
GROUPS = (('B', 'A', 'A2'), ('C', 'H'), ('D',))   # головы зерна делятся на workflow: пул агентов — 2 на workflow (4 ядра)


def rd(stage, *a):
    d = os.path.join(HERE, 'runs', stage, *a)
    os.makedirs(d, exist_ok=True)
    return d
def J(p): return json.load(open(p))
def W(p, o): json.dump(o, open(p, 'w'), ensure_ascii=False, indent=1)
def state_path(stage): return os.path.join(rd(stage), 'state.json')
def load(stage): return J(state_path(stage))
def save(stage, st): W(state_path(stage), st)
def key(part, seed): return f'{part}_s{seed}'


def _init_worker(i):
    game.PORTS = iter(range(30000 + 100 * i, 30000 + 100 * i + 99))


def _pool():
    ctx = mp.get_context('fork')
    q = ctx.Queue()
    for i in range(WORKERS): q.put(i)
    return ctx.Pool(WORKERS, initializer=lambda: _init_worker(q.get()))


# ------------------------------------------------------------------------------------------------ init
def _init_seed(a):
    stage, seed = a
    sv = os.path.join(rd(stage, 'saves'), f'init_s{seed}.zip')
    h, out = game.create_initial(seed, sv, os.path.join(rd(stage, 'work'), f'init{seed}'))
    obs, sh = game.observe_save(sv, h, os.path.join(rd(stage, 'work'), f'obs{seed}'))
    return seed, sv, h, obs, sh


def init(stage, seeds, parts, R, rmin, wmin):
    cfg = dict(stage=stage, seeds=seeds, parts=parts, R=R, round_ticks=int(round(rmin * 3600)), W_ticks=int(round(wmin * 3600)),
               rmin=rmin, wmin=wmin, prompt_hashes=P.prompt_hashes())
    with _pool() as pool:
        res = pool.map(_init_seed, [(stage, s) for s in seeds])
    chains = {}
    for seed, sv, h, obs, sh in res:
        for p in parts:
            chains[key(p, seed)] = dict(part=p, seed=seed, round=0, save=sv, sha=h, init_save=sv, init_sha=h, state_hash=[sh],
                                        obs=obs, mem=None, botmem={}, hist=[])
    save(stage, dict(cfg=cfg, chains=chains, decisions={}))
    print(f'{stage}: {len(seeds)} зёрен × {len(parts)} участников, R={R}, раунд {rmin} мин, W {wmin} мин')


# ------------------------------------------------------------------------------------------------ heads (workflow)
def _js_str(s): return json.dumps(s, ensure_ascii=False)


def heads(stage):
    st = load(stage); cfg = st['cfg']
    k = min(c['round'] for c in st['chains'].values() if c['part'] in HEADS) + 1
    if k > cfg['R']: print('все раунды сыграны'); return []
    common = P.common(cfg['R'], P._num(cfg['rmin']), P._num(cfg['wmin']))
    paths = []
    for seed in cfg['seeds']:
      for gi, grp in enumerate(GROUPS):
        jobs = {}
        for p in cfg['parts']:
            if p not in HEADS or p not in grp: continue
            c = st['chains'][key(p, seed)]
            if c['round'] != k - 1: continue
            jobs[p] = '\n\n'.join([P.memory_block(c['mem']), P.obs_block(c['obs'], k, cfg['R'])])
        if not jobs: continue
        js = f"""export const meta = {{ name: 'play01-{stage}-r{k}-s{seed}-g{gi}', description: 'PLAY-01 {stage}: раунд {k}, зерно {seed}, головы {"+".join(jobs)}', phases: [{{ title: 'Головы' }}] }}
const COMMON = {_js_str(common)}
const CTX = {_js_str(jobs)}
const SOLO = {_js_str(P.SOLO)}
const B_STEPS = {_js_str(P.B_STEPS)}
const ROLES = {_js_str([r[1] for r in P.ROLES])}
const ROLE_TXT = {_js_str(P.ROLE_TXT)}
const CALLOSUM = {_js_str(P.CALLOSUM_TXT)}
const S = {_js_str(P.SCHEMA)}
const D_MODELS = {_js_str(list(D_MODELS))}
const tag = {_js_str(f'r{k}_s{seed}')}
const mk = (role, ctx, extra) => COMMON + '\\n\\n## Твоя роль\\n' + role + '\\n\\n' + ctx + (extra ? '\\n\\n' + extra : '')
const prev = (r) => '## Решение с прошлого шага\\n' + JSON.stringify(r)
const props = (rs) => rs.map((r, i) => '### Предложение головы «' + ROLES[i] + '»\\n' + (r ? JSON.stringify(r) : '(голова не ответила)')).join('\\n\\n')
let retries = 0
async function call(p, label, model) {{
  const o = {{label: label + '_' + tag, phase: 'Головы', schema: S}}
  if (model) o.model = model
  let r = await agent(p, o)
  if (!r) {{ retries++; r = await agent(p, o) }}
  return r
}}
const RUN = {{
  A: async () => ({{final: await call(mk(SOLO, CTX.A), 'A')}}),
  A2: async () => ({{final: await call(mk(SOLO, CTX.A2), 'A2')}}),
  H: async () => ({{final: await call(mk(SOLO, CTX.H), 'H', 'haiku')}}),
  B: async () => {{
    const s1 = await call(mk(B_STEPS[0], CTX.B), 'B1')
    const s2 = await call(mk(B_STEPS[1].replace('{{k}}', '2'), CTX.B, prev(s1)), 'B2')
    const s3 = await call(mk(B_STEPS[1].replace('{{k}}', '3'), CTX.B, prev(s2)), 'B3')
    const s4 = await call(mk(B_STEPS[2], CTX.B, prev(s3)), 'B4')
    return {{steps: [s1, s2, s3], final: s4}}
  }},
  C: async () => {{
    const rs = await parallel(ROLES.map((a, i) => () => call(mk(ROLE_TXT.replace('{{area}}', a), CTX.C), 'C' + (i + 1))))
    return {{roles: rs, final: await call(mk(CALLOSUM, CTX.C, props(rs)), 'Ccc')}}
  }},
  D: async () => {{
    const rs = await parallel(ROLES.map((a, i) => () => call(mk(ROLE_TXT.replace('{{area}}', a), CTX.D), 'D' + (i + 1), D_MODELS[i])))
    return {{roles: rs, final: await call(mk(CALLOSUM, CTX.D, props(rs)), 'Dcc', 'opus')}}
  }},
}}
phase('Головы')
const parts = Object.keys(CTX)
const res = await parallel(parts.map(p => () => RUN[p]()))
const out = {{}}
parts.forEach((p, i) => {{ out[p] = res[i] }})
return {{stage: {_js_str(stage)}, round: {k}, seed: {seed}, group: {gi}, retries, out}}
"""
        path = os.path.join(rd(stage, f'r{k}'), f'seed{seed}_g{gi}.js')
        open(path, 'w').write(js)
        paths.append(path)
    print('\n'.join(paths))
    return paths


def ingest(stage, files):
    st = load(stage)
    n = 0
    for f in files:
        d = J(f)
        r = d.get('result', d)
        k, seed = r['round'], r['seed']
        dec = st['decisions'].setdefault(str(k), {})
        for p, v in r['out'].items():
            dec[key(p, seed)] = dict(v or {}, retries=r.get('retries', 0))
            n += 1
        W(os.path.join(rd(stage, f'r{k}'), f'out_seed{seed}_g{r.get("group", 0)}.json'), r)
    save(stage, st)
    print(f'принято решений: {n}')


# ------------------------------------------------------------------------------------------------ play
def clean_actions(final):
    """Действие — только ключи языка; не больше 40 (лишнее отбрасывает мод и пишет dropped)."""
    keys = ('a', 'x', 'y', 'n', 'item', 'recipe', 'tech', 'dir', 'ticks')
    acts = []
    for a in (final or {}).get('actions') or []:
        if isinstance(a, dict): acts.append({k: a[k] for k in keys if k in a})
    return acts


def _play_one(a):
    stage, ck, c, actions, ticks, k = a
    out = os.path.join(rd(stage, 'saves'), f'{ck}_r{k}.zip')
    work = os.path.join(rd(stage, 'work'), f'{ck}_r{k}')
    t = time.time()
    r = game.round_unit(c['save'], c['sha'], actions, ticks, out, work)
    shutil.rmtree(work, ignore_errors=True)
    r['save'], r['secs'] = out, round(time.time() - t, 1)
    return ck, r


def decide_bots(st, ck, c, k):
    cfg = st['cfg']
    if c['part'] == 'bot': return bots.bot(c['obs'], c['botmem'], k, cfg['R'], cfg['round_ticks'])
    if c['part'] == 'rand': return bots.random_agent(c['obs'], random.Random(c['seed'] * 1000 + k), cfg['round_ticks'])
    if c['part'] == 'idle': return []
    if c['part'] == 'cheat': return bots.cheater(c['obs'], k)
    raise KeyError(c['part'])


def play(stage):
    st = load(stage); cfg = st['cfg']
    jobs, meta = [], {}
    for ck, c in st['chains'].items():
        k = c['round'] + 1
        if k > cfg['R']: continue
        if c['part'] in HEADS:
            d = st['decisions'].get(str(k), {}).get(ck)
            if d is None: continue
            final = d.get('final')
            acts = clean_actions(final)
            meta[ck] = dict(final=final, failed=final is None)
        else:
            acts = decide_bots(st, ck, c, k)
            meta[ck] = dict(final={'actions': acts})
        jobs.append((stage, ck, c, acts, cfg['round_ticks'], k))
    if not jobs: print('нечего играть'); return
    t = time.time()
    with _pool() as pool:
        res = pool.map(_play_one, jobs)
    for ck, r in res:
        c = st['chains'][ck]; k = c['round'] + 1
        actions = [j[3] for j in jobs if j[1] == ck][0]
        fin = meta[ck]['final'] or {}
        c['hist'].append(dict(round=k, actions=actions, head_failed=meta[ck].get('failed', False), predict=fin.get('predict'), note=fin.get('note'),
                              results=r['observe']['last_actions'], submit=r['submit'], state_hash=r['state_hash'], sha=r['sha'],
                              balance=r['balance'], violations=r['violations'], tick0=r['tick0'], tick1=r['tick1'], secs=r['secs'],
                              inventory=r['observe']['inventory'], buildings=r['observe']['entities_total']))
        c['state_hash'].append(r['state_hash'])
        c['round'], c['save'], c['sha'], c['obs'] = k, r['save'], r['sha'], r['observe']
        c['mem'] = dict(actions=actions, note=(fin.get('note') or '')[:P.NOTE_MAX]) if c['part'] in HEADS else None
    save(stage, st)
    bad = {ck: r['balance'] for ck, r in res if r['balance'] or r['violations']}
    print(f'сыграно {len(res)} цепочек за {time.time() - t:.0f} с; сверка баланса: ' + ('без расхождений' if not bad else json.dumps(bad, ensure_ascii=False)))


# ------------------------------------------------------------------------------------------------ score, replay
def _score_one(a):
    stage, ck, c, W_ticks = a
    work = os.path.join(rd(stage, 'work'), f'{ck}_score')
    r = game.score_game(c['save'], c['sha'], W_ticks, work)
    shutil.rmtree(work, ignore_errors=True)
    return ck, r


def score(stage):
    st = load(stage); cfg = st['cfg']
    jobs = [(stage, ck, c, cfg['W_ticks']) for ck, c in st['chains'].items() if c['round'] == cfg['R']]
    with _pool() as pool:
        res = dict(pool.map(_score_one, jobs))
    W(os.path.join(rd(stage), 'scores.json'), res)
    for ck in sorted(res):
        r = res[ck]
        print(f'{ck:<12} S_auto {r["s_auto"]:9.1f} (Lua {r["s_auto_lua"]:9.1f})  S′ {r["s_prime"]:9.1f}  очередь пуста {r["queue_empty"]}  '
              f'баланс {"ок" if not r["balance"] else r["balance"]}  нарушения {r["violations"]}')


def _replay_one(a):
    stage, ck, c, ticks = a
    work = os.path.join(rd(stage, 'work'), f'{ck}_replay')
    save_in, sha_in, hs = c['init_save'], c['init_sha'], []
    for h in c['hist']:
        out = os.path.join(work, f'r{h["round"]}.zip')
        r = game.round_unit(save_in, sha_in, h['actions'], ticks, out, os.path.join(work, f'w{h["round"]}'), observe_after=False)
        hs.append(r['state_hash'])
        if save_in != c['init_save']: os.remove(save_in)
        save_in, sha_in = out, r['sha']
    shutil.rmtree(work, ignore_errors=True)
    return ck, hs


def replay(stage):
    st = load(stage); cfg = st['cfg']
    jobs = [(stage, ck, c, cfg['round_ticks']) for ck, c in sorted(st['chains'].items(), reverse=True)]   # другой порядок, чем в игре
    with _pool() as pool:
        res = dict(pool.map(_replay_one, jobs))
    out = {}
    for ck, hs in res.items():
        live = st['chains'][ck]['state_hash'][1:]
        out[ck] = dict(live=live, replay=hs, match=live == hs, first_mismatch=next((i + 1 for i, (a, b) in enumerate(zip(live, hs)) if a != b), None))
    W(os.path.join(rd(stage), 'replay.json'), out)
    bad = [ck for ck, v in out.items() if not v['match']]
    print(f'повтор: {len(out) - len(bad)} из {len(out)} цепочек совпали' + (f'; расхождения: {bad}' if bad else ''))


def status(stage):
    st = load(stage); cfg = st['cfg']
    print(json.dumps({k: v for k, v in cfg.items() if k != 'prompt_hashes'}, ensure_ascii=False))
    for ck, c in sorted(st['chains'].items()):
        last = c['hist'][-1] if c['hist'] else {}
        rej = sum(1 for x in last.get('results', []) if not x.get('ok'))
        print(f'{ck:<12} раунд {c["round"]}  построек {last.get("buildings", 0):>3}  отказов {rej:>2}/{len(last.get("results", []))}  '
              f'инв {json.dumps(dict(sorted(c["obs"]["inventory"].items(), key=lambda kv: -kv[1])[:5]), ensure_ascii=False)}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd'); ap.add_argument('stage'); ap.add_argument('files', nargs='*')
    ap.add_argument('--seeds'); ap.add_argument('--parts'); ap.add_argument('--R', type=int); ap.add_argument('--round', type=float); ap.add_argument('--W', type=float)
    a = ap.parse_args()
    if a.cmd == 'init': init(a.stage, [int(x) for x in a.seeds.split(',')], a.parts.split(','), a.R, a.round, a.W)
    elif a.cmd == 'heads': heads(a.stage)
    elif a.cmd == 'ingest': ingest(a.stage, a.files)
    elif a.cmd == 'play': play(a.stage)
    elif a.cmd == 'score': score(a.stage)
    elif a.cmd == 'replay': replay(a.stage)
    elif a.cmd == 'status': status(a.stage)
