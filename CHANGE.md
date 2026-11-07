# Layout comparison

D1 and R6 move 2.54 mm left. The RED silkscreen label and reference placement follow the change, and the board is rerouted.

The schematic and BoM remain identical to baseline; all 32 pin/net memberships remain unchanged. Pocket KiView’s actual semantic comparison detects 7 modified objects (two footprints, four pads and the RED label), 30 added copper objects and 30 removed copper objects. See evidence/semantic-diff.json.

KiCad 10.0.6 ERC, DRC, unconnected-item and schematic-parity checks all report zero findings. All component models resolve. Physical hardware remains unbuilt and untested.
