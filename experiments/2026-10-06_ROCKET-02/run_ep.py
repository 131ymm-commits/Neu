# Эпизод кампании ROCKET-02: begin в демоне + workflow одной головы. python3 run_ep.py <ep> <role> [max_steps]
import json, sys
from campaign_prompt import prompt, SCHEMA, ROLES
from orch import send
SLOT = 6
ep, role = sys.argv[1], sys.argv[2]; ms = int(sys.argv[3]) if len(sys.argv) > 3 else 40
print(send(SLOT, dict(cmd='begin', ep=ep, max_steps=ms)))
p = prompt(SLOT, ep, ROLES[role], ms)
src = (f"export const meta = {{ name: 'rocket2-{ep}', description: 'ROCKET-02 эпизод {ep} ({role})', phases: [{{ title: 'Эпизод' }}] }}\n"
       f"const P = {json.dumps(p, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA)}\nphase('Эпизод')\nconst r = await agent(P, {{label: '{ep}', phase: 'Эпизод', schema: S}})\nreturn {{out: r}}\n")
open(f'ep_{ep}.js', 'w').write(src); print('ok', ep)
