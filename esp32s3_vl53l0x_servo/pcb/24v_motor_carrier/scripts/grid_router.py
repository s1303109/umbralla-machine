"""Deterministic two-layer draft PCB grid router (standard library only).

This is a routing aid, not a replacement for KiCad DRC. ``route_board(spec)``
returns only newly created tracks/vias; supplied fixed geometry stays untouched.
Coordinates, diameters and widths are millimetres. Layers are 0 (F.Cu) and 1
(B.Cu). Four-direction paths avoid diagonal corner-cutting. Optional rectangular
pads accept shape='rect', width and height; otherwise pads are circular.

Optional knobs: net_order, max_expansions (per connection), time_limit_s (whole
call), edge_clearance, via_cost and fixed_vias. Netless pads are obstacles.
"""
from collections import deque
import heapq
import math
import time


def _net(value):
    return str(value) if value not in (None, '') else None


class _Grid:
    def __init__(self, spec):
        self.spec = spec
        self.x0, self.y0, self.x1, self.y1 = map(float, spec['bounds'])
        self.pitch = float(spec.get('grid', .254))
        self.nx = int(math.floor((self.x1-self.x0)/self.pitch))+1
        self.ny = int(math.floor((self.y1-self.y0)/self.pitch))+1
        self.n = self.nx*self.ny
        self.xs = [self.x0+i*self.pitch for i in range(self.nx)]
        self.ys = [self.y0+i*self.pitch for i in range(self.ny)]
        self.pads = [dict(p, net=_net(p.get('net'))) for p in spec.get('pads', [])]
        self.tracks = [dict(t, net=_net(t.get('net'))) for t in spec.get('fixed_tracks', [])]
        self.vias = [dict(v, net=_net(v.get('net'))) for v in spec.get('fixed_vias', [])]
        self.keepouts = spec.get('keepouts', [])
        self.clear = float(spec.get('clearance', .2))
        self.via_d = float(spec.get('via_diameter', .6))
        self.via_drill = float(spec.get('via_drill', .3))
        self.new_tracks, self.new_vias = [], []
        self.started = time.monotonic()
        self.deadline = self.started+float(spec.get('time_limit_s', 180))
        self.expansions = 0
        self.connection_attempts = 0
        self.connection_successes = 0

    def ij(self, x, y):
        return max(0, min(self.nx-1, round((x-self.x0)/self.pitch))), max(0, min(self.ny-1, round((y-self.y0)/self.pitch)))

    def index(self, x, y):
        i, j = self.ij(x, y)
        return j*self.nx+i

    def xy(self, index):
        return self.xs[index % self.nx], self.ys[index//self.nx]

    def ranges(self, x0, y0, x1, y1):
        i0 = max(0, int(math.floor((x0-self.x0)/self.pitch)))
        i1 = min(self.nx-1, int(math.ceil((x1-self.x0)/self.pitch)))
        j0 = max(0, int(math.floor((y0-self.y0)/self.pitch)))
        j1 = min(self.ny-1, int(math.ceil((y1-self.y0)/self.pitch)))
        return range(i0, i1+1), range(j0, j1+1)

    def paint_circle(self, mask, x, y, radius):
        ii, jj = self.ranges(x-radius, y-radius, x+radius, y+radius)
        rr = radius*radius
        for j in jj:
            dy = self.ys[j]-y
            remain = rr-dy*dy
            if remain < 0:
                continue
            row = j*self.nx
            for i in ii:
                if (self.xs[i]-x)**2 <= remain:
                    mask[row+i] = 1

    def paint_rect(self, mask, x0, y0, x1, y1):
        ii, jj = self.ranges(x0, y0, x1, y1)
        for j in jj:
            if y0 <= self.ys[j] <= y1:
                row = j*self.nx
                for i in ii:
                    if x0 <= self.xs[i] <= x1:
                        mask[row+i] = 1

    def paint_segment(self, mask, t, radius):
        x0, y0, x1, y1 = [float(t[k]) for k in ('x1', 'y1', 'x2', 'y2')]
        ii, jj = self.ranges(min(x0,x1)-radius, min(y0,y1)-radius, max(x0,x1)+radius, max(y0,y1)+radius)
        dx, dy = x1-x0, y1-y0
        ll = dx*dx+dy*dy
        rr = radius*radius
        for j in jj:
            py = self.ys[j]
            row = j*self.nx
            for i in ii:
                px = self.xs[i]
                f = max(0.,min(1.,((px-x0)*dx+(py-y0)*dy)/ll)) if ll else 0.
                if (px-x0-f*dx)**2+(py-y0-f*dy)**2 <= rr:
                    mask[row+i] = 1

    def paint_pad(self, mask, p, extra):
        diameter = float(p.get('diameter', 1.8))
        if str(p.get('shape', '')).lower() in ('rect', 'rectangle', 'roundrect'):
            w, h = float(p.get('width', diameter)), float(p.get('height', diameter))
            self.paint_rect(mask, p['x']-w/2-extra, p['y']-h/2-extra, p['x']+w/2+extra, p['y']+h/2+extra)
        else:
            self.paint_circle(mask, p['x'], p['y'], diameter/2+extra)

    def masks(self, net, width):
        trace = [bytearray(self.n), bytearray(self.n)]
        via = [bytearray(self.n), bytearray(self.n)]
        trace_extra = self.clear+width/2+.02
        via_extra = self.clear+self.via_d/2+.02
        for p in self.pads:
            if p['net'] != net:
                for mask in trace:
                    self.paint_pad(mask, p, trace_extra)
                for mask in via:
                    self.paint_pad(mask, p, via_extra)
        for t in self.tracks:
            if t['net'] != net:
                layer = int(t['layer'])
                other = float(t.get('width',.254))/2
                self.paint_segment(trace[layer], t, other+trace_extra)
                self.paint_segment(via[layer], t, other+via_extra)
        for v in self.vias:
            if v['net'] != net:
                other = float(v.get('diameter', self.via_d))/2
                for masks, extra in ((trace, trace_extra),(via,via_extra)):
                    for mask in masks:
                        self.paint_circle(mask, v['x'], v['y'], other+extra)
        for k in self.keepouts:
            layers = k.get('layers',[0,1])
            for masks, extra in ((trace,width/2),(via,self.via_d/2)):
                for layer in layers:
                    self.paint_rect(masks[int(layer)],float(k['xmin'])-extra,float(k['ymin'])-extra,float(k['xmax'])+extra,float(k['ymax'])+extra)
        for masks, radius in ((trace,width/2),(via,self.via_d/2)):
            border = radius+float(self.spec.get('edge_clearance',self.clear))
            for j,y in enumerate(self.ys):
                row = j*self.nx
                for i,x in enumerate(self.xs):
                    if x < self.x0+border or x > self.x1-border or y < self.y0+border or y > self.y1-border:
                        masks[0][row+i] = masks[1][row+i] = 1
        combined_via = bytearray(a|b for a,b in zip(via[0],via[1]))
        return trace, combined_via

    def line_nodes(self, t):
        i0,j0 = self.ij(t['x1'], t['y1'])
        i1,j1 = self.ij(t['x2'], t['y2'])
        steps = max(abs(i1-i0), abs(j1-j0))
        layer = int(t['layer'])*self.n
        if not steps:
            return {layer+j0*self.nx+i0}
        return {layer+round(j0+(j1-j0)*s/steps)*self.nx+round(i0+(i1-i0)*s/steps) for s in range(steps+1)}

    def initial_network(self, net, pads):
        existing = set()
        vertical = set()
        # Copper inside a through-hole pad is connected on both layers.
        for p in pads:
            mask = bytearray(self.n)
            self.paint_pad(mask,p,0.)
            cells = {i for i,v in enumerate(mask) if v}
            cells.add(self.index(p['x'],p['y']))
            existing.update(cells)
            existing.update(i+self.n for i in cells)
            vertical.update(cells)
        for t in self.tracks:
            if t['net']==net:
                existing.update(self.line_nodes(t))
        for v in self.vias:
            if v['net']==net:
                index = self.index(v['x'],v['y'])
                existing.update((index,index+self.n));vertical.add(index)
        return existing, vertical

    def grow(self, existing, vertical, connected, seeds):
        queue = deque(seeds)
        while queue:
            state = queue.popleft()
            if state in connected or state not in existing:
                continue
            connected.add(state)
            layer,index = divmod(state,self.n)
            i,j = index%self.nx,index//self.nx
            if i: queue.append(state-1)
            if i+1<self.nx: queue.append(state+1)
            if j: queue.append(state-self.nx)
            if j+1<self.ny: queue.append(state+self.nx)
            if index in vertical: queue.append((1-layer)*self.n+index)

    def nearest(self, start_index, goals):
        sx,sy = start_index%self.nx,start_index//self.nx
        return min(goals,key=lambda s:(abs(s%self.n%self.nx-sx)+abs((s%self.n)//self.nx-sy),s))

    def astar(self, start_index, goals, goal_hint, trace, via, vertical):
        self.connection_attempts += 1
        gx,gy = goal_hint%self.n%self.nx,(goal_hint%self.n)//self.nx
        def heuristic(index):
            return 10*(abs(index%self.nx-gx)+abs(index//self.nx-gy))
        queue = []
        gscore, parent = {}, {}
        for layer in (0,1):
            if not trace[layer][start_index]:
                state=layer*self.n+start_index
                gscore[state]=0;parent[state]=-1
                heapq.heappush(queue,(heuristic(start_index),0,state))
        max_expansions = int(self.spec.get('max_expansions',300000))
        count = 0
        while queue:
            _,cost,state=heapq.heappop(queue)
            if gscore.get(state)!=cost:
                continue
            if state in goals:
                path=[]
                while state!=-1:
                    path.append(state);state=parent[state]
                self.expansions += count
                self.connection_successes += 1
                return path[::-1],None
            count+=1
            if count>=max_expansions or (count%1024==0 and time.monotonic()>self.deadline):
                self.expansions += count
                return None,'expansion_limit' if count>=max_expansions else 'time_limit'
            layer,index=divmod(state,self.n)
            i,j=index%self.nx,index//self.nx
            neighbors=[]
            # Cheap preferred directions: horizontal F.Cu, vertical B.Cu.
            hcost,vcost=(10,13) if layer==0 else (13,10)
            if i: neighbors.append((state-1,index-1,hcost))
            if i+1<self.nx: neighbors.append((state+1,index+1,hcost))
            if j: neighbors.append((state-self.nx,index-self.nx,vcost))
            if j+1<self.ny: neighbors.append((state+self.nx,index+self.nx,vcost))
            for nxt,ni,increment in neighbors:
                if trace[layer][ni]: continue
                new_cost=cost+increment
                if new_cost < gscore.get(nxt,math.inf):
                    gscore[nxt]=new_cost;parent[nxt]=state
                    heapq.heappush(queue,(new_cost+heuristic(ni),new_cost,nxt))
            if index in vertical or not via[index]:
                nxt=(1-layer)*self.n+index
                if not trace[1-layer][index]:
                    new_cost=cost+(1 if index in vertical else int(self.spec.get('via_cost',65)))
                    if new_cost < gscore.get(nxt,math.inf):
                        gscore[nxt]=new_cost;parent[nxt]=state
                        heapq.heappush(queue,(new_cost+heuristic(index),new_cost,nxt))
        self.expansions+=count
        return None,'no_path'

    def emit(self, net, width, states, vertical):
        if len(states)<2: return
        # Emit maximal straight segments and a via at each real layer change.
        begin=states[0];last=states[0];direction=None
        via_keys={(v['net'],round(v['x'],6),round(v['y'],6)) for v in self.vias}
        def segment(a,b):
            la,ia=divmod(a,self.n);lb,ib=divmod(b,self.n)
            if ia==ib or la!=lb: return
            x0,y0=self.xy(ia);x1,y1=self.xy(ib)
            item={'net':net,'layer':la,'x1':x0,'y1':y0,'x2':x1,'y2':y1,'width':width}
            self.tracks.append(item);self.new_tracks.append(item)
        for state in states[1:]:
            layer,index=divmod(state,self.n)
            old_layer,old_index=divmod(last,self.n)
            if layer!=old_layer:
                segment(begin,last)
                if index not in vertical:
                    x,y=self.xy(index);key=(net,round(x,6),round(y,6))
                    if key not in via_keys:
                        v={'net':net,'x':x,'y':y,'diameter':self.via_d,'drill':self.via_drill}
                        self.vias.append(v);self.new_vias.append(v);via_keys.add(key)
                    vertical.add(index)
                begin=state;direction=None
            else:
                step=index-old_index
                if direction is not None and direction!=step:
                    segment(begin,last);begin=last
                direction=step
            last=state
        segment(begin,last)

    def run(self):
        nets={}
        for p in self.pads:
            if p['net'] is not None: nets.setdefault(p['net'],[]).append(p)
        widths=self.spec.get('net_widths',{})
        priority={str(n):i for i,n in enumerate(self.spec.get('net_order',[]))}
        order=sorted(nets,key=lambda n:(priority.get(n,len(priority)), -float(widths.get(n,.254)), -len(nets[n]),n))
        unrouted=[]
        net_stats={}
        for net in order:
            pads=sorted(nets[net],key=lambda p:(str(p.get('id','')),p['x'],p['y']))
            if len(pads)<2: continue
            width=float(widths.get(net,.254))
            trace,via=self.masks(net,width)
            existing,vertical=self.initial_network(net,pads)
            seed=self.index(pads[0]['x'],pads[0]['y'])
            connected=set();self.grow(existing,vertical,connected,[seed,seed+self.n])
            failed=set()
            before=len(self.new_tracks)
            while True:
                pending=[p for p in pads if self.index(p['x'],p['y']) not in connected and self.index(p['x'],p['y'])+self.n not in connected and str(p.get('id','')) not in failed]
                if not pending: break
                if time.monotonic()>self.deadline:
                    for p in pending:
                        unrouted.append({'net':net,'pad_id':p.get('id'),'reason':'time_limit','x':p['x'],'y':p['y']})
                        failed.add(str(p.get('id','')))
                    break
                choices=[]
                for p in pending:
                    start=self.index(p['x'],p['y']);goal=self.nearest(start,connected)
                    sx,sy=start%self.nx,start//self.nx
                    gx,gy=goal%self.n%self.nx,(goal%self.n)//self.nx
                    choices.append((abs(sx-gx)+abs(sy-gy),str(p.get('id','')),p,start,goal))
                _,_,p,start,goal=min(choices,key=lambda x:x[:2])
                states,reason=self.astar(start,connected,goal,trace,via,vertical)
                if states is None:
                    failed.add(str(p.get('id','')))
                    unrouted.append({'net':net,'pad_id':p.get('id'),'reason':reason,'x':p['x'],'y':p['y']})
                    continue
                self.emit(net,width,states,vertical)
                existing.update(states)
                self.grow(existing,vertical,connected,states)
            # A later successful connection can incidentally connect a failed pad.
            unresolved=[]
            for p in pads:
                start=self.index(p['x'],p['y'])
                if start not in connected and start+self.n not in connected: unresolved.append(str(p.get('id','')))
            unrouted=[u for u in unrouted if u['net']!=net or str(u['pad_id']) in unresolved]
            net_stats[net]={'pads':len(pads),'unconnected_pads':len(unresolved),'new_track_segments':len(self.new_tracks)-before}
        return {'tracks':self.new_tracks,'vias':self.new_vias,'unrouted':unrouted,
                'stats':{'grid':self.pitch,'grid_cells_per_layer':self.n,'connection_attempts':self.connection_attempts,
                         'connection_successes':self.connection_successes,'expansions':self.expansions,
                         'elapsed_s':round(time.monotonic()-self.started,3),'net_stats':net_stats}}


def route_board(spec):
    """Route supplied pad nets on two copper layers; return new geometry only."""
    if len(spec.get('bounds',[]))!=4:
        raise ValueError('bounds must be [xmin,ymin,xmax,ymax]')
    return _Grid(spec).run()


if __name__=='__main__':
    import json
    import sys
    if len(sys.argv)!=3:
        raise SystemExit('usage: grid_router.py input.json output.json')
    with open(sys.argv[1],encoding='utf-8') as f: spec=json.load(f)
    result=route_board(spec)
    with open(sys.argv[2],'w',encoding='utf-8') as f: json.dump(result,f,indent=2)
    print(json.dumps({'tracks':len(result['tracks']),'vias':len(result['vias']),'unrouted':len(result['unrouted']),'stats':result['stats']}))
