`timescale 1ns/1ps
// 8N1 transmitter. Accept data exactly when valid && ready at a rising edge.
module uart_tx #(parameter integer CLKS_PER_BIT=434) (
    input wire clk, input wire rst,
    input wire [7:0] data, input wire valid,
    output wire ready, output reg tx
);
    localparam WIDTH=$clog2(CLKS_PER_BIT);
    reg [WIDTH-1:0] timer;
    reg [9:0] frame;
    reg [3:0] bit_index;
    reg busy;
    assign ready=!busy && !rst;
    always @(posedge clk) begin
        if(rst) begin
            timer<=0; frame<=10'h3ff; bit_index<=0; busy<=0; tx<=1;
        end else if(!busy) begin
            if(valid) begin
                frame<={1'b1,data,1'b0}; tx<=0;
                bit_index<=0; timer<=CLKS_PER_BIT-1; busy<=1;
            end
        end else if(timer!=0) timer<=timer-1'b1;
        else if(bit_index==9) begin busy<=0; tx<=1; end
        else begin
            bit_index<=bit_index+1'b1;
            frame<={1'b1,frame[9:1]}; tx<=frame[1]; timer<=CLKS_PER_BIT-1;
        end
    end
endmodule
