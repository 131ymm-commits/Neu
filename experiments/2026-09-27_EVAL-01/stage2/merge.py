# слить выходы двух частей стадии 2: python3 stage2/merge.py a.json b.json → stage2/out.json
import json, sys, os
out = {}
for p in sys.argv[1:3]:
    d = json.load(open(p)); d = d.get('out', d.get('result', {}).get('out', d))
    for arm, cells in d.items():
        dup = set(out.setdefault(arm, {})) & set(cells); assert not dup, (arm, sorted(dup)[:3])
        out[arm].update(cells)
print({a: len(c) for a, c in out.items()})
json.dump({'out': out}, open(os.path.join(os.path.dirname(__file__), sys.argv[3] if len(sys.argv) > 3 else 'out.json'), 'w'), ensure_ascii=False)
