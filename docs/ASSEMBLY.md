# KERO assembly guide

This is an unbuilt educational board. Start from the PR’s exact schematic, PCB and BoM revision; do not mix a changed BoM with an older board.

1. Check the bare board and fit the SMD resistors, capacitors and SOIC-8 LMV358A. Align U1 pin 1 with the board marking.
2. Fit D1 red and D2 low-forward-voltage yellow-green LEDs. Match each cathode/flat to the footprint.
3. Fit the Keystone 1058 holder. Inspect its pads for bridges before inserting a cell.
4. Check supply resistance and soldering with the cell removed. Insert one primary CR2032 with the marked polarity.
5. Remove the cell to switch off. Do not recharge it.

The BoM’s generic passives/LEDs are specification selections; a package model is not proof of an exact supplier part. Keep the native model and source provenance files with the project.
