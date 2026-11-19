#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-01: факты запечатывания голов-переводчиков (вместо tools/audit_heads.py, который читает журналы workflow, а не
вызовы claude -p). По каждому переводу: хеш поручения совпадает с закоммиченным prompts/<модуль>.md; флаг инструментов
--tools ""; папка вызова вне репозитория; ответ без ошибки; модель ответа — заказанная; код извлечён.
Плюс факты среды на момент записи: папка вызова пуста, пользовательского ~/.claude/CLAUDE.md нет.
  python3 harness/sealing_facts.py SEALED_CWD OUT.json"""
import glob
import hashlib
import json
import os
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(a):
    cwd, dst = a[0], a[1]
    rows, ok_all = [], True
    for f in sorted(glob.glob(os.path.join(X, 'translations', '*', '*.json'))):
        r = json.load(open(f, encoding='utf-8'))
        mod = r['module']
        sha = hashlib.sha256(open(os.path.join(X, 'prompts', f'{mod}.md'), 'rb').read()).hexdigest()
        row = dict(head=r['head'], module=mod,
                   prompt_matches_committed=r.get('prompt_sha256') == sha,
                   tools_flag_empty=r.get('tools_flag') == '--tools ""',
                   cwd_outside_repo=bool(r.get('cwd_outside_repo')),
                   returncode_zero=r.get('returncode') == 0,
                   not_error=r.get('is_error') is False,
                   model_is_target=r.get('models_used') == [r.get('model_target')],
                   code_extracted=bool(r.get('code_extracted')),
                   rs_exists=os.path.exists(f[:-5] + '.rs'))
        row['ok'] = all(v for k, v in row.items() if k not in ('head', 'module'))
        ok_all &= row['ok']
        rows.append(row)
    env = dict(sealed_cwd_entries=sorted(os.listdir(cwd)) if os.path.isdir(cwd) else None,
               user_claude_md_exists=os.path.exists(os.path.expanduser('~/.claude/CLAUDE.md')))
    env['ok'] = env['sealed_cwd_entries'] == [] and not env['user_claude_md_exists']
    res = dict(n=len(rows), all_ok=ok_all and env['ok'], env=env, rows=rows)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('переводов', len(rows), '| все проверки', res['all_ok'], '| среда', env)
    for r in rows:
        if not r['ok']:
            print('  НЕ ПРОШЛО:', r)
    return 0 if res['all_ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
