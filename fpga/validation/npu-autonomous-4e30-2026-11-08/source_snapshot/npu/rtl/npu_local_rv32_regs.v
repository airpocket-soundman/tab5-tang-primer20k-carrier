// Official PicoRV32 register-file hook; distributed RAM preserves scarce BSRAM.
module npu_local_rv32_regs(input wire clk,wen,input wire[5:0]waddr,raddr1,raddr2,input wire[31:0]wdata,output wire[31:0]rdata1,rdata2);
 reg[31:0]words[0:31] /* synthesis syn_ramstyle="distributed_ram" */;
 always @(posedge clk)if(wen&&waddr[5]==0&&waddr[4:0]!=0)words[waddr[4:0]]<=wdata;
 assign rdata1=raddr1[5]||raddr1[4:0]==0?32'd0:words[raddr1[4:0]];
 assign rdata2=raddr2[5]||raddr2[4:0]==0?32'd0:words[raddr2[4:0]];
endmodule
