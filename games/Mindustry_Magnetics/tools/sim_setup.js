var T=Team.sharded,B=Blocks,m=function(n){return Vars.content.block("magnetics-"+n)},I=function(n){return Vars.content.item("magnetics-"+n)};
for(var x=2;x<70;x++)for(var y=2;y<60;y++){var t=Vars.world.tile(x,y);t.setAir();t.setFloor(B.metalFloor);t.setOverlay(B.air)}
var put=function(bl,x,y,r){Vars.world.tile(x,y).setNet(bl,T,r||0);return Vars.world.tile(x,y).build};
var f=put(m("induction-furnace"),10,10);put(B.itemSource,9,10).outputItem=Items.titanium;put(B.itemSource,9,11).outputItem=Items.silicon;put(B.powerSource,10,12);put(B.vault,13,11);
var c=put(m("cryo-chamber"),10,25);put(B.itemSource,8,24).outputItem=I("magnet-alloy");put(B.itemSource,8,25).outputItem=Items.plastanium;put(B.liquidSource,8,26).source=Liquids.cryofluid;put(B.powerSource,10,27);put(B.vault,13,25);
put(B.itemSource,20,40).outputItem=Items.copper;for(var i=21;i<51;i++)put(m("mag-conveyor"),i,40,0);put(B.vault,52,40);
put(B.itemSource,20,50).outputItem=Items.copper;for(var i=21;i<51;i++)put(B.titaniumConveyor,i,50,0);put(B.vault,52,50);
Vars.state.rules.waves=false;
"setup tick="+Vars.state.tick
