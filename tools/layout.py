import pcbnew as pcb
import math,heapq,json
from build_demo import ROOT,LIB,uid,write,parse,kids,one
V=lambda x,y:pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))
def stable_fields(f):
 for i,field in enumerate(f.GetFields()):field.SetUuidDirect(pcb.KIID(uid(f.GetReference()+'-field-'+str(i)+'-'+field.GetName())))
def build_board(ps,variant):
 b=pcb.BOARD();b.SetCopperLayerCount(2);b.GetDesignSettings().SetCopperLayerCount(2)
 nets={}
 for name in sorted({n for p in ps for n in p['pins'].values()}):
  n=pcb.NETINFO_ITEM(b,'/'+name);b.Add(n);nets[name]=n
 for p in ps:
  f=pcb.FootprintLoad(str(ROOT/'Demo.pretty'),p['footprint'].split(':')[1]);f.SetReference(p['ref']);f.SetValue(p['value']);f.SetFPID(pcb.LIB_ID('Demo',p['footprint'].split(':')[1]));f.SetUuid(pcb.KIID(uid('pcb'+p['ref'])));f.SetPath(pcb.KIID_PATH('/'+uid('root')+'/'+uid(p['ref'])))
  x,y,a=p['pcb'];f.SetPosition(V(x,y));f.SetOrientationDegrees(a)
  if p['ref']=='D2':f.Models()[0].m_Filename='${KIPRJMOD}/models/LED_D5.0mm_green.step'
  if p['ref']=='BT1':
   model=pcb.FP_3DMODEL();model.m_Filename='${KIPRJMOD}/models/CR2032_nominal.wrl';f.Add3DModel(model)
  for pad in f.Pads():pad.SetNet(nets[p['pins'][pad.GetNumber()]]);pad.SetUuid(pcb.KIID(uid(p['ref']+'-pad-'+pad.GetNumber())))
  for i,g in enumerate(f.GraphicalItems()):g.SetUuid(pcb.KIID(uid(p['ref']+'-graphic-'+str(i))))
  f.Reference().SetUuid(pcb.KIID(uid(p['ref']+'-reference')));f.Value().SetUuid(pcb.KIID(uid(p['ref']+'-value')))
  for key,value in [('Manufacturer','Texas Instruments' if p['ref']=='U1' else 'Keystone' if p['ref']=='BT1' else 'Generic'),('MPN','LMV358ADR' if p['ref']=='U1' else '1058' if p['ref']=='BT1' else 'Select to specification'),('Rating',p['rating']),('Datasheet','https://www.ti.com/lit/ds/symlink/lmv358a.pdf' if p['ref']=='U1' else '')]:
   field=pcb.PCB_FIELD(f,pcb.FIELD_T_USER);field.SetUuid(pcb.KIID(uid(p['ref']+'-field-'+key)));field.SetName(key);field.SetText(value);field.SetVisible(False);f.Add(field)
  f.Reference().SetTextSize(V(1,1));f.Reference().SetTextThickness(pcb.FromMM(.15));f.Reference().SetPosition(V(*{'U1':(99.06,67),'R1':(91.44,71.5),'R2':(96.52,62.8),'R3':(91.44,66.6),'R4':(87.63,81.28),'R5':(87.63,85.09),'C1':(88.9,79.4),'C2':(105.41,76.2),'R6':(107.95,66.04),'R7':(104.14,81.5),'D1':(106.68,55.4),'D2':(104.14,94),'BT1':(69.85,60)}[p['ref']]));f.Reference().SetTextAngle(pcb.EDA_ANGLE(0,pcb.DEGREES_T));f.Value().SetVisible(False);stable_fields(f);b.Add(f)
 for i,(x,y) in enumerate([(53.34,53.34),(111.76,53.34),(53.34,93.98),(111.76,93.98)],1):
  f=pcb.FootprintLoad(str(LIB/'footprints/MountingHole.pretty'),'MountingHole_2.2mm_M2');f.SetReference('H'+str(i));f.SetPosition(V(x,y));f.SetAttributes(pcb.FP_EXCLUDE_FROM_BOM|pcb.FP_EXCLUDE_FROM_POS_FILES|pcb.FP_BOARD_ONLY);f.Reference().SetVisible(False);f.Value().SetVisible(False);f.SetUuid(pcb.KIID(uid('H'+str(i))));
  for j,g in enumerate(list(f.Pads())+list(f.GraphicalItems())+[f.Reference(),f.Value()]):g.SetUuid(pcb.KIID(uid('H'+str(i)+'-item-'+str(j))))
  stable_fields(f);b.Add(f)
 for i,(a,z) in enumerate([((50.8,50.8),(114.3,50.8)),((114.3,50.8),(114.3,96.52)),((114.3,96.52),(50.8,96.52)),((50.8,96.52),(50.8,50.8))]):
  s=pcb.PCB_SHAPE();s.SetShape(pcb.SHAPE_T_SEGMENT);s.SetStart(V(*a));s.SetEnd(V(*z));s.SetLayer(pcb.Edge_Cuts);s.SetWidth(pcb.FromMM(.05));s.SetUuid(pcb.KIID(uid('edge'+str(i))));b.Add(s)
 for s,x,y,size in [('KERO / LED RELAX',75,53.3,1.2),('RED',106.68,63.5,.9),('GREEN',104.14,86,.9),('CR2032 / 3V',70,91.44,1)]:
  t=pcb.PCB_TEXT(b);t.SetText(s);t.SetPosition(V(x,y));t.SetTextSize(V(size,size));t.SetTextThickness(pcb.FromMM(.15));t.SetLayer(pcb.F_SilkS);t.SetUuid(pcb.KIID(uid('text'+s)));b.Add(t)
 route(b)
 b.BuildConnectivity();pcb.SaveBoard(str(ROOT/'KERO.kicad_pcb'),b)
 # KiCad 10's footprint anchor points lack a usable SWIG setter. Patch only
 # their parsed UUID tokens, never coordinates, then validate with native KiCad.
 path=ROOT/'KERO.kicad_pcb';text=path.read_text(encoding='utf-8');tree=parse(text)
 for fp in kids(tree,'footprint'):
  ref=next(p[2] for p in kids(fp,'property') if p[1]=='Reference')
  for i,point in enumerate(kids(fp,'point')):
   old=one(point,'uuid')[1];token='(uuid "'+old+'")';assert text.count(token)==1
   text=text.replace(token,'(uuid "'+uid(ref+'-point-'+str(i))+'")',1)
 write(path,text)
 pro={'meta':{'filename':'KERO.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_clearance':.25,'min_track_width':.25,'min_via_diameter':.6,'min_through_hole_diameter':.3,'min_hole_clearance':.25,'min_copper_edge_clearance':.3}}},'net_settings':{'classes':[{'name':'Default','clearance':.25,'track_width':.3,'via_diameter':.8,'via_drill':.4,'microvia_diameter':.3,'microvia_drill':.1,'wire_width':6,'bus_width':12}]}}
 write(ROOT/'KERO.kicad_pro',json.dumps(pro,indent=2)+'\n')
 print('Board saved:',len(list(b.GetTracks())),'copper items')
def route(b,connections=None):
 step=.254;xmin,xmax,ymin,ymax=51.5,113.5,51.5,95.7;nx,ny=int((xmax-xmin)/step),int((ymax-ymin)/step);blocked=[{},{}]
 def grid(x,y):return round((x-xmin)/step),round((y-ymin)/step)
 def xy(g):return xmin+g[0]*step,ymin+g[1]*step
 def disc(x,y,r,n,layers=(0,1)):
  gx,gy=grid(x,y);d=math.ceil(r/step)+1
  for i in range(max(0,gx-d),min(nx,gx+d)+1):
   for j in range(max(0,gy-d),min(ny,gy+d)+1):
    xx,yy=xy((i,j))
    if (xx-x)**2+(yy-y)**2<=r*r:
     for l in layers:blocked[l].setdefault((i,j),set()).add(n)
 pads={}
 for f in b.GetFootprints():
  for p in f.Pads():
   pos=p.GetPosition();x,y=pcb.ToMM(pos.x),pcb.ToMM(pos.y);n=p.GetNetname();box=p.GetBoundingBox();hx=pcb.ToMM(box.GetWidth())/2+.43;hy=pcb.ToMM(box.GetHeight())/2+.43
   gx,gy=grid(x,y)
   for ii in range(max(0,gx-math.ceil(hx/step)-1),min(nx,gx+math.ceil(hx/step)+1)+1):
    for jj in range(max(0,gy-math.ceil(hy/step)-1),min(ny,gy+math.ceil(hy/step)+1)+1):
     xx,yy=xy((ii,jj))
     if abs(xx-x)<=hx and abs(yy-y)<=hy:
      for layer in (0,1):blocked[layer].setdefault((ii,jj),set()).add(n or '__hole__')
   if n:pads.setdefault(n,[]).append((x,y,f.GetReference(),p.GetNumber()))
 # Existing saved copper is an obstacle too when extending one ECO branch.
 if connections is not None:
  for track in b.GetTracks():
   net=track.GetNetname()
   if isinstance(track,pcb.PCB_VIA):
    pos=track.GetPosition();disc(pcb.ToMM(pos.x),pcb.ToMM(pos.y),pcb.ToMM(track.GetWidth(pcb.F_Cu))/2+.4,net)
   else:
    a,z=track.GetStart(),track.GetEnd();a=(pcb.ToMM(a.x),pcb.ToMM(a.y));z=(pcb.ToMM(z.x),pcb.ToMM(z.y));count=max(1,math.ceil(math.dist(a,z)/.1));layer=0 if track.GetLayer()==pcb.F_Cu else 1
    for k in range(count+1):disc(a[0]+(z[0]-a[0])*k/count,a[1]+(z[1]-a[1])*k/count,pcb.ToMM(track.GetWidth())/2+.4,net,(layer,))
 route_pads=pads if connections is None else {net:[(*a,'ECO_START','1'),(*z,'ECO_END','1')] for net,a,z in connections}
 def free(i,j,l,n):return 0<=i<=nx and 0<=j<=ny and not(blocked[l].get((i,j),set())-{n})
 def seg(a,z,n,l):
  if math.dist(a,z)<1e-6:return
  t=pcb.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetWidth(pcb.FromMM(.3));t.SetLayer(pcb.F_Cu if l==0 else pcb.B_Cu);t.SetNet(b.FindNet(n));t.SetUuid(pcb.KIID(uid('track'+n+str(a)+str(z)+str(l))));b.Add(t)
  count=max(1,math.ceil(math.dist(a,z)/.1))
  for k in range(count+1):disc(a[0]+(z[0]-a[0])*k/count,a[1]+(z[1]-a[1])*k/count,.56,n,(l,))
 via_set=set()
 def via(g,n):
  if (g[0],g[1],n) in via_set:return
  via_set.add((g[0],g[1],n))
  x,y=xy(g);v=pcb.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(pcb.FromMM(.8));v.SetDrill(pcb.FromMM(.4));v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNet(b.FindNet(n));v.SetUuid(pcb.KIID(uid('via'+n+str(g))));b.Add(v);disc(x,y,.8,n)
 for n,ps in sorted(route_pads.items(),key=lambda kv:(kv[0]=='GND',-len(kv[1]),kv[0])):
  tree=[ps[0]];todo=ps[1:]
  while todo:
   _,si,ti=min((math.dist(a[:2],z[:2]),i,j) for i,a in enumerate(todo) for j,z in enumerate(tree));a=todo.pop(si);z=tree[ti];start=(*grid(*a[:2]),0);goal=grid(*z[:2]);dist={start:0};prev={};heap=[(0,0,start)];end=None
   while heap:
    _,cost,u=heapq.heappop(heap)
    if cost!=dist.get(u):continue
    if u[:2]==goal and u[2]==0:end=u;break
    i,j,l=u
    for di,dj in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1),(0,0)]:
     nl=1-l if di==dj==0 else l;v=(i+di,j+dj,nl)
     if not free(v[0],v[1],nl,n):continue
     if di and dj and (not free(i+di,j,l,n) or not free(i,j+dj,l,n)):continue
     if nl!=l and any(math.dist(xy(u),p[:2])<1.5 for pp in pads.values() for p in pp if p[2].startswith(('D','TP','C3'))):continue
     if nl!=l and any(not free(i+ii,j+jj,ll,n) for ii,jj in [(0,0),(1,0),(-1,0),(0,1),(0,-1),(2,0),(-2,0),(0,2),(0,-2)] for ll in (0,1)):continue
     nc=cost+(12 if nl!=l else (1.414214 if di and dj else 1))
     if nc<dist.get(v,1e99):dist[v]=nc;prev[v]=u;heapq.heappush(heap,(nc+math.hypot(v[0]-goal[0],v[1]-goal[1]),nc,v))
   if end is None:raise RuntimeError(f'Unroutable {n}: {a} -> {z}; start={start}, blockers={blocked[start[2]].get(start[:2])}, goal={goal}, blockers={blocked[0].get(goal)}; reached={len(dist)}')
   path=[end]
   while path[-1]!=start:path.append(prev[path[-1]])
   path.reverse();seg(a[:2],xy(start),n,start[2]);run=path[0];direction=None
   for u,v in zip(path,path[1:]):
    d=(v[0]-u[0],v[1]-u[1],v[2]-u[2])
    if d[2]:seg(xy(run),xy(u),n,u[2]);via(u,n);run=v;direction=None
    elif direction is not None and d!=direction:seg(xy(run),xy(u),n,u[2]);run=u
    direction=d
   seg(xy(run),xy(end),n,end[2]);seg(xy(end),z[:2],n,end[2]);tree.append(a)
 print('Routed all',sum(len(v) for v in pads.values()),'pads on',len(pads),'nets')
