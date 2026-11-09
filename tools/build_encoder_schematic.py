"""Build the native hierarchical RC encoder from the simulation-bound specification."""
from pathlib import Path
import copy,json,math,hashlib,subprocess,os,csv,xml.etree.ElementTree as ET,argparse
from build_demo import ROOT,LIB,Q,uid,kids,one,dump,write,sym
OUT=ROOT/'encoder'; SPEC=json.loads((ROOT/'encoded-model/design.json').read_text())
PROJECT='Encoder'; ROOTID=uid('encoder/root')
FP_R='Resistor_SMD:R_0402_1005Metric'; FP_C='Capacitor_SMD:C_0805_2012Metric'
parts=[]; variables={'TIMING_C':'47n','BYPASS_C':'100n','SUM_R':'1M','DIVIDER_R':'100k','LED_R':'15k','OPAMP':'TLV9044IPWR','RES_TOL':'0.1%','CAP_TOL':'1%','OPAMP_MFR':'Texas Instruments','PASSIVE_MFR':'Select to specification','OPAMP_DATASHEET':'https://www.ti.com/lit/ds/symlink/tlv9044.pdf'}
def val(v):
 for scale,suffix in [(1e6,'M'),(1e3,'k')]:
  if v>=scale:return f'{v/scale:g}'+suffix
 return f'{v:g}'
def part(ref,symbol,value,fp,pins,rating,variable=None):
 if ref.startswith('R'):
  numeric=float(value.rstrip('kM'))*(1e6 if value.endswith('M') else 1e3 if value.endswith('k') else 1)
  package='0402_1005' if numeric<=1e6 else '0603_1608' if numeric<=2e6 else '0805_2012'
  fp='Resistor_SMD:R_'+package+'Metric';rating='0.1%, '+package[:4]+'; exact MPN unverified'
 p=dict(ref=ref,symbol=symbol,value=value,footprint='Encoder:'+fp.split(':')[1],source_footprint=fp,pins={str(k):v for k,v in pins.items()},rating=rating)
 p['value_expression']='${'+variable+'}' if variable else value
 if ref.startswith('U'):p.update(manufacturer='Texas Instruments',mpn='TLV9044IPWR',datasheet=variables['OPAMP_DATASHEET'])
 elif ref=='BT1':p.update(manufacturer='Keystone',mpn='1058',datasheet='')
 else:p.update(manufacturer='Select to specification',mpn='Select to specification',datasheet='')
 parts.append(p);return p
variables['ENCODER_OPAMP_MPN']=variables['OPAMP']
for j in range(1,4):part(f'U{j}','TLV9044',variables['OPAMP'],SPEC['footprint'],{'4':'VBAT','11':'GND'},'1.2–5.5 V RRIO quad op amp', 'ENCODER_OPAMP_MPN')
for s in SPEC['stages']:
 i=s['index']+1; u=next(p for p in parts if p['ref']==s['package'])
 u['pins'].update({str(s['pins'][k]):s[n] for k,n in [('out','output'),('minus','timing_node'),('plus','threshold_node')]})
 mappings=[('R_timing_ohm',s['previous_output'],s['timing_node']),('R_vbat_ohm','VBAT',s['threshold_node']),('R_feedback_ohm',s['threshold_node'],s['output']),('R_gnd_ohm',s['threshold_node'],'GND')]
 for k,(name,a,b) in enumerate(mappings):
  ref=f'R{4*i-3+k}';variables[ref+'_VALUE']=val(s['resistors'][name]);part(ref,'Device:R',variables[ref+'_VALUE'],FP_R,{'1':a,'2':b},'0.1%, 0402; exact MPN unverified',ref+'_VALUE')
 part(f'C{i}','Device:C','47n',FP_C,{'1':s['timing_node'],'2':s['capacitor_bottom']},'47 nF, C0G, 1%, 0805; exact MPN unverified','TIMING_C')
for i,s in enumerate(SPEC['stages']):part(f'R{45+i}','Device:R','1M',FP_R,{'1':s['output'],'2':'MAJORITY_SUM'},'0.1%, 0402','SUM_R')
part('R56','Device:R','100k',FP_R,{'1':'VBAT','2':'MIDREF'},'0.1%, 0402','DIVIDER_R');part('R57','Device:R','100k',FP_R,{'1':'MIDREF','2':'GND'},'0.1%, 0402','DIVIDER_R')
part('R58','Device:R','15k',FP_R,{'1':'ENCODED_OUT','2':'RED_A'},'0.1%, 0402','LED_R');part('R59','Device:R','15k',FP_R,{'1':'VBAT','2':'GREEN_A'},'0.1%, 0402','LED_R')
part('D1','Device:LED','RED','LED_SMD:LED_0603_1608Metric',{'1':'GND','2':'RED_A'},'Low-current red; generic SPICE model, exact MPN unverified')
part('D2','Device:LED','GREEN','LED_SMD:LED_0603_1608Metric',{'1':'ENCODED_OUT','2':'GREEN_A'},'Low-Vf yellow-green; generic SPICE model, exact MPN unverified')
part('BT1','Device:Battery_Cell','CR2032','Battery:BatteryHolder_Keystone_1058_1x2032',{'1':'VBAT','2':'GND'},'One CR2032 coin cell, 3 V nominal; holder only')
for i in range(12,15):part(f'C{i}','Device:C','100n','Capacitor_SMD:C_0603_1608Metric',{'1':'VBAT','2':'GND'},'10 V, X7R, 0603; exact MPN unverified','BYPASS_C')
next(p for p in parts if p['ref']=='U3')['pins'].update({'12':'MAJORITY_SUM','13':'MIDREF','14':'ENCODED_OUT'})
def native_net(net):
 if net=='ENCODED_OUT':return net
 if net.endswith(('_TIMING','_TH')):
  index=int(net[2:4]);return '/bank'+str((index-1)//4+1)+'/'+net
 if net in ['MAJORITY_SUM','MIDREF','RED_A','GREEN_A']:return '/decoder/'+net
 return '/'+net
for p in parts:
 p['logical_pins']=p['pins'].copy();p['pins']={k:native_net(v) for k,v in p['pins'].items()}
write(OUT/'design-intent.json',json.dumps({'schema':'kero.encoder-cad/v1','project':PROJECT,'source_spec_sha256':hashlib.sha256((ROOT/'encoded-model/design.json').read_bytes()).hexdigest(),'parts':parts,'variables':variables},indent=2)+'\n')

libs={key:sym(*key.split(':')) for key in ['Device:R','Device:C','Device:LED','Device:Battery_Cell','power:PWR_FLAG']}
n=sym('Amplifier_Operational','LMV324');old=n[1];n[1]=Q('TLV9044')
for sub in kids(n,'symbol'):sub[1]=Q('TLV9044' + sub[1][len(old):])
for k,v in [('Value','TLV9044IPWR'),('Datasheet',variables['OPAMP_DATASHEET']),('Description','TLV9044 quad RRIO low-power op amp; standard TSSOP-14 pin map')]:next(p for p in kids(n,'property') if p[1]==k)[2]=Q(v)
libs['TLV9044']=n
write(OUT/'Encoder.kicad_sym',dump(['kicad_symbol_lib',['version',20241209],['generator',Q('eeschema')]]+list(libs.values()))+'\n')
write(OUT/'sym-lib-table','(sym_lib_table (version 7) (lib (name "Encoder") (type "KiCad") (uri "${KIPRJMOD}/Encoder.kicad_sym") (options "") (descr "Portable encoder symbols")))\n')
propath=OUT/'Encoder.kicad_pro'
pro=json.loads(propath.read_text()) if propath.exists() else {'meta':{'filename':'Encoder.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_clearance':0.15,'min_track_width':0.15,'min_via_diameter':0.6,'min_through_hole_diameter':0.3,'min_copper_edge_clearance':0.3}}}}
pro.setdefault('text_variables',{}).update(variables)
classes=pro.setdefault('net_settings',{}).setdefault('classes',[])
default=next((c for c in classes if c.get('name')=='Default'),None)
if default is None:default={'name':'Default'};classes.append(default)
default.update(clearance=0.15,track_width=0.15,via_diameter=0.6,via_drill=0.3,microvia_diameter=0.3,microvia_drill=0.1,wire_width=6,bus_width=12)
write(propath,json.dumps(pro,indent=2)+'\n')
def effects(size=1.27,justify=None):
 n=['effects',['font',['size',size,size]]]
 if justify:n.append(['justify',*justify])
 return n
def prop(k,v,x,y,hidden=False):
 n=['property',Q(k),Q(v),['at',x,y,0],effects()]
 if hidden:one(n,'effects').append(['hide','yes'])
 return n
class Sheet:
 def __init__(self,name,title):
  self.name=name;self.id=ROOTID if name=='Encoder' else uid('encoder/'+name);self.path='/'+ROOTID+('' if name=='Encoder' else '/'+self.id)
  cache=copy.deepcopy(list(libs.values()))
  for n in cache:n[1]=Q('Encoder:'+n[1])
  self.n=['kicad_sch',['version',20250114],['generator',Q('eeschema')],['uuid',Q(self.id)],['paper',Q('A3' if name.startswith('bank') else 'A4')],['title_block',['title',Q(title)],['date',Q('2026-11-07')],['rev',Q('candidate')]],['lib_symbols',*cache]];self.serial=0
 def unique(self,key):self.serial+=1;return Q(uid(self.name+'/'+key+'/'+str(self.serial)))
 def wire(self,*pts):
  for a,b in zip(pts,pts[1:]):
   a=tuple(round(v,4) for v in a);b=tuple(round(v,4) for v in b)
   assert a[0]==b[0] or a[1]==b[1],(a,b)
   self.n.append(['wire',['pts',['xy',*a],['xy',*b]],['stroke',['width',0],['type','default']],['uuid',self.unique('wire')]])
 def label(self,name,xy,kind='label',shape='bidirectional'):
  n=[kind,Q(name),['at',*xy,0]]
  if kind=='hierarchical_label':n.append(['shape',shape])
  n.extend([effects(justify=['left','bottom']),['uuid',self.unique('label')]])
  self.n.append(n)
 def dot(self,xy):self.n.append(['junction',['at',*xy],['diameter',0],['color',0,0,0,0],['uuid',self.unique('junction')]])
 def note(self,text,x,y,size=1.27):self.n.append(['text',Q(text),['at',x,y,0],effects(size),['uuid',self.unique('text')]])
 def place(self,ref,x,y,a=0,unit=1):
  p=next(p for p in parts if p['ref']==ref);lib=libs[p['symbol']];name=lib[1]
  positions=(x,y-7.62,x,y+7.62) if ref.startswith('U') else (x+7.62,y-1.27,x+7.62,y+1.27)
  if a==90:positions=(x,y-6.35,x,y-3.81)
  rx,ry,vx,vy=positions
  n=['symbol',['lib_id',Q('Encoder:'+name)],['at',x,y,a],['unit',unit],['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',Q(uid('encoder/'+ref+'/'+str(unit)))],prop('Reference',ref,rx,ry),prop('Value',p['value_expression'],vx,vy),prop('Footprint',p['footprint'],x,y,True),prop('Datasheet',p['datasheet'],x,y,True),prop('Manufacturer','${OPAMP_MFR}' if ref.startswith('U') else p['manufacturer'],x,y,True),prop('MPN','${ENCODER_OPAMP_MPN}' if ref.startswith('U') else p['mpn'],x,y,True),prop('Rating',p['rating'],x,y,True),['instances',['project',Q(PROJECT),['path',Q(self.path),['reference',Q(ref)],['unit',unit]]]]]
  if a==90:
   for field in kids(n,'property'):
    if field[1] in ['Reference','Value']:one(field,'at')[3]=90
  self.n.append(n)
  pins={}
  for sub in kids(lib,'symbol'):
   if int(sub[1].rsplit('_',2)[1]) not in (0,unit):continue
   for pin in kids(sub,'pin'):
    at=one(pin,'at');dx=float(at[1]);dy=-float(at[2]);rad=math.radians(-a)
    pins[str(one(pin,'number')[1])]=(round(x+dx*math.cos(rad)-dy*math.sin(rad),4),round(y+dx*math.sin(rad)+dy*math.cos(rad),4))
  return pins
 def save(self):write(OUT/(self.name+'.kicad_sch'),dump(self.n)+'\n')
def stub(sheet,net,pin,direction='left'):
 x,y=pin;end=(x-25.4,y) if direction=='left' else (x+5.08,y);sheet.wire(pin,end);sheet.label(net,end)
 if direction=='left':one(one(sheet.n[-1],'effects'),'justify')[1:]=['right','bottom']
def stage(sheet,s,x,y):
 i=s['index']+1;r=4*i-3
 u=sheet.place(s['package'],x,y,unit=s['unit']);a=u[str(s['pins']['plus'])];b=u[str(s['pins']['minus'])];o=u[str(s['pins']['out'])]
 rt=sheet.place(f'R{r}',x-43.18,y+2.54,90);rv=sheet.place(f'R{r+1}',x-38.1,y-20.32,90);rf=sheet.place(f'R{r+2}',x+2.54,y-20.32,90);rg=sheet.place(f'R{r+3}',x-22.86,y-35.56,180);c=sheet.place(f'C{i}',x-22.86,y+20.32)
 th=(x-22.86,y-20.32);tn=(x-22.86,y+2.54);out=(x+20.32,y)
 # R1 points left-to-right after rotation: native R pin1 is left.
 stub(sheet,s['previous_output'],rt['1']);sheet.wire(rt['2'],tn,b);sheet.dot(tn);sheet.label(s['timing_node'],tn)
 sheet.wire(tn,c['1']);sheet.wire(c['2'],(c['2'][0],y+30.48));sheet.label(s['capacitor_bottom'],(c['2'][0],y+30.48))
 stub(sheet,'VBAT',rv['1']);sheet.wire(rv['2'],th,rf['1']);sheet.dot(th);sheet.wire(th,(th[0],a[1]),a);sheet.label(s['threshold_node'],th)
 sheet.wire(rg['1'],th);sheet.wire(rg['2'],(rg['2'][0],y-43.18));sheet.label('GND',(rg['2'][0],y-43.18))
 sheet.wire(rf['2'],(out[0],rf['2'][1]),out,o);sheet.dot(out);stub(sheet,s['output'],out,'right')
 sheet.note(s['id']+' - '+s['amplifier'],x,y-49.53,1.65)

def bank(name,stages):
 sh=Sheet(name,'RC delay bank: '+stages[0]['id']+'–'+stages[-1]['id'])
 for i,s in enumerate(stages):stage(sh,s,109.22+(i%2)*170.18,93.98+(i//2)*109.22)
 # Hierarchical interfaces are wired to local functional labels.
 names=['VBAT','GND',stages[0]['previous_output']]+[s['output'] for s in stages]
 for i,net in enumerate(names):sh.label(net,(12.7,30.48+i*5.08),'hierarchical_label');sh.wire((12.7,30.48+i*5.08),(25.4,30.48+i*5.08));sh.label(net,(25.4,30.48+i*5.08))
 sh.note('Timing R/C and three threshold resistors program both edge delays.\nAlternating capacitor bottom rails preload startup; all stage outputs feed the majority decoder.',210,20.32)
 sh.save();return sh,names

def power():
 sh=Sheet('power','CR2032 power and quad-op-amp bypass');pins=sh.place('BT1',38.1,63.5)
 for pin,net,y in [('1','VBAT',40.64),('2','GND',88.9)]:sh.wire(pins[pin],(38.1,y),(63.5,y));sh.label(net,(63.5,y),'hierarchical_label')
 for j,x in enumerate([91.44,149.86,208.28],1):
  u=sh.place(f'U{j}',x,63.5,unit=5);c=sh.place(f'C{j+11}',x+22.86,63.5)
  for net,pin,cpin,y in [('VBAT','4','1',40.64),('GND','11','2',88.9)]:sh.wire(u[pin],(u[pin][0],y),(c[cpin][0],y),c[cpin]);sh.label(net,(u[pin][0],y))
 # Power flags assert the battery supplies these low-energy nets.
 for i,(net,y) in enumerate([('VBAT',111.76),('GND',127)]):
  lib=libs['power:PWR_FLAG'];ref=f'#FLG0{i+1}';sh.n.append(['symbol',['lib_id',Q('Encoder:'+lib[1])],['at',38.1,y,0],['unit',1],['in_bom','no'],['on_board','no'],['dnp','no'],['uuid',sh.unique('flag')],prop('Reference',ref,38.1,y,True),prop('Value','PWR_FLAG',38.1,y,True),['instances',['project',Q(PROJECT),['path',Q(sh.path),['reference',Q(ref)],['unit',1]]]]]);sh.wire((38.1,y),(63.5,y));sh.label(net,(63.5,y))
 sh.note('One CR2032: 3 V nominal, evaluated at 2.5–3.3 V.\nRemove cell to switch off. No reverse-cell protection.\nDo not short the cell. Ideal supply model omits cell ESR and capacity effects.',139.7,149.86)
 sh.save();return sh,['VBAT','GND']

def decoder():
 sh=Sheet('decoder','Eleven-input majority decoder and alternating LEDs')
 for i,s in enumerate(SPEC['stages']):
  y=35.56+i*10.16;r=sh.place(f'R{45+i}',76.2,y,90);sh.label(s['output'],(35.56,y),'hierarchical_label');sh.wire((35.56,y),r['1']);sh.wire(r['2'],(101.6,y))
 sh.wire(*[(101.6,35.56+i*10.16) for i in range(11)])
 for i in range(1,10):sh.dot((101.6,35.56+i*10.16))
 u=sh.place('U3',154.94,76.2,unit=4);sh.wire((101.6,73.66),u['12']);sh.dot((101.6,73.66));sh.label('MAJORITY_SUM',(114.3,73.66))
 a=sh.place('R56',129.54,101.6);b=sh.place('R57',129.54,124.46)
 sh.wire(a['2'],(129.54,114.3),b['1']);sh.dot((129.54,114.3));sh.wire((129.54,114.3),(139.7,114.3),(139.7,78.74),u['13']);sh.label('MIDREF',(132.08,114.3))
 sh.wire(a['1'],(129.54,88.9));sh.label('VBAT',(129.54,88.9));sh.wire(b['2'],(129.54,139.7));sh.label('GND',(129.54,139.7))
 out=(185.42,76.2);sh.wire(u['14'],out,(215.9,76.2));sh.dot(out);sh.label('ENCODED_OUT',out,'global_label')
 r=sh.place('R58',185.42,96.52);d=sh.place('D1',185.42,116.84,90);sh.wire(out,r['1']);sh.wire(r['2'],d['2']);stub(sh,'GND',d['1']);sh.label('RED_A',(185.42,106.68))
 r=sh.place('R59',215.9,43.18);d=sh.place('D2',215.9,63.5,90);stub(sh,'VBAT',r['1']);sh.wire(r['2'],d['2']);sh.wire(d['1'],(215.9,76.2));sh.label('GREEN_A',(215.9,53.34))
 for i,net in enumerate(['VBAT','GND']):sh.label(net,(167.64+i*25.4,152.4),'hierarchical_label');sh.wire((167.64+i*25.4,152.4),(167.64+i*25.4,144.78));sh.label(net,(167.64+i*25.4,144.78))
 sh.note('RED = encoded output HIGH; GREEN = LOW.\n11 equal resistors sum the delay-ring states.\nU3D compares with VBAT/2. Custom PWM alphabet.\nElectrical/visible output; no radio.',101.6,172.72)
 sh.save();return sh,['VBAT','GND']+[s['output'] for s in SPEC['stages']]

def main():
 blocks=[power(),bank('bank1',SPEC['stages'][:4]),bank('bank2',SPEC['stages'][4:8]),bank('bank3',SPEC['stages'][8:]),decoder()]
 root=Sheet('Encoder','KERO: RC-programmed hello world transmitter')
 for (sh,names),(x,y,w,h) in zip(blocks,[(20.32,48.26,55.88,30.48),(101.6,48.26,55.88,45.72),(190.5,48.26,55.88,45.72),(20.32,106.68,55.88,50.8),(119.38,106.68,104.14,50.8)]):
  n=['sheet',['at',x,y],['size',w,h],['stroke',['width',0],['type','default']],['fill',['color',0,0,0,0]],['uuid',Q(sh.id)],prop('Sheetname',sh.name,x,y-2.54),prop('Sheetfile',sh.name+'.kicad_sch',x,y+h+2.54)]
  for i,net in enumerate(names):
   yy=round(y+5.08+i*3.81,4);xx=x+w;n.append(['pin',Q(net),'bidirectional',['at',xx,yy,0],effects(1.016),['uuid',root.unique('sheetpin')]]);root.wire((xx,yy),(xx+7.62,yy));root.label(net,(xx+7.62,yy),'global_label' if net=='ENCODED_OUT' else 'label')
  n.append(['instances',['project',Q(PROJECT),['path',Q('/'+ROOTID),['page',Q(str(blocks.index((sh,names))+2))]]]])
  root.n.append(n)
  descriptions={'power':'CR2032 cell\nU1–U3 supplies / bypass','bank1':'ST01–ST04 / U1A–U1D','bank2':'ST05–ST08 / U2A–U2D','bank3':'ST09–ST11 / U3A–U3C','decoder':'11 × 1 MΩ weighted sum\nU3D majority comparator\nRED / GREEN indication'}
  root.note(descriptions[sh.name],x+w*.4,y+h+7.62,1.27)
 root.note('RC-programmed repeating "hello world"',139.7,22.86,2.54)
 root.note('11 inverting Schmitt delay stages form an odd ring. Equal-weight majority decoding yields 11 PWM symbols.\nShared project variables define nominal values and common metadata; exact passive MPN selection remains open.\nSingle CR2032 powers three TLV9044 quad op amps. Simulation evidence: ../encoded-model/spice/.',139.7,32.258,1.27)
 root.save()
def validate():
 evidence=OUT/'evidence';evidence.mkdir(exist_ok=True);scratch=OUT/'.scratch';scratch.mkdir(exist_ok=True)
 cli=Path(r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe');env=os.environ.copy();env.update(TEMP=str(scratch),TMP=str(scratch))
 inputs=[p for p in OUT.iterdir() if p.suffix in ['.kicad_sch','.kicad_pro','.kicad_sym']]+[Path(__file__)]
 hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 commands=[]
 for args in [['sch','export','netlist','--format','kicadxml','-o','evidence/netlist.xml','Encoder.kicad_sch'],['sch','erc','--format','json','--severity-all','-o','evidence/erc.json','Encoder.kicad_sch'],['sch','export','svg','-o','previews/','Encoder.kicad_sch']]:
  r=subprocess.run([str(cli),*args],cwd=OUT,env=env,capture_output=True,text=True,check=True);commands.append({'args':args,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 erc=json.loads((evidence/'erc.json').read_text());violations=[v for s in erc['sheets'] for v in s['violations']]
 assert not violations,violations
 xml=ET.parse(evidence/'netlist.xml');actual={}
 for net in xml.findall('./nets/net'):
  for node in net.findall('node'):actual[(node.get('ref'),node.get('pin'))]=net.get('name')
 expected={(p['ref'],pin):net for p in parts for pin,net in p['pins'].items()}
 assert {k:v for k,v in actual.items() if not k[0].startswith('#')}==expected,[(k,expected.get(k),actual.get(k)) for k in expected if expected[k]!=actual.get(k)]
 comps={c.get('ref'):c for c in xml.findall('./components/comp')}
 for p in parts:
  c=comps[p['ref']];assert c.findtext('value')==p['value'],(p['ref'],c.findtext('value'),p['value'])
  assert c.findtext('footprint')==p['footprint']
  props={f.get('name'):f.get('value') for f in c.findall('property')}
  for key,name in [('Manufacturer','manufacturer'),('MPN','mpn')]:assert props[key]==p[name],(p['ref'],key,props[key],p[name])
 assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'Source changed during validation'
 with (OUT/'bom.csv').open('w',encoding='utf-8',newline='') as f:
  w=csv.writer(f);w.writerow(['Reference','Quantity','Value','Footprint','Manufacturer','MPN','Rating','Datasheet'])
  for p in parts:w.writerow([p['ref'],1,p['value'],p['footprint'],p['manufacturer'],p['mpn'],p['rating'],p['datasheet']])
 receipt={'schema':'kero.encoder-schematic-validation/v1','kicad_version':subprocess.check_output([str(cli),'version'],text=True).strip(),'source_sha256':hashes,'native_erc_violations':len(violations),'parts':len(parts),'named_terminal_assignments':len(expected),'native_pin_net_equivalence':True,'native_value_footprint_manufacturer_mpn_equivalence':True,'sheets':len(erc['sheets']),'commands':commands,'limitations':['Circuit behavior is supported by sibling encoded-model/spice evidence, not by ERC.','Exact passive and LED MPNs remain unverified.','No PCB DRC or manufacturing acceptance is implied by this schematic receipt.']}
 write(evidence/'schematic-validation.json',json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['native_erc_violations','parts','named_terminal_assignments','sheets']}))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--validate',action='store_true');args=parser.parse_args();main()
 if args.validate:validate()
