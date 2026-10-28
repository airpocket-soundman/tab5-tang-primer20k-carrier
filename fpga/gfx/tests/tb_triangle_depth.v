`timescale 1ns/1ps
module tb_triangle_depth;
    localparam COUNT=1154;
    reg clk=0,reset_n=0,in_valid=0,out_ready=0;
    reg [383:0] sample=0;
    wire in_ready,out_valid,invalid_input,depth_pass;
    wire [15:0] new_depth;
    wire [63:0] actual={46'b0,depth_pass,invalid_input,new_depth};
    reg [383:0] inputs[0:COUNT-1];
    reg [63:0] expected[0:COUNT-1];
    reg [63:0] held;
    integer n,cycles,k;
    always #5 clk=~clk;
    triangle_depth dut(.clk(clk),.reset_n(reset_n),.in_valid(in_valid),.in_ready(in_ready),
      .covered(sample[0]),.area(sample[383:320]),.weight_a(sample[319:256]),
      .weight_b(sample[255:192]),.weight_c(sample[191:128]),.za(sample[127:112]),
      .zb(sample[111:96]),.zc(sample[95:80]),.old_depth(sample[79:64]),
      .out_valid(out_valid),.out_ready(out_ready),.invalid_input(invalid_input),.depth_pass(depth_pass),.new_depth(new_depth));
    initial begin
      $readmemh("gfx/tests/depth_inputs.mem",inputs);
      $readmemh("gfx/tests/depth_expected.mem",expected);
      #1;reset_n=1;#1;reset_n=0;#1;
      if(in_ready!==0 || out_valid!==0 || actual!==0) $fatal(1,"reset outputs");
      #9;reset_n=1;
      for(n=0;n<COUNT;n=n+1) begin
        @(negedge clk);
        if(!in_ready) $fatal(1,"input not ready %0d",n);
        sample=inputs[n];in_valid=1;out_ready=0;
        @(posedge clk);#1;cycles=0;
        // Try changing inputs while stalled; a request must only be accepted once.
        while(!out_valid) begin
          @(negedge clk);sample=~sample;in_valid=1;
          if(in_ready) $fatal(1,"ready during divide");
          @(posedge clk);#1;cycles=cycles+1;
          if(cycles>49) $fatal(1,"divider latency");
        end
        if(actual!==expected[n]) $fatal(1,"vector %0d got %016x expected %016x",n,actual,expected[n]);
        if(inputs[n][0] && !expected[n][16]) begin
          if(cycles!=49) $fatal(1,"covered latency %0d",cycles);
        end else if(cycles!=0) $fatal(1,"early-result latency");
        held=actual;
        for(k=0;k<3;k=k+1) begin
          @(negedge clk);sample=~sample;in_valid=1;
          @(posedge clk);#1;
          if(!out_valid || in_ready || actual!==held) $fatal(1,"backpressure");
        end
        @(negedge clk);in_valid=0;out_ready=1;
        @(posedge clk);#1;if(out_valid || !in_ready) $fatal(1,"result consume");
      end
      // Abort an active divider with reset and confirm it cannot leak a result.
      @(negedge clk);sample=inputs[0];in_valid=1;out_ready=0;
      @(posedge clk);#1;
      #1;reset_n=0;#1;
      if(out_valid || in_ready || actual!==0) $fatal(1,"busy reset");
      in_valid=0;#1;reset_n=1;
      repeat(55) begin @(posedge clk);#1;if(out_valid) $fatal(1,"stale reset result");end
      $display("PASS triangle_depth: %0d vectors, 49-step exact divide, stall, reset",COUNT);
      $finish;
    end
    initial begin #2000000;$fatal(1,"watchdog");end
endmodule
