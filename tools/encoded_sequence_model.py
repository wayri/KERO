"""Synthesize and verify an R/C-only, op-amp ring encoder for 'hello world'.
Exact piecewise-exponential event model, NOT a transistor-level simulation.
No installs, GUI, or modifications to native KiCad design files.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'encoded-model'
MESSAGE = 'hello world'
ALPHABET = {' ': 0, 'd': 1, 'e': 2, 'h': 3, 'l': 4, 'o': 5, 'r': 6, 'w': 7}
BASE = .05
RATIO = 1.3
GAP = .1
FRAME_GAP = 1.
C = 47e-9
RTH = 100e3
PIN_MAP = [dict(out=1, minus=2, plus=3), dict(out=7, minus=6, plus=5),
           dict(out=8, minus=9, plus=10), dict(out=14, minus=13, plus=12)]


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


# Vishay standard E192 table includes 920, not the formula-rounded 919.
E192 = tuple(920 if n == 185 else round(100 * 10**(n/192)) for n in range(192))
assert len(set(E192)) == 192 and E192[:4] == (100, 101, 102, 104)
assert E192[184:188] == (909, 920, 931, 942)

def nearest_e192(value):
    decade = math.floor(math.log10(value)) - 2
    candidates = [mantissa * 10**power for power in range(decade-1, decade+2) for mantissa in E192]
    return float(min(candidates, key=lambda candidate: abs(math.log(candidate/value))))


def synthesize():
    widths = [BASE * RATIO**ALPHABET[c] for c in MESSAGE]
    dwell = [value for i, width in enumerate(widths) for value in (width, FRAME_GAP if i == 10 else GAP)]
    event_times = [0.]
    for value in dwell[:-1]:
        event_times.append(event_times[-1] + value)
    period = sum(dwell)
    stages = []
    for i in range(11):
        j = (i - 1) % 11
        input_rise = j if j % 2 == 0 else j + 11
        input_fall = j + 11 if j % 2 == 0 else j
        output_rise = i if i % 2 == 0 else i + 11
        output_fall = i + 11 if i % 2 == 0 else i
        high_time = (event_times[input_fall] - event_times[input_rise]) % period
        fall_delay = (event_times[output_fall] - event_times[input_rise]) % period
        rise_delay = (event_times[output_rise] - event_times[input_fall]) % period
        # Select tau by maximizing the smallest normalized threshold/rail margin.
        # Each candidate uses exact periodic capacitor extrema, not settled rails.
        lower = min(fall_delay, rise_delay) / 30
        upper = max(fall_delay, rise_delay) * 5
        best = None
        for k in range(2001):
            tau = lower * (upper / lower)**(k / 2000)
            peak = -math.expm1(-high_time / tau) / -math.expm1(-period / tau)
            bottom = peak * math.exp(-(period - high_time) / tau)
            low = peak * math.exp(-rise_delay / tau)
            high = 1 - (1 - bottom) * math.exp(-fall_delay / tau)
            margin = min(low, 1-high, (high-low)/2)
            if best is None or margin > best[0]:
                best = margin, tau, low, high
        margin, tau, low, high = best
        if margin <= 0:
            raise ValueError('No positive-hysteresis solution')
        ideal = dict(R_timing_ohm=tau/C, R_vbat_ohm=RTH/low,
                     R_feedback_ohm=RTH/(high-low), R_gnd_ohm=RTH/(1-high))
        resistors = {key: nearest_e192(value) for key, value in ideal.items()}
        gv, gf, gg = [1/resistors[key] for key in ['R_vbat_ohm','R_feedback_ohm','R_gnd_ohm']]
        total = gv+gf+gg
        name = f'ST{i+1:02d}'
        stages.append(dict(index=i, id=name, amplifier=f'U{i//4+1}{"ABCD"[i%4]}',
            package=f'U{i//4+1}', unit=i%4+1, pins=PIN_MAP[i%4],
            previous_output=f'ST{j+1:02d}_OUT', output=name+'_OUT',
            timing_node=name+'_TIMING', threshold_node=name+'_TH',
            capacitor_F=C, capacitor_bottom='VBAT' if i%2==0 else 'GND',
            resistors=resistors, unrounded_resistors=ideal,
            input_high_duration_s=high_time, input_low_duration_s=period-high_time,
            requested_output_fall_delay_s=fall_delay, requested_output_rise_delay_s=rise_delay,
            ideal_tau_s=tau, quantized_tau_s=resistors['R_timing_ohm']*C,
            ideal_threshold_low_fraction=low, ideal_threshold_high_fraction=high,
            quantized_threshold_low_fraction=gv/total,
            quantized_threshold_high_fraction=(gv+gf)/total,
            ideal_minimum_threshold_margin_fraction=margin))
    return dict(schema='kero.rc-pwm-ring/v1', message=MESSAGE, alphabet=ALPHABET,
        pulse_width_s={char:BASE*RATIO**code for char,code in ALPHABET.items()},
        base_pulse_s=BASE, width_ratio=RATIO, intersymbol_gap_s=GAP, frame_gap_s=FRAME_GAP,
        frame_duration_s=period, payload_symbols=11, payload_code_bits=33,
        alphabet_scope='Custom fixed eight-symbol codebook; not ASCII, UART or universal text encoding.',
        intended_dwell_s=dwell, stages=stages,
        capacitor_specification='47 nF, C0G, 1%, intended 0805; exact MPN and procurement remain unverified.',
        resistor_specification='0.1%; nearest E192 standard nominal values; exact MPN, tolerance and package availability remain unverified.',
        majority=dict(amplifier='U3D', package='U3', unit=4, pins=PIN_MAP[3],
            sum_resistor_ohm=1e6, divider_top_ohm=100e3, divider_bottom_ohm=100e3,
            plus_node='MAJORITY_SUM', minus_node='MIDREF', output='ENCODED_OUT',
            inputs=[s['output'] for s in stages], positive_feedback=False),
        supply_pins={'VBAT':4,'GND':11}, ic='TLV9044IPWR',
        footprint='Package_SO:TSSOP-14_4.4x5mm_P0.65mm',
        source_urls=['https://www.ti.com/lit/ds/symlink/tlv9044.pdf',
                     'https://www.ti.com/lit/zip/SBOMB62', 'https://www.ti.com/lit/zip/SBOMB61',
                     'https://www.vishay.com/docs/50034/stohmval.pdf'])


def parameters(design, supply=3., rng=None, vary=False):
    def tolerance(nominal, amount):
        return nominal * (1 + (rng.uniform(-amount,amount) if vary else 0))
    parts=[]
    for stage in design['stages']:
        resistors={k:tolerance(v,.001) for k,v in stage['resistors'].items()}
        gv,gf,gg=[1/resistors[k] for k in ['R_vbat_ohm','R_feedback_ohm','R_gnd_ohm']]
        total=gv+gf+gg
        H=supply-(rng.uniform(0,.010) if vary else 0)
        L=rng.uniform(0,.010) if vary else 0
        offset=rng.uniform(-.00225,.00225) if vary else 0
        parts.append(dict(tau=resistors['R_timing_ohm']*tolerance(C,.01),H=H,L=L,
            low=(gv*supply+gf*L)/total+offset,
            high=(gv*supply+gf*H)/total+offset,
            resistors=resistors,offset_V=offset))
    decoder=dict(weights=[1/tolerance(1e6,.001) for _ in range(11)],
                 top=tolerance(100e3,.001),bottom=tolerance(100e3,.001),
                 offset=rng.uniform(-.00225,.00225) if vary else 0)
    return parts,decoder


def simulate(parts, decoder, supply, *, initial='preset', rng=None, events=550):
    if initial=='preset':
        # Fast power step from discharged caps: even bottom=VBAT, odd bottom=GND.
        x=[supply if i%2==0 else 0. for i in range(11)]
        q=[i%2 for i in range(11)]
    else:
        x=[rng.uniform(0,supply) for _ in range(11)]
        q=[rng.randrange(2) for _ in range(11)]
    initial_x=list(x);initial_q=list(q)
    t=0.;trace=[];minimum_decoder_margin=float('inf')
    for n in range(events):
        delays=[]
        targets=[]
        for i,p in enumerate(parts):
            j=(i-1)%11
            goal=parts[j]['H'] if q[j] else parts[j]['L']
            targets.append(goal)
            if q[i] and x[i]>=p['high']-1e-12:
                delay=0.
            elif not q[i] and x[i]<=p['low']+1e-12:
                delay=0.
            elif q[i] and goal>p['high']:
                delay=p['tau']*math.log((goal-x[i])/(goal-p['high']))
            elif not q[i] and goal<p['low']:
                delay=p['tau']*math.log((x[i]-goal)/(p['low']-goal))
            else:
                delay=float('inf')
            delays.append(delay)
        dt=min(delays)
        if not math.isfinite(dt) or dt < -1e-12:
            raise ValueError('No admissible next event')
        x=[target+(value-target)*math.exp(-dt/part['tau']) for value,target,part in zip(x,targets,parts)]
        stage=delays.index(dt)
        q[stage]=1-q[stage]
        t+=dt
        summed=sum(w*(p['H'] if state else p['L']) for w,p,state in zip(decoder['weights'],parts,q))/sum(decoder['weights'])
        threshold=supply*decoder['bottom']/(decoder['top']+decoder['bottom'])+decoder['offset']
        majority=int(summed>threshold)
        count=sum(q)
        margin=abs(summed-threshold)
        if n>=events-44:
            minimum_decoder_margin=min(minimum_decoder_margin,margin)
        trace.append(dict(time_s=t, preceding_dwell_s=dt, stage=stage,
                          count_high=count, decoded_output=majority,
                          state=''.join(map(str,q)), comparator_margin_V=margin))
    return dict(initial_capacitor_nodes_V=initial_x,initial_outputs=initial_q,
                first_events=trace[:44],last_events=trace[-44:],
                minimum_settled_decoder_margin_V=minimum_decoder_margin)


def check(design, simulation):
    sequence=simulation['last_events'][-22:]
    cells={}
    state_valid=all(r['count_high'] in (5,6) and r['decoded_output']==int(r['count_high']==6) for r in sequence)
    for row in sequence:
        i=row['stage']
        event=i+(11 if (row['count_high']==6)!=(i%2==0) else 0)
        preceding=(event-1)%22
        cells[preceding]=row['preceding_dwell_s']
    complete=len(cells)==22 and state_valid
    if not complete:
        return dict(pass_check=False,state_cycle_complete=False)
    inverse={code:char for char,code in ALPHABET.items()}
    widths=[cells[2*i] for i in range(11)]
    # Decode directly against the published codebook. No hidden per-unit calibration.
    codes=[round(math.log(width/BASE)/math.log(RATIO)) for width in widths]
    decoded=''.join(inverse.get(code,'?') for code in codes)
    expected=[ALPHABET[c] for c in MESSAGE]
    coordinate_errors=[abs(math.log(width/BASE)/math.log(RATIO)-code) for width,code in zip(widths,expected)]
    gap_errors=[abs(cells[2*i+1]/(FRAME_GAP if i==10 else GAP)-1) for i in range(11)]
    return dict(pass_check=decoded==MESSAGE, state_cycle_complete=True,decoded=decoded,
        measured_widths_s=widths, frame_duration_s=sum(cells.values()),
        maximum_symbol_coordinate_error=max(coordinate_errors),
        nearest_code_decision_boundary=0.5,
        maximum_gap_relative_error=max(gap_errors),
        minimum_decoder_margin_V=simulation['minimum_settled_decoder_margin_V'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials-per-voltage',type=int,default=250)
    args=parser.parse_args()
    if not 1<=args.trials_per_voltage<=2000:
        raise ValueError('Bound trials to 1..2000 per voltage')
    started=time.time()
    OUT.mkdir(exist_ok=True)
    before={drive:shutil.disk_usage(drive).free/2**30 for drive in ['C:/','D:/']}
    design=synthesize()
    write('design.json',design)
    nominal={}
    for supply in [2.5,3.,3.3]:
        parts,decoder=parameters(design,supply)
        sim=simulate(parts,decoder,supply)
        nominal[str(supply)]=dict(check=check(design,sim),simulation=sim,parameters=parts)
    write('nominal-event-model.json',nominal)
    rng=random.Random(9044112026)
    rows=[];worst=None
    for supply in [2.5,3.,3.3]:
        for trial in range(args.trials_per_voltage):
            parts,decoder=parameters(design,supply,rng,True)
            sim=simulate(parts,decoder,supply,initial='random',rng=rng)
            result=check(design,sim)
            row=dict(supply_V=supply,trial=trial,**result)
            rows.append(row)
            score=result.get('maximum_symbol_coordinate_error',float('inf'))
            if worst is None or score>worst['score']:
                worst=dict(score=score,trial=row,stage_parameters=parts,decoder_parameters=decoder,simulation=sim)
        selected=[r for r in rows if r['supply_V']==supply]
        print(supply,'V',sum(r['pass_check'] for r in selected),'/',len(selected),'frames decoded correctly',flush=True)
    summary=dict(schema='kero.rc-pwm-event-evidence/v1', evidence='Exact exponential event integration with ideal instantaneous saturated op amps; not SPICE/device/ramp/bench validation.',
        seed=9044112026,trials_per_voltage=args.trials_per_voltage,total_trials=len(rows),
        passed=sum(r['pass_check'] for r in rows),failed=sum(not r['pass_check'] for r in rows),
        uncertainties=dict(resistors_relative=.001,capacitors_relative=.01,input_offset_max_V=.00225,
            output_high_headroom_V=[0,.010],output_low_V=[0,.010],sample_distribution='Independent uniform per component and channel; random initial capacitor voltages and output states.'),
        maximum_symbol_coordinate_error=max(r.get('maximum_symbol_coordinate_error',1e99) for r in rows),
        nearest_code_decision_boundary=.5,
        minimum_settled_majority_margin_V=min(r.get('minimum_decoder_margin_V',0) for r in rows),
        limitations=['Sampling is not worst-case proof or population yield prediction.',
            'No finite slew, overload recovery, dynamic supply current, loading-dependent output rail or input capacitance model.',
            'No supply ramp or brownout integration; alternate capacitor bottom plates assume a fast initial power step from discharged capacitors.',
            'Input differential >2.5 V can increase input bias in TI specification; leakage needs explicit device and board evaluation.',
            'E192 nominal resistor values and 47nF 1% C0G capacitors require exact MPN/package/tolerance sourcing review.',
            'Static decoder margin is evaluated; simultaneous analog transitions and output glitches require device simulation.',
            'No complete cell-current budget or lifetime claim is established by this model.'])
    write('tolerance-summary.json',summary)
    write('tolerance-trials.json',rows)
    write('worst-sampled-case.json',worst)
    write('execution.json',dict(command=[sys.executable,*sys.argv],elapsed_s=time.time()-started,
        exit_code=0 if not summary['failed'] and all(v['check']['pass_check'] for v in nominal.values()) else 2,
        tool='Python exact-event analytical model',helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        capacity_before_GiB=before,capacity_after_GiB={drive:shutil.disk_usage(drive).free/2**30 for drive in ['C:/','D:/']}))
    print(json.dumps(summary,indent=2),flush=True)
    return 0 if not summary['failed'] and all(v['check']['pass_check'] for v in nominal.values()) else 2

if __name__=='__main__':
    raise SystemExit(main())
