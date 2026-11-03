// Isolated4-stage candidate. Same signed17 differences/34 products/35 edges
// and64-bit outputs as original G0. Winding normalization follows multiplication.
module triangle_coverage(input wire clk,reset_n,in_valid,
    input wire signed [15:0]ax,ay,bx,by,cx,cy,
    input wire [9:0]pixel_x,input wire [8:0]pixel_y,
    output reg out_valid,covered,degenerate,winding_swapped,
    output reg signed [63:0]area,weight_a,weight_b,weight_c);
    reg [2:0]valid_pipe;
    reg signed [16:0]dx[0:3],dy[0:3],rx[0:3],ry[0:3];
    reg signed [33:0]lhs[0:3],rhs[0:3];
    reg signed [34:0]edge_value[0:3];
    reg [2:0]top_forward1,top_reverse1,top_forward2,top_reverse2,top_forward3,top_reverse3;
    wire signed [16:0]px=$signed({3'b0,pixel_x,4'b1000});
    wire signed [16:0]py=$signed({4'b0,pixel_y,4'b1000});
    function signed [16:0]difference(input signed [15:0]v,u);
        begin difference=$signed({v[15],v})-$signed({u[15],u});end
    endfunction
    function left_edge(input signed [16:0]x,y);
        begin left_edge=(y<0)||((y==0)&&(x>0));end
    endfunction
    function signed [34:0]normalize(input signed [34:0]v,input swapped);
        begin normalize=swapped?-v:v;end
    endfunction
    function signed [63:0]extend35(input signed [34:0]v);
        begin extend35={{29{v[34]}},v};end
    endfunction
    wire swapped=edge_value[0][34];
    wire zero_area=edge_value[0]==0;
    wire signed [34:0]wa=normalize(edge_value[1],swapped);
    wire signed [34:0]wb=normalize(edge_value[2],swapped);
    wire signed [34:0]wc=normalize(edge_value[3],swapped);
    wire [2:0]top=swapped?top_reverse3:top_forward3;
    integer i;
    always @(posedge clk or negedge reset_n)begin
        if(!reset_n)begin
            valid_pipe<=0;out_valid<=0;covered<=0;degenerate<=0;winding_swapped<=0;
            area<=0;weight_a<=0;weight_b<=0;weight_c<=0;
            top_forward1<=0;top_reverse1<=0;top_forward2<=0;top_reverse2<=0;top_forward3<=0;top_reverse3<=0;
            for(i=0;i<4;i=i+1)begin dx[i]<=0;dy[i]<=0;rx[i]<=0;ry[i]<=0;lhs[i]<=0;rhs[i]<=0;edge_value[i]<=0;end
        end else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
            if(in_valid)begin
                dx[0]<=difference(bx,ax);dy[0]<=difference(by,ay);rx[0]<=difference(cx,ax);ry[0]<=difference(cy,ay);
                dx[1]<=difference(cx,bx);dy[1]<=difference(cy,by);rx[1]<=px-$signed({bx[15],bx});ry[1]<=py-$signed({by[15],by});
                dx[2]<=difference(ax,cx);dy[2]<=difference(ay,cy);rx[2]<=px-$signed({cx[15],cx});ry[2]<=py-$signed({cy[15],cy});
                dx[3]<=difference(bx,ax);dy[3]<=difference(by,ay);rx[3]<=px-$signed({ax[15],ax});ry[3]<=py-$signed({ay[15],ay});
                top_forward1<={left_edge(difference(bx,ax),difference(by,ay)),left_edge(difference(ax,cx),difference(ay,cy)),left_edge(difference(cx,bx),difference(cy,by))};
                top_reverse1<={left_edge(difference(ax,bx),difference(ay,by)),left_edge(difference(cx,ax),difference(cy,ay)),left_edge(difference(bx,cx),difference(by,cy))};
            end
            if(valid_pipe[0])begin
                for(i=0;i<4;i=i+1)begin lhs[i]<=dx[i]*ry[i];rhs[i]<=dy[i]*rx[i];end
                top_forward2<=top_forward1;top_reverse2<=top_reverse1;
            end
            if(valid_pipe[1])begin
                for(i=0;i<4;i=i+1)edge_value[i]<=$signed({lhs[i][33],lhs[i]})-$signed({rhs[i][33],rhs[i]});
                top_forward3<=top_forward2;top_reverse3<=top_reverse2;
            end
            if(valid_pipe[2])begin
                winding_swapped<=swapped;degenerate<=zero_area;
                area<=extend35(normalize(edge_value[0],swapped));
                weight_a<=zero_area?64'sd0:extend35(wa);
                weight_b<=zero_area?64'sd0:extend35(wb);
                weight_c<=zero_area?64'sd0:extend35(wc);
                covered<=!zero_area && ((wa>0)||((wa==0)&&top[0])) && ((wb>0)||((wb==0)&&top[1])) && ((wc>0)||((wc==0)&&top[2]));
            end
        end
    end
endmodule
