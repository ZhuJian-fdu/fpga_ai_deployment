`timescale 1ns/1ps
module acx720_v3_heartbeat_top #(
    parameter integer CLK_HZ = 50000000
) (
    input wire clk,
    input wire reset_n,
    output wire led0
);
    // S4: active low. Async assertion, two-clock synchronous release.
    // Initial values map to FPGA configuration INIT bits.
    (* ASYNC_REG = "TRUE" *) reg [1:0] reset_sync = 2'b11;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) reset_sync <= 2'b11;
        else reset_sync <= {reset_sync[0], 1'b0};
    end
    // V3 LEDs have grounded cathodes: logic 1 lights LED0.
    heartbeat #(.CLK_HZ(CLK_HZ)) u_heartbeat (
        .clk(clk), .rst(reset_sync[1]), .led(led0)
    );
endmodule
