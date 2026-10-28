// Portable link-test core only. No package pins or DDR3 controller assumed.
// DIR=0: host writes on rising bus_clk. DIR=1: host samples then pulses.
module link_bringup #(
    parameter TIMEOUT_CYCLES = 2700000
)(input wire sys_clk, input wire reset_n, input wire arm,
  input wire bus_clk, input wire dir, input wire [7:0] data_i,
  output reg [7:0] data_o, output wire data_oe, output wire ready);
    reg [2:0] clk_sync;
    reg [1:0] dir_sync;
    wire rise = clk_sync[1] & ~clk_sync[2];
    reg [7:0] req[0:6];
    reg [7:0] reply[0:5];
    reg [2:0] rx_index, tx_index;
    reg valid;
    reg [15:0] rx_crc;
    reg [31:0] idle_count;
    reg [15:0] reply_crc;
    integer j;
    function [15:0] crc_byte;
        input [15:0] c;
        input [7:0] b;
        reg [15:0] v;
        integer k;
        begin
            v=c ^ {b,8'h00};
            for(k=0;k<8;k=k+1) v=v[15] ? (v<<1)^16'h1021 : v<<1;
            crc_byte=v;
        end
    endfunction
    // raw DIR/reset/arm immediately remove output; synchronized DIR enables it.
    assign data_oe=reset_n && arm && dir && dir_sync[1] && valid;
    assign ready=reset_n && arm && valid;
    always @* begin
        reply_crc=16'hffff;
        for(j=0;j<6;j=j+1) reply_crc=crc_byte(reply_crc,reply[j]);
        case(tx_index)
            6: data_o=reply_crc[7:0];
            7: data_o=reply_crc[15:8];
            default: data_o=reply[tx_index];
        endcase
    end
    always @(posedge sys_clk or negedge reset_n) begin
        if(!reset_n) begin
            clk_sync<=0; dir_sync<=0; rx_index<=0; tx_index<=0;
            valid<=0; rx_crc<=16'hffff; idle_count<=0;
        end else begin
            clk_sync<={clk_sync[1:0],bus_clk}; dir_sync<={dir_sync[0],dir};
            if(!arm) begin
                valid<=0; rx_index<=0; tx_index<=0; rx_crc<=16'hffff; idle_count<=0;
            end else if(idle_count>=TIMEOUT_CYCLES-1) begin
                valid<=0; rx_index<=0; tx_index<=0; rx_crc<=16'hffff; idle_count<=0;
            end else begin
                idle_count<=idle_count+1;
                if(dir_sync[1] && rx_index!=0) begin rx_index<=0; rx_crc<=16'hffff; end
                if(rise) begin
                    idle_count<=0;
                    if(!dir_sync[1] && !dir && !valid) begin
                        if(rx_index<7) req[rx_index]<=data_i;
                        if(rx_index<6) rx_crc<=crc_byte(rx_crc,data_i);
                        if(rx_index==7) begin
                            rx_index<=0; rx_crc<=16'hffff;
                            reply[0]<=8'h5a; reply[2]<=req[2]; reply[3]<=2;
                            reply[4]<=0; reply[5]<=0; tx_index<=0; valid<=1;
                            if(req[0]!=8'ha5 || req[3]!=2 || req[6]!=rx_crc[7:0] || data_i!=rx_crc[15:8]) reply[1]<=1;
                            else case(req[1])
                                1: begin reply[1]<=0; reply[4]<=8'h54; reply[5]<=8'h50; end
                                2: begin reply[1]<=0; reply[4]<=req[4]; reply[5]<=req[5]; end
                                3: begin reply[1]<=0; reply[4]<=~req[4]; reply[5]<=~req[5]; end
                                default: reply[1]<=2;
                            endcase
                        end else rx_index<=rx_index+1'b1;
                    end else if(dir_sync[1] && dir && valid) begin
                        if(tx_index==7) begin valid<=0; tx_index<=0; end
                        else tx_index<=tx_index+1'b1;
                    end
                end
            end
        end
    end
endmodule
