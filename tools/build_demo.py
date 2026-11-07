from pathlib import Path
import re,json,copy,uuid,math,csv,shutil,argparse
ROOT=Path(__file__).resolve().parents[1]
LIB=Path(r'C:/Program Files/KiCad/10.0/share/kicad')
NS=uuid.UUID('ebea4d74-522b-4822-9732-82a3715176fa')
def uid(s):return str(uuid.uuid5(NS,s))
class Q(str):pass
def parse(s):
 st=[];root=None
 for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',s):
  if t=='(':
   n=[]
   if st:st[-1].append(n)
   else:root=n
   st.append(n)
  elif t==')':st.pop()
  else:st[-1].append(Q(json.loads(t)) if t.startswith('"') else t)
 return root
def dump(n,level=0):
 if not isinstance(n,list):return json.dumps(str(n),ensure_ascii=False) if isinstance(n,Q) else str(n)
 compact='('+' '.join(dump(x,level+1) for x in n)+')'
 if len(compact)<130 and '\n' not in compact:return compact
 return '('+dump(n[0],level+1)+'\n'+'\n'.join('  '*(level+1)+dump(x,level+1) for x in n[1:])+'\n'+'  '*level+')'
def kids(n,k):return [x for x in n if isinstance(x,list) and x and x[0]==k]
def one(n,k):return next(iter(kids(n,k)),None)
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8',newline='\n')
def sym(lib,name):
 nodes=parse((LIB/'symbols'/f'{lib}.kicad_sym').read_text(encoding='utf-8'))
 def get(name):
  n=copy.deepcopy(next(x for x in kids(nodes,'symbol') if x[1]==name));ex=one(n,'extends')
  if ex:
   b=get(ex[1]);props={x[1]:x for x in kids(b,'property')};props.update({x[1]:x for x in kids(n,'property')});n=[x for x in b if not(isinstance(x,list) and x[0]=='property')]+list(props.values());n[1]=Q(name)
  return n
 n=get(name);local=lib+'_'+name;n[1]=Q(local)
 for sub in kids(n,'symbol'):sub[1]=Q(local+'_'+'_'.join(sub[1].rsplit('_',2)[-2:]))
 return n
R='Resistor_SMD:R_0603_1608Metric'
C='Capacitor_SMD:C_0603_1608Metric'
CP='Capacitor_SMD:C_0805_2012Metric'
rows=[
('U1','Amplifier_Operational:LMV358','LMV358ADR','Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',(114.3,81.28,0),(99.06,71.12,0),{'1':'OUT','2':'TIMING','3':'SCHMITT','4':'GND','5':'DIVIDER','6':'VREF','7':'VREF','8':'VBAT'},'TI LMV358ADR, SOIC-8; 2.5 to 5.5 V'),
('R1','Device:R','1M',R,(114.3,104.14,90),(91.44,73.66,0),{'1':'TIMING','2':'OUT'},'1%, 0.1 W, 0603'),
('R2','Device:R','402k',R,(114.3,58.42,90),(96.52,64.77,0),{'1':'SCHMITT','2':'OUT'},'1%, 0.1 W, 0603'),
('R3','Device:R','100k',R,(88.9,58.42,90),(91.44,68.58,0),{'1':'VREF','2':'SCHMITT'},'1%, 0.1 W, 0603'),
('R4','Device:R','300k',R,(40.64,116.84,0),(91.44,81.28,0),{'1':'VBAT','2':'DIVIDER'},'1%, 0.1 W, 0603'),
('R5','Device:R','100k',R,(40.64,132.08,0),(91.44,85.09,0),{'1':'DIVIDER','2':'GND'},'1%, 0.1 W, 0603'),
('C1','Device:C','1u',CP,(88.9,104.14,0),(88.9,77.47,0),{'1':'TIMING','2':'GND'},'10 V min, X7R, +/-10%, 0805; effective C affects frequency'),
('C2','Device:C','100n',C,(66.04,68.58,0),(102.87,76.2,0),{'1':'VBAT','2':'GND'},'10 V min, X7R, +/-10%, 0603'),
('BT1','Device:Battery_Cell','CR2032','Battery:BatteryHolder_Keystone_1058_1x2032',(43.18,68.58,0),(69.85,73.66,0),{'1':'VBAT','2':'GND'},'Keystone 1058 holder; one CR2032, 3 V nominal'),
('R6','Device:R','3.3k',R,(154.94,91.44,0),(104.14,66.04,0),{'1':'OUT','2':'RED_A'},'1%, 0.1 W, 0603'),
('D1','Device:LED','RED','LED_THT:LED_D5.0mm',(154.94,106.68,90),(106.68,58.42,270),{'1':'GND','2':'RED_A'},'5 mm diffused red LED; low-current type, Vf <=2 V preferred'),
('R7','Device:R','3.3k',R,(180.34,66.04,0),(104.14,83.82,0),{'1':'VBAT','2':'GREEN_A'},'1%, 0.1 W, 0603'),
('D2','Device:LED','GREEN','LED_THT:LED_D5.0mm',(180.34,81.28,90),(104.14,88.9,270),{'1':'OUT','2':'GREEN_A'},'5 mm diffused yellow-green LED; Vf <=2.1 V; avoid blue/InGaN green')]
def parts(variant):
 ps=[dict(zip(['ref','symbol','value','footprint','sch','pcb','pins','rating'],r)) for r in rows]
 if variant=='timing':next(p for p in ps if p['ref']=='R1')['value']='470k'
 if variant=='layout':
  next(p for p in ps if p['ref']=='D1')['pcb']=(104.14,58.42,270)
  next(p for p in ps if p['ref']=='R6')['pcb']=(101.6,66.04,0)
 return ps
def schematic(ps,variant):
 from draw_schematic import schematic as draw
 return draw(ps,variant)
def localize(ps):
 models=ROOT/'models';models.mkdir(exist_ok=True);dest=ROOT/'Demo.pretty';dest.mkdir(exist_ok=True);manifest=[]
 for fp in sorted({p['footprint'] for p in ps}):
  lib,name=fp.split(':');n=parse((LIB/'footprints'/f'{lib}.pretty'/f'{name}.kicad_mod').read_text(encoding='utf-8'))
  for m in kids(n,'model'):
   source=LIB/'3dmodels'/m[1].split('}/',1)[1];target=models/source.name
   if not target.exists():shutil.copyfile(source,target)
   m[1]=Q('${KIPRJMOD}/models/'+source.name);manifest.append({'footprint':fp,'model':'models/'+source.name,'source':str(source)})
  assert kids(n,'model'),fp
  write(dest/f'{name}.kicad_mod',dump(n)+'\n')
 # Full per-reference model hashes are written by tools/validate.py.

 write(ROOT/'fp-lib-table','(fp_lib_table (version 7) (lib (name "Demo") (type "KiCad") (uri "${KIPRJMOD}/Demo.pretty") (options "") (descr "Localized KiCad 10 footprints")))\n')
 write(ROOT/'sym-lib-table','(sym_lib_table (version 7) (lib (name "Demo") (type "KiCad") (uri "${KIPRJMOD}/Demo.kicad_sym") (options "") (descr "Localized KiCad 10 symbols")))\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['baseline','timing','layout'],default='baseline');args=ap.parse_args();ps=parts(args.variant);localize(ps)
 from draw_schematic import schematic as draw
 draw(ps,'baseline' if args.variant=='layout' else args.variant)
 write(ROOT/'design-intent.json',json.dumps({'variant':args.variant,'supply_v':3,'parts':ps},indent=2)+'\n')
 with (ROOT/'bom.csv').open('w',encoding='utf-8',newline='') as f:
  w=csv.writer(f);w.writerow(['Reference','Quantity','Value','Footprint','Manufacturer','MPN','Rating','Datasheet'])
  for p in ps:w.writerow([p['ref'],1,p['value'],'Demo:'+p['footprint'].split(':')[1],'Texas Instruments' if p['ref']=='U1' else 'Keystone' if p['ref']=='BT1' else 'Generic','LMV358ADR' if p['ref']=='U1' else '1058' if p['ref']=='BT1' else 'Select to specification',p['rating'],'https://www.ti.com/lit/ds/symlink/lmv358a.pdf' if p['ref']=='U1' else ''])
 from layout import build_board
 build_board(ps,args.variant)
if __name__=='__main__':main()
