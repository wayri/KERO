# Saved engineering studies

Open these files on the same revision as KERO.kicad_pcb in Pocket KiView. The portable companion retains the complete producer mesh/results and the PCB's exact solve-time SHA-256.

| Study | Extension companion | Native WayriCAD file |
| --- | --- | --- |
| High-output battery rail | [PI high](pi/KERO.vbat-high.pocket-kivi.json) | [Native high](pi/KERO.vbat-high.quick-pi.results.json) |
| Low-output battery rail | [PI low](pi/KERO.vbat-low.pocket-kivi.json) | [Native low](pi/KERO.vbat-low.quick-pi.results.json) |
| High-output ground return, reversed test current | [PI ground](pi/KERO.gnd-high-reversed.pocket-kivi.json) | [Native ground](pi/KERO.gnd-high-reversed.quick-pi.results.json) |

The GND file uses a shifted mathematical reference, not a physical 3 V ground; interpret drop magnitudes. [Replayable PI batch study](pi/KERO.quick-pi.study.json) contains explicit loads, mesh and copper assumptions. Native results reopen through WayriCAD Files → Load simulation; companion files open as saved analysis in the extension. Both retain full numerical data.

The actual extension reader produced six spatial fields per PI file: potential, cell power and current density, separately on F.Cu/B.Cu. All have an exact matching KERO board binding. A property-preview limit warning is expected; full source remains available. File-format/parser verification is distinct from a tested browser gesture.

See [power and numerical limits](../docs/POWER-ANALYSIS.md), [layout checks](../docs/LAYOUT.md), [native receipt](../evidence/summary.json), [refinement receipt](../evidence/analysis/wayricad-summary.json), and [actual viewer adapter probes](../evidence/analysis/viewer-probes.json). Local peak current density is not converged; no local thermal signoff is claimed.

## QuickTherm board-temperature fields

[Portable thermal map](thermal/nominal.pocket-kivi.json) · [native saved simulation](thermal/nominal.results.json) · [HTML report](thermal/nominal.html) · [complete JSON](thermal/nominal.json) · [fine configuration](thermal/nominal.config.json) · [coarse comparison](thermal/coarse.results.json) · [assumptions and receipts](thermal/summary.json).

The extension reader recognizes both 80 by 58 saved layer heatmaps and two valid spatial surfaces with the matching PCB hash. Fine-grid peak board temperature is 25.1763 C for the illustrative 25 C ambient/1.11386 mW heat case. This is a steady board screen; junction temperatures are unknown. See [thermal method and limits](../docs/THERMAL-ANALYSIS.md).
