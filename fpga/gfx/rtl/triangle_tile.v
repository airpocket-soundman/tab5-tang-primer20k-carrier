// Diagnostic 32x32 color/depth tile. Exact G0 fragment unit, one pixel in flight.
// No DDR3, no performance claim. Abort invalidates RAM until a complete clear.
module triangle_tile(
    input wire clk, reset_n, abort, start,
    input wire [7:0] opcode, a, b,
    output reg done,
    output reg [7:0] status,
    output reg [15:0] result,
    input wire [10:0] row_index,
    output wire [7:0] row_byte
);
    localparam IDLE=0, CLEAR=1, READ_WAIT=2, READ_DONE=3,
               SCAN_WAIT=4, SUBMIT=5, WAIT_RESULT=6, COMPLETE=7,
               ROW_WAIT=8, ROW_CAPTURE=9,
               FRACTAL_BEGIN=10, FRACTAL_MULT=11, FRACTAL_STEP=12, FRACTAL_WRITE=13, TILE_PREFETCH_WAIT=14, TILE_PREFETCH_CAPTURE=15;
    reg [3:0] state;
    reg initialized, read_depth;
    reg tile_stream;
    reg [15:0] tile_words[0:1];
    reg [9:0] prefetch_address,stream_word_seen;
    reg prefetch_slot;
    reg [1:0] prefetch_pending;
    reg [9:0] address;
    wire [9:0] ram_read_address=tile_stream ? prefetch_address : address;
    reg [9:0] configured;
    reg [15:0] params[0:9];
    reg [4:0] scan_x0, scan_x1, scan_y1;
    function signed [15:0] min3;
        input signed [15:0] a,b,c;
        begin min3=(a<b) ? ((a<c)?a:c) : ((b<c)?b:c); end
    endfunction
    function signed [15:0] max3;
        input signed [15:0] a,b,c;
        begin max3=(a>b) ? ((a>c)?a:c) : ((b>c)?b:c); end
    endfunction
    // A conservative inclusive bounding box in pixel coordinates. Arithmetic
    // shifts floor negative Q12.4 coordinates; clipping occurs before narrowing.
    wire signed [15:0] bbox_x0 = min3(params[0],params[2],params[4]) >>> 4;
    wire signed [15:0] bbox_x1 = max3(params[0],params[2],params[4]) >>> 4;
    wire signed [15:0] bbox_y0 = min3(params[1],params[3],params[5]) >>> 4;
    wire signed [15:0] bbox_y1 = max3(params[1],params[3],params[5]) >>> 4;
    wire [4:0] clipped_x0 = bbox_x0<0 ? 5'd0 : bbox_x0[4:0];
    wire [4:0] clipped_x1 = bbox_x1>31 ? 5'd31 : bbox_x1[4:0];
    wire [4:0] clipped_y0 = bbox_y0<0 ? 5'd0 : bbox_y0[4:0];
    wire [4:0] clipped_y1 = bbox_y1>31 ? 5'd31 : bbox_y1[4:0];
    reg [15:0] colors[0:1023], depths[0:1023];
    reg [15:0] color_q, depth_q, clear_color;
    reg [15:0] written;
    reg [15:0] row_cache[0:31];
    reg [15:0] fractal_params[0:6];
    reg [6:0] fractal_configured;
    reg signed [17:0] zx, zy, cx, cy;
    wire signed [35:0] square_x=zx*zx, square_y=zy*zy, product_xy=zx*zy;
    reg [31:0] fractal_cycles,last_fractal_cycles;
    reg [7:0] iterations;
    wire signed [35:0] delta_square = square_x-square_y;
    wire signed [36:0] twice_product = $signed({product_xy[35],product_xy}) <<< 1;
    wire [36:0] magnitude = {1'b0,square_x}+{1'b0,square_y};
    wire signed [31:0] tile_end_x = $signed(fractal_params[0]) + 32'sd31*$signed({1'b0,fractal_params[2]});
    wire signed [31:0] tile_end_y = $signed(fractal_params[1]) + 32'sd31*$signed({1'b0,fractal_params[3]});
    wire signed [31:0] pixel_px = $signed(fractal_params[0]) + $signed({1'b0,address[4:0]})*$signed({1'b0,fractal_params[2]});
    wire signed [31:0] pixel_py = $signed(fractal_params[1]) + $signed({1'b0,address[9:5]})*$signed({1'b0,fractal_params[3]});
    wire signed [31:0] next_pixel_px = address[4:0]==31 ? $signed(fractal_params[0]) :
        pixel_px+$signed({1'b0,fractal_params[2]});
    wire signed [31:0] next_pixel_py = address[4:0]==31 ?
        pixel_py+$signed({1'b0,fractal_params[3]}) : pixel_py;
    function [15:0] fractal_palette;
        input [7:0] i;
        begin
            case(i)
                8'd0: fractal_palette=16'h21ec;
                8'd1: fractal_palette=16'h3a4d;
                8'd2: fractal_palette=16'h52ce;
                8'd3: fractal_palette=16'h734f;
                8'd4: fractal_palette=16'h8bd1;
                8'd5: fractal_palette=16'ha432;
                8'd6: fractal_palette=16'hc4b3;
                8'd7: fractal_palette=16'hdd34;
                8'd8: fractal_palette=16'hfdb5;
                8'd9: fractal_palette=16'h3616;
                8'd10: fractal_palette=16'h4e97;
                8'd11: fractal_palette=16'h6f18;
                8'd12: fractal_palette=16'h879a;
                8'd13: fractal_palette=16'h9ffb;
                8'd14: fractal_palette=16'hba5c;
                8'd15: fractal_palette=16'hd2dd;
                8'd16: fractal_palette=16'hf35e;
                8'd17: fractal_palette=16'h2bbf;
                8'd18: fractal_palette=16'h442d;
                8'd19: fractal_palette=16'h64ae;
                8'd20: fractal_palette=16'h7d2f;
                8'd21: fractal_palette=16'h9590;
                8'd22: fractal_palette=16'hb611;
                8'd23: fractal_palette=16'hce92;
                8'd24: fractal_palette=16'hef14;
                8'd25: fractal_palette=16'h2775;
                8'd26: fractal_palette=16'h3ff6;
                8'd27: fractal_palette=16'h5a57;
                8'd28: fractal_palette=16'h72d8;
                8'd29: fractal_palette=16'h8b39;
                8'd30: fractal_palette=16'habba;
                8'd31: fractal_palette=16'hc43b;
                8'd32: fractal_palette=16'he4bd;
                8'd33: fractal_palette=16'hfd1e;
                8'd34: fractal_palette=16'h359f;
                8'd35: fractal_palette=16'h560c;
                8'd36: fractal_palette=16'h6e8e;
                8'd37: fractal_palette=16'h86ef;
                8'd38: fractal_palette=16'ha770;
                8'd39: fractal_palette=16'hbff1;
                8'd40: fractal_palette=16'hda52;
                8'd41: fractal_palette=16'hf2b3;
                8'd42: fractal_palette=16'h2b34;
                8'd43: fractal_palette=16'h4bb5;
                8'd44: fractal_palette=16'h6437;
                8'd45: fractal_palette=16'h7c98;
                8'd46: fractal_palette=16'h9d19;
                8'd47: fractal_palette=16'hb59a;
                8'd48: fractal_palette=16'hd61b;
                8'd49: fractal_palette=16'hee7c;
                8'd50: fractal_palette=16'h26fd;
                8'd51: fractal_palette=16'h477e;
                8'd52: fractal_palette=16'h5fec;
                8'd53: fractal_palette=16'h722d;
                8'd54: fractal_palette=16'h92ae;
                8'd55: fractal_palette=16'hab2f;
                8'd56: fractal_palette=16'hcbb1;
                8'd57: fractal_palette=16'he412;
                8'd58: fractal_palette=16'hfc93;
                8'd59: fractal_palette=16'h3d14;
                8'd60: fractal_palette=16'h5595;
                8'd61: fractal_palette=16'h6df6;
                8'd62: fractal_palette=16'h8e77;
                8'd63: fractal_palette=16'ha6f8;
                8'd64: fractal_palette=16'hc77a;
                8'd65: fractal_palette=16'hdfdb;
                8'd66: fractal_palette=16'hf23c;
                8'd67: fractal_palette=16'h32bd;
                8'd68: fractal_palette=16'h4b3e;
                8'd69: fractal_palette=16'h639f;
                8'd70: fractal_palette=16'h840d;
                8'd71: fractal_palette=16'h9c8e;
                8'd72: fractal_palette=16'hbd0f;
                8'd73: fractal_palette=16'hd570;
                8'd74: fractal_palette=16'hedf1;
                8'd75: fractal_palette=16'h2e72;
                8'd76: fractal_palette=16'h46f4;
                8'd77: fractal_palette=16'h5f55;
                8'd78: fractal_palette=16'h7fd6;
                8'd79: fractal_palette=16'h9237;
                8'd80: fractal_palette=16'hb2b8;
                8'd81: fractal_palette=16'hcb19;
                8'd82: fractal_palette=16'he39a;
                8'd83: fractal_palette=16'h241b;
                8'd84: fractal_palette=16'h3c9d;
                8'd85: fractal_palette=16'h54fe;
                8'd86: fractal_palette=16'h757f;
                8'd87: fractal_palette=16'h8dec;
                8'd88: fractal_palette=16'hae6e;
                8'd89: fractal_palette=16'hc6cf;
                8'd90: fractal_palette=16'hdf50;
                8'd91: fractal_palette=16'hffd1;
                8'd92: fractal_palette=16'h3232;
                8'd93: fractal_palette=16'h4a93;
                8'd94: fractal_palette=16'h6b14;
                8'd95: fractal_palette=16'h8395;
                8'd96: fractal_palette=16'ha417;
                8'd97: fractal_palette=16'hbc78;
                8'd98: fractal_palette=16'hd4f9;
                8'd99: fractal_palette=16'hf57a;
                8'd100: fractal_palette=16'h2dfb;
                8'd101: fractal_palette=16'h465c;
                8'd102: fractal_palette=16'h66dd;
                8'd103: fractal_palette=16'h7f5e;
                8'd104: fractal_palette=16'h9fcc;
                8'd105: fractal_palette=16'hb20d;
                8'd106: fractal_palette=16'hca8e;
                8'd107: fractal_palette=16'heb0f;
                8'd108: fractal_palette=16'h2391;
                8'd109: fractal_palette=16'h3bf2;
                8'd110: fractal_palette=16'h5c73;
                8'd111: fractal_palette=16'h74f4;
                8'd112: fractal_palette=16'h9575;
                8'd113: fractal_palette=16'hadd6;
                8'd114: fractal_palette=16'hc657;
                8'd115: fractal_palette=16'he6d8;
                8'd116: fractal_palette=16'hff5a;
                8'd117: fractal_palette=16'h37bb;
                8'd118: fractal_palette=16'h521c;
                8'd119: fractal_palette=16'h6a9d;
                8'd120: fractal_palette=16'h8b1e;
                8'd121: fractal_palette=16'ha37f;
                8'd122: fractal_palette=16'hbbed;
                8'd123: fractal_palette=16'hdc6e;
                8'd124: fractal_palette=16'hf4ef;
                8'd125: fractal_palette=16'h2d50;
                8'd126: fractal_palette=16'h4dd1;
                8'd127: fractal_palette=16'h6652;
                default: fractal_palette=16'h0042;
            endcase
        end
    endfunction
    function [15:0] fractal_vivid_palette;
        input [4:0] index;
        begin
            case(index)
                5'd0: fractal_vivid_palette=16'h000a;
                5'd1: fractal_vivid_palette=16'h0010;
                5'd2: fractal_vivid_palette=16'h0018;
                5'd3: fractal_vivid_palette=16'h011f;
                5'd4: fractal_vivid_palette=16'h031f;
                5'd5: fractal_vivid_palette=16'h051f;
                5'd6: fractal_vivid_palette=16'h071f;
                5'd7: fractal_vivid_palette=16'h07ff;
                5'd8: fractal_vivid_palette=16'h47fc;
                5'd9: fractal_vivid_palette=16'h87f4;
                5'd10: fractal_vivid_palette=16'hc7ec;
                5'd11: fractal_vivid_palette=16'hf7e4;
                5'd12: fractal_vivid_palette=16'hffe0;
                5'd13: fractal_vivid_palette=16'hff00;
                5'd14: fractal_vivid_palette=16'hfe00;
                5'd15: fractal_vivid_palette=16'hfd00;
                5'd16: fractal_vivid_palette=16'hfc00;
                5'd17: fractal_vivid_palette=16'hfb00;
                5'd18: fractal_vivid_palette=16'hfa00;
                5'd19: fractal_vivid_palette=16'hf880;
                5'd20: fractal_vivid_palette=16'hf800;
                5'd21: fractal_vivid_palette=16'hf808;
                5'd22: fractal_vivid_palette=16'hf810;
                5'd23: fractal_vivid_palette=16'hf818;
                5'd24: fractal_vivid_palette=16'hf81f;
                5'd25: fractal_vivid_palette=16'hd01f;
                5'd26: fractal_vivid_palette=16'ha01f;
                5'd27: fractal_vivid_palette=16'h701f;
                5'd28: fractal_vivid_palette=16'h501c;
                5'd29: fractal_vivid_palette=16'h3016;
                5'd30: fractal_vivid_palette=16'h1810;
                5'd31: fractal_vivid_palette=16'h080c;
            endcase
        end
    endfunction
    wire vivid_palette=fractal_params[6][9];
    wire [15:0] fractal_color = iterations==fractal_params[6][7:0] ?
        (vivid_palette?16'h0000:16'h0042) :
        (vivid_palette?fractal_vivid_palette(iterations[4:0]):fractal_palette(iterations));
    // Snapshot data is immutable while the link sends the response. It is not
    // exposed until all 32 synchronous RAM reads have completed.
    wire [15:0] ram_stream_word=read_depth ? depth_q : color_q;
    wire [15:0] stream_word=tile_words[row_index[1]];
    assign row_byte = tile_stream ? (row_index[0] ? stream_word[15:8] : stream_word[7:0]) :
                     (row_index[0] ? row_cache[row_index[5:1]][15:8] : row_cache[row_index[5:1]][7:0]);
    wire fragment_ready, fragment_valid, fragment_write;
    wire covered, degenerate, invalid_input, depth_pass;
    wire [15:0] new_depth, out_color;
    wire [9:0] out_x;
    wire [8:0] out_y;
    wire active = reset_n && !abort;
    triangle_fragment fragment(
        .clk(clk), .reset_n(active), .in_valid(state==SUBMIT), .in_ready(fragment_ready),
        .ax(params[0]), .ay(params[1]), .bx(params[2]), .by(params[3]),
        .cx(params[4]), .cy(params[5]), .za(params[6]), .zb(params[7]),
        .zc(params[8]), .old_depth(depth_q), .color(params[9]),
        .pixel_x({5'b0,address[4:0]}), .pixel_y({4'b0,address[9:5]}),
        .out_valid(fragment_valid), .out_ready(state==WAIT_RESULT),
        .covered(covered), .degenerate(degenerate), .invalid_input(invalid_input),
        .depth_pass(depth_pass), .write_enable(fragment_write),
        .new_depth(new_depth), .out_color(out_color), .out_x(out_x), .out_y(out_y)
    );
    // Synchronous RAM reads. No array reset, so block RAM can be inferred.
    always @(posedge clk) begin
        if(active && state==CLEAR) begin
            colors[address]<=clear_color; depths[address]<=0;
        end else if(active && state==WAIT_RESULT && fragment_write) begin
            colors[address]<=out_color; depths[address]<=new_depth;
        end else if(active && state==FRACTAL_WRITE) begin
            colors[address]<=fractal_color; depths[address]<=0;
        end
        color_q<=colors[ram_read_address]; depth_q<=depths[ram_read_address];
    end
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            state<=IDLE; initialized<=0; tile_stream<=0; prefetch_pending<=0; prefetch_address<=0; stream_word_seen<=0; prefetch_slot<=0; configured<=0; fractal_configured<=0; address<=0;
            done<=0; status<=0; result<=0; written<=0; read_depth<=0; clear_color<=0;
            fractal_cycles<=0; last_fractal_cycles<=0;
        end else if(abort) begin
            state<=IDLE; initialized<=0; tile_stream<=0; prefetch_pending<=0; prefetch_address<=0; stream_word_seen<=0; prefetch_slot<=0; configured<=0; fractal_configured<=0; address<=0;
            done<=0; status<=0; result<=0; written<=0;
            fractal_cycles<=0; last_fractal_cycles<=0;
        end else begin
            done<=0;
            // Cache the next word before its byte index is presented. The
            // consumed parity slot can be refilled during two byte periods.
            if(tile_stream && state==IDLE) begin
                if(prefetch_pending==1) begin
                    tile_words[prefetch_slot]<=ram_stream_word;
                    prefetch_pending<=0;
                end else if(prefetch_pending!=0) prefetch_pending<=prefetch_pending-1'b1;
                if(row_index[10:1]!=stream_word_seen) begin
                    stream_word_seen<=row_index[10:1];
                    prefetch_address<=row_index[10:1]+1'b1;
                    prefetch_slot<=~row_index[1];
                    prefetch_pending<=2;
                end
            end
            if(state==FRACTAL_BEGIN || state==FRACTAL_MULT || state==FRACTAL_WRITE)
                fractal_cycles<=fractal_cycles+1'b1;
            case(state)
                IDLE: if(start) begin
                    status<=0; result<=0; tile_stream<=0; prefetch_pending<=0;
                    if(opcode>=8'h21 && opcode<=8'h2a) begin
                        params[opcode-8'h21]<={b,a};
                        configured[opcode-8'h21]<=1; result<={b,a}; done<=1;
                    end else if(opcode>=8'h31 && opcode<=8'h36) begin
                        fractal_params[opcode-8'h31]<={b,a};
                        fractal_configured[opcode-8'h31]<=1; result<={b,a}; done<=1;
                    end else case(opcode)
                        8'h20: begin result<=16'h2020; done<=1; end
                        8'h3c: begin
                            if(a!=0 || b!=0) status<=3;
                            else result<=16'h0103;
                            done<=1;
                        end
                        8'h3b: begin
                            if(a!=0 || b>1) begin status<=3; done<=1; end
                            else if(!initialized) begin status<=5; done<=1; end
                            else begin
                                tile_stream<=1;read_depth<=b[0];result<={b,a};
                                prefetch_address<=0;stream_word_seen<=0;prefetch_slot<=0;
                                state<=TILE_PREFETCH_WAIT;
                            end
                        end
                        8'h30: begin result<=16'h0117; done<=1; end
                        8'h39,8'h3a: begin
                            if(a!=0 || b!=0) status<=3;
                            else if(last_fractal_cycles==0) status<=5;
                            else result<=opcode==8'h39 ? last_fractal_cycles[15:0] : last_fractal_cycles[31:16];
                            done<=1;
                        end
                        8'h37: begin
                            if(a==0 || a>128 || b>3) begin status<=3; done<=1; end
                            else begin fractal_params[6]<={b,a}; fractal_configured[6]<=1; result<={b,a}; done<=1; end
                        end
                        8'h38: begin
                            if(a!=0 || b!=0) begin status<=3; done<=1; end
                            else if(!(&fractal_configured)) begin status<=5; done<=1; end
                            else if(fractal_params[2]==0 || fractal_params[2]>32767 ||
                                    fractal_params[3]==0 || fractal_params[3]>32767 ||
                                    tile_end_x>32767 || tile_end_y>32767) begin status<=3; done<=1; end
                            else begin initialized<=0; address<=0; written<=0; fractal_cycles<=0; last_fractal_cycles<=0; state<=FRACTAL_BEGIN; end
                        end
                        8'h2b: begin address<=0; clear_color<={b,a}; written<=0; initialized<=0; state<=CLEAR; end
                        8'h2c: begin
                            if(a!=0 || b!=0) begin status<=3; done<=1; end
                            else if(!initialized || !(&configured)) begin status<=5; done<=1; end
                            else begin
                                written<=0;
                                if(bbox_x1<0 || bbox_y1<0 || bbox_x0>31 || bbox_y0>31) state<=COMPLETE;
                                else begin
                                    address<={clipped_y0,clipped_x0};
                                    scan_x0<=clipped_x0; scan_x1<=clipped_x1; scan_y1<=clipped_y1;
                                    state<=SCAN_WAIT;
                                end
                            end
                        end
                        8'h2d,8'h2e: begin
                            if(a>=32 || b>=32) begin status<=3; done<=1; end
                            else if(!initialized) begin status<=5; done<=1; end
                            else begin
                                address<={b[4:0],a[4:0]}; read_depth<=opcode==8'h2e; state<=READ_WAIT;
                            end
                        end
                        8'h2f: begin
                            if(a>=32 || b>1) begin status<=3; done<=1; end
                            else if(!initialized) begin status<=5; done<=1; end
                            else begin
                                address<={a[4:0],5'b0}; read_depth<=b[0];
                                result<={b,a}; state<=ROW_WAIT;
                            end
                        end
                        default: begin status<=2; done<=1; end
                    endcase
                end
                CLEAR: if(address==1023) begin initialized<=1; state<=COMPLETE; end
                       else address<=address+1'b1;
                READ_WAIT: state<=READ_DONE;
                READ_DONE: begin result<=read_depth ? depth_q : color_q; done<=1; state<=IDLE; end
                TILE_PREFETCH_WAIT: state<=TILE_PREFETCH_CAPTURE;
                TILE_PREFETCH_CAPTURE: begin
                    tile_words[prefetch_slot]<=ram_stream_word;
                    if(!prefetch_slot) begin
                        prefetch_address<=1;prefetch_slot<=1;state<=TILE_PREFETCH_WAIT;
                    end else begin done<=1;state<=IDLE;end
                end
                ROW_WAIT: state<=ROW_CAPTURE;
                ROW_CAPTURE: begin
                    row_cache[address[4:0]]<=read_depth ? depth_q : color_q;
                    if(address[4:0]==31) begin done<=1; state<=IDLE; end
                    else begin address<=address+1'b1; state<=ROW_WAIT; end
                end
                SCAN_WAIT: state<=SUBMIT;
                SUBMIT: if(fragment_ready) state<=WAIT_RESULT;
                WAIT_RESULT: if(fragment_valid) begin
                    if(invalid_input) begin status<=3; initialized<=0; state<=COMPLETE; end
                    else begin
                        if(fragment_write) written<=written+1'b1;
                        if(degenerate || (address[4:0]==scan_x1 && address[9:5]==scan_y1)) state<=COMPLETE;
                        else begin
                            if(address[4:0]==scan_x1) address<={address[9:5]+5'd1,scan_x0};
                            else address<=address+1'b1;
                            state<=SCAN_WAIT;
                        end
                    end
                end
                FRACTAL_BEGIN: begin
                    if(fractal_params[6][8]) begin
                        zx<=pixel_px; zy<=pixel_py;
                        cx<=$signed(fractal_params[4]); cy<=$signed(fractal_params[5]);
                    end else begin
                        zx<=0; zy<=0; cx<=pixel_px; cy<=pixel_py;
                    end
                    iterations<=0; state<=FRACTAL_MULT;
                end
                FRACTAL_MULT: begin
                    if(magnitude>=37'd67108864 || iterations==fractal_params[6][7:0]) state<=FRACTAL_WRITE;
                    else begin
                        zx<=(delta_square >>> 12)+cx;
                        zy<=(twice_product >>> 12)+cy;
                        iterations<=iterations+1'b1; state<=FRACTAL_MULT;
                    end
                end
                FRACTAL_WRITE: begin
                    if(address==1023) begin
                        initialized<=1; written<=1024;
                        last_fractal_cycles<=fractal_cycles+1'b1; state<=COMPLETE;
                    end else begin
                        // Prepare the next sample while this one is written;
                        // no separate BEGIN bubble is needed between pixels.
                        address<=address+1'b1; iterations<=0;
                        if(fractal_params[6][8]) begin
                            zx<=next_pixel_px; zy<=next_pixel_py;
                            cx<=$signed(fractal_params[4]); cy<=$signed(fractal_params[5]);
                        end else begin
                            zx<=0; zy<=0; cx<=next_pixel_px; cy<=next_pixel_py;
                        end
                        state<=FRACTAL_MULT;
                    end
                end
                COMPLETE: begin result<=written; done<=1; state<=IDLE; end
                default: begin initialized<=0; state<=IDLE; end
            endcase
        end
    end
endmodule
