// Isolated copy of9c314f3 link_bringup; only reply-domain clock/OE fault gate differs.
// Portable link-test core only. No package pins or DDR3 controller assumed.
// DIR=0: host writes on rising bus_clk. DIR=1: host samples then pulses.
module link_bringup_filtered #(
    parameter TIMEOUT_CYCLES = 2700000,
    parameter GFX_ENABLE = 0,
    parameter ALL_SCENES_ENABLE = 0,
    parameter REQUEST_DATA_PIPELINE = 0,
    parameter REPLY_ACTIVE_PIPELINE = 0,
    parameter CORE_CLOCK_MHZ = 27,
    parameter CLOCK_QUERY_ENABLE = 0,
    parameter FAST_REPLY_ENABLE = 0
)(input wire sys_clk, input wire reset_n, input wire arm,
  input wire bus_clk, input wire dir, input wire [7:0] data_i,
  output reg [7:0] data_o, output wire data_oe, output wire ready, input wire filter_clk,filter_reset_async_n);
    (* keep *) wire clean_reply_clk;
    wire clock_filter_fault;
    reg [2:0] clk_sync;
    reg [1:0] dir_sync;
    wire rise = clk_sync[1] & ~clk_sync[2];
    // Opt-in bundled request-data alignment. The byte and CLK first-stage
    // samples are taken at the same SYS edge; the delayed rise consumes that
    // same byte through the second data stage. This is a timing candidate,
    // not a guarantee of analog setup/hold or a replacement for packet CRC.
    wire [7:0] request_data;
    generate if(REQUEST_DATA_PIPELINE) begin: request_pipe
        reg [7:0] request_meta,request_sampled;
        always @(posedge sys_clk or negedge reset_n) begin
            if(!reset_n) begin request_meta<=0;request_sampled<=0;end
            else begin request_meta<=data_i;request_sampled<=request_meta;end
        end
        assign request_data=request_sampled;
    end else begin: request_direct
        assign request_data=data_i;
    end endgenerate
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
    reg batch_start,batch_pending,batch_is_2d,batch_is_upload;
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
    reply_clock_filter #(.ACTIVE_PIPELINE(REPLY_ACTIVE_PIPELINE)) clock_conditioner(filter_clk,filter_running,bus_clk,fast_offer && dir,clean_reply_clk,clock_filter_fault);
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
            raw_row_index,raw_ram_address,raw_ram_enable);
    end else begin: no_fast_serializer
        assign raw_data=0;assign raw_done=0;assign raw_started=0;assign raw_error=0;assign raw_progress=0;
        assign raw_row_index=0;assign raw_ram_address=0;assign raw_ram_enable=0;
    end endgenerate
    // Clamp preamble/CRC to valid endpoints so the tile prefetcher sees
    // only real payload word advances, never unsigned header underflow.
    wire [10:0] legacy_row_index = in_prefix || logical_tx_index<8 ? 11'd0 :
                            logical_tx_index>=payload_end ? (tile_mode?11'd2047:11'd63) :
                            logical_tx_index-12'd8;
    wire [10:0] row_index=use_raw ? (tile_mode?11'd0:{5'b0,raw_row_index}):legacy_row_index;
    generate if(GFX_ENABLE==2) begin: triangle
        wire renderer_abort = (gfx_pending || batch_pending) && idle_count >= TIMEOUT_CYCLES-1;
        wire tri_receiving,tri_busy,tri_done,tri_cmd_start;
        wire [7:0] tri_status,tri_opcode,tri_a,tri_b;
        wire d2_receiving,d2_busy,d2_done,d2_cmd_start;
        wire up_receiving,up_busy,up_done,up_cmd_start;
        wire [7:0] up_status,up_opcode,up_a,up_b;
        wire [7:0] d2_status,d2_opcode,d2_a,d2_b;
        triangle_batch staging(sys_clk,reset_n,batch_abort,batch_start && !batch_is_2d && !batch_is_upload,{1'b0,req[4][5:0]}+(req[4]==64?7'd64:7'd0),
            batch_header_crc,batch_byte_valid,request_data,tri_receiving,tri_busy,tri_done,tri_status,
            tri_cmd_start,tri_opcode,tri_a,tri_b,gfx_done,gfx_status);
        if(ALL_SCENES_ENABLE) begin: scenes_batch
            triangle_batch #(.BASE_OP(8'h61),.DRAW_OP(8'h6b),.REGISTER_INPUT(1)) staging2d(sys_clk,reset_n,batch_abort,batch_start && batch_is_2d,{1'b0,req[4][5:0]}+(req[4]==64?7'd64:7'd0),
                batch_header_crc,batch_byte_valid,request_data,d2_receiving,d2_busy,d2_done,d2_status,
                d2_cmd_start,d2_opcode,d2_a,d2_b,gfx_done,gfx_status);
            triangle_batch #(.BASE_OP(8'h6c),.DRAW_OP(8'h5e),.UPLOAD_MODE(1),.REGISTER_INPUT(1)) upload_staging(sys_clk,reset_n,batch_abort,batch_start && batch_is_upload,{1'b0,req[4][5:0]}+(req[4]==64?7'd64:7'd0),
                batch_header_crc,batch_byte_valid,request_data,up_receiving,up_busy,up_done,up_status,
                up_cmd_start,up_opcode,up_a,up_b,gfx_done,gfx_status);
        end else begin: no_scenes_batch
            assign d2_receiving=0;assign d2_busy=0;assign d2_done=0;assign d2_status=0;
            assign d2_cmd_start=0;assign d2_opcode=0;assign d2_a=0;assign d2_b=0;
            assign up_receiving=0;assign up_busy=0;assign up_done=0;assign up_status=0;
            assign up_cmd_start=0;assign up_opcode=0;assign up_a=0;assign up_b=0;
        end
        assign batch_receiving=batch_is_upload?up_receiving:(batch_is_2d?d2_receiving:tri_receiving);
        assign batch_busy=batch_is_upload?up_busy:(batch_is_2d?d2_busy:tri_busy);
        assign batch_done=batch_is_upload?up_done:(batch_is_2d?d2_done:tri_done);
        assign batch_status=batch_is_upload?up_status:(batch_is_2d?d2_status:tri_status);
        assign batch_cmd_start=batch_is_upload?up_cmd_start:(batch_is_2d?d2_cmd_start:tri_cmd_start);
        assign batch_cmd_opcode=batch_is_upload?up_opcode:(batch_is_2d?d2_opcode:tri_opcode);
        assign batch_cmd_a=batch_is_upload?up_a:(batch_is_2d?d2_a:tri_a);
        assign batch_cmd_b=batch_is_upload?up_b:(batch_is_2d?d2_b:tri_b);
        triangle_tile #(.ALL_SCENES_ENABLE(ALL_SCENES_ENABLE),.CORE_CLOCK_MHZ(CORE_CLOCK_MHZ),.CLOCK_QUERY_ENABLE(CLOCK_QUERY_ENABLE),.RAW_READ_ENABLE(FAST_REPLY_ENABLE)) renderer(sys_clk, reset_n && arm, renderer_abort, gfx_start || batch_cmd_start,
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
            gfx_start<=0; gfx_pending<=0;batch_start<=0;batch_pending<=0;batch_is_2d<=0;batch_is_upload<=0;
            bulk_mode<=0; tile_mode<=0; prefixed<=0; stream_crc<=16'hffff;
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
                        if(rx_index<7) req[rx_index]<=request_data;
                        if(rx_index<6) rx_crc<=crc_byte(rx_crc,request_data);
                        if(rx_index==7) begin
                            rx_index<=0; rx_crc<=16'hffff;
                            reply[0]<=8'h5a; reply[2]<=req[2]; reply[3]<=2;
                            reply[4]<=0; reply[5]<=0; tx_index<=0; valid<=1;
                            bulk_mode<=0; tile_mode<=0; prefixed<=0; stream_crc<=16'hffff;
                            prefixed<=req[1][7] && req[0]==8'ha5 && req[3]==2 &&
                                      req[6]==rx_crc[7:0] && request_data==rx_crc[15:8];
                            if(req[0]!=8'ha5 || req[3]!=2 || req[6]!=rx_crc[7:0] || request_data!=rx_crc[15:8]) reply[1]<=1;
                            else case(logical_opcode)
                                8'h40: if(GFX_ENABLE==2) begin
                                    if(req[4]!=0 || req[5]!=0) reply[1]<=3;
                                    else begin reply[1]<=0;reply[4]<=64;reply[5]<=1;end
                                end else reply[1]<=2;
                                8'h41,8'h5f,8'h6e: if(GFX_ENABLE==2 && (logical_opcode==8'h41 || ALL_SCENES_ENABLE)) begin
                                    if(req[4]<1 || req[4]>64 || req[5]!=1) reply[1]<=3;
                                    else begin valid<=0;batch_pending<=1;batch_is_2d<=logical_opcode==8'h6e;batch_is_upload<=logical_opcode==8'h5f;batch_start<=1;batch_header_crc<=rx_crc;end
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
                                8'h5e,8'h60,8'h61,8'h62,8'h63,8'h64,8'h65,8'h66,8'h67,
                                8'h68,8'h69,8'h6a,8'h6b,8'h6c,8'h6d,8'h6f,
                                8'h70,8'h71,8'h72,8'h73,8'h74,8'h75,8'h76,8'h77,8'h78:
                                    if(GFX_ENABLE==2 && ALL_SCENES_ENABLE) begin
                                        valid<=0;gfx_pending<=1;gfx_start<=1;
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
