`timescale 1ns/1ps
module acx720_v3_integer_head_top(input wire clk50m,reset_n,output wire led0,led1,led2);
    (* ASYNC_REG="TRUE" *) reg [2:0] reset_pipe=3'b111;
    always @(posedge clk50m) reset_pipe<={reset_pipe[1:0],!reset_n};
    wire reset=reset_pipe[2];
    reg [24:0] heartbeat=0;
    always @(posedge clk50m) begin
        if(reset) heartbeat<=0;else heartbeat<=heartbeat+1'b1;
    end
    wire done,failed;
    integer_head_selftest u_test(.clk(clk50m),.reset(reset),.done(done),.failed(failed));
    assign led0=done && !failed;
    assign led1=heartbeat[24];
    assign led2=failed;
endmodule
