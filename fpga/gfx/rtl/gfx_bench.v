// Slow-link diagnostic renderer: 32x32 RGB565, no DDR3/HDMI/DMA.
// RAM is deliberately not reset. CLEAR must complete before pixel access.
module gfx_bench(
    input wire clk, reset_n, abort, start,
    input wire [7:0] opcode, a, b,
    output reg done,
    output reg [7:0] status,
    output reg [15:0] result
);
    localparam IDLE=0, FILL=1, READ_WAIT=2, READ_DONE=3, WRITE_DONE=4;
    reg [2:0] state;
    reg initialized, clearing;
    reg [15:0] color;
    reg [4:0] origin_x, origin_y, x, y, last_x, last_y;
    reg [9:0] address;
    reg [15:0] pixels [0:1023];
    reg [15:0] read_pixel;
    wire writing = reset_n && !abort && state==FILL;
    wire [9:0] ram_address = state==FILL ? {y,x} : address;
    always @(posedge clk) begin
        if(writing) pixels[ram_address] <= color;
        read_pixel <= pixels[ram_address];
    end
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            state<=IDLE; done<=0; status<=0; result<=0;
            initialized<=0; clearing<=0; color<=16'hffff;
            origin_x<=0; origin_y<=0; x<=0; y<=0;
            last_x<=0; last_y<=0; address<=0;
        end else if(abort) begin
            state<=IDLE; done<=0; status<=0; result<=0;
            initialized<=0; clearing<=0; color<=16'hffff;
            origin_x<=0; origin_y<=0; x<=0; y<=0;
            last_x<=0; last_y<=0; address<=0;
        end else begin
            done<=0;
            case(state)
                IDLE: if(start) begin
                    status<=0; result<={b,a};
                    case(opcode)
                        8'h10: begin result<=16'h2020; done<=1; end // width, height
                        8'h11: begin color<={b,a}; done<=1; end
                        8'h12: begin
                            x<=0; y<=0; origin_x<=0; origin_y<=0;
                            last_x<=31; last_y<=31; clearing<=1; state<=FILL;
                            result<=0;
                        end
                        8'h13,8'h14,8'h15: begin
                            if(a>=32 || b>=32) begin status<=3; result<=0; done<=1; end
                            else if(opcode==8'h15) begin
                                origin_x<=a[4:0]; origin_y<=b[4:0]; done<=1;
                            end else if(!initialized) begin status<=5; result<=0; done<=1; end
                            else if(opcode==8'h14) begin
                                address<={b[4:0],a[4:0]}; state<=READ_WAIT;
                            end else begin
                                x<=a[4:0]; y<=b[4:0]; last_x<=a[4:0]; last_y<=b[4:0];
                                clearing<=0; state<=FILL;
                            end
                        end
                        8'h16: begin
                            if(a==0 || b==0 || a>32 || b>32 ||
                               {1'b0,origin_x}+{1'b0,a}>32 ||
                               {1'b0,origin_y}+{1'b0,b}>32) begin
                                status<=3; result<=0; done<=1;
                            end else if(!initialized) begin status<=5; result<=0; done<=1; end
                            else begin
                                x<=origin_x; y<=origin_y;
                                last_x<=origin_x+a-1'b1; last_y<=origin_y+b-1'b1;
                                clearing<=0; state<=FILL;
                            end
                        end
                        default: begin status<=2; result<=0; done<=1; end
                    endcase
                end
                FILL: begin
                    if(x==last_x) begin
                        if(y==last_y) begin
                            if(clearing) initialized<=1;
                            state<=WRITE_DONE;
                        end else begin x<=origin_x; y<=y+1'b1; end
                    end else x<=x+1'b1;
                end
                READ_WAIT: state<=READ_DONE;
                READ_DONE: begin result<=read_pixel; done<=1; state<=IDLE; end
                WRITE_DONE: begin done<=1; state<=IDLE; end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
