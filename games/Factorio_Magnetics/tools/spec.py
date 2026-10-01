"""Magnetics для Factorio 2.0.77 — единственный источник чисел (design/FINAL_SPEC.md, разделы 2–5, 7, 9).
Отсюда генерируются: magnetics/prototypes/spec_data.lua (числа для прототипов), locale/{en,ru,de}/magnetics.cfg,
tools/magnetics-tests/expected.lua (ожидания статических тестов). Число набирается один раз — здесь.
Запуск: python3 tools/spec.py"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD = os.path.join(ROOT, 'magnetics')
VERSION = '1.0.0'
P = 'magnetics-'

def I(name, amount): return {'type': 'item', 'name': name, 'amount': amount}
def F(name, amount): return {'type': 'fluid', 'name': name, 'amount': amount}
def M(n): return P + n

# ---------------------------------------------------------------- 2. предметы и жидкости
# en, ru, de — имя; den, dru — описание (de-описание не задаём: игра берёт английское)
ITEMS = {
  M('ferrite'): dict(stack=100, order='a[ferrite]', en='Ferrite', ru='Феррит', de='Ferrit',
      den='Iron ore sintered with stone into a magnetic ceramic. The core of every coil.',
      dru='Железная руда, спечённая с камнем в магнитную керамику. Сердечник каждой катушки.'),
  M('coil'): dict(stack=200, order='b[coil]', en='Coil', ru='Катушка', de='Spule',
      den='Copper cable wound on a ferrite core. The universal part of magnetic machines.',
      dru='Медный кабель на ферритовом сердечнике. Универсальная деталь магнитных машин.'),
  M('magnet-alloy'): dict(stack=100, order='c[magnet-alloy]', en='Magnet alloy', ru='Магнитный сплав', de='Magnetlegierung',
      den='Steel, ferrite and copper fused by eddy currents. The base of blue-tier magnetic machines.',
      dru='Сталь, феррит и медь, сплавленные вихревыми токами. Основа магнитных машин синего уровня.'),
  M('superconducting-cable'): dict(stack=200, order='d[superconducting-cable]', auto_recycle=False,
      en='Superconducting cable', ru='Сверхпроводящий кабель', de='Supraleitendes Kabel',
      den='Magnet alloy in a plastic sheath, frozen by liquid nitrogen. Carries current without loss.',
      dru='Магнитный сплав в пластиковой оболочке, замороженный жидким азотом. Проводит ток без потерь.'),
  M('flux-crystal-uncharged'): dict(stack=20, order='e[flux-crystal-uncharged]', auto_recycle=False,
      en='Uncharged flux crystal', ru='Незаряженный кристалл потока', de='Ungeladener Flusskristall',
      den='Charge it in a flux resonator. The flux dynamo returns it after use.',
      dru='Заряжается в резонаторе потока. Динамо-машина потока возвращает его после разрядки.'),
  M('flux-crystal'): dict(stack=20, order='f[flux-crystal]', auto_recycle=False,
      fuel_category=M('flux'), fuel_value='100MJ', burnt_result=M('flux-crystal-uncharged'),
      en='Flux crystal', ru='Кристалл потока', de='Flusskristall',
      den='A charged crystal holding 100 MJ. Fuel for the flux dynamo and the core of flux rail slugs.',
      dru='Заряженный кристалл на 100 МДж. Топливо динамо-машины потока и сердечник рельсовой болванки потока.'),
}
# боеприпасы: урон и поведение собираются в Lua (prototypes/items.lua) из этих чисел
AMMO = {
  M('ferrite-slug'): dict(category=M('slug'), magazine=10, stack=100, order='m[magnetics]-a[ferrite-slug]',
      projectile=M('ferrite-slug-projectile'), damage=20, piercing=30, tint='6E5A62', speed=1, max_range=24,
      en='Ferrite slugs', ru='Ферритовые болванки', de='Ferritbolzen',
      den='Coilgun ammo. A slug pierces small enemies standing in a line.',
      dru='Боеприпас катушечника. Болванка пробивает мелких врагов, стоящих на одной линии.'),
  M('magnet-slug'): dict(category=M('slug'), magazine=10, stack=100, order='m[magnetics]-b[magnet-slug]',
      projectile=M('magnet-slug-projectile'), damage=32, piercing=150, tint='6D86C9', speed=1, max_range=24,
      en='Magnet slugs', ru='Магнитные болванки', de='Magnetbolzen',
      den='Heavy coilgun ammo that keeps its punch against armour.',
      dru='Тяжёлый боеприпас катушечника, не теряющий силы против брони.'),
  M('gauss-slug'): dict(category=M('gauss'), magazine=4, stack=50, order='m[magnetics]-c[gauss-slug]',
      projectile=M('gauss-slug-projectile'), damage=90, piercing=400, tint='9FB4FF', speed=1.5, max_range=34,
      en='Gauss slugs', ru='Болванки Гаусса', de='Gauß-Bolzen',
      den='Gauss turret ammo: one heavy hit that ignores most armour.',
      dru='Боеприпас пушки Гаусса: один тяжёлый удар, почти не замечающий брони.'),
  M('rail-slug'): dict(category=M('rail'), magazine=1, stack=20, order='m[magnetics]-d[rail-slug]',
      line=dict(range=34.60625, width=1.5, damage=[(1200, 'physical')]),  # 36 от центра турели: линия начинается у дула (1.39375), PILOT-8
      en='Rail slug', ru='Рельсовая болванка', de='Schienenbolzen',
      den='Rail cannon ammo. Hits every enemy on a 36-tile line.',
      dru='Боеприпас рельсовой пушки. Поражает всех врагов на линии длиной 36 клеток.'),
  M('flux-rail-slug'): dict(category=M('rail'), magazine=3, stack=10, order='m[magnetics]-e[flux-rail-slug]',
      line=dict(range=34.60625, width=2, damage=[(1800, 'physical'), (600, 'electric')]),
      en='Flux rail slug', ru='Рельсовая болванка потока', de='Fluss-Schienenbolzen',
      den='A rail slug around a charged flux crystal: three shots with physical and electric damage.',
      dru='Рельсовая болванка вокруг заряженного кристалла: три выстрела с физическим и электрическим уроном.'),
}
AMMO_CATEGORIES = {
  M('slug'): dict(bonus_gui_order='l-m1', en='Coilgun slugs', ru='Болванки катушечника', de='Spulenbolzen'),
  M('gauss'): dict(bonus_gui_order='l-m2', en='Gauss slugs', ru='Болванки Гаусса', de='Gauß-Bolzen'),
  M('rail'): dict(bonus_gui_order='l-m3', en='Rail slugs', ru='Рельсовые болванки', de='Schienenbolzen'),
}
FUEL_CATEGORIES = {M('flux'): dict(en='Flux', ru='Поток', de='Fluss')}
RECIPE_CATEGORIES = [M(x) for x in ('sintering', 'induction', 'winding', 'cryogenics', 'resonance', 'separation')]
FLUIDS = {
  M('ferrofluid'): dict(default_temperature=25, base_color=[0.07, 0.06, 0.09], flow_color=[0.48, 0.36, 0.72],
      order='a[fluid]-b[oil]-f[magnetics-ferrofluid]',
      en='Ferrofluid', ru='Феррожидкость', de='Ferrofluid',
      den='Ferrite suspended in light oil. The lubricant of maglev belts and the bath of the magnetic separator.',
      dru='Феррит во взвеси лёгкой нефти. Смазка маглев-конвейеров и ванна магнитного сепаратора.'),
  M('liquid-nitrogen'): dict(default_temperature=-196, base_color=[0.75, 0.90, 1.00], flow_color=[0.94, 0.98, 1.00],
      order='a[fluid]-z[magnetics-liquid-nitrogen]',
      en='Liquid nitrogen', ru='Жидкий азот', de='Flüssigstickstoff',
      den='Liquefied from air in the cryo chamber. Cools superconductors.',
      dru='Сжижается из воздуха в криокамере. Охлаждает сверхпроводники.'),
}

# ---------------------------------------------------------------- 3. рецепты
# TOP- в имени ингредиента: express-* без Space Age, turbo-* с ним (разрешается в Lua)
RECIPES = {
  # 3.1 промежуточные
  M('ferrite'): dict(category=M('sintering'), ing=[I('iron-ore', 1), I('stone', 1)], res=[I(M('ferrite'), 1)], energy=3.2, prod=True, ar=False),
  M('coil'): dict(category=M('winding'), ing=[I(M('ferrite'), 1), I('copper-cable', 4)], res=[I(M('coil'), 1)], energy=1.6, prod=True, ar=True),
  M('magnet-alloy'): dict(category=M('induction'), ing=[I('steel-plate', 1), I(M('ferrite'), 2), I('copper-plate', 1)], res=[I(M('magnet-alloy'), 1)], energy=6.4, prod=True, ar=False),
  M('ferrofluid'): dict(category='chemistry', ing=[I(M('ferrite'), 1), F('light-oil', 10)], res=[F(M('ferrofluid'), 10)], energy=1, prod=True, ar=False,
      tint=dict(primary=[0.07, 0.06, 0.09], secondary=[0.48, 0.36, 0.72], tertiary=[0.30, 0.25, 0.40], quaternary=[0.15, 0.10, 0.20])),
  M('liquid-nitrogen'): dict(category=M('cryogenics'), ing=[], res=[F(M('liquid-nitrogen'), 50)], energy=2, prod=False, ar=False, own_icon=True,
      subgroup='fluid-recipes', order='z[magnetics-liquid-nitrogen]',
      tint=dict(primary=[0.75, 0.90, 1.00], secondary=[0.94, 0.98, 1.00], tertiary=[0.60, 0.80, 0.95], quaternary=[0.85, 0.95, 1.00]),
      en='Air liquefaction', ru='Сжижение воздуха', de='Luftverflüssigung'),
  M('superconducting-cable'): dict(category=M('cryogenics'), ing=[I(M('magnet-alloy'), 1), I('copper-cable', 6), I('plastic-bar', 1), F(M('liquid-nitrogen'), 20)],
      res=[I(M('superconducting-cable'), 2)], energy=10, prod=True, ar=False),
  M('flux-crystal-growth'): dict(category=M('cryogenics'), ing=[I(M('superconducting-cable'), 2), I('processing-unit', 1), I('uranium-238', 1), F(M('ferrofluid'), 20), F(M('liquid-nitrogen'), 50)],
      res=[I(M('flux-crystal-uncharged'), 1)], energy=20, prod=True, ar=False, allow_quality=False, own_icon=True,
      subgroup=M('intermediate'), order='z-a', en='Flux crystal growth', ru='Выращивание кристалла потока', de='Flusskristallzucht'),
  M('flux-crystal-charging'): dict(category=M('resonance'), ing=[I(M('flux-crystal-uncharged'), 1)], res=[I(M('flux-crystal'), 1)], energy=25, prod=False, ar=False,
      allow_quality=False, own_icon=True, subgroup=M('intermediate'), order='z-b', en='Flux crystal charging', ru='Зарядка кристалла потока', de='Flusskristall laden'),
  M('stone-separation'): dict(category=M('separation'), ing=[I('stone', 10), F(M('ferrofluid'), 5)],
      res=[I('iron-ore', 2), dict(type='item', name='copper-ore', amount=1, probability=0.5)], energy=5, prod=True, ar=False, own_icon=True,
      subgroup=M('intermediate'), order='z-c', sa_magnetic_field_min=50,
      en='Magnetic stone separation', ru='Магнитная сепарация камня', de='Magnetische Gesteinstrennung'),
  # 3.2 боеприпасы
  M('ferrite-slug'): dict(category='crafting', ing=[I(M('ferrite'), 6), I('copper-plate', 2)], res=[I(M('ferrite-slug'), 1)], energy=3, prod=False, ar=True),
  M('magnet-slug'): dict(category='crafting', ing=[I(M('ferrite-slug'), 1), I(M('magnet-alloy'), 1)], res=[I(M('magnet-slug'), 1)], energy=5, prod=False, ar=True),
  M('gauss-slug'): dict(category='crafting', ing=[I(M('magnet-alloy'), 2), I('steel-plate', 1)], res=[I(M('gauss-slug'), 1)], energy=6, prod=False, ar=True),
  M('rail-slug'): dict(category='crafting', ing=[I(M('superconducting-cable'), 1), I(M('magnet-alloy'), 2), I('steel-plate', 2)], res=[I(M('rail-slug'), 1)], energy=10, prod=False, ar=True),
  M('flux-rail-slug'): dict(category='crafting', ing=[I(M('rail-slug'), 1), I(M('flux-crystal'), 1)], res=[I(M('flux-rail-slug'), 1)], energy=15, prod=False, ar=False),
}
# 3.3 постройки: (ингредиенты, время, категория, число результатов)
BUILD = {
  'sintering-kiln': ([I('stone-furnace', 1), I('iron-gear-wheel', 2), I('stone-brick', 5)], 2),
  'induction-furnace': ([I('steel-plate', 10), I('advanced-circuit', 5), I('stone-brick', 10), I(M('coil'), 10)], 5),
  'coil-winder': ([I('assembling-machine-2', 1), I(M('ferrite'), 10), I('copper-cable', 20)], 3),
  'cryo-chamber': ([I('chemical-plant', 1), I(M('magnet-alloy'), 10), I(M('coil'), 10), I('pipe', 10)], 5),
  'flux-resonator': ([I('centrifuge', 1), I(M('superconducting-cable'), 50), I('processing-unit', 20)], 10),
  'magnetic-separator': ([I('steel-plate', 10), I(M('magnet-alloy'), 10), I(M('coil'), 20), I('advanced-circuit', 5), I('iron-gear-wheel', 10)], 5),
  'magnetic-drill': ([I('electric-mining-drill', 1), I(M('magnet-alloy'), 5), I(M('coil'), 5), I('advanced-circuit', 2)], 2),
  'maglev-transport-belt': ([I('TOP-transport-belt', 1), I(M('superconducting-cable'), 1), I(M('magnet-alloy'), 1), F(M('ferrofluid'), 20)], 0.5, 'crafting-with-fluid'),
  'maglev-underground-belt': ([I('TOP-underground-belt', 2), I(M('magnet-alloy'), 20), I(M('superconducting-cable'), 10), F(M('ferrofluid'), 40)], 2, 'crafting-with-fluid', 2),
  'maglev-splitter': ([I('TOP-splitter', 1), I(M('superconducting-cable'), 5), I(M('magnet-alloy'), 10), I('processing-unit', 2), F(M('ferrofluid'), 80)], 2, 'crafting-with-fluid'),
  'coil-capacitor': ([I(M('coil'), 5), I('steel-plate', 2), I('electronic-circuit', 2)], 5),
  'superconducting-accumulator': ([I('accumulator', 1), I(M('superconducting-cable'), 10), I(M('magnet-alloy'), 5)], 10),
  'superconducting-pylon': ([I('big-electric-pole', 1), I(M('superconducting-cable'), 2), I('steel-plate', 2)], 1),
  'mhd-generator': ([I('steel-plate', 20), I(M('coil'), 20), I(M('magnet-alloy'), 10), I('advanced-circuit', 10)], 10),
  'flux-dynamo': ([I('steel-plate', 20), I(M('superconducting-cable'), 20), I(M('coil'), 20), I('processing-unit', 10)], 10),
  'geomagnetic-coil': ([I(M('magnet-alloy'), 4), I(M('coil'), 10), I('steel-plate', 5), I('electronic-circuit', 5)], 10),
  'ferrite-wall': ([I('stone-wall', 1), I(M('ferrite'), 2)], 0.5),
  'magnet-wall': ([I(M('ferrite-wall'), 1), I(M('magnet-alloy'), 1), I('steel-plate', 1)], 1),
  'superconducting-wall': ([I(M('magnet-wall'), 1), I(M('superconducting-cable'), 1), I('refined-concrete', 4)], 2),
  'magnet-gate': ([I(M('magnet-wall'), 1), I('steel-plate', 2), I('electronic-circuit', 2)], 0.5),
  'superconducting-gate': ([I(M('magnet-gate'), 1), I(M('superconducting-cable'), 1), I('refined-concrete', 4)], 1),
  'mend-coil': ([I('steel-plate', 10), I(M('coil'), 20), I('repair-pack', 10), I('advanced-circuit', 5)], 10),
  'coilgun-turret': ([I('gun-turret', 1), I(M('coil'), 10), I(M('ferrite'), 10), I('electronic-circuit', 5)], 8),
  'gauss-turret': ([I('steel-plate', 20), I(M('magnet-alloy'), 10), I(M('coil'), 20), I('advanced-circuit', 10)], 20),
  'arc-emitter': ([I('laser-turret', 1), I(M('coil'), 20), I(M('magnet-alloy'), 10)], 20),
  'rail-cannon': ([I('steel-plate', 40), I(M('superconducting-cable'), 20), I(M('coil'), 30), I(M('magnet-alloy'), 20), I('processing-unit', 10)], 30),
}
for n, v in BUILD.items():
    ing, t = v[0], v[1]
    cat = v[2] if len(v) > 2 else 'crafting'
    cnt = v[3] if len(v) > 3 else 1
    RECIPES[M(n)] = dict(category=cat, ing=ing, res=[I(M(n), cnt)], energy=t, prod=False, ar=True)

# ---------------------------------------------------------------- 4. постройки
# kind — ветка кода в Lua; base — ванильный образец; set — поля поверх копии (глубокое слияние таблиц);
# item — стак/подгруппа/порядок предмета; heat — heating_energy под Space Age; cond — лишние surface_conditions под SA
def RES(*rows):
    names = ('physical', 'impact', 'explosion', 'fire', 'acid', 'laser', 'electric')
    out = []
    for nm, r in zip(names, rows):
        if r is None: continue
        out.append({'type': nm, 'decrease': r[0], 'percent': r[1]})
    return out

def es_el(usage, drain=None, pollution=None, **kw):
    d = {'type': 'electric', 'usage_priority': kw.pop('priority', 'secondary-input')}
    if drain is not None: d['drain'] = drain
    if pollution is not None: d['emissions_per_minute'] = {'pollution': pollution}
    d.update(kw); return d

FIVE = ['consumption', 'speed', 'productivity', 'pollution', 'quality']
ENTITIES = {
  # 4.2 производство и добыча
  M('sintering-kiln'): dict(kind='kiln', type='assembling-machine', base_type='furnace', base='stone-furnace', tint=[0.80, 0.62, 0.66], frg=M('sintering-kiln'), hp=200,
      set=dict(crafting_speed=1, energy_usage='90kW', crafting_categories=[M('sintering')], fixed_recipe=M('ferrite'), module_slots=0,
               energy_source={'type': 'burner', 'fuel_categories': ['chemical'], 'effectivity': 1, 'fuel_inventory_size': 1, 'emissions_per_minute': {'pollution': 2}}),
      item=dict(stack=50, subgroup='smelting-machine', order='a[stone-furnace]-m[magnetics-sintering-kiln]'), heat=None, cond=[('pressure', 10)],
      en='Sintering kiln', ru='Спекательная печь', de='Sinterofen',
      den='Burns fuel to sinter iron ore and stone into ferrite.', dru='Сжигает топливо и спекает железную руду с камнем в феррит.'),
  M('induction-furnace'): dict(kind='crafter', type='assembling-machine', base_type='furnace', base='electric-furnace', tint=[0.62, 0.72, 1.00], frg=M('induction-furnace'), hp=350,
      set=dict(crafting_speed=2, energy_usage='240kW', crafting_categories=[M('sintering'), M('induction')], module_slots=2, allowed_effects=FIVE,
               energy_source=es_el('240kW', drain='8kW', pollution=1)),
      item=dict(stack=50, subgroup='smelting-machine', order='c[electric-furnace]-m[magnetics-induction-furnace]'), heat='100kW',
      en='Induction furnace', ru='Индукционная печь', de='Induktionsofen',
      den='Electric furnace for ferrite and magnet alloy.', dru='Электропечь для феррита и магнитного сплава.'),
  M('coil-winder'): dict(kind='crafter', type='assembling-machine', base='assembling-machine-2', tint=[1.00, 0.72, 0.50], frg=M('coil-winder'), hp=350,
      set=dict(crafting_speed=1, energy_usage='150kW', crafting_categories=[M('winding')], module_slots=2, allowed_effects=FIVE,
               energy_source=es_el('150kW', drain='5kW', pollution=3)),
      item=dict(stack=50, subgroup='production-machine', order='m[magnetics]-a[coil-winder]'), heat='100kW',
      en='Coil winder', ru='Намоточный станок', de='Wickelmaschine',
      den='Winds copper cable onto ferrite cores.', dru='Наматывает медный кабель на ферритовые сердечники.'),
  M('cryo-chamber'): dict(kind='crafter', type='assembling-machine', base='chemical-plant', tint=[0.70, 0.95, 1.00], frg=M('cryo-chamber'), hp=350,
      set=dict(crafting_speed=1, energy_usage='300kW', crafting_categories=[M('cryogenics')], module_slots=3, allowed_effects=FIVE,
               energy_source=es_el('300kW', drain='10kW', pollution=3)),
      item=dict(stack=10, subgroup='production-machine', order='m[magnetics]-b[cryo-chamber]'), heat='100kW',
      en='Cryo chamber', ru='Криокамера', de='Kryokammer',
      den='Liquefies nitrogen from air, makes superconducting cable and grows flux crystals.',
      dru='Сжижает азот из воздуха, делает сверхпроводящий кабель и выращивает кристаллы потока.'),
  M('flux-resonator'): dict(kind='crafter', type='assembling-machine', base='centrifuge', tint=[0.82, 0.64, 1.00], frg=M('flux-resonator'), hp=350,
      set=dict(crafting_speed=1, energy_usage='5MW', crafting_categories=[M('resonance')], fixed_recipe=M('flux-crystal-charging'), module_slots=0,
               effect_receiver={'uses_module_effects': False, 'uses_beacon_effects': False, 'uses_surface_effects': False},
               energy_source=es_el('5MW', drain='10kW', pollution=0)),
      item=dict(stack=20, subgroup='production-machine', order='m[magnetics]-c[flux-resonator]'), heat='100kW',
      en='Flux resonator', ru='Резонатор потока', de='Flussresonator',
      den='Charges flux crystals from the grid. A fifth of the energy is lost; modules, beacons and quality do not help.',
      dru='Заряжает кристаллы потока от сети. Пятая часть энергии теряется; модули, маяки и качество не помогают.'),
  M('magnetic-separator'): dict(kind='crafter', type='assembling-machine', base='assembling-machine-3', tint=[0.68, 0.78, 0.88], frg=M('magnetic-separator'), hp=400,
      set=dict(crafting_speed=1, energy_usage='250kW', crafting_categories=[M('separation')], module_slots=2, allowed_effects=FIVE,
               energy_source=es_el('250kW', drain='8.333kW', pollution=4)),
      item=dict(stack=50, subgroup='production-machine', order='m[magnetics]-d[magnetic-separator]'), heat='100kW',
      en='Magnetic separator', ru='Магнитный сепаратор', de='Magnetabscheider',
      den='Separates iron and copper ore from stone in a ferrofluid bath.', dru='Отделяет железную и медную руду от камня в ванне с феррожидкостью.'),
  M('magnetic-drill'): dict(kind='drill', type='mining-drill', base='electric-mining-drill', tint=[0.60, 0.72, 1.00], frg='mining-drill', hp=400,
      set=dict(mining_speed=0.75, energy_usage='150kW', resource_searching_radius=2.49, resource_categories=['basic-solid'], module_slots=3,
               energy_source=es_el('150kW', pollution=15)),
      item=dict(stack=50, subgroup='extraction-machine', order='a[items]-b[electric-mining-drill]-m[magnetics]'), heat='100kW', upgrade_from=['electric-mining-drill'],
      en='Magnetic mining drill', ru='Магнитный бур', de='Magnetbohrer',
      den='Upgrade of the electric mining drill: 50% faster on the same 5×5 area.', dru='Улучшение электробура: на 50% быстрее на той же площади 5×5.'),
  # 4.3 логистика
  M('maglev-transport-belt'): dict(kind='belt', type='transport-belt', base='express-transport-belt', tint=[0.90, 0.62, 1.00], frg='transport-belt', hp=180,
      set=dict(speed=0.15625), item=dict(stack=100, subgroup='belt', order='a[transport-belt]-e[magnetics-maglev]'), heat='10kW',
      upgrade_from=['TOP-transport-belt'],
      en='Maglev belt', ru='Маглев-конвейер', de='Magnetschwebeband',
      den='The fastest belt: 75 items per second.', dru='Самый быстрый конвейер: 75 предметов в секунду.'),
  M('maglev-underground-belt'): dict(kind='belt', type='underground-belt', base='express-underground-belt', tint=[0.90, 0.62, 1.00], frg='transport-belt', hp=180,
      set=dict(speed=0.15625, max_distance=13), item=dict(stack=50, subgroup='belt', order='b[underground-belt]-e[magnetics-maglev]'), heat='250kW',
      upgrade_from=['TOP-underground-belt'],
      en='Maglev underground belt', ru='Подземный маглев-конвейер', de='Unterirdisches Magnetschwebeband',
      den='75 items per second, maximum distance 13.', dru='75 предметов в секунду, наибольшая длина 13.'),
  M('maglev-splitter'): dict(kind='belt', type='splitter', base='express-splitter', tint=[0.90, 0.62, 1.00], frg='transport-belt', hp=200,
      set=dict(speed=0.15625), item=dict(stack=50, subgroup='belt', order='c[splitter]-e[magnetics-maglev]'), heat='40kW',
      upgrade_from=['TOP-splitter'],
      en='Maglev splitter', ru='Маглев-разделитель', de='Magnetschwebe-Splitter',
      den='Splits and merges maglev lanes at 75 items per second.', dru='Делит и сливает потоки маглев-конвейеров, 75 предметов в секунду.'),
  # 4.4 энергия
  M('coil-capacitor'): dict(kind='capacitor', type='accumulator', base='accumulator', tint=[1.00, 0.75, 0.55], frg=M('coil-capacitor'), hp=100,
      set=dict(energy_source={'type': 'electric', 'usage_priority': 'tertiary', 'buffer_capacity': '1MJ', 'input_flow_limit': '1MW', 'output_flow_limit': '1MW'},
               collision_box=[[-0.4, -0.4], [0.4, 0.4]], selection_box=[[-0.5, -0.5], [0.5, 0.5]]),
      item=dict(stack=50, subgroup='energy', order='e[accumulator]-b[magnetics-coil-capacitor]'), heat=None,
      en='Coil capacitor', ru='Катушечный конденсатор', de='Spulenkondensator',
      den='1×1 storage: only 1 MJ, but moves 1 MW. For burst loads such as turrets.',
      dru='Накопитель 1×1: всего 1 МДж, зато отдаёт 1 МВт. Для пиковых нагрузок, например турелей.'),
  M('superconducting-accumulator'): dict(kind='accumulator', type='accumulator', base='accumulator', tint=[0.65, 0.95, 1.00], frg='accumulator', hp=250,
      set=dict(energy_source={'type': 'electric', 'usage_priority': 'tertiary', 'buffer_capacity': '20MJ', 'input_flow_limit': '1.2MW', 'output_flow_limit': '1.2MW'}),
      item=dict(stack=50, subgroup='energy', order='e[accumulator]-c[magnetics-superconducting-accumulator]'), heat=None, upgrade_from=['accumulator'],
      en='Superconducting accumulator', ru='Сверхпроводящий аккумулятор', de='Supraleitender Akkumulator',
      den='Four times the capacity and power of an accumulator on the same 2×2.', dru='Вчетверо больше ёмкости и мощности, чем у аккумулятора, на тех же 2×2.'),
  M('superconducting-pylon'): dict(kind='pole', type='electric-pole', base='big-electric-pole', tint=[0.65, 0.95, 1.00], frg='big-electric-pole', hp=250,
      set=dict(maximum_wire_distance=48, supply_area_distance=2),
      item=dict(stack=50, subgroup='energy-pipe-distribution', order='a[energy]-c[big-electric-pole]-m[magnetics]'), heat=None, upgrade_from=['big-electric-pole'],
      en='Superconducting pylon', ru='Сверхпроводящая опора', de='Supraleitender Mast',
      den='Wire reach 48: a third fewer poles on long lines.', dru='Дальность провода 48: на треть меньше опор на длинных линиях.'),
  M('mhd-generator'): dict(kind='generator', type='burner-generator', base='burner-generator', tint=[1.00, 0.60, 0.45], frg=M('mhd-generator'), hp=400,
      set=dict(max_power_output='5.4MW', burner={'type': 'burner', 'fuel_categories': ['chemical'], 'effectivity': 0.9, 'fuel_inventory_size': 2, 'emissions_per_minute': {'pollution': 100}},
               energy_source={'type': 'electric', 'usage_priority': 'secondary-output'}),
      item=dict(stack=10, subgroup='energy', order='b[steam-power]-m[magnetics-mhd-generator]'), heat='50kW', cond=[('pressure', 10)],
      en='MHD generator', ru='МГД-генератор', de='MHD-Generator',
      den='Turns chemical fuel into 5.4 MW without water. Loses a tenth of the fuel energy.',
      dru='Превращает химическое топливо в 5,4 МВт без воды. Теряет десятую часть энергии топлива.'),
  M('flux-dynamo'): dict(kind='generator', type='burner-generator', base='burner-generator', tint=[0.80, 0.60, 1.00], frg=M('flux-dynamo'), hp=500,
      set=dict(max_power_output='10MW', burner={'type': 'burner', 'fuel_categories': [M('flux')], 'effectivity': 1, 'fuel_inventory_size': 1, 'burnt_inventory_size': 1, 'emissions_per_minute': {'pollution': 0}},
               energy_source={'type': 'electric', 'usage_priority': 'secondary-output'}),
      item=dict(stack=10, subgroup='energy', order='f[nuclear-energy]-m[magnetics-flux-dynamo]'), heat='50kW',
      en='Flux dynamo', ru='Динамо-машина потока', de='Flussdynamo',
      den='Discharges flux crystals: 10 MW with no pollution and no water.', dru='Разряжает кристаллы потока: 10 МВт без загрязнения и без воды.'),
  M('geomagnetic-coil'): dict(kind='geomagnetic', type='solar-panel', base='solar-panel', tint=[0.82, 0.75, 1.00], frg=M('geomagnetic-coil'), hp=200,
      set=dict(production='20kW', solar_coefficient_property='magnetic-field', performance_at_day=1, performance_at_night=1),
      item=dict(stack=50, subgroup='energy', order='d[solar-panel]-m[magnetics-geomagnetic-coil]'), heat=None,
      en='Geomagnetic coil', ru='Геомагнитная катушка', de='Geomagnetische Spule',
      den="Draws power from the planet's magnetic field: a small, constant output by day and night.",
      dru='Берёт энергию из магнитного поля планеты: небольшая постоянная мощность днём и ночью.'),
  # 4.5 стены, ворота, ремонтная катушка
  M('ferrite-wall'): dict(kind='wall', type='wall', base='stone-wall', tint=[0.62, 0.55, 0.60], frg='wall', hp=500,
      set=dict(resistances=RES((3, 25), (45, 60), (10, 30), (0, 100), (0, 80), (0, 70), (0, 30))),
      item=dict(stack=100, subgroup='defensive-structure', order='a[stone-wall]-b[magnetics-ferrite-wall]'), heat=None, upgrade_from=['stone-wall'],
      en='Ferrite wall', ru='Ферритовая стена', de='Ferritwand',
      den='A cheap early upgrade of the stone wall.', dru='Дешёвое раннее улучшение каменной стены.'),
  M('magnet-wall'): dict(kind='wall', type='wall', base='stone-wall', tint=[0.60, 0.70, 1.00], frg='wall', hp=800, thorns=5,
      set=dict(resistances=RES((5, 30), (50, 65), (15, 35), (0, 100), (0, 85), (0, 75), (0, 50))),
      item=dict(stack=100, subgroup='defensive-structure', order='a[stone-wall]-c[magnetics-magnet-wall]'), heat=None, upgrade_from=[M('ferrite-wall')],
      en='Magnet wall', ru='Магнитная стена', de='Magnetwand',
      den='Its field shocks the biters that bite it.', dru='Её поле бьёт током кусающих её жуков.'),
  M('superconducting-wall'): dict(kind='wall', type='wall', base='stone-wall', tint=[0.70, 0.95, 1.00], frg='wall', hp=1500, thorns=10,
      set=dict(resistances=RES((8, 35), (60, 70), (20, 40), (0, 100), (0, 90), (0, 100), (0, 100))),
      item=dict(stack=100, subgroup='defensive-structure', order='a[stone-wall]-d[magnetics-superconducting-wall]'), heat=None, upgrade_from=[M('magnet-wall')],
      en='Superconducting wall', ru='Сверхпроводящая стена', de='Supraleitende Wand',
      den='Absorbs lasers and lightning and shocks attackers.', dru='Поглощает лазеры и молнии и бьёт током нападающих.'),
  M('magnet-gate'): dict(kind='gate', type='gate', base='gate', tint=[0.60, 0.70, 1.00], frg='wall', hp=800, thorns=5,
      set=dict(resistances=RES((5, 30), (50, 65), (15, 35), (0, 100), (0, 85), (0, 75), (0, 50))),
      item=dict(stack=50, subgroup='defensive-structure', order='a[wall]-c[magnetics-magnet-gate]'), heat=None, upgrade_from=['gate'],
      en='Magnet gate', ru='Магнитные ворота', de='Magnettor',
      den='A gate as strong as a magnet wall.', dru='Ворота, прочные, как магнитная стена.'),
  M('superconducting-gate'): dict(kind='gate', type='gate', base='gate', tint=[0.70, 0.95, 1.00], frg='wall', hp=1500, thorns=10,
      set=dict(resistances=RES((8, 35), (60, 70), (20, 40), (0, 100), (0, 90), (0, 100), (0, 100))),
      item=dict(stack=50, subgroup='defensive-structure', order='a[wall]-d[magnetics-superconducting-gate]'), heat=None, upgrade_from=[M('magnet-gate')],
      en='Superconducting gate', ru='Сверхпроводящие ворота', de='Supraleitendes Tor',
      den='A gate as strong as a superconducting wall.', dru='Ворота, прочные, как сверхпроводящая стена.'),
  M('mend-coil'): dict(kind='mend', type='electric-energy-interface', base='electric-energy-interface', tint=[0.60, 1.00, 0.70], frg=M('mend-coil'), hp=300,
      set=dict(gui_mode='none', allow_copy_paste=False, energy_production='0W', energy_usage='0W',
               energy_source={'type': 'electric', 'usage_priority': 'secondary-input', 'buffer_capacity': '1MJ', 'input_flow_limit': '200kW', 'output_flow_limit': '0W'}),
      item=dict(stack=20, subgroup='defensive-structure', order='e[magnetics-mend-coil]'), heat=None,
      en='Mend coil', ru='Ремонтная катушка', de='Reparaturspule',
      den='Repairs walls and turrets within 10 tiles from the power grid, 5 kJ per point of health.',
      dru='Чинит стены и турели в радиусе 10 клеток за счёт электросети, 5 кДж на единицу прочности.'),
  # 4.6 турели
  M('coilgun-turret'): dict(kind='ammo-turret', type='ammo-turret', base='gun-turret', tint=[1.00, 0.70, 0.50], frg=M('coilgun-turret'), hp=500,
      attack=dict(ammo_category=M('slug'), cooldown=24, range=20),
      set=dict(inventory_size=1, automated_ammo_count=10, rotation_speed=0.015, energy_per_shot='40kJ',
               energy_source={'type': 'electric', 'usage_priority': 'primary-input', 'buffer_capacity': '200kJ', 'input_flow_limit': '250kW'}),
      item=dict(stack=50, subgroup='turret', order='b[turret]-m[magnetics]-a[coilgun]'), heat='50kW',
      en='Coilgun', ru='Катушечник', de='Spulenkanone',
      den='An electric turret firing ferrite slugs that pierce small enemies.', dru='Электрическая турель: ферритовые болванки пробивают мелких врагов.'),
  M('gauss-turret'): dict(kind='ammo-turret', type='ammo-turret', base='gun-turret', tint=[0.55, 0.65, 1.00], frg=M('gauss-turret'), hp=800,
      attack=dict(ammo_category=M('gauss'), cooldown=60, range=30),
      set=dict(automated_ammo_count=8, rotation_speed=0.008, energy_per_shot='250kJ',
               energy_source={'type': 'electric', 'usage_priority': 'primary-input', 'buffer_capacity': '1MJ', 'input_flow_limit': '1MW'}),
      item=dict(stack=50, subgroup='turret', order='b[turret]-m[magnetics]-b[gauss]'), heat='50kW',
      en='Gauss turret', ru='Пушка Гаусса', de='Gauß-Geschütz',
      den='A long-range turret whose heavy slugs break armour.', dru='Дальнобойная турель, тяжёлые болванки которой пробивают броню.'),
  M('arc-emitter'): dict(kind='arc', type='electric-turret', base='laser-turret', tint=[0.60, 0.95, 1.00], frg=M('arc-emitter'), hp=1000,
      attack=dict(ammo_category='laser', cooldown=120, range=20, energy='1MJ',  # 120: лазер даёт 30 урона/с (PILOT-15), разрядник 22,5 = 0,75 лазера
                   damage=45, chain_jumps=4, chain_range=6, chain_damage=30, beam_length=22),
      set=dict(energy_source={'type': 'electric', 'usage_priority': 'primary-input', 'buffer_capacity': '2MJ', 'input_flow_limit': '3MW', 'drain': '24kW'}),
      item=dict(stack=50, subgroup='turret', order='b[turret]-m[magnetics]-c[arc-emitter]'), heat='50kW',
      en='Arc emitter', ru='Разрядник', de='Bogenstrahler',
      den='Chain lightning that jumps through a swarm and slows it.', dru='Цепная молния перескакивает по стае и замедляет её.'),
  M('rail-cannon'): dict(kind='ammo-turret', type='ammo-turret', base='gun-turret', tint=[0.78, 0.55, 1.00], frg=M('rail-cannon'), hp=2000,
      attack=dict(ammo_category=M('rail'), cooldown=150, range=36, min_range=4, health_penalty=-1),
      set=dict(automated_ammo_count=5, rotation_speed=0.005, energy_per_shot='4MJ',
               energy_source={'type': 'electric', 'usage_priority': 'primary-input', 'buffer_capacity': '8MJ', 'input_flow_limit': '2MW'}),
      item=dict(stack=10, subgroup='turret', order='b[turret]-m[magnetics]-d[rail-cannon]'), heat='50kW',
      en='Rail cannon', ru='Рельсовая пушка', de='Schienenkanone',
      den='Fires a slug through every enemy on a line.', dru='Прошивает болванкой всех врагов на линии.'),
}
# каждая постройка Magnetics под Space Age требует магнитного поля ≥ 10 (не ставится на космические платформы)
SA_MAGNETIC_FIELD_MIN = 10

# ---------------------------------------------------------------- 5. технологии
A, L, C, Mil, Pr, U = 'automation-science-pack', 'logistic-science-pack', 'chemical-science-pack', 'military-science-pack', 'production-science-pack', 'utility-science-pack'
def T(prereq, count, time, packs, unlocks, en, ru, de, den, dru, icon=None, sa=None):
    return dict(prereq=prereq, count=count, time=time, packs=packs, unlocks=[M(u) for u in unlocks], en=en, ru=ru, de=de, den=den, dru=dru, sa=sa)
TECHS = {
  M('ferrite-sintering'): T(['automation-science-pack', 'stone-wall'], 30, 10, [A], ['sintering-kiln', 'ferrite', 'ferrite-wall'],
      'Ferrite sintering', 'Спекание феррита', 'Ferritsintern', 'Sinter iron ore with stone into ferrite; ferrite walls.', 'Спекание железной руды с камнем в феррит; ферритовые стены.'),
  M('electromagnetic-coils'): T([M('ferrite-sintering'), 'automation-2'], 75, 15, [A, L], ['coil-winder', 'coil'],
      'Electromagnetic coils', 'Электромагнитные катушки', 'Elektromagnetische Spulen', 'Wind copper cable on ferrite cores.', 'Намотка медного кабеля на ферритовые сердечники.'),
  M('coilgun'): T([M('electromagnetic-coils'), 'gun-turret', 'military-2'], 100, 15, [A, L], ['coilgun-turret', 'ferrite-slug'],
      'Coilgun', 'Катушечник', 'Spulenkanone', 'An electric turret with piercing ferrite slugs.', 'Электрическая турель с пробивающими ферритовыми болванками.'),
  M('induction-smelting'): T([M('electromagnetic-coils'), 'advanced-material-processing-2'], 250, 30, [A, L, C], ['induction-furnace', 'magnet-alloy'],
      'Induction smelting', 'Индукционная плавка', 'Induktionsschmelzen', 'Fuse steel, ferrite and copper into magnet alloy.', 'Сплавление стали, феррита и меди в магнитный сплав.'),
  M('magnetic-mining'): T([M('induction-smelting'), 'electric-mining-drill'], 250, 30, [A, L, C], ['magnetic-drill'],
      'Magnetic mining', 'Магнитная добыча', 'Magnetischer Bergbau', 'A faster in-place upgrade of the electric mining drill.', 'Более быстрое улучшение электробура на том же месте.'),
  M('magnetic-power'): T([M('induction-smelting'), 'solar-energy', 'electric-energy-accumulators'], 250, 30, [A, L, C], ['mhd-generator', 'coil-capacitor', 'geomagnetic-coil'],
      'Magnetic power', 'Магнитная энергетика', 'Magnetische Energie', 'MHD generator, coil capacitor and geomagnetic coil.', 'МГД-генератор, катушечный конденсатор и геомагнитная катушка.'),
  M('magnetic-separation'): T([M('induction-smelting'), 'advanced-oil-processing'], 150, 30, [A, L, C], ['ferrofluid', 'magnetic-separator', 'stone-separation'],
      'Magnetic separation', 'Магнитная сепарация', 'Magnetische Trennung', 'Ferrofluid, and ore recovered from stone.', 'Феррожидкость и руда, извлечённая из камня.'),
  M('magnetic-fortifications'): T([M('coilgun'), M('induction-smelting'), 'military-3', 'gate', 'repair-pack'], 250, 30, [A, L, C, Mil],
      ['magnet-wall', 'magnet-gate', 'magnet-slug', 'gauss-turret', 'gauss-slug', 'mend-coil'],
      'Magnetic fortifications', 'Магнитные укрепления', 'Magnetische Befestigungen',
      'Magnet walls and gates, magnet slugs, the gauss turret and the mend coil.', 'Магнитные стены и ворота, магнитные болванки, пушка Гаусса и ремонтная катушка.'),
  M('arc-emitter'): T([M('induction-smelting'), 'laser-turret'], 200, 30, [A, L, C, Mil], ['arc-emitter'],
      'Arc emitter', 'Разрядник', 'Bogenstrahler', 'A chain-lightning turret against swarms.', 'Турель с цепной молнией против стай.'),
  M('superconductivity'): T([M('induction-smelting'), 'production-science-pack'], 300, 30, [A, L, C, Pr], ['cryo-chamber', 'liquid-nitrogen', 'superconducting-cable'],
      'Superconductivity', 'Сверхпроводимость', 'Supraleitung', 'Liquid nitrogen from air and superconducting cable.', 'Жидкий азот из воздуха и сверхпроводящий кабель.'),
  M('superconducting-power'): T([M('superconductivity'), 'electric-energy-distribution-2', 'electric-energy-accumulators'], 300, 30, [A, L, C, Pr],
      ['superconducting-accumulator', 'superconducting-pylon'],
      'Superconducting grid', 'Сверхпроводящие сети', 'Supraleitendes Stromnetz', 'Superconducting accumulators and pylons.', 'Сверхпроводящие аккумуляторы и опоры.'),
  M('flux-energy'): T([M('superconducting-power'), M('magnetic-separation'), 'utility-science-pack', 'uranium-processing'], 500, 30, [A, L, C, Pr, U],
      ['flux-resonator', 'flux-dynamo', 'flux-crystal-growth', 'flux-crystal-charging'],
      'Flux energy', 'Энергия потока', 'Flussenergie',
      'Grow and charge flux crystals; carry power where poles cannot reach.', 'Выращивание и зарядка кристаллов потока; энергия туда, куда не дотянуть провода.'),
  M('maglev-logistics'): T(['logistics-3', M('superconductivity'), M('magnetic-separation'), 'utility-science-pack'], 600, 30, [A, L, C, Pr, U],
      ['maglev-transport-belt', 'maglev-underground-belt', 'maglev-splitter'],
      'Maglev logistics', 'Маглев-логистика', 'Magnetschwebe-Logistik',
      'Belts, undergrounds and splitters at 75 items per second.', 'Конвейеры, подземные конвейеры и разделители на 75 предметов в секунду.',
      sa=dict(extra_prereq=['turbo-transport-belt', 'electromagnetic-science-pack'], count=1000, time=60,
              packs=[A, L, C, Pr, U, 'space-science-pack', 'metallurgic-science-pack', 'electromagnetic-science-pack'])),
  M('superconducting-defense'): T([M('magnetic-fortifications'), M('flux-energy'), 'military-4', 'concrete'], 500, 45, [A, L, C, Mil, Pr, U],
      ['superconducting-wall', 'superconducting-gate', 'rail-cannon', 'rail-slug', 'flux-rail-slug'],
      'Superconducting defense', 'Сверхпроводящая оборона', 'Supraleitende Verteidigung',
      'Superconducting walls and gates, and the rail cannon.', 'Сверхпроводящие стены и ворота и рельсовая пушка.'),
}
TECH_TIER = {  # цвет ореола иконки (§10.3) — для paint.py
  'ferrite-sintering': 'red', 'electromagnetic-coils': 'green', 'coilgun': 'green', 'induction-smelting': 'blue', 'magnetic-mining': 'blue',
  'magnetic-power': 'blue', 'magnetic-separation': 'blue', 'magnetic-fortifications': 'military', 'arc-emitter': 'military',
  'superconductivity': 'purple', 'superconducting-power': 'purple', 'flux-energy': 'yellow', 'maglev-logistics': 'yellow', 'superconducting-defense': 'yellow'}

# ---------------------------------------------------------------- проверки согласованности спецификации
def self_check():
    errs = []
    unlocked = {}
    for t, d in TECHS.items():
        for r in d['unlocks']:
            if r not in RECIPES: errs.append(f'{t}: рецепт {r} не описан')
            if r in unlocked: errs.append(f'рецепт {r} открывают две технологии: {unlocked[r]} и {t}')
            unlocked[r] = t
    for r in RECIPES:
        if r not in unlocked: errs.append(f'рецепт {r} не открывает ни одна технология')
    for e in ENTITIES:
        if e not in RECIPES: errs.append(f'постройка {e} без рецепта')
    allnames = list(ITEMS) + list(AMMO) + list(FLUIDS) + list(ENTITIES) + list(RECIPES) + list(TECHS)
    for n in allnames:
        if not n.startswith(P): errs.append(f'имя без префикса: {n}')
    assert len(ENTITIES) == 26, len(ENTITIES)
    assert len(ITEMS) + len(AMMO) == 11
    assert len(RECIPES) == 40, len(RECIPES)
    assert len(TECHS) == 14
    return errs

# ---------------------------------------------------------------- генерация
def lua(v, ind=0):
    sp = '  ' * ind
    if v is None: return 'nil'
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return repr(v)
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        if not v: return '{}'
        inner = ', '.join(lua(x, ind + 1) for x in v)
        if len(inner) < 100 and '\n' not in inner: return '{' + inner + '}'
        return '{\n' + ',\n'.join(sp + '  ' + lua(x, ind + 1) for x in v) + '\n' + sp + '}'
    if isinstance(v, dict):
        if not v: return '{}'
        parts = []
        for k, x in v.items():
            key = k if k.isidentifier() else '[' + json.dumps(k) + ']'
            parts.append(f'{key} = {lua(x, ind + 1)}')
        inner = ', '.join(parts)
        if len(inner) < 100 and '\n' not in inner: return '{' + inner + '}'
        return '{\n' + ',\n'.join(sp + '  ' + p for p in parts) + '\n' + sp + '}'
    raise TypeError(type(v))

TEXT_KEYS = ('en', 'ru', 'de', 'den', 'dru')
def strip_text(d):
    return {k: v for k, v in d.items() if k not in TEXT_KEYS}

def data_table():
    return dict(
        version=VERSION,
        items={k: strip_text(v) for k, v in ITEMS.items()},
        ammo={k: strip_text(v) for k, v in AMMO.items()},
        ammo_categories={k: strip_text(v) for k, v in AMMO_CATEGORIES.items()},
        fuel_categories=list(FUEL_CATEGORIES),
        recipe_categories=RECIPE_CATEGORIES,
        fluids={k: strip_text(v) for k, v in FLUIDS.items()},
        recipes={k: strip_text(v) for k, v in RECIPES.items()},
        entities={k: strip_text(v) for k, v in ENTITIES.items()},
        techs={k: strip_text(v) for k, v in TECHS.items()},
        sa_magnetic_field_min=SA_MAGNETIC_FIELD_MIN,
    )

def write_lua(path, header):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(header + 'return ' + lua(data_table()) + '\n')

def locale(lang):
    L = []
    def sec(name, rows):
        rows = [r for r in rows if r[1]]
        if rows:
            L.append(f'[{name}]')
            L.extend(f'{k}={v}' for k, v in rows)
            L.append('')
    nm = lambda d: d.get(lang) if lang != 'de' or d.get('de') else d.get('en')
    ds = lambda d: d.get('den') if lang == 'en' else (d.get('dru') if lang == 'ru' else None)
    L.append('[mod-name]'); L.append('magnetics=Magnetics'); L.append('')
    L.append('[mod-description]')
    L.append({'en': 'magnetics=A magnetic technology branch: ferrite, coils, magnet alloy, superconducting cable and flux crystals; 26 buildings from a sintering kiln to maglev belts and a rail cannon.',
              'ru': 'magnetics=Магнитная ветка технологий: феррит, катушки, магнитный сплав, сверхпроводящий кабель и кристаллы потока; 26 построек — от спекательной печи до маглев-конвейеров и рельсовой пушки.',
              'de': 'magnetics=Ein magnetischer Technologiezweig: Ferrit, Spulen, Magnetlegierung, supraleitendes Kabel und Flusskristalle; 26 Gebäude vom Sinterofen bis zu Magnetschwebebändern und der Schienenkanone.'}[lang])
    L.append('')
    items = {**ITEMS, **AMMO}
    sec('item-name', [(k, nm(v)) for k, v in items.items()])
    sec('item-description', [(k, ds(v)) for k, v in items.items()])
    sec('fluid-name', [(k, nm(v)) for k, v in FLUIDS.items()])
    sec('fluid-description', [(k, ds(v)) for k, v in FLUIDS.items()])
    sec('entity-name', [(k, nm(v)) for k, v in ENTITIES.items()])
    sec('entity-description', [(k, ds(v)) for k, v in ENTITIES.items()])
    sec('recipe-name', [(k, nm(v)) for k, v in RECIPES.items() if v.get('en')])
    sec('technology-name', [(k, nm(v)) for k, v in TECHS.items()])
    sec('technology-description', [(k, ds(v)) for k, v in TECHS.items()])
    sec('ammo-category-name', [(k, nm(v)) for k, v in AMMO_CATEGORIES.items()])
    sec('fuel-category-name', [(k, nm(v)) for k, v in FUEL_CATEGORIES.items()])
    return '\n'.join(L)

def main():
    errs = self_check()
    if errs:
        for e in errs: print('ОШИБКА СПЕЦИФИКАЦИИ:', e)
        raise SystemExit(1)
    hdr = '-- СГЕНЕРИРОВАНО tools/spec.py — не править руками. Все числа мода — здесь.\n'
    write_lua(os.path.join(MOD, 'prototypes', 'spec_data.lua'), hdr)
    write_lua(os.path.join(HERE, 'magnetics-tests', 'expected.lua'), '-- СГЕНЕРИРОВАНО tools/spec.py: ожидания статических тестов (та же спецификация).\n')
    for lang in ('en', 'ru', 'de'):
        p = os.path.join(MOD, 'locale', lang, 'magnetics.cfg')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w', encoding='utf-8').write(locale(lang) + '\n')
    json.dump(data_table(), open(os.path.join(HERE, 'spec.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'spec: {len(ENTITIES)} построек, {len(ITEMS) + len(AMMO)} предметов, {len(FLUIDS)} жидкости, {len(RECIPES)} рецептов, {len(TECHS)} технологий — сгенерировано')

if __name__ == '__main__':
    main()
