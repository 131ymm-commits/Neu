var ys=[15,50,85,150,185],names=["gauss-alloy","gauss-thorium","lancer","salvo-graphite","ripple-graphite"],o=[];
for(var k=0;k<5;k++){var y=ys[k],hp=0,n=0;Groups.unit.each(u=>{if(u.team==Team.crux&&Math.abs(u.y/8-y)<7){hp+=u.health+u.shield;n++}});o.push(names[k]+": alive="+n+" hp_left="+Math.round(hp))}
"t="+Math.round(Vars.state.tick)+" "+o.join(" | ")
