"""Repair only the separate encoder PCB; native checks remain authoritative."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'encoder'
SCRATCH=DEST/'.scratch'
SCRATCH.mkdir(exist_ok=True)
os.environ['TEMP']=str(SCRATCH)
os.environ['TMP']=str(SCRATCH)
import argparse, collections, hashlib, heapq, json, math
import pcbnew as pcb
from build_demo import uid,write

V=lambda x,y:pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))
xy=lambda p:(pcb.ToMM(p.x),pcb.ToMM(p.y))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def native_partitions(b):
    b.BuildConnectivity();c=b.GetConnectivity();c.RecalculateRatsnest()
    pads={f.GetReference()+'.'+p.GetNumber():p for f in b.GetFootprints() for p in f.Pads()}
    names=collections.defaultdict(set)
    for key,p in pads.items():names[p.GetNetname()].add(key)
    partitions={}
    for name,required in sorted(names.items()):
        remaining=set(required);groups=[]
        while remaining:
            queue=[pads[min(remaining)]];seen=set();group=set()
            while queue:
                item=queue.pop();identity=item.m_Uuid.AsString()
                if identity in seen:continue
                seen.add(identity)
                if isinstance(item,pcb.PAD):group.add(item.GetParentFootprint().GetReference()+'.'+item.GetNumber())
                queue.extend(c.GetConnectedItems(item))
            group&=required;assert group
            groups.append(sorted(group));remaining-=group
        partitions[name]=groups
    return partitions


def pruning():
    path=DEST/'Encoder.kicad_pcb';before=sha(path);b=pcb.LoadBoard(str(path))
    original=native_partitions(b);tracks=list(b.GetTracks());pads=[p for f in b.GetFootprints() for p in f.Pads()]
    drc=json.loads((DEST/'evidence/board-drc.json').read_text(encoding='utf-8'))
    report=json.loads((DEST/'evidence/board-validation.json').read_text(encoding='utf-8'))
    assert report['source_sha256']['encoder/Encoder.kicad_pcb']==before,'Native report is stale'
    ids={i['uuid'] for row in drc['violations'] if row['type']=='track_dangling' for i in row['items']}
    rows=[]
    for track in tracks:
        if track.m_Uuid.AsString() not in ids:continue
        a,z=xy(track.GetStart()),xy(track.GetEnd());dx,dy=z[0]-a[0],z[1]-a[1];length2=dx*dx+dy*dy
        assert length2>0
        def project(p):return ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length2
        def point(t):return (a[0]+dx*t,a[1]+dy*t)
        contacts=[]
        for pad in pads:
            if pad.GetNetCode()!=track.GetNetCode() or not pad.IsOnLayer(track.GetLayer()):continue
            t=max(0,min(1,project(xy(pad.GetPosition()))))
            if pad.HitTest(V(*point(t))):contacts.append(t)
        for other in tracks:
            if other is track or other.m_Uuid==track.m_Uuid or other.GetNetCode()!=track.GetNetCode():continue
            if isinstance(other,pcb.PCB_VIA):
                t=max(0,min(1,project(xy(other.GetPosition()))))
                if math.dist(point(t),xy(other.GetPosition()))<=pcb.ToMM(other.GetWidth(pcb.F_Cu))/2+pcb.ToMM(track.GetWidth())/2:contacts.append(t)
                continue
            if other.GetLayer()!=track.GetLayer():continue
            oa,oz=xy(other.GetStart()),xy(other.GetEnd());ox,oy=oz[0]-oa[0],oz[1]-oa[1]
            for p in (oa,oz):
                t=max(0,min(1,project(p)))
                if math.dist(point(t),p)<=pcb.ToMM(other.GetWidth()+track.GetWidth())/2+.000001:contacts.append(t)
            den=dx*oy-dy*ox
            if abs(den)>1e-12:
                px,py=oa[0]-a[0],oa[1]-a[1];t=(px*oy-py*ox)/den;s=(px*dy-py*dx)/den
                if 0<=t<=1 and 0<=s<=1:contacts.append(t)
        if not contacts:
            b.Remove(track);rows.append({'uuid':track.m_Uuid.AsString(),'action':'remove_unattached_track'})
        else:
            low,high=min(contacts),max(contacts)
            if math.dist(point(low),point(high))<.000001:
                b.Remove(track);rows.append({'uuid':track.m_Uuid.AsString(),'action':'remove_terminal_branch','contacts':contacts})
            else:
                track.SetStart(V(*point(low)));track.SetEnd(V(*point(high)))
                rows.append({'uuid':track.m_Uuid.AsString(),'action':'trim_terminal_segment','old_mm':[a,z],'new_mm':[point(low),point(high)]})
    final=native_partitions(b)
    assert original==final,'Pruning changed a required native pad partition; refusing save'
    pcb.SaveBoard(str(path),b,True)
    write(DEST/'evidence/terminal-stub-pruning.json',json.dumps({'schema':'kero.native-stub-pruning/v1',
          'source_before_sha256':before,'source_after_sha256':sha(path),'changes':rows,
          'native_pad_partitions_preserved':True},indent=2)+'\n')
    print('Pruned/trimmed',len(rows),'native-reported dangling tracks; pad partitions preserved')


def negotiated(max_steps=160):
    """Whole-net rip-up with hard pads and penalized foreign copper.

    Geometry is never accepted by this raster estimate. The resulting saved
    candidate must pass native DRC and complete connected-pad partitions.
    """
    import numpy as np
    from scipy.ndimage import distance_transform_edt
    source=DEST/'Encoder.kicad_pcb';before=sha(source);b=pcb.LoadBoard(str(source))
    original=native_partitions(b)
    initial_open=sum(len(groups)-1 for groups in original.values())
    pitch=.1;origin=50.5;size=391
    point=lambda g:(origin+g[0]*pitch,origin+g[1]*pitch)
    grid=lambda p:(round((p[0]-origin)/pitch),round((p[1]-origin)/pitch))
    pads=collections.defaultdict(list)
    for f in b.GetFootprints():
        for p in f.Pads():
            pads[p.GetNetname()].append({'id':f.GetReference()+'.'+p.GetNumber(),'p':xy(p.GetPosition()),
              'g':grid(xy(p.GetPosition())),'layers':tuple(l for l,k in enumerate((pcb.F_Cu,pcb.B_Cu)) if p.IsOnLayer(k)),
              'pad':p})
    names=sorted(pads);assert len(names)<63
    bits={name:np.uint64(1<<i) for i,name in enumerate(names)}
    hard=np.zeros((2,size,size),dtype=np.uint64);copper=np.zeros_like(hard)
    via_hard=np.zeros((size,size),dtype=bool);history=np.zeros((2,size,size),dtype=np.float32)
    def bounds(x,y,rx,ry):
        i,j=grid((x,y));return max(0,i-math.ceil(rx/pitch)-1),min(size-1,i+math.ceil(rx/pitch)+1),max(0,j-math.ceil(ry/pitch)-1),min(size-1,j+math.ceil(ry/pitch)+1)
    def disc(array,x,y,r,bit,layers):
        ia,iz,ja,jz=bounds(x,y,r,r)
        xx=origin+np.arange(ia,iz+1)*pitch;yy=origin+np.arange(ja,jz+1)*pitch
        mask=(xx[:,None]-x)**2+(yy[None,:]-y)**2<=r*r
        for layer in layers:
            arr=array[layer,ia:iz+1,ja:jz+1];arr[mask]|=bit
    for name,pp in pads.items():
        for p in pp:
            pad=p['pad'];box=pad.GetBoundingBox();x,y=p['p'];hx,hy=pcb.ToMM(box.GetWidth())/2,pcb.ToMM(box.GetHeight())/2
            ia,iz,ja,jz=bounds(x,y,hx+.265,hy+.265)
            xx=origin+np.arange(ia,iz+1)*pitch;yy=origin+np.arange(ja,jz+1)*pitch
            mask=(abs(xx[:,None]-x)<=hx+.265)&(abs(yy[None,:]-y)<=hy+.265)
            for layer in p['layers']:
                arr=hard[layer,ia:iz+1,ja:jz+1];arr[mask]|=bits[name]
            ia,iz,ja,jz=bounds(x,y,hx+.5,hy+.5)
            xx=origin+np.arange(ia,iz+1)*pitch;yy=origin+np.arange(ja,jz+1)*pitch
            via_hard[ia:iz+1,ja:jz+1]|=(abs(xx[:,None]-x)<=hx+.5)&(abs(yy[None,:]-y)<=hy+.5)
    items=collections.defaultdict(list)
    def stamp_track(track,name):
        bit=bits[name]
        if isinstance(track,pcb.PCB_VIA):
            x,y=xy(track.GetPosition());disc(copper,x,y,pcb.ToMM(track.GetWidth(pcb.F_Cu))/2+.26,bit,(0,1));return
        a,z=xy(track.GetStart()),xy(track.GetEnd());n=max(1,math.ceil(math.dist(a,z)/.05));layer=0 if track.GetLayer()==pcb.F_Cu else 1
        for k in range(n+1):disc(copper,a[0]+(z[0]-a[0])*k/n,a[1]+(z[1]-a[1])*k/n,pcb.ToMM(track.GetWidth())/2+.26,bit,(layer,))
    for track in b.GetTracks():
        name=track.GetNetname();items[name].append(track);stamp_track(track,name)
    def remove(name):
        copper[:]&=np.uint64(~bits[name])
        removed=items[name];items[name]=[]
        for item in removed:
            b.Remove(item);item.thisown=False
        return removed
    def restore(name,removed):
        for item in removed:b.Add(item);items[name].append(item);stamp_track(item,name)
    offsets=[(i,j) for i in range(-3,4) for j in range(-3,4) if i*i+j*j<=9]
    counter=0
    def materialize(name,segments,vias):
        nonlocal counter
        for a,z,layer in segments:
            if math.dist(a,z)<1e-7:continue
            item=pcb.PCB_TRACK(b);item.SetStart(V(*a));item.SetEnd(V(*z));item.SetWidth(pcb.FromMM(.15));item.SetLayer(pcb.F_Cu if layer==0 else pcb.B_Cu);item.SetNet(b.FindNet(name));item.SetUuid(pcb.KIID(uid('encoder-negotiated-track-'+str(counter))));counter+=1;b.Add(item);items[name].append(item);stamp_track(item,name)
        for g in sorted(vias):
            item=pcb.PCB_VIA(b);item.SetPosition(V(*point(g)));item.SetWidth(pcb.FromMM(.6));item.SetDrill(pcb.FromMM(.3));item.SetViaType(pcb.VIATYPE_THROUGH);item.SetLayerPair(pcb.F_Cu,pcb.B_Cu);item.SetNet(b.FindNet(name));item.SetUuid(pcb.KIID(uid('encoder-negotiated-via-'+str(counter))));counter+=1;b.Add(item);items[name].append(item);stamp_track(item,name)
    def plan(name):
        pp=sorted(pads[name],key=lambda p:p['id']);bit=bits[name];other=np.uint64(~bit)
        # Central first pad avoids forcing every branch toward a corner endpoint.
        first=min(pp,key=lambda p:sum(math.dist(p['p'],q['p']) for q in pp))
        tree={(*first['g'],l) for l in first['layers']};tree_points=[first['p']];todo=[p for p in pp if p is not first]
        segments=[];vias=set();conflicts=np.uint64(0);expanded_total=0
        def seg(a,z,l):
            nonlocal conflicts
            if math.dist(a,z)<1e-7:return
            segments.append((a,z,l))
            count=max(1,math.ceil(math.dist(a,z)/.04))
            for k in range(count+1):
                i,j=grid((a[0]+(z[0]-a[0])*k/count,a[1]+(z[1]-a[1])*k/count))
                conflicts|=copper[l,i,j]&other
        while todo:
            a=min(todo,key=lambda p:min(math.dist(p['p'],z) for z in tree_points));todo.remove(a)
            goals=np.ones((2,size,size),dtype=bool)
            for i,j,l in tree:goals[l,i,j]=False
            heuristic=np.minimum(distance_transform_edt(goals[0]),distance_transform_edt(goals[1]))
            free=(hard&other)==0;foreign=copper&other
            # Previously planned same-net copper is free and forms the tree;
            # a transition through foreign copper causes whole-net rip-up.
            heap=[];dist={};prev={}
            for l in a['layers']:
                u=(*a['g'],l);dist[u]=0;heapq.heappush(heap,(float(heuristic[u[0],u[1]]),0,u))
            end=None;expanded=0
            while heap and expanded<300000:
                _,cost,u=heapq.heappop(heap)
                if cost!=dist.get(u):continue
                if u in tree:end=u;break
                expanded+=1;i,j,l=u
                for di,dj in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                    ii,jj=i+di,j+dj
                    if not(0<=ii<size and 0<=jj<size and free[l,ii,jj]):continue
                    if di and dj and not(free[l,ii,j] and free[l,i,jj]):continue
                    v=(ii,jj,l);mask=int(foreign[l,ii,jj]);extra=mask.bit_count()*12+float(history[l,ii,jj])*.6
                    nc=cost+(1.4142135623730951 if di and dj else 1)+extra
                    if nc<dist.get(v,1e99):dist[v]=nc;prev[v]=u;heapq.heappush(heap,(nc+float(heuristic[ii,jj]),nc,v))
                if not via_hard[i,j] and 3<=i<size-3 and 3<=j<size-3 and all(free[ll,i+di,j+dj] for di,dj in offsets for ll in (0,1)):
                    mask=np.uint64(0)
                    for di,dj in offsets:
                        mask|=foreign[0,i+di,j+dj]|foreign[1,i+di,j+dj]
                    v=(i,j,1-l);nc=cost+18+int(mask).bit_count()*35+float(history[:,i,j].sum())*.6
                    if nc<dist.get(v,1e99):dist[v]=nc;prev[v]=u;heapq.heappush(heap,(nc+float(heuristic[i,j]),nc,v))
            expanded_total+=expanded
            if end is None:return None,{'pad':a['id'],'expanded':expanded_total,'reason':'hard-pad geometry or bounded search'}
            path=[end]
            while path[-1] in prev:path.append(prev[path[-1]])
            path.reverse();start=path[0];seg(a['p'],point(start),start[2]);run=path[0];direction=None
            for u,v in zip(path,path[1:]):
                conflicts|=foreign[u[2],u[0],u[1]]
                d=(v[0]-u[0],v[1]-u[1],v[2]-u[2])
                if d[2]:
                    seg(point(run),point(u),u[2]);vias.add(u[:2]);run=v;direction=None
                    for di,dj in offsets:conflicts|=foreign[0,u[0]+di,u[1]+dj]|foreign[1,u[0]+di,u[1]+dj]
                elif direction is not None and d!=direction:seg(point(run),point(u),u[2]);run=u
                direction=d
            seg(point(run),point(end),end[2]);tree.update(path);tree_points.append(a['p'])
        seg(first['p'],point((*first['g'],first['layers'][0])),first['layers'][0])
        return (segments,vias,conflicts),{'expanded':expanded_total}
    pending=collections.deque(sorted((n for n,g in original.items() if len(g)>1),key=lambda n:(n!='/decoder/MIDREF',n)))
    queued=set(pending);records=[];best_pending=len(pending);failures=[]
    for step in range(max_steps):
        if not pending:break
        name=pending.popleft();queued.remove(name);removed=remove(name)
        planned,stats=plan(name)
        if planned is None:
            restore(name,removed);failures.append({'net':name,**stats});print('HARD_FAIL',name,stats,flush=True);break
        segments,vias,mask=planned
        ripped=[n for n in names if mask&bits[n]]
        for n in ripped:
            remove(n)
            if n not in queued:pending.append(n);queued.add(n)
        materialize(name,segments,vias)
        # Congested regions acquire a history cost, so repeated rip-ups seek
        # alternate corridors rather than simply reversing the previous route.
        for a,z,l in segments:
            count=max(1,math.ceil(math.dist(a,z)/.1))
            for k in range(count+1):
                i,j=grid((a[0]+(z[0]-a[0])*k/count,a[1]+(z[1]-a[1])*k/count))
                if len(ripped):history[l,i,j]+=.5
        record={'step':step+1,'net':name,'ripped':ripped,'pending':list(pending),'segments':len(segments),'vias':len(vias),**stats};records.append(record)
        print(step+1,name,'rip',','.join(ripped) or '-', 'pending',len(pending),flush=True)
        write(ROOT/'.git/encoder-board/repair-progress.json',json.dumps({'step':step+1,'pending':list(pending),'last':record},indent=2)+'\n')
        best_pending=min(best_pending,len(pending))
    final=native_partitions(b);open_edges=sum(len(g)-1 for g in final.values())
    accepted_estimate=not pending and open_edges==0
    saved=False
    if accepted_estimate or open_edges<initial_open:
        assert sha(source)==before,'PCB source changed during repair'
        pcb.SaveBoard(str(source),b,True);saved=True
    receipt={'schema':'kero.negotiated-routing/v1','source_before_sha256':before,
      'source_after_sha256':sha(source),'grid_mm':pitch,'track_mm':.15,'via_mm':[.6,.3],
      'initial_native_open_edges':initial_open,'candidate_native_open_edges':open_edges,
      'saved':saved,'estimated_complete':accepted_estimate,'pending':list(pending),
      'records':records,'failures':failures,'native_pad_partitions':final,
      'acceptance':'Native DRC and schematic parity pending; this receipt alone is not a pass.'}
    write(DEST/'evidence/negotiated-routing.json',json.dumps(receipt,indent=2)+'\n')
    print('DONE','saved',saved,'open_edges',open_edges,'pending',len(pending),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prune-stubs',action='store_true');parser.add_argument('--route',action='store_true');parser.add_argument('--max-steps',type=int,default=160);args=parser.parse_args()
    if args.prune_stubs:pruning()
    elif args.route:negotiated(args.max_steps)

if __name__=='__main__':main()
