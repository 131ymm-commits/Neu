# PRECOND-01: хеши для PREREG — матрица плана, вступления 64 сочетаний и опорных клеток, код и сиды.
#   python3 prereg_hashes.py  →  prereg_hashes.json
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import harness_precond as HP, prompts_precond as PP  # noqa: E402
sha = lambda b: hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()
def preamble(on):   # вступление (инструкции предусловия) — до первой пустой строки; правила и кандидаты к нему не относятся
    return PP.compose(set(on), '<ПРАВИЛА>', [dict(plan={}, claim=0, note='')] * 8)[0].split('\n\n')[0]
out = dict(design64=sha(json.dumps([HP.CELLS[c] for c in HP.CELLS], ensure_ascii=False)),
           preambles={c: sha(preamble(on)) for c, on in HP.CELLS.items()} | {c: sha(preamble(on)) for c, (on, eff) in HP.EXTRA.items()},
           files={})
FILES = ['harness_precond.py', 'analyze_precond.py', 'prompts_precond.py', 'dryrun_precond_main.py', 'run_precond.sh', 'checkin_precond.sh', 'prereg_hashes.py',
         'seeds_open.json', 'seeds_val.json', 'requirements.txt', 'run/precond_medium.json', 'run/precond_high.json',
         '../2026-10-07_SELECT-01/sim.py', '../2026-10-07_SELECT-01/prompts.py', '../2026-10-07_SELECT-01/analyze.py', '../../tools/run_sealed2.py']
for f in FILES:                                                    # совет 38, К3: нет файла — регистрировать нельзя
    assert os.path.exists(f'{HERE}/{f}'), f'нет файла {f}'
    out['files'][f] = sha(open(f'{HERE}/{f}', 'rb').read())
json.dump(out, open(f'{HERE}/prereg_hashes.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out['files'], ensure_ascii=False, indent=1)); print('design64', out['design64'][:16])
