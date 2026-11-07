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
  next(p for p in ps if p['ref']=='R6')['pcb']=(101.6,63.5,0)
 return ps
def schematic(ps,variant):
 libs={p['symbol']:sym(*p['symbol'].split(':')) for p in ps};libs['power:PWR_FLAG']=sym('power','PWR_FLAG')
 # LMV358A has the same SOIC-8 pinout as LMV358; retain native multi-unit geometry.
 n=libs['Amplifier_Operational:LMV358']
 for k,v in [('Value','LMV358ADR'),('Datasheet','https://www.ti.com/lit/ds/symlink/lmv358a.pdf'),('Description','LMV358A dual low-voltage op amp; verified SOIC-8 pin map')]:next(x for x in kids(n,'property') if x[1]==k)[2]=Q(v)
 write(ROOT/'Demo.kicad_sym',dump(['kicad_symbol_lib',['version',20241209],['generator',Q('eeschema')]]+list(libs.values()))+'\n')
 cache=copy.deepcopy(list(libs.values()))
 for n in cache:n[1]=Q('Demo:'+n[1])
 sch=['kicad_sch',['version',20250114],['generator',Q('eeschema')],['uuid',Q(uid('root'))],['paper',Q('A4')],['title_block',['title',Q('KERO - coin-cell red / green relaxation oscillator')],['date',Q('2026-11-07')],['rev',Q(variant)]],['lib_symbols']+cache]
 def eff(s=1.27):return ['effects',['font',['size',s,s]]]
 def prop(k,v,x,y,hide=False):
  e=eff()
  if hide:e.append(['hide','yes'])
  return ['property',Q(k),Q(v),['at',x,y,0],e]
 def place(p,x,y,a=0,unit=1):
  ref=p['ref'];rx,ry,vx,vy=(x,y-7.62,x,y+7.62) if ref=='U1' else (x+6.35,y-1.27,x+6.35,y+1.27)
  if a==90 and ref.startswith('R'):rx,ry,vx,vy=x,y-5.08,x,y-2.54
  n=['symbol',['lib_id',Q('Demo:'+p['symbol'].replace(':','_'))],['at',x,y,a],['unit',unit],['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',Q(uid(ref+('' if unit==1 else '-'+str(unit))))],prop('Reference',ref,rx,ry),prop('Value',p['value'],vx,vy),prop('Footprint','Demo:'+p['footprint'].split(':')[1] if p['footprint'].split(':')[1] else '',x,y,True),prop('Datasheet','https://www.ti.com/lit/ds/symlink/lmv358a.pdf' if ref=='U1' else '',x,y,True),prop('Manufacturer','Texas Instruments' if ref=='U1' else 'Keystone' if ref=='BT1' else 'Generic',x,y,True),prop('MPN','LMV358ADR' if ref=='U1' else '1058' if ref=='BT1' else 'Select to specification',x,y,True),prop('Rating',p['rating'],x,y,True),['instances',['project',Q('KERO'),['path',Q('/'+uid('root')),['reference',Q(ref)],['unit',unit]]]]];
  for field in kids(n,'property'):
   if field[1] in ['Reference','Value'] and a==90:one(field,'at')[3]=90
  sch.append(n)
 for p in ps:place(p,*p['sch'])
 u=next(p for p in ps if p['ref']=='U1');place(u,66.04,127,unit=2);place(u,88.9,137.16,unit=3)
 def path(*pts):
  for a,b in zip(pts,pts[1:]):sch.append(['wire',['pts',['xy',*a],['xy',*b]],['stroke',['width',0.1524],['type','default']],['uuid',Q(uid('wire'+str(a)+str(b)))]])
 def label(n,p):sch.append(['label',Q(n),['at',*p,0],eff(),['uuid',Q(uid('label'+n+str(p)))]])
 def dot(p):sch.append(['junction',['at',*p],['diameter',0.9144],['color',0,0,0,0],['uuid',Q(uid('dot'+str(p)))]])
 def note(s,x,y,size=1.27):sch.append(['text',Q(s),['at',x,y,0],eff(size),['uuid',Q(uid('note'+s.splitlines()[0]))]])
 path((85.09,58.42),(78.74,58.42));label('VREF',(78.74,58.42))
 path((92.71,58.42),(101.6,58.42),(110.49,58.42));dot((101.6,58.42));label('SCHMITT',(101.6,58.42))
 path((101.6,58.42),(101.6,78.74),(106.68,78.74))
 path((118.11,58.42),(132.08,58.42),(132.08,81.28),(132.08,104.14),(118.11,104.14));dot((132.08,81.28));label('OUT',(132.08,81.28))
 path((121.92,81.28),(132.08,81.28))
 path((110.49,104.14),(99.06,104.14),(99.06,100.33),(99.06,83.82),(106.68,83.82));dot((99.06,100.33));label('TIMING',(99.06,100.33))
 path((88.9,100.33),(99.06,100.33));path((88.9,107.95),(88.9,114.3));label('GND',(88.9,114.3))
 # Buffered quarter-supply reference, kept separate from oscillator wire lanes.
 path((40.64,113.03),(40.64,106.68));label('VBAT',(40.64,106.68))
 path((40.64,120.65),(40.64,124.46),(40.64,128.27));dot((40.64,124.46));path((40.64,124.46),(58.42,124.46));label('DIVIDER',(45.72,124.46))
 path((40.64,135.89),(40.64,142.24));label('GND',(40.64,142.24))
 path((73.66,127),(78.74,127),(78.74,139.7),(53.34,139.7),(53.34,129.54),(58.42,129.54));dot((78.74,127));label('VREF',(78.74,127))
 path((86.36,129.54),(86.36,124.46));label('VBAT',(86.36,124.46))
 path((86.36,144.78),(86.36,149.86));label('GND',(86.36,149.86))
 # LED current paths, opposite phases on the same oscillator output.
 path((154.94,87.63),(154.94,81.28));label('OUT',(154.94,81.28))
 path((154.94,95.25),(154.94,102.87));label('RED_A',(154.94,99.06))
 path((154.94,110.49),(154.94,116.84));label('GND',(154.94,116.84))
 path((180.34,62.23),(180.34,55.88));label('VBAT',(180.34,55.88))
 path((180.34,69.85),(180.34,77.47));label('GREEN_A',(180.34,73.66))
 path((180.34,85.09),(180.34,91.44));label('OUT',(180.34,91.44))
 # Power entry uses actual symbol pin coordinates, including battery-cell asymmetry.
 for ref in ['BT1','C2']:
  p=next(p for p in ps if p['ref']==ref);n=libs[p['symbol']];x,y,a=p['sch']
  for sub in kids(n,'symbol'):
   for pin in kids(sub,'pin'):
    at=one(pin,'at');num=one(pin,'number')[1];px,py=x+float(at[1]),y-float(at[2]);dy=-5.08 if num=='1' else 5.08
    path((px,py),(px,py+dy));label(p['pins'][num],(px,py+dy))
 for s,x,y in [('COIN CELL / BYPASS',50.8,48.26),('SCHMITT + RC OSCILLATOR',106.68,40.64),('ALTERNATING LEDs',168.91,40.64),('REFERENCE BUFFER',55.88,99.06)]:note(s,x,y,1.7)
 note('RED = output HIGH\nGREEN = output LOW\nUse low-Vf yellow-green LED.',170.18,132.08)
 note('CR2032: 3 V nominal. Design operating range: 2.5-3.3 V.\nR2/R3 keep both oscillator inputs below 0.41 x VBAT.\nRemove cell to switch off. No reverse-cell protection.',53.34,87.63)
 rt=470000 if variant=='timing' else 1000000
 lo=.25*402/502;hi=lo+100/502;t=rt*1e-6*(math.log((1-lo)/(1-hi))+math.log(hi/lo))
 note(f'Ideal calculated f = {1/t:.2f} Hz; red duty about 29%.\nR1/C1 set speed; R2/R3 set hysteresis.\nFrequency, LED brightness and battery life require bench verification.',144.78,154.94)
 for i,(net,x) in enumerate([('VBAT',40.64),('GND',60.96)],1):
  f={'ref':f'#FLG0{i:02d}','symbol':'power:PWR_FLAG','value':'PWR_FLAG','footprint':':','rating':''};place(f,x,165.1);path((x,165.1),(x,170.18));label(net,(x,170.18))
  node=next(n for n in sch if isinstance(n,list) and n[0]=='symbol' and one(n,'uuid')[1]==uid(f['ref']))
  one(node,'in_bom')[1]='no';one(node,'on_board')[1]='no'
  for propnode in kids(node,'property'):one(propnode,'effects').append(['hide','yes'])
 write(ROOT/'KERO.kicad_sch',dump(sch)+'\n')
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
 ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['baseline','timing','layout'],default='baseline');args=ap.parse_args();ps=parts(args.variant);localize(ps);schematic(ps,'baseline' if args.variant=='layout' else args.variant)
 write(ROOT/'design-intent.json',json.dumps({'variant':args.variant,'supply_v':3,'parts':ps},indent=2)+'\n')
 with (ROOT/'bom.csv').open('w',encoding='utf-8',newline='') as f:
  w=csv.writer(f);w.writerow(['Reference','Quantity','Value','Footprint','Manufacturer','MPN','Rating','Datasheet'])
  for p in ps:w.writerow([p['ref'],1,p['value'],'Demo:'+p['footprint'].split(':')[1],'Texas Instruments' if p['ref']=='U1' else 'Keystone' if p['ref']=='BT1' else 'Generic','LMV358ADR' if p['ref']=='U1' else '1058' if p['ref']=='BT1' else 'Select to specification',p['rating'],'https://www.ti.com/lit/ds/symlink/lmv358a.pdf' if p['ref']=='U1' else ''])
 from layout import build_board
 build_board(ps,args.variant)
if __name__=='__main__':main()
