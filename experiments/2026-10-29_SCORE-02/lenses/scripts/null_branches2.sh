#!/bin/bash
set -euo pipefail
cd "$1"
for st in main_opus rep_opus main_haiku rep_haiku; do echo '{"flag": false, "why": [], "n": 1}' > dry/ctx_$st.json; done
run () {
  for st in main_opus rep_opus; do
    smp=${st%%_*}
    python3 dry/make_stub.py $smp dry/stub_$1_$st.jsonl $2 $3 $4 0.0 $5 5 0 > /dev/null
    python3 score02.py metrics $st $smp dry/stub_$1_$st.jsonl 5 dry/evals > /dev/null
  done
  python3 analyze_score02.py --dry --stages main_opus,rep_opus > dry/dry_$1.log
  echo "== ветка $1 (a=$2 c=$3 s=$4)"; grep -E "→" dry/dry_$1.log | grep -E "X1o|X2o|X3o"
  python3 - "$1" <<'PY'
import json, sys
for st in ('main_opus', 'rep_opus'):
    E = json.load(open(f'dry/evals/{st}.json'))
    S = E['summary']; A = [c for t in E['judgments'].values() for c, _ in t['agree']]
    print(f"   {st}: точность single {S['single']['acc']:.3f}, уверенность single {S['single']['conf']:.3f}; доля единогласных {sum(c == 1.0 for c in A) / len(A):.3f}")
PY
}
run N2 0.3 0.3 1.0 21
run N3 0.6 0.2 1.5 22
