// Bounded INT8 Conv tile. No wire protocol, DDR, bias, requantization or graph.
// Host provides CHW padded halo and OIHW weights for one IC block (<=16).
// Partial sums stay private until a successful final_block. See CONV_TILE.md.
module conv_tile_engine_8oc #(
    parameter INPUT_CAPACITY=17424, WEIGHT_CAPACITY=1152, OUTPUT_CAPACITY=2048
)(
    input wire clk,reset,abort,
    input wire load_start,
    input wire [4:0] cfg_ic,cfg_oh,cfg_ow,
    input wire [3:0] cfg_oc,
    input wire [1:0] cfg_kernel,cfg_stride,
    input wire [5:0] cfg_input_h,cfg_input_w,
    input wire first_block,final_block,
    input wire upload_valid,upload_kind,
    input wire [14:0] upload_address,
    input wire signed [7:0] upload_data,
    output wire upload_ready,
    input wire start,
    output wire busy,
    output reg block_done,output_valid,error,
    output reg [2:0] error_code,
    output reg [31:0] compute_cycles,
    input wire read_enable,
    input wire [10:0] read_address,
    output reg read_valid,
    output wire signed [31:0] read_data
);

    localparam IDLE=0,LOAD_ACC=1,WAIT_ACC=2,READ_PAIR=3,MAC=4,STORE=5,FAULT=6;
    reg [2:0] state;
    reg loaded,partial_valid,saved_first,saved_final;
    reg [4:0] nic,oh,ow,ic,oy,ox;
    reg [3:0] noc;
    reg [1:0] kernel,stride,ky,kx;
    reg [5:0] ih,iw;
    reg [4:0] partial_oh,partial_ow;
    reg [3:0] partial_oc;
    reg [1:0] partial_kernel,partial_stride;
    reg [15:0] input_count,weight_count,input_bytes,weight_bytes;
    reg [11:0] output_words;
    reg [8:0] pixel_span;
    reg [7:0] pixel_index,weight_tap,upload_tap;
    reg [2:0] upload_lane;
    reg [14:0] input_address,input_plane_base,input_row_base,input_pixel_base,output_row_base;
    reg [10:0] weight_oc_span,input_plane_span;
    reg [6:0] input_output_row_step;
    reg signed [7:0] input_q;
    reg signed [31:0] accumulators[0:7];
    wire signed [31:0] output_q[0:7];
    wire signed [15:0] weight_q[0:3];
    reg signed [7:0] input_memory[0:INPUT_CAPACITY-1];
    reg weight_pending;
    reg [7:0] pending_tap;
    reg [2:0] pending_lane;
    reg [7:0] pending_data;
    wire [31:0] config_plane={26'd0,cfg_input_h}*{26'd0,cfg_input_w};
    wire [31:0] config_inputs=config_plane*{27'd0,cfg_ic};
    wire [31:0] config_kernel_area=cfg_kernel==3?32'd9:32'd1;
    wire [31:0] config_weights={28'd0,cfg_oc}*{27'd0,cfg_ic}*config_kernel_area;
    wire [31:0] config_outputs={28'd0,cfg_oc}*{27'd0,cfg_oh}*{27'd0,cfg_ow};
    wire [31:0] required_h=({27'd0,cfg_oh}-1)*{30'd0,cfg_stride}+{30'd0,cfg_kernel};
    wire [31:0] required_w=({27'd0,cfg_ow}-1)*{30'd0,cfg_stride}+{30'd0,cfg_kernel};
    wire config_valid=cfg_ic>=1 && cfg_ic<=16 && cfg_oc>=1 && cfg_oc<=8 &&
        cfg_oh>=1 && cfg_oh<=16 && cfg_ow>=1 && cfg_ow<=16 &&
        (cfg_kernel==1 || cfg_kernel==3) && (cfg_stride==1 || cfg_stride==2) &&
        cfg_input_h==required_h && cfg_input_w==required_w &&
        config_inputs<=INPUT_CAPACITY && config_weights<=WEIGHT_CAPACITY && config_outputs<=OUTPUT_CAPACITY;
    assign busy=state!=IDLE && state!=FAULT;
    assign upload_ready=state==IDLE && loaded && !error && !load_start && !start && !weight_pending;
    wire upload_fire=upload_valid && upload_ready;
    wire input_write=upload_fire && !upload_kind && upload_address==input_count && input_count<input_bytes;
    wire weight_write=upload_fire && upload_kind && upload_address==weight_count && weight_count<weight_bytes;
    wire output_read=state==IDLE && read_enable && output_valid && !error && read_address<output_words;
    wire [7:0] external_pixel[0:7];
    wire external_lane[0:7];
    wire signed [32:0] sums[0:7];
    wire [7:0] overflow;
    reg signed [31:0] ram_q;
    assign read_data=read_valid ? ram_q : 32'sd0;
    // One synchronous input read is broadcast to all eight OC lanes.
    always @(posedge clk) begin
        if(input_write) input_memory[upload_address]<=upload_data;
        if(state==READ_PAIR) input_q<=input_memory[input_address];
    end
    genvar b,l;
    generate for(b=0;b<4;b=b+1)begin:weight_banks
        // Explicit 16-bit write port prevents two independent byte RAMs.
        // Upload is OC-major: latch the old pair, merge only on the next edge.
        reg [15:0] memory[0:143];
        reg [15:0] bank_q;
        assign weight_q[b]=bank_q;
        always @(posedge clk)begin
            if((weight_write && upload_lane[2:1]==b) || state==READ_PAIR)
                bank_q<=memory[state==READ_PAIR ? weight_tap : upload_tap];
            if(weight_pending && pending_lane[2:1]==b && !reset && !abort && !error)
                memory[pending_tap]<=pending_lane[0] ? {pending_data,bank_q[7:0]} : {8'd0,pending_data};
        end
    end
    for(l=0;l<8;l=l+1)begin:lanes
        reg signed [31:0] memory[0:255];
        reg signed [31:0] q;
        wire signed [7:0] lane_weight=l%2 ? weight_q[l/2][15:8] : weight_q[l/2][7:0];
        wire signed [15:0] product=input_q*lane_weight;
        assign sums[l]=$signed({accumulators[l][31],accumulators[l]})+$signed({{17{product[15]}},product});
        assign overflow[l]=(l<noc) && (sums[l][32]!=sums[l][31]);
        assign output_q[l]=q;
        assign external_lane[l]=read_address>=l*pixel_span && read_address<(l+1)*pixel_span;
        wire [10:0] pixel_offset=read_address-l*pixel_span;
        assign external_pixel[l]=pixel_offset[7:0];
        always @(posedge clk)begin
            if(state==STORE && l<noc)memory[pixel_index]<=accumulators[l];
            if(state==LOAD_ACC || (output_read && external_lane[l]))
                q<=memory[state==LOAD_ACC ? pixel_index : external_pixel[l]];
        end
    end endgenerate
    // Publication mux selects the registered bank value in the same cycle as
    // read_valid; it is combinational to retain the original one-edge read.
    reg [2:0] read_lane;
    always @* ram_q=output_q[read_lane];
    task fail;
        input [2:0] code;
        begin error<=1;error_code<=code;state<=FAULT;loaded<=0;partial_valid<=0;output_valid<=0;read_valid<=0;weight_pending<=0;end
    endtask
    integer a;
    always @(posedge clk)begin
        if(reset || abort)begin
            state<=IDLE;loaded<=0;partial_valid<=0;saved_first<=0;saved_final<=0;
            nic<=0;noc<=0;oh<=0;ow<=0;ih<=0;iw<=0;kernel<=0;stride<=0;
            ic<=0;oy<=0;ox<=0;ky<=0;kx<=0;
            partial_oh<=0;partial_ow<=0;partial_oc<=0;partial_kernel<=0;partial_stride<=0;
            input_count<=0;weight_count<=0;input_bytes<=0;weight_bytes<=0;output_words<=0;pixel_span<=0;
            pixel_index<=0;weight_tap<=0;upload_tap<=0;upload_lane<=0;
            input_address<=0;input_plane_base<=0;input_row_base<=0;input_pixel_base<=0;output_row_base<=0;
            weight_oc_span<=0;input_plane_span<=0;input_output_row_step<=0;
            for(a=0;a<8;a=a+1)accumulators[a]<=0;
            block_done<=0;output_valid<=0;error<=0;error_code<=0;compute_cycles<=0;read_valid<=0;
            weight_pending<=0;pending_tap<=0;pending_lane<=0;pending_data<=0;read_lane<=0;
        end else begin
            block_done<=0;read_valid<=0;
            if(busy && compute_cycles!=32'hffffffff)compute_cycles<=compute_cycles+1'b1;
            if(weight_pending)weight_pending<=0;
            if(error)begin state<=FAULT;output_valid<=0;partial_valid<=0;end
            else if(load_start)begin
                if(state!=IDLE)fail(4);
                else if(!config_valid)fail(1);
                else if(!first_block && (!partial_valid || partial_oh!=cfg_oh || partial_ow!=cfg_ow || partial_oc!=cfg_oc || partial_kernel!=cfg_kernel || partial_stride!=cfg_stride))fail(4);
                else begin
                    nic<=cfg_ic;noc<=cfg_oc;oh<=cfg_oh;ow<=cfg_ow;ih<=cfg_input_h;iw<=cfg_input_w;kernel<=cfg_kernel;stride<=cfg_stride;
                    input_bytes<=config_inputs[15:0];weight_bytes<=config_weights[15:0];output_words<=config_outputs[11:0];
                    pixel_span<={4'd0,cfg_oh}*{4'd0,cfg_ow};
                    input_plane_span<=config_plane[10:0];weight_oc_span<=cfg_kernel==3 ? {6'd0,cfg_ic}+({6'd0,cfg_ic}<<3) : {6'd0,cfg_ic};
                    input_output_row_step<=cfg_stride==2 ? {cfg_input_w,1'b0} : {1'b0,cfg_input_w};
                    saved_first<=first_block;saved_final<=final_block;input_count<=0;weight_count<=0;loaded<=1;output_valid<=0;
                    upload_tap<=0;upload_lane<=0;if(first_block)partial_valid<=0;
                end
            end else if(start)begin
                if(state!=IDLE)fail(4);
                else if(!loaded || input_count!=input_bytes || weight_count!=weight_bytes)fail(2);
                else begin
                    state<=LOAD_ACC;loaded<=0;output_valid<=0;compute_cycles<=0;
                    pixel_index<=0;ic<=0;oy<=0;ox<=0;ky<=0;kx<=0;
                    input_pixel_base<=0;output_row_base<=0;
                end
            end else if(upload_fire)begin
                if(input_write)input_count<=input_count+1'b1;
                else if(weight_write)begin
                    weight_count<=weight_count+1'b1;weight_pending<=1;
                    pending_tap<=upload_tap;pending_lane<=upload_lane;pending_data<=upload_data;
                    if(upload_tap+1<weight_oc_span)upload_tap<=upload_tap+1'b1;
                    else begin upload_tap<=0;upload_lane<=upload_lane+1'b1;end
                end else fail(2);
            end else case(state)
                IDLE: if(read_enable)begin
                    if(!output_valid || read_address>=output_words)fail(4);
                    else begin
                        read_valid<=1;
                        for(a=0;a<8;a=a+1)if(external_lane[a])read_lane<=a;
                    end
                end
                LOAD_ACC:state<=WAIT_ACC;
                WAIT_ACC:begin
                    for(a=0;a<8;a=a+1)accumulators[a]<=saved_first ? 32'sd0 : output_q[a];
                    ic<=0;ky<=0;kx<=0;input_plane_base<=input_pixel_base;input_row_base<=input_pixel_base;
                    input_address<=input_pixel_base;weight_tap<=0;state<=READ_PAIR;
                end
                READ_PAIR:state<=MAC;
                MAC:if(|overflow)fail(3);
                    else begin
                        for(a=0;a<8;a=a+1)if(a<noc)accumulators[a]<=sums[a][31:0];
                        weight_tap<=weight_tap+1'b1;
                        if(kx+1<kernel)begin kx<=kx+1'b1;input_address<=input_address+1'b1;state<=READ_PAIR;end
                        else if(ky+1<kernel)begin kx<=0;ky<=ky+1'b1;input_row_base<=input_row_base+iw;input_address<=input_row_base+iw;state<=READ_PAIR;end
                        else if(ic+1<nic)begin kx<=0;ky<=0;ic<=ic+1'b1;input_plane_base<=input_plane_base+input_plane_span;input_row_base<=input_plane_base+input_plane_span;input_address<=input_plane_base+input_plane_span;state<=READ_PAIR;end
                        else state<=STORE;
                    end
                STORE:begin
                    if(ox+1<ow)begin ox<=ox+1'b1;input_pixel_base<=input_pixel_base+stride;pixel_index<=pixel_index+1'b1;state<=LOAD_ACC;end
                    else if(oy+1<oh)begin ox<=0;oy<=oy+1'b1;output_row_base<=output_row_base+input_output_row_step;input_pixel_base<=output_row_base+input_output_row_step;pixel_index<=pixel_index+1'b1;state<=LOAD_ACC;end
                    else begin
                        state<=IDLE;block_done<=1;output_valid<=saved_final;partial_valid<=!saved_final;
                        partial_oc<=noc;partial_oh<=oh;partial_ow<=ow;partial_kernel<=kernel;partial_stride<=stride;
                    end
                end
                default:fail(4);
            endcase
        end
    end
endmodule
