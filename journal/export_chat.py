"""Выгружает чат сессии Claude Code в markdown: реплики человека и текстовые ответы Claude.
Вызовы инструментов показаны одной строкой (что делалось), их выводы и системные вставки не включаются."""
import json, sys, re
src, dst = sys.argv[1], sys.argv[2]
out = ['# Журнал чата сессии\n\nСессия: https://claude.ai/code/session_01EAUcgUVu3BhYQ16NUm8BDT\n'
       'Формат: реплики человека — полностью (длинные вставки сокращены до начала), ответы Claude — полностью, '
       'действия — одной строкой. Выводы инструментов и служебные сообщения среды не включены.\n']
def clean(t):
    t = re.sub(r'<system-reminder>.*?</system-reminder>', '', t, flags=re.S)
    t = re.sub(r'<command-[a-z-]+>.*?</command-[a-z-]+>', '', t, flags=re.S)
    t = re.sub(r'<local-command-[a-z-]+>.*?</local-command-[a-z-]+>', '', t, flags=re.S)
    return t.strip()
last_ts = None
for line in open(src):
    try: j = json.loads(line)
    except Exception: continue
    t, msg, ts = j.get('type'), j.get('message') or {}, (j.get('timestamp') or '')[:16].replace('T', ' ')
    c = msg.get('content')
    if t == 'user':
        if isinstance(c, str): txt = clean(c)
        elif isinstance(c, list): txt = clean('\n'.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text'))
        else: txt = ''
        if not txt or 'task-notification' in txt or txt.startswith('Stop hook feedback') and False: pass
        if txt and '<task-notification>' in txt:
            m = re.search(r'<summary>(.*?)</summary>', txt, re.S)
            out.append(f'\n- _событие среды (не человек): {(m.group(1) if m else "фоновая задача").strip()[:200]}_\n'); continue
        if txt.startswith('Stop hook feedback'):
            out.append(f'\n---\n\n## Проверка среды (stop hook, не человек) · {ts}\n\n{txt[:800]}\n'); continue
        if txt.startswith('# Workflow authoring reference') or txt.startswith('<skill-format>'):
            out.append('\n- _среда загрузила справку по Workflow (не человек)_\n'); continue
        if txt:
            if len(txt) > 4000: txt = txt[:1500] + f'\n\n[… вставка сокращена, всего {len(txt)} символов …]'
            out.append(f'\n---\n\n## Человек · {ts}\n\n{txt}\n')
    elif t == 'assistant' and isinstance(c, list):
        for x in c:
            if x.get('type') == 'text' and x.get('text', '').strip():
                out.append(f'\n**Claude · {ts}**\n\n{x["text"].strip()}\n')
            elif x.get('type') == 'tool_use':
                inp = x.get('input', {})
                d = inp.get('description') or inp.get('subject') or inp.get('query') or inp.get('file_path') or inp.get('name') or ''
                out.append(f'- _действие: {x.get("name")} — {str(d)[:160]}_\n')
open(dst, 'w').write(''.join(out))
print(len(out), 'blocks')
