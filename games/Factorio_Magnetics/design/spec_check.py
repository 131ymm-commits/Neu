"""Static check of the FINAL_SPEC tech tree: every ingredient of every unlocked recipe must be
craftable from recipes enabled at start or unlocked in the tech's transitive prerequisites.
Uses the 2.0.77 data.raw dumps (base, full SA)."""
import json, sys
P='/tmp/claude-0/-home-user-Neu/5dc61be6-6c38-58c2-939b-4b416832b0f1/scratchpad/fx/'
M='magnetics-'
def m(x): return x if x in RAWV else (M+x)
RAWV=set()
# recipes: name -> (category, ingredients{name:amt}, results)
R = {
 'ferrite': ('magnetics-sintering', {'iron-ore':1,'stone':1}, ['ferrite']),
 'coil': ('magnetics-winding', {'ferrite':1,'copper-cable':4}, ['coil']),
 'magnet-alloy': ('magnetics-induction', {'steel-plate':1,'ferrite':2,'copper-plate':1}, ['magnet-alloy']),
 'ferrofluid': ('chemistry', {'ferrite':1,'light-oil':10}, ['ferrofluid']),
 'liquid-nitrogen': ('magnetics-cryogenics', {}, ['liquid-nitrogen']),
 'superconducting-cable': ('magnetics-cryogenics', {'magnet-alloy':1,'copper-cable':6,'plastic-bar':1,'liquid-nitrogen':20}, ['superconducting-cable']),
 'flux-crystal-growth': ('magnetics-cryogenics', {'superconducting-cable':2,'processing-unit':1,'uranium-238':1,'ferrofluid':20,'liquid-nitrogen':50}, ['flux-crystal-uncharged']),
 'flux-crystal-charging': ('magnetics-resonance', {'flux-crystal-uncharged':1}, ['flux-crystal']),
 'stone-separation': ('magnetics-separation', {'stone':10,'ferrofluid':5}, ['iron-ore','copper-ore']),
 'ferrite-slug': ('crafting', {'ferrite':6,'copper-plate':2}, ['ferrite-slug']),
 'magnet-slug': ('crafting', {'ferrite-slug':1,'magnet-alloy':1}, ['magnet-slug']),
 'gauss-slug': ('crafting', {'magnet-alloy':2,'steel-plate':1}, ['gauss-slug']),
 'rail-slug': ('crafting', {'superconducting-cable':1,'magnet-alloy':2,'steel-plate':2}, ['rail-slug']),
 'flux-rail-slug': ('crafting', {'rail-slug':1,'flux-crystal':1}, ['flux-rail-slug']),
 'sintering-kiln': ('crafting', {'stone-furnace':1,'iron-gear-wheel':2,'stone-brick':5}, ['sintering-kiln']),
 'induction-furnace': ('crafting', {'steel-plate':10,'advanced-circuit':5,'stone-brick':10,'coil':10}, ['induction-furnace']),
 'coil-winder': ('crafting', {'assembling-machine-2':1,'ferrite':10,'copper-cable':20}, ['coil-winder']),
 'cryo-chamber': ('crafting', {'chemical-plant':1,'magnet-alloy':10,'coil':10,'pipe':10}, ['cryo-chamber']),
 'flux-resonator': ('crafting', {'centrifuge':1,'superconducting-cable':50,'processing-unit':20}, ['flux-resonator']),
 'magnetic-separator': ('crafting', {'steel-plate':10,'magnet-alloy':10,'coil':20,'advanced-circuit':5,'iron-gear-wheel':10}, ['magnetic-separator']),
 'magnetic-drill': ('crafting', {'electric-mining-drill':1,'magnet-alloy':5,'coil':5,'advanced-circuit':2}, ['magnetic-drill']),
 'maglev-transport-belt': ('crafting-with-fluid', {'TOP-transport-belt':1,'superconducting-cable':1,'magnet-alloy':1,'ferrofluid':20}, ['maglev-transport-belt']),
 'maglev-underground-belt': ('crafting-with-fluid', {'TOP-underground-belt':2,'magnet-alloy':20,'superconducting-cable':10,'ferrofluid':40}, ['maglev-underground-belt']),
 'maglev-splitter': ('crafting-with-fluid', {'TOP-splitter':1,'superconducting-cable':5,'magnet-alloy':10,'processing-unit':2,'ferrofluid':80}, ['maglev-splitter']),
 'coil-capacitor': ('crafting', {'coil':5,'steel-plate':2,'electronic-circuit':2}, ['coil-capacitor']),
 'superconducting-accumulator': ('crafting', {'accumulator':1,'superconducting-cable':10,'magnet-alloy':5}, ['superconducting-accumulator']),
 'superconducting-pylon': ('crafting', {'big-electric-pole':1,'superconducting-cable':2,'steel-plate':2}, ['superconducting-pylon']),
 'mhd-generator': ('crafting', {'steel-plate':20,'coil':20,'magnet-alloy':10,'advanced-circuit':10}, ['mhd-generator']),
 'flux-dynamo': ('crafting', {'steel-plate':20,'superconducting-cable':20,'coil':20,'processing-unit':10}, ['flux-dynamo']),
 'geomagnetic-coil': ('crafting', {'magnet-alloy':4,'coil':10,'steel-plate':5,'electronic-circuit':5}, ['geomagnetic-coil']),
 'ferrite-wall': ('crafting', {'stone-wall':1,'ferrite':2}, ['ferrite-wall']),
 'magnet-wall': ('crafting', {'ferrite-wall':1,'magnet-alloy':1,'steel-plate':1}, ['magnet-wall']),
 'superconducting-wall': ('crafting', {'magnet-wall':1,'superconducting-cable':1,'refined-concrete':4}, ['superconducting-wall']),
 'magnet-gate': ('crafting', {'magnet-wall':1,'steel-plate':2,'electronic-circuit':2}, ['magnet-gate']),
 'superconducting-gate': ('crafting', {'magnet-gate':1,'superconducting-cable':1,'refined-concrete':4}, ['superconducting-gate']),
 'mend-coil': ('crafting', {'steel-plate':10,'coil':20,'repair-pack':10,'advanced-circuit':5}, ['mend-coil']),
 'coilgun-turret': ('crafting', {'gun-turret':1,'coil':10,'ferrite':10,'electronic-circuit':5}, ['coilgun-turret']),
 'gauss-turret': ('crafting', {'steel-plate':20,'magnet-alloy':10,'coil':20,'advanced-circuit':10}, ['gauss-turret']),
 'arc-emitter': ('crafting', {'laser-turret':1,'coil':20,'magnet-alloy':10}, ['arc-emitter']),
 'rail-cannon': ('crafting', {'steel-plate':40,'superconducting-cable':20,'coil':30,'magnet-alloy':20,'processing-unit':10}, ['rail-cannon']),
}
T = {
 'ferrite-sintering': (['automation-science-pack','stone-wall'], ['sintering-kiln','ferrite','ferrite-wall']),
 'electromagnetic-coils': (['T:ferrite-sintering','automation-2'], ['coil-winder','coil']),
 'coilgun': (['T:electromagnetic-coils','gun-turret','military-2'], ['coilgun-turret','ferrite-slug']),
 'induction-smelting': (['T:electromagnetic-coils','advanced-material-processing-2'], ['induction-furnace','magnet-alloy']),
 'magnetic-mining': (['T:induction-smelting','electric-mining-drill'], ['magnetic-drill']),
 'magnetic-power': (['T:induction-smelting','solar-energy','electric-energy-accumulators'], ['mhd-generator','coil-capacitor','geomagnetic-coil']),
 'magnetic-separation': (['T:induction-smelting','advanced-oil-processing'], ['ferrofluid','magnetic-separator','stone-separation']),
 'magnetic-fortifications': (['T:coilgun','T:induction-smelting','military-3','gate','repair-pack'], ['magnet-wall','magnet-gate','magnet-slug','gauss-turret','gauss-slug','mend-coil']),
 'arc-emitter': (['T:induction-smelting','laser-turret'], ['arc-emitter']),
 'superconductivity': (['T:induction-smelting','production-science-pack'], ['cryo-chamber','liquid-nitrogen','superconducting-cable']),
 'superconducting-power': (['T:superconductivity','electric-energy-distribution-2','electric-energy-accumulators'], ['superconducting-accumulator','superconducting-pylon']),
 'flux-energy': (['T:superconducting-power','T:magnetic-separation','utility-science-pack','uranium-processing'], ['flux-resonator','flux-dynamo','flux-crystal-growth','flux-crystal-charging']),
 'maglev-logistics': (['logistics-3','T:superconductivity','T:magnetic-separation','utility-science-pack'], ['maglev-transport-belt','maglev-underground-belt','maglev-splitter']),
 'superconducting-defense': (['T:magnetic-fortifications','T:flux-energy','military-4','concrete'], ['superconducting-wall','superconducting-gate','rail-cannon','rail-slug','flux-rail-slug']),
}
def check(cfg):
    d=json.load(open(P+('raw_base.json' if cfg=='base' else 'raw_sa.json')))
    VR=d['recipe']; VT=d['technology']; sa = cfg!='base'
    ITEMS=set(d['fluid'])
    for t,v in d.items():
        if isinstance(v,dict):
            for n,p in v.items():
                if isinstance(p,dict) and 'stack_size' in p: ITEMS.add(n)
    produced=set()
    for r in VR.values():
        for x in (r.get('results') or []): produced.add(x['name'])
    NATURAL=set()
    for t in ('resource','tree','plant','simple-entity','fish','asteroid-chunk'):
        for n,p in (d.get(t) or {}).items():
            mm=p.get('minable') or {}
            if mm.get('result'): NATURAL.add(mm['result'])
            for x in (mm.get('results') or []): NATURAL.add(x['name'])
    for n,p in (d.get('asteroid-chunk') or {}).items(): NATURAL.add(n)
    for n,p in (d.get('tile') or {}).items():
        if p.get('fluid'): NATURAL.add(p['fluid'])
    NATURAL.add('water'); NATURAL.add('spoilage')
    top = 'turbo' if sa else 'express'
    Tl = {k:(list(v[0]),v[1]) for k,v in T.items()}
    if sa: Tl['maglev-logistics'][0].extend(['turbo-transport-belt','electromagnetic-science-pack'])
    def prods(r):
        res=r.get('results') or []
        return [x['name'] for x in res]
    def ings(r): return [x['name'] for x in (r.get('ingredients') or [])]
    unlock={}
    for tn,t in VT.items():
        for e in (t.get('effects') or []):
            if e.get('type')=='unlock-recipe': unlock.setdefault(tn,[]).append(e['recipe'])
    start=[n for n,r in VR.items() if r.get('enabled',True) and not r.get('hidden') and not r.get('parameter')]
    def closure(tn, seen=None):
        seen = seen if seen is not None else set()
        if tn in seen: return seen
        seen.add(tn)
        pre = Tl[tn[2:]][0] if tn.startswith('T:') else (VT[tn].get('prerequisites') or [])
        for p in pre:
            if not p.startswith('T:') and p not in VT: raise SystemExit(f'{cfg}: missing vanilla tech {p}')
            closure(p, seen)
        return seen
    bad=0
    for tn in Tl:
        C=closure('T:'+tn)
        vrec=list(start); mrec=[]
        for c in C:
            if c.startswith('T:'): mrec+=Tl[c[2:]][1]
            else: vrec+=unlock.get(c,[])
        avail=set(NATURAL) - {'uranium-ore','crude-oil'} if sa else {'iron-ore','copper-ore','stone','coal','wood','water'}
        if 'uranium-mining' in C: avail.add('uranium-ore')
        changed=True
        allrec=[('v',n) for n in vrec]+[('m',n) for n in mrec]
        while changed:
            changed=False
            for kind,n in allrec:
                if kind=='v':
                    r=VR[n]; ii=ings(r); pp=prods(r)
                    if n=='pumpjack' or 'pumpjack' in pp: avail.add('crude-oil')
                else:
                    cat,ing,res=R[n]; ii=[i.replace('TOP',top) if i.startswith('TOP') else (i if i in VR or i in d['item'] or i in d['fluid'] else i) for i in ing]
                    ii=[(i if i in ITEMS else M+i) for i in ii]; pp=[M+x for x in res]
                if kind=='v' and VR[n].get('category')=='recycling': continue
                if all(i in avail for i in ii):
                    for p in pp:
                        if p not in avail: avail.add(p); changed=True
        for n in Tl[tn][1]:
            cat,ing,res=R[n]
            for i in ing:
                i=i.replace('TOP',top)
                nm = i if i in ITEMS else M+i
                if nm not in avail:
                    bad+=1; print(f'{cfg}: tech {tn}: recipe {n} ingredient {nm} NOT reachable')
            if cat.startswith('magnetics-')==False and cat not in d.get('recipe-category',{}): print(cfg,'missing category',cat); bad+=1
    # every recipe unlocked exactly once
    cnt={}
    for tn,(p,u) in Tl.items():
        for n in u: cnt[n]=cnt.get(n,0)+1
    for n in R:
        if cnt.get(n,0)!=1: print(cfg,'recipe',n,'unlocked',cnt.get(n,0),'times'); bad+=1
    # names vs vanilla
    names=set()
    for f in ('names_base.tsv','names_sa.tsv'):
        for l in open(P+f):
            parts=l.rstrip('\n').split('\t')
            if len(parts)==2: names.add(parts[1])
    for n in list(R)+['magnetics-'+t for t in T]:
        full = n if n.startswith(M) else M+n
        if full in names: print('CLASH',full); bad+=1
    print(cfg,'reachability problems:',bad)
    return bad
b=check('base')+check('sa')
sys.exit(1 if b else 0)
