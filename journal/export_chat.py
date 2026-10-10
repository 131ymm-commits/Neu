"""Выгружает чат сессии Claude Code в markdown: реплики человека и текстовые ответы Claude.
Вызовы инструментов показаны одной строкой (что делалось), их выводы и системные вставки не включаются.

  python3 journal/export_chat.py <transcript.jsonl> <журнал.md> [ссылка или подпись сессии]

Реплики человека, присланные во время хода Claude (в транскрипте — вложения queued_command), включаются; отчёты
подагентов («Another Claude session sent a message») подписаны как отчёты, не как слова человека (ERRORS № 99)."""
import json, sys, re
src, dst = sys.argv[1], sys.argv[2]
session = sys.argv[3] if len(sys.argv) > 3 else 'не указана'
out = [f'# Журнал чата сессии\n\nСессия: {session}\n'
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
    a = j.get('attachment') or {}
    if t == 'attachment' and a.get('type') == 'queued_command' and (a.get('origin') or {}).get('kind') == 'human':
        pr = a.get('prompt')                            # реплика человека, присланная во время хода Claude
        if isinstance(pr, list):
            imgs = sum(1 for x in pr if isinstance(x, dict) and x.get('type') == 'image')
            pr = '\n'.join(x.get('text', '') for x in pr if isinstance(x, dict) and x.get('type') == 'text')
            pr = (pr + (f'\n\n[снимков экрана: {imgs}]' if imgs else '')).strip()
        if isinstance(pr, str) and pr.strip():
            out.append(f'\n---\n\n## Человек (во время хода Claude) · {ts}\n\n{pr.strip()[:4000]}\n')
        continue
    if t == 'user':
        if isinstance(c, str): txt = clean(c)
        elif isinstance(c, list): txt = clean('\n'.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text'))
        else: txt = ''
        if txt.startswith('Stop hook feedback') or txt.startswith('[SYSTEM NOTIFICATION') or txt.startswith('<system-reminder>'): continue  # служебные сообщения среды, не реплики человека
        if txt and '<task-notification>' in txt:
            m = re.search(r'<summary>(.*?)</summary>', txt, re.S)
            out.append(f'\n- _событие среды (не человек): {(m.group(1) if m else "фоновая задача").strip()[:200]}_\n'); continue
        if txt.startswith('Stop hook feedback'):
            out.append(f'\n---\n\n## Проверка среды (stop hook, не человек) · {ts}\n\n{txt[:800]}\n'); continue
        if txt.startswith('# Workflow authoring reference') or txt.startswith('<skill-format>'):
            out.append('\n- _среда загрузила справку по Workflow (не человек)_\n'); continue
        if txt.startswith('Another Claude session sent a message'):
            if len(txt) > 4000: txt = txt[:3000] + f'\n\n[… отчёт сокращён, всего {len(txt)} символов …]'
            out.append(f'\n---\n\n## Отчёт подагента (не человек) · {ts}\n\n{txt}\n'); continue
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
