`timescale 1ps/1ps
module tb_registered_reply;
 reg clk=0,reset_n=0,arm=0,dir=0,offer=0;
 reg [49:0] metadata=0;
 wire [7:0] out_old,out_zero,out_one;
 wire done_old,done_zero,done_one,started_old,started_zero,started_one;
 wire error_old,error_zero,error_one,progress_old,progress_zero,progress_one;
 wire [5:0] row_old,row_zero,row_one;
 wire [9:0] address_old,address_zero,address_one;
 wire enable_old,enable_zero,enable_one;
 reg [15:0] color_old=0,color_zero=0,color_one=0,depth_old=0,depth_zero=0,depth_one=0;
 reg [7:0] header[0:5],expected[0:2065];
 integer plane=0,packets=0,i,j,kind,seqcase,count;
 reg [15:0] crc;
 function [15:0] color_word(input [9:0] a);begin color_word=(a*197)^16'ha753;end endfunction
 function [15:0] depth_word(input [9:0] a);begin depth_word=(a*313)^16'h5ca7;end endfunction
 function [7:0] row_value(input [5:0] a);begin row_value=(a*73)^8'ha5^(plane?8'h5a:8'h00);end endfunction
 wire [7:0] byte_old=row_value(row_old),byte_zero=row_value(row_zero),byte_one=row_value(row_one);
 link_reply_raw_legacy old(clk,reset_n,arm,dir,offer,metadata,byte_old,color_old,depth_old,
   out_old,done_old,started_old,error_old,progress_old,row_old,address_old,enable_old);
 link_reply_raw unchanged(clk,reset_n,arm,dir,offer,metadata,byte_zero,color_zero,depth_zero,
   out_zero,done_zero,started_zero,error_zero,progress_zero,row_zero,address_zero,enable_zero);
 link_reply_raw #(.REGISTER_OUTPUT(1)) registered(clk,reset_n,arm,dir,offer,metadata,byte_one,color_one,depth_one,
   out_one,done_one,started_one,error_one,progress_one,row_one,address_one,enable_one);
 always @(posedge clk) begin
  if(enable_old)begin color_old<=color_word(address_old);depth_old<=depth_word(address_old);end
  if(enable_zero)begin color_zero<=color_word(address_zero);depth_zero<=depth_word(address_zero);end
  if(enable_one)begin color_one<=color_word(address_one);depth_one<=depth_word(address_one);end
 end
 task legacy_equivalent;
  begin
   if({out_old,done_old,started_old,error_old,progress_old,row_old,address_old,enable_old}!==
      {out_zero,done_zero,started_zero,error_zero,progress_zero,row_zero,address_zero,enable_zero})
    $fatal(1,"default0 differs from frozen legacy waveform packet%0d",packets);
  end
 endtask
 task pulse;
  begin #12500;clk=1;#1;legacy_equivalent();#12499;clk=0;#1;legacy_equivalent();end
 endtask
 function [15:0] crc_byte(input [15:0] c,input [7:0] b);
  reg [15:0] v;integer k;
  begin v=c^{b,8'h00};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
 endfunction
 task make;
  input integer mode,selected_plane,seqno;
  reg [15:0] word;
  begin
   plane=selected_plane;
   header[0]=8'h5a;header[1]=seqno&7;header[2]=seqno;header[3]=2;header[4]=(seqno*7)&31;header[5]=plane;
   metadata={mode==2,mode!=0,header[5],header[4],header[3],header[2],header[1],header[0]};
   for(j=0;j<8;j=j+1)expected[j]=8'hc3;
   crc=16'hffff;
   for(j=0;j<6;j=j+1)begin expected[j+8]=header[j];crc=crc_byte(crc,header[j]);end
   expected[14]=crc[7:0];expected[15]=crc[15:8];
   count=mode==2?2066:mode==1?82:16;
   for(j=16;j<count-2;j=j+1)begin
    if(mode==2)begin
     word=plane?depth_word((j-16)/2):color_word((j-16)/2);
     expected[j]=j[0]?word[15:8]:word[7:0];
    end else expected[j]=row_value(j-16);
    crc=crc_byte(crc,expected[j]);
   end
   if(mode!=0)begin expected[count-2]=crc[7:0];expected[count-1]=crc[15:8];end
  end
 endtask
 task reset_offer;
  begin
   offer=0;dir=0;repeat(3)pulse();
   if(out_one!==8'hc3 || registered.retiring || done_one || error_one)$fatal(1,"offer reset failed");
  end
 endtask
 initial begin
  #1;reset_n=1;arm=1;
  for(kind=0;kind<3;kind=kind+1)for(plane=0;plane<2;plane=plane+1)for(seqcase=0;seqcase<3;seqcase=seqcase+1)begin
   reset_offer();
   // Metadata changes just before offer with the clock stopped, exercising
   // both settling stages and the actual third-edge RAM prime.
   make(kind,plane,seqcase*83+plane*17);#1;offer=1;dir=1;
   for(i=0;i<count;i=i+1)begin
    #1;
    if(out_old!==expected[i] || out_zero!==expected[i] || out_one!==expected[i])
     $fatal(1,"byte mismatch packet%0d mode%0d byte%0d old%h zero%h one%h expected%h",packets,kind,i,out_old,out_zero,out_one,expected[i]);
    if(done_one || done_old)$fatal(1,"done before last physical sample");
    pulse();
    if(error_one || error_old)$fatal(1,"unexpected RAM tag error");
    if(i==count-2 && (!registered.retiring || done_one))$fatal(1,"CRC_HI not parked for retirement");
    if(i==count-1 && (!done_one || !done_old || enable_one))$fatal(1,"last sample did not retire immediately");
   end
   packets=packets+1;
  end
  reset_offer();make(2,0,199);offer=1;dir=1;
  repeat(15)pulse();
  force registered.current_valid=0;pulse();
  if(!done_one || !error_one || registered.retiring || out_one!==8'hc3)$fatal(1,"RAM tag error did not abort immediately");
  release registered.current_valid;
  reset_offer();make(2,1,201);offer=1;dir=1;repeat(7)pulse();dir=0;pulse();
  if(!done_one || !error_one || registered.retiring || out_one!==8'hc3)$fatal(1,"DIR abort state wrong");
  reset_offer();make(2,0,202);offer=1;dir=1;repeat(11)pulse();
  reset_n=0;#1;
  if(out_one!==8'hc3 || done_one || error_one || registered.retiring)$fatal(1,"stopped-clock reset failed");
  legacy_equivalent();
  $display("REGISTERED_REPLY PASS packets%0d all ROW/TILE color/depth bytes, prefix8, CRC, last-edge retirement, late metadata, RAM tags, offer/DIR/reset; legacy0 waveform identical",packets);
  $finish;
 end
 initial begin #10000000000;$fatal(1,"registered reply watchdog");end
endmodule
