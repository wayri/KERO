# KERO thermal analysis

Actual WayriCAD QuickTherm 4.5.0 saved-board solves were run on the C3 film-capacitor / 4.7 kohm LED-resistor design. These are illustrative steady board-temperature estimates, not measured temperatures or package junction qualification.

## Open the saved results

- [Portable field map](../analysis/thermal/nominal.pocket-kivi.json): open alongside [KERO.kicad_pcb](../KERO.kicad_pcb) in the KiCad review extension. Contains both 80 by 58 layer-temperature grids, saved XY coordinates and an exact PCB SHA-256 binding.
- [Native saved simulation](../analysis/thermal/nominal.results.json): load through WayriCAD QuickTherm Files / Load simulation. Native loading verified current source state, can_restore=true, and no source issues.
- [HTML report](../analysis/thermal/nominal.html) and [complete producer JSON](../analysis/thermal/nominal.json).
- [Coarse native result](../analysis/thermal/coarse.results.json), [fine configuration](../analysis/thermal/nominal.config.json), [coarse configuration](../analysis/thermal/coarse.config.json), [model inputs](../analysis/thermal/model-inputs.json), and [comparison and source receipts](../analysis/thermal/summary.json).

Saved PCB SHA-256: 67c8981fce6cd003b58aa396febdd7da22f7feb196f664df3d18c9e04c6a2fc5. A matching fingerprint identifies geometry; it does not validate material or cooling assumptions.

## Computed results

| Quantity | 40 by 29 grid | 80 by 58 grid |
|---|---:|---:|
| Heat deposited | 1.113858653 mW | 1.113858653 mW |
| Top-layer sampled maximum | 25.164069 C | 25.176332 C |
| Bottom-layer sampled maximum | 25.162736 C | 25.166176 C |
| Relative heat-balance residual | 1.45e-12 | 9.29e-12 |
| Active cells per layer | 1,160 | 4,640 |
| Unresolved barrel stencils | 0 | 0 |

The largest component board-site or source-peak change between grids is 0.013846 C at R7, about 7.9% of the fine-grid maximum rise of 0.176332 C. This comparison documents remaining numerical sensitivity; it is not a local contact-resolution convergence certificate. The fine top-layer maximum is a mixed copper/dielectric cell near R7, not a resistor body or junction temperature.

All ten dissipating components have unknown junction temperature because no package-to-board thermal resistance or internal package model was supplied. Component coverage therefore reports ten power sources and zero solved junctions. Both board fields were solved successfully.

## Declared model

Heat inputs come from the nominal 3 V cycle-average [power budget](../evidence/analysis/power-budget.json): R1-R7 resistor losses, the sum of U1A/U1B dissipation in U1, and D1/D2 electrical power. Their sum is 1.113858653 mW. Treating all LED electrical power as heat is conservative with respect to optical emission, which is unknown.

- Ambient 25 C; both faces exposed with illustrative natural-convection coefficient 5 W/m2/K. Radiation is disabled (emissivity zero), so all solved heat leaves by convection.
- Isotropic homogeneous FR4 conductivity 0.3 W/m/K; copper 385 W/m/K; 25 um plated barrels.
- Two explicit 35 um copper layers with midplanes at 0.0175 and 1.5825 mm within the saved 1.6 mm board span. Copper polygons, drilled holes, plated connections and footprint positions come from the actual saved board.
- Finite-volume area/face copper rasterization and producer annulus stencils. Component heat enters producer footprint contact-area proxies. No fabricated package Rtheta or mounting heat sink is applied.

These inputs are illustrative screening assumptions, not manufacturer-certified material values. Omitting radiation increases temperature for this model, but the overall model is not a guaranteed worst case: enclosure airflow, battery/package shadowing, physical contacts and laminate properties are unknown. The result excludes cell internal heat, capacitor loss and copper Joule heating; the latter remains separately quantified by the PI studies. It models cycle averages rather than startup or individual flashes.

## Reproduce

Use an existing KiCad-native Python with pcbnew, wx, NumPy, SciPy and Matplotlib, and WayriCAD 4.5.0 source. No installation, environment provisioning, shared-source edit or PCB edit is performed.

    <prepared-KiCad-Python> -B tools/analyze_thermal.py --wayricad-source <WayriCAD-4.5.0-source>

Run from this project in a fresh output destination or preserve the prior analysis/thermal outputs first: the helper refuses to overwrite existing result deliverables. It verifies all power-budget source hashes before solving, reloads the native files, and verifies the board hash after each solve. Inputs, source evidence and producer version are retained.

The source PCB has no explicit saved stackup. QuickTherm 4.5.0 geometry collection does not expose a request-level stackup override. The helper temporarily adapts only that collector stackup call, delegating to the original shared stackup function with the explicit layer records above. The original function is restored in a finally block. This is recorded input adaptation, not a change to copper geometry, solver equations or saved board files. The config files contain native CLI-compatible settings, but this design additionally requires the recorded stackup adapter when solving; use the helper for reproduction.

The native result writer and report writer created the saved simulations, HTML, complete numerical JSON and portable companion. Native files retain front-depth elevation metadata supported by explicit layer geometry; the report producer leaves the companion optional zBasis unspecified, preserving its own export behavior. XY registration and layer samples remain in both.

## Verification and storage

Both solves and native reloads completed. Source hashes stayed unchanged; numerical heat balance closed to better than 1e-11 relative. Grid sensitivity, unknown package junctions and modelling exclusions remain explicit. Extension visualization compatibility is separately checked by the integrating task.

No dependencies were downloaded or installed. The run retained about 2.1 MiB of results on D: and removed its task-owned Matplotlib font cache. Observed availability before/after was C: 10.55814/10.55811 GiB and D: 184.74154/184.73938 GiB; concurrent writes can affect these measurements. C: remains below the required 100 GiB reserve, so new storage-intensive work remains suspended there.
