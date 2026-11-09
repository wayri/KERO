"""Revision-bound instrumented Xyce encoder power accounting; no provisioning."""
import argparse, csv, gzip, hashlib, json, math, os, re, shutil, subprocess, sys, time
from types import SimpleNamespace
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from simulate_encoder import edges_and_frames

ROOT=Path(__file__).resolve().parents[1]
BOARD_SHA='08437dcfd8f304786d4f3444a26bd56c443661ea22bd25d69c3900906c6ef109'
CHANNELS=[('A','3','2','1'),('B','5','6','7'),('C','10','9','8'),('D','12','13','14')]
LIMITS=[
 'Actual Xyce transient using twelve external TI TLV9042 Rev B channel models as a family approximation for three TLV9044 packages; no package-specific or bench validation.',
 'Ideal 3 V source, 1 ms linear ramp, zero initial capacitor voltage, no battery electrochemistry, ESR feedback, trace resistance, capacitor ESR/leakage, optical model or lifetime calculation.',
 'LED electrical absorption is assigned 100% to board heat conservatively; generic red/green diode models are not exact selected part models.',
 'Opamp heat is mean net electrical absorption across all five measured channel terminals; internal macro stored-energy change over a settled frame is treated as negligible, supported by adjacent-frame comparison.',
 'Ideal capacitor heat is zero, while terminal power and endpoint stored-energy change are separately accounted; real dielectric/ESR losses remain unknown.',
 'Terminal-current PI loads are derived from an equipotential schematic. A rail-only DC PI solve is a separate spatial screen, not a coupled nonlinear circuit solve.',
 'Per-pad positive-peak envelopes are noncoincident conservative loads and must not be described as a simultaneous physical operating state.',
 'Startup sampled peak applies to the specified source ramp and ideal initial state only; sampled maxima are not guaranteed continuous-time or hardware bounds.',
 'Existing six-case evidence remains circuit-applicable only after native connectivity/value and source-spec identity checks; it is not re-run here.',
 'Printed Xyce I(D1)/I(D2) differs transiently from the associated unique series-resistor terminal current. LED terminal current is reconstructed from R58/R59 by KCL; the measured printed-current discrepancy is retained. No unverified explanation of the reporting discrepancy is assumed.',
 'The TI macro also connects internal elements to SPICE global 0. Physical GND pad currents include the inferred missing global-0 return, calculated per channel by KCL and assigned to that package GND pin. This reconstructed closure is algebraic, not an independent physical validation; the raw measured VEE-only KCL failure is retained.',
 'Xyce ignores the macro R_NOISELESS T_ABS noise parameter and reports single-terminal internal node warnings and recovered timestep failures; logs are retained.'
]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def json_scalar(x):
    if isinstance(x,np.generic):return x.item()
    raise TypeError('Unsupported JSON evidence type: '+type(x).__name__)
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False,default=json_scalar)+'\n',encoding='utf-8')
def value(s):
    m=re.fullmatch(r'([0-9.]+)([Mkunp]?)',s)
    if not m:raise ValueError('Unsupported passive value '+s)
    return float(m[1])*{'':1,'M':1e6,'k':1e3,'u':1e-6,'n':1e-9,'p':1e-12}[m[2]]
def node(s):return '0' if s=='GND' else s

def validate_native(intent,netlist):
    root=ET.parse(netlist).getroot();pins={}
    for net in root.findall('./nets/net'):
        for p in net.findall('node'):pins[(p.attrib['ref'],p.attrib['pin'])]=net.attrib['name']
    expected={(p['ref'],pin):net for p in intent['parts'] for pin,net in p['pins'].items()}
    assert pins==expected,'Native netlist pin/net mismatch'
    actual={c.attrib['ref']:c.findtext('value') for c in root.findall('./components/comp')}
    assert actual=={p['ref']:p['value'] for p in intent['parts']},'Native values mismatch'
    return dict(parts=len(actual),terminals=len(pins),pin_net_and_value_equivalence=True)

def make_deck(intent,include):
    lines=['KERO corrected native encoder instrumented power accounting',f'.include "{include}"','Vbat VBAT 0 PWL(0 0 .001 3)']
    signals=['V(VBAT)','V(ENCODED_OUT)','V(MAJORITY_SUM)','V(MIDREF)','I(Vbat)']
    nets=sorted({n for p in intent['parts'] for n in p['logical_pins'].values()}-{'GND','VBAT','ENCODED_OUT','MAJORITY_SUM','MIDREF'})
    signals += [f'V({n})' for n in nets]
    for p in intent['parts']:
        ref=p['ref'];pins=p['logical_pins']
        if ref.startswith(('R','C')):
            suffix=' IC=0' if ref.startswith('C') else ''
            lines.append(f'{ref} {node(pins["1"])} {node(pins["2"])} {value(p["value"]):.12g}{suffix}')
            if ref.startswith('C'):signals.append(f'I({ref})')
        elif ref.startswith('D'):
            lines.append(f'{ref} {node(pins["2"])} {node(pins["1"])} '+('REDMODEL' if ref=='D1' else 'GREENMODEL'))
            signals.append(f'I({ref})')
        elif ref.startswith('U'):
            for unit,plus,minus,output in CHANNELS:
                channel=ref+unit;internal=[]
                for tag,pin in [('P',plus),('M',minus),('V','4'),('G','11'),('O',output)]:
                    endpoint=channel+'_'+tag
                    sensor='VS_'+endpoint
                    lines.append(f'{sensor} {node(pins[pin])} {endpoint} 0')
                    signals.append(f'I({sensor})');internal.append(endpoint)
                lines.append('X'+channel+' '+' '.join(internal)+' TLV9042')
        elif ref!='BT1':raise ValueError('Unknown component '+ref)
    lines += ['.model REDMODEL D(IS=7.6e-20 N=2 RS=10)', '.model GREENMODEL D(IS=1.58e-21 N=2 RS=10)',
        '.options TIMEINT METHOD=GEAR RELTOL=1e-4 ABSTOL=1e-10', '.TRAN .0005 12 0 .0005 UIC',
        '.PRINT TRAN FORMAT=CSV '+' '.join(signals),'.END']
    return '\n'.join(lines)+'\n'

def mean_product(a,b,t):
    return float(np.sum(np.diff(t)*(2*a[:-1]*b[:-1]+a[:-1]*b[1:]+a[1:]*b[:-1]+2*a[1:]*b[1:])/6)/(t[-1]-t[0]))
def mean(a,t):return float(np.sum(np.diff(t)*(a[:-1]+a[1:])/2)/(t[-1]-t[0]))
def clip(data,start,end):
    ts=data[:,0];inside=data[(ts>start)&(ts<end)]
    def sample(at):return np.array([np.interp(at,ts,data[:,j]) for j in range(data.shape[1])])
    return np.vstack([sample(start),inside,sample(end)])
def read_csv(path):
    with (gzip.open(path,'rt',newline='',encoding='utf-8') if str(path).endswith('.gz') else path.open(newline='',encoding='utf-8')) as f:
        reader=csv.reader(f);header=next(reader)
        def values():
            for row in reader:
                if not row:continue
                try:float(row[0])
                except ValueError:continue
                if len(row)!=len(header):raise ValueError('Malformed CSV row')
                for cell in row:yield float(cell)
        array=np.fromiter(values(),dtype=float).reshape(-1,len(header))
    assert np.isfinite(array).all() and np.all(np.diff(array[:,0])>=0),'Invalid transient samples'
    assert array[-1,0]>=12,'Incomplete simulation'
    return header,array

def calculate(data,header,intent,start,end):
    d=clip(data,start,end);t=d[:,0];col={h.upper():d[:,i] for i,h in enumerate(header)};zero=np.zeros(len(t))
    def v(n):return zero if n=='GND' else col['V('+n.upper()+')']
    def current(name):return col['I('+name.upper()+')']
    pin_current={};raw_ground={};heat={};details={};cap_energy=0.;cap_terminal=0.;amp_input=0.
    parts_by_ref={p['ref']:p for p in intent['parts']}
    for p in intent['parts']:
        ref=p['ref'];pins=p['logical_pins']
        if ref.startswith('R'):
            resistance=value(p['value']);dv=v(pins['1'])-v(pins['2']);i=dv/resistance
            heat[ref]=mean_product(dv,dv,t)/resistance
            pin_current[(ref,'1')]=i;pin_current[(ref,'2')]=-i
            details[ref]=dict(kind='resistor',heat_W=heat[ref],resistance_ohm=resistance)
        elif ref.startswith('C'):
            c=value(p['value']);dv=v(pins['1'])-v(pins['2']);i=current(ref)
            heat[ref]=0.;delta=.5*c*float(dv[-1]**2-dv[0]**2);power=mean_product(dv,i,t)
            cap_energy+=delta;cap_terminal+=power
            pin_current[(ref,'1')]=i;pin_current[(ref,'2')]=-i
            details[ref]=dict(kind='ideal_capacitor',heat_W=0.,actual_loss_unknown=True,stored_energy_change_J=delta,mean_terminal_power_W=power,stored_charge_change_C=float(c*(dv[-1]-dv[0])),integrated_terminal_charge_C=mean(i,t)*(end-start))
        elif ref.startswith('D'):
            reported=current(ref);series=parts_by_ref['R58' if ref=='D1' else 'R59'];sp=series['logical_pins']
            i=(v(sp['1'])-v(sp['2']))/value(series['value']);dv=v(pins['2'])-v(pins['1']);power=mean_product(dv,i,t)
            heat[ref]=power;pin_current[(ref,'2')]=i;pin_current[(ref,'1')]=-i
            details[ref]=dict(kind='generic_LED',heat_W=power,electrical_absorption_W=power,heat_fraction_assumption=1.,current_basis='unique series resistor terminal current by KCL',
                reported_diode_current_minus_series_mean_A=mean(reported-i,t),reported_diode_current_minus_series_peak_abs_A=float(np.max(np.abs(reported-i))))
        elif ref.startswith('U'):
            pin_current[(ref,'4')]=zero.copy();pin_current[(ref,'11')]=zero.copy();channels={}
            for unit,plus,minus,output in CHANNELS:
                channel=ref+unit;powers={};hidden_return=zero.copy()
                for tag,pin in [('P',plus),('M',minus),('V','4'),('G','11'),('O',output)]:
                    i=current('VS_'+channel+'_'+tag)
                    hidden_return+=i
                    if pin in ['4','11']:pin_current[(ref,pin)]+=i
                    else:pin_current[(ref,pin)]=i
                    powers[tag]=mean_product(v(pins[pin]),i,t)
                channels[unit]=dict(terminal_power_W=powers,net_absorption_W=sum(powers.values()),inferred_global_ground_return_mean_A=mean(hidden_return,t),inferred_global_ground_return_peak_abs_A=float(np.max(np.abs(hidden_return))))
                if (ref,'11') not in raw_ground:raw_ground[(ref,'11')]=zero.copy()
                raw_ground[(ref,'11')]+=current('VS_'+channel+'_G')
                pin_current[(ref,'11')]-=hidden_return
                amp_input+=powers['P']+powers['M']
            heat[ref]=sum(c['net_absorption_W'] for c in channels.values())
            details[ref]=dict(kind='opamp_package',heat_W=heat[ref],channels=channels)
    i_cell=-current('Vbat');p_cell=mean_product(v('VBAT'),i_cell,t)
    padloads=[];vbat_sum=zero.copy();gnd_sum=zero.copy();raw_gnd_sum=zero.copy();is_high=v('ENCODED_OUT')>.5*v('VBAT')
    def conditional(a,condition):
        # Time-weighted trapezoids in segments whose midpoint state is selected.
        mask=condition[:-1]&condition[1:];dt=np.diff(t)*mask
        return float(np.sum(dt*(a[:-1]+a[1:])/2)/np.sum(dt)) if np.sum(dt)>0 else None
    peak_index=int(np.argmax(i_cell))
    for p in intent['parts']:
        if p['ref']=='BT1':continue
        for pin,net in p['logical_pins'].items():
            if net not in ['VBAT','GND']:continue
            into=pin_current[(p['ref'],pin)];load=into if net=='VBAT' else -into
            if net=='VBAT':vbat_sum+=load
            else:
                gnd_sum+=load
                raw_gnd_sum+=-raw_ground.get((p['ref'],pin),into)
            padloads.append(dict(ref=p['ref'],pin=pin,native_net=p['pins'][pin],rail=net,
                sign='positive draw from VBAT' if net=='VBAT' else 'positive return into GND',
                mean_A=mean(load,t),output_high_mean_A=conditional(load,is_high),output_low_mean_A=conditional(load,~is_high),
                minimum_A=float(load.min()),maximum_A=float(load.max()),conservative_positive_peak_A=max(0.,float(load.max())),
                at_settled_cell_peak_A=float(load[peak_index]),
                ground_assignment='measured VEE plus inferred global-0 model return' if (p['ref'],pin) in raw_ground else 'direct passive or supply terminal',
                raw_mean_A=mean(-raw_ground[(p['ref'],pin)],t) if (p['ref'],pin) in raw_ground else mean(load,t)))
    residual=p_cell-sum(heat.values())-cap_energy/(end-start)
    cell=dict(mean_A=mean(i_cell,t),rms_A=math.sqrt(mean_product(i_cell,i_cell,t)),minimum_sampled_A=float(i_cell.min()),
        peak_sampled_A=float(i_cell.max()),peak_sample_time_s=float(t[peak_index]),electrical_power_W=p_cell,charge_C=mean(i_cell,t)*(end-start))
    energy=dict(cell_input_W=p_cell,total_part_heat_W=sum(heat.values()),external_capacitor_delta_energy_J=cap_energy,
        external_capacitor_storage_W=cap_energy/(end-start),external_capacitor_terminal_power_W=cap_terminal,
        capacitor_integration_vs_endpoint_delta_W=cap_terminal-cap_energy/(end-start),residual_W=residual,residual_fraction_of_input=residual/p_cell,
        net_opamp_input_power_W=amp_input,terminal_power_balance_residual_W=p_cell-sum(heat.values())-cap_terminal,
        maximum_sampled_vbat_kcl_residual_A=float(np.max(np.abs(i_cell-vbat_sum))),maximum_sampled_gnd_kcl_residual_A=float(np.max(np.abs(i_cell-raw_gnd_sum))),
        mean_raw_gnd_kcl_residual_A=mean(i_cell-raw_gnd_sum,t),
        maximum_sampled_gnd_kcl_residual_after_global_ground_assignment_A=float(np.max(np.abs(i_cell-gnd_sum))))
    return dict(window=dict(start_s=start,end_s=end,duration_s=end-start),cell=cell,part_heat_W=heat,part_details=details,energy_balance=energy,pi_pad_loads=padloads)

def reference_checks():
    t=np.array([0.,2.]);a=np.array([1.,3.])
    assert abs(mean(a,t)-2)<1e-14
    assert abs(mean_product(a,a,t)-13/3)<1e-14
    assert abs(mean_product(np.array([2.,4.]),a,t)-19/3)<1e-14
    d=clip(np.array([[0.,1.],[2.,3.]]),.5,1.5)
    assert np.allclose(d,[[.5,1.5],[1.5,2.5]])
    return dict(status='PASS',checks=['linear mean 2 A','linear-current mean-square 13/3 A^2','bilinear power mean 19/3 W','clipped interpolated endpoints'])

def postprocess_saved(out):
    old=json.loads((out/'power-budget.json').read_text())
    for path,digest in old['bindings'].items():assert sha(ROOT/path)==digest,'Input changed'
    intent=json.loads((ROOT/'encoder/design-intent.json').read_text())
    header,data=read_csv(out/'waveform.csv.gz')
    with gzip.open(out/'waveform.csv.gz','rb') as stream:
        digest=hashlib.sha256()
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    assert digest.hexdigest()==old['waveform']['uncompressed_sha256']
    windows=[calculate(data,header,intent,w['window']['start_s'],w['window']['end_s']) for w in old['adjacent_complete_frames']]
    nominal=windows[-1]
    for key,val in old['nominal']['cell'].items():
        if key not in nominal['cell']:nominal['cell'][key]=val
    nominal['decoded']=old['nominal']['decoded'];nominal['pulse_widths_s']=old['nominal']['pulse_widths_s']
    old['postprocessing']=dict(previous_helper_sha256=old['helper_sha256'],operation='Assign inferred macro global-ground return to physical GND pins; preserve raw failed check',solver_rerun=False,
        original_measured_rail_check=old['checks']['rail_kcl_residual_below_10nA'])
    old['nominal']=nominal;old['helper_sha256']=sha(__file__);old['limitations']=LIMITS
    old['adjacent_complete_frames']=[dict(window=w['window'],cell=w['cell'],energy_balance=w['energy_balance']) for w in windows]
    old['checks']['gnd_reconstructed_closure_below_10nA']=nominal['energy_balance']['maximum_sampled_gnd_kcl_residual_after_global_ground_assignment_A']<1e-8
    old['status']='qualified_model_accounting_with_explicit_global_ground_assignment'
    save(out/'power-budget.json',old)
    with (out/'component-powers.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['reference','model_mean_heat_W','kind'])
        writer.writerows((ref,power,nominal['part_details'][ref]['kind']) for ref,power in nominal['part_heat_W'].items())
    with (out/'pi-pad-loads.csv').open('w',newline='',encoding='utf-8') as stream:
        w=csv.DictWriter(stream,fieldnames=list(nominal['pi_pad_loads'][0]));w.writeheader();w.writerows(nominal['pi_pad_loads'])
    policy={}
    for rail in ['VBAT','GND']:
        loads=[p for p in nominal['pi_pad_loads'] if p['rail']==rail]
        included=[p for p in loads if not p['ref'].startswith('C') and p['mean_A']>0]
        omitted=[p for p in loads if p not in included]
        policy[rail]=dict(included_mean_A=sum(p['mean_A'] for p in included),included_refs=[p['ref']+'.'+p['pin'] for p in included],
            omitted_signed_mean_A=sum(p['mean_A'] for p in omitted),omitted=omitted,
            cell_mean_A=nominal['cell']['mean_A'],included_minus_cell_A=sum(p['mean_A'] for p in included)-nominal['cell']['mean_A'],
            conservative_positive_peak_sum_A=sum(p['conservative_positive_peak_A'] for p in loads),
            interpretation='Mean-load DC omits ideal capacitors after quantifying residual charge; peak envelope includes them and is noncoincident.')
    save(out/'pi-mean-policy.json',dict(schema='kero.encoder-pi-load-policy/v1',board_sha256=BOARD_SHA,rails=policy,
        capacitor_charge={r:{k:v for k,v in p.items() if 'charge' in k} for r,p in nominal['part_details'].items() if r.startswith('C')},
        limitations=['Ground loads include the explicitly inferred macro global-0 return assigned to physical GND pins.','No negative current is silently clipped; every omitted signed mean is listed.']))
    save(out/'postprocessing-execution.json',dict(command=[sys.executable,*sys.argv],exit_code=0,solver_rerun=False,
        compressed_waveform_verified=True,input_hashes_unchanged=True,analytic_references=reference_checks(),checks=old['checks']))
    print(json.dumps(dict(status=old['status'],cell=nominal['cell'],energy_balance=nominal['energy_balance'],checks=old['checks']),indent=2,default=json_scalar))
    return 0 if old['checks']['gnd_reconstructed_closure_below_10nA'] and old['checks']['energy_residual_below_0p1percent'] else 2

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--model',type=Path,required=True);ap.add_argument('--xyce',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=ROOT/'encoder/analysis/power');ap.add_argument('--postprocess-saved',action='store_true',help='Reprocess retained gzip evidence without launching a solver');ap.add_argument('--reuse-runtime',action='store_true',help='Reprocess an owned completed runtime without rerunning Xyce');args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.postprocess_saved:return postprocess_saved(out)
    if (out/'power-budget.json').exists() or ((out/'runtime').exists() and not args.reuse_runtime):raise FileExistsError('Use a fresh output directory to preserve existing evidence')
    affected=['encoder/Encoder.kicad_pcb','encoder/design-intent.json','encoder/bom.csv','encoder/evidence/netlist.xml','encoded-model/design.json','encoder/evidence/circuit-equivalence.json']
    bindings={p:sha(ROOT/p) for p in affected}
    assert bindings['encoder/Encoder.kicad_pcb']==BOARD_SHA,'Unexpected board revision'
    intent=json.loads((ROOT/'encoder/design-intent.json').read_text());spec=json.loads((ROOT/'encoded-model/design.json').read_text())
    assert intent['source_spec_sha256']==bindings['encoded-model/design.json']
    native_check=validate_native(intent,ROOT/'encoder/evidence/netlist.xml');references=reference_checks()
    capacities={v:shutil.disk_usage(v).free/2**30 for v in ['C:/','D:/']}
    assert shutil.disk_usage(out).free>100*2**30+150*2**20,'D reserve guard'
    model=args.model.resolve();xyce=args.xyce.resolve();model_sha=sha(model)
    assert '.subckt TLV9042 ' in model.read_text(errors='replace')
    scratch=out/'runtime';scratch.mkdir(exist_ok=args.reuse_runtime);deck=scratch/'power.cir'
    expected_deck=make_deck(intent,model.as_posix())
    (out/'circuit.cir').write_text(make_deck(intent,'tlv9042.lib'),encoding='utf-8')
    start=time.time();raw=scratch/'xyce.log'
    if args.reuse_runtime:
        assert deck.read_text()==expected_deck,'Runtime deck differs from current inputs'
        previous_log=(out/'helper-output.log').read_text()
        match=re.search(r'Solver ended 0 elapsed ([0-9.]+)',previous_log)
        assert match and (scratch/'power.cir.csv').is_file(),'No recorded successful solver to reprocess'
        proc=SimpleNamespace(returncode=0)
        solver_elapsed=float(match[1]);start-=solver_elapsed
    else:
        deck.write_text(expected_deck,encoding='utf-8')
        env=os.environ.copy()
        for key in ['TMP','TEMP','MPLCONFIGDIR','WAYRICAD_ANALYSIS_SCRATCH']:env[key]=str(scratch)
        env['OMP_NUM_THREADS']='1'
        with raw.open('wb') as log:
            proc=subprocess.Popen([str(xyce),str(deck)],cwd=scratch,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            while proc.poll() is None:
                if time.time()-start>240 or sum(p.stat().st_size for p in scratch.iterdir() if p.is_file())>150*2**20:
                    proc.terminate();proc.wait(timeout=10);raise RuntimeError('Bounded time/storage guard stopped owned solver')
                time.sleep(.25)
        solver_elapsed=time.time()-start
    save(out/'solver-execution.json',dict(exit_code=proc.returncode,elapsed_s=solver_elapsed,runtime_deck_sha256=sha(deck),
        bindings=bindings,model_sha256=model_sha,reused_completed_runtime=args.reuse_runtime))
    logtext=raw.read_text(errors='replace').replace(model.as_posix(),'[external TI model]').replace(str(model),'[external TI model]')
    (out/'xyce.log').write_text(logtext,encoding='utf-8')
    print('Solver ended',proc.returncode,'elapsed',time.time()-start,flush=True)
    assert proc.returncode==0,'Xyce failed; inspect log'
    csvpath=scratch/'power.cir.csv';header,data=read_csv(csvpath)
    edges,pulses,frames=edges_and_frames(data,spec,.001)
    assert frames and all(f['pass_check'] for f in frames),'Complete-frame decode failed'
    windows=[calculate(data,header,intent,f['start_s'],f['end_s']) for f in frames]
    nominal=windows[-1];nominal['decoded']=frames[-1]['decoded'];nominal['pulse_widths_s']=frames[-1]['widths_s']
    startup=data[data[:,0]<=.001];settling=data[data[:,0]<frames[0]['start_s']]
    nominal['cell']['supply_ramp_peak_sampled_A']=float(np.max(-startup[:,5]))
    nominal['cell']['startup_to_first_accepted_frame_peak_sampled_A']=float(np.max(-settling[:,5]))
    nominal['cell']['startup_window_end_s']=frames[0]['start_s']
    nominal['cell']['series_resistance_scenarios']=[dict(resistance_ohm=r,mean_internal_heat_W=nominal['cell']['rms_A']**2*r,
        mean_voltage_drop_V=nominal['cell']['mean_A']*r,settled_peak_voltage_drop_V=nominal['cell']['peak_sampled_A']*r,
        startup_peak_voltage_drop_V=nominal['cell']['supply_ramp_peak_sampled_A']*r,
        interpretation='postprocessed constant resistance scenario; no coupled source droop recalculation') for r in [0,10,20,30,50,100]]
    balance=nominal['energy_balance'];checks=dict(native_equivalence=native_check,analytic_references=references,
        complete_frames=len(frames),all_frames_decode=True,finite_samples=True,all_heat_nonnegative=all(p>=0 for p in nominal['part_heat_W'].values()),
        energy_residual_below_0p1percent=abs(balance['residual_fraction_of_input'])<.001,
        rail_kcl_residual_below_10nA=max(balance['maximum_sampled_vbat_kcl_residual_A'],balance['maximum_sampled_gnd_kcl_residual_A'])<1e-8)
    previous=json.loads((ROOT/'encoded-model/spice/summary.json').read_text());baseline=next(c for c in previous['cases'] if c['name']=='v3-ramp1ms')
    assert previous['source_spec_sha256']==bindings['encoded-model/design.json'] and previous['model_sha256']==model_sha
    comparison=dict(evidence='encoded-model/spice/summary.json',sha256=sha(ROOT/'encoded-model/spice/summary.json'),
        source_and_model_match=True,mean_current_delta_A=nominal['cell']['mean_A']-baseline['frames'][-1]['cell_current']['mean_A'],
        maximum_pulse_width_delta_s=max(abs(a-b) for a,b in zip(nominal['pulse_widths_s'],baseline['frames'][-1]['widths_s'])),
        prior_cases_applicability='Nominal connectivity/values and macro identity match; prior results exclude layout parasitics just as this schematic simulation does.')
    for p,h in bindings.items():assert sha(ROOT/p)==h,'Input changed during analysis: '+p
    assert sha(model)==model_sha
    with csvpath.open('rb') as src,gzip.open(out/'waveform.csv.gz','wb',compresslevel=6) as dest:shutil.copyfileobj(src,dest)
    waveform_sha=sha(csvpath)
    with gzip.open(out/'waveform.csv.gz','rb') as f:
        verify=hashlib.sha256()
        for chunk in iter(lambda:f.read(1024*1024),b''):verify.update(chunk)
    assert verify.hexdigest()==waveform_sha
    result=dict(schema='kero.encoder-power/v1',bindings=bindings,board_sha256=BOARD_SHA,helper_sha256=sha(__file__),model_sha256=model_sha,
        simulator='Xyce 7.8.0',operating_point=dict(supply_V=3,ramp_s=.001,temperature='macro default',maximum_timestep_s=.0005,stop_s=12),
        nominal=nominal,adjacent_complete_frames=[dict(window=x['window'],cell=x['cell'],energy_balance=x['energy_balance']) for x in windows],
        baseline_comparison=comparison,checks=checks,limitations=LIMITS,
        waveform=dict(file='waveform.csv.gz',uncompressed_sha256=waveform_sha,uncompressed_bytes=csvpath.stat().st_size,columns=header,samples=len(data)),
        execution=dict(command=[str(xyce),'runtime/power.cir'],exit_code=proc.returncode,elapsed_s=time.time()-start,capacity_before_GiB=capacities,
            capacity_after_GiB={v:shutil.disk_usage(v).free/2**30 for v in ['C:/','D:/']},peak_output_estimate_MiB=150,concurrent_solvers=1))
    save(out/'power-budget.json',result)
    with (out/'component-powers.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['reference','model_mean_heat_W','kind']);w.writerows((r,p,nominal['part_details'][r]['kind']) for r,p in nominal['part_heat_W'].items())
    with (out/'pi-pad-loads.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(nominal['pi_pad_loads'][0]));w.writeheader();w.writerows(nominal['pi_pad_loads'])
    removed=[]
    for p in [deck,raw,csvpath]:
        assert p.resolve().parent==scratch.resolve();removed.append(dict(file=p.name,bytes=p.stat().st_size));p.unlink()
    if not any(scratch.iterdir()):scratch.rmdir()
    save(out/'execution.json',dict(command=[sys.executable,*sys.argv],solver_exit=proc.returncode,checks=checks,removed_owned_scratch=removed,
        retained_waveform_gzip_verified=True,input_hashes_unchanged=True,baseline_comparison=comparison))
    print(json.dumps(dict(cell=nominal['cell'],energy_balance=balance,checks=checks,heat=nominal['part_heat_W']),indent=2,default=json_scalar))
    return postprocess_saved(out) if checks['all_heat_nonnegative'] and checks['energy_residual_below_0p1percent'] else 2

if __name__=='__main__':raise SystemExit(main())
