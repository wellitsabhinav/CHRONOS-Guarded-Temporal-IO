/*
 * Copyright (c) 2026 CHRONOS contributors
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none
`timescale 1ns/1ps

module tt_um_chronos (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // selection masks outputs; time/dispatch continue
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    wire valid, ready, drop;
    wire [31:0] timestamp, time_now;
    wire [23:0] state_in, gpio_state;
    wire [3:0] occupancy;
    wire [2:0] faults;
    wire epoch_closed, accepted, rejected, executed;
    wire [7:0] readback;
    chronos_loader loader (
        .clk(clk), .rst_n(rst_n), .ena(ena), .ui_in(ui_in),
        .event_valid(valid), .event_ready(ready), .event_drop(drop),
        .event_timestamp(timestamp), .event_state(state_in),
        .time_now(time_now), .gpio_state(gpio_state), .occupancy(occupancy),
        .faults(faults), .epoch_closed(epoch_closed),
        .accepted(accepted), .rejected(rejected), .executed(executed), .readback(readback)
    );
    chronos_engine engine (
        .clk(clk), .rst_n(rst_n), .event_valid(valid), .event_ready(ready),
        .event_drop(drop), .event_timestamp(timestamp), .event_state(state_in),
        .time_now(time_now), .gpio_state(gpio_state), .occupancy(occupancy), .faults(faults),
        .epoch_closed(epoch_closed), .accepted(accepted), .rejected(rejected), .executed(executed)
    );
    assign uo_out = ena ? (ui_in[7] ? readback : gpio_state[7:0]) : 8'b0;
    assign uio_out = ena ? gpio_state[15:8] : 8'b0;
    assign uio_oe = ena ? gpio_state[23:16] : 8'b0;
    wire _unused = &{uio_in, 1'b0};

endmodule
