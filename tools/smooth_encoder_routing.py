"""Create a detached, native-arc encoder routing candidate; never overwrite source.

Run with KiCad's Python. Straight collinear runs are consolidated. Degree-two
bends receive tangent circular fillets; pad/via landings and branches are fixed.
Native DRC and connected-pad comparison remain the acceptance gates.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import math
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'encoder'
WORK = SOURCE / '.scratch' / 'curved-routing'
WORK.mkdir(parents=True, exist_ok=True)
os.environ['TEMP'] = os.environ['TMP'] = str(WORK)
import pcbnew as pcb
from repair_encoder_board import native_partitions


def point(v):
    return (v.x, v.y)


def vector(p):
    return pcb.VECTOR2I(round(p[0]), round(p[1]))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(board):
    return sorted((f.GetReference(), f.GetPosition().x, f.GetPosition().y,
                   f.GetOrientationDegrees(), f.GetLayer(),
                   tuple(sorted((p.GetNumber(), p.GetNetname(),
                                 p.GetPosition().x, p.GetPosition().y)
                                for p in f.Pads())))
                  for f in board.GetFootprints())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cut-mm', type=float, default=.20)
    parser.add_argument('--blocked', type=Path)
    parser.add_argument('--simplify-mm', type=float, default=.065)
    parser.add_argument('--blocked-chains', type=Path)
    args = parser.parse_args()
    blocked = set(json.loads(args.blocked.read_text()) if args.blocked else [])
    blocked_chains = set(json.loads(args.blocked_chains.read_text()) if args.blocked_chains else [])
    candidate = WORK / 'candidate'
    candidate.mkdir(exist_ok=True)
    for pattern in ('*.kicad_sch', '*.kicad_pro', '*.kicad_sym', '*.kicad_dru', '*-lib-table'):
        for path in SOURCE.glob(pattern):
            shutil.copy2(path, candidate / path.name)
    shutil.copytree(SOURCE / 'Encoder.pretty', candidate / 'Encoder.pretty', dirs_exist_ok=True)
    source = SOURCE / 'Encoder.kicad_pcb'
    board = pcb.LoadBoard(str(source))
    if any(isinstance(t, pcb.PCB_ARC) for t in board.GetTracks()):
        raise RuntimeError('This converter requires the straight-track baseline; preserve existing arcs and validate later edits separately.')
    original_parts = identity(board)
    original_partitions = native_partitions(board)
    vias = [t for t in board.GetTracks() if isinstance(t, pcb.PCB_VIA)]
    original_vias = sorted((v.m_Uuid.AsString(), point(v.GetPosition()), v.GetNetCode()) for v in vias)
    pads = [p for f in board.GetFootprints() for p in f.Pads()]
    edges = {}
    removed_tracks = []  # Retain SWIG wrappers until board serialization completes.
    nodes = collections.defaultdict(set)
    for track in board.GetTracks():
        if type(track) != pcb.PCB_TRACK or track.IsLocked():
            continue
        key = track.m_Uuid.AsString()
        group = (track.GetNetCode(), track.GetLayer(), track.GetWidth())
        a, b = point(track.GetStart()), point(track.GetEnd())
        edges[key] = {'track': track, 'group': group, 'ends': [a, b]}
        nodes[(group, a)].add(key)
        nodes[(group, b)].add(key)

    def protected(group, pt):
        net, layer, width = group
        for pad in pads:
            if pad.GetNetCode() == net and pad.IsOnLayer(layer) and pad.HitTest(vector(pt), width // 2):
                return True
        for via in vias:
            if via.GetNetCode() == net and math.dist(point(via.GetPosition()), pt) <= (via.GetWidth(layer) + width) / 2:
                return True
        # Protect coincident endpoints of another width: these are real branches.
        return any(g[:2] == group[:2] and g != group and p == pt for g, p in nodes)

    # Simplify whole pad-to-branch/via paths before filleting. This removes the
    # raster staircase rather than rounding every small staircase corner.
    def rdp(points, tolerance):
        if len(points) <= 2:
            return points
        a, b = points[0], points[-1]
        length2 = sum((b[i] - a[i]) ** 2 for i in (0, 1))
        distances = []
        for p in points[1:-1]:
            t = max(0, min(1, sum((p[i] - a[i]) * (b[i] - a[i]) for i in (0, 1)) / length2)) if length2 else 0
            distances.append(math.dist(p, tuple(a[i] + t * (b[i] - a[i]) for i in (0, 1))))
        distance = max(distances)
        split = distances.index(distance) + 1
        if distance <= tolerance:
            return [a, b]
        return rdp(points[:split + 1], tolerance)[:-1] + rdp(points[split:], tolerance)

    visited = set()
    chains = []
    edge_chain = {}
    anchors = [node for node, ids in nodes.items() if len(ids) != 2 or protected(*node)]
    for group, start in anchors:
        for first in sorted(nodes[(group, start)]):
            if first in visited:
                continue
            vertices, chain_edges, at, edge_id = [start], [], start, first
            while edge_id not in visited:
                visited.add(edge_id)
                chain_edges.append(edge_id)
                at = next(p for p in edges[edge_id]['ends'] if p != at)
                vertices.append(at)
                ids = nodes[(group, at)]
                if len(ids) != 2 or protected(group, at):
                    break
                edge_id = next(k for k in ids if k != edge_id)
            chain_key = min(chain_edges)
            if chain_key in blocked_chains:
                continue
            simplified = rdp(vertices, pcb.FromMM(args.simplify_mm))
            if len(simplified) == len(vertices):
                continue
            for key in chain_edges:
                for endpoint in edges[key]['ends']:
                    nodes[(group, endpoint)].discard(key)
            kept = chain_edges[:len(simplified) - 1]
            for i, key in enumerate(kept):
                a, b = simplified[i:i + 2]
                edges[key]['ends'] = [a, b]
                edges[key]['track'].SetStart(vector(a))
                edges[key]['track'].SetEnd(vector(b))
                nodes[(group, a)].add(key)
                nodes[(group, b)].add(key)
                edge_chain[key] = chain_key
            for key in chain_edges[len(kept):]:
                removed_tracks.append(edges[key]['track'])
                board.Remove(edges[key]['track'])
                del edges[key]
            chains.append({'key': chain_key, 'before_segments': len(chain_edges),
                           'after_segments': len(kept), 'track_uuids': kept})

    merged = 0
    for (group, pt), ids in list(nodes.items()):
        ids = nodes[(group, pt)]
        if len(ids) != 2 or protected(group, pt):
            continue
        first, second = sorted(ids)
        if first not in edges or second not in edges:
            continue
        a = next(p for p in edges[first]['ends'] if p != pt)
        b = next(p for p in edges[second]['ends'] if p != pt)
        u = (a[0] - pt[0], a[1] - pt[1])
        v = (b[0] - pt[0], b[1] - pt[1])
        if abs(u[0] * v[1] - u[1] * v[0]) > 1 or u[0] * v[0] + u[1] * v[1] >= 0:
            continue
        for key in (first, second):
            for endpoint in edges[key]['ends']:
                nodes[(group, endpoint)].discard(key)
        edges[first]['ends'] = [a, b]
        edges[first]['track'].SetStart(vector(a))
        edges[first]['track'].SetEnd(vector(b))
        removed_tracks.append(edges[second]['track'])
        board.Remove(edges[second]['track'])
        del edges[second]
        nodes[(group, a)].add(first)
        nodes[(group, b)].add(first)
        merged += 1

    bends = []
    ownership = collections.defaultdict(list)
    for (group, pt), ids in list(nodes.items()):
        if len(ids) != 2 or protected(group, pt):
            continue
        key = ':'.join(map(str, (*group, *pt)))
        if key in blocked:
            continue
        first, second = sorted(ids)
        a = next(p for p in edges[first]['ends'] if p != pt)
        b = next(p for p in edges[second]['ends'] if p != pt)
        la, lb = math.dist(a, pt), math.dist(b, pt)
        u = ((a[0] - pt[0]) / la, (a[1] - pt[1]) / la)
        v = ((b[0] - pt[0]) / lb, (b[1] - pt[1]) / lb)
        angle = math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1])))
        if angle < math.radians(20) or angle > math.radians(170):
            continue
        cut = min(pcb.FromMM(args.cut_mm), .40 * la, .40 * lb)
        if cut < pcb.FromMM(.008):
            continue
        s = (pt[0] + u[0] * cut, pt[1] + u[1] * cut)
        e = (pt[0] + v[0] * cut, pt[1] + v[1] * cut)
        norm = math.hypot(u[0] + v[0], u[1] + v[1])
        bis = ((u[0] + v[0]) / norm, (u[1] + v[1]) / norm)
        distance = cut / math.cos(angle / 2)
        radius = cut * math.tan(angle / 2)
        mid = (pt[0] + bis[0] * (distance - radius), pt[1] + bis[1] * (distance - radius))
        arc = pcb.PCB_ARC(board)
        arc.SetStart(vector(s)); arc.SetMid(vector(mid)); arc.SetEnd(vector(e))
        arc.SetWidth(group[2]); arc.SetLayer(group[1]); arc.SetNetCode(group[0])
        board.Add(arc)
        for edge_id, endpoint in ((first, s), (second, e)):
            track = edges[edge_id]['track']
            if point(track.GetStart()) == pt:
                track.SetStart(vector(endpoint))
            elif point(track.GetEnd()) == pt:
                track.SetEnd(vector(endpoint))
            else:
                raise RuntimeError('Lost endpoint custody')
            ownership[edge_id].append(key)
        ownership[arc.m_Uuid.AsString()].append(key)
        affected_chains = sorted({edge_chain[k] for k in (first, second) if k in edge_chain})
        bends.append({'key': key, 'arc_uuid': arc.m_Uuid.AsString(),
                      'cut_mm': pcb.ToMM(round(cut)), 'radius_mm': pcb.ToMM(round(radius)),
                      'simplified_chains': affected_chains})

    target = candidate / source.name
    pcb.SaveBoard(str(target), board, True)
    reread = pcb.LoadBoard(str(target))
    final_partitions = native_partitions(reread)
    assert identity(reread) == original_parts, 'Footprint/pad/placement identity changed'
    assert sorted((v.m_Uuid.AsString(), point(v.GetPosition()), v.GetNetCode())
                  for v in reread.GetTracks() if isinstance(v, pcb.PCB_VIA)) == original_vias
    report = {'source_sha256': sha(source), 'candidate_sha256': sha(target),
              'kicad_version': pcb.Version(), 'collinear_segments_removed': merged,
              'arc_count': len(bends), 'bends': bends, 'ownership': dict(ownership),
              'simplified_chains': chains, 'simplify_tolerance_mm': args.simplify_mm,
              'blocked_chains': sorted(blocked_chains),
              'blocked_bends': sorted(blocked), 'pad_partitions_before': original_partitions,
              'pad_partitions_after': final_partitions,
              'partitions_equal': final_partitions == original_partitions,
              'footprints_pads_and_vias_preserved': True,
              'native_DRC_pending': True}
    (WORK / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('collinear_segments_removed', 'arc_count', 'partitions_equal')}), flush=True)


if __name__ == '__main__':
    main()
