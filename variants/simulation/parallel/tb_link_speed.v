`timescale 1ns/1ps
module tb_link_speed;
  parameter DATA_DELAY=100,CLOCK_DELAY=100,DIR_DELAY=100;
  reg sys_clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
  reg [7:0] host_data=0;
  wire bus_clk_core,dir_core,ready_core,ready;
  tri [7:0] core_bus;
  wire [7:0] host_received;
  assign #(CLOCK_DELAY) bus_clk_core=bus_clk;
  assign #(DIR_DELAY) dir_core=dir;
  assign #(DATA_DELAY) core_bus=host_oe ? host_data : 8'bz;
  assign #(DATA_DELAY) host_received=core_bus;
  assign #(DATA_DELAY) ready=ready_core;
  always #18.5185185 sys_clk=~sys_clk;
  link_bus_wrapper dut(sys_clk,reset_n,arm,bus_clk_core,dir_core,core_bus,ready_core);
  reg [7:0] q[0:7],r[0:7];
  reg [31:0] rng=32'h17a23b49;
  integer hz=1000000,phase_ps=0,t,n,ret;
  real half;
  always @(posedge sys_clk) if(reset_n && host_oe && dut.oe) $fatal(1,"bus contention");
  function [15:0] crc_byte;
    input [15:0] c;input [7:0] b;
    reg [15:0] v;integer k;
    begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
  endfunction
  task pulse;
    begin
      #(half);bus_clk=1;
      // Exercise the minimum250ns hold, rather than relying on the entire
      // 500ns high half-cycle of the initial1MHz mode.
      if(host_oe && half>=250)begin #250;host_data=~host_data;#(half-250);end
      else #(half);
      bus_clk=0;
    end
  endtask
  task transact;
    input [7:0] op,a,b;input corrupt;
    reg [15:0] c;integer j;
    begin
      dir=0;#500;host_oe=1;
      q[0]=8'ha5;q[1]=op;q[2]=8'h73;q[3]=2;q[4]=a;q[5]=b;
      c=16'hffff;for(j=0;j<6;j=j+1)c=crc_byte(c,q[j]);
      q[6]=c[7:0]^corrupt;q[7]=c[15:8];
      for(j=0;j<8;j=j+1)begin host_data=q[j];pulse();end
      host_oe=0;#500;dir=1;#500;
      if(!ready || !dut.oe)$fatal(1,"response missing");
      for(j=0;j<8;j=j+1)begin r[j]=host_received;pulse();end
      dir=0;#500;
      if(ready || dut.oe)$fatal(1,"response not released");
      c=16'hffff;for(j=0;j<6;j=j+1)c=crc_byte(c,r[j]);
      if(r[0]!==8'h5a || r[2]!==8'h73 || r[3]!==2 || r[6]!==c[7:0] || r[7]!==c[15:8])$fatal(1,"response envelope/CRC");
      if(corrupt)begin if(r[1]!==1)$fatal(1,"bad request CRC accepted");end
      else if(op==2)begin if(r[1]!==0 || r[4]!==a || r[5]!==b)$fatal(1,"echo mismatch");end
      else if(op==3)begin if(r[1]!==0 || r[4]!==~a || r[5]!==~b)$fatal(1,"invert mismatch");end
      else if(op==1)begin if(r[1]!==0 || r[4]!==8'h54 || r[5]!==8'h50)$fatal(1,"ID mismatch");end
      else if(r[1]!==2)$fatal(1,"unknown operation accepted");
    end
  endtask
  initial begin
    ret=$value$plusargs("HZ=%d",hz);ret=$value$plusargs("PHASE_PS=%d",phase_ps);
    half=5.0e8/hz;
    #(phase_ps*0.001);#100;reset_n=1;#100;
    if(dut.oe || ready)$fatal(1,"unarmed drives bus");
    arm=1;#500;
    transact(1,0,0,0);
    for(n=0;n<32;n=n+1)begin
      rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
      transact(2,rng[7:0],rng[15:8],0);transact(3,n,255-n,0);
    end
    transact(2,8'hff,0,0);transact(2,0,8'hff,0);
    transact(2,1,2,1);transact(99,1,2,0);
    // Raw direction/arm/reset remove Core output asynchronously.
    dir=1;#500;arm=0;#1;if(dut.oe || ready_core)$fatal(1,"disarm release");
    #100;reset_n=0;#1;if(dut.oe || ready_core)$fatal(1,"reset release");
    $display("PASS speed HZ=%0d phase_ps=%0d sysclk=27MHz 69transactions CRC/random/invert/turnaround",hz,phase_ps);
    $finish;
  end
  initial begin #4000000;$fatal(1,"watchdog");end
endmodule
