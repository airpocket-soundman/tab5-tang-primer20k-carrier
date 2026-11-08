
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg resetn=0,pcpi_valid=0,slow_valid=0;reg[31:0]pcpi_insn=0,pcpi_rs1=0,pcpi_rs2=0;
wire pcpi_wr,pcpi_wait,pcpi_ready;wire[31:0]pcpi_rd;
wire slow_wr,slow_wait,slow_ready;wire[31:0]slow_rd;
picorv32_pcpi_fast_mul fast(.*);
picorv32_pcpi_mul iterative(.clk(clk),.resetn(resetn),.pcpi_valid(slow_valid),.pcpi_insn(pcpi_insn),.pcpi_rs1(pcpi_rs1),.pcpi_rs2(pcpi_rs2),.pcpi_wr(slow_wr),.pcpi_rd(slow_rd),.pcpi_wait(slow_wait),.pcpi_ready(slow_ready));
integer fd,rc,op,checked=0,cycles,fast_cycles,slow_cycles,fast_total=0,slow_total=0,fast_max=0,slow_max=0;
reg[31:0]a,b,expected;reg got_fast,got_slow;
initial begin
 repeat(5)@(negedge clk);resetn=1;repeat(3)@(negedge clk);
 fd=$fopen("vectors.txt","r");if(!fd)$fatal(1,"vectors missing");
 while(!$feof(fd))begin
  rc=$fscanf(fd,"%h %h %h %h\n",op,a,b,expected);
  if(rc==4)begin
   pcpi_insn=32'h02000033|(op<<12);pcpi_rs1=a;pcpi_rs2=b;pcpi_valid=1;slow_valid=1;got_fast=0;got_slow=0;cycles=0;
   while(!got_fast||!got_slow)begin
    @(negedge clk);cycles=cycles+1;
    if(pcpi_ready&&!got_fast)begin
     if(!pcpi_wr||pcpi_rd!==expected)$fatal(1,"fast mismatch op%0d a%h b%h actual%h expected%h",op,a,b,pcpi_rd,expected);
     fast_cycles=cycles;got_fast=1;pcpi_valid=0;
    end
    if(slow_ready&&!got_slow)begin
     if(!slow_wr||slow_rd!==expected)$fatal(1,"iterative mismatch");
     slow_cycles=cycles;got_slow=1;slow_valid=0;
    end
    if(cycles>90)$fatal(1,"PCPI timeout");
   end
   checked=checked+1;fast_total=fast_total+fast_cycles;slow_total=slow_total+slow_cycles;
   if(fast_cycles>fast_max)fast_max=fast_cycles;if(slow_cycles>slow_max)slow_max=slow_cycles;
   repeat(4)@(negedge clk);
   if(pcpi_ready||pcpi_wr||slow_ready||slow_wr)$fatal(1,"duplicate completed response");
  end else if(rc!=-1)$fatal(1,"malformed vectors");
 end
 $fclose(fd);
 // Unsupported operations must not be spuriously accepted by the MUL unit.
 pcpi_valid=1;pcpi_insn=32'h00000033;repeat(8)begin @(negedge clk);if(pcpi_ready||pcpi_wr)$fatal(1,"accepted invalid funct7");end
 pcpi_insn=32'h02004033;repeat(8)begin @(negedge clk);if(pcpi_ready||pcpi_wr)$fatal(1,"accepted DIV opcode as MUL");end
 pcpi_insn=32'h02001033;pcpi_rs1=32'h80000000;pcpi_rs2=32'hffffffff;@(negedge clk);resetn=0;pcpi_valid=0;repeat(3)@(negedge clk);
 if(pcpi_ready||pcpi_wr)$fatal(1,"reset failed to drain multiplier");
 if(checked!=1348)$fatal(1,"vector count mismatch");
 $display("PASS MUL/MULH/MULHU/MULHSU independentPythonoracle vectors=%0d fast_total=%0d slow_total=%0d fast_max=%0d slow_max=%0d",checked,fast_total,slow_total,fast_max,slow_max);$finish;
end
endmodule
