// Test-only subset. See README.md; this is not a Gowin simulation library.
module IOBUF(input wire I, OEN, inout wire IO, output wire O);
    assign IO = OEN ? 1'bz : I;
    assign O = IO;
endmodule

// Test-only equivalent of the Yosys Gowin ALU ADDSUB mode used by GFX.
module ALU(output wire SUM, COUT, input wire I0, I1, I3, CIN);
    parameter ALU_MODE=0;
    wire select_bit = I3 ? (I0 ^ I1) : (I0 ^ ~I1);
    initial if (ALU_MODE != 2) $fatal(1,"ALU test model: unsupported configuration");
    assign SUM = select_bit ^ CIN;
    assign COUT = select_bit ? CIN : I0;
endmodule

module SPX9 #(
    parameter READ_MODE=0, WRITE_MODE=2, BIT_WIDTH=18,
    parameter [2:0] BLK_SEL=3'b000,
    parameter RESET_MODE="ASYNC",
    parameter [287:0] INIT_RAM_00=288'b0,
    parameter [287:0] INIT_RAM_01=288'b0,
    parameter [287:0] INIT_RAM_02=288'b0,
    parameter [287:0] INIT_RAM_03=288'b0,
    parameter [287:0] INIT_RAM_04=288'b0,
    parameter [287:0] INIT_RAM_05=288'b0,
    parameter [287:0] INIT_RAM_06=288'b0,
    parameter [287:0] INIT_RAM_07=288'b0,
    parameter [287:0] INIT_RAM_08=288'b0,
    parameter [287:0] INIT_RAM_09=288'b0,
    parameter [287:0] INIT_RAM_0A=288'b0,
    parameter [287:0] INIT_RAM_0B=288'b0,
    parameter [287:0] INIT_RAM_0C=288'b0,
    parameter [287:0] INIT_RAM_0D=288'b0,
    parameter [287:0] INIT_RAM_0E=288'b0,
    parameter [287:0] INIT_RAM_0F=288'b0,
    parameter [287:0] INIT_RAM_10=288'b0,
    parameter [287:0] INIT_RAM_11=288'b0,
    parameter [287:0] INIT_RAM_12=288'b0,
    parameter [287:0] INIT_RAM_13=288'b0,
    parameter [287:0] INIT_RAM_14=288'b0,
    parameter [287:0] INIT_RAM_15=288'b0,
    parameter [287:0] INIT_RAM_16=288'b0,
    parameter [287:0] INIT_RAM_17=288'b0,
    parameter [287:0] INIT_RAM_18=288'b0,
    parameter [287:0] INIT_RAM_19=288'b0,
    parameter [287:0] INIT_RAM_1A=288'b0,
    parameter [287:0] INIT_RAM_1B=288'b0,
    parameter [287:0] INIT_RAM_1C=288'b0,
    parameter [287:0] INIT_RAM_1D=288'b0,
    parameter [287:0] INIT_RAM_1E=288'b0,
    parameter [287:0] INIT_RAM_1F=288'b0,
    parameter [287:0] INIT_RAM_20=288'b0,
    parameter [287:0] INIT_RAM_21=288'b0,
    parameter [287:0] INIT_RAM_22=288'b0,
    parameter [287:0] INIT_RAM_23=288'b0,
    parameter [287:0] INIT_RAM_24=288'b0,
    parameter [287:0] INIT_RAM_25=288'b0,
    parameter [287:0] INIT_RAM_26=288'b0,
    parameter [287:0] INIT_RAM_27=288'b0,
    parameter [287:0] INIT_RAM_28=288'b0,
    parameter [287:0] INIT_RAM_29=288'b0,
    parameter [287:0] INIT_RAM_2A=288'b0,
    parameter [287:0] INIT_RAM_2B=288'b0,
    parameter [287:0] INIT_RAM_2C=288'b0,
    parameter [287:0] INIT_RAM_2D=288'b0,
    parameter [287:0] INIT_RAM_2E=288'b0,
    parameter [287:0] INIT_RAM_2F=288'b0,
    parameter [287:0] INIT_RAM_30=288'b0,
    parameter [287:0] INIT_RAM_31=288'b0,
    parameter [287:0] INIT_RAM_32=288'b0,
    parameter [287:0] INIT_RAM_33=288'b0,
    parameter [287:0] INIT_RAM_34=288'b0,
    parameter [287:0] INIT_RAM_35=288'b0,
    parameter [287:0] INIT_RAM_36=288'b0,
    parameter [287:0] INIT_RAM_37=288'b0,
    parameter [287:0] INIT_RAM_38=288'b0,
    parameter [287:0] INIT_RAM_39=288'b0,
    parameter [287:0] INIT_RAM_3A=288'b0,
    parameter [287:0] INIT_RAM_3B=288'b0,
    parameter [287:0] INIT_RAM_3C=288'b0,
    parameter [287:0] INIT_RAM_3D=288'b0,
    parameter [287:0] INIT_RAM_3E=288'b0,
    parameter [287:0] INIT_RAM_3F=288'b0
)(output wire [35:0] DO, input wire CLK, CE, OCE, RESET, WRE,
  input wire [2:0] BLKSEL, input wire [13:0] AD, input wire [35:0] DI);
    reg [17:0] memory [0:1023];
    reg [17:0] dout;
    integer i;
    initial begin
        if (BIT_WIDTH != 18 || READ_MODE != 0 || WRITE_MODE != 2 ||
            BLK_SEL != 0 || RESET_MODE != "ASYNC" ||
           INIT_RAM_00 !== 288'b0 ||
           INIT_RAM_01 !== 288'b0 ||
           INIT_RAM_02 !== 288'b0 ||
           INIT_RAM_03 !== 288'b0 ||
           INIT_RAM_04 !== 288'b0 ||
           INIT_RAM_05 !== 288'b0 ||
           INIT_RAM_06 !== 288'b0 ||
           INIT_RAM_07 !== 288'b0 ||
           INIT_RAM_08 !== 288'b0 ||
           INIT_RAM_09 !== 288'b0 ||
           INIT_RAM_0A !== 288'b0 ||
           INIT_RAM_0B !== 288'b0 ||
           INIT_RAM_0C !== 288'b0 ||
           INIT_RAM_0D !== 288'b0 ||
           INIT_RAM_0E !== 288'b0 ||
           INIT_RAM_0F !== 288'b0 ||
           INIT_RAM_10 !== 288'b0 ||
           INIT_RAM_11 !== 288'b0 ||
           INIT_RAM_12 !== 288'b0 ||
           INIT_RAM_13 !== 288'b0 ||
           INIT_RAM_14 !== 288'b0 ||
           INIT_RAM_15 !== 288'b0 ||
           INIT_RAM_16 !== 288'b0 ||
           INIT_RAM_17 !== 288'b0 ||
           INIT_RAM_18 !== 288'b0 ||
           INIT_RAM_19 !== 288'b0 ||
           INIT_RAM_1A !== 288'b0 ||
           INIT_RAM_1B !== 288'b0 ||
           INIT_RAM_1C !== 288'b0 ||
           INIT_RAM_1D !== 288'b0 ||
           INIT_RAM_1E !== 288'b0 ||
           INIT_RAM_1F !== 288'b0 ||
           INIT_RAM_20 !== 288'b0 ||
           INIT_RAM_21 !== 288'b0 ||
           INIT_RAM_22 !== 288'b0 ||
           INIT_RAM_23 !== 288'b0 ||
           INIT_RAM_24 !== 288'b0 ||
           INIT_RAM_25 !== 288'b0 ||
           INIT_RAM_26 !== 288'b0 ||
           INIT_RAM_27 !== 288'b0 ||
           INIT_RAM_28 !== 288'b0 ||
           INIT_RAM_29 !== 288'b0 ||
           INIT_RAM_2A !== 288'b0 ||
           INIT_RAM_2B !== 288'b0 ||
           INIT_RAM_2C !== 288'b0 ||
           INIT_RAM_2D !== 288'b0 ||
           INIT_RAM_2E !== 288'b0 ||
           INIT_RAM_2F !== 288'b0 ||
           INIT_RAM_30 !== 288'b0 ||
           INIT_RAM_31 !== 288'b0 ||
           INIT_RAM_32 !== 288'b0 ||
           INIT_RAM_33 !== 288'b0 ||
           INIT_RAM_34 !== 288'b0 ||
           INIT_RAM_35 !== 288'b0 ||
           INIT_RAM_36 !== 288'b0 ||
           INIT_RAM_37 !== 288'b0 ||
           INIT_RAM_38 !== 288'b0 ||
           INIT_RAM_39 !== 288'b0 ||
           INIT_RAM_3A !== 288'b0 ||
           INIT_RAM_3B !== 288'b0 ||
           INIT_RAM_3C !== 288'b0 ||
           INIT_RAM_3D !== 288'b0 ||
           INIT_RAM_3E !== 288'b0 ||
           INIT_RAM_3F !== 288'b0)
            $fatal(1,"SPX9 test model: unsupported configuration");
        for (i=0; i<1024; i=i+1) memory[i]=0;
        dout=0;
    end
    // UG285 table 3-2/3-3: AD[13:4] word, AD[1:0] 9-bit write enables.
    // Asynchronous output reset does not clear the storage array.
    always @(posedge CLK) begin
        if (CE && BLKSEL == BLK_SEL && WRE) begin
            if (AD[0]) memory[AD[13:4]][8:0] <= DI[8:0];
            if (AD[1]) memory[AD[13:4]][17:9] <= DI[17:9];
        end
    end
    // READ_MODE=0 bypasses OCE; WRITE_MODE=2 produces the previous word.
    always @(posedge CLK or posedge RESET) begin
        if (RESET) dout <= 0;
        else if (CE && BLKSEL == BLK_SEL) dout <= memory[AD[13:4]];
    end
    assign DO = {18'bx, dout};
endmodule
