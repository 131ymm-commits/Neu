# Сводчик линии: python3 make_writer.py <line> <pass> <prev_rules_file|-> → writer_<line>_p<pass>.js
import json, sys
from rules import writer_prompt, SCHEMA_RULES
line, ps, prev = sys.argv[1], int(sys.argv[2]), sys.argv[3]
R = json.load(open(f'../rounds/{line}p{ps}.json'))
eps = [dict(id=e['id'].split('|')[0] + ':' + e['task'], task=e['task'], success=e['success'], measure=e['measure'], lessons=e['lessons'], summary=e['summary']) for e in R['episodes']]
p = writer_prompt(open(prev).read() if prev != '-' else None, eps)
src = (f"export const meta = {{ name: 'factorio-writer-{line}-p{ps}', description: 'FACTORIO-01 сводчик правил линии {line}, проход {ps}', phases: [{{ title: 'Свод' }}] }}\n"
       f"const P = {json.dumps(p, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA_RULES)}\nphase('Свод')\nconst r = await agent(P, {{label: 'writer-{line}-p{ps}', phase: 'Свод', schema: S}})\nreturn {{out: r}}\n")
open(f'writer_{line}_p{ps}.js', 'w').write(src); print(len(p), 'символов промпта')
