var T=Team.sharded,E=Team.crux,B=Blocks,m=function(n){return Vars.content.block("magnetics-"+n)},I=function(n){return Vars.content.item("magnetics-"+n)};
var put=function(bl,x,y){Vars.world.tile(x,y).setNet(bl,T,0);return Vars.world.tile(x,y).build};
var lanes=[["gauss-alloy",m("gauss"),I("magnet-alloy")],["gauss-thorium",m("gauss"),Items.thorium],["lancer",B.lancer,null],["salvo-graphite",B.salvo,Items.graphite],["ripple-graphite",B.ripple,Items.graphite]];
var ys=[15,50,85,150,185];
Vars.state.rules.waves=false;
for(var k=0;k<lanes.length;k++){var y=ys[k];
 for(var x=5;x<50;x++)for(var yy=y-6;yy<=y+6;yy++){var t=Vars.world.tile(x,yy);t.setAir();t.setFloor(B.metalFloor);t.setOverlay(B.air)}
 var bl=lanes[k][1],s=bl.size,L=10-Math.floor((s-1)/2)-1,U=y+Math.floor(s/2)+1;put(bl,10,y);
 if(lanes[k][2]!=null){put(B.itemSource,L,y).outputItem=lanes[k][2];}
 put(B.powerSource,10,U);
 put(B.liquidSource,L,U-1);Vars.world.tile(L,U-1).build.source=Liquids.water;
 for(var j=0;j<5;j++){var u=UnitTypes.mace.spawn(E,(10+18)*8,(y-4+2*j)*8);u.apply(StatusEffects.unmoving,1e9);u.apply(StatusEffects.disarmed,1e9);}
}
"ok "+Vars.state.tick
