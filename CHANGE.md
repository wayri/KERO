# Timing comparison

R1 changes from 1 MΩ to 470 kΩ. Ideal calculated blink frequency changes from 1.02 Hz to 2.18 Hz.

Pocket KiView’s actual saved-object comparison reports exactly three modified objects: the R1 schematic symbol, R1 PCB footprint value, and calculated-timing note. Zero objects are added or removed; no copper or pad geometry changes. See evidence/semantic-diff.json.

Native KiCad 10.0.6 ERC, DRC, unconnected-item and schematic-parity checks report zero findings. All 32 pad/net mappings match. These checks do not establish measured oscillator or battery performance.
