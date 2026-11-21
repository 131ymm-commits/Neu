#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: факты запечатывания голов-переводчиков — как в LINUX-01 (harness/sealing_facts.py там же; tools/audit_heads.py
читает журналы workflow, а не вызовы claude -p). Новое: фаза (translations/<фаза>/<голова>/<модуль>_r<k>.json) и повтор.
По каждому вызову — факты запечатывания: хеш поручения совпадает с закоммиченным prompts/<модуль>.md (фазы pilot2 и test — prompts/test/<модуль>.md); флаг инструментов
--tools ""; папка вызова вне репозитория; модель ответа — заказанная. Отдельно — исход (в запечатывание не входит): ответ без
ошибки, код извлечён, файл .rs на месте; отказ площадки (текст «safeguards flagged») помечается refused.
Плюс факты среды на момент записи: папки вызовов (через запятую) пусты, пользовательского ~/.claude/CLAUDE.md нет.
  python3 harness/sealing_facts.py SEALED_CWD PHASE OUT.json"""
import glob
import hashlib
import json
import os
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(a):
    cwd, phase, dst = a[0], a[1], a[2]
    rows, ok_all = [], True
    for f in sorted(glob.glob(os.path.join(X, 'translations', phase, '*', '*.json'))):
        r = json.load(open(f, encoding='utf-8'))
        mod = r['module']
        sha = hashlib.sha256(open(os.path.join(X, 'prompts', *(['test'] if phase != 'pilot' else []), f'{mod}.md'), 'rb').read()).hexdigest()
        seal = dict(prompt_matches_committed=r.get('prompt_sha256') == sha,
                    tools_flag_empty=r.get('tools_flag') == '--tools ""',
                    cwd_outside_repo=bool(r.get('cwd_outside_repo')),
                    model_is_target=r.get('models_used') == [r.get('model_target')])
        outcome = dict(returncode_zero=r.get('returncode') == 0,
                       not_error=r.get('is_error') is False,
                       code_extracted=bool(r.get('code_extracted')),
                       rs_exists=os.path.exists(f[:-5] + '.rs'),
                       refused='safeguards flagged' in (r.get('result') or ''))
        row = dict(head=r['head'], module=mod, rep=r.get('rep'), file=os.path.relpath(f, X), **seal, sealed=all(seal.values()),
                   **outcome, translation=all(v for k, v in outcome.items() if k != 'refused'))
        ok_all &= row['sealed']
        rows.append(row)
    dirs = cwd.split(',')
    env = dict(sealed_cwd_entries={os.path.basename(d): sorted(os.listdir(d)) if os.path.isdir(d) else None for d in dirs},
               user_claude_md_exists=os.path.exists(os.path.expanduser('~/.claude/CLAUDE.md')))
    env['ok'] = all(v == [] for v in env['sealed_cwd_entries'].values()) and not env['user_claude_md_exists']
    res = dict(phase=phase, n_calls=len(rows), n_translations=sum(r['translation'] for r in rows), n_refused=sum(r['refused'] for r in rows),
               all_sealed=ok_all and env['ok'], env=env, rows=rows)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вызовов', len(rows), '| переводов', res['n_translations'], '| отказов площадки', res['n_refused'], '| запечатаны все',
          res['all_sealed'], '| среда', env)
    for r in rows:
        if not r['sealed']:
            print('  НЕ ЗАПЕЧАТАН:', r)
        elif not r['translation']:
            print('  БЕЗ ПЕРЕВОДА:', r['head'], r['module'], 'r%s' % r['rep'], '| отказ площадки' if r['refused'] else '')
    return 0 if res['all_sealed'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
