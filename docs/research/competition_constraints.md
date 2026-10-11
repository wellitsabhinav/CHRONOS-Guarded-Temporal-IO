# Current competition constraints

Checked 2026-10-11 against [Jane Street's official announcement](https://blog.janestreet.com/protocol-emulator-asic-competition/).

The rules prescribe open-source programmable protocol emulation, IHP 130 nm
CMOS5L, **6x4** tiles and submission by **January 18, 2027**. The possible
8x4 increase is still conditional. Nominal tile allocation is roughly
0.7 mm²; it must not be substituted for the actual flow floorplan area.
UART, SPI and I²C are eventual programmable demonstrations. M0 establishes
only their timing substrate. The prospective shuttle is March 2027,
subject to foundry scheduling.

Official [CMOS5L template](https://github.com/TinyTapeout/ttihp-verilog-template/tree/cmos5l)
checked out at `b86a2a781484bcab7ba522dc5de540086695a430`.
Its workflow uses `TinyTapeout/tt-gds-action@ihp-cmos5l` and
`pdk: ihp-sg13cmos5l`. GDS, precheck, gate simulation and documentation
actions are retained. Apache-2.0 is retained. Template info.yaml comments
still list old tile sizes and dimensions: use the competition's explicit
6x4 choice, not those comments. The top interface provides eight inputs,
eight outputs, eight bidirectional data/OE pairs, clk, rst_n and ena.

[Local hardening](https://tinytapeout.com/guides/local-hardening/) describes
LibreLane, Docker and tt-support-tools. Its general IHP example selects
sg13g2, so do not use it unchanged for CMOS5L. Read the competition action
for the actual process and tool pins. [Precheck source](https://github.com/TinyTapeout/tt-precheck)
defines additional layout checks; synthesis is not physical qualification.

[Memory guidance](https://tinytapeout.com/specs/memory/) explicitly warns
that SRAM integration is changing. The [1024x8 walkthrough](https://github.com/urish/ttihp-sram-test)
shows macro instantiation/configuration and test transport; its prior-shuttle
success does not establish compatibility with a current CMOS5L build.
The [IHP library reference](https://ihp-open-pdk-docs.readthedocs.io/en/latest/contents/reference_libraries/sram.html)
lists macro variants. M0 needs only 448 event bits; no SRAM is instantiated.
