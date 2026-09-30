# Magnetics 1.0 — единая спецификация: контент (JSON для Mindustry v146), имена и описания (ru/en/de), вид спрайта, ожидания для тестов.
# Числа ванили для сравнения сняты с сервера v146 (см. README).
def R(*a): return [f"{a[i]}/{a[i+1]}" for i in range(0, len(a), 2)]
ITEMS = {
  'ferrite':       dict(color='5c4a52', cost=0.7, research='lead', ru=('Феррит', 'Спечённый песок со свинцом. Дешёвый магнитный материал ранней игры.'), en=('Ferrite', 'Sand sintered with lead. A cheap early magnetic material.'), de='Ferrit'),
  'magnet-alloy':  dict(color='6d86c9', cost=1.1, research='titanium', ru=('Магнитный сплав', 'Титан, сплавленный с кремнием в индукционном поле. Основа всех магнитных машин.'), en=('Magnet Alloy', 'Titanium fused with silicon in an induction field. Base of every magnetic machine.'), de='Magnetlegierung'),
  'coil':          dict(color='d6854a', cost=0.9, research='magnet-alloy', ru=('Катушка', 'Медный провод на сердечнике из сплава. Идёт в генераторы, зенитки и юниты.'), en=('Coil', 'Copper wire on an alloy core. Used in generators, flak and units.'), de='Spule'),
  'superconductor':dict(color='9fe8ff', cost=1.4, research='coil', ru=('Сверхпроводник', 'Сплав в пластановой оболочке, охлаждённый криожидкостью. Ток без потерь.'), en=('Superconductor', 'Alloy in a plastanium sheath, cooled by cryofluid. Current without loss.'), de='Supraleiter'),
  'flux-crystal':  dict(color='b58cff', cost=1.8, research='superconductor', ru=('Кристалл потока', 'Фазовая ткань, застывшая в сверхпроводящем поле. Топливо реактора и снаряд рельсотрона.'), en=('Flux Crystal', 'Phase fabric frozen in a superconducting field. Reactor fuel and railgun ammo.'), de='Flusskristall'),
}
B = {}   # имя → (json, текст, спрайт, тест)
def add(name, j, ru, en, de, art, test=None): B[name] = dict(j=j, ru=ru, en=en, de=de, art=art, test=test or {})
# ---------- производство предметов ----------
def crafter(name, size, req, items, out, t, power, research, ru, en, de, art, liquid=None, outs=None, hp=None):
    c = {'items': {'items': R(*items)}, 'power': power}
    if liquid: c['liquid'] = {'liquid': liquid[0], 'amount': liquid[1]}
    j = dict(type='GenericCrafter', size=size, health=hp or 80 * size * size, category='crafting', requirements=R(*req), craftTime=t, consumes=c, research=research,
             craftEffect='smeltsmoke', drawer={'type': 'DrawMulti', 'drawers': [{'type': 'DrawDefault'}, {'type': 'DrawFlame', 'flameColor': '8fb4ff'}]})
    if outs: j['outputItems'] = R(*outs)
    else: j['outputItem'] = f'{out[0]}/{out[1]}'
    add(name, j, ru, en, de, art, dict(kind='crafter', items=items, out=outs or out, t=t, liquid=liquid))
crafter('sintering-kiln', 2, ('copper', 45, 'lead', 30), ('sand', 2, 'lead', 1), ('ferrite', 2), 50, 0.5, 'graphite-press',
        ('Спекательная печь', 'Спекает песок со свинцом в феррит.'), ('Sintering Kiln', 'Sinters sand and lead into ferrite.'), 'Sinterofen', 'kiln')
crafter('induction-furnace', 2, ('copper', 60, 'lead', 50, 'titanium', 60, 'silicon', 40), ('titanium', 2, 'silicon', 1), ('magnet-alloy', 1), 60, 1.2, 'silicon-smelter',
        ('Индукционная печь', 'Сплавляет титан и кремний в магнитный сплав вихревыми токами.'), ('Induction Furnace', 'Fuses titanium and silicon into magnet alloy with eddy currents.'), 'Induktionsofen', 'furnace')
crafter('coil-winder', 2, ('copper', 80, 'lead', 40, 'magnet-alloy', 30), ('magnet-alloy', 1, 'copper', 2), ('coil', 2), 45, 0.8, 'induction-furnace',
        ('Намоточный станок', 'Наматывает медный провод на сердечник из сплава.'), ('Coil Winder', 'Winds copper wire onto an alloy core.'), 'Wickelmaschine', 'winder')
crafter('cryo-chamber', 3, ('lead', 120, 'titanium', 100, 'silicon', 80, 'plastanium', 40, 'magnet-alloy', 60), ('magnet-alloy', 2, 'plastanium', 1), ('superconductor', 1), 90, 3, 'coil-winder',
        ('Криокамера', 'Одевает сплав в пластан и замораживает криожидкостью — получается сверхпроводник.'), ('Cryo Chamber', 'Sheathes alloy in plastanium and freezes it with cryofluid into superconductor.'), 'Kryokammer', 'cryo', liquid=('cryofluid', 0.12))
crafter('flux-resonator', 3, ('lead', 150, 'silicon', 120, 'phase-fabric', 50, 'superconductor', 80), ('superconductor', 2, 'phase-fabric', 1), ('flux-crystal', 1), 120, 6, 'cryo-chamber',
        ('Резонатор потока', 'Замораживает фазовую ткань в сверхпроводящем поле — растит кристалл потока.'), ('Flux Resonator', 'Freezes phase fabric in a superconducting field, growing flux crystals.'), 'Flussresonator', 'resonator')
crafter('magnetic-separator', 3, ('copper', 100, 'titanium', 60, 'ferrite', 80), ('scrap', 3), None, 60, 1.5, 'separator',
        ('Магнитный сепаратор', 'Магнитами разбирает металлолом на медь, свинец и титан.'), ('Magnetic Separator', 'Sorts scrap into copper, lead and titanium with magnets.'), 'Magnetabscheider', 'separator', outs=('copper', 2, 'lead', 1, 'titanium', 1))
# ---------- добыча ----------
add('magnetic-drill', dict(type='Drill', size=3, health=720, category='production', requirements=R('copper', 60, 'silicon', 40, 'titanium', 50, 'magnet-alloy', 40), tier=4, drillTime=200,
    consumes={'power': 2.5, 'liquid': {'liquid': 'water', 'amount': 0.08, 'optional': True, 'booster': True}}, research='laser-drill', updateEffect='pulverizeMedium', drillEffect='mineBig'),
    ('Магнитный бур', 'Бур с магнитным приводом. Быстрее лазерного, берёт торий.'), ('Magnetic Drill', 'A drill with a magnetic drive. Faster than the laser drill, mines thorium.'), 'Magnetbohrer', 'drill', dict(kind='drill'))
# ---------- логистика ----------
add('mag-conveyor', dict(type='Conveyor', health=90, category='distribution', requirements=R('copper', 1, 'lead', 1, 'magnet-alloy', 1), speed=0.11, displayedSpeed=16, research='titanium-conveyor'),
    ('Магнитная лента', 'Перемещает предметы по магнитной дорожке. Быстрее титанового конвейера.'), ('Mag Conveyor', 'Moves items along a magnetic track. Faster than the titanium conveyor.'), 'Magnetband', 'conveyor', dict(kind='conveyor'))
add('mag-junction', dict(type='Junction', health=120, category='distribution', requirements=R('copper', 3, 'magnet-alloy', 2), speed=12, capacity=8, research='mag-conveyor'),
    ('Магнитный перекрёсток', 'Пропускает два потока крест-накрест.'), ('Mag Junction', 'Passes two item streams across each other.'), 'Magnetkreuzung', 'junction')
add('mag-router', dict(type='Router', health=120, category='distribution', requirements=R('copper', 3, 'magnet-alloy', 2), speed=4, research='mag-junction'),
    ('Магнитный разветвитель', 'Раздаёт предметы во все стороны.'), ('Mag Router', 'Distributes items to all sides.'), 'Magnetverteiler', 'router')
add('mag-bridge', dict(type='BufferedItemBridge', health=150, category='distribution', requirements=R('lead', 8, 'graphite', 6, 'magnet-alloy', 6), range=8, speed=90, bufferCapacity=20, research='mag-router'),
    ('Магнитный мост', 'Перебрасывает предметы на 8 клеток над препятствиями.'), ('Mag Bridge', 'Carries items over obstacles for 8 tiles.'), 'Magnetbrücke', 'bridge')
# ---------- энергия ----------
add('coil-battery', dict(type='Battery', size=1, health=120, category='power', requirements=R('copper', 8, 'lead', 30, 'coil', 6), consumes={'powerBuffered': 4000}, research='battery',
    emptyLightColor='3a4a7a', fullLightColor='9fe8ff'), ('Катушечный аккумулятор', 'Маленький аккумулятор: 4000 единиц.'), ('Coil Battery', 'A small battery: 4000 units.'), 'Spulenakku', 'battery1', dict(kind='battery', cap=4000))
add('superconducting-battery', dict(type='Battery', size=3, health=800, category='power', requirements=R('lead', 60, 'titanium', 40, 'silicon', 40, 'superconductor', 30), consumes={'powerBuffered': 150000},
    research='battery-large', emptyLightColor='3a4a7a', fullLightColor='9fe8ff'), ('Сверхпроводящая батарея', 'Хранит втрое больше большого аккумулятора.'), ('Superconducting Battery', 'Stores three times as much as a large battery.'), 'Supraleitende Batterie', 'battery3', dict(kind='battery', cap=150000))
add('superconducting-node', dict(type='PowerNode', size=2, health=300, category='power', requirements=R('lead', 10, 'titanium', 10, 'silicon', 10, 'superconductor', 5), laserRange=22, maxNodes=20, research='power-node-large'),
    ('Сверхпроводящий узел', 'Силовой узел со связью на 22 блока.'), ('Superconducting Node', 'A power node linking up to 22 tiles.'), 'Supraleitender Knoten', 'node', dict(kind='node'))
add('mhd-generator', dict(type='ConsumeGenerator', size=2, health=400, category='power', requirements=R('copper', 60, 'lead', 60, 'silicon', 40, 'coil', 30), powerProduction=14, itemDuration=120,
    consumes={'item': 'pyratite', 'liquid': {'liquid': 'cryofluid', 'amount': 0.06}}, research='steam-generator', generateEffect='generatespark'),
    ('МГД-генератор', 'Прогоняет плазму пиратита через поле катушек. 840 энергии в секунду.'), ('MHD Generator', 'Drives pyratite plasma through a coil field. 840 power per second.'), 'MHD-Generator', 'mhd', dict(kind='generator', prod=14))
add('flux-dynamo', dict(type='ConsumeGenerator', size=3, health=1200, category='power', requirements=R('lead', 200, 'silicon', 150, 'plastanium', 80, 'superconductor', 100), powerProduction=60, itemDuration=600,
    consumes={'item': 'flux-crystal'}, research='mhd-generator', generateEffect='generatespark'),
    ('Реактор потока', 'Медленно разряжает кристалл потока. 3600 энергии в секунду, не взрывается.'), ('Flux Reactor', 'Slowly discharges flux crystals. 3600 power per second, never explodes.'), 'Flussreaktor', 'reactor', dict(kind='generator', prod=60))
# ---------- оборона ----------
def wall(name, sz, hp, req, research, ru, en, de, art, extra=None):
    j = dict(type='Wall', size=sz, health=hp, category='defense', requirements=R(*req), research=research); j.update(extra or {})
    add(name, j, ru, en, de, art, dict(kind='wall', hp=hp))
wall('ferrite-wall', 1, 360, ('ferrite', 6), 'copper-wall', ('Ферритовая стена', 'Дешёвая стена ранней игры.'), ('Ferrite Wall', 'A cheap early wall.'), 'Ferritwand', 'wall-ferrite')
wall('ferrite-wall-large', 2, 1440, ('ferrite', 24), 'ferrite-wall', ('Большая ферритовая стена', 'Дешёвая стена ранней игры.'), ('Large Ferrite Wall', 'A cheap early wall.'), 'Große Ferritwand', 'wall-ferrite')
wall('magnet-wall', 1, 640, ('magnet-alloy', 6), 'titanium-wall', ('Магнитная стена', 'Прочнее титановой. Поле иногда отражает пули.'), ('Magnet Wall', 'Tougher than titanium. Its field sometimes deflects bullets.'), 'Magnetwand', 'wall-magnet', dict(chanceDeflect=5, flashHit=True))
wall('magnet-wall-large', 2, 2560, ('magnet-alloy', 24), 'magnet-wall', ('Большая магнитная стена', 'Прочнее титановой. Поле иногда отражает пули.'), ('Large Magnet Wall', 'Tougher than titanium. Its field sometimes deflects bullets.'), 'Große Magnetwand', 'wall-magnet', dict(chanceDeflect=5, flashHit=True))
wall('superconducting-wall', 1, 1000, ('superconductor', 6), 'magnet-wall', ('Сверхпроводящая стена', 'Поглощает лазеры и молнии, не проводит ток.'), ('Superconducting Wall', 'Absorbs lasers and lightning, does not conduct power.'), 'Supraleitende Wand', 'wall-super', dict(absorbLasers=True, insulated=True))
wall('superconducting-wall-large', 2, 4000, ('superconductor', 24), 'superconducting-wall', ('Большая сверхпроводящая стена', 'Поглощает лазеры и молнии, не проводит ток.'), ('Large Superconducting Wall', 'Absorbs lasers and lightning, does not conduct power.'), 'Große supraleitende Wand', 'wall-super', dict(absorbLasers=True, insulated=True))
add('mend-coil', dict(type='MendProjector', size=2, health=240, category='effect', requirements=R('lead', 40, 'silicon', 30, 'coil', 20), reload=200, range=90, healPercent=14, phaseBoost=10, phaseRangeBoost=20,
    consumes={'power': 0.45}, research='mender'), ('Ремонтная катушка', 'Индукцией чинит постройки в радиусе 11 блоков.'), ('Mend Coil', 'Repairs buildings within 11 tiles by induction.'), 'Reparaturspule', 'mend', dict(kind='mend'))
add('magnetic-shield', dict(type='ForceProjector', size=3, health=900, category='effect', requirements=R('lead', 120, 'titanium', 90, 'silicon', 100, 'superconductor', 40), radius=110, shieldHealth=1100, cooldownNormal=2.2,
    cooldownBrokenBase=0.45, phaseRadiusBoost=40, consumes={'power': 5}, research='force-projector'), ('Магнитный щит', 'Силовой купол, который выдерживает больше, чем обычный.'), ('Magnetic Shield', 'A force dome that takes more punishment than the standard one.'), 'Magnetschild', 'shield', dict(kind='shield'))
# ---------- турели ----------
def bullet(speed, dmg, life, **kw):
    b = dict(type='BasicBulletType', speed=speed, damage=dmg, lifetime=life, width=kw.pop('w', 8), height=kw.pop('h', 14), frontColor='e3ecff', backColor='6d86c9', hitEffect='hitBulletSmall', shootEffect='shootSmall'); b.update(kw); return b
add('coilgun', dict(type='ItemTurret', size=1, health=300, category='turret', requirements=R('copper', 40, 'ferrite', 25), range=130, reload=18, recoil=1.5, rotateSpeed=10, shootSound='shootSnap', research='duo', targetAir=True,
    ammoTypes={'ferrite': bullet(5, 14, 27, ammoMultiplier=3, pierce=True, pierceCap=2), 'magnet-alloy': bullet(6, 24, 22, ammoMultiplier=2, pierce=True, pierceCap=3, reloadMultiplier=0.9)}),
    ('Катушечник', 'Маленькая пушка-катушка ранней игры. Ферритовые болты пробивают двух врагов.'), ('Coilgun', 'A small early coil cannon. Ferrite bolts pierce two enemies.'), 'Spulenkanone', 'turret1', dict(kind='turret', ammo='ferrite'))
add('gauss', dict(type='ItemTurret', size=2, health=1200, category='turret', requirements=R('copper', 120, 'titanium', 80, 'silicon', 60, 'magnet-alloy', 80), range=280, reload=70, recoil=3, rotateSpeed=4, shake=1.5, shootSound='railgun',
    research='lancer', targetAir=True, consumes={'coolant': {'amount': 0.2}}, coolantMultiplier=4,
    ammoTypes={'magnet-alloy': bullet(12, 110, 24, w=8, h=18, ammoMultiplier=2, pierce=True, pierceCap=3, pierceBuilding=False, trailLength=6, trailWidth=2, trailColor='8fb4ff', hitEffect='hitBulletBig', shootEffect='shootBig'),
               'thorium': bullet(10, 150, 28, w=9, h=18, ammoMultiplier=1, reloadMultiplier=0.8, pierce=True, pierceCap=2, frontColor='ffd0f0', backColor='f9a3c7', hitEffect='hitBulletBig', shootEffect='shootBig')}),
    ('Гаусс', 'Пушка-катушка. Болванки пробивают три цели. Большая дальность, медленная перезарядка.'), ('Gauss', 'A coilgun. Slugs pierce three targets. Long range, slow reload.'), 'Gauß', 'turret2', dict(kind='turret', ammo='magnet-alloy'))
add('arc-emitter', dict(type='PowerTurret', size=2, health=900, category='turret', requirements=R('copper', 100, 'lead', 80, 'silicon', 60, 'coil', 50), range=115, reload=32, recoil=1, rotateSpeed=8, shootSound='spark', research='arc',
    targetAir=False, consumes={'power': 3.5, 'coolant': {'amount': 0.2}}, shootType={'type': 'LightningBulletType', 'damage': 26, 'lightningLength': 20, 'collidesAir': False, 'lightningColor': '9fe8ff', 'ammoMultiplier': 1}),
    ('Разрядник', 'Бьёт наземные цели ветвистой молнией. Нужна только энергия.'), ('Arc Emitter', 'Strikes ground targets with branching lightning. Needs only power.'), 'Bogenstrahler', 'turret2arc', dict(kind='turret', ammo=None))
add('maglev-flak', dict(type='ItemTurret', size=2, health=900, category='turret', requirements=R('copper', 90, 'lead', 60, 'coil', 40), range=240, reload=11, recoil=1.5, rotateSpeed=12, shootSound='shootSnap', research='scatter',
    targetGround=False, targetAir=True, shoot={'type': 'ShootAlternate', 'spread': 4},
    ammoTypes={'coil': {'type': 'FlakBulletType', 'speed': 5, 'damage': 5, 'splashDamage': 45, 'splashDamageRadius': 28, 'lifetime': 48, 'explodeRange': 20, 'width': 6, 'height': 8, 'ammoMultiplier': 4,
                        'frontColor': 'ffd8a8', 'backColor': 'd6854a', 'hitEffect': 'flakExplosion', 'collidesGround': False},
               'ferrite': {'type': 'FlakBulletType', 'speed': 4.5, 'damage': 3, 'splashDamage': 22, 'splashDamageRadius': 22, 'lifetime': 50, 'explodeRange': 18, 'width': 6, 'height': 8, 'ammoMultiplier': 5, 'hitEffect': 'flakExplosion', 'collidesGround': False}}),
    ('Маглев-зенитка', 'Скорострельная зенитка: разгоняет катушки магнитом и рвёт их у цели.'), ('Maglev Flak', 'A rapid anti-air gun: launches coils magnetically and bursts them near targets.'), 'Maglev-Flak', 'turret2flak', dict(kind='aa', ammo='coil'))
add('railgun', dict(type='ItemTurret', size=3, health=2400, category='turret', requirements=R('copper', 300, 'titanium', 200, 'plastanium', 120, 'superconductor', 150), range=420, reload=210, recoil=5, rotateSpeed=2.2, shake=4, shootSound='railgun',
    research='ripple', targetAir=True, consumes={'power': 8, 'coolant': {'amount': 0.4}}, coolantMultiplier=3,
    ammoTypes={'superconductor': {'type': 'RailBulletType', 'length': 420, 'damage': 700, 'pierceDamageFactor': 0.5, 'shootEffect': 'railShoot', 'hitEffect': 'hitBulletBig', 'pointEffect': 'railTrail', 'pierceEffect': 'railHit', 'ammoMultiplier': 1},
               'flux-crystal': {'type': 'RailBulletType', 'length': 460, 'damage': 1200, 'pierceDamageFactor': 0.6, 'shootEffect': 'railShoot', 'hitEffect': 'hitBulletBig', 'pointEffect': 'railTrail', 'pierceEffect': 'railHit', 'ammoMultiplier': 2, 'rangeChange': 40}}),
    ('Рельсотрон', 'Сверхпроводящие рельсы, один выстрел раз в 3,5 с — прошивает всё на линии.'), ('Railgun', 'Superconducting rails; one shot every 3.5 s pierces everything in line.'), 'Railgun', 'turret3', dict(kind='turret', ammo='superconductor'))
# ---------- юниты ----------
UNITS = {
  'spark': dict(health=190, speed=3.1, hitSize=10, armor=1, engineOffset=6, engineSize=2.5, drag=0.04, accel=0.09, itemCapacity=15, circleTarget=True,
      weapons=[dict(x=3, y=1, reload=16, mirror=True, alternate=True, bullet=bullet(4, 11, 40, w=6, h=9, pierce=True, pierceCap=2), shootSound='pew')],
      ru=('Искра', 'Лёгкий магнитный истребитель. Болты пробивают двух врагов.'), en=('Spark', 'A light magnetic fighter. Bolts pierce two enemies.'), de='Funke', art='unit-spark',
      plan=dict(time=900, req=R('silicon', 20, 'coil', 10))),
  'inductor': dict(health=480, speed=2.3, hitSize=14, armor=3, engineOffset=8, engineSize=3, drag=0.05, accel=0.07, itemCapacity=30, mineTier=2, mineSpeed=4, buildSpeed=0.6,
      weapons=[dict(x=0, y=2, reload=30, mirror=False, bullet={'type': 'LaserBoltBulletType', 'speed': 5.2, 'damage': 14, 'lifetime': 36, 'healPercent': 6, 'collidesTeam': True, 'backColor': '9fe8ff', 'frontColor': 'ffffff'}, shootSound='lasershoot')],
      ru=('Индуктор', 'Ремонтник: чинит постройки болтами, добывает и строит.'), en=('Inductor', 'A support craft: heals buildings with bolts, mines and builds.'), de='Induktor', art='unit-inductor',
      plan=dict(time=1500, req=R('silicon', 40, 'coil', 25, 'magnet-alloy', 20))),
  'magnetar': dict(health=1900, speed=1.6, hitSize=24, armor=7, engineOffset=13, engineSize=4.5, drag=0.06, accel=0.05, itemCapacity=0, rotateSpeed=2.5,
      weapons=[dict(x=6, y=0, reload=55, mirror=True, alternate=True, shake=1, bullet=bullet(9, 95, 30, w=8, h=18, pierce=True, pierceCap=3, trailLength=6, trailWidth=2, trailColor='8fb4ff', hitEffect='hitBulletBig', shootEffect='shootBig'), shootSound='railgun')],
      ru=('Магнетар', 'Тяжёлый ганшип с двумя пушками Гаусса.'), en=('Magnetar', 'A heavy gunship with twin gauss cannons.'), de='Magnetar', art='unit-magnetar',
      plan=dict(time=3000, req=R('silicon', 90, 'titanium', 60, 'coil', 50, 'superconductor', 30))),
}
add('magnet-factory', dict(type='UnitFactory', size=3, health=900, category='units', requirements=R('copper', 120, 'lead', 100, 'silicon', 80, 'coil', 40), consumes={'power': 2}, research='air-factory'),
    ('Магнитный завод', 'Собирает летающие магнитные машины: Искру, Индуктор и Магнетар.'), ('Magnet Factory', 'Builds magnetic aircraft: Spark, Inductor and Magnetar.'), 'Magnetfabrik', 'factory', dict(kind='factory'))
