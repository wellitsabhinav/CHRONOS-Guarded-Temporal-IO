`default_nettype none
module formal_top(input wire clk);
    (* anyseq *) reg rst_n, event_valid, event_drop;
    (* anyseq *) reg [3:0] event_timestamp;
    (* anyseq *) reg [2:0] event_state;
    wire event_ready;
    wire [3:0] time_now;
    wire [2:0] gpio_state, faults;
    wire [1:0] occupancy;
    wire epoch_closed, accepted, rejected, executed;
    chronos_engine #(.TIME_W(4), .GPIO_W(3), .DEPTH(3)) dut (
        .clk(clk), .rst_n(rst_n), .event_valid(event_valid), .event_drop(event_drop),
        .event_timestamp(event_timestamp), .event_state(event_state), .event_ready(event_ready),
        .time_now(time_now), .gpio_state(gpio_state), .faults(faults), .occupancy(occupancy),
        .epoch_closed(epoch_closed), .accepted(accepted), .rejected(rejected), .executed(executed)
    );
endmodule
