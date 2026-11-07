# Mixed hardware review scenario

This branch deliberately combines PR #3 documentation and PR #4 4.7 kohm resistor/MPN changes, then adds TP1 and replaces C1 with C3. Keep the individual commits visible during review.

- TP1 adds a physical OUT probe loop, one pad and a routed copper branch.
- C1 (0805 X7R) is removed; C3 is a new 1 uF radial film part with a 5 mm pitch and a portable generic STEP model. Its timing function and nominal capacitance remain the same. This is a demonstration ECO, not a claimed necessary circuit improvement.
- The old SMD timing escape via is removed because the plated C3 lead supplies the layer connection. The unused old ground stub is removed; the new ground lead is routed.
- All native rules remain unchanged. Native ERC, all-severity DRC, schematic parity, explicit 33-pad/9-net mapping and fitted-model resolution pass. Five pre-existing ignored native check types remain listed in the receipt; no exclusions were added.

Use exact part numbers for fitted production hardware. C3 and TP1 remain specification selections; the film model is a generic envelope, not manufacturer fit evidence. Verify C3 body height and LED brightness before ordering.

The baseline generator rebuilds the baseline. For ECO history, apply tools/review_scenarios.py in the documented order on matching branches. Native save/load normalization is restrained to changed objects to keep comparisons useful.
