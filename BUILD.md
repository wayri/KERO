# Rebuild and validate KERO

Use KiCad 10.0.6's bundled Python, which provides pcbnew. No pip installations are needed. The generator defaults to the standard Windows KiCad library installation; edit the LIB constant if your KiCad libraries are installed elsewhere.

Run from this directory:

```powershell
& 'C:/Program Files/KiCad/10.0/bin/python.exe' tools/build_demo.py --variant baseline
& 'C:/Program Files/KiCad/10.0/bin/python.exe' tools/validate.py
```

Other generation variants are timing and layout. The timing variant changes R1 to 470k. The layout variant repositions D1/R6 and reroutes the board without changing the baseline schematic or electrical pin/net mapping. Work in a separate checkout for experiments; these commands replace this directory's generated native files and evidence.

The native gate runs ERC and DRC with all severities, DRC schematic parity, XML netlist export, exact pin/net comparison across all 32 pads, model-path resolution, schematic/PCB SVG exports and a native 3D render. Source hashes are checked before/after validation. Native CLI output and exit codes are retained in evidence/commands.json. Five native KiCad default ignored checks are listed explicitly in the receipt; no exclusions or severity relaxations were added. There are no copper zones: connectivity comes from saved tracks, vias and pads.

The PNG schematic is a rasterization of the native SVG; the SVG is the authoritative preview. There is no hardware test or transistor-level simulation in this gate. CLI sandbox registry warnings were captured; they did not prevent valid checks or exports.

Libraries and models are vendored for viewing and assembly review. The rebuild tool additionally needs the matching standard KiCad source libraries for regeneration. Its layout router is a small deterministic demo helper, not a general KiCad router.

## Mixed ECO and analysis

This branch is a staged ECO, with 33 electrical pads. Do not run the baseline generator over it. Start from the documented BoM branch and apply add-testpoint, then film-capacitor with tools/review_scenarios.py; validate each milestone. tools/analyze_power.py computes the current/power budget and optionally runs prepared WayriCAD 4.5 copper studies. See docs/ECO.md and docs/POWER-ANALYSIS.md.
