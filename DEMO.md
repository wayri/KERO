# Demonstrating KERO in Pocket KiView

Keep the comparison pull requests open and unmerged so the original baseline remains available.

1. Open the repository and KERO.kicad_sch in Pocket KiView. Follow the RC loop and select U1A, R1 and C1 (C3 in the mixed ECO). Open the BoM and find the matching references.
2. Open KERO.kicad_pcb. Highlight OUT, then inspect the two LEDs and the RC input. Open 3D to see the coin-cell holder, nominal cell, red/green LEDs and SMD parts. Native ERC/DRC results are saved under evidence; viewing them does not run KiCad.
3. Use commit history to compare the schematic-only stage with the routed-board stage. The board and its models appear as additions.
4. Open the timing pull request. Compare baseline with its head: R1 changes from 1M to 470k in both schematic and PCB, with a matching BoM change. Copper and component positions should remain unchanged. The ideal calculated blink rate changes from about 1.02 Hz to 2.18 Hz.
5. Open the layout pull request. Compare D1 and R6 movement, changed pad positions and corresponding track/via additions/removals. The schematic, BoM and pin/net memberships should remain identical to baseline.
6. Check each branch's native evidence and semantic comparison receipt. These receipts describe saved source changes; the live PR browser/UI still needs an installed Pocket KiView edition to demonstrate interaction.

Suggested 90-second recording: 15 s introduction; 20 s schematic/BoM; 15 s PCB/3D; 20 s timing PR; 20 s layout PR. Keep hardware behavior labelled as calculated until a physical board has been tested.

## Published references

- [Introduction: 232f023](https://github.com/wayri/KERO/commit/232f023)
- [Schematic and BoM: 635a9a3](https://github.com/wayri/KERO/commit/635a9a3)
- [PCB and models: 54ecd3c](https://github.com/wayri/KERO/commit/54ecd3c)
- [Verified baseline: db7a709](https://github.com/wayri/KERO/commit/db7a709)
- [Timing comparison PR #5](https://github.com/wayri/KERO/pull/5)
- [Layout comparison PR #6](https://github.com/wayri/KERO/pull/6)

## Extended review sequence

- PR #7: documentation only; expect zero electrical object changes.
- PR #8: R6/R7 values and Vishay MPNs; compare schematic properties, PCB properties and CSV BoM.
- PR #9: combined ECO; step through TP1 addition, C1 removal/C3 addition, routing repair, PI export and thermal export commits. Read the commit notes, PR discussion and inline comments with their pinned revision.
- In PR #9 open analysis/README.md, then a .pocket-kivi.json with the matching KERO PCB. Compare PI potential/loss/current-density fields and the QuickTherm temperature fields; inspect source-match status and numerical assumptions.

Current PR numbers changed when demo branches were renamed. PRs #1–#4 remain historical; use #5–#9 for the current walkthrough.

## Encoded-message and analysis demonstration

In PR #16 open `encoder/Encoder.kicad_sch` and follow the power sheet, three RC banks and majority/LED decoder. Inspect shared project variables and the 79-part BoM, then open the 40 × 40 mm routed board and bottom coin-cell holder. Compare 83b9344 with d951d83 to see the routing repair; saved-object differences are tracks/vias only. Native ERC/DRC/parity and all 40 connected nets are recorded.

Open `encoder/analysis/README.md` for the executed cell-current/loss budget and native/portable WayriCAD files. Load one selected `.pocket-kivi.json` with the matching encoder PCB, inspect potential/loss/current-density or board-temperature fields, and check the source-match status. Keep the shifted GND reference, unresolved mean-GND pad region, unconverged local peaks, and board-versus-junction temperature limits visible. Analysis additions do not change the routed PCB.
