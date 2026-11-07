"""Save existing completed PI fields for native WayriCAD and Pocket KiView.
No solver execution. Use a new output directory for another revision.
"""
import argparse,gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--wayricad-source',required=True,type=Path);ap.add_argument('--output',type=Path,default=ROOT/'analysis'/'pi');a=ap.parse_args();sys.path.insert(0,str(a.wayricad_source.resolve()))
 from wayricad_runtime.pocket_kivi_export import export_bundle
 from wayricad_runtime.project_results import save_result,load_result
 from quick_pi_plugin.batch import validate_study
 a.output.mkdir(parents=True,exist_ok=True);receipts=[];cases=[]
 for label in ['vbat-high','vbat-low','gnd-high-reversed']:
  source=ROOT/'evidence'/'analysis'/('wayricad-'+label+'-fine.json.gz')
  with gzip.open(source,'rt',encoding='utf-8') as stream:bundle=json.load(stream)
  evidence=dict(board_path=str(ROOT/'KERO.kicad_pcb'),source_sha256=bundle['geometry']['source_sha256'],source_state='saved',tool='Quick PI',version=bundle['producer_version'],source_root=str(ROOT),units={'potential_V':'V','cell_power_W':'W','cell_J_A_mm2':'A/mm2','points_mm':'mm'},coordinate_frame='KiCad PCB XY in mm',z_basis='front-depth')
  target=a.output/('KERO.'+label+'.quick-pi.results.json')
  if target.exists():raise ValueError('Choose a new output directory; native result already exists.')
  receipt=save_result(ROOT,'quick-pi',bundle,pocket_kivi=evidence,destination=target)
  loaded=load_result(ROOT,target,plugin='quick-pi',chosen=True)
  assert loaded['receipt']['source_state']=='current' and loaded['receipt']['can_restore']
  companion=export_bundle(bundle,a.output/('KERO.'+label+'.pocket-kivi.json'),**evidence)
  electrical={k:v for k,v in bundle['request'].items() if k not in ['action','board_path']}
  cases.append({'name':label,'electrical':electrical})
  receipts.append({'case':label,'native':{k:v for k,v in receipt.items() if k not in ['path']},'portable':{**companion,'json':str(Path(companion['json']).relative_to(ROOT))},'native_load_source_state':loaded['receipt']['source_state']})
 study={'schema':'wayricad.pi-batch/v1','cases':cases};validate_study(study)
 (a.output/'KERO.quick-pi.study.json').write_text(json.dumps(study,indent=2)+'\n',encoding='utf-8')
 (a.output/'export-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
 print([(r['case'],r['native']['bytes'],r['portable']['bytes'],r['native_load_source_state']) for r in receipts])
if __name__=='__main__':main()
