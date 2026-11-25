`timescale 1ns/1ps
module acx720_v3_ai_top (
    input wire clk, input wire reset_n, input wire uart_rx,
    output wire uart_tx, output wire led0, output wire led1, output wire led2
);
    (* ASYNC_REG = "TRUE" *) reg [1:0] reset_sync=2'b11;
    // The oscillator runs continuously. Synchronize both button edges as data,
    // so no asynchronously reset register can drive an inferred BRAM control.
    always @(posedge clk) reset_sync<={reset_sync[0],!reset_n};
    // BRAM controls must only change synchronously, including reset assertion.
    reg core_reset=1'b1;
    always @(posedge clk) core_reset<=reset_sync[1];
    heartbeat #(.CLK_HZ(50000000)) u_heartbeat(.clk(clk),.rst(core_reset),.led(led0));
    digit_uart u_ai(.clk(clk),.rst(core_reset),.rx(uart_rx),.tx(uart_tx),.completed(led1),.error(led2));
endmodule
