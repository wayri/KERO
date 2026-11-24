# Encoder routing convention

Default to native KiCad tangent circular arcs at track bends, with straight runs
between them. Simplify redundant staircase vertices before rounding; do not
approximate curves with a dense series of tiny straight tracks. KiCad has no
native Bézier copper-track primitive, so decorative Bézier graphics are not a
substitute for routed, net-assigned copper.

Preserve pads, vias, branch junctions, widths, layers, net assignments and design
rules. Keep a constrained corridor where smoothing would violate clearance or
connectivity, and record the exception. Do not move components to make a
cosmetic routing change pass.

Generate automated geometry in a detached candidate. Refill and save zones with
native KiCad, compare connected-pad partitions, and require no new DRC or
schematic parity findings before replacing the source. Bind evidence to the
saved board hash. Existing PI and thermal results remain historical evidence
for their recorded board hash until rerun on changed copper.

The reusable candidate generator is `../tools/smooth_encoder_routing.py`; its
output alone is not acceptance. See `evidence/curved-routing.json` for the
accepted conversion and native gate results.
