from dataclasses import dataclass
import math

@dataclass
class Object:
    kind: str
    x: float
    y: float
    w: float
    h: float
    confidence: float
    vx: float = -300.
    track: int = -1

@dataclass
class Player:
    x: float
    y: float
    w: float = 34.
    h: float = 54.
    vy: float = 0.
    airborne: bool = False

@dataclass
class Decision:
    action: str
    duration: float
    risk: float
    ttc: float

class Planner:
    """Forward simulation in normalized 960px coordinates, with uncertainty cost."""
    def __init__(self, config):
        self.c = config

    def choose(self, player, objects, ground):
        hazards = [o for o in objects if o.kind in ('obstacle','hole','unknown')]
        ttc = min((max(0., (o.x-player.x-player.w)/max(1.,-o.vx))
                   for o in hazards if o.x+o.w>player.x), default=math.inf)
        choices = [('run',0.), ('slide',.25), ('slide',.65)]
        if not player.airborne:
            choices += [('jump',.08),('jump',.22),('double_jump',.32)]
        scored=[]
        for action,duration in choices:
            y,vy=player.y,player.vy
            if action in ('jump','double_jump'): vy=-self.c['jump_velocity']
            risk=0.; reward=0.
            for i in range(1,int(self.c['horizon']/.025)+1):
                t=i*.025
                if action=='double_jump' and i==13: vy=-self.c['jump_velocity']
                vy+=self.c['gravity']*.025
                y=min(ground-player.h,y+vy*.025)
                if y>=ground-player.h: vy=0.
                height=player.h*.5 if action=='slide' and t<=duration else player.h
                top=y+player.h-height
                for o in objects:
                    left=o.x+o.vx*t
                    overlap=left<player.x+player.w and left+o.w>player.x
                    if not overlap: continue
                    collision=(top+height>=ground-5) if o.kind=='hole' else (top<o.y+o.h and top+height>o.y)
                    if collision:
                        if o.kind=='jelly': reward+=.001*o.confidence
                        else: risk+=max(.3,o.confidence)*math.exp(-t)*.025
            cost=risk-reward+(.003 if action!='run' else 0.)
            scored.append((cost,Decision(action,duration,risk,ttc)))
        return min(scored,key=lambda v:v[0])[1]

class Tracker:
    def __init__(self):
        self.previous=[]; self.counter=0
    def update(self, objects, dt):
        dt=max(.001,min(dt,.5)); used=set()
        for o in objects:
            matches=[p for p in self.previous if p.track not in used and p.kind==o.kind
                     and abs((p.x+p.vx*dt)-o.x)<80 and abs(p.y-o.y)<35]
            if matches:
                p=min(matches,key=lambda p:abs(p.x+p.vx*dt-o.x))
                o.vx=.6*p.vx+.4*(o.x-p.x)/dt; o.track=p.track
                used.add(p.track)
                o.confidence=min(.95,.6*o.confidence+.4*p.confidence+.04)
            else:
                self.counter+=1; o.track=self.counter
            o.confidence=max(0.,min(1.,o.confidence))
        self.previous=objects
        return objects

class InputScheduler:
    """Edges only. Clear all scheduled actions on stop/focus loss."""
    def __init__(self, backend, jump='capslock', slide='enter'):
        self.b=backend; self.keys={'jump':jump,'slide':slide}; self.held={}; self.events=[]; self.busy_until=0.
    def tick(self, now):
        pending=[]
        for due,key,down in self.events:
            if due>now: pending.append((due,key,down)); continue
            if down:
                self.b.key(key,True); self.held[key]=True
            elif key in self.held:
                self.b.key(key,False); self.held.pop(key,None)
        self.events=pending
    def request(self, decision, now):
        self.tick(now)
        if now<self.busy_until or decision.action=='run': return False
        self.release()
        key=self.keys['slide' if decision.action=='slide' else 'jump']
        self.b.key(key,True); self.held[key]=True
        hold=decision.duration if decision.action=='slide' else min(decision.duration,.22)
        self.events=[(now+hold,key,False)]
        if decision.action=='double_jump':
            self.events += [(now+.32,key,True),(now+.40,key,False)]
        self.busy_until=now+(max(.5,decision.duration) if decision.action!='slide' else decision.duration+.05)
        return True
    def release(self):
        try:
            for key in list(self.held): self.b.key(key,False)
        finally:
            self.held.clear(); self.events.clear()
