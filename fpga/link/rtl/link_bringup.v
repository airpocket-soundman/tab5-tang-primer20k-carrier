// Portable link-test core only. No package pins or DDR3 controller assumed.
// DIR=0: host writes on rising bus_clk. DIR=1: host samples then pulses.
module link_bringup #(
    parameter TIMEOUT_CYCLES = 2700000,
    parameter GFX_ENABLE = 0
)(input wire sys_clk, input wire reset_n, input wire arm,
  input wire bus_clk, input wire dir, input wire [7:0] data_i,
  output reg [7:0] data_o, output wire data_oe, output wire ready);
    reg [2:0] clk_sync;
    reg [1:0] dir_sync;
    wire rise = clk_sync[1] & ~clk_sync[2];
    reg [7:0] req[0:6];
    reg [7:0] reply[0:5];
    reg [2:0] rx_index;
    reg [6:0] tx_index;
    reg valid;
    reg bulk_mode;
    reg [15:0] stream_crc;
    reg [15:0] rx_crc;
    reg [31:0] idle_count;
    reg [15:0] reply_crc;
    reg gfx_start, gfx_pending;
    wire gfx_done;
    wire [7:0] gfx_status;
    wire [15:0] gfx_result;
    wire [7:0] row_byte;
    wire [5:0] row_index = tx_index-7'd8;
    generate if(GFX_ENABLE==2) begin: triangle
        wire renderer_abort = gfx_pending && idle_count >= TIMEOUT_CYCLES-1;
        triangle_tile renderer(sys_clk, reset_n && arm, renderer_abort, gfx_start,
                              req[1], req[4], req[5], gfx_done, gfx_status, gfx_result,
                              row_index, row_byte);
    end else if(GFX_ENABLE) begin: gfx
        // A timed-out operation must not keep mutating RAM or consume a later start.
        wire renderer_reset_n = reset_n && arm;
        wire renderer_abort = gfx_pending && idle_count >= TIMEOUT_CYCLES-1;
        gfx_bench renderer(sys_clk, renderer_reset_n, renderer_abort, gfx_start,
                           req[1], req[4], req[5], gfx_done, gfx_status, gfx_result);
        assign row_byte=8'h00;
    end else begin: no_gfx
        assign gfx_done=1'b0;
        assign gfx_status=8'h02;
        assign gfx_result=16'h0000;
        assign row_byte=8'h00;
    end endgenerate
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
        if(tx_index<6) data_o=reply[tx_index];
        else if(tx_index==6) data_o=reply_crc[7:0];
        else if(tx_index==7) data_o=reply_crc[15:8];
        else if(bulk_mode && tx_index<72) data_o=row_byte;
        else if(bulk_mode && tx_index==72) data_o=stream_crc[7:0];
        else if(bulk_mode && tx_index==73) data_o=stream_crc[15:8];
        else data_o=8'h00;
    end
    always @(posedge sys_clk or negedge reset_n) begin
        if(!reset_n) begin
            clk_sync<=0; dir_sync<=0; rx_index<=0; tx_index<=0;
            valid<=0; rx_crc<=16'hffff; idle_count<=0;
            gfx_start<=0; gfx_pending<=0;
            bulk_mode<=0; stream_crc<=16'hffff;
        end else begin
            gfx_start<=0;
            clk_sync<={clk_sync[1:0],bus_clk}; dir_sync<={dir_sync[0],dir};
            if(!arm) begin
                valid<=0; rx_index<=0; tx_index<=0; rx_crc<=16'hffff; idle_count<=0;
                gfx_pending<=0;
                bulk_mode<=0; stream_crc<=16'hffff;
            end else if(idle_count>=TIMEOUT_CYCLES-1) begin
                valid<=0; rx_index<=0; tx_index<=0; rx_crc<=16'hffff; idle_count<=0;
                gfx_pending<=0;
                bulk_mode<=0; stream_crc<=16'hffff;
            end else begin
                idle_count<=idle_count+1;
                if(gfx_pending && gfx_done) begin
                    reply[1]<=gfx_status; reply[4]<=gfx_result[7:0]; reply[5]<=gfx_result[15:8];
                    valid<=1; gfx_pending<=0;
                    bulk_mode<=GFX_ENABLE==2 && req[1]==8'h2f && gfx_status==0;
                end
                if(dir_sync[1] && rx_index!=0) begin rx_index<=0; rx_crc<=16'hffff; end
                if(rise) begin
                    idle_count<=0;
                    if(!dir_sync[1] && !dir && !valid && !gfx_pending) begin
                        if(rx_index==0) begin bulk_mode<=0; stream_crc<=16'hffff; end
                        if(rx_index<7) req[rx_index]<=data_i;
                        if(rx_index<6) rx_crc<=crc_byte(rx_crc,data_i);
                        if(rx_index==7) begin
                            rx_index<=0; rx_crc<=16'hffff;
                            reply[0]<=8'h5a; reply[2]<=req[2]; reply[3]<=2;
                            reply[4]<=0; reply[5]<=0; tx_index<=0; valid<=1;
                            bulk_mode<=0; stream_crc<=16'hffff;
                            if(req[0]!=8'ha5 || req[3]!=2 || req[6]!=rx_crc[7:0] || data_i!=rx_crc[15:8]) reply[1]<=1;
                            else case(req[1])
                                1: begin reply[1]<=0; reply[4]<=8'h54; reply[5]<=8'h50; end
                                2: begin reply[1]<=0; reply[4]<=req[4]; reply[5]<=req[5]; end
                                3: begin reply[1]<=0; reply[4]<=~req[4]; reply[5]<=~req[5]; end
                                8'h10,8'h11,8'h12,8'h13,8'h14,8'h15,8'h16:
                                    if(GFX_ENABLE==1) begin
                                        valid<=0; gfx_pending<=1; gfx_start<=1;
                                    end else reply[1]<=2;
                                8'h20,8'h21,8'h22,8'h23,8'h24,8'h25,8'h26,8'h27,
                                8'h28,8'h29,8'h2a,8'h2b,8'h2c,8'h2d,8'h2e,8'h2f,
                                8'h30,8'h31,8'h32,8'h33,8'h34,8'h35,8'h36,8'h37,8'h38,8'h39,8'h3a:
                                    if(GFX_ENABLE==2) begin
                                        valid<=0; gfx_pending<=1; gfx_start<=1;
                                    end else reply[1]<=2;
                                default: reply[1]<=2;
                            endcase
                        end else rx_index<=rx_index+1'b1;
                    end else if(dir_sync[1] && dir && valid) begin
                        if(bulk_mode && (tx_index<6 || (tx_index>=8 && tx_index<72)))
                            stream_crc<=crc_byte(stream_crc,data_o);
                        if((!bulk_mode && tx_index==7) || (bulk_mode && tx_index==73)) begin
                            valid<=0; tx_index<=0; bulk_mode<=0;
                        end
                        else tx_index<=tx_index+1'b1;
                    end
                end
            end
        end
    end
endmodule
