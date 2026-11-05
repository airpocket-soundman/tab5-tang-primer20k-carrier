// Integer 2D operations on the shared 32x32 RGB565 tile. No private framebuffer.
// read_color is a synchronous, one-cycle tile RAM read of read_address.
// Coordinates are integer pixels, endpoints inclusive; line clipping discards
// off-tile samples without changing the original Bresenham stepping sequence.
module raster2d(
    input wire clk, reset_n, abort, start,
    input wire [1:0] kind,
    input wire signed [15:0] x0,y0,x1,y1,
    input wire [15:0] color,
    input wire [23:0] add_rgb,
    output wire busy,
    output reg done,
    output reg [9:0] read_address,
    input wire [15:0] read_color,
    output wire write_enable,
    output wire [9:0] write_address,
    output wire [15:0] write_color
);
    localparam IDLE=0,DRAW=1,ADD_WAIT=2,ADD_WRITE=3;
    reg [1:0] state,op;
    reg signed [16:0] x,y,finish_x,finish_y,rect_left;
    reg signed [16:0] sx,sy;
    reg [16:0] dx,dy;
    reg signed [17:0] error;
    reg [15:0] ink;
    reg [23:0] addend;
    wire [16:0] initial_dx=x1>=x0 ? $signed({x1[15],x1})-$signed({x0[15],x0}) :
                                                  $signed({x0[15],x0})-$signed({x1[15],x1});
    wire [16:0] initial_dy=y1>=y0 ? $signed({y1[15],y1})-$signed({y0[15],y0}) :
                                                  $signed({y0[15],y0})-$signed({y1[15],y1});
    wire inside_tile=(x>=0 && x<32 && y>=0 && y<32);
    wire signed [18:0] twice_error=$signed({error[17],error}) <<< 1;
    wire signed [18:0] dx_wide=$signed({2'b0,dx});
    wire signed [18:0] dy_wide=$signed({2'b0,dy});
    wire step_x=twice_error>=-dy_wide;
    wire step_y=twice_error<=dx_wide;
    assign busy=state!=IDLE;
    assign write_enable=reset_n && !abort &&
                        ((state==DRAW && inside_tile) || state==ADD_WRITE);
    assign write_address=state==ADD_WRITE ? read_address : {y[4:0],x[4:0]};

    function [7:0] expand5;
        input [4:0] value;
        begin
            case(value)
                5'd0:expand5=8'd0;
                5'd1:expand5=8'd8;
                5'd2:expand5=8'd16;
                5'd3:expand5=8'd24;
                5'd4:expand5=8'd32;
                5'd5:expand5=8'd41;
                5'd6:expand5=8'd49;
                5'd7:expand5=8'd57;
                5'd8:expand5=8'd65;
                5'd9:expand5=8'd74;
                5'd10:expand5=8'd82;
                5'd11:expand5=8'd90;
                5'd12:expand5=8'd98;
                5'd13:expand5=8'd106;
                5'd14:expand5=8'd115;
                5'd15:expand5=8'd123;
                5'd16:expand5=8'd131;
                5'd17:expand5=8'd139;
                5'd18:expand5=8'd148;
                5'd19:expand5=8'd156;
                5'd20:expand5=8'd164;
                5'd21:expand5=8'd172;
                5'd22:expand5=8'd180;
                5'd23:expand5=8'd189;
                5'd24:expand5=8'd197;
                5'd25:expand5=8'd205;
                5'd26:expand5=8'd213;
                5'd27:expand5=8'd222;
                5'd28:expand5=8'd230;
                5'd29:expand5=8'd238;
                5'd30:expand5=8'd246;
                5'd31:expand5=8'd255;
                default:expand5=0;
            endcase
        end
    endfunction
    function [7:0] expand6;
        input [5:0] value;
        begin
            case(value)
                6'd0:expand6=8'd0;
                6'd1:expand6=8'd4;
                6'd2:expand6=8'd8;
                6'd3:expand6=8'd12;
                6'd4:expand6=8'd16;
                6'd5:expand6=8'd20;
                6'd6:expand6=8'd24;
                6'd7:expand6=8'd28;
                6'd8:expand6=8'd32;
                6'd9:expand6=8'd36;
                6'd10:expand6=8'd40;
                6'd11:expand6=8'd44;
                6'd12:expand6=8'd48;
                6'd13:expand6=8'd52;
                6'd14:expand6=8'd56;
                6'd15:expand6=8'd60;
                6'd16:expand6=8'd64;
                6'd17:expand6=8'd68;
                6'd18:expand6=8'd72;
                6'd19:expand6=8'd76;
                6'd20:expand6=8'd80;
                6'd21:expand6=8'd85;
                6'd22:expand6=8'd89;
                6'd23:expand6=8'd93;
                6'd24:expand6=8'd97;
                6'd25:expand6=8'd101;
                6'd26:expand6=8'd105;
                6'd27:expand6=8'd109;
                6'd28:expand6=8'd113;
                6'd29:expand6=8'd117;
                6'd30:expand6=8'd121;
                6'd31:expand6=8'd125;
                6'd32:expand6=8'd129;
                6'd33:expand6=8'd133;
                6'd34:expand6=8'd137;
                6'd35:expand6=8'd141;
                6'd36:expand6=8'd145;
                6'd37:expand6=8'd149;
                6'd38:expand6=8'd153;
                6'd39:expand6=8'd157;
                6'd40:expand6=8'd161;
                6'd41:expand6=8'd165;
                6'd42:expand6=8'd170;
                6'd43:expand6=8'd174;
                6'd44:expand6=8'd178;
                6'd45:expand6=8'd182;
                6'd46:expand6=8'd186;
                6'd47:expand6=8'd190;
                6'd48:expand6=8'd194;
                6'd49:expand6=8'd198;
                6'd50:expand6=8'd202;
                6'd51:expand6=8'd206;
                6'd52:expand6=8'd210;
                6'd53:expand6=8'd214;
                6'd54:expand6=8'd218;
                6'd55:expand6=8'd222;
                6'd56:expand6=8'd226;
                6'd57:expand6=8'd230;
                6'd58:expand6=8'd234;
                6'd59:expand6=8'd238;
                6'd60:expand6=8'd242;
                6'd61:expand6=8'd246;
                6'd62:expand6=8'd250;
                6'd63:expand6=8'd255;
                default:expand6=0;
            endcase
        end
    endfunction
    function [15:0] saturated_add;
        input [15:0] dst;
        input [23:0] src;
        reg [8:0] r,g,b;
        begin
            // Explicit widths retain the ninth carry bit before saturation.
            r={1'b0,expand5(dst[15:11])}+{1'b0,src[23:16]};
            g={1'b0,expand6(dst[10:5])}+{1'b0,src[15:8]};
            b={1'b0,expand5(dst[4:0])}+{1'b0,src[7:0]};
            if(r>255) r=255;
            if(g>255) g=255;
            if(b>255) b=255;
            saturated_add={r[7:3],g[7:2],b[7:3]};
        end
    endfunction
    assign write_color=state==ADD_WRITE ? saturated_add(read_color,addend) : ink;

    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            state<=IDLE;op<=0;done<=0;read_address<=0;
            x<=0;y<=0;finish_x<=0;finish_y<=0;rect_left<=0;
            sx<=0;sy<=0;dx<=0;dy<=0;error<=0;ink<=0;addend<=0;
        end else begin
            done<=0;
            if(abort) state<=IDLE;
            else case(state)
                IDLE: if(start) begin
                    op<=kind;ink<=color;addend<=add_rgb;
                    x<=$signed(x0);y<=$signed(y0);
                    finish_x<=$signed(x1);finish_y<=$signed(y1);
                    dx<=initial_dx;dy<=initial_dy;
                    sx<=x0<x1 ? 17'sd1 : -17'sd1;
                    sy<=y0<y1 ? 17'sd1 : -17'sd1;
                    error<=$signed({1'b0,initial_dx})-$signed({1'b0,initial_dy});
                    if(kind==3) begin
                        if(x0<0 || x0>31 || y0<0 || y0>31) done<=1;
                        else begin read_address<={y0[4:0],x0[4:0]};state<=ADD_WAIT;end
                    end else if(kind==2) begin
                        if(x0>x1 || y0>y1 || x1<0 || y1<0 || x0>31 || y0>31) done<=1;
                        else begin
                            x<=x0<0 ? 17'sd0 : $signed(x0);
                            y<=y0<0 ? 17'sd0 : $signed(y0);
                            rect_left<=x0<0 ? 17'sd0 : $signed(x0);
                            finish_x<=x1>31 ? 17'sd31 : $signed(x1);
                            finish_y<=y1>31 ? 17'sd31 : $signed(y1);
                            state<=DRAW;
                        end
                    end else state<=DRAW;
                end
                DRAW: begin
                    if(op==0 || (x==finish_x && y==finish_y)) begin state<=IDLE;done<=1;end
                    else if(op==2) begin
                        if(x==finish_x) begin x<=rect_left;y<=y+17'sd1;end
                        else x<=x+17'sd1;
                    end else begin
                        if(step_x) x<=x+sx;
                        if(step_y) y<=y+sy;
                        case({step_x,step_y})
                            2'b10:error<=error-$signed({1'b0,dy});
                            2'b01:error<=error+$signed({1'b0,dx});
                            2'b11:error<=error-$signed({1'b0,dy})+$signed({1'b0,dx});
                            default: begin end
                        endcase
                    end
                end
                ADD_WAIT:state<=ADD_WRITE;
                ADD_WRITE:begin state<=IDLE;done<=1;end
                default:state<=IDLE;
            endcase
        end
    end
endmodule
