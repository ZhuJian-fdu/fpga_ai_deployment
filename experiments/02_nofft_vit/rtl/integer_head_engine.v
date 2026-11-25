`timescale 1ns/1ps
// Runtime input RAM, fixed layer weights; no expected-result ROM/comparator.
module integer_head_engine(
    input wire clk,reset,input wire input_we,input wire [6:0] input_addr,
    input wire [15:0] input_data,input wire start,output wire ready,output reg done,
    output wire result_valid,input wire result_ready,output wire [5:0] result_index,
    output wire signed [47:0] result_acc,output wire signed [15:0] result_y,
    output wire result_sat,result_error
);
    reg [15:0] weights_mem[0:4031],inputs_mem[0:95];
    reg [47:0] biases_mem[0:41];
    reg [31:0] multipliers_mem[0:41];reg [6:0] shifts_mem[0:41];
    initial begin
        $readmemh("weights.mem",weights_mem);$readmemh("biases.mem",biases_mem);
        $readmemh("multipliers.mem",multipliers_mem);$readmemh("shifts.mem",shifts_mem);
    end
    localparam IDLE=0,PREP=1,START_DOT=2,READ=3,SEND=4,WAIT_RESULT=5;
    reg [2:0] state;
    reg [5:0] output_index;reg [6:0] term_index;
    reg signed [15:0] x_reg,w_reg;reg signed [47:0] bias_reg;
    reg [31:0] multiplier_reg;reg [6:0] shift_reg;
    wire core_start_ready,core_in_ready,core_out_valid;
    assign ready=state==IDLE;
    assign result_index=output_index;
    assign result_valid=core_out_valid && state==WAIT_RESULT;
    always @(posedge clk) if(input_we && ready && input_addr<96) inputs_mem[input_addr]<=input_data;
    int16_dot_requant u_dot(.clk(clk),.reset(reset),.start(state==START_DOT),.start_ready(core_start_ready),
        .bias(bias_reg),.multiplier(multiplier_reg),.shift(shift_reg),
        .in_valid(state==SEND),.in_ready(core_in_ready),.in_x(x_reg),.in_w(w_reg),.in_last(term_index==95),
        .out_valid(core_out_valid),.out_ready(result_ready && state==WAIT_RESULT),
        .out_acc(result_acc),.out_y(result_y),.out_saturated(result_sat),.out_error(result_error));
    always @(posedge clk) begin
        if(reset) begin state<=IDLE;done<=0;output_index<=0;term_index<=0;end
        else begin
            done<=0;
            case(state)
                IDLE: if(start) begin output_index<=0;term_index<=0;state<=PREP;end
                PREP: begin bias_reg<=biases_mem[output_index];multiplier_reg<=multipliers_mem[output_index];
                    shift_reg<=shifts_mem[output_index];state<=START_DOT;end
                START_DOT: if(core_start_ready) state<=READ;
                READ: begin x_reg<=inputs_mem[term_index];w_reg<=weights_mem[output_index*12'd96+term_index];state<=SEND;end
                SEND: if(core_in_ready) begin
                    if(term_index==95) state<=WAIT_RESULT;
                    else begin term_index<=term_index+1'b1;state<=READ;end
                end
                WAIT_RESULT: if(core_out_valid && result_ready) begin
                    if(output_index==41) begin done<=1;state<=IDLE;end
                    else begin output_index<=output_index+1'b1;term_index<=0;state<=PREP;end
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
