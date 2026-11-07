# Cell draw, losses and WayriCAD analysis

These are calculations on the mixed ECO, not bench measurements. Native design hashes are in [power-budget.json](../evidence/analysis/power-budget.json) and [wayricad-summary.json](../evidence/analysis/wayricad-summary.json).

## Operating assumptions

One loaded 3.00 V CR2032 supply, LMV358ADR, R1=1 Mohm, C3=1 uF, R2=402 kohm, R3=100 kohm, R4/R5=300/100 kohm, R6/R7=4.7 kohm. Assumed output levels are 2.98 V/0.02 V and LED forward drops are 1.8 V red/2.0 V yellow-green. Those rail and diode drops are scenarios, not guaranteed limits.

TI specifies 70 uA typical **per amplifier**: both channels need 140 uA typical. The 125 uA/channel 25 C and 150 uA/channel full-temperature maxima give 250/300 uA package scenarios under the datasheet test conditions (5.5 V); these are not measured 3 V draws. Minimum supply is 2.5 V. [TI LMV358A datasheet](https://www.ti.com/lit/ds/symlink/lmv358a.pdf).

## Nominal analytical result

| Quantity | Calculated result |
| --- | ---: |
| Frequency | 1.0175 Hz |
| Red duty cycle | 29.03% |
| Red / green ON current | 251.1 / 208.5 uA |
| Mean / peak cell current | 371.3 / 405.4 uA |
| RMS cell current | 371.9 uA |
| Cell terminal power | 1.1139 mW |
| Both op amps, including output/reference losses | 427.78 uW |
| LED electrical power | 427.15 uW |
| R6 + R7 loss | 231.02 uW |
| Reference divider | 22.50 uW |
| Positive-feedback resistors | 3.63 uW |
| Timing resistor | 1.78 uW |

LED electrical power includes optical output and cannot all be labelled heat. Ideal capacitors dissipate no average steady-cycle power; leakage, dielectric loss, ESR, startup and switching-current bursts are omitted. The analytical energy balance closes within floating-point error. PCB copper loss is a separate small correction.

The supply-current budget includes capacitor charging and both source/sink directions of the buffered reference. Capacitor discharge is local stored energy and is not counted as fresh battery draw. The script uses exact exponential timing and RMS current integration. It asserts that component powers sum to terminal power.

At 3 V, changing only package quiescent current to 250/300 uA raises the mean draw to 481.3/531.3 uA. With typical quiescent current and the same output assumptions, the 2.5/2.7/3.2 V scenarios draw 263.1/306.4/414.5 uA. Assumed red Vf 1.6–2.0 V and green Vf 1.8–2.2 V give 328.7–413.8 uA at 3 V. These are scenario ranges, not toleranced vendor guarantees.

## Cell loss and useful life

Internal cell loss is R_internal times mean(I_cell squared), **not** R_internal times mean(I_cell) squared. The nominal coefficient is 0.13832 uW per ohm. Cell resistance, age, temperature and pulse sag are unknown; no fixed internal heat or discharge-curve prediction is claimed.

Panasonic lists a CR2032 at 3 V, 225 mAh and 0.2 mA standard continuous drain. That capacity does not establish capacity available above this circuit's **loaded 2.5 V** minimum. [Panasonic CR2032 datasheet](https://energy.panasonic.com/dam/master/pdf/en/datasheet/lithium/CR2032_Datasheet_EN.pdf).

If measured usable capacity above 2.5 V were 100/150/200 mAh, dividing by the nominal 0.3713 mA gives approximately 269/404/539 hours. Actual current changes during discharge, so these are planning examples, not promised runtime. Measure brightness, startup and current across battery voltage and temperature.

## Actual WayriCAD Quick PI 4.5.0 runs

Used saved native copper through the installed KiCad 10 Python and WayriCAD service.execute, with existing NumPy/SciPy/Gmsh. No packages were installed. This avoids the separate runtime-provisioning workflow.

Explicit study assumptions: 35 um top/bottom copper, 1.6 mm outer copper span, 25 um via plating, 20 C. The saved board has no filled zones. Copper conductivity is the solver's recorded material model. These are study assumptions, not a purchased fabricator stackup.

| State / saved net | Worst contact drop | Copper loss | Finest mesh |
| --- | ---: | ---: | ---: |
| High-output VBAT | 39.34 uV | 15.82 nW | 0.075 mm |
| Low-output VBAT | 30.93 uV | 10.94 nW | 0.075 mm |
| High-output GND return | 15.11 uV magnitude | 4.99 nW | 0.050 mm |

VBAT loads include the state-mean charging/reference currents and the correct LED branch. The GND calculation reverses all high-state current injections and uses a 3 V mathematical reference; only drop magnitudes and losses are interpreted. The physical ground is near 0 V. The low-state capacitor has a signed ground injection and was **not** silently converted into an all-positive sink; a complete low-state ground study remains unperformed. Other signal-net copper and device internals are outside Quick PI scope.

Drop and total loss change by less than 1% on each of the final two refinements for all three studies. Current balance errors are below 0.7 pA and energy relative errors below 1.2e-9. **Local peak current density does not converge at 1%**; sharp-corner/terminal peaks must not be used for local heating or ampacity signoff. No electrothermal, AC, EMI, battery electrochemical or transistor-level oscillator solve was run.

Complete finest fields/mesh/results are retained as gzip-compressed JSON; decompress to a separate JSON file for numerical inspection. [Summary](../evidence/analysis/wayricad-summary.json) includes actual requests, refinements, producer version, source hashes and warnings. Raw execution diagnostics include repeated wx image-handler warnings; solves completed.

## Reproduce

Run tools/analyze_power.py with KiCad 10 Python. Without options it regenerates the analytical budget. To include copper solves, pass --wayricad-source followed by the root of an existing WayriCAD 4.5 source tree. Scientific/native dependencies must already be available; the helper does not provision a runtime. All outputs belong to evidence/analysis. Rerun after any design change.
