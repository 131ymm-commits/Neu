var T=Team.sharded,B=Blocks,m=function(n){return Vars.content.block("magnetics-"+n)};
var put=function(bl,x,y){Vars.world.tile(x,y).setNet(bl,T,0);return Vars.world.tile(x,y).build};
for(var x=2;x<70;x++)for(var y=2;y<60;y++){var t=Vars.world.tile(x,y);t.setAir();t.setFloor(B.metalFloor);t.setOverlay(B.air)}
var sp=[0.08,0.09,0.10,0.11];var cv=m("mag-conveyor");
for(var k=0;k<4;k++){var y=10+10*k;put(B.itemSource,5,y).outputItem=Items.copper;for(var i=6;i<36;i++)put(cv,i,y);put(B.vault,37,y+1);}
put(B.itemSource,5,50).outputItem=Items.copper;for(var i=6;i<36;i++)put(B.titaniumConveyor,i,50);put(B.vault,37,51);
"ok"
