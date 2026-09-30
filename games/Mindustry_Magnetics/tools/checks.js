var R=[];function ok(n,c,v){R.push((c?"OK ":"FAIL ")+n+(c?"":" got="+v))}
var b=function(n){return Vars.content.block("magnetics-"+n)},it=function(n){return Vars.content.item("magnetics-"+n)};
var A=it("magnet-alloy"),S=it("superconductor");ok("items",A!=null&&S!=null,A);
var f=b("induction-furnace");ok("furnace out",f.outputItem.item==A&&f.outputItem.amount==1,f.outputItem);ok("furnace time",f.craftTime==60,f.craftTime);ok("furnace power",Math.abs(f.consPower.usage-1.2)<1e-4,f.consPower.usage);
var ci=f.findConsumer(c=>c instanceof ConsumeItems);ok("furnace items",ci!=null&&ci.items.length==2&&ci.items[0].item==Items.titanium&&ci.items[0].amount==2,ci);
var c=b("cryo-chamber");var cl=c.findConsumer(x=>x instanceof ConsumeLiquid);ok("cryo liquid",cl!=null&&cl.liquid==Liquids.cryofluid&&Math.abs(cl.amount-0.12)<1e-4,cl);ok("cryo out",c.outputItem.item==S,c.outputItem);
var cv=b("mag-conveyor");ok("conv speed",Math.abs(cv.speed-0.11)<1e-4,cv.speed);ok("conv disp",cv.displayedSpeed==16,cv.displayedSpeed);
var w=b("magnet-wall"),wl=b("magnet-wall-large");ok("wall hp",w.health==640&&wl.health==2560,w.health+"/"+wl.health);ok("wall defl",w.chanceDeflect==5,w.chanceDeflect);
var g=b("gauss");ok("gauss ammo n",g.ammoTypes.size==2,g.ammoTypes.size);var ga=g.ammoTypes.get(A);ok("gauss alloy dmg",ga!=null&&ga.damage==110&&ga.pierceCap==3,ga);ok("gauss range",g.range==280,g.range);
ok("gauss coolant",g.coolant!=null,g.coolant);ok("gauss bullet reach",ga.speed*ga.lifetime>=g.range,ga.speed*ga.lifetime);
var n=b("superconducting-node");ok("node range",n.laserRange==22&&n.maxNodes==20,n.laserRange);
var bt=b("superconducting-battery");ok("battery cap",bt.consPower.capacity==150000,bt.consPower.capacity);
var tn=function(x){var t=x.techNode;return t==null?"нет":(t.parent==null?"корень":t.parent.content.name)};
ok("tech furnace",tn(f)=="silicon-smelter",tn(f));ok("tech cryo",tn(c)=="magnetics-induction-furnace",tn(c));ok("tech gauss",tn(g)=="lancer",tn(g));ok("tech conv",tn(cv)=="titanium-conveyor",tn(cv));ok("tech battery",tn(bt)=="battery-large",tn(bt));ok("tech alloy",tn(A)=="titanium",tn(A));ok("tech sc",tn(S)=="magnetics-magnet-alloy",tn(S));
[f,c,cv,w,wl,g,n,bt].forEach(x=>ok("visible "+x.name,x.isVisible()&&x.requirements.length>0,x.buildVisibility));
R.join(" ; ")
