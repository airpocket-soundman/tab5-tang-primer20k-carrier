// Isolated copy of9c314f3 link_bringup; only reply-domain clock/OE fault gate differs.
// Portable link-test core only. No package pins or DDR3 controller assumed.
// DIR=0: host writes on rising bus_clk. DIR=1: host samples then pulses.
module link_bringup_filtered #(
    parameter TIMEOUT_CYCLES = 2700000,
    parameter GFX_ENABLE = 0,
    parameter CORE_CLOCK_MHZ = 27,
    parameter CLOCK_QUERY_ENABLE = 0,
    parameter FAST_REPLY_ENABLE = 0,
    // Diagnostic-only edge counters (opcodes 0x4c/0x4d). 0 = original behaviour,
    // new opcodes answer status 2 (unsupported) exactly like any unknown opcode.
    parameter EDGE_MONITOR_ENABLE = 0
)(input wire sys_clk, input wire reset_n, input wire arm,
  input wire bus_clk, input wire dir, input wire [7:0] data_i,
  output reg [7:0] data_o, output wire data_oe, output wire ready, input wire filter_clk,filter_reset_async_n);
    (* keep *) wire clean_reply_clk;
    wire clock_filter_fault;
    wire ev_accept,ev_reject,ev_drop,ev_runt,ev_fall,qualified_diag;
    wire [11:0] raw_done_index;
    reg [2:0] clk_sync;
    reg [1:0] dir_sync;
    wire rise = clk_sync[1] & ~clk_sync[2];
    reg [7:0] req[0:6];
    reg [7:0] reply[0:5];
    reg [2:0] rx_index;
    reg [11:0] tx_index;
    reg valid;
    reg bulk_mode,prefixed,tile_mode;
    wire [7:0] logical_opcode={1'b0,req[1][6:0]};
    wire in_prefix=prefixed && tx_index<8;
    wire [11:0] logical_tx_index=tx_index-(prefixed?12'd8:12'd0);
    wire [11:0] payload_end=tile_mode ? 12'd2056 : 12'd72;
    reg [15:0] stream_crc;
    reg [15:0] rx_crc;
    reg [31:0] idle_count;
    reg [15:0] reply_crc;
    reg gfx_start, gfx_pending;
    reg batch_start,batch_pending;
    reg [15:0] batch_header_crc;
    wire batch_receiving,batch_busy,batch_done,batch_cmd_start;
    wire [7:0] batch_status,batch_cmd_opcode,batch_cmd_a,batch_cmd_b;
    wire batch_abort=!arm || idle_count>=TIMEOUT_CYCLES-1 || (batch_receiving && dir_sync[1]);
    wire batch_byte_valid=rise && !dir && !dir_sync[1] && batch_receiving;
    wire [7:0] renderer_opcode=batch_pending?batch_cmd_opcode:logical_opcode;
    wire [7:0] renderer_a=batch_pending?batch_cmd_a:req[4];
    wire [7:0] renderer_b=batch_pending?batch_cmd_b:req[5];
    wire gfx_done;
    wire [7:0] gfx_status;
    wire [15:0] gfx_result;
    wire [7:0] row_byte;
    wire [7:0] raw_data;
    wire raw_done,raw_started,raw_error,raw_progress,raw_ram_enable;
    wire [5:0] raw_row_index;
    wire [9:0] raw_ram_address;
    wire [15:0] raw_ram_color,raw_ram_depth;
    reg fast_inflight,fast_offer;
    (* ASYNC_REG="TRUE" *) reg [1:0]filter_reset_release=0;
    always @(posedge filter_clk or negedge filter_reset_async_n)
        if(!filter_reset_async_n)filter_reset_release<=0;
        else filter_reset_release<={filter_reset_release[0],1'b1};
    wire filter_running=filter_reset_async_n && filter_reset_release[1];
    reply_clock_filter clock_conditioner(filter_clk,filter_running,bus_clk,fast_offer && dir,clean_reply_clk,clock_filter_fault,
        ev_accept,ev_reject,ev_drop,ev_runt,ev_fall,qualified_diag);
    reg [1:0] fast_prepare;
    reg [49:0] fast_metadata;
    (* ASYNC_REG="TRUE" *) reg [1:0] raw_done_sync,raw_started_sync,raw_progress_sync;
    reg raw_progress_last;
    wire use_raw=FAST_REPLY_ENABLE && prefixed;
    wire raw_valid=fast_offer && !raw_done && (!raw_started || dir);
    generate if(FAST_REPLY_ENABLE) begin: fast_serializer
        // Physical hold repair on this one serializer input only. The original
        // fast_offer still owns immediate OE/READY kill and SYS lifecycle.
        (* keep = "true" *) wire serializer_offer;
        (* keep = "true" *) LUT1 #(.INIT(2'h2)) offer_hold_buffer(.F(serializer_offer),.I0(fast_offer));
        link_reply_raw serializer(clean_reply_clk,reset_n,arm,dir,serializer_offer,fast_metadata,
            row_byte,raw_ram_color,raw_ram_depth,raw_data,raw_done,raw_started,raw_error,raw_progress,
            raw_row_index,raw_ram_address,raw_ram_enable,raw_done_index);
    end else begin: no_fast_serializer
        assign raw_data=0;assign raw_done=0;assign raw_started=0;assign raw_error=0;assign raw_progress=0;
        assign raw_row_index=0;assign raw_ram_address=0;assign raw_ram_enable=0;assign raw_done_index=0;
    end endgenerate
    wire [15:0] edge_value;
    reg edge_clear_tog;
    generate if(EDGE_MONITOR_ENABLE && FAST_REPLY_ENABLE) begin: edge_diag
        // Diagnostic readout of the conditioned reply clock (docs/CLK_edge_monitor.md).
        wire [11:0] e_pre,e_post,e_fall,e_expect,e_didx;
        wire [7:0] e_rej,e_drp,e_rnt,e_minh,e_minl,e_flags;
        wire e_tog;
        wire [11:0] expect_edges=fast_metadata[49]?12'd2066:(fast_metadata[48]?12'd82:12'd16);
        reply_edge_monitor monitor(filter_clk,filter_running,fast_offer && dir,dir,expect_edges,
            ev_accept,ev_reject,ev_drop,ev_runt,ev_fall,clock_filter_fault,raw_done,raw_error,raw_done_index,
            e_tog,e_pre,e_post,e_fall,e_expect,e_didx,e_rej,e_drp,e_rnt,e_minh,e_minl,e_flags);
        // Toggle-synchronized bundled-data copy. The snapshot registers are written
        // together with e_tog and then stay constant until the next reply window
        // closes, many SYS cycles later; they are sampled only after the toggle
        // has crossed a 2FF synchronizer.
        (* ASYNC_REG="TRUE" *) reg [1:0] tog_sync;
        reg tog_seen,hist_pending,clear_seen;
        reg [15:0] windows,bad_windows,seq;
        reg [11:0] l_pre,l_post,l_fall,l_expect,l_didx;
        reg [7:0] l_rej,l_drp,l_rnt,l_minh,l_minl,l_flags,w_rej,w_rnt,ever_minh,ever_minl;
        always @(posedge sys_clk or negedge reset_n) begin
            if(!reset_n) begin
                tog_sync<=0;tog_seen<=0;hist_pending<=0;clear_seen<=0;
                windows<=0;bad_windows<=0;seq<=0;
                l_pre<=0;l_post<=0;l_fall<=0;l_expect<=0;l_didx<=0;
                l_rej<=0;l_drp<=0;l_rnt<=0;l_minh<=8'hff;l_minl<=8'hff;l_flags<=0;
                w_rej<=0;w_rnt<=0;ever_minh<=8'hff;ever_minl<=8'hff;
            end else begin
                tog_sync<={tog_sync[0],e_tog};tog_seen<=tog_sync[1];
                hist_pending<=0;
                if(tog_sync[1]!=tog_seen) begin
                    l_pre<=e_pre;l_post<=e_post;l_fall<=e_fall;l_expect<=e_expect;l_didx<=e_didx;
                    l_rej<=e_rej;l_drp<=e_drp;l_rnt<=e_rnt;l_minh<=e_minh;l_minl<=e_minl;l_flags<=e_flags;
                    hist_pending<=1;
                end
                if(hist_pending && l_flags[7]) begin
                    seq<=seq+1'b1;
                    if(windows!=16'hffff) windows<=windows+1'b1;
                    if((l_rej!=0 || l_drp!=0 || l_rnt!=0 || l_flags[4] || l_flags[3] || l_flags[2] || l_flags[1] || !l_flags[0]) && bad_windows!=16'hffff)
                        bad_windows<=bad_windows+1'b1;
                    if(l_rej>w_rej) w_rej<=l_rej;
                    if(l_rnt>w_rnt) w_rnt<=l_rnt;
                    if(l_minh<ever_minh) ever_minh<=l_minh;
                    if(l_minl<ever_minl) ever_minl<=l_minl;
                end
                if(edge_clear_tog!=clear_seen) begin
                    clear_seen<=edge_clear_tog;
                    windows<=0;bad_windows<=0;w_rej<=0;w_rnt<=0;ever_minh<=8'hff;ever_minl<=8'hff;
                end
            end
        end
        reg [15:0] ev;
        always @* begin
            case(req[4])
                8'd0: ev=16'hed01;
                8'd1: ev=windows;
                8'd2: ev=bad_windows;
                8'd3: ev=seq;
                8'd4: ev={4'd0,l_pre};
                8'd5: ev={4'd0,l_post};
                8'd6: ev={8'd0,l_rej};
                8'd7: ev={8'd0,l_drp};
                8'd8: ev={8'd0,l_rnt};
                8'd9: ev={4'd0,l_fall};
                8'd10: ev={8'd0,l_minh};
                8'd11: ev={8'd0,l_minl};
                8'd12: ev={4'd0,l_expect};
                8'd13: ev={4'd0,l_didx};
                8'd14: ev={8'd0,l_flags};
                8'd15: ev={8'd0,w_rej};
                8'd16: ev={8'd0,w_rnt};
                8'd17: ev={8'd0,ever_minh};
                8'd18: ev={8'd0,ever_minl};
                default: ev=16'h0000;
            endcase
        end
        assign edge_value=ev;
    end else begin: no_edge_diag
        assign edge_value=16'h0000;
    end endgenerate
    // Clamp preamble/CRC to valid endpoints so the tile prefetcher sees
    // only real payload word advances, never unsigned header underflow.
    wire [10:0] legacy_row_index = in_prefix || logical_tx_index<8 ? 11'd0 :
                            logical_tx_index>=payload_end ? (tile_mode?11'd2047:11'd63) :
                            logical_tx_index-12'd8;
    wire [10:0] row_index=use_raw ? (tile_mode?11'd0:{5'b0,raw_row_index}):legacy_row_index;
    generate if(GFX_ENABLE==2) begin: triangle
        wire renderer_abort = (gfx_pending || batch_pending) && idle_count >= TIMEOUT_CYCLES-1;
        triangle_batch staging(sys_clk,reset_n,batch_abort,batch_start,{1'b0,req[4][5:0]}+(req[4]==64?7'd64:7'd0),
            batch_header_crc,batch_byte_valid,data_i,batch_receiving,batch_busy,batch_done,batch_status,
            batch_cmd_start,batch_cmd_opcode,batch_cmd_a,batch_cmd_b,gfx_done,gfx_status);
        triangle_tile #(.CORE_CLOCK_MHZ(CORE_CLOCK_MHZ),.CLOCK_QUERY_ENABLE(CLOCK_QUERY_ENABLE),.RAW_READ_ENABLE(FAST_REPLY_ENABLE)) renderer(sys_clk, reset_n && arm, renderer_abort, gfx_start || batch_cmd_start,
                              renderer_opcode, renderer_a, renderer_b, gfx_done, gfx_status, gfx_result,
                              row_index, row_byte,clean_reply_clk,raw_ram_enable,raw_ram_address,raw_ram_color,raw_ram_depth);
    end else if(GFX_ENABLE) begin: gfx
        assign batch_receiving=0;assign batch_busy=0;assign batch_done=0;assign batch_status=0;
        assign batch_cmd_start=0;assign batch_cmd_opcode=0;assign batch_cmd_a=0;assign batch_cmd_b=0;
        // A timed-out operation must not keep mutating RAM or consume a later start.
        wire renderer_reset_n = reset_n && arm;
        wire renderer_abort = (gfx_pending || batch_pending) && idle_count >= TIMEOUT_CYCLES-1;
        gfx_bench renderer(sys_clk, renderer_reset_n, renderer_abort, gfx_start,
                           logical_opcode, req[4], req[5], gfx_done, gfx_status, gfx_result);
        assign row_byte=8'h00;assign raw_ram_color=0;assign raw_ram_depth=0;
    end else begin: no_gfx
        assign batch_receiving=0;assign batch_busy=0;assign batch_done=0;assign batch_status=0;
        assign batch_cmd_start=0;assign batch_cmd_opcode=0;assign batch_cmd_a=0;assign batch_cmd_b=0;
        assign gfx_done=1'b0;
        assign gfx_status=8'h02;
        assign gfx_result=16'h0000;
        assign row_byte=8'h00;assign raw_ram_color=0;assign raw_ram_depth=0;
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
    assign data_oe=!clock_filter_fault && reset_n && arm && dir && dir_sync[1] && valid && (!use_raw || raw_valid);
    assign ready=!clock_filter_fault && reset_n && arm && valid && (!use_raw || raw_valid);
    always @* begin
        reply_crc=16'hffff;
        for(j=0;j<6;j=j+1) reply_crc=crc_byte(reply_crc,reply[j]);
        if(use_raw) data_o=raw_data;
        else if(in_prefix) data_o=8'hc3;
        else if(logical_tx_index<6) data_o=reply[logical_tx_index];
        else if(logical_tx_index==6) data_o=reply_crc[7:0];
        else if(logical_tx_index==7) data_o=reply_crc[15:8];
        else if(bulk_mode && logical_tx_index<payload_end) data_o=row_byte;
        else if(bulk_mode && logical_tx_index==payload_end) data_o=stream_crc[7:0];
        else if(bulk_mode && logical_tx_index==payload_end+1'b1) data_o=stream_crc[15:8];
        else data_o=8'h00;
    end
    always @(posedge sys_clk or negedge reset_n) begin
        if(!reset_n) begin
            clk_sync<=0; dir_sync<=0; rx_index<=0; tx_index<=0;
            fast_inflight<=0;fast_offer<=0;fast_prepare<=0;fast_metadata<=0;
            raw_done_sync<=0;raw_started_sync<=0;raw_progress_sync<=0;raw_progress_last<=0;
            valid<=0; rx_crc<=16'hffff; idle_count<=0;
            gfx_start<=0; gfx_pending<=0;batch_start<=0;batch_pending<=0;
            bulk_mode<=0; tile_mode<=0; prefixed<=0; stream_crc<=16'hffff;
            edge_clear_tog<=0;
        end else begin
            gfx_start<=0;batch_start<=0;
            raw_done_sync<={raw_done_sync[0],raw_done};
            raw_started_sync<={raw_started_sync[0],raw_started};
            raw_progress_sync<={raw_progress_sync[0],raw_progress};
            raw_progress_last<=raw_progress_sync[1];
            clk_sync<={clk_sync[1:0],bus_clk}; dir_sync<={dir_sync[0],dir};
            if(!arm) begin
                valid<=0; rx_index<=0; tx_index<=0; rx_crc<=16'hffff; idle_count<=0;
                gfx_pending<=0;batch_pending<=0;fast_offer<=0;fast_inflight<=0;fast_prepare<=0;
                bulk_mode<=0; tile_mode<=0; prefixed<=0; stream_crc<=16'hffff;
            end else if(idle_count>=TIMEOUT_CYCLES-1) begin
                valid<=0; rx_index<=0; tx_index<=0; rx_crc<=16'hffff; idle_count<=0;
                gfx_pending<=0;batch_pending<=0;fast_offer<=0;fast_inflight<=0;fast_prepare<=0;
                bulk_mode<=0; tile_mode<=0; prefixed<=0; stream_crc<=16'hffff;
            end else begin
                idle_count<=idle_count+1;
                if(FAST_REPLY_ENABLE && fast_inflight && raw_progress_sync[1]!=raw_progress_last) idle_count<=0;
                // Four-phase bundled-data handshake. Snapshot metadata before
                // raising offer; source stays frozen until RAW done or abort.
                if(FAST_REPLY_ENABLE && valid && prefixed && !fast_inflight) begin
                    fast_inflight<=1;fast_prepare<=2;
                end else if(fast_inflight) begin
                    if(fast_prepare==2) begin
                        fast_metadata<={tile_mode,bulk_mode,reply[5],reply[4],reply[3],reply[2],reply[1],reply[0]};
                        fast_prepare<=1;
                    end else if(fast_prepare==1 && !raw_done_sync[1]) begin
                        fast_offer<=1;fast_prepare<=0;
                    end else if(fast_offer && (raw_done_sync[1] || (raw_started_sync[1] && !dir && !dir_sync[1]))) begin
                        valid<=0;fast_offer<=0;fast_inflight<=0;fast_prepare<=0;
                        bulk_mode<=0;tile_mode<=0;prefixed<=0;tx_index<=0;idle_count<=0;
                    end
                end
                if(batch_pending && gfx_done) idle_count<=0;
                if(batch_pending && batch_done) begin
                    reply[1]<=batch_status;reply[4]<=req[4];reply[5]<=1;
                    valid<=1;batch_pending<=0;
                end
                if(batch_pending && batch_receiving && dir_sync[1]) begin
                    batch_pending<=0;rx_index<=0;rx_crc<=16'hffff;
                end
                if(gfx_pending && gfx_done) begin
                    reply[1]<=gfx_status; reply[4]<=gfx_result[7:0]; reply[5]<=gfx_result[15:8];
                    valid<=1; gfx_pending<=0;
                    bulk_mode<=GFX_ENABLE==2 && (logical_opcode==8'h2f || logical_opcode==8'h3b) && gfx_status==0;
                    tile_mode<=logical_opcode==8'h3b && gfx_status==0;
                end
                if(dir_sync[1] && rx_index!=0) begin rx_index<=0; rx_crc<=16'hffff; end
                if(rise) begin
                    idle_count<=0;
                    if(!dir_sync[1] && !dir && !valid && !gfx_pending && !batch_pending) begin
                        if(rx_index==0) begin bulk_mode<=0; tile_mode<=0; prefixed<=0; stream_crc<=16'hffff; end
                        if(rx_index<7) req[rx_index]<=data_i;
                        if(rx_index<6) rx_crc<=crc_byte(rx_crc,data_i);
                        if(rx_index==7) begin
                            rx_index<=0; rx_crc<=16'hffff;
                            reply[0]<=8'h5a; reply[2]<=req[2]; reply[3]<=2;
                            reply[4]<=0; reply[5]<=0; tx_index<=0; valid<=1;
                            bulk_mode<=0; tile_mode<=0; prefixed<=0; stream_crc<=16'hffff;
                            prefixed<=req[1][7] && req[0]==8'ha5 && req[3]==2 &&
                                      req[6]==rx_crc[7:0] && data_i==rx_crc[15:8];
                            if(req[0]!=8'ha5 || req[3]!=2 || req[6]!=rx_crc[7:0] || data_i!=rx_crc[15:8]) reply[1]<=1;
                            else case(logical_opcode)
                                8'h40: if(GFX_ENABLE==2) begin
                                    if(req[4]!=0 || req[5]!=0) reply[1]<=3;
                                    else begin reply[1]<=0;reply[4]<=64;reply[5]<=1;end
                                end else reply[1]<=2;
                                8'h41: if(GFX_ENABLE==2) begin
                                    if(req[4]<1 || req[4]>64 || req[5]!=1) reply[1]<=3;
                                    else begin valid<=0;batch_pending<=1;batch_start<=1;batch_header_crc<=rx_crc;end
                                end else reply[1]<=2;
                                1: begin reply[1]<=0; reply[4]<=8'h54; reply[5]<=8'h50; end
                                2: begin reply[1]<=0; reply[4]<=req[4]; reply[5]<=req[5]; end
                                3: begin reply[1]<=0; reply[4]<=~req[4]; reply[5]<=~req[5]; end
                                4: begin reply[1]<=0; reply[4]<=8; reply[5]<=1; end
                                8'h10,8'h11,8'h12,8'h13,8'h14,8'h15,8'h16:
                                    if(GFX_ENABLE==1) begin
                                        valid<=0; gfx_pending<=1; gfx_start<=1;
                                    end else reply[1]<=2;
                                8'h20,8'h21,8'h22,8'h23,8'h24,8'h25,8'h26,8'h27,
                                8'h28,8'h29,8'h2a,8'h2b,8'h2c,8'h2d,8'h2e,8'h2f,
                                8'h30,8'h31,8'h32,8'h33,8'h34,8'h35,8'h36,8'h37,8'h38,8'h39,8'h3a,8'h3b,8'h3c,8'h3d:
                                    if(GFX_ENABLE==2) begin
                                        valid<=0; gfx_pending<=1; gfx_start<=1;
                                    end else reply[1]<=2;
                                8'h4c: if(EDGE_MONITOR_ENABLE && FAST_REPLY_ENABLE) begin
                                    if(req[5]!=0 || req[4]>8'd18) reply[1]<=3;
                                    else begin reply[1]<=0;reply[4]<=edge_value[7:0];reply[5]<=edge_value[15:8];end
                                end else reply[1]<=2;
                                8'h4d: if(EDGE_MONITOR_ENABLE && FAST_REPLY_ENABLE) begin
                                    if(req[4]!=8'h5a || req[5]!=8'ha5) reply[1]<=3;
                                    else begin reply[1]<=0;edge_clear_tog<=~edge_clear_tog;end
                                end else reply[1]<=2;
                                default: reply[1]<=2;
                            endcase
                        end else rx_index<=rx_index+1'b1;
                    end else if(dir_sync[1] && dir && valid && !use_raw) begin
                        if(bulk_mode && !in_prefix && (logical_tx_index<6 || (logical_tx_index>=8 && logical_tx_index<payload_end)))
                            stream_crc<=crc_byte(stream_crc,data_o);
                        if(!in_prefix && ((!bulk_mode && logical_tx_index==7) || (bulk_mode && logical_tx_index==payload_end+1'b1))) begin
                            valid<=0; tx_index<=0; bulk_mode<=0; tile_mode<=0; prefixed<=0;
                        end
                        else tx_index<=tx_index+1'b1;
                    end
                end
            end
        end
    end
endmodule
