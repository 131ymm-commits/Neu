# Сохранить итог workflow «council» в docs/council/<имя>.json и .md.
#   python3 tools/council_render.py <result.json> <docs/council/дата_ТЕМА_sessionN> "<заголовок>"
# Понимает и прежний формат (transcript, decision; до 12.10.2026), и упрощённый (proposal, votes с errors).
import json, sys
src, base, title = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(src))
if 'result' in d and isinstance(d['result'], dict): d = d['result']
json.dump(d, open(base + '.json', 'w'), ensure_ascii=False, indent=1)
L = [f'# {title}', f'**Задача:** {d.get("task", "")}', '']
if d.get('proposal'): L += ['## Предложение', '', str(d['proposal']).strip(), '']
if d.get('context'): L += ['## Контекст', '', str(d['context']).strip(), '']
for x in d.get('transcript', []):
    L += [f'## Раунд {x["round"]} — {x["speaker"]}', '', str(x['text']).strip(), '']
if d.get('decision'): L += ['## decision', '', str(d['decision']).strip(), '']
L += ['## status', '', str(d.get('status', '')), '', '## votes', '']
for v in d.get('votes', []):
    L.append(f'- **{v["name"]}: {v["vote"]}.** {v.get("reason", "")}')
    for e in v.get('errors', []) or []: L.append(f'  - ошибка/риск: {e}')
    if v.get('required_change'): L.append(f'  - нужно: {v["required_change"]}')
    L.append('')
open(base + '.md', 'w').write('\n'.join(L))
print(base + '.md', '— статус:', d.get('status'))
