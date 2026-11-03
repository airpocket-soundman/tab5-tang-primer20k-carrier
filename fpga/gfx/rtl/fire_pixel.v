// One-pixel serial "Procedural fire" (fire_g0) core. Bit-exact with
// fpga/reference/fire_g0.py. A single signed 18x18 multiplier is time-shared;
// latency is data independent: 8 + 14*octaves cycles after start.
// Octaves must be 1..6. No dynamic memory, no reset of the datapath registers.
module fire_pixel(
    input wire clk, reset_n, abort, start,
    input wire [9:0] x,            // pixel x, 0..1023 (frame is 640 wide; outside values are still defined)
    input wire [9:0] y,            // pixel y
    input wire [15:0] frame,
    input wire [2:0] octaves,      // 1..6
    output reg busy, done,
    output reg [15:0] color
);
    localparam IDLE=6'd0, PRE0=6'd1, PRE1=6'd2, PRE2=6'd3, PRE3=6'd4,
               O0=6'd8, O1=6'd9, O2=6'd10, O3=6'd11, O4=6'd12, O5=6'd13, O6=6'd14,
               O7=6'd15, O8=6'd16, O9=6'd17, O10=6'd18, O11=6'd19, O12=6'd20, O13=6'd21,
               H0=6'd24, H1=6'd25, H2=6'd26, H3=6'd27;
    localparam [31:0] HA=32'd40503, HB=32'd34283;

    reg [5:0] st;
    reg signed [17:0] ma, mb;
    wire signed [35:0] prod = ma*mb;

    reg [9:0] x_r, y_r;
    reg [15:0] frame_r;
    reg [2:0] oct_r, o;
    reg signed [31:0] nx, h, t, turb;
    reg signed [31:0] u, v;
    reg signed [15:0] ix, iy;
    reg [15:0] fx, fy;
    reg [31:0] p1, hv0;
    reg [15:0] n00, n10, n01, n11;
    reg [15:0] s_x, s_y;
    reg signed [17:0] sx, sy;
    reg signed [31:0] a_r, bq;
    reg signed [31:0] hq;

    // u = nx*(3<<o) + 12<<16 ; v = h*(3<<o) - (t + (t>>2)*o)
    wire signed [31:0] nx_f = (nx <<< o) + (nx <<< (o+3'd1));
    wire signed [31:0] u_w = nx_f + 32'sd786432;
    wire signed [31:0] q4 = t >>> 2;
    reg signed [31:0] tm_mul;
    always @* begin
        case(o)
            3'd0: tm_mul = 32'sd0;
            3'd1: tm_mul = q4;
            3'd2: tm_mul = q4 <<< 1;
            3'd3: tm_mul = q4 + (q4 <<< 1);
            3'd4: tm_mul = q4 <<< 2;
            default: tm_mul = q4 + (q4 <<< 2);
        endcase
    end
    wire signed [31:0] h_f = (h <<< o) + (h <<< (o+3'd1));
    wire signed [31:0] v_w = h_f - (t + tm_mul);

    reg [31:0] seed_c;
    always @* begin
        case(o)
            3'd0: seed_c = 32'd847331;   // 17*0xC2B3
            3'd1: seed_c = 32'd897174;   // 18*
            3'd2: seed_c = 32'd947017;   // 19*
            3'd3: seed_c = 32'd996860;   // 20*
            3'd4: seed_c = 32'd1046703;  // 21*
            default: seed_c = 32'd1096546; // 22*
        endcase
    end

    wire [31:0] hv_c10 = hv0 + HA;
    wire [31:0] hv_c01 = hv0 + HB;
    wire [31:0] hv_c11 = hv0 + HA + HB;
    wire [31:0] x1_c00 = hv0 ^ (hv0 >> 15);
    wire [31:0] x1_c10 = hv_c10 ^ (hv_c10 >> 15);
    wire [31:0] x1_c01 = hv_c01 ^ (hv_c01 >> 15);
    wire [31:0] x1_c11 = hv_c11 ^ (hv_c11 >> 15);
    function [15:0] hash_out;
        input [31:0] hv;
        input [35:0] p;
        reg [29:0] m;
        begin
            m = p[29:0];
            hash_out = (m[15:0] ^ m[26:11]) ^ hv[31:16];
        end
    endfunction

    // smoothstep helpers (signed 18-bit operands)
    wire signed [17:0] one_minus_2fx = 18'sd65536 - $signed({1'b0,fx,1'b0});
    wire signed [17:0] one_minus_2fy = 18'sd65536 - $signed({1'b0,fy,1'b0});
    wire signed [31:0] smooth_x = (prod >>> 16) + $signed({15'b0,s_x,1'b0});
    wire signed [31:0] smooth_y = (prod >>> 16) + $signed({15'b0,s_y,1'b0});

    wire signed [17:0] d_x0 = $signed({2'b0,n10}) - $signed({2'b0,n00});
    wire signed [17:0] d_x1 = $signed({2'b0,n11}) - $signed({2'b0,n01});
    wire signed [31:0] b_w = $signed({16'b0,n01}) + (prod >>> 16);
    wire signed [31:0] d_y = b_w - a_r;
    wire signed [31:0] nz = a_r + (prod >>> 16);

    wire signed [31:0] abs_nx = nx < 0 ? -nx : nx;
    wire signed [31:0] cq = prod >>> 16;
    wire signed [31:0] a_term = ((32'sd65536 - h) * 32'sd3) >>> 1;
    wire signed [31:0] sum_q = a_term - bq + cq - 32'sd45875;
    wire signed [31:0] hq_c = sum_q < 0 ? 32'sd0 : (sum_q > 32'sd65536 ? 32'sd65536 : sum_q);

    wire signed [31:0] r3 = hq*3;
    wire signed [31:0] r_in = r3 > 32'sd65536 ? 32'sd65536 : r3;
    wire signed [31:0] g3 = r3 - 32'sd52429;
    wire signed [31:0] g_in = g3 < 0 ? 32'sd0 : (g3 > 32'sd65536 ? 32'sd65536 : g3);
    wire signed [31:0] b4 = (hq <<< 2) - 32'sd163840;
    wire signed [31:0] b_in = b4 < 0 ? 32'sd0 : (b4 > 32'sd65536 ? 32'sd65536 : b4);
    wire [31:0] r8 = ((r_in <<< 8) - r_in) >>> 16;
    wire [31:0] g8 = ((g_in <<< 8) - (g_in <<< 4)) >>> 16;
    wire [31:0] b8 = ((b_in <<< 7) + (b_in <<< 5)) >>> 16;

    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            st<=IDLE; busy<=0; done<=0; color<=0;
        end else if(abort) begin
            st<=IDLE; busy<=0; done<=0;
        end else begin
            done<=0;
            case(st)
                IDLE: if(start) begin
                    x_r<=x; y_r<=y; frame_r<=frame; oct_r<=octaves;
                    busy<=1;
                    ma<=$signed({1'b0,x}) - 18'sd320; mb<=18'sd205;
                    st<=PRE1;
                end
                PRE1: begin
                    nx<=prod[31:0];
                    ma<=18'sd359 - $signed({8'b0,y_r}); mb<=18'sd182;
                    st<=PRE2;
                end
                PRE2: begin
                    h<=prod[31:0];
                    ma<={2'b00,frame_r}; mb<=18'sd2949;
                    st<=PRE3;
                end
                PRE3: begin
                    t<=prod[31:0]; o<=0; turb<=0; st<=O0;
                end
                O0: begin
                    u<=u_w; v<=v_w;
                    ix<=u_w[31:16]; fx<=u_w[15:0]; iy<=v_w[31:16]; fy<=v_w[15:0];
                    ma<=$signed(u_w[31:16]); mb<=18'sd40503;
                    st<=O1;
                end
                O1: begin
                    p1<=prod[31:0];
                    ma<=$signed(iy); mb<=18'sd34283;
                    st<=O2;
                end
                O2: begin
                    hv0<=p1+prod[31:0]+seed_c;
                    ma<={2'b00,fx}; mb<={2'b00,fx};
                    st<=O3;
                end
                O3: begin
                    s_x<=prod[31:16];
                    ma<={2'b00,prod[31:16]}; mb<=one_minus_2fx;
                    st<=O4;
                end
                O4: begin
                    sx<=smooth_x[17:0];
                    ma<={2'b00,fy}; mb<={2'b00,fy};
                    st<=O5;
                end
                O5: begin
                    s_y<=prod[31:16];
                    ma<={2'b00,prod[31:16]}; mb<=one_minus_2fy;
                    st<=O6;
                end
                O6: begin
                    sy<=smooth_y[17:0];
                    ma<={2'b00,x1_c00[15:0]}; mb<=18'sd11291;
                    st<=O7;
                end
                O7: begin
                    n00<=hash_out(hv0,prod);
                    ma<={2'b00,x1_c10[15:0]}; mb<=18'sd11291;
                    st<=O8;
                end
                O8: begin
                    n10<=hash_out(hv_c10,prod);
                    ma<={2'b00,x1_c01[15:0]}; mb<=18'sd11291;
                    st<=O9;
                end
                O9: begin
                    n01<=hash_out(hv_c01,prod);
                    ma<={2'b00,x1_c11[15:0]}; mb<=18'sd11291;
                    st<=O10;
                end
                O10: begin
                    n11<=hash_out(hv_c11,prod);
                    ma<=d_x0; mb<=sx;
                    st<=O11;
                end
                O11: begin
                    a_r<=$signed({16'b0,n00}) + (prod >>> 16);
                    ma<=d_x1; mb<=sx;
                    st<=O12;
                end
                O12: begin
                    ma<=d_y[17:0]; mb<=sy;
                    st<=O13;
                end
                O13: begin
                    turb<=turb + (nz >>> (o+3'd1));
                    if(o+3'd1==oct_r) st<=H0;
                    else begin o<=o+3'd1; st<=O0; end
                end
                H0: begin
                    ma<=abs_nx[17:0]; mb<=(32'sd32768 + h);
                    st<=H1;
                end
                H1: begin
                    bq<=prod >>> 16;
                    ma<=turb[17:0]; mb<=18'sd55706;
                    st<=H2;
                end
                H2: begin
                    hq<=hq_c; st<=H3;
                end
                H3: begin
                    color<={r8[7:3], g8[7:2], b8[7:3]};
                    done<=1; busy<=0; st<=IDLE;
                end
                default: begin st<=IDLE; busy<=0; end
            endcase
        end
    end
endmodule
