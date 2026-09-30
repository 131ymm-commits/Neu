# Автотесты Magnetics 1.0, сгенерированные из spec.py: (1) статические — каждое число применено; (2) симуляции в живом мире.
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import spec, mdt
MOD = os.path.join(HERE, '..', 'magnetics')
VAN = set(open(os.path.join(HERE, 'vanilla_names_v146.txt')).read().split()) if os.path.exists(os.path.join(HERE, 'vanilla_names_v146.txt')) else set()
def cname(n): return n if n in VAN or n in ('copper','lead','sand','coal','titanium','thorium','scrap','silicon','plastanium','phase-fabric','surge-alloy','spore-pod','blast-compound','pyratite','metaglass','graphite','cryofluid','water','slag','oil') else 'magnetics-' + n
def split(req): return [(a.split('/')[0], int(a.split('/')[1])) for a in req]
def static_js():
    L = ['var R=[];function ok(n,c,v){R.push((c?"OK ":"FAIL ")+n+(c?"":" got="+v))}', 'var bl=n=>Vars.content.block(n),it=n=>Vars.content.item(n),un=n=>Vars.content.unit(n);',
         'var par=x=>{var t=x.techNode;return t==null?"нет":(t.parent==null?"корень":t.parent.content.name)};', 'var close=(a,b)=>Math.abs(a-b)<1e-3;']
    for n, v in spec.ITEMS.items():
        L.append(f'var x=it("magnetics-{n}");ok("item {n}",x!=null&&close(x.cost,{v["cost"]}),x&&x.cost);ok("tech {n}",x!=null&&par(x)=="{cname(v["research"])}",x&&par(x));')
    for n, b in spec.B.items():
        j = b['j']; L.append(f'var b=bl("magnetics-{n}");ok("exists {n}",b!=null,b);')
        L.append(f'ok("visible {n}",b.isVisible(),b.buildVisibility);ok("hp {n}",b.health=={j["health"]},b.health);ok("size {n}",b.size=={j.get("size",1)},b.size);ok("tech {n}",par(b)=="{cname(j["research"])}",par(b));')
        req = split(j['requirements']); L.append(f'ok("req {n}",b.requirements.length=={len(req)}&&' + '&&'.join(f'b.requirements.some(s=>s.item.name=="{cname(i)}"&&s.amount=={a})' for i, a in req) + ',b.requirements.map(s=>s.item.name+":"+s.amount).join(","));')
        t = b['test']; k = t.get('kind')
        if k == 'crafter':
            L.append(f'ok("craft {n}",b.craftTime=={t["t"]},b.craftTime);ok("power {n}",close(b.consPower.usage,{j["consumes"]["power"]}),b.consPower.usage);')
            its = split(j['consumes']['items']['items']); L.append(f'var ci=b.findConsumer(c=>c instanceof ConsumeItems);ok("inputs {n}",ci!=null&&ci.items.length=={len(its)}&&' + '&&'.join(f'ci.items.some(s=>s.item.name=="{cname(i)}"&&s.amount=={a})' for i, a in its) + ',ci);')
            if 'liquid' in j['consumes']: L.append(f'var cl=b.findConsumer(c=>c instanceof ConsumeLiquid);ok("liquid {n}",cl!=null&&cl.liquid.name=="{cname(j["consumes"]["liquid"]["liquid"])}"&&close(cl.amount,{j["consumes"]["liquid"]["amount"]}),cl);')
            outs = split(j['outputItems']) if 'outputItems' in j else split([j['outputItem']])
            L.append(f'var os_=b.outputItems;ok("outputs {n}",os_!=null&&os_.length=={len(outs)}&&' + '&&'.join(f'os_.some(s=>s.item.name=="{cname(i)}"&&s.amount=={a})' for i, a in outs) + ',os_);')
        if k == 'generator': L.append(f'ok("prod {n}",close(b.powerProduction,{j["powerProduction"]}),b.powerProduction);ok("dur {n}",b.itemDuration=={j["itemDuration"]},b.itemDuration);')
        if k == 'battery': L.append(f'ok("cap {n}",b.consPower.capacity=={t["cap"]},b.consPower.capacity);')
        if k == 'node': L.append(f'ok("range {n}",b.laserRange=={j["laserRange"]}&&b.maxNodes=={j["maxNodes"]},b.laserRange);')
        if k == 'conveyor': L.append(f'ok("speed {n}",close(b.speed,{j["speed"]})&&b.displayedSpeed=={j["displayedSpeed"]},b.speed);')
        if k == 'drill': L.append(f'ok("drill {n}",b.tier=={j["tier"]}&&b.drillTime=={j["drillTime"]},b.tier+"/"+b.drillTime);')
        if k in ('turret', 'aa'):
            if 'ammoTypes' in j:
                L.append(f'ok("ammo {n}",b.ammoTypes.size=={len(j["ammoTypes"])},b.ammoTypes.size);')
                for ai, bt in j['ammoTypes'].items(): L.append(f'var bb=b.ammoTypes.get(it("{cname(ai)}"));ok("ammo {n}/{ai}",bb!=null&&close(bb.damage,{bt["damage"]}),bb&&bb.damage);')
            else: L.append(f'ok("shoot {n}",b.shootType!=null&&close(b.shootType.damage,{j["shootType"]["damage"]}),b.shootType);')
            L.append(f'ok("range {n}",close(b.range,{j["range"]})&&close(b.reload,{j["reload"]}),b.range+"/"+b.reload);')
    for n, u in spec.UNITS.items():
        L.append(f'var u=un("magnetics-{n}");ok("unit {n}",u!=null&&u.health=={u["health"]}&&u.flying&&u.weapons.size>0,u);')
        L.append(f'var f=bl("magnetics-magnet-factory");ok("plan {n}",f.plans.find(p=>p.unit==u&&p.time=={u["plan"]["time"]})!=null,f.plans.size);ok("tech {n}",par(u)=="magnetics-magnet-factory",par(u));')
    L.append('R.filter(r=>r.startsWith("FAIL")).join(" ; ")+" ||| всего "+R.length+", провалов "+R.filter(r=>r.startsWith("FAIL")).length')
    return ' '.join(L)
def run_static():
    out = mdt.run(['js ' + static_js()], MOD, wait=12, tail=2)
    return [l for l in out if 'всего' in l or '[E]' in l or 'Error' in l]
if __name__ == '__main__':
    print('\n'.join(run_static()))
