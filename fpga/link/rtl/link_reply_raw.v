// Experimental tagged response serializer. Bus master samples OLD data at
// posedge bus_clk; this domain prepares the NEXT byte after that same edge.
// Metadata is immutable from SYS offer until the four-phase done acknowledgement.
module link_reply_raw(
    input wire bus_clk, reset_n, arm, dir, offer,
    input wire [49:0] metadata,
    input wire [7:0] row_byte,
    input wire [15:0] ram_color,ram_depth,
    output reg [7:0] data_o,
    output reg done,started,error,progress,
    output wire [5:0] row_index,
    output reg [9:0] ram_address,
    output wire ram_enable,
    // Diagnostic only: serializer byte index captured when done rose. Stable from
    // that edge until the offer drops; read by reply_edge_monitor after a
    // synchronized done flag. Does not feed any pre-existing output.
    output reg [11:0] done_index
);
    wire active_reset_n=reset_n && arm;
    (* ASYNC_REG="TRUE" *) reg [49:0] metadata_meta,metadata_bus;
    reg [11:0] index;
    reg [15:0] crc,current_word;
    reg [9:0] current_tag,ram_tag;
    reg current_valid,ram_valid;
    wire bulk=metadata_bus[48],tile=metadata_bus[49];
    wire depth_plane=metadata_bus[40];
    wire [11:0] payload_end=tile?12'd2064:12'd80;
    wire [11:0] last_index=bulk?payload_end+1'b1:12'd15;
    wire payload=bulk && index>=16 && index<payload_end;
    wire [10:0] payload_index=index-12'd16;
    wire [15:0] ram_word=depth_plane?ram_depth:ram_color;
    assign row_index=index<16?6'd0:(index>=80?6'd63:payload_index[5:0]);
    assign ram_enable=offer && dir && !done && !error;
    function [15:0] crc_byte;
        input [15:0] c;input [7:0] b;
        reg [15:0] v;integer k;
        begin v=c^{b,8'h00};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    always @* begin
        if(index<8) data_o=8'hc3;
        else if(index<14) data_o=metadata_bus[(index-8)*8+:8];
        else if(index==14) data_o=crc[7:0];
        else if(index==15) data_o=crc[15:8];
        else if(payload) data_o=tile?(index[0]?current_word[15:8]:current_word[7:0]):row_byte;
        else if(bulk && index==payload_end) data_o=crc[7:0];
        else if(bulk && index==payload_end+1'b1) data_o=crc[15:8];
        else data_o=0;
    end
    always @(posedge bus_clk or negedge active_reset_n) begin
        if(!active_reset_n) begin
            metadata_meta<=0;metadata_bus<=0;index<=0;crc<=16'hffff;
            done<=0;started<=0;error<=0;progress<=0;
            current_word<=0;current_tag<=0;current_valid<=0;
            ram_address<=0;ram_tag<=0;ram_valid<=0;done_index<=0;
        end else begin
            metadata_meta<=metadata;metadata_bus<=metadata_meta;
            if(!offer) begin
                index<=0;crc<=16'hffff;done<=0;started<=0;error<=0;
                current_valid<=0;ram_valid<=0;ram_address<=0;
            end else if(!dir) begin
                // DIR may be LOW while READY is offered, before the first byte.
                // Once started, its falling edge cancels via the SYS handshake;
                // a clock arriving in that phase also latches a local abort.
                if(started && !done) begin done<=1;error<=1;done_index<=index;end
            end else if(!done) begin
                started<=1;
                ram_tag<=ram_address;ram_valid<=1;
                if(index[3:0]==15) progress<=~progress;
                // Two metadata stages have settled by the third prefix edge.
                // Port B has already loaded word0; header edges prime word1.
                if(index==2) begin
                    current_word<=ram_word;current_tag<=ram_tag;current_valid<=ram_valid;
                    ram_address<=1;
                end
                if(payload && tile && (!current_valid || current_tag!=payload_index[10:1] ||
                   (index[0] && payload_index[10:1]!=1023 &&
                    (!ram_valid || ram_tag!=payload_index[10:1]+1'b1)))) begin
                    error<=1;done<=1;done_index<=index;
                end else begin
                    if(payload && tile) begin
                        if(!index[0]) ram_address<=payload_index[10:1]>=1022?10'd1023:payload_index[10:1]+2'd2;
                        else if(payload_index[10:1]!=1023) begin
                            current_word<=ram_word;current_tag<=ram_tag;current_valid<=ram_valid;
                        end
                    end
                    if((index>=8 && index<14) || payload) crc<=crc_byte(crc,data_o);
                    if(index==last_index) begin done<=1;done_index<=index;end
                    else index<=index+1'b1;
                end
            end
        end
    end
endmodule
