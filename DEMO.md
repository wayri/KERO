# Demonstrating KERO in Pocket KiView

Keep the comparison pull requests open and unmerged so the original baseline remains available.

1. Open the repository and KERO.kicad_sch in Pocket KiView. Follow the RC loop and select U1A, R1 and C1. Open the BoM and find the matching references.
2. Open KERO.kicad_pcb. Highlight OUT, then inspect the two LEDs and the RC input. Open 3D to see the coin-cell holder, nominal cell, red/green LEDs and SMD parts. Native ERC/DRC results are saved under evidence; viewing them does not run KiCad.
3. Use commit history to compare the schematic-only stage with the routed-board stage. The board and its models appear as additions.
4. Open the timing pull request. Compare baseline with its head: R1 changes from 1M to 470k in both schematic and PCB, with a matching BoM change. Copper and component positions should remain unchanged. The ideal calculated blink rate changes from about 1.02 Hz to 2.18 Hz.
5. Open the layout pull request. Compare D1 and R6 movement, changed pad positions and corresponding track/via additions/removals. The schematic, BoM and pin/net memberships should remain identical to baseline.
6. Check each branch's native evidence and semantic comparison receipt. These receipts describe saved source changes; the live PR browser/UI still needs an installed Pocket KiView edition to demonstrate interaction.

Suggested 90-second recording: 15 s introduction; 20 s schematic/BoM; 15 s PCB/3D; 20 s timing PR; 20 s layout PR. Keep hardware behavior labelled as calculated until a physical board has been tested.
