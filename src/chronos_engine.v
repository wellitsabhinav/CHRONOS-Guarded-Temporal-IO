/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
module chronos_engine #(
    parameter integer TIME_W = 32,
    parameter integer GPIO_W = 24,
    parameter integer DEPTH = 8,
    parameter integer COUNT_W = (DEPTH > 1) ? $clog2(DEPTH+1) : 1
) (
    input wire clk, rst_n, event_valid,
    output wire event_ready,
    input wire event_drop,
    input wire [TIME_W-1:0] event_timestamp,
    input wire [GPIO_W-1:0] event_state,
    output reg [TIME_W-1:0] time_now,
    output reg [GPIO_W-1:0] gpio_state,
    output reg [COUNT_W-1:0] occupancy,
    output reg [2:0] faults,
    output reg epoch_closed, accepted, rejected, executed
);
    localparam integer PTR_W = (DEPTH > 1) ? $clog2(DEPTH) : 1;
    localparam integer LAST = DEPTH-1;
    localparam [PTR_W-1:0] LAST_PTR = LAST[PTR_W-1:0];
    localparam [COUNT_W-1:0] CAPACITY = DEPTH[COUNT_W-1:0];
    reg [TIME_W+GPIO_W-1:0] entries [0:DEPTH-1];
    reg [PTR_W-1:0] read_ptr, write_ptr;
    reg [TIME_W-1:0] last_time;
    reg have_last;
    wire [TIME_W+GPIO_W-1:0] head = entries[read_ptr];
    wire [TIME_W-1:0] head_time = head[TIME_W-1:0];
    wire pop = !epoch_closed && (occupancy != 0) && (head_time <= time_now);
    wire deadline_bad = epoch_closed || (event_timestamp <= time_now);
    wire order_bad = have_last && (event_timestamp <= last_time);
    wire consume = event_valid && event_ready;
    wire push = consume && !deadline_bad && !order_bad;
    assign event_ready = rst_n && ((occupancy < CAPACITY) || pop);

    always @(posedge clk) begin
        if (!rst_n) begin
            time_now <= 0;
            gpio_state <= 0;
            occupancy <= 0;
            read_ptr <= 0;
            write_ptr <= 0;
            last_time <= 0;
            have_last <= 0;
            faults <= 0;
            epoch_closed <= 0;
            accepted <= 0;
            rejected <= 0;
            executed <= 0;
        end else begin
            time_now <= time_now + 1'b1;
            accepted <= push;
            rejected <= consume && (deadline_bad || order_bad);
            executed <= 1'b0;
            if (event_valid && !event_ready && event_drop) faults[0] <= 1'b1;
            if (consume && order_bad) faults[1] <= 1'b1;
            if (consume && deadline_bad) faults[2] <= 1'b1;
            if (pop) begin
                read_ptr <= (read_ptr == LAST_PTR) ? {PTR_W{1'b0}} : read_ptr + 1'b1;
                if (head_time == time_now) begin
                    gpio_state <= head[TIME_W+GPIO_W-1:TIME_W];
                    executed <= 1'b1;
                end else faults[2] <= 1'b1;
            end
            if (push) begin
                entries[write_ptr] <= {event_state, event_timestamp};
                write_ptr <= (write_ptr == LAST_PTR) ? {PTR_W{1'b0}} : write_ptr + 1'b1;
                last_time <= event_timestamp;
                have_last <= 1'b1;
            end
            case ({push, pop})
                2'b10: occupancy <= occupancy + 1'b1;
                2'b01: occupancy <= occupancy - 1'b1;
                default: begin end
            endcase
            if (&time_now) begin
                epoch_closed <= 1'b1;
                occupancy <= 0;
                if ((occupancy != 0) && !(pop && (occupancy == 1))) faults[2] <= 1'b1;
            end
        end
    end
`ifdef FORMAL
    // Formal-only observers; no ports, registers or initial values in silicon.
    reg f_past_valid = 1'b0;
    (* anyconst *) reg [PTR_W-1:0] f_slot;
    always @(posedge clk) begin
        f_past_valid <= 1'b1;
        assume(f_slot < DEPTH);
        if (!f_past_valid) assume(!rst_n);
        if (f_past_valid) begin
            assert(occupancy <= CAPACITY);
            assert(read_ptr <= LAST_PTR && write_ptr <= LAST_PTR);
            if (!$past(rst_n)) begin
                assert(time_now == 0 && occupancy == 0 && gpio_state == 0);
                assert(faults == 0 && !epoch_closed && !accepted && !rejected && !executed);
            end else begin
                // Execute only an existing, due, non-late head; never an empty slot.
                if (executed) begin
                    assert($past(occupancy != 0 && !epoch_closed));
                    assert($past(head_time == time_now));
                    assert(gpio_state == $past(head[TIME_W+GPIO_W-1:TIME_W]));
                end
                if (gpio_state != $past(gpio_state)) assert(executed);
                if (accepted) begin
                    assert($past(event_timestamp > time_now && !epoch_closed));
                    if ($past(have_last)) assert(last_time > $past(last_time));
                end
                if ($past(push && write_ptr == f_slot))
                    assert(entries[f_slot] == $past({event_state, event_timestamp}));
                else
                    assert(entries[f_slot] == $past(entries[f_slot]));
                // Retirement always advances the head once, preserving FIFO order.
                if ($past(pop))
                    assert(read_ptr == (($past(read_ptr) == LAST_PTR) ? 0 : $past(read_ptr) + 1'b1));
                else assert(read_ptr == $past(read_ptr));
            end
        end
    end
`endif
endmodule
