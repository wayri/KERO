# R/C-programmed hello world encoder

This is a proposed analog transmitter made from 11 inverting Schmitt op-amp stages in a ring and one resistive-majority output op amp. Three TLV9044IPWR quad packages provide all 12 channels. No MCU, logic IC, transistor switch, or extra discrete diode is used. The majority function is implemented by resistors and an op amp; it is not a separate logic IC.

## Encoding

The exact lowercase payload is `hello world`. The custom eight-symbol codebook is space=0, d=1, e=2, h=3, l=4, o=5, r=6, w=7. Symbol high width is 50 ms times 1.3^code. Ordinary low gaps are 100 ms; the final low gap is 1000 ms. The nominal frame is 3.664141035 s.

| Symbol | Code | High width (ms) |
|---|---:|---:|
| space | 0 | 50.000000 |
| d | 1 | 65.000000 |
| e | 2 | 84.500000 |
| h | 3 | 109.850000 |
| l | 4 | 142.805000 |
| o | 5 | 185.646500 |
| r | 6 | 241.340450 |
| w | 7 | 313.742585 |

Decode using the nearest logarithmic code: round(log(width/50 ms)/log(1.3)). A symbol decision boundary lies half a code interval away, a multiplicative width ratio sqrt(1.3). The receiver must identify the long low gap and then decode eleven high widths. No MCU is needed in the transmitter; reading text still needs a human/tool/receiver that knows this codebook.

Eleven eight-choice symbols carry 33 bits of codebook-index payload instead of eleven 8-bit ASCII bytes. This excludes codebook/framing overhead and is not a universal text compressor or a serial ASCII waveform. Changing R/C values changes the emitted timing sequence; changing the alphabet requires the receiver codebook to change too.

## Exact periodic synthesis

For each stage, let tau=Rtim*C. Its preceding stage drives a normalized 0/1 square wave of high duration A and low duration B, with T=A+B. The periodic capacitor extrema are:

    xmax = (1-exp(-A/tau)) / (1-exp(-T/tau))
    xmin = xmax*exp(-B/tau)
    TH = 1-(1-xmin)*exp(-d_fall/tau)
    TL = xmax*exp(-d_rise/tau)

These use the actual periodic initial voltages. They do not assume the capacitor fully reaches a supply rail. The required delays d_fall and d_rise are the two dwell intervals preceding that stage flipping. The generator searches for a tau with positive hysteresis and useful rail margins.

For a three-resistor noninverting threshold node, define total conductance G and choose:

    Gvbat/G = TL
    Gfeedback/G = TH-TL
    Gground/G = 1-TH

The chosen equivalent resistance 1/G is 100 kohm. Thus Rvbat=100k/TL, Rfeedback=100k/(TH-TL), Rground=100k/(1-TH). The actual stored values are quantized to nearest E192 standard nominal values; the event model tests those quantized values, not the unrounded mathematical design. The E192 mantissas follow the [Vishay preferred-value table](https://www.vishay.com/docs/50034/stohmval.pdf), including the 920 exception to direct logarithmic rounding. An E192 value still does not establish an available 0.1% part in the intended package; exact sourcing remains a gate.

Each timing capacitor is specified as 47 nF C0G, 1%, intended 0805. An exact orderable MPN satisfying that combination has not been verified. The largest timing resistor is 6.98 Mohm, so PCB leakage and contamination require assessment even though op-amp bias current is small.

## Wiring and values

For every stage STnn: previous stage OUT connects through Rtim to TIMING and the inverting input. C connects TIMING to the declared bottom rail. The noninverting input connects to TH; Rvbat connects TH to VBAT, Rground connects TH to GND, and Rfeedback connects TH to that same stage OUT. Stage ST01 receives ST11_OUT, closing the ring. All units use VBAT/GND supply pins.

| Stage | Unit | Rtim (ohm) | Rvbat (ohm) | Rfeedback (ohm) | Rground (ohm) | C bottom |
|---|---|---:|---:|---:|---:|---|
| ST01 | U1A | 6980000 | 2130000 | 1050000 | 117000 | VBAT |
| ST02 | U1B | 1650000 | 365000 | 208000 | 412000 | GND |
| ST03 | U1C | 3520000 | 182000 | 332000 | 665000 | VBAT |
| ST04 | U1D | 1470000 | 427000 | 213000 | 340000 | GND |
| ST05 | U2A | 2430000 | 240000 | 258000 | 511000 | VBAT |
| ST06 | U2B | 2000000 | 291000 | 229000 | 459000 | GND |
| ST07 | U2C | 2910000 | 208000 | 291000 | 583000 | VBAT |
| ST08 | U2D | 2000000 | 291000 | 229000 | 459000 | GND |
| ST09 | U3A | 2000000 | 291000 | 229000 | 459000 | VBAT |
| ST10 | U3B | 2430000 | 240000 | 258000 | 511000 | GND |
| ST11 | U3C | 1370000 | 470000 | 237000 | 274000 | VBAT |

U3D noninverting input receives the resistive average of all eleven ring outputs through eleven equal 1 Mohm resistors. Its inverting input receives VBAT/2 from two 100 kohm resistors. Five high ring outputs give below-half-rail average; six give above-half-rail average. The emitted sequence alternates between five-high and six-high states, with one stage transition per edge. Majority-stage feedback is absent in this candidate; finite-slew switching and glitch behavior need device-model validation.

Verified TI 14-pin quad mapping: A OUT=1, IN-=2, IN+=3; B OUT=7, IN-=6, IN+=5; C OUT=8, IN-=9, IN+=10; D OUT=14, IN-=13, IN+=12; V+=4 and V-=11. These are the TLV9044 non-shutdown PW/TSSOP pins, not the TLV9044S shutdown variant.

## Startup and model boundaries

Timing capacitors on zero-based even stages connect to VBAT, odd stages to GND. A fast power step from fully discharged capacitors presets their input nodes to [VBAT,0,VBAT,0,...,VBAT], and output states to [0,1,0,1,...,0]. This is one alternating state with one unsatisfied ring connection. The majority output starts low and the first stage times the initial long gap. This passive preset uses capacitor reference choice, not invented initial conditions in a claim of hardware validation.

A slow supply ramp, residual charge, short power interruption, or brownout does not necessarily reproduce that preset. The exact-event model assumes an already established constant supply and instantaneous rail decisions. It tests arbitrary initial states at that fixed supply, but this is not a slow-ramp or power-cycle guarantee. Ignore incomplete startup frames until a complete long-gap-delimited frame is observed.

## Executed verification

Run the authoritative model with:

    <Python> -B tools/encoded_sequence_model.py --trials-per-voltage 250

Nominal quantized-R models at 2.5, 3.0 and 3.3 V decode the intended text. There are 750 reproducible sampled trials, 250 per voltage, using seed 9044112026, random initial capacitor voltages/output states, independent +/-0.1% resistor errors, +/-1% capacitor errors, +/-2.25 mV input offsets, and independent output headroom between 0 and 10 mV. Decoder resistor errors and offset are included. Every sampled settled frame decoded correctly. The largest logarithmic code error was 0.140520 versus a 0.5 decision boundary; minimum static majority-input margin was 107.519 mV.

Sampling does not prove every combination, establish a yield figure, or validate the analog device. Full sample results, worst sampled parameters, first/last events, source helper checksum and command receipt are retained in this directory. No circuit simulation or bench measurement is claimed by these files.

## Device and next validation gate

TI TLV9044 Rev H specifies RRIO operation from 1.2 to 5.5 V and typical supply current 10 uA/channel. Twelve channels therefore budget 120 uA typical before resistor, LED and output-current loading; tabulated 13/13.5 uA channel maxima imply 156/162 uA under their stated 5.5 V test conditions. Overload recovery is 13 us typical, not a maximum comparator delay. Offset is up to +/-2.25 mV at 25 C and +/-2.5 mV over temperature. Differential input greater than 2.5 V can increase input bias. These conditions must remain visible in the supply-current and timing assessment.

Primary references: [TI TLV9044 datasheet](https://www.ti.com/lit/ds/symlink/tlv9044.pdf), [TI PSpice model](https://www.ti.com/lit/zip/SBOMB62), [TI TINA Spice model](https://www.ti.com/lit/zip/SBOMB61). The model links are manufacturer downloads; they were located but not downloaded or executed by this task. The integrating task found SBOMB62 Rev B declares a TLV9042 family-channel model; reusing that amplifier macro twelve times for TLV9044 channels is an explicit family-model applicability assumption, not an exact quad-package or startup-power model. Do not redistribute a downloaded model without reviewing its license.

Existing Xyce executable D:/xyce/Xyce_7.8/bin/Xyce.exe returned XyceNF Release 7.8.0. The next gate is an actual transient using the declared R/C connectivity, first with an explicitly labelled behavioral op-amp and then a compatible reviewed TI model: verify finite gain/slew/recovery, loaded rail swing, parasitic input capacitance, LED loading, exact pulse counts and decoded frames, and cell-current accounting. Sweep 2.5/3.0/3.3 V, representative fast/slow ramps, residual capacitor states and short/long power interruptions. Include +/-2.5 mV offsets for a full-temperature claim, plus capacitor temperature/drift/leakage and actual resistor network choices. A passing behavioral simulation alone cannot establish comparator behavior of the selected op amp.

Native schematic hierarchy and PCB editing are separate integration work. Suggested sheet boundaries are Power, repeated RC Stage, and Majority / LED Output; global variables describe the supply, C value, base width, width ratio and gaps, while each stage instance retains explicit resistor parameters from design.json.
