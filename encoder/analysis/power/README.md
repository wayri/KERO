# Encoder cell draw and component power

This is an executed Xyce 7.8.0 model study bound to the corrected routed PCB SHA-256 `08437dcfd8f304786d4f3444a26bd56c443661ea22bd25d69c3900906c6ef109`. Native XML connectivity and values match all 79 components and 194 logical terminals. The board, BoM, native netlist, design intent, circuit-equivalence evidence and encoded timing specification hashes are retained in `power-budget.json`. This is circuit-model evidence, not measured hardware performance.

The one new 12 s nominal transient completed with simulator exit 0 in 167.921 s. Its last complete decoded frame runs from 8.322450868 to 11.988177924 s; both complete frames decode `hello world`. The 117-column, 34,179-sample waveform is retained losslessly as `waveform.csv.gz` with its uncompressed SHA-256. Runtime scratch was removed after decompression/hash verification. The external TI library is not redistributed.

| Nominal 3 V result | Value |
|---|---:|
| Cell mean current | 279.081393 uA |
| Cell RMS current | 279.149494 uA |
| Largest sampled settled-frame current | 290.788378 uA |
| Largest sampled 1 ms supply-ramp current | 1.174109 mA |
| Cell electrical input power | 837.244178 uW |
| U1 / U2 / U3 assigned heat | 119.867619 / 119.849527 / 119.365178 uW |
| All resistor heat | 338.274826 uW |
| D1 / D2 electrical absorption, assigned entirely to heat | 66.209706 / 73.677323 uW |
| Total assigned component heat | 837.244179 uW |
| Energy-balance residual | -1.676922 pW (-2.002907e-9 relative) |

## Accounting method

Each of the twelve amplifier channels has a zero-volt current sensor on both inputs, both rails and its output. Channel absorption is the sum of Vterminal times Iinto-terminal across all five pins; the four channels are summed into each physical U package. Input power is included, not discarded. Internal macro stored-energy change is treated as negligible over the settled frame; adjacent-frame input powers differ by about 0.338 nW.

Resistor heat is the time mean of voltage difference squared divided by R. LED power is terminal voltage times its unique series-resistor current (R58 or R59). All of that electrical LED absorption is conservatively assigned to heat because optical conversion and exact LED MPNs are unknown. Ideal capacitor heat is zero; each capacitor retains endpoint charge change, integrated terminal charge, endpoint energy change and mean terminal power. Real capacitor ESR, dielectric loss and leakage are unknown and excluded. The external capacitor net energy change is 2.866335 pJ over the selected frame.

Integrals use actual nonuniform sample times, interpolated frame endpoints, and the exact integral of the product of two linear interpolants on each interval. Analytic checks cover linear mean/current-square, a bilinear power reference, and clipped endpoint interpolation. The energy residual is cell input minus all component absorption minus external capacitor stored-energy change divided by frame time. Small numerical residuals establish accounting consistency, not physical prediction accuracy.

## Explicit model-boundary findings

The raw measured VEE-only GND-current gate failed: its maximum sampled current residual was 0.527110 uA. The TI macro contains internal elements connected to SPICE global zero, beyond its exposed VEE pin. Each channel's inferred global-ground return is therefore calculated as the sum of its five external terminal currents and assigned to the physical package GND pin for the PCB load map. The raw failed check remains visible; reconstructed closure is algebraic and is not an independent model validation.

A separate node-current audit found that printed Xyce I(D1)/I(D2) differed transiently from their unique series-resistor terminal currents by 168.029 nA and 68.434 nA. The cause of that reporting discrepancy is not assumed. LED terminal currents are reconstructed from the series resistors by KCL, and the discrepancy is retained in each LED record. With these explicit mappings, maximum VBAT and physical-GND rail closure residuals are 1.321 pA and 1.275 pA. The original raw-ground gate remains false; the reconstructed-ground gate passes the unchanged 10 nA threshold.

TI's [TLV9042 Rev. B family PSpice model](https://www.ti.com/lit/zip/SBOMB62) is instantiated per channel for the [TLV9044 device family](https://www.ti.com/lit/ds/symlink/tlv9044.pdf). This applicability assumption is not a package-specific quad model. Full logs retain ignored noise-temperature parameters, internal node warnings and recovered timestep failures. No noise analysis or manufacturer model qualification in Xyce is claimed.

## Downstream PI and thermal contract

`nominal.part_heat_W` maps component reference to cycle-average watts. `component-powers.csv` is the matching tabular view. BT1 is not assigned internal cell heat: its ESR is unknown and its KiCad footprint represents the holder. Capacitors explicitly have ideal-model zero heat with real loss marked unknown.

`nominal.pi_pad_loads` and `pi-pad-loads.csv` identify reference, pin, native net and rail. Positive means draw from VBAT or return into GND. They provide signed means, output-HIGH/LOW conditional means, sampled min/max, a nonnegative individual-peak envelope, and pad currents at the actual coincident settled cell-current peak. Conditional state means omit transition-straddling sample intervals.

For positive-only mean-load DC PI, `pi-mean-policy.json` lists exactly which non-capacitor positive means to include and every signed omitted capacitor mean. Included VBAT and GND sums are 279.081392680 and 279.081392859 uA. Their differences from cell mean are -0.0215 pA and +0.1569 pA. Omitted signed capacitor rail means are +0.1698 pA (VBAT) and +0.000323 pA (GND); endpoint and integrated capacitor charge residuals are recorded. No negative load is silently clipped.

The sum of individual positive pad peaks is 400.988523 uA on VBAT and 395.862412 uA on GND. These are noncoincident stress envelopes, not battery-current peaks or a simultaneous state. Mean-load DC copper heating is based on squared mean branch currents; it is not the full waveform-average I-squared-R loss. Trace resistance and resulting voltage-drop feedback are absent from this schematic solve.

Cell internal resistance is an explicit postprocessing scenario only: Pinternal=Irms^2 times R, giving 0.779244 uW per 10 ohm at this waveform. The budget lists 0/10/20/30/50/100 ohm scenarios, with mean/peak voltage drops. No specific cell ESR, loaded capacity, lifetime, or coupled droop is asserted.

## Reproduction and retained failures

Use installed Python with NumPy and Xyce; nothing is installed or provisioned. Supply the official model separately. Run from KERO with a new output directory:

```powershell
python -B tools/analyze_encoder_power.py --xyce D:/xyce/Xyce_7.8/bin/Xyce.exe --model /path/to/tlv9042.lib --output encoder/analysis/power-reproduction
```

For a saved completed run, the same helper accepts `--postprocess-saved` to recompute accounting directly from the verified gzip waveform without launching Xyce. A temporary `--reuse-runtime` recovery mode is only for an owned completed uncompressed runtime and validates its generated netlist and recorded successful solver status. The published run used one solver invocation; a NumPy-scalar JSON serialization error was repaired by reprocessing its saved output. Subsequent accounting refinements likewise used the same waveform. The failed raw ground check and all helper output remain retained.

`execution.json`, `solver-execution.json`, `postprocessing-execution.json`, and `helper-output.log` distinguish solver completion from postprocessing attempts. Capacity fields in the successful recovery invocation describe that invocation, after the raw solver file already existed; they are not a fabricated pre-solver capacity measurement. The solver itself was bounded to D: scratch and one process, with a 150 MiB output allowance. C: remained below the user's operating reserve; no dependencies, models, build trees or scratch were installed there.

The earlier six supply/ramp/timestep cases remain applicable to the same nominal circuit and external macro identity. This new instrumented run differs from the previous 3 V current mean by 0.0000919 uA and corresponding pulse widths by at most 0.060983 ms. Reuse of that evidence does not include layout parasitics, component tolerances, brownouts or arbitrary partial capacitor charge.
