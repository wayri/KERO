"""Analytical oscillator energy budget and optional saved-copper WayriCAD studies.
Run with KiCad Python and an already prepared scientific runtime. No provisioning.
"""
import argparse,gzip,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'/'analysis'
def save(name,data):
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def operating(v=3.,iq=140e-6,vfr=1.8,vfg=2.,dh=.02,dl=.02):
 h,l,f=v-dh,dl,v/4;r1=1e6;r2=402e3;r3=100e3;s=r2+r3;c=1e-6;b=r3/s
 tl=(1-b)*f+b*l;th=(1-b)*f+b*h
 ah=math.log((h-tl)/(h-th));al=math.log((th-l)/(tl-l));tH=r1*c*ah;tL=r1*c*al;t=tH+tL;d=tH/t;q=c*(th-tl);ic=q/t
 ir=max(0,(h-vfr)/4700);ig=max(0,(v-l-vfg)/4700);fh=(h-f)/s;fl=(f-l)/s;div=v/400e3
 av=iq+div+d*ir+(1-d)*ig+ic+d*fh+(1-d)*fl
 high_base=iq+div+ir+fh;low=iq+div+ig+fl
 # Exact exponential charge contribution to battery-current RMS.
 a=(h-tl)/r1;mean_i2=(high_base**2*tH+2*high_base*a*r1*c*(1-math.exp(-ah))+a*a*r1*c/2*(1-math.exp(-2*ah))+low*low*tL)/t
 pa=v*iq/2+d*(v-h)*(ir+fh)+(1-d)*l*(ig+fl)+(v-h+l)*ic
 pb=v*iq/2+d*f*fh+(1-d)*(v-f)*fl
 feedback=s*(d*fh*fh+(1-d)*fl*fl)
 losses={'R1_W':ic*(h-l),'R2_W':feedback*r2/s,'R3_W':feedback*r3/s,'R4_W':div*div*300e3,'R5_W':div*div*100e3,'R6_W':d*ir*ir*4700,'R7_W':(1-d)*ig*ig*4700,'U1A_W':pa,'U1B_W':pb,'D1_electrical_W':d*ir*vfr,'D2_electrical_W':(1-d)*ig*vfg,'ideal_C3_average_loss_W':0,'ideal_C2_steady_loss_W':0}
 assert abs(sum(losses.values())-v*av)<1e-12
 return {'inputs':{'supply_V':v,'Iq_package_A':iq,'red_Vf_V':vfr,'green_Vf_V':vfg,'assumed_high_headroom_V':dh,'assumed_low_output_V':dl},'frequency_Hz':1/t,'high_duty':d,'threshold_low_V':tl,'threshold_high_V':th,'red_on_current_A':ir,'green_on_current_A':ig,'cell_average_A':av,'cell_peak_A':max(high_base+(h-tl)/r1,low),'cell_low_state_A':low,'cell_rms_A':math.sqrt(mean_i2),'cell_internal_loss_W_per_ohm':mean_i2,'battery_terminal_power_W':v*av,'losses':losses,'energy_residual_W':sum(losses.values())-v*av,'high_VBAT_loads_A':{'U1.8':iq+ir+fh+q/tH,'R4.1':div},'low_VBAT_loads_A':{'U1.8':iq+fl,'R4.1':div,'R7.1':ig},'high_GND_injections_A':{'U1.4':iq+fh,'D1.1':ir,'R5.2':div,'C3.2':q/tH}}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--wayricad-source',type=Path);args=ap.parse_args()
 intent=json.loads((ROOT/'design-intent.json').read_text());parts={p['ref']:p for p in intent['parts']}
 assert parts['R6']['value']==parts['R7']['value']=='4.7k' and parts['C3']['value']=='1u' and parts['R1']['value']=='1M','Scenario changed: review model inputs first'
 nominal=operating();cases=[operating(v=v,iq=iq) for v in [2.5,2.7,3.,3.2,3.3] for iq in [140e-6,250e-6,300e-6]]
 diode_cases=[operating(vfr=r,vfg=g) for r in [1.6,2.,] for g in [1.8,2.2]]
 hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['KERO.kicad_pcb','KERO.kicad_sch','KERO.kicad_pro','design-intent.json','bom.csv']}
 report={'model':'Analytical finite-output-rail relaxation oscillator; energy-conserving steady cycle','source_sha256':hashes,'nominal':nominal,'voltage_and_iq_scenarios':cases,'assumed_Vf_scenarios':diode_cases,'conditional_runtime_hours':{str(mah):mah/(nominal['cell_average_A']*1000) for mah in [100,150,200]},'runtime_condition':'Capacity must be measured usable capacity above 2.5 V under this load and temperature; these are scenarios, not CR2032 rated-capacity or lifetime claims.','references':['https://www.ti.com/lit/ds/symlink/lmv358a.pdf','https://energy.panasonic.com/dam/master/pdf/en/datasheet/lithium/CR2032_Datasheet_EN.pdf'],'limits':['20 mV output offsets and diode drops are assumed operating points, not guaranteed at 3 V.','140 uA is two times typical per-channel Iq; 250 and 300 uA package scenarios reflect tabulated 25 C and full-temperature maxima under stated datasheet test conditions.','No startup, overload recovery, switching-current, capacitor leakage/ESR, bias-current, cell electrochemistry or temperature-dependent LED model.','LED electrical power includes optical output; it is not all heat.','Cell internal loss is RMS-current squared times unknown internal resistance. It is outside terminal-power balance.','No transistor-level simulation or bench measurements.']}
 save('power-budget.json',report)
 if args.wayricad_source:
  sys.path.insert(0,str(args.wayricad_source.resolve()))
  from quick_pi_plugin.service import execute
  studies=[('vbat-high','/VBAT','BT1.1',nominal['high_VBAT_loads_A']),('vbat-low','/VBAT','BT1.1',nominal['low_VBAT_loads_A']),('gnd-high-reversed','/GND','BT1.2',nominal['high_GND_injections_A'])]
  receipt={'source_sha256':hashes,'producer':'WayriCAD Quick PI 4.5.0','execution':'Direct service.execute in prepared KiCad 10 Python; no runtime provisioning','stackup_assumption':'35 um top/bottom copper, 1.6 mm outer copper span; 25 um via plating; 20 C. No filled zones in this design.','scope':'VBAT high/low state-mean loads and high-state ground return. GND currents reversed and shifted to a 3 V mathematical reference to obtain resistance/drop magnitudes; ground is physically near 0 V. Low-state signed capacitor ground injection not solved.','studies':[]}
  for label,net,source,loads in studies:
   levels=[]
   edges=[.3,.15,.075,.05] if net=='/GND' else [.3,.15,.075]
   for edge in edges:
    request={'action':'solve','board_path':str(ROOT/'KERO.kicad_pcb'),'net':net,'source_terminal':source,'source_voltage':3.,'sinks':[{'terminal':key,'current_A':value} for key,value in loads.items()],'edge_mm':edge,'mesh_backend':'gmsh','max_cells':100000,'plating_mm':.025,'stackup_override':[{'name':'F.Cu','z_mm':.0175,'thickness_mm':.035},{'name':'B.Cu','z_mm':1.5825,'thickness_mm':.035}],'options':{'temperature_c':20.,'ambient_c':20.,'temperature_limit_c':105.}}
    result=execute(request);r=result['result']
    row={key:r[key] for key in ['voltage_drop_V','conductor_power_W','source_current_A','current_balance_error_A','energy_relative_error','max_current_density_A_mm2','floating_nodes','floating_triangles']};row.update(edge_mm=edge,triangles=len(result['mesh']['triangles']),producer_version=result['producer_version'],geometry_warnings=result['geometry'].get('warnings',[]),request=request)
    if levels:
     row['drop_refinement_change_percent']=100*abs(row['voltage_drop_V']/levels[-1]['voltage_drop_V']-1)
     row['loss_refinement_change_percent']=100*abs(row['conductor_power_W']/levels[-1]['conductor_power_W']-1)
     row['local_peak_refinement_change_percent']=100*abs(row['max_current_density_A_mm2']/levels[-1]['max_current_density_A_mm2']-1)
    levels.append(row)
    if edge==edges[-1]:
     with gzip.open(OUT/('wayricad-'+label+'-fine.json.gz'),'wt',encoding='utf-8') as target:json.dump(result,target,allow_nan=False)
    print(label,edge,'drop_V',r['voltage_drop_V'],'loss_W',r['conductor_power_W'],flush=True)
   global_stable=all(levels[i][key]<1 for i in range(len(levels)-2,len(levels)) for key in ['drop_refinement_change_percent','loss_refinement_change_percent'])
   peak_stable=all(levels[i]['local_peak_refinement_change_percent']<1 for i in range(len(levels)-2,len(levels)))
   receipt['studies'].append({'name':label,'levels':levels,'global_drop_and_loss_stable_at_1percent':global_stable,'local_peak_stable_at_1percent':peak_stable})
  assert hashes=={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in hashes},'Source changed during analysis'
  save('wayricad-summary.json',receipt)
 print('Power budget saved; energy balance verified.')
if __name__=='__main__':main()
