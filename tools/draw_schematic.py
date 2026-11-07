"""Readable native schematic presentation; electrical pin/net assignments stay unchanged."""
import copy,math
from build_demo import ROOT,Q,uid,sym,kids,one,dump,write
POSITIONS={'U1':(144.78,81.28,0),'R1':(144.78,106.68,90),'R2':(144.78,55.88,90),'R3':(113.03,55.88,90),'R4':(66.04,66.04,0),'R5':(66.04,88.9,0),'C1':(116.84,102.87,0),'C2':(30.48,110.49,0),'BT1':(30.48,66.04,0),'R6':(190.5,91.44,0),'D1':(190.5,106.68,90),'R7':(218.44,63.5,0),'D2':(218.44,76.2,90)}
def schematic(ps,variant):
 for p in ps:p['sch']=POSITIONS[p['ref']]
 libs={p['symbol']:sym(*p['symbol'].split(':')) for p in ps};libs['power:PWR_FLAG']=sym('power','PWR_FLAG')
 n=libs['Amplifier_Operational:LMV358']
 for k,v in [('Value','LMV358ADR'),('Datasheet','https://www.ti.com/lit/ds/symlink/lmv358a.pdf'),('Description','LMV358A dual low-voltage op amp; verified SOIC-8 pin map')]:next(x for x in kids(n,'property') if x[1]==k)[2]=Q(v)
 write(ROOT/'Demo.kicad_sym',dump(['kicad_symbol_lib',['version',20241209],['generator',Q('eeschema')]]+list(libs.values()))+'\n')
 cache=copy.deepcopy(list(libs.values()))
 for n in cache:n[1]=Q('Demo:'+n[1])
 sch=['kicad_sch',['version',20250114],['generator',Q('eeschema')],['uuid',Q(uid('root'))],['paper',Q('A4')],['title_block',['title',Q('KERO - coin-cell red / green relaxation oscillator')],['date',Q('2026-11-07')],['rev',Q(variant)]],['lib_symbols']+cache]
 def eff(size=1.27):return ['effects',['font',['size',size,size]]]
 def prop(k,v,x,y,angle=0,hidden=False):
  e=eff()
  if hidden:e.append(['hide','yes'])
  return ['property',Q(k),Q(v),['at',x,y,angle],e]
 def place(p,x,y,a=0,unit=1):
  ref=p['ref'];rx,ry,vx,vy=(x,y-7.62,x,y+7.62) if ref=='U1' else (x+6.35,y-1.27,x+6.35,y+1.27)
  if ref=='R5':rx,ry,vx,vy=x-6.35,y-1.27,x-6.35,y+1.27
  if ref=='U1' and unit==3:rx,ry,vx,vy=x+7.62,y-1.27,x+7.62,y+1.27
  if a==90 and ref.startswith('R'):rx,ry,vx,vy=x,y-5.08,x,y-2.54
  n=['symbol',['lib_id',Q('Demo:'+p['symbol'].replace(':','_'))],['at',x,y,a],['unit',unit],['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',Q(uid(ref+('' if unit==1 else '-'+str(unit))))],prop('Reference',ref,rx,ry,90 if a==90 else 0),prop('Value',p['value'],vx,vy,90 if a==90 else 0),prop('Footprint','Demo:'+p['footprint'].split(':')[1] if p['footprint'].split(':')[1] else '',x,y,hidden=True),prop('Datasheet','https://www.ti.com/lit/ds/symlink/lmv358a.pdf' if ref=='U1' else '',x,y,hidden=True),prop('Manufacturer','Texas Instruments' if ref=='U1' else 'Keystone' if ref=='BT1' else 'Generic',x,y,hidden=True),prop('MPN','LMV358ADR' if ref=='U1' else '1058' if ref=='BT1' else 'Select to specification',x,y,hidden=True),prop('Rating',p['rating'],x,y,hidden=True),['instances',['project',Q('KERO'),['path',Q('/'+uid('root')),['reference',Q(ref)],['unit',unit]]]]]
  sch.append(n);return n
 for p in ps:place(p,*POSITIONS[p['ref']])
 u=next(p for p in ps if p['ref']=='U1');place(u,86.36,81.28,unit=2);place(u,53.34,110.49,unit=3)
 def path(*pts):
  for a,b in zip(pts,pts[1:]):
   assert a[0]==b[0] or a[1]==b[1],(a,b)
   sch.append(['wire',['pts',['xy',*a],['xy',*b]],['stroke',['width',0.2032],['type','default']],['uuid',Q(uid('wire'+str(a)+str(b)))]])
 def label(name,xy):
  e=eff();e.append(['justify','left','bottom'])
  sch.append(['label',Q(name),['at',*xy,0],e,['uuid',Q(uid('label'+name+str(xy)))]])
 def dot(xy):sch.append(['junction',['at',*xy],['diameter',0.9144],['color',0,0,0,0],['uuid',Q(uid('dot'+str(xy)))]])
 def note(key,s,x,y,size=1.27):sch.append(['text',Q(s),['at',x,y,0],eff(size),['uuid',Q(uid('drawing-note-'+key))]])
 # Visible supply bus: cell -> reference divider -> green LED branch.
 path((30.48,48.26),(53.34,48.26),(66.04,48.26),(218.44,48.26),(218.44,59.69));dot((53.34,48.26));dot((66.04,48.26));label('VBAT',(30.48,48.26))
 battery=next(p for p in ps if p['ref']=='BT1');pins={}
 for sub in kids(libs[battery['symbol']],'symbol'):
  for pin in kids(sub,'pin'):
   at=one(pin,'at');pins[one(pin,'number')[1]]=(30.48+float(at[1]),66.04-float(at[2]))
 path(pins['1'],(30.48,48.26));path(pins['2'],(30.48,88.9),(40.64,88.9));label('GND',(30.48,88.9))
 path((66.04,48.26),(66.04,62.23))
 # U1B reference buffer: a physically drawn divider and unity-gain feedback.
 path((66.04,69.85),(66.04,78.74),(66.04,85.09));dot((66.04,78.74));path((66.04,78.74),(78.74,78.74));label('DIVIDER',(68.58,78.74))
 path((66.04,92.71),(66.04,99.06));label('GND',(66.04,99.06))
 path((93.98,81.28),(101.6,81.28),(101.6,55.88),(109.22,55.88));dot((101.6,81.28));label('VREF',(95.25,81.28))
 path((101.6,81.28),(101.6,101.6),(73.66,101.6),(73.66,83.82),(78.74,83.82))
 # U1A Schmitt feedback: VREF -> R3 -> + input, OUT -> R2 -> + input.
 path((116.84,55.88),(129.54,55.88),(140.97,55.88));dot((129.54,55.88));label('SCHMITT',(119.38,55.88))
 path((129.54,55.88),(129.54,78.74),(137.16,78.74))
 path((148.59,55.88),(165.1,55.88),(165.1,81.28),(165.1,106.68),(148.59,106.68));dot((165.1,81.28))
 # Main output continues directly to both alternating LED current paths.
 path((152.4,81.28),(165.1,81.28),(190.5,81.28),(218.44,81.28));dot((190.5,81.28));label('OUT',(172.72,81.28))
 # RC relaxation path, with an unmistakable capacitor T junction.
 path((140.97,106.68),(129.54,106.68),(129.54,99.06),(129.54,83.82),(137.16,83.82));dot((129.54,99.06))
 path((116.84,99.06),(129.54,99.06));label('TIMING',(119.38,99.06))
 path((116.84,106.68),(116.84,124.46));label('GND',(116.84,124.46))
 # Red: OUT -> resistor -> LED -> GND. Green: VBAT -> resistor -> LED -> OUT.
 path((190.5,81.28),(190.5,87.63));path((190.5,95.25),(190.5,99.06),(190.5,102.87));dot((190.5,99.06));path((190.5,99.06),(198.12,99.06));label('RED_A',(198.12,99.06))
 path((190.5,110.49),(190.5,124.46));label('GND',(190.5,124.46))
 path((218.44,67.31),(218.44,69.85),(218.44,72.39));dot((218.44,69.85));path((218.44,69.85),(226.06,69.85));label('GREEN_A',(226.06,69.85))
 path((218.44,80.01),(218.44,81.28))
 # U1 power unit and its bypass capacitor form one wired group.
 path((30.48,106.68),(30.48,97.79),(50.8,97.79),(50.8,102.87));label('VBAT',(30.48,97.79))
 path((30.48,114.3),(30.48,124.46),(50.8,124.46),(50.8,118.11));label('GND',(30.48,124.46))
 for ref,xy in [('#FLG001',(53.34,48.26)),('#FLG002',(40.64,88.9))]:
  f={'ref':ref,'symbol':'power:PWR_FLAG','value':'PWR_FLAG','footprint':':','rating':''};n=place(f,*xy);one(n,'in_bom')[1]='no';one(n,'on_board')[1]='no'
  for propnode in kids(n,'property'):one(propnode,'effects').append(['hide','yes'])
 for key,title,x in [('power','COIN CELL / POWER',38.1),('ref','REFERENCE BUFFER',85.09),('osc','RELAXATION OSCILLATOR',144.78),('led','ALTERNATING LEDs',204.47)]:note(key,title,x,35.56,1.65)
 note('vref','VREF = VBAT / 4',86.36,111.76)
 rt=470000 if variant=='timing' else 1000000;lo=.25*402/502;hi=lo+100/502;t=rt*1e-6*(math.log((1-lo)/(1-hi))+math.log(hi/lo))
 note('timing',f'Calculated f = {1/t:.2f} Hz\nR1 / C1 set blink speed\nRed duty approximately 29%',144.78,137.16)
 note('red','RED ON\nwhen OUT is HIGH',190.5,137.16)
 note('green','GREEN ON\nwhen OUT is LOW',218.44,102.87)
 note('limits','CR2032: 3 V nominal; design range 2.5-3.3 V.\nRemove cell to switch off; no reverse-cell protection.\nUse a low-Vf yellow-green LED. Bench verification required.',111.76,157.48)
 write(ROOT/'KERO.kicad_sch',dump(sch)+'\n')
