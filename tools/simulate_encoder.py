"""Run the reviewed TI-family model for KERO using installed Xyce; no provisioning.
The TI library remains external. Exact full sampled waveforms are retained as gzip CSV.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import gzip
import hashlib
import html
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SOURCE=ROOT/'encoded-model'/'design.json'
CASES=[('v2p5-ramp1ms',2.5,.001,.0005),('v3-ramp1ms',3.,.001,.0005),
       ('v3p3-ramp1ms',3.3,.001,.0005),('v3-ramp100ms',3.,.1,.0005),
       ('v3-ramp1s',3.,1.,.0005),('v3-ramp1ms-refined',3.,.001,.00025)]
LIMITS=[
 'TI TLV9042 Rev B family channel macro instantiated twelve times for TLV9044; not a package-specific quad or battery model.',
 'The library includes a 10 uA/channel quiescent source and output-current supply accounting; model validity is not bench correlation.',
 'Generic LED diode models and 15 kohm series resistors are illustrative, not selected LED part models.',
 'Battery is an ideal ramped voltage source: no ESR, electrochemistry, capacity or lifetime prediction.',
 'Crossings and integrals use sampled simulated waveforms; startup peak is the largest sampled current.',
 'Xyce may ignore R_NOISELESS/T_ABS noise-temperature parameters. No noise analysis is claimed.',
 'Recovered nonlinear time-step failures are retained in the log and do not alone invalidate a successful completed transient.',
 'Incomplete startup frames are excluded by explicit frame boundaries; every complete frame after the supply ramp is checked.',
 'These supply/ramp cases are not component tolerance, full-temperature, partial-discharge or brownout qualification.'
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,data,compact=False):
    path.write_text(json.dumps(data,indent=None if compact else 2,separators=(',',':') if compact else None,allow_nan=False)+'\n',encoding='utf-8')


def circuit(design,voltage,ramp,step,include):
    lines=['KERO E192 RC-coded hello world - TI family macro transient',f'.include "{include}"',
           f'Vbat VBAT 0 PWL(0 0 {ramp:.12g} {voltage:.12g})','Cdec VBAT 0 300n']
    for stage in design['stages']:
        name=stage['id'];r=stage['resistors'];bottom='VBAT' if stage['capacitor_bottom']=='VBAT' else '0'
        lines += [f'R{name}T {stage["previous_output"]} {stage["timing_node"]} {r["R_timing_ohm"]:.12g}',
            f'C{name} {stage["timing_node"]} {bottom} {stage["capacitor_F"]:.12g} IC=0',
            f'R{name}V VBAT {stage["threshold_node"]} {r["R_vbat_ohm"]:.12g}',
            f'R{name}G {stage["threshold_node"]} 0 {r["R_gnd_ohm"]:.12g}',
            f'R{name}F {stage["output"]} {stage["threshold_node"]} {r["R_feedback_ohm"]:.12g}',
            f'X{name} {stage["threshold_node"]} {stage["timing_node"]} VBAT 0 {stage["output"]} TLV9042',
            f'RSUM{name} {stage["output"]} SUM {design["majority"]["sum_resistor_ohm"]:.12g}']
    majority=design['majority']
    lines += [f'RmidV VBAT MID {majority["divider_top_ohm"]:.12g}',f'RmidG MID 0 {majority["divider_bottom_ohm"]:.12g}',
        'XDEC SUM MID VBAT 0 OUT TLV9042','RledR OUT RED_A 15k','Dred RED_A 0 LEDRMOD',
        'RledG VBAT GREEN_A 15k','Dgreen GREEN_A OUT LEDGMOD',
        '.model LEDRMOD D(IS=7.6e-20 N=2 RS=10)','.model LEDGMOD D(IS=1.58e-21 N=2 RS=10)',
        '.options TIMEINT METHOD=GEAR RELTOL=1e-4 ABSTOL=1e-10',
        f'.TRAN {step:.12g} 12 0 {step:.12g} UIC',
        '.PRINT TRAN FORMAT=CSV V(VBAT) V(OUT) V(SUM) V(MID) I(Vbat) '+' '.join(f'V({s["output"]})' for s in design['stages']),'.END']
    return '\n'.join(lines)+'\n'


def edges_and_frames(data,design,ramp):
    edges=[]
    for i in range(1,len(data)):
        a,b=data[i-1],data[i]
        ga=a[2]-.5*a[1];gb=b[2]-.5*b[1]
        if b[0]<=ramp or b[0]<=a[0]:
            continue
        direction='rise' if ga<=0<gb else 'fall' if ga>=0>gb else None
        if direction:
            fraction=-ga/(gb-ga)
            crossing=a[0]+fraction*(b[0]-a[0])
            if crossing>=ramp:
                edges.append(dict(time_s=crossing,direction=direction,sample_index=i))
    pulses=[]
    for edge in edges:
        if edge['direction']=='rise':
            pulses.append(dict(start_s=edge['time_s'],end_s=None))
        elif pulses and pulses[-1]['end_s'] is None:
            pulses[-1]['end_s']=edge['time_s']
    boundaries=[]
    for i in range(1,len(pulses)):
        previous=pulses[i-1]
        if previous['end_s'] is not None and pulses[i]['start_s']-previous['end_s']>.5:
            boundaries.append(i)
    inverse={code:character for character,code in design['alphabet'].items()}
    frames=[]
    for left,right in zip(boundaries,boundaries[1:]):
        selected=pulses[left:right]
        if not selected or any(p['end_s'] is None for p in selected):
            continue
        widths=[p['end_s']-p['start_s'] for p in selected]
        codes=[round(math.log(width/design['base_pulse_s'])/math.log(design['width_ratio'])) for width in widths]
        decoded=''.join(inverse.get(code,'?') for code in codes)
        frames.append(dict(start_s=selected[0]['start_s'],end_s=pulses[right]['start_s'],
            pulse_count=len(selected),widths_s=widths,codes=codes,decoded=decoded,
            pass_check=len(selected)==11 and decoded==design['message']))
    return edges,pulses,frames


def integrate_current(data,start,end):
    total=0.;square=0.;duration=end-start
    maximum=-float('inf');minimum=float('inf')
    for a,b in zip(data,data[1:]):
        left=max(start,a[0]);right=min(end,b[0])
        if right<=left or b[0]<=a[0]:
            continue
        ia=-a[5];ib=-b[5]
        x=ia+(ib-ia)*(left-a[0])/(b[0]-a[0]);y=ia+(ib-ia)*(right-a[0])/(b[0]-a[0])
        dt=right-left
        total += dt*(x+y)/2
        square += dt*(x*x+x*y+y*y)/3
        maximum=max(maximum,x,y);minimum=min(minimum,x,y)
    return dict(window_start_s=start,window_end_s=end,duration_s=duration,
                mean_A=total/duration,rms_A=math.sqrt(square/duration),
                maximum_sampled_A=maximum,minimum_sampled_A=minimum,charge_C=total)


def run_case(case,design,source,source_sha,model,model_sha,xyce,out):
    label,voltage,ramp,step=case
    folder=out/label
    folder.mkdir()
    scratch=folder/'.scratch'
    scratch.mkdir()
    portable=circuit(design,voltage,ramp,step,'tlv9042.lib')
    (folder/'circuit.cir').write_text(portable,encoding='utf-8')
    actual=circuit(design,voltage,ramp,step,model.as_posix())
    deck=scratch/'run.cir';deck.write_text(actual,encoding='utf-8')
    raw_log=scratch/'xyce.log'
    environment=os.environ.copy()
    environment['TEMP']=environment['TMP']=str(scratch)
    environment['OMP_NUM_THREADS']='1'
    started=time.time()
    command=[str(xyce),str(deck)]
    timed_out=False;log_limit=False
    with raw_log.open('wb') as stream:
        process=subprocess.Popen(command,cwd=scratch,env=environment,stdin=subprocess.DEVNULL,
            stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        while process.poll() is None:
            if time.time()-started>180 or raw_log.stat().st_size>8*1024*1024:
                timed_out=time.time()-started>180;log_limit=not timed_out
                process.terminate()
                process.wait(timeout=10)
                break
            time.sleep(.2)
    log=raw_log.read_text(encoding='utf-8',errors='replace')
    # Only normalize the supplied external model path; preserve numerical messages.
    normalized=log.replace(str(model),'[external TI model]').replace(model.as_posix(),'[external TI model]')
    (folder/'xyce.log').write_text(normalized,encoding='utf-8')
    report=dict(name=label,supply_V=voltage,ramp_s=ramp,maximum_timestep_s=step,requested_stop_s=12.,
        elapsed_s=time.time()-started,exit_code=process.returncode,timed_out=timed_out,log_limit_reached=log_limit,
        simulator_command=[xyce.name,'runtime deck with externally supplied model path'],
        source_spec_sha256=source_sha,model_sha256=model_sha,
        portable_netlist_sha256=sha(folder/'circuit.cir'),actual_run_deck_sha256=sha(deck),
        family_model_applicability='TLV9042 Rev B macro per channel for TLV9044; not a quad-package-specific model.',
        warning_lines=[line for line in normalized.splitlines() if any(word in line.lower() for word in ['warning','failure','failed','ignored','r_noiseless','t_abs'])],
        limitations=LIMITS)
    csvpath=scratch/'run.cir.csv'
    if process.returncode==0 and csvpath.exists():
        with csvpath.open(newline='',encoding='utf-8') as stream:
            reader=csv.reader(stream);columns=next(reader)
            data=[]
            for row in reader:
                if not row or not row[0].strip():continue
                try:values=list(map(float,row))
                except ValueError:continue
                if len(values)!=len(columns) or not all(math.isfinite(v) for v in values):
                    raise ValueError('Nonfinite or malformed Xyce sample')
                data.append(values)
        if len(data)<2 or data[-1][0]<11.999:
            raise ValueError('Transient did not reach requested stop time')
        if columns[:6]!=['TIME','V(VBAT)','V(OUT)','V(SUM)','V(MID)','I(VBAT)']:
            raise ValueError('Unexpected Xyce columns')
        edges,pulses,frames=edges_and_frames(data,design,ramp)
        for frame in frames:
            frame['cell_current']=integrate_current(data,frame['start_s'],frame['end_s'])
        report.update(completed_stop_s=data[-1][0],sample_count=len(data),
            full_waveform_csv_sha256=sha(csvpath),full_waveform_csv_bytes=csvpath.stat().st_size,
            edges=edges,frames=frames,complete_frame_count=len(frames),
            pass_check=bool(frames) and all(f['pass_check'] for f in frames),
            maximum_sampled_startup_current_A=max(-row[5] for row in data),
            current_sign='Positive cell draw = -I(Vbat).',
            frame_policy='Use all complete intervals between low gaps >0.5 s after the supply ramp. Incomplete startup/end fragments are excluded.',
            integration_method='Piecewise-linear sampled current: trapezoid for charge; exact quadratic integral of the linear interpolant for I squared.')
        with csvpath.open('rb') as src,gzip.open(folder/'waveform.csv.gz','wb',compresslevel=6) as dest:
            shutil.copyfileobj(src,dest)
        # Plotting trace only: preserve edge brackets and peak plus <=4096 base samples.
        stride=max(1,math.ceil(len(data)/4096))
        indices=set(range(0,len(data),stride));indices.add(len(data)-1)
        indices.add(max(range(len(data)),key=lambda i:-data[i][5]))
        for edge in edges:
            indices.add(edge['sample_index']);indices.add(edge['sample_index']-1)
        chosen=[data[i] for i in sorted(indices)]
        signals={columns[i]:[row[i] for row in chosen] for i in range(1,len(columns))}
        signals['CELL_CURRENT_A']=[-row[5] for row in chosen]
        trace=dict(schema='kero.xyce-transient/v1',producer='Xyce 7.8.0',
            source_spec_sha256=source_sha,model_sha256=model_sha,name=label,
            time_s=[row[0] for row in chosen],signals=signals,
            units={'time_s':'s','V(*)':'V','I(VBAT)':'A','CELL_CURRENT_A':'A'},
            plotting_downsample_only=True,full_samples_file='waveform.csv.gz',
            full_sample_count=len(data),plot_sample_count=len(chosen),
            note='Generic scalar time traces; no WayriCAD saved-board result or extension rendering certification is claimed.')
        save(folder/'trace.json',trace,compact=True)
    else:
        report['pass_check']=False
    if sha(source)!=source_sha or sha(model)!=model_sha:
        raise ValueError('Source or external model changed during simulation')
    save(folder/'result.json',report)
    # Exact owned-file cleanup only; keep unknown outputs for inspection.
    removed=[]
    for target in [deck,raw_log,csvpath]:
        if target.is_file() and target.resolve().parent==scratch.resolve():
            removed.append(dict(name=target.name,bytes=target.stat().st_size))
            target.unlink()
    if not any(scratch.iterdir()):scratch.rmdir()
    report['removed_owned_runtime_files']=removed
    save(folder/'result.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,type=Path)
    parser.add_argument('--xyce',required=True,type=Path)
    parser.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--output',type=Path,default=ROOT/'encoded-model'/'spice')
    args=parser.parse_args()
    model=args.model.resolve();xyce=args.xyce.resolve();source=args.source.resolve();out=args.output.resolve()
    if not model.is_file() or not xyce.is_file():raise ValueError('Existing model and Xyce executable are required')
    if '.subckt TLV9042 ' not in model.read_text(encoding='utf-8',errors='replace'):
        raise ValueError('Expected reviewed TLV9042-family subcircuit')
    design=json.loads(source.read_text(encoding='utf-8'))
    out.mkdir(parents=True,exist_ok=True)
    if any((out/case[0]).exists() for case in CASES):raise FileExistsError('Preserve existing case outputs before rerunning')
    capacity_before={drive:shutil.disk_usage(drive).free/2**30 for drive in ['C:/','D:/']}
    if shutil.disk_usage(out).free < 100*2**30+200*2**20:
        raise RuntimeError('Output drive cannot retain the 100 GiB reserve plus a 200 MiB run allowance')
    version=subprocess.run([str(xyce),'-v'],capture_output=True,text=True,check=True,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout.strip()
    source_sha=sha(source);model_sha=sha(model);started=time.time()
    reports=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(run_case,case,design,source,source_sha,model,model_sha,xyce,out):case for case in CASES}
        for future in as_completed(futures):
            result=future.result();reports.append(result)
            print(result['name'],'exit',result['exit_code'],'frames',result.get('complete_frame_count',0),'PASS',result['pass_check'],flush=True)
    reports.sort(key=lambda r:next(i for i,c in enumerate(CASES) if c[0]==r['name']))
    base=next(r for r in reports if r['name']=='v3-ramp1ms')
    fine=next(r for r in reports if r['name']=='v3-ramp1ms-refined')
    refinement=dict(baseline_step_s=.0005,refined_step_s=.00025,
        both_decode=base['pass_check'] and fine['pass_check'])
    if base.get('frames') and fine.get('frames'):
        a=base['frames'][-1];b=fine['frames'][-1]
        if len(a['widths_s'])==len(b['widths_s']):
            refinement['maximum_last_complete_frame_pulse_width_delta_s']=max(abs(x-y) for x,y in zip(a['widths_s'],b['widths_s']))
            refinement['last_complete_frame_period_delta_s']=abs((a['end_s']-a['start_s'])-(b['end_s']-b['start_s']))
            refinement['last_complete_frame_mean_current_delta_A']=abs(a['cell_current']['mean_A']-b['cell_current']['mean_A'])
    summary=dict(schema='kero.xyce-encoder-suite/v1',simulator_version=version,model_file_name=model.name,
        model_sha256=model_sha,source_spec_file='encoded-model/design.json',source_spec_sha256=source_sha,
        helper_sha256=sha(Path(__file__)),command=[str(xyce),'[case circuit generated by tools/simulate_encoder.py]'],
        maximum_concurrent_processes=2,elapsed_s=time.time()-started,
        passed=sum(r['pass_check'] for r in reports),total=len(reports),refinement=refinement,
        cases=[{key:value for key,value in r.items() if key not in ['edges','limitations','warning_lines','removed_owned_runtime_files']} for r in reports],
        capacity_before_GiB=capacity_before,capacity_after_GiB={drive:shutil.disk_usage(drive).free/2**30 for drive in ['C:/','D:/']},
        limitations=LIMITS)
    save(out/'summary.json',summary)
    rows=[]
    for result in reports:
        frame=result.get('frames',[])
        last=frame[-1]['cell_current'] if frame else {}
        rows.append('<tr>'+''.join('<td>'+html.escape(str(value))+'</td>' for value in [result['name'],result['pass_check'],len(frame),last.get('mean_A'),last.get('rms_A'),result.get('maximum_sampled_startup_current_A')])+'</tr>')
    document='<!doctype html><meta charset="utf-8"><title>KERO Xyce encoder evidence</title><style>body{font:16px system-ui;max-width:1200px;margin:40px auto}td,th{padding:8px;border:1px solid #ccc}table{border-collapse:collapse}</style><h1>KERO manufacturer-family model transient</h1><p>Measured simulated source draw is positive -I(Vbat). Current units are amperes. This is model-based evidence, not a battery-life claim.</p><table><tr><th>Case</th><th>Decode pass</th><th>Complete frames</th><th>Last-frame mean A</th><th>Last-frame RMS A</th><th>Maximum sampled startup A</th></tr>'+''.join(rows)+'</table><p><a href="summary.json">Complete suite summary</a></p><ul>'+''.join('<li>'+html.escape(item)+'</li>' for item in LIMITS)+'</ul>'
    (out/'report.html').write_text(document,encoding='utf-8')
    return 0 if all(r['pass_check'] for r in reports) else 2

if __name__=='__main__':
    raise SystemExit(main())
