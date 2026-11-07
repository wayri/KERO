# Actual Xyce transient evidence

The six 12-second simulations completed successfully with Xyce 7.8.0. Every detected complete frame decoded `hello world` (10 complete frames total). The supply ramp and timestep cases are finite checks, not general startup or component qualification.

| Case | Complete frames | Last-frame mean current (uA) | RMS (uA) | Maximum sampled whole-transient current (mA) |
|---|---:|---:|---:|---:|
| v2p5-ramp1ms | 2 | 233.555 | 233.630 | 0.978620 |
| v3-ramp1ms | 2 | 279.081 | 279.149 | 1.174109 |
| v3p3-ramp1ms | 2 | 306.752 | 306.816 | 1.291812 |
| v3-ramp100ms | 1 | 279.082 | 279.150 | 0.290787 |
| v3-ramp1s | 1 | 279.082 | 279.150 | 0.290788 |
| v3-ramp1ms-refined | 2 | 279.082 | 279.150 | 1.174109 |

At 3 V, the last complete frame is 3.665841 s. Reducing maximum timestep from 0.5 to 0.25 ms changed corresponding pulse widths by at most 0.147100 ms and mean current by 0.000640 uA. All width symbols remained unchanged.

## Reproduce

Use an already installed Python 3 and Xyce 7.8 executable; the script has no third-party Python requirements and installs nothing. Run from KERO, selecting a new output directory to preserve the retained run:

```powershell
python -B tools/simulate_encoder.py --xyce D:/xyce/Xyce_7.8/bin/Xyce.exe --model /path/to/tlv9042.lib --output encoded-model/spice-reproduction
```

Obtain the official TI PSpice family model [SBOMB62](https://www.ti.com/lit/zip/SBOMB62), TLV9042 Rev. B, separately. The exact library SHA-256 for this run is `75019b68d85b360113538587ae6231b3e7b48e511d444a953799f1756dfd0543`. It is instantiated once per amplifier channel; this is an applicability assumption for TLV9044, not a quad-package-specific model. The vendor library is not redistributed here. Portable `circuit.cir` files reference `tlv9042.lib`; the runner supplies the actual external path in a temporary runtime deck.

## Evidence and interpretation

- `summary.json` binds results to the E192 `design.json`, helper, and external model hashes. `execution.json` records the actual Python command, exit status and independent analytic integration checks.
- Each case contains the portable circuit, complete Xyce log, detailed `result.json`, losslessly gzip-compressed full sampled `waveform.csv.gz`, and compact `trace.json` for plotting. Full-waveform hashes are in the results; plotting downsampling preserves crossing brackets and the sampled current peak. `trace.json` is an explicitly named generic scalar-time schema, not a claimed WayriCAD or extension-supported result format.
- Edges are linear-interpolated crossings of `V(OUT)-V(VBAT)/2` after the supply ramp. A LOW gap greater than 0.5 s marks a frame boundary. A complete frame runs from one such rising edge to the next, contains exactly eleven pulses, and decodes with the supplied logarithmic eight-symbol codebook. Incomplete leading/trailing fragments are excluded. This conservative policy also excludes the first payload before an observed preceding frame gap.
- Positive cell draw is `-I(VBAT)`, including the macro supply currents, external network, the 300 nF supply bypass capacitor, and both generic LED circuits with 15 kohm series resistors. Mean current is charge divided by frame duration; RMS integrates the square of the piecewise-linear sampled current exactly. No battery ESR, capacity, electrochemistry, optical output or lifetime is modeled.
- The result key `maximum_sampled_startup_current_A` means the largest sampled current over the entire 12-second transient including startup. For slow ramps, the maximum can occur later during normal switching; it is not a continuous-time guaranteed peak.
- Xyce warns that `T_ABS` on `R_NOISELESS` is ignored and that model node 49 has one device terminal. These messages and recovered nonlinear/step failures remain visible in each log. Runs had zero failed linear solves, approximately 2200 rejected timestep attempts each, and reached the requested 12 s with exit zero. The timestep comparison checks numerical sensitivity, not all PSpice-to-Xyce model semantics.
- These cases start with discharged timing capacitors and UIC. Passing a 1 s ramp does not establish recovery after partial discharge, arbitrary hot-plug/brownout states, full-temperature behavior, or physical prototype performance.

All generated runtime decks, uncompressed waveforms and raw scratch logs from this suite were removed after equivalent retained evidence was verified; no vendor model or earlier private trial was copied into this directory.
