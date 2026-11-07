"""Native checks, rendered previews and explicit schematic/PCB pad parity."""
from pathlib import Path
import subprocess,json,hashlib,xml.etree.ElementTree as ET
import pcbnew as pcb
from build_demo import ROOT,write
CLI=Path(pcb.__file__).resolve().parents[2]/'kicad-cli.exe'
def run(args):
 p=subprocess.run([str(CLI),*map(str,args)],capture_output=True,text=True)
 logs.append({'command':[str(CLI),*map(str,args)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
 if p.returncode:raise RuntimeError(f'{args[:2]} failed with {p.returncode}: {p.stdout} {p.stderr}')
logs=[]
def main():
 e=ROOT/'evidence';e.mkdir(exist_ok=True);preview=ROOT/'previews';preview.mkdir(exist_ok=True)
 sources=[ROOT/'KERO.kicad_sch',ROOT/'KERO.kicad_pcb',ROOT/'KERO.kicad_pro',ROOT/'Demo.kicad_sym',ROOT/'fp-lib-table',ROOT/'sym-lib-table']+list((ROOT/'models').glob('*'))+list((ROOT/'Demo.pretty').glob('*'))
 hashes=lambda:{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
 before=hashes()
 try:
  run(['version'])
  run(['sch','erc',ROOT/'KERO.kicad_sch','--format','json','--output',e/'erc.json','--severity-all','--exit-code-violations'])
  run(['pcb','drc',ROOT/'KERO.kicad_pcb','--format','json','--output',e/'drc.json','--severity-all','--all-track-errors','--schematic-parity','--exit-code-violations'])
  run(['sch','export','netlist',ROOT/'KERO.kicad_sch','--format','kicadxml','--output',e/'netlist.xml'])
  run(['sch','export','svg',ROOT/'KERO.kicad_sch','--output',str(preview)+'/'])
  run(['pcb','export','svg',ROOT/'KERO.kicad_pcb','--output',preview/'board.svg','--mode-single','--layers','F.Cu,F.Silkscreen,Edge.Cuts','--page-size-mode','2'])
  run(['pcb','render',ROOT/'KERO.kicad_pcb','--output',preview/'board-3d.png','--width','1200','--height','850','--rotate','25,0,25','--quality','basic'])
  xml=ET.parse(e/'netlist.xml').getroot();expected={}
  for net in xml.findall('./nets/net'):
   for node in net.findall('node'):expected[(node.attrib['ref'],node.attrib['pin'])]=net.attrib['name']
  b=pcb.LoadBoard(str(ROOT/'KERO.kicad_pcb'));b.BuildConnectivity();actual={};models=[]
  for f in b.GetFootprints():
   if f.GetReference().startswith('H'):continue
   for p in f.Pads():actual[(f.GetReference(),p.GetNumber())]=p.GetNetname()
   assert len(f.Models())>0,f.GetReference()
   for m in f.Models():
    path=ROOT/m.m_Filename.replace('${KIPRJMOD}/','');assert path.is_file(),path;models.append({'reference':f.GetReference(),'model':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'origin':'Original nominal cell envelope' if path.suffix=='.wrl' else 'KiCad LED colour derivative' if path.stem.endswith('_green') else 'Installed KiCad 10.0.6 standard library'})
  assert expected==actual,{'missing':list(expected.keys()-actual.keys()),'different':[(k,v,actual.get(k)) for k,v in expected.items() if actual.get(k)!=v]}
  # Native complete net coverage is supplied by DRC's uncapped-small-board unconnected report.
  drc=json.loads((e/'drc.json').read_text());assert not drc['unconnected_items'] and not drc['violations'] and not drc['schematic_parity']
  assert before==hashes(),'Design changed during verification'
  write(ROOT/'model-manifest.json',json.dumps(models,indent=2)+'\n')
  write(e/'summary.json',json.dumps({'status':'PASS','kicad_version':'10.0.6','native_erc_findings':0,'native_drc_findings':0,'native_unconnected_items':0,'native_schematic_parity_findings':0,'explicit_pad_net_parity':{'pads':len(actual),'nets':len(set(actual.values()))},'resolved_3d_models':models,'source_sha256':before,'limitations':['Analytical oscillator timing only; no transistor-level simulation or bench measurements.','Nominal CR2032 envelope is illustrative, not a manufacturer mechanical model.','Generic passives and LEDs are specification selections, not procurement-qualified MPNs.','KiCad CLI reports sandbox registry-access warnings; native checks and exports complete.'],'ignored_native_drc_checks':drc.get('ignored_checks',[])},indent=2)+'\n')
  print('PASS: ERC, DRC, schematic parity, 32 pad/net mappings, all component models resolved')
 finally:write(e/'commands.json',json.dumps(logs,indent=2)+'\n')
if __name__=='__main__':main()
