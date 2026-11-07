"""One extra source-bound mesh check of the floating region in GND mean-load PI."""
import argparse,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'encoder';OUT=BASE/'analysis'/'pi-ground-refinement';SCRATCH=BASE/'.scratch'/'ground-refinement'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--wayricad-source',required=True,type=Path);args=a.parse_args()
 if OUT.exists():raise FileExistsError(OUT)
 SCRATCH.mkdir(parents=True,exist_ok=True);os.environ['TEMP']=os.environ['TMP']=str(SCRATCH);os.environ['MPLCONFIGDIR']=str(SCRATCH/'matplotlib');os.environ['KICAD_CONFIG_HOME']=str(SCRATCH/'kicad-config');sys.dont_write_bytecode=True
 sys.path.insert(0,str(args.wayricad_source));from quick_pi_plugin.service import execute
 from wayricad_runtime.project_results import save_result,load_result
 from wayricad_runtime.pocket_kivi_export import export_bundle
 source=BASE/'analysis/pi/gnd-mean-reversed.quick-pi.results.json';prior=json.loads(source.read_text(encoding='utf-8'));before=sha(BASE/'Encoder.kicad_pcb')
 assert prior['geometry']['source_sha256']==before
 request={**prior['request'],'board_path':str(BASE/'Encoder.kicad_pcb'),'edge_mm':.05};result=execute(request);assert sha(BASE/'Encoder.kicad_pcb')==before
 OUT.mkdir();evidence={'board_path':str(BASE/'Encoder.kicad_pcb'),'source_sha256':before,'source_state':'saved','tool':'Quick PI','version':result['producer_version'],'source_root':str(BASE),'units':{'potential_V':'V','cell_power_W':'W','cell_J_A_mm2':'A/mm2','points_mm':'mm'},'coordinate_frame':'KiCad PCB XY in mm','z_basis':'front-depth'}
 result['kero_load_basis']=prior['kero_load_basis'];native=OUT/'gnd-mean-reversed-0p05.quick-pi.results.json';save_result(BASE,'quick-pi',result,pocket_kivi=evidence,destination=native);export_bundle(result,OUT/'gnd-mean-reversed-0p05.pocket-kivi.json',**evidence)
 loaded=load_result(BASE,native,plugin='quick-pi',chosen=True);assert loaded['receipt']['source_state']=='current' and loaded['receipt']['can_restore']
 fields=['voltage_drop_V','conductor_power_W','source_current_A','current_balance_error_A','energy_relative_error','max_current_density_A_mm2','floating_nodes','floating_triangles']
 summary={'schema':'kero.encoder-ground-pi-refinement/v1','source_sha256':before,'source_report_sha256':sha(source),'producer_script_sha256':sha(Path(__file__)),'request':request,'before':{k:prior['result'][k] for k in fields},'after':{k:result['result'][k] for k in fields},'native_load_receipt':loaded['receipt'],'scope':'Extra refinement tests the unresolved mean-load GND region; no source, circuit, terminal loads, or solver checks were altered.'}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+chr(10),encoding='utf-8',newline=chr(10));print(json.dumps(summary['after']),flush=True)
if __name__=='__main__':main()
