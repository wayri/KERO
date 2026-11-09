# BoM value and MPN comparison

R6/R7 change from 3.3k to 4.7k, then receive Vishay Manufacturer/MPN/Rating/Datasheet fields. The PCB geometry and all pin/net memberships are unchanged.

A native load/save initially normalized hidden-field serialization on unrelated footprints. A follow-up commit preserves their original bytes; the final PR comparison is exactly four modified objects: R6 and R7 in both schematic and PCB. No objects are added or removed.

See docs/BOM-ECO.md and evidence/semantic-diff.json. Physical brightness and battery life remain unmeasured.
