`timescale 1ns/1ps
module digit_uart #(
    parameter integer CLKS_PER_BIT=434,
    parameter integer TIMEOUT_CYCLES=2500000
) (
    input wire clk, input wire rst, input wire rx,
    output wire tx, output wire completed, output wire error
);
    wire [7:0] rx_data,tx_data;
    wire rx_valid,rx_error,tx_valid,tx_ready;
    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_rx(
        .clk(clk),.rst(rst),.rx(rx),.data(rx_data),.valid(rx_valid),.framing_error(rx_error)
    );
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx(
        .clk(clk),.rst(rst),.data(tx_data),.valid(tx_valid),.ready(tx_ready),.tx(tx)
    );
    digit_protocol #(.TIMEOUT_CYCLES(TIMEOUT_CYCLES)) u_protocol(.*);
endmodule
