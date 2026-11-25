`timescale 1ns/1ps
// Two integer dense layers and a synchronous full-code-space GELU ROM.
module integer_tail_engine(
    input wire clk,reset,input_we,input wire [7:0] input_addr,input wire [15:0] input_data,
    input wire start,output wire ready,output reg done,
    output wire result_valid,input wire result_ready,output wire [5:0] result_index,
    output wire signed [47:0] result_acc,output wire signed [15:0] result_y,
    output wire result_sat,result_error
);
    localparam IDLE=0,START_PRE=1,RUN_PRE=2,WRITE_G=3,START_FINAL=4,RUN_FINAL=5;
    reg [2:0] state;reg intermediate_error;
    reg [15:0] gelu_mem[0:65535];reg [15:0] gelu_q;reg [6:0] gelu_index;
    initial $readmemh("gelu.mem",gelu_mem);
    wire pre_ready,pre_done,pre_valid,pre_sat,pre_error;
    wire [6:0] pre_index;wire signed [47:0] pre_acc;wire signed [15:0] pre_y;
    wire final_ready,final_done,final_valid,final_error;
    wire [15:0] gelu_address=pre_y;
    assign ready=state==IDLE;
    assign result_valid=final_valid && state==RUN_FINAL;
    assign result_error=final_error|intermediate_error;
    integer_dense_engine u_pre(.clk(clk),.reset(reset),.input_we(input_we && ready),
        .input_addr(input_addr),.input_data(input_data),.start(state==START_PRE),.ready(pre_ready),.done(pre_done),
        .result_valid(pre_valid),.result_ready(state==WRITE_G),.result_index(pre_index),
        .result_acc(pre_acc),.result_y(pre_y),.result_sat(pre_sat),.result_error(pre_error));
    integer_dense_engine #(.IN_FEATURES(96),.OUT_FEATURES(42),.IN_ADDR_BITS(7),.OUT_ADDR_BITS(6),
        .WEIGHTS_FILE("final_weights.mem"),.BIASES_FILE("final_biases.mem"),
        .MULTIPLIERS_FILE("final_multipliers.mem"),.SHIFTS_FILE("final_shifts.mem")) u_final(
        .clk(clk),.reset(reset),.input_we(state==WRITE_G),.input_addr(gelu_index),.input_data(gelu_q),
        .start(state==START_FINAL),.ready(final_ready),.done(final_done),.result_valid(final_valid),
        .result_ready(result_ready && state==RUN_FINAL),.result_index(result_index),.result_acc(result_acc),
        .result_y(result_y),.result_sat(result_sat),.result_error(final_error));
    // Dedicated synchronous ROM read allows block RAM inference.
    always @(posedge clk) if(state==RUN_PRE && pre_valid) gelu_q<=gelu_mem[gelu_address];
    always @(posedge clk) begin
        if(reset) begin state<=IDLE;done<=0;intermediate_error<=0;gelu_index<=0;end
        else begin
            done<=0;
            case(state)
                IDLE: if(start) begin intermediate_error<=0;state<=START_PRE;end
                START_PRE: if(pre_ready) state<=RUN_PRE;
                RUN_PRE: if(pre_valid) begin
                    gelu_index<=pre_index;
                    if(pre_sat || pre_error) intermediate_error<=1;
                    state<=WRITE_G;
                end
                WRITE_G: if(gelu_index==95) state<=START_FINAL;else state<=RUN_PRE;
                START_FINAL: if(final_ready) state<=RUN_FINAL;
                RUN_FINAL: if(final_done) begin done<=1;state<=IDLE;end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
