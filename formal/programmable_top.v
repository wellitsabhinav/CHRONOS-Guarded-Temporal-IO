`default_nettype none
module programmable_formal_top(input wire clk);
    (* anyseq *) reg rst_n,program_write,program_start;
    (* anyseq *) reg [7:0] gpio_in;
    (* anyseq *) reg [3:0] program_address;
    (* anyseq *) reg [31:0] program_data;
    chronos_programmable_core #(.TIME_W(5),.GPIO_W(2),.DEPTH(2),.PRED_W(1),.GEN_W(2),.GUARDS_ENABLED(1)) dut (
        .clk(clk),.rst_n(rst_n),.gpio_in(gpio_in),.program_write(program_write),.program_start(program_start),
        .program_address(program_address),.program_data(program_data)
    );
endmodule
