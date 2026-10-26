// Parametric mechanical CONCEPT. Not validated against assembled Tab5/Core.
// Units:mm. The carrier model usesx2..127,y1..79; this cover origin isx2,y1.
// Export only after actual spacer length, Core height and connector access review.
board_x=125;
board_y=78;
wall=2;
clearance=1;
cover_inner_height=20; // placeholder: measure actual tallest part + safe clearance
cover_top=2;
mount_boss_od=7;
mount_hole=3.4;
mounts=[[2.06,2.95],[2.06,74.95],[49.06,2.95],[49.06,74.95],[122.06,2.95],[122.06,74.95]];
// Two halves are intentionally not auto-produced: backplate would obstruct Tab5.
// A protective front cap fastens to separately selected insulating spacers.
module cover(){
 difference(){
  translate([-clearance-wall,-clearance-wall,0])
   cube([board_x+2*(clearance+wall),board_y+2*(clearance+wall),cover_inner_height+cover_top]);
  translate([-clearance,-clearance,-.1])cube([board_x+2*clearance,board_y+2*clearance,cover_inner_height+.1]);
  // Large cable-access openings; final sizes depend on connector drawings/cables.
  translate([-clearance-wall-1,15,-1])cube([wall+clearance+5,45,cover_inner_height]);
  translate([board_x-5,9,-1])cube([wall+clearance+7,23,cover_inner_height]);
  // Ventilation slots over FPGA and power areas; no claimed thermal qualification.
  for(x=[12:8:112])translate([x,24,cover_inner_height-.1])cube([3,30,cover_top+.2]);
  // User access to controls. Must be aligned after mechanical validation.
  for(p=[[12,10],[27,10],[43.5,14]])translate([p[0],p[1],cover_inner_height-.1])cylinder(d=10,h=cover_top+.2,$fn=32);
  for(p=mounts)translate([p[0],p[1],-.1])cylinder(d=mount_hole,h=cover_inner_height+cover_top+.2,$fn=32);
 }
}
cover();
