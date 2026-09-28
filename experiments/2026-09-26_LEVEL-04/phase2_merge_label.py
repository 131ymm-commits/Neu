# LEVEL-04, фаза 2: слияние прогона 27.09 (phase2_out_partial.json) с дозапуском 28.09 (phase2_resume_out.json) и механическая разметка клеток (label.py).
#   python3 phase2_merge_label.py partial   → проверка: разметка одного лишь частичного прогона должна совпасть с phase2_partial_labels.json
#   python3 phase2_merge_label.py            → phase2_out.json, phase2_labels.json, phase2_landscape.json, phase2_status.txt
import json, re, sys, os
from label import label_chain
HERE = os.path.dirname(os.path.abspath(__file__))
TRUTH = {c['id']: c for c in json.load(open('/root/level_secret/l4_phase2.json'))}
cell_of = lambda tag: tag.split(':L')[0]
def merge(partial, resume):
    recs, out = [], dict(partial['out'])
    cells = sorted({cell_of(r['tag']) for r in partial['records']}, key=lambda c: [cell_of(r['tag']) for r in partial['records']].index(c))
    for c in cells:
        rs = [r for r in partial['records'] if cell_of(r['tag']) == c]
        if resume and c in resume['out']:
            ff = next((i for i, r in enumerate(rs) if r.get('n') is None), len(rs))
            recs += rs[:ff] + [r for r in resume['records'] if cell_of(r['tag']) == c]; out[c] = resume['out'][c]
        else: recs += rs
    return dict(out=out, records=recs)
def label_all(data):
    rows, land = [], {}
    for c, o in data['out'].items():
        geno, chain = c.split(':'); rep = geno.endswith('#rep'); g = geno.replace('#rep', '')
        links = [dict(m=r['m'], n=r.get('n'), values=r.get('values')) for r in data['records'] if cell_of(r['tag']) == c]
        incomplete = any(r.get('n') is None for r in data['records'] if cell_of(r['tag']) == c)
        lab, done = label_chain(links, o['final'], TRUTH[chain]['truth'])
        if incomplete: lab = 'нет данных (лимит)'
        rows.append([geno, chain, lab, done, o['calls']])
        land.setdefault(g, []).append(dict(chain=chain, ok=int(lab == 'верно'), label=lab, calls=o['calls'], rep=rep))
    return rows, land
if __name__ == '__main__':
    partial = json.load(open(f'{HERE}/phase2_out_partial.json'))
    if sys.argv[1:] == ['partial']:
        rows, _ = label_all(partial); ref = json.load(open(f'{HERE}/phase2_partial_labels.json'))['rows']
        rows_cmp = [r[:2] + (['отказ с догадкой'] if r[2] == 'нет данных (лимит)' else [r[2]]) + r[3:] for r in rows]
        same = sorted(map(tuple, rows_cmp)) == sorted(map(tuple, ref)); print('совпадает с phase2_partial_labels.json:', same)
        if not same:
            a, b = set(map(tuple, rows_cmp)), set(map(tuple, ref)); print('лишнее:', a - b); print('нет:', b - a)
        sys.exit(0 if same else 1)
    resume = json.load(open(f'{HERE}/phase2_resume_out.json'))
    data = merge(partial, resume); json.dump(data, open(f'{HERE}/phase2_out.json', 'w'), ensure_ascii=False, indent=1)
    rows, land = label_all(data)
    missing = [c for c, o in data['out'].items() if any(r.get('n') is None for r in data['records'] if cell_of(r['tag']) == c)]
    json.dump(dict(rows=rows, missing=missing), open(f'{HERE}/phase2_labels.json', 'w'), ensure_ascii=False, indent=1)
    json.dump(dict(landscape={g: [c for c in v if not c['rep']] for g, v in land.items()}, landscape_with_rep=land, missing=missing), open(f'{HERE}/phase2_landscape.json', 'w'), ensure_ascii=False, indent=1)
    with open(f'{HERE}/phase2_status.txt', 'w') as f:
        f.write('Фаза 2, полная таблица (27.09 + дозапуск 28.09; записи дозапуска помечены полем model в phase2_out.json)\n')
        for r in sorted(rows): f.write(f'{r[0]+":"+r[1]:16s} {r[2]}; шагов {r[3]}; вызовов {r[4]}\n')
    print(open(f'{HERE}/phase2_status.txt').read())
