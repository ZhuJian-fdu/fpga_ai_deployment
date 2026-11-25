`timescale 1ns/1ps
// Signed int16 dot product + signed int48 bias. Wrap on MAC overflow and
// latch error (never silently accept overflow). Output uses nearest-even
// right shift then symmetric int16 saturation [-32767,32767].
module int16_dot_requant (
    input wire clk, reset,
    input wire start, output wire start_ready,
    input wire signed [47:0] bias,
    input wire [31:0] multiplier, input wire [6:0] shift,
    input wire in_valid, output wire in_ready,
    input wire signed [15:0] in_x, in_w, input wire in_last,
    output reg out_valid, input wire out_ready,
    output reg signed [47:0] out_acc,
    output reg signed [15:0] out_y,
    output reg out_saturated, output reg out_error
);
    localparam IDLE=0, MAC=1, MULTIPLY=2, SCALE=3, RESULT=4;
    reg [2:0] state;
    reg signed [47:0] acc;
    reg [31:0] multiplier_reg;
    reg [6:0] shift_reg;
    reg error_reg;
    reg signed [80:0] scale_product;
    wire signed [31:0] term_product=$signed(in_x)*$signed(in_w);
    wire signed [48:0] sum_ext=$signed({acc[47],acc})+
                                     $signed({{17{term_product[31]}},term_product});
    wire [80:0] magnitude=scale_product[80] ? -scale_product : scale_product;
    reg [80:0] quotient, remainder, half, mask;
    always @* begin
        quotient=magnitude >> shift_reg;
        mask=(81'd1 << shift_reg)-1'b1;
        remainder=magnitude & mask;
        half=0;
        if (shift_reg!=0) begin
            half=81'd1 << (shift_reg-1'b1);
            if (remainder>half || (remainder==half && quotient[0])) quotient=quotient+1'b1;
        end
    end
    assign start_ready=(state==IDLE);
    assign in_ready=(state==MAC);
    always @(posedge clk) begin
        if (reset) begin
            state<=IDLE;acc<=0;multiplier_reg<=0;shift_reg<=0;error_reg<=0;
            scale_product<=0;out_valid<=0;out_acc<=0;out_y<=0;out_saturated<=0;out_error<=0;
        end else case(state)
            IDLE: if (start) begin
                acc<=bias;multiplier_reg<=multiplier;shift_reg<=shift;
                error_reg<=(shift>79);state<=MAC;
            end
            MAC: if (in_valid) begin
                acc<=sum_ext[47:0];error_reg<=error_reg || (sum_ext[48]!=sum_ext[47]);
                if(in_last) state<=MULTIPLY;
            end
            MULTIPLY: begin
                scale_product<=$signed(acc)*$signed({1'b0,multiplier_reg});state<=SCALE;
            end
            SCALE: begin
                out_acc<=acc;out_error<=error_reg;out_valid<=1;
                out_saturated<=(quotient>32767);
                if(quotient>32767) out_y<=scale_product[80] ? -16'sd32767 : 16'sd32767;
                else out_y<=scale_product[80] ? -$signed(quotient[15:0]) : $signed(quotient[15:0]);
                state<=RESULT;
            end
            RESULT: if(out_ready) begin out_valid<=0;state<=IDLE;end
            default: begin state<=IDLE;out_valid<=0;end
        endcase
    end
endmodule
