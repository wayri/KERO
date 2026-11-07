"""Run existing WayriCAD Quick PI on the frozen encoder; never provision runtimes."""
import argparse,hashlib,json,os,sys,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'encoder'; BOARD=BASE/'Encoder.kicad_pcb'
SCRATCH=BASE/'.scratch'/'pi-analysis'; OUT=BASE/'analysis'/'pi'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--wayricad-source',required=True,type=Path);ap.add_argument('--loads',required=True,type=Path);a=ap.parse_args()
 if OUT.exists():raise FileExistsError('Preserve existing PI results before another revision.')
 SCRATCH.mkdir(parents=True,exist_ok=True)
 os.environ['TEMP']=os.environ['TMP']=str(SCRATCH);os.environ['KICAD_CONFIG_HOME']=str(SCRATCH/'kicad-config');os.environ['WAYRICAD_ANALYSIS_SCRATCH']=str(SCRATCH);os.environ['MPLCONFIGDIR']=str(SCRATCH/'matplotlib');os.environ['MPLBACKEND']='Agg';sys.dont_write_bytecode=True
 sys.path.insert(0,str(a.wayricad_source.resolve()))
 from quick_pi_plugin.service import execute
 from quick_pi_plugin.batch import validate_study
 from wayricad_runtime.project_results import save_result,load_result
 from wayricad_runtime.pocket_kivi_export import export_bundle
 loads=json.loads(a.loads.read_text(encoding='utf-8'));before=sha(BOARD)
 assert loads['source_sha256']==before,'Load cases belong to another board'
 power=ROOT/loads['power_budget_file'];assert sha(power)==loads['power_budget_sha256'],'Power budget changed'
 stage=SCRATCH/'stage';stage.mkdir()
 write(stage/'load-cases.json',loads)
 summary={'schema':'kero.encoder-pi/v1','source_sha256':before,'board_path':str(BOARD),'power_budget_sha256':sha(power),'stackup_assumption':'35 um top/bottom copper, 1.6 mm outer copper span, 25 um via plating, fixed 20 C copper','producer':'Actual WayriCAD Quick PI service.execute; no provisioning','producer_script_sha256':sha(Path(__file__)),'studies':[],'capacity_before_GiB':{d:shutil.disk_usage(d).free/2**30 for d in ['C:/','D:/']},'limitations':loads['limitations']}
 study_cases=[];receipts=[];started=time.time()
 for case in loads['cases']:
  levels=[];bundle=None
  for edge in [.3,.15,.075,.05]:
   request={'action':'solve','board_path':str(BOARD),'net':case['net'],'source_terminal':case['source_terminal'],'source_voltage':3.,'sinks':[{'terminal':k,'current_A':v} for k,v in case['sinks_A'].items() if v>0],'edge_mm':edge,'mesh_backend':'gmsh','max_cells':100000,'plating_mm':.025,'stackup_override':[{'name':'F.Cu','z_mm':.0175,'thickness_mm':.035},{'name':'B.Cu','z_mm':1.5825,'thickness_mm':.035}],'options':{'temperature_c':20.,'ambient_c':20.,'temperature_limit_c':105.}}
   bundle=execute(request);result=bundle['result'];assert sha(BOARD)==before,'PCB changed during PI'
   assert bundle['geometry']['source_sha256']==before
   if result.get('feasibility',{}).get('operating_point_valid') is not True:raise ValueError('PI operating point not feasible')
   row={k:result[k] for k in ['voltage_drop_V','conductor_power_W','source_current_A','current_balance_error_A','energy_relative_error','max_current_density_A_mm2','floating_nodes','floating_triangles']}
   row.update(edge_mm=edge,triangles=len(bundle['mesh']['triangles']),geometry_warnings=bundle['geometry'].get('warnings',[]))
   if levels:
    for key,metric in [('drop','voltage_drop_V'),('loss','conductor_power_W'),('local_peak','max_current_density_A_mm2')]:row[key+'_refinement_change_percent']=100*abs(row[metric]/levels[-1][metric]-1) if levels[-1][metric] else None
   levels.append(row);print(case['name'],edge,'drop_V',row['voltage_drop_V'],'loss_W',row['conductor_power_W'],flush=True)
   stable=len(levels)>=3 and all(levels[i][k] is not None and levels[i][k]<1 for i in [-2,-1] for k in ['drop_refinement_change_percent','loss_refinement_change_percent'])
   if stable:break
  evidence={'board_path':str(BOARD),'source_sha256':before,'source_state':'saved','tool':'Quick PI','version':bundle['producer_version'],'source_root':str(BASE),'units':{'potential_V':'V','cell_power_W':'W','cell_J_A_mm2':'A/mm2','points_mm':'mm'},'coordinate_frame':'KiCad PCB XY in mm','z_basis':'front-depth'}
  bundle['kero_load_basis']=case['meaning'];bundle['kero_limits']=loads['limitations']
  native=case['name']+'.quick-pi.results.json';portable=case['name']+'.pocket-kivi.json'
  saved=save_result(BASE,'quick-pi',bundle,pocket_kivi=evidence,destination=stage/native)
  companion=export_bundle(bundle,stage/portable,**evidence)
  receipts.append({'name':case['name'],'native_file':native,'portable_file':portable,'native_bytes':saved['bytes'],'portable_bytes':companion['bytes']})
  summary['studies'].append({'name':case['name'],'net':case['net'],'load_basis':case['meaning'],'levels':levels,'global_drop_and_loss_stable_at_1percent':stable,'local_peak_stable_at_1percent':len(levels)>=3 and all(levels[i]['local_peak_refinement_change_percent'] is not None and levels[i]['local_peak_refinement_change_percent']<1 for i in [-2,-1]),'producer_version':bundle['producer_version']})
  study_cases.append({'name':case['name'],'electrical':{k:v for k,v in request.items() if k not in ['action','board_path']}})
 study={'schema':'wayricad.pi-batch/v1','cases':study_cases};validate_study(study);write(stage/'Encoder.quick-pi.study.json',study)
 assert sha(BOARD)==before and sha(power)==loads['power_budget_sha256']
 summary['elapsed_seconds']=time.time()-started;summary['capacity_after_GiB']={d:shutil.disk_usage(d).free/2**30 for d in ['C:/','D:/']};write(stage/'summary.json',summary)
 OUT.parent.mkdir(exist_ok=True);os.replace(stage,OUT)
 for r in receipts:
  loaded=load_result(BASE,OUT/r['native_file'],plugin='quick-pi',chosen=True);assert loaded['receipt']['source_state']=='current' and loaded['receipt']['can_restore'];r['native_load_receipt']=loaded['receipt']
 write(OUT/'export-receipts.json',receipts)
 print('PI files exported and reloaded against exact saved source.',flush=True)
if __name__=='__main__':main()
