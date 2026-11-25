`timescale 1ns/1ps
module tb_int16_dot_requant;
    reg clk=0,reset=1,start=0,in_valid=0,in_last=0,out_ready=0;
    always #5 clk=~clk;
    reg signed [47:0] bias=0;
    reg [31:0] multiplier=0;
    reg [6:0] shift=0;
    reg signed [15:0] in_x=0,in_w=0;
    wire start_ready,in_ready,out_valid,out_saturated,out_error;
    wire signed [47:0] out_acc;
    wire signed [15:0] out_y;
    int16_dot_requant dut(.*);
    integer fd,rc,total,i,j,n,expected_sat,expected_error,gap;
    reg [47:0] expected_acc;
    reg [15:0] expected_y;
    initial begin
        repeat(3) @(negedge clk);reset=0;
        // Reset during a partially received dot product must discard it.
        @(negedge clk);start=1;bias=123;multiplier=1;shift=0;
        @(negedge clk);start=0;in_valid=1;in_x=2;in_w=3;in_last=0;
        @(negedge clk);in_valid=0;reset=1;
        repeat(3) @(negedge clk);reset=0;
        repeat(4) @(negedge clk);
        if(!start_ready || out_valid) $fatal(1,"Reset did not abort transaction");
        fd=$fopen("dot_vectors.txt","r");if(!fd) $fatal(1,"Missing vectors");
        rc=$fscanf(fd,"%d\n",total);if(rc!=1) $fatal(1,"Header");
        for(i=0;i<total;i=i+1) begin
            rc=$fscanf(fd,"%h %h %h %d %h %h %d %d\n",bias,multiplier,shift,n,expected_acc,expected_y,expected_sat,expected_error);
            if(rc!=8) $fatal(1,"Vector header %0d",i);
            while(!start_ready) @(negedge clk);
            start=1;@(negedge clk);start=0;
            for(j=0;j<n;j=j+1) begin
                rc=$fscanf(fd,"%h %h\n",in_x,in_w);if(rc!=2) $fatal(1,"Term");
                gap=(i+j)%3;repeat(gap) @(negedge clk);
                while(!in_ready) @(negedge clk);
                in_last=(j==n-1);in_valid=1;
                @(negedge clk);in_valid=0;
            end
            wait(out_valid);@(negedge clk);
            if(out_acc!==expected_acc || out_y!==expected_y || out_saturated!==expected_sat[0] || out_error!==expected_error[0])
                $fatal(1,"case=%0d acc=%h/%h y=%h/%h sat=%b/%b err=%b/%b",i,out_acc,expected_acc,out_y,expected_y,out_saturated,expected_sat[0],out_error,expected_error[0]);
            repeat(3) begin
                @(negedge clk);
                if(!out_valid || out_acc!==expected_acc || out_y!==expected_y) $fatal(1,"Unstable backpressure result");
            end
            out_ready=1;@(negedge clk);out_ready=0;
        end
        $fclose(fd);$display("PASS: %0d directed/random dot products, input gaps, output backpressure, reset abort",total);$finish;
    end
    initial begin repeat(100000) @(posedge clk);$fatal(1,"Timeout");end
endmodule
