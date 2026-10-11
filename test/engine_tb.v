`default_nettype none
`timescale 1ns/1ps
module engine_tb #(parameter integer TIME_W=32, parameter integer DEPTH=8);
    reg clk, rst_n, event_valid, event_drop;
    reg [TIME_W-1:0] event_timestamp;
    reg [23:0] event_state;
    wire event_ready;
    wire [TIME_W-1:0] time_now;
    wire [23:0] gpio_state;
    wire [((DEPTH>1) ? $clog2(DEPTH+1) : 1)-1:0] occupancy;
    wire [2:0] faults;
    wire epoch_closed, accepted, rejected, executed;
    chronos_engine #(.TIME_W(TIME_W), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst_n(rst_n), .event_valid(event_valid), .event_ready(event_ready),
        .event_drop(event_drop), .event_timestamp(event_timestamp), .event_state(event_state),
        .time_now(time_now), .gpio_state(gpio_state), .occupancy(occupancy), .faults(faults),
        .epoch_closed(epoch_closed), .accepted(accepted), .rejected(rejected), .executed(executed)
    );
endmodule
