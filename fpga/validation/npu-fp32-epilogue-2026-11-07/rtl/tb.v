
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,abort=0,in_valid=0,out_ready=0,bias_enable=0;
reg signed[31:0] accumulator;reg[31:0] row_scale,column_scale,alpha,bias;
wire in_ready,out_valid,error;wire[31:0] result;wire[3:0] error_code;
npu_fp32_epilogue dut(clk,reset_n,abort,in_valid,in_ready,accumulator,row_scale,column_scale,alpha,bias,bias_enable,out_valid,out_ready,result,error,error_code);
integer f,scan,id,expected_error,en,n=0,t;reg[31:0] expected,saved;reg[3:0] saved_error;
task cycle;begin @(posedge clk);#1;end endtask
initial begin
 repeat(2)cycle;@(negedge clk);reset_n=1;
 f=$fopen("D:/GitHub/airpocket-soundman/tab5-tang-primer20k-carrier-resume-20261106/fpga/build/npu-fp32-epilogue/vectors.txt","r");if(!f)$fatal(1,"vectors missing");
 while(!$feof(f))begin
  scan=$fscanf(f,"%d %h %h %h %h %h %d %h %d\n",id,accumulator,row_scale,column_scale,alpha,bias,en,expected,expected_error);
  if(scan==9)begin
   bias_enable=en;
   // Abort dominates acceptance, even with both handshake inputs high.
   if(id%97==0)begin
    @(negedge clk);abort=1;in_valid=1;out_ready=1;cycle;
    if(out_valid||in_ready)$fatal(1,"abort input dominance");
    @(negedge clk);abort=0;in_valid=0;out_ready=0;cycle;
    if(out_valid)$fatal(1,"stale output after abort");
   end
   @(negedge clk);in_valid=1;cycle;if(!dut.state&&!out_valid)$fatal(1,"not accepted");
   @(negedge clk);in_valid=0;
   // Abort each in-flight phase, then retry the same vector.
   if(id%101==0)begin
    repeat(id%4)cycle;
    @(negedge clk);abort=1;out_ready=1;in_valid=1;cycle;
    if(out_valid)$fatal(1,"abort pending dominance");
    @(negedge clk);abort=0;out_ready=0;in_valid=0;cycle;
    if(out_valid)$fatal(1,"abort stale");
    @(negedge clk);in_valid=1;cycle;@(negedge clk);in_valid=0;
   end
   if(id%107==0)begin
    cycle;@(negedge clk);reset_n=0;in_valid=1;out_ready=1;cycle;
    if(out_valid||in_ready)$fatal(1,"reset pending dominance");
    @(negedge clk);reset_n=1;in_valid=0;out_ready=0;cycle;
    if(out_valid)$fatal(1,"reset pending stale");
    @(negedge clk);in_valid=1;cycle;@(negedge clk);in_valid=0;
   end
   t=0;while(!out_valid&&t<12)begin cycle;t=t+1;end
   if(!out_valid||error_code!==expected_error||error!==(expected_error!=0)||result!==expected)
    $fatal(1,"case %0d result %h expected %h error %0d expected %0d",id,result,expected,error_code,expected_error);
   saved=result;saved_error=error_code;
   repeat(3)begin cycle;if(!out_valid||in_ready||result!==saved||error_code!==saved_error)$fatal(1,"backpressure unstable");end
   if(id%103==0)begin
    @(negedge clk);reset_n=0;in_valid=1;out_ready=1;cycle;
    if(out_valid||in_ready)$fatal(1,"reset publication dominance");
    @(negedge clk);reset_n=1;in_valid=0;out_ready=0;cycle;if(out_valid)$fatal(1,"reset stale");
   end else begin @(negedge clk);out_ready=1;cycle;@(negedge clk);out_ready=0;end
   n=n+1;
  end
 end
 $display("PASS FP32 epilogue vectors=%0d RNE/profile/backpressure/abort/reset",n);$finish;
end
initial begin #100000000;$fatal(1,"timeout");end
endmodule
