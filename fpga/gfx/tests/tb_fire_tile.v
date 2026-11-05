`timescale 1ns/1ps
module tb_fire_tile;
 reg clk=0;always #5 clk=~clk;
 reg reset_n=0,abort=0,start=0;
 reg [15:0] origin_x=0,origin_y=0,width=640,height=360;
 reg [31:0] frame=0;reg [1:0] load=0;
 wire busy,done,write_enable;wire [9:0]write_address;wire[15:0]write_color;
 fire_tile dut(.*);
 reg [15:0] expected[0:65535];
 reg scoring=0;integer offset=0,writes=0,cases=0,cycles=0;
 integer fd,rc,x,y,w,h,f,l,n,expected_writes,total_words;
 reg[4095:0] vector_path,case_path;
 always @(posedge clk) if(scoring && write_enable) begin
  if(write_address!==writes[9:0] || write_color!==expected[offset+writes])
   $fatal(1,"case%0d address%0d got%04x expected%04x",cases,write_address,write_color,expected[offset+writes]);
  writes=writes+1;
 end
 initial begin
  if(!$value$plusargs("vectors=%s",vector_path) || !$value$plusargs("cases=%s",case_path) ||
     !$value$plusargs("words=%d",total_words)) $fatal(1,"missing paths/count");
  if(total_words<1 || total_words>65536)$fatal(1,"invalid vector count");
  $readmemh(vector_path,expected,0,total_words-1);fd=$fopen(case_path,"r");if(!fd)$fatal(1,"cases open failed");
  repeat(3)@(negedge clk);reset_n=1;
  // Abort an in-flight draw. The cancellation edge suppresses RAM writes.
  @(negedge clk);start=1;repeat(1)@(negedge clk);start=0;
  repeat(500)@(negedge clk);abort=1;
  @(negedge clk);abort=0;
  repeat(10)begin @(negedge clk);if(busy || write_enable)$fatal(1,"abort left work active");end
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%d %d %d %d %d %d %d\n",x,y,w,h,f,l,expected_writes);
   if(rc==7)begin
    @(negedge clk);origin_x=x;origin_y=y;width=w;height=h;frame=f;load=l;
    writes=0;scoring=1;start=1;
    @(negedge clk);start=0;cycles=0;
    while(!done)begin
     @(negedge clk);cycles=cycles+1;
     // A second start and changed input pins must not replace a running draw.
     if(cycles==8)begin start=1;origin_x=65535;origin_y=65535;width=0;height=0;frame=123;load=3;end
     if(cycles==9)start=0;
     if(cycles>300000)$fatal(1,"timeout");
    end
    if(writes!=expected_writes)$fatal(1,"wrong write count%0d wanted%0d",writes,expected_writes);
    if(busy)$fatal(1,"done while busy");
    scoring=0;offset=offset+writes;cases=cases+1;
   end
  end
  if(offset!=total_words)$fatal(1,"did not consume all golden pixels");
  $display("fire_tile PASS: %0d cases, %0d exact pixels, abort, busy-start/input isolation",cases,offset);$finish;
 end
endmodule
