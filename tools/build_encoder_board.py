"""Build the separate 40 mm KERO encoder candidate from its schematic intent.

Native KiCad 10 pcbnew materializes geometry. Placement and routing are separate
stages; neither a generated board nor a router exit substitutes for native DRC.
"""
from pathlib import Path
import argparse, collections, hashlib, heapq, json, math, shutil
import subprocess, xml.etree.ElementTree as ET
import os
_native_scratch=Path(__file__).resolve().parents[1]/'encoder'/'.scratch'
_native_scratch.mkdir(parents=True,exist_ok=True)
os.environ['TEMP']=str(_native_scratch)
os.environ['TMP']=str(_native_scratch)
import pcbnew as pcb
from build_demo import ROOT, LIB, Q, parse, dump, kids, one, uid, write

DEST = ROOT / 'encoder'
V = lambda x,y: pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))


def localize(parts):
    target = DEST / 'Encoder.pretty'
    models = DEST / 'models'
    target.mkdir(parents=True, exist_ok=True)
    models.mkdir(exist_ok=True)
    receipts = []
    for source_name in sorted({p['source_footprint'] for p in parts}):
        lib, name = source_name.split(':')
        source = LIB / 'footprints' / (lib+'.pretty') / (name+'.kicad_mod')
        tree = parse(source.read_text(encoding='utf-8'))
        for model in kids(tree,'model'):
            source_model = LIB / '3dmodels' / model[1].split('}/',1)[1]
            out = models / source_model.name
            if not out.exists(): shutil.copyfile(source_model, out)
            model[1] = Q('${KIPRJMOD}/models/'+out.name)
            receipts.append({'footprint':source_name, 'model':'models/'+out.name,
                             'source_sha256':hashlib.sha256(source_model.read_bytes()).hexdigest()})
        assert kids(tree,'model'), source_name
        write(target / (name+'.kicad_mod'), dump(tree)+'\n')
    write(DEST/'fp-lib-table', '(fp_lib_table (version 7) (lib (name "Encoder") (type "KiCad") (uri "${KIPRJMOD}/Encoder.pretty") (options "") (descr "Local KiCad 10 footprints")))\n')
    # The holder's vendor-neutral coin is a nominal mechanical envelope.
    shutil.copyfile(ROOT/'models/CR2032_nominal.wrl',models/'CR2032_nominal.wrl')
    return receipts


def poses(parts):
    pos={'U1':(60,60,0),'U2':(80,60,0),'U3':(60,80,0),
         'BT1':(70,70,0),'C12':(60,64.5,0),'C13':(80,64.5,0),'C14':(60,84.5,0),
         'R56':(74,85.5,0),'R57':(77,85.5,0),'R58':(82,85.5,0),'R59':(86,85.5,0),
         'D1':(82,88,0),'D2':(86,88,0)}
    for i in range(11):
        ic=i//4;unit=i%4;ux,uy=pos['U'+str(ic+1)][:2]
        dx,dy=[(-6.5,-4.5),(-6.5,4.5),(6.5,4.5),(6.5,-4.5)][unit]
        x,y=ux+dx,uy+dy
        pos['R'+str(4*i+1)]=(x,y-2.5,0)
        pos['C'+str(i+1)]=(x,y,0)
        for j in range(3):pos['R'+str(4*i+j+2)]=(x+(j-1)*1.8,y+3,90)
        pos['R'+str(45+i)]=(74+(i%4)*3.5,73+(i//4)*3.0,0)
    assert set(pos)=={p['ref'] for p in parts}
    return pos


def symbol_paths():
    result={}
    for sheet in DEST.glob('*.kicad_sch'):
        tree=parse(sheet.read_text(encoding='utf-8'))
        for symbol in kids(tree,'symbol'):
            ref=next(p[2] for p in kids(symbol,'property') if p[1]=='Reference')
            instances=one(symbol,'instances')
            project=one(instances,'project')
            path=one(project,'path')[1]
            result.setdefault(ref,path+'/'+one(symbol,'uuid')[1])
    return result


def build():
    intent=json.loads((DEST/'design-intent.json').read_text(encoding='utf-8'))
    parts=intent['parts']; receipts=localize(parts); pos=poses(parts); paths=symbol_paths()
    print('Libraries localized; intent paths resolved',flush=True)
    b=pcb.BOARD();b.SetCopperLayerCount(2)
    nets={}
    for name in sorted({n for p in parts for n in p['pins'].values()}):
        net=pcb.NETINFO_ITEM(b,name);b.Add(net);nets[name]=net
    for p in parts:
        ref=p['ref'];name=p['footprint'].split(':')[1]
        fp=pcb.FootprintLoad(str(DEST/'Encoder.pretty'),name)
        # Values are resolved from the shared project variables for the PCB.
        # KiCad 10 schematic parity compares these against expanded netlist data.
        fp.SetReference(ref);fp.SetValue(p['value'])
        fp.SetFPID(pcb.LIB_ID('Encoder',name));fp.SetUuid(pcb.KIID(uid('encoder-pcb-'+ref)))
        fp.SetPath(pcb.KIID_PATH(paths[ref]));x,y,a=pos[ref];fp.SetPosition(V(x,y));fp.SetOrientationDegrees(a)
        if ref=='BT1':
            coin=pcb.FP_3DMODEL();coin.m_Filename='${KIPRJMOD}/models/CR2032_nominal.wrl';fp.Add3DModel(coin)
        for pad in fp.Pads():
            pad.SetNet(nets[p['pins'][pad.GetNumber()]])
            pad.SetUuid(pcb.KIID(uid('encoder-'+ref+'-pad-'+pad.GetNumber())))
        for key in ('manufacturer','mpn','rating','datasheet'):
            fld=pcb.PCB_FIELD(fp,pcb.FIELD_T_USER);fld.SetName({'mpn':'MPN','datasheet':'Datasheet'}.get(key,key.title()))
            fld.SetText(p[key]);fld.SetVisible(False);fp.Add(fld)
        fp.Reference().SetTextSize(V(.65,.65));fp.Reference().SetTextThickness(pcb.FromMM(.1))
        # The dense assembly identification is exported on fabrication layers.
        # Silkscreen remains reserved for polarity and product identification.
        fp.Reference().SetLayer(pcb.B_Fab if ref=='BT1' else pcb.F_Fab)
        fp.Value().SetVisible(False)
        for i,g in enumerate(list(fp.GraphicalItems())+list(fp.GetFields())):
            g.SetUuid(pcb.KIID(uid('encoder-'+ref+'-graphic-'+str(i))))
        b.Add(fp)
        if ref=='BT1':
            fp.Flip(V(x,y),False)
            fp.Reference().SetLayer(pcb.B_Fab)
    points=[(50,50),(90,50),(90,90),(50,90)]
    for i,(a,z) in enumerate(zip(points,points[1:]+points[:1])):
        edge=pcb.PCB_SHAPE();edge.SetShape(pcb.SHAPE_T_SEGMENT);edge.SetStart(V(*a));edge.SetEnd(V(*z))
        edge.SetLayer(pcb.Edge_Cuts);edge.SetWidth(pcb.FromMM(.05));edge.SetUuid(pcb.KIID(uid('encoder-edge-'+str(i))));b.Add(edge)
    for label,x,y in [('KERO / HELLO',70,50.9),('RC PWM',70,89.1)]:
        text=pcb.PCB_TEXT(b);text.SetText(label);text.SetPosition(V(x,y));text.SetTextSize(V(.8,.8));text.SetTextThickness(pcb.FromMM(.12));text.SetLayer(pcb.F_SilkS);text.SetUuid(pcb.KIID(uid('encoder-text-'+label)));b.Add(text)
    b.BuildConnectivity();pcb.SaveBoard(str(DEST/'Encoder.kicad_pcb'),b,True)
    evidence=DEST/'evidence';evidence.mkdir(exist_ok=True)
    write(evidence/'placement.json',json.dumps({'schema':'kero.encoder-placement/v1','board_mm':[40,40],
       'baseline_board_mm':[63.5,45.72],'area_reduction_fraction':1-1600/(63.5*45.72),'parts':len(parts),
       'poses':pos,'source_intent_sha256':hashlib.sha256((DEST/'design-intent.json').read_bytes()).hexdigest(),
       'status':'UNROUTED_CANDIDATE','assumptions':['2 copper layers; 1.6 mm FR4; 35 um copper nominal',
       '0.15 mm minimum track and clearance, ordinary 0.6/0.3 mm through vias; fabrication capability unconfirmed',
       'High-impedance timing nodes require cleanliness and leakage qualification',
       'Generic passive and LED MPNs remain unverified; library models are package envelopes']},indent=2)+'\n')
    write(evidence/'models.json',json.dumps(receipts,indent=2)+'\n')
    print('Saved compact placement:',len(parts),'parts,',sum(len(list(f.Pads())) for f in b.GetFootprints()),'pads')


def route():
    """One bounded, deterministic two-layer grid attempt on the saved candidate.

    Conservative raster obstacles are advisory; native DRC remains authoritative.
    Unroutable connections are retained explicitly and do not become a pass.
    """
    import numpy as np
    from scipy.ndimage import distance_transform_edt
    b=pcb.LoadBoard(str(DEST/'Encoder.kicad_pcb'))
    if list(b.GetTracks()):raise RuntimeError('Route requires the untouched placement candidate')
    pitch=.1;origin=50.5;limit=89.5;size=391
    def grid(x,y):return (round((x-origin)/pitch),round((y-origin)/pitch))
    def point(g):return (origin+g[0]*pitch,origin+g[1]*pitch)
    names=sorted({p.GetNetname() for f in b.GetFootprints() for p in f.Pads() if p.GetNetname()})
    assert len(names)<63
    bits={name:np.uint64(1<<i) for i,name in enumerate(names)}
    blocked=np.zeros((2,size,size),dtype=np.uint64)
    pad_via=np.zeros((size,size),dtype=bool)
    pads=collections.defaultdict(list)
    def bounds(x,y,rx,ry):
        i,j=grid(x,y);return max(0,i-math.ceil(rx/pitch)-1),min(size-1,i+math.ceil(rx/pitch)+1),max(0,j-math.ceil(ry/pitch)-1),min(size-1,j+math.ceil(ry/pitch)+1)
    def disc(x,y,r,bit,layers):
        ia,iz,ja,jz=bounds(x,y,r,r)
        xx=origin+np.arange(ia,iz+1)*pitch;yy=origin+np.arange(ja,jz+1)*pitch
        mask=(xx[:,None]-x)**2+(yy[None,:]-y)**2<=r*r
        for layer in layers:
            arr=blocked[layer,ia:iz+1,ja:jz+1];arr[mask]|=bit
    for f in b.GetFootprints():
        for p in f.Pads():
            xy=p.GetPosition();x,y=pcb.ToMM(xy.x),pcb.ToMM(xy.y)
            box=p.GetBoundingBox();hx,hy=pcb.ToMM(box.GetWidth())/2,pcb.ToMM(box.GetHeight())/2
            layers=tuple(l for l,k in enumerate((pcb.F_Cu,pcb.B_Cu)) if p.IsOnLayer(k))
            name=p.GetNetname();bit=bits[name] if name else np.uint64(1<<62)
            ia,iz,ja,jz=bounds(x,y,hx+.265,hy+.265)
            xx=origin+np.arange(ia,iz+1)*pitch;yy=origin+np.arange(ja,jz+1)*pitch
            mask=(abs(xx[:,None]-x)<=hx+.265)&(abs(yy[None,:]-y)<=hy+.265)
            for layer in layers:
                arr=blocked[layer,ia:iz+1,ja:jz+1];arr[mask]|=bit
            ia,iz,ja,jz=bounds(x,y,hx+.5,hy+.5)
            xx=origin+np.arange(ia,iz+1)*pitch;yy=origin+np.arange(ja,jz+1)*pitch
            pad_via[ia:iz+1,ja:jz+1]|=(abs(xx[:,None]-x)<=hx+.5)&(abs(yy[None,:]-y)<=hy+.5)
            if name:pads[name].append({'point':(x,y),'grid':grid(x,y),'layers':layers,'id':f.GetReference()+'.'+p.GetNumber()})
    records=[];via_keys=set();segment_no=0
    def segment(a,z,name,layer):
        nonlocal segment_no
        if math.dist(a,z)<1e-7:return
        track=pcb.PCB_TRACK(b);track.SetStart(V(*a));track.SetEnd(V(*z));track.SetWidth(pcb.FromMM(.15))
        track.SetLayer(pcb.F_Cu if layer==0 else pcb.B_Cu);track.SetNet(b.FindNet(name));track.SetUuid(pcb.KIID(uid('encoder-track-'+str(segment_no))));segment_no+=1;b.Add(track)
        n=max(1,math.ceil(math.dist(a,z)/.05))
        for k in range(n+1):disc(a[0]+(z[0]-a[0])*k/n,a[1]+(z[1]-a[1])*k/n,.335,bits[name],(layer,))
    def via(g,name):
        key=(*g,name)
        if key in via_keys:return
        via_keys.add(key);x,y=point(g);v=pcb.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(pcb.FromMM(.6));v.SetDrill(pcb.FromMM(.3));v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNet(b.FindNet(name));v.SetUuid(pcb.KIID(uid('encoder-via-'+str(key))));b.Add(v);disc(x,y,.56,bits[name],(0,1))
    # Reserve every TSSOP pin's escape before global routing can surround it.
    # Alternating via columns lie under the package body, not in solder pads.
    # This assumes ordinary tented through vias; assembly qualification is open.
    centres={f.GetReference():(pcb.ToMM(f.GetPosition().x),pcb.ToMM(f.GetPosition().y)) for f in b.GetFootprints() if f.GetReference().startswith('U')}
    for name,pp in pads.items():
        for p in pp:
            if not p['id'].startswith('U'):continue
            ref=p['id'].split('.')[0];ux,uy=centres[ref];x,y=p['point']
            row=round((y-uy)/.65+3);side=-1 if x<ux else 1
            g=grid(ux+side*(1.3 if row%2==0 else .4),y)
            segment(p['point'],point(g),name,0);via(g,name)
            z=point(g);samples=max(1,math.ceil(math.dist(p['point'],z)/.04))
            p['access']={(*grid(x+(z[0]-x)*k/samples,y+(z[1]-y)*k/samples),0) for k in range(samples+1)}|{(*g,1)}
            p['point']=point(g);p['grid']=g;p['layers']=(0,1)
    ordered=sorted(names,key=lambda n:(0 if n in ('/VBAT','/GND') else 3 if 'MAJORITY' in n else 2 if n.endswith('_OUT') or n=='ENCODED_OUT' else 1,n))
    offsets=[(i,j) for i in range(-3,4) for j in range(-3,4) if i*i+j*j<=9]
    for name in ordered:
        pp=pads[name];bit=bits[name];other=np.uint64(~bit)
        tree=set(pp[0].get('access',((*pp[0]['grid'],l) for l in pp[0]['layers'])));tree_points=[pp[0]['point']];todo=pp[1:]
        while todo:
            a=min(todo,key=lambda p:min(math.dist(p['point'],z) for z in tree_points));todo.remove(a)
            goal_mask=np.ones((2,size,size),dtype=bool)
            for i,j,l in tree:goal_mask[l,i,j]=False
            heuristic=np.minimum(distance_transform_edt(goal_mask[0]),distance_transform_edt(goal_mask[1]))
            free=(blocked&other)==0
            distances={};previous={};heap=[]
            for u in a.get('access',((*a['grid'],layer) for layer in a['layers'])):
                distances[u]=0;heapq.heappush(heap,(float(heuristic[u[0],u[1]]),0,u))
            end=None;expanded=0
            while heap and expanded<250000:
                _,cost,u=heapq.heappop(heap)
                if cost!=distances.get(u):continue
                if u in tree:end=u;break
                expanded+=1;i,j,l=u
                moves=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
                for di,dj in moves:
                    ii,jj=i+di,j+dj
                    if not(0<=ii<size and 0<=jj<size and free[l,ii,jj]):continue
                    if di and dj and not(free[l,ii,j] and free[l,i,jj]):continue
                    v=(ii,jj,l);nc=cost+(1.4142135623730951 if di and dj else 1)
                    if nc<distances.get(v,1e99):distances[v]=nc;previous[v]=u;heapq.heappush(heap,(nc+float(heuristic[ii,jj]),nc,v))
                if not pad_via[i,j] and 3<=i<size-3 and 3<=j<size-3 and all(free[ll,i+di,j+dj] for di,dj in offsets for ll in (0,1)):
                    v=(i,j,1-l);nc=cost+18
                    if nc<distances.get(v,1e99):distances[v]=nc;previous[v]=u;heapq.heappush(heap,(nc+float(heuristic[i,j]),nc,v))
            rec={'net':name,'pad':a['id'],'expanded':expanded,'status':'ROUTED' if end else 'UNROUTABLE'};records.append(rec)
            if end is None:
                print('Unroutable',name,a['id'],expanded,flush=True);continue
            path=[end]
            while path[-1] in previous:path.append(previous[path[-1]])
            path.reverse();start=path[0]
            if 'access' not in a:segment(a['point'],point(start),name,start[2])
            run=path[0];direction=None
            for u,v in zip(path,path[1:]):
                d=(v[0]-u[0],v[1]-u[1],v[2]-u[2])
                if d[2]:segment(point(run),point(u),name,u[2]);via(u[:2],name);run=v;direction=None
                elif direction is not None and d!=direction:segment(point(run),point(u),name,u[2]);run=u
                direction=d
            segment(point(run),point(end),name,end[2]);tree.update(path);tree.update(a.get('access',()));tree_points.append(a['point'])
        # The initial pad's native centre also needs a grid stub.
        if 'access' not in pp[0]:segment(pp[0]['point'],point((*pp[0]['grid'],pp[0]['layers'][0])),name,pp[0]['layers'][0])
        print(name, 'connections',sum(r['status']=='ROUTED' for r in records if r['net']==name),'/',len(pp)-1,flush=True)
    b.BuildConnectivity();pcb.SaveBoard(str(DEST/'Encoder.kicad_pcb'),b,True)
    write(DEST/'evidence/routing-attempt.json',json.dumps({'schema':'kero.grid-routing/v1','grid_mm':pitch,
          'track_mm':.15,'clearance_model_mm':.15,'via_mm':[.6,.3],'records':records,
          'estimated_complete':all(r['status']=='ROUTED' for r in records),
          'native_acceptance':'PENDING_NATIVE_DRC_AND_CONNECTIVITY'},indent=2)+'\n')


def verify():
    evidence=DEST/'evidence';previews=DEST/'previews';previews.mkdir(exist_ok=True)
    sources=[p for p in DEST.glob('*.kicad_*') if p.suffix!='.kicad_prl']+list((DEST/'Encoder.pretty').glob('*.kicad_mod'))+list((DEST/'models').glob('*'))+[DEST/'design-intent.json',DEST/'fp-lib-table',DEST/'sym-lib-table']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    before=hashes();logs=[];cli=LIB.parents[1]/'bin/kicad-cli.exe'
    def run(args):
        result=subprocess.run([str(cli),*map(str,args)],capture_output=True,text=True)
        logs.append({'command':[str(cli),*map(str,args)],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        if result.returncode not in (0,5):raise RuntimeError(result.stderr or result.stdout)
        return result
    run(['version'])
    run(['pcb','drc',DEST/'Encoder.kicad_pcb','--output',evidence/'board-drc.json','--format','json','--severity-all','--all-track-errors','--schematic-parity','--exit-code-violations'])
    run(['pcb','export','svg',DEST/'Encoder.kicad_pcb','--output',previews/'board-front.svg','--mode-single','--layers','F.Cu,F.Silkscreen,Edge.Cuts','--page-size-mode','2'])
    run(['pcb','export','svg',DEST/'Encoder.kicad_pcb','--output',previews/'board-back.svg','--mode-single','--layers','B.Cu,B.Silkscreen,Edge.Cuts','--page-size-mode','2'])
    run(['pcb','render',DEST/'Encoder.kicad_pcb','--output',previews/'board-3d.png','--width','1200','--height','850','--rotate','25,0,25','--zoom','.7','--quality','basic'])
    run(['pcb','render',DEST/'Encoder.kicad_pcb','--output',previews/'board-3d-bottom.png','--width','1200','--height','850','--side','bottom','--rotate','25,0,25','--zoom','.7','--quality','basic'])
    b=pcb.LoadBoard(str(DEST/'Encoder.kicad_pcb'));b.BuildConnectivity();c=b.GetConnectivity();c.RecalculateRatsnest()
    actual={};nativepads={};models=[]
    for f in b.GetFootprints():
        for p in f.Pads():
            key=f.GetReference()+'.'+p.GetNumber();actual[key]=p.GetNetname();nativepads[key]=p
        assert len(f.Models())>0,f.GetReference()
        for m in f.Models():
            path=DEST/m.m_Filename.replace('${KIPRJMOD}/','');assert path.is_file(),path
            models.append({'reference':f.GetReference(),'model':str(path.relative_to(DEST)),
                           'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    xml=ET.parse(evidence/'netlist.xml').getroot()
    expected={n.attrib['ref']+'.'+n.attrib['pin']:net.attrib['name'] for net in xml.findall('./nets/net') for n in net.findall('node')}
    parity=[{'pad':key,'expected':v,'actual':actual.get(key)} for key,v in expected.items() if actual.get(key)!=v]
    parity += [{'unexpected_pad':key} for key in actual.keys()-expected.keys()]
    # Traverse native copper/pad adjacency without the DRC display report's cap.
    bynet=collections.defaultdict(set)
    for key,name in actual.items():bynet[name].add(key)
    partitions={}
    for name,required in sorted(bynet.items()):
        remaining=set(required);groups=[]
        while remaining:
            start=sorted(remaining)[0];queue=[nativepads[start]];visited=set();connected=set()
            while queue:
                item=queue.pop();identity=item.m_Uuid.AsString()
                if identity in visited:continue
                visited.add(identity)
                if isinstance(item,pcb.PAD):connected.add(item.GetParentFootprint().GetReference()+'.'+item.GetNumber())
                queue.extend(c.GetConnectedItems(item))
            group=sorted(required&connected);assert group,start
            groups.append(group);remaining.difference_update(group)
        partitions[name]=groups
    open_nets={n:g for n,g in partitions.items() if len(g)>1}
    drc=json.loads((evidence/'board-drc.json').read_text(encoding='utf-8'))
    unchanged=before==hashes()
    accepted=not(drc['violations'] or drc['unconnected_items'] or drc['schematic_parity'] or parity or open_nets) and unchanged
    result={'schema':'kero.encoder-board-validation/v1','status':'PASS' if accepted else 'INCOMPLETE',
       'source_sha256':before,'source_unchanged_during_checks':unchanged,'native_kicad_version':pcb.Version(),
       'board_mm':[40,40],'parts':len(list(b.GetFootprints())),'pads':len(actual),'nets':len(bynet),
       'native_drc_findings':len(drc['violations']),'native_unconnected_items':len(drc['unconnected_items']),
       'native_schematic_parity_findings':len(drc['schematic_parity']),'explicit_pad_net_differences':parity,
       'native_graph_unconnected_count':c.GetUnconnectedCount(False),'native_connected_pad_partitions':partitions,
       'incomplete_nets':open_nets,'models':models,'ignored_checks':drc.get('ignored_checks',[]),
       'limitations':['No fabrication capability or sourcing closure; exact passive/LED MPNs remain unverified.',
       'No bench, enclosure or battery electrochemical validation.',
       'Package models are standard KiCad envelopes; nominal coin model is illustrative.',
       'No copper zones are present; tracks and vias provide all connections.',
       'Native CLI registry-access warnings are retained in the command receipt.']}
    write(evidence/'board-validation.json',json.dumps(result,indent=2)+'\n')
    write(evidence/'board-commands.json',json.dumps(logs,indent=2)+'\n')
    print(result['status'],len(actual),'pads;',len(drc['violations']),'DRC findings;',len(open_nets),'incomplete nets')


def prune_unused_vias():
    path=DEST/'Encoder.kicad_pcb';before=hashlib.sha256(path.read_bytes()).hexdigest()
    report=json.loads((DEST/'evidence/board-validation.json').read_text(encoding='utf-8'))
    source_hashes={k.replace('\\','/'):v for k,v in report['source_sha256'].items()}
    assert source_hashes['encoder/Encoder.kicad_pcb']==before,'DRC is stale'
    drc=json.loads((DEST/'evidence/board-drc.json').read_text(encoding='utf-8'))
    ids={i['uuid'] for row in drc['violations'] if row['type']=='via_dangling' for i in row['items']}
    b=pcb.LoadBoard(str(path));b.BuildConnectivity();c=b.GetConnectivity();remove=[];receipt=[]
    for via in b.GetTracks():
        if not isinstance(via,pcb.PCB_VIA) or via.m_Uuid.AsString() not in ids:continue
        tracks=list(c.GetConnectedTracks(via));pads=list(c.GetConnectedPads(via))
        assert tracks and all(t.GetLayer()==pcb.F_Cu and not isinstance(t,pcb.PCB_VIA) for t in tracks)
        assert not any(p.IsOnLayer(pcb.B_Cu) for p in pads),'Bottom-side pad connection forbids pruning'
        remove.append(via);receipt.append({'uuid':via.m_Uuid.AsString(),'net':via.GetNetname(),
           'direct_native_connected_tracks':len(tracks),'connected_track_layers':['F.Cu'],'bottom_pad_connections':0})
    assert len(remove)==len(ids),'Not all reported unused vias were verified'
    for via in remove:b.Remove(via)
    b.BuildConnectivity();pcb.SaveBoard(str(path),b,True)
    write(DEST/'evidence/unused-via-pruning.json',json.dumps({'source_before_sha256':before,
          'source_after_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'removed':receipt,
          'reason':'Unused prefanout via barrel had no bottom copper connection; front traces remain unchanged.'},indent=2)+'\n')
    print('Pruned',len(remove),'verified one-layer-only prefanout vias')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--route',action='store_true');parser.add_argument('--verify',action='store_true');parser.add_argument('--prune-unused-vias',action='store_true');args=parser.parse_args()
    if args.prune_unused_vias:prune_unused_vias()
    elif args.verify:verify()
    elif args.route:
        route()
    else:build()

if __name__=='__main__':main()
