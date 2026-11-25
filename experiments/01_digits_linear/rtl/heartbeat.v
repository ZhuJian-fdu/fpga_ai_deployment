`timescale 1ns/1ps
// Board-independent LED counter. The board wrapper must synchronize reset,
// supply its real clock frequency and handle LED polarity.
module heartbeat #(
    parameter integer CLK_HZ = 50000000  // example; NOT a confirmed board clock
) (
    input wire clk,
    input wire rst,
    output reg led
);
    localparam integer HALF_PERIOD = CLK_HZ / 2;
    localparam integer WIDTH = (HALF_PERIOD <= 1) ? 1 : $clog2(HALF_PERIOD);
    reg [WIDTH-1:0] counter;
    always @(posedge clk) begin
        if (rst) begin
            counter <= 0;
            led <= 0;
        end else if (counter == HALF_PERIOD-1) begin
            counter <= 0;
            led <= ~led;
        end else counter <= counter + 1'b1;
    end
endmodule
