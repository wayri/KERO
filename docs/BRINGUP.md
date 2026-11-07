# KERO bring-up and review checklist

Record the tested Git SHA, cell voltage, ambient conditions and fitted BoM before making a hardware claim. The design range is 2.5–3.3 V. No measured results are supplied here.

| Check | Expected basis | Actual observation |
| --- | --- | --- |
| U1 supply | Cell voltage, correct polarity | To be measured |
| VREF | Approximately VBAT / 4 | To be measured |
| TIMING | Charge/discharge between about 0.20 and 0.40 × VBAT | To be measured |
| OUT | Alternating high/low output; near 1.02 Hz at nominal baseline R/C | To be measured |
| LEDs | Red at OUT high; green at OUT low | To be measured |

Do not fill this table with simulated or calculated values presented as measurements. A probe can load the timing node; record its impedance. Stop if the battery heats or polarity is wrong.

For a documentation-only PR, the saved-object comparison should report zero schematic/PCB changes. Review the prose diff on GitHub, then verify the viewer still opens the exact unchanged drawing.
