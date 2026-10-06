# Сводчик ветви U: python3 make_u_writer.py → writer_U.js (после L3p2 и заморозки S1–S3)
import json
from rules import u_writer_prompt, SCHEMA_RULES
eps = []
for r in ['L1p1', 'L1p2', 'L2p1', 'L2p2', 'L3p1', 'L3p2']:
    for e in json.load(open(f'../rounds/{r}.json'))['episodes']:
        eps.append(dict(id=e['id'].split('|')[0] + ':' + e['task'], task=e['task'], success=e['success'], measure=e['measure'], lessons=e['lessons'], summary=e['summary']))
assert len(eps) == 36, len(eps)
p = u_writer_prompt(eps, {k: open(f'../rules/{k}_final.md').read() for k in ['S1', 'S2', 'S3']})
src = ("export const meta = { name: 'factorio-writer-U', description: 'FACTORIO-01 сводчик ветви U (без предела длины)', phases: [{ title: 'Свод' }] }\n"
       f"const P = {json.dumps(p, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA_RULES)}\nphase('Свод')\nconst r = await agent(P, {{label: 'writer-U', phase: 'Свод', schema: S}})\nreturn {{out: r}}\n")
open('writer_U.js', 'w').write(src); print(len(p), 'символов промпта')
