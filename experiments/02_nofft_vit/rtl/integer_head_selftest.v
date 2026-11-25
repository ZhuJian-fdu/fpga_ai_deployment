`timescale 1ns/1ps
// 16 development vectors x 42 outputs. Synchronous ROM reads permit BRAM.
// This verifies a single fixed final layer, not the preceding neural network.
module integer_head_selftest(input wire clk, reset, output reg done, failed);
    reg [15:0] weights_mem[0:4031],inputs_mem[0:1535];
    reg [47:0] biases_mem[0:41],expected_acc_mem[0:671];
    reg [31:0] multipliers_mem[0:41];
    reg [6:0] shifts_mem[0:41];
    reg [15:0] expected_out_mem[0:671];
    reg [0:0] expected_sat_mem[0:671];
    initial begin
        $readmemh("weights.mem",weights_mem);$readmemh("inputs.mem",inputs_mem);
        $readmemh("biases.mem",biases_mem);$readmemh("multipliers.mem",multipliers_mem);
        $readmemh("shifts.mem",shifts_mem);$readmemh("expected_acc.mem",expected_acc_mem);
        $readmemh("expected_out.mem",expected_out_mem);$readmemh("expected_sat.mem",expected_sat_mem);
    end
    localparam PREP=0,START=1,READ=2,SEND=3,WAIT_RESULT=4,FINISHED=5;
    reg [2:0] state;
    reg [3:0] sample_index;
    reg [5:0] output_index;
    reg [6:0] term_index;
    wire [11:0] weight_address=output_index*12'd96+term_index;
    wire [10:0] input_address=sample_index*11'd96+term_index;
    wire [9:0] reference_address=sample_index*10'd42+output_index;
    reg signed [15:0] x_reg,w_reg;
    reg signed [47:0] bias_reg;
    reg [31:0] multiplier_reg;
    reg [6:0] shift_reg;
    reg [47:0] expected_acc;
    reg [15:0] expected_y;
    reg expected_sat;
    wire core_start_ready,core_in_ready,core_out_valid,core_saturated,core_error;
    wire signed [47:0] core_acc;
    wire signed [15:0] core_y;
    int16_dot_requant u_dot(
        .clk(clk),.reset(reset),.start(state==START),.start_ready(core_start_ready),
        .bias(bias_reg),.multiplier(multiplier_reg),.shift(shift_reg),
        .in_valid(state==SEND),.in_ready(core_in_ready),.in_x(x_reg),.in_w(w_reg),.in_last(term_index==95),
        .out_valid(core_out_valid),.out_ready(state==WAIT_RESULT),.out_acc(core_acc),.out_y(core_y),
        .out_saturated(core_saturated),.out_error(core_error));
    always @(posedge clk) begin
        if(reset) begin
            state<=PREP;sample_index<=0;output_index<=0;term_index<=0;done<=0;failed<=0;
        end else case(state)
            PREP: begin
                bias_reg<=biases_mem[output_index];multiplier_reg<=multipliers_mem[output_index];
                shift_reg<=shifts_mem[output_index];expected_acc<=expected_acc_mem[reference_address];
                expected_y<=expected_out_mem[reference_address];expected_sat<=expected_sat_mem[reference_address];
                state<=START;
            end
            START: if(core_start_ready) state<=READ;
            READ: begin x_reg<=inputs_mem[input_address];w_reg<=weights_mem[weight_address];state<=SEND;end
            SEND: if(core_in_ready) begin
                if(term_index==95) state<=WAIT_RESULT;
                else begin term_index<=term_index+1'b1;state<=READ;end
            end
            WAIT_RESULT: if(core_out_valid) begin
                if(core_error || core_acc!=expected_acc || core_y!=expected_y || core_saturated!=expected_sat) begin
                    failed<=1;state<=FINISHED;
                end else if(sample_index==15 && output_index==41) begin done<=1;state<=FINISHED;end
                else begin
                    term_index<=0;
                    if(output_index==41) begin output_index<=0;sample_index<=sample_index+1'b1;end
                    else output_index<=output_index+1'b1;
                    state<=PREP;
                end
            end
            FINISHED: state<=FINISHED;
            default: begin failed<=1;state<=FINISHED;end
        endcase
    end
endmodule
