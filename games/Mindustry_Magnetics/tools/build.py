# Сборка мода из spec.py: content/*.json, bundles, sprites, mod.hjson, архив.
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import spec, paint
ROOT = os.path.join(HERE, '..'); M = os.path.join(ROOT, 'magnetics')
VERSION = '1.0.0'
shutil.rmtree(M, ignore_errors=True)
for p in ('content/items', 'content/blocks', 'content/units', 'bundles', 'sprites/items', 'sprites/blocks', 'sprites/units'): os.makedirs(os.path.join(M, p))
def W(p, o): open(os.path.join(M, p), 'w').write(json.dumps(o, ensure_ascii=False, indent=1))
open(os.path.join(M, 'mod.hjson'), 'w').write(f'''name: "magnetics"
displayName: "Magnetics"
author: "Claude (Neu)"
description: "Магнитная эра для Серпуло: 5 предметов, 30 построек, 3 летающих юнита — от ферритовых стен до рельсотрона и реактора потока. Все модели нарисованы заново.\\nA magnetic era for Serpulo: 5 items, 30 buildings, 3 aircraft."
version: "{VERSION}"
minGameVersion: 146
''')
L = {'': [], '_ru': [], '_de': []}
def bundle(kind, name, ru, en, de):
    L[''].append(f'{kind}.magnetics-{name}.name = {en[0]}'); L[''].append(f'{kind}.magnetics-{name}.description = {en[1]}')
    L['_ru'].append(f'{kind}.magnetics-{name}.name = {ru[0]}'); L['_ru'].append(f'{kind}.magnetics-{name}.description = {ru[1]}')
    L['_de'].append(f'{kind}.magnetics-{name}.name = {de}')
for n, v in spec.ITEMS.items():
    W(f'content/items/{n}.json', dict(color=v['color'], cost=v['cost'], research=v['research'])); bundle('item', n, v['ru'], v['en'], v['de'])
    paint.item(n).save(os.path.join(M, 'sprites/items', n + '.png'))
for n, b in spec.B.items():
    W(f'content/blocks/{n}.json', b['j']); bundle('block', n, b['ru'], b['en'], b['de'])
    if b['art'] == 'conveyor':
        for a in range(5):
            for f in range(4): paint.conveyor(a, f).save(os.path.join(M, 'sprites/blocks', f'{n}-{a}-{f}.png'))
        continue
    im, extra = paint.art_block(b['art'], b['j'].get('size', 1))
    im.save(os.path.join(M, 'sprites/blocks', n + '.png'))
    for suf, e in extra.items(): e.save(os.path.join(M, 'sprites/blocks', n + suf + '.png'))
for n, u in spec.UNITS.items():
    j = {k: v for k, v in u.items() if k not in ('ru', 'en', 'de', 'art', 'plan')}
    j.update(type='flying', flying=True, research='magnet-factory', requirements=dict(block='magnetics-magnet-factory', time=u['plan']['time'], requirements=u['plan']['req']))
    W(f'content/units/{n}.json', j); bundle('unit', n, u['ru'], u['en'], u['de'])
    im, cell = paint.unit(u['art']); im.save(os.path.join(M, 'sprites/units', n + '.png')); cell.save(os.path.join(M, 'sprites/units', n + '-cell.png'))
for suf, lines in L.items(): open(os.path.join(M, 'bundles', f'bundle{suf}.properties'), 'w').write('\n'.join(lines) + '\n')
z = os.path.join(ROOT, 'Magnetics.zip'); os.path.exists(z) and os.remove(z)
shutil.make_archive(z[:-4], 'zip', M)
print('предметов', len(spec.ITEMS), 'построек', len(spec.B), 'юнитов', len(spec.UNITS), 'спрайтов', sum(len(f) for _, _, f in os.walk(os.path.join(M, 'sprites'))))
