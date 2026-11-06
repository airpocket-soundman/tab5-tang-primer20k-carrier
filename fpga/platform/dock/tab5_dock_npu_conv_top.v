module tab5_dock_npu_conv_top(input wire sys_clk,reset_n,arm_sw,bus_clk,dir,input wire[3:0] aux,inout wire[7:0] data,output wire ready,output wire[3:0] led);
 reg[2:0] rs=0,arms=0;reg[23:0] hb=0;wire raw=reset_n&&arm_sw;wire active=raw&&rs[2]&&arms[2];wire[7:0] data_o;wire oe;
 always @(posedge sys_clk or negedge reset_n)if(!reset_n)begin rs<=0;hb<=0;end else begin rs<={rs[1:0],1'b1};hb<=hb+1'b1;end
 always @(posedge sys_clk or negedge raw)if(!raw)arms<=0;else arms<={arms[1:0],1'b1};
 npu_conv_link link(sys_clk,reset_n&&rs[2],active,bus_clk,dir,data,data_o,oe,ready);
 assign data=oe?data_o:8'bz;assign led=~{hb[23],ready,oe,active};
endmodule
