#!/bin/bash
# Ветки-нули поверх текущего кода SCORE-02 (в копии опыта, не в репозитории): заглушка → metrics → analyze --dry.
set -euo pipefail
cd "$1"
for st in main_opus rep_opus main_haiku rep_haiku; do echo '{"flag": false, "why": [], "n": 1}' > dry/ctx_$st.json; done
run () {
  for st in main_opus rep_opus main_haiku rep_haiku; do
    smp=${st%%_*}
    python3 dry/make_stub.py $smp dry/stub_$1_$st.jsonl $2 $3 $4 $5 $6 5 0 > /dev/null
    python3 score02.py metrics $st $smp dry/stub_$1_$st.jsonl 5 dry/evals > /dev/null
  done
  python3 analyze_score02.py --dry > dry/dry_$1.log
  cp dry/analysis_score02.json dry/analysis_$1.json
  echo "== ветка $1 (a=$2 c=$3 s=$4)"; grep -E "→|статус" dry/dry_$1.log | grep -E "X1o|X2|статус"
}
run N0 0.3 1.0 0.0 0.0 11
run N1 0.3 1.0 0.35 0.0 12
