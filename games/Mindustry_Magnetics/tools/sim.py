# Симуляции Magnetics 1.0 на сервере v146: производство, генераторы, бур, завод, ремонт, щит, бой. Результат — sim_results.json.
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import spec, mdt
from tests import cname
MOD = os.path.join(HERE, '..', 'magnetics')
PRE = ('var T=Team.sharded,E=Team.crux,B=Blocks,bl=n=>Vars.content.block(n),it=n=>Vars.content.item(n),un=n=>Vars.content.unit(n),liq=n=>Vars.content.liquid(n);'
       'var put=function(b,x,y,r){Vars.world.tile(x,y).setNet(b,T,r||0);return Vars.world.tile(x,y).build};'
       'var clr=function(x0,y0,x1,y1){for(var x=x0;x<=x1;x++)for(var y=y0;y<=y1;y++){var t=Vars.world.tile(x,y);if(t==null)continue;t.setAir();t.setFloor(B.metalFloor);t.setOverlay(B.air)}};'
       'Vars.state.rules.waves=false;Vars.state.rules.unitCap=999;')
def js(s): return 'js ' + PRE + s
def grab(out, tag):
    for l in out:
        m = re.search(tag + r' (\{.*\})', l)
        if m: return json.loads(m.group(1))
    return {'error': [l for l in out if '[E]' in l or 'Error' in l][:3]}
def production():
    setup, meas = ['clr(2,2,120,60);'], []
    cr = [(n, b) for n, b in spec.B.items() if b['test'].get('kind') == 'crafter']; x = 8
    for n, b in cr:
        j = b['j']; s = j['size']; off = (s - 1) // 2; y = 10; x0, y0 = x - off, y - off
        setup.append(f'put(bl("magnetics-{n}"),{x},{y});')
        for k, (i, a) in enumerate([(q.split("/")[0], q) for q in j['consumes']['items']['items']]): setup.append(f'put(B.itemSource,{x0 - 1},{y0 + k}).outputItem=it("{cname(i)}");')
        if 'liquid' in j['consumes']: setup.append(f'put(B.liquidSource,{x0 - 1},{y0 + s - 1}).source=liq("{cname(j["consumes"]["liquid"]["liquid"])}");')
        setup.append(f'put(B.powerSource,{x0},{y0 + s});'); setup.append(f'put(B.vault,{x0 + s + 1},{y0 + 1});')
        outs = j['outputItems'] if 'outputItems' in j else [j['outputItem']]
        meas.append(f'o["{n}"]={{t:{b["test"]["t"]},out:{{' + ','.join(f'"{q.split("/")[0]}":[Vars.world.tile({x0 + s + 1},{y0 + 1}).build.items.get(it("{cname(q.split("/")[0])}")),{q.split("/")[1]}]' for q in outs) + '}};')
        x += s + 6
    # генераторы
    setup.append('clr(2,70,60,90);')
    setup.append('put(bl("magnetics-mhd-generator"),10,76);put(B.itemSource,9,76).outputItem=it("pyratite");put(B.liquidSource,9,77).source=liq("cryofluid");')
    setup.append('put(bl("magnetics-flux-dynamo"),30,76);put(B.itemSource,28,76).outputItem=it("magnetics-flux-crystal");')
    meas.append('o["mhd-generator"]={eff:Vars.world.tile(10,76).build.productionEfficiency,prod:Vars.world.tile(10,76).block.powerProduction};o["flux-dynamo"]={eff:Vars.world.tile(30,76).build.productionEfficiency,prod:Vars.world.tile(30,76).block.powerProduction};')
    # бур против лазерного на тории
    setup.append('clr(70,70,110,95);for(var dx=-1;dx<=1;dx++)for(var dy=-1;dy<=1;dy++){Vars.world.tile(75+dx,80+dy).setOverlay(B.oreThorium);Vars.world.tile(95+dx,80+dy).setOverlay(B.oreThorium);}')
    setup.append('for(var dx=-1;dx<=1;dx++)for(var dy=-1;dy<=1;dy++){Vars.world.tile(75+dx,90+dy).setOverlay(B.oreThorium);Vars.world.tile(95+dx,90+dy).setOverlay(B.oreThorium);}put(bl("magnetics-magnetic-drill"),75,90);put(B.powerSource,75,92);put(B.vault,78,90);put(B.liquidSource,73,90).source=Liquids.water;put(B.laserDrill,95,90);put(B.powerSource,95,92);put(B.vault,98,90);put(B.liquidSource,93,90).source=Liquids.water;');setup.append('put(bl("magnetics-magnetic-drill"),75,80);put(B.powerSource,75,82);put(B.vault,78,80);put(B.laserDrill,95,80);put(B.powerSource,95,82);put(B.vault,98,80);')
    meas.append('o["drill_water"]={magnetic:Vars.world.tile(78,90).build.items.get(Items.thorium),laser:Vars.world.tile(98,90).build.items.get(Items.thorium)};o["drill"]={magnetic:Vars.world.tile(78,80).build.items.get(Items.thorium),laser:Vars.world.tile(98,80).build.items.get(Items.thorium)};')
    # завод: план 0 (Искра)
    setup.append('clr(120,10,150,40);var f=put(bl("magnetics-magnet-factory"),130,20);for(var pi=0;pi<f.block.plans.size;pi++)if(f.block.plans.get(pi).unit==un("magnetics-spark"))f.currentPlan=pi;put(B.powerSource,130,22);put(B.itemSource,128,20).outputItem=it("silicon");put(B.itemSource,128,19).outputItem=it("magnetics-coil");')
    meas.append('var nsp=0;Groups.unit.each(u=>{if(u.type==un("magnetics-spark"))nsp++});o["factory"]={spark:nsp,progress:Vars.world.tile(130,20).build.progress};')
    # ремонт и щит
    setup.append('clr(120,50,160,80);var w=put(bl("magnetics-magnet-wall"),130,60);w.health=100;put(bl("magnetics-mend-coil"),134,60);put(B.powerSource,134,62);put(bl("magnetics-magnetic-shield"),150,60);put(B.powerSource,150,62);')
    meas.append('o["mend"]={wall_hp:Vars.world.tile(130,60).build.health,from:100};o["shield"]={broken:Vars.world.tile(150,60).build.broken,radscl:Vars.world.tile(150,60).build.radscl,eff:Vars.world.tile(150,60).build.efficiency};')
    out = mdt.run(['host Triad sandbox', 'sleep 2', js(''.join(setup) + '"setup "+Vars.state.tick'), 'js "t0 "+Vars.state.tick', 'sleep 33', js('var o={};' + ''.join(meas) + 'o.ticks=Vars.state.tick;"RES "+JSON.stringify(o)')], MOD, wait=12, tail=2)
    t0 = next((float(re.search(r't0 ([\d.]+)', l).group(1)) for l in out if re.search(r't0 [\d.]+', l)), None)
    r = grab(out, 'RES'); r['t0'] = t0; return r, out
LANES = {
  'A': [('coilgun', 'magnetics-coilgun', 'magnetics-ferrite', 'dagger', 11), ('duo', 'duo', 'graphite', 'dagger', 11), ('gauss', 'magnetics-gauss', 'magnetics-magnet-alloy', 'mace', 18), ('lancer', 'lancer', None, 'mace', 18), ('salvo', 'salvo', 'graphite', 'mace', 18)],
  'B': [('arc-emitter', 'magnetics-arc-emitter', None, 'dagger', 10), ('arc', 'arc', None, 'dagger', 10), ('maglev-flak', 'magnetics-maglev-flak', 'magnetics-coil', 'horizon', 20), ('scatter', 'scatter', 'scrap', 'horizon', 20)],
  'C': [('railgun', 'magnetics-railgun', 'magnetics-superconductor', 'fortress', 28), ('ripple', 'ripple', 'graphite', 'fortress', 28)],
}
def combat(group):
    ys = [20, 60, 100, 140, 180] if len(LANES[group]) > 2 else [30, 160]
    setup = []
    for (name, blk, ammo, enemy, dist), y in zip(LANES[group], ys):
        setup.append(f'clr(3,{y - 8},75,{y + 8});var b=bl("{blk}"),s=b.size,L=10-Math.floor((s-1)/2)-1,U={y}+Math.floor(s/2)+1;put(b,10,{y});')
        if ammo: setup.append(f'put(B.itemSource,L,{y}).outputItem=it("{ammo}");')
        setup.append(f'put(B.powerSource,10,U);put(B.liquidSource,10+Math.floor(s/2)+1,{y}).source=liq("water");')
        line = 'true' if group == 'C' else 'false'
        setup.append(f'for(var j=0;j<5;j++){{var u=UnitTypes.{enemy}.spawn(E,(10+{dist}+({line}?j*2:0))*8,({y}+({line}?0:(-4+2*j)))*8);u.apply(StatusEffects.unmoving,1e9);u.apply(StatusEffects.disarmed,1e9);}}')
    names = [l[0] for l in LANES[group]]
    meas = (f'var ys={json.dumps(ys[:len(names)])},nm={json.dumps(names)},o={{}};for(var k=0;k<nm.length;k++){{var y=ys[k],hp=0,mx=0,n=0;'
            'Groups.unit.each(u=>{if(u.team==E&&Math.abs(u.y/8-y)<8){hp+=u.health;mx+=u.maxHealth;n++}});o[nm[k]]={alive:n,hp_left:Math.round(hp)}};"RES "+JSON.stringify(o)')
    cmds = ['host Triad sandbox', 'sleep 2', js(''.join(setup) + '"ok"')]
    for t in (5, 10, 20): cmds += [f'sleep {5 if t == 5 else (5 if t == 10 else 10)}', js(meas.replace('"RES "', f'"R{t} "'))]
    out = mdt.run(cmds, MOD, wait=12, tail=2)
    res = {}
    for t in (5, 10, 20): res[t] = grab(out, f'R{t}')
    return res, out
if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'prod': r, out = production()
    else: r, out = combat(what)
    print(json.dumps(r, ensure_ascii=False))
    p = os.path.join(HERE, 'sim_results.json'); allr = json.load(open(p)) if os.path.exists(p) else {}
    allr[what] = r; json.dump(allr, open(p, 'w'), ensure_ascii=False, indent=1)
