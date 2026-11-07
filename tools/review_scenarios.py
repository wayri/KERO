"""Incremental review-demo ECOs. Run in the matching KERO branch checkout."""
import argparse,copy,csv,json,hashlib,re
import pcbnew as pcb
from build_demo import ROOT,LIB,Q,uid,parse,dump,kids,one,write,sym
from layout import route,stable_fields,V

def field(n,name,value):
 p=next((x for x in kids(n,'property') if x[1]==name),None)
 if p is None:p=['property',Q(name),Q(value),['at',0,0,0],['effects',['font',['size',1.27,1.27]],['hide','yes']]];n.append(p)
 else:p[2]=Q(value)

def meta(p):
 return {'Manufacturer':p.get('manufacturer','Texas Instruments' if p['ref']=='U1' else 'Keystone' if p['ref']=='BT1' else 'Generic'),'MPN':p.get('mpn','LMV358ADR' if p['ref']=='U1' else '1058' if p['ref']=='BT1' else 'Select to specification'),'Rating':p['rating'],'Datasheet':p.get('datasheet','https://www.ti.com/lit/ds/symlink/lmv358a.pdf' if p['ref']=='U1' else '')}

def board_fields(f,p):
 f.SetValue(p['value'])
 for name,value in meta(p).items():
  target=f.GetField(name)
  if target is None:
   target=pcb.PCB_FIELD(f,pcb.FIELD_T_USER);target.SetName(name);target.SetText(value);target.SetVisible(False);f.Add(target)
  else:target.SetText(value)

def local_footprint(fp):
 lib,name=fp.split(':');n=parse((LIB/'footprints'/f'{lib}.pretty'/f'{name}.kicad_mod').read_text(encoding='utf-8'))
 for m in kids(n,'model'):
  source=LIB/'3dmodels'/m[1].split('}/',1)[1];target=ROOT/'models'/source.name
  if not target.exists():write(target,source.read_text(encoding='utf-8'))
  m[1]=Q('${KIPRJMOD}/models/'+source.name)
 assert kids(n,'model'),fp
 write(ROOT/'Demo.pretty'/f'{name}.kicad_mod',dump(n)+'\n')
 return name

def add_board_part(board,p):
 name=local_footprint(p['footprint']);f=pcb.FootprintLoad(str(ROOT/'Demo.pretty'),name);f.SetReference(p['ref']);f.SetFPID(pcb.LIB_ID('Demo',name));f.SetUuid(pcb.KIID(uid('pcb'+p['ref'])));f.SetPath(pcb.KIID_PATH('/'+uid('root')+'/'+uid(p['ref'])));x,y,a=p['pcb'];f.SetPosition(V(x,y));f.SetOrientationDegrees(a)
 for pad in f.Pads():pad.SetNet(board.FindNet('/'+p['pins'][pad.GetNumber()]));pad.SetUuid(pcb.KIID(uid(p['ref']+'-pad-'+pad.GetNumber())))
 board_fields(f,p)
 f.Reference().SetTextSize(V(1,1));f.Reference().SetTextThickness(pcb.FromMM(.15));f.Reference().SetPosition(V(x+3.81,y) if p['ref']=='TP1' else V(x,y-3));f.Value().SetVisible(False)
 for i,g in enumerate(f.GraphicalItems()):g.SetUuid(pcb.KIID(uid(p['ref']+'-graphic-'+str(i))))
 stable_fields(f);board.Add(f)


def save_bom(intent):
 with (ROOT/'bom.csv').open('w',encoding='utf-8',newline='') as out:
  w=csv.writer(out,lineterminator='\n');w.writerow(['Reference','Quantity','Value','Footprint','Manufacturer','MPN','Rating','Datasheet'])
  for p in intent['parts']:
   m=meta(p);w.writerow([p['ref'],1,p['value'],'Demo:'+p['footprint'].split(':')[1],m['Manufacturer'],m['MPN'],m['Rating'],m['Datasheet']])
 write(ROOT/'design-intent.json',json.dumps(intent,indent=2)+'\n')


def native_tree(raw):
 stack=[];root=None
 for match in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',raw):
  t=match[0]
  if t=='(':
   node={'items':[],'start':match.start()}
   if stack:stack[-1]['items'].append(node)
   else:root=node
   stack.append(node)
  elif t==')':stack.pop()['end']=match.end()
  else:stack[-1]['items'].append({'value':json.loads(t) if t.startswith('"') else t,'start':match.start(),'end':match.end()})
 return root

def node_children(n,kind):return [x for x in n['items'] if 'items' in x and x['items'][0].get('value')==kind]
def footprint_blocks(raw):
 result={}
 for fp in node_children(native_tree(raw),'footprint'):
  ref=next(x['items'][2]['value'] for x in node_children(fp,'property') if x['items'][1]['value']=='Reference')
  result[ref]=fp
 return result

def targeted_properties(raw,updates):
 # Keep every unselected native byte, including hidden-field styling and UUIDs.
 edits=[]
 for ref,fp in footprint_blocks(raw).items():
  if ref not in updates:continue
  found=set()
  for prop in node_children(fp,'property'):
   key=prop['items'][1]['value']
   if key in updates[ref]:
    token=prop['items'][2];edits.append((token['start'],token['end'],json.dumps(updates[ref][key])));found.add(key)
  assert found==set(updates[ref]),(ref,found,updates[ref])
 for start,end,replacement in sorted(edits,reverse=True):raw=raw[:start]+replacement+raw[end:]
 return raw

def preserve_unchanged_footprints(after,before):
 previous=footprint_blocks(before);edits=[]
 for ref,fp in footprint_blocks(after).items():
  if ref in previous:
   old=previous[ref];edits.append((fp['start'],fp['end'],before[old['start']:old['end']]))
 for start,end,replacement in sorted(edits,reverse=True):after=after[:start]+replacement+after[end:]
 return after

def main():
 ap=argparse.ArgumentParser();ap.add_argument('scenario',choices=['bom-values','bom-mpn','add-testpoint','film-capacitor']);args=ap.parse_args()
 project_before=(ROOT/'KERO.kicad_pro').read_text()
 intent=json.loads((ROOT/'design-intent.json').read_text());sch=parse((ROOT/'KERO.kicad_sch').read_text());raw_board=(ROOT/'KERO.kicad_pcb').read_text();board=pcb.LoadBoard(str(ROOT/'KERO.kicad_pcb'));reroute=False;updates={};connections=[]
 if args.scenario in ['bom-values','bom-mpn']:
  for p in intent['parts']:
   if p['ref'] not in ['R6','R7']:continue
   if args.scenario=='bom-values':p['value']='4.7k'
   else:p.update(manufacturer='Vishay',mpn='CRCW06034K70FKEA',datasheet='https://www.vishay.com/docs/20035/dcrcwe3.pdf',rating='4.7 kohm, 1%, >=0.1 W, 0603, thick film')
   for n in kids(sch,'symbol'):
    if next(x[2] for x in kids(n,'property') if x[1]=='Reference')==p['ref']:
     field(n,'Value',p['value'])
     for name,val in meta(p).items():field(n,name,val)
   updates[p['ref']]={'Value':p['value'],**meta(p)}
 elif args.scenario=='add-testpoint':
  assert not any(p['ref']=='TP1' for p in intent['parts'])
  p={'ref':'TP1','symbol':'Connector:TestPoint','value':'OUT','footprint':'TestPoint:TestPoint_Loop_D2.50mm_Drill1.0mm','sch':[175.26,73.66,0],'pcb':[106.68,78.74,0],'pins':{'1':'OUT'},'manufacturer':'Generic','mpn':'Select to specification','rating':'2.5 mm loop test point, 1.0 mm drill; OUT probe access'}
  definition=sym('Connector','TestPoint');lib=parse((ROOT/'Demo.kicad_sym').read_text());lib.append(copy.deepcopy(definition));write(ROOT/'Demo.kicad_sym',dump(lib)+'\n');definition[1]=Q('Demo:'+definition[1]);one(sch,'lib_symbols').append(definition)
  n=copy.deepcopy(next(n for n in kids(sch,'symbol') if next(p[2] for p in kids(n,'property') if p[1]=='Reference')=='C1'))
  one(n,'lib_id')[1]=Q('Demo:Connector_TestPoint');one(n,'at')[1:]=p['sch'];one(n,'uuid')[1]=Q(uid('TP1'));field(n,'Reference','TP1');field(n,'Value','OUT');field(n,'Footprint','Demo:'+p['footprint'].split(':')[1])
  for name,val in meta(p).items():field(n,name,val)
  for prop in kids(n,'property'):
   one(prop,'at')[1:]=[180.34,72.39 if prop[1]=='Reference' else 74.93,0]
  inst=one(one(n,'instances'),'project');one(one(inst,'path'),'reference')[1]=Q('TP1');sch.append(n)
  pin=next(pin for sub in kids(definition,'symbol') for pin in kids(sub,'pin'));at=one(pin,'at');px,py=175.26+float(at[1]),73.66-float(at[2]);sch.append(['wire',['pts',['xy',px,py],['xy',175.26,81.28]],['stroke',['width',0.2032],['type','default']],['uuid',Q(uid('tp1-wire'))]])
  
  for label in kids(sch,'label'):
   if label[1]=='OUT':one(label,'at')[1]=180.34
  sch.append(['junction',['at',175.26,81.28],['diameter',0.9144],['color',0,0,0,0],['uuid',Q(uid('tp1-junction'))]])
  intent['parts'].append(p);add_board_part(board,p);connections=[('/OUT',(106.68,78.74),(104.14,88.9))];reroute=True
 elif args.scenario=='film-capacitor':
  old=next(p for p in intent['parts'] if p['ref']=='C1');p=copy.deepcopy(old);p.update(ref='C3',footprint='Capacitor_THT:C_Rect_L7.2mm_W4.5mm_P5.00mm',pcb=[87.95,77.47,0],rating='1 uF, >=16 V, +/-10%, film, radial P5 mm; verify body height')
  intent['parts'].remove(old);intent['parts'].append(p);board.Delete(board.FindFootprintByReference('C1'));add_board_part(board,p);connections=[('/GND',(92.95,77.47),(89.85,77.47))]
  n=next(n for n in kids(sch,'symbol') if next(p[2] for p in kids(n,'property') if p[1]=='Reference')=='C1');one(n,'uuid')[1]=Q(uid('C3'));field(n,'Reference','C3');field(n,'Footprint','Demo:'+p['footprint'].split(':')[1]);field(n,'Rating',p['rating']);inst=one(one(n,'instances'),'project');one(one(inst,'path'),'reference')[1]=Q('C3')
  for note in kids(sch,'text'):
   if 'R1 / C1' in note[1]:note[1]=Q(note[1].replace('R1 / C1','R1 / C3'))
  reroute=True
 if reroute:
  route(board,connections)
 if updates:write(ROOT/'KERO.kicad_pcb',targeted_properties(raw_board,updates))
 else:board.BuildConnectivity();pcb.SaveBoard(str(ROOT/'KERO.kicad_pcb'),board)
 # Keep native serialized files portable and avoid newline-only Git changes.
 saved=(ROOT/'KERO.kicad_pcb').read_text()
 if reroute:saved=preserve_unchanged_footprints(saved,raw_board)
 write(ROOT/'KERO.kicad_pcb',saved)
 write(ROOT/'KERO.kicad_sch',dump(sch)+'\n');intent['review_scenario']=args.scenario;save_bom(intent)
 del board
 write(ROOT/'KERO.kicad_pro',project_before)
 print('Applied',args.scenario)
if __name__=='__main__':main()
