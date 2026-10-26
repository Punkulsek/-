import json
from pathlib import Path
import numpy as np
import cv2
from cookiebot.core import *
from cookiebot.vision import Vision,Menu
from cookiebot.storage import Store,evaluate_candidate
C=json.loads((Path(__file__).parents[1]/'config.json').read_text())

def test_floor_obstacle_jump():
    d=Planner(C).choose(Player(210,383),[Object('obstacle',330,390,40,47,.9)],437)
    assert d.action in ('jump','double_jump')

def test_overhead_slide():
    d=Planner(C).choose(Player(210,383),[Object('obstacle',280,365,100,40,.9)],437)
    assert d.action=='slide'

def test_jelly_not_hazard():
    assert Planner(C).choose(Player(210,383),[Object('jelly',290,390,15,15,.9)],437).risk==0

def test_no_airborne_jump():
    assert Planner(C).choose(Player(210,300,vy=-100,airborne=True),[Object('hole',300,437,90,100,.9)],437).action not in ('jump','double_jump')

def test_hole_jump():
    assert Planner(C).choose(Player(210,383),[Object('hole',310,437,90,100,.9)],437).action in ('jump','double_jump')

class Fake:
    def __init__(self):self.events=[]
    def key(self,k,d):self.events.append((k,d))

def test_edges_and_stop():
    b=Fake();s=InputScheduler(b);d=Decision('jump',.08,0,0)
    s.request(d,0);s.request(d,.01);s.tick(.1);s.release()
    assert b.events==[('capslock',True),('capslock',False)]

def test_double_jump_cancel():
    b=Fake();s=InputScheduler(b);s.request(Decision('double_jump',.32,0,0),0);s.release();s.tick(1)
    assert b.events==[('capslock',True),('capslock',False)]

def test_transition():
    b=Fake();s=InputScheduler(b);s.request(Decision('slide',.25,0,0),0);s.request(Decision('jump',.08,0,0),.31);s.tick(1)
    assert b.events==[('enter',True),('enter',False),('capslock',True),('capslock',False)]

def test_tracking_velocity():
    t=Tracker();a=t.update([Object('obstacle',500,380,40,40,.7)],.1)[0]
    b=t.update([Object('obstacle',470,380,40,40,.7)],.1)[0]
    assert a.track==b.track and b.vx==-300

def test_free_menu_confirmation():
    m=Menu();lines=[('free retry',.99,[[0,0],[100,0],[100,40],[0,40]])]
    assert m.classify(lines)[1] is None
    assert m.classify(lines)[1] is None
    assert m.classify(lines)==('result',(50.,20.))

def test_paid_menu_blocks():
    assert Menu().classify([('buy crystals',.99,[])])==('payment',None)

def test_unknown_menu_blocks():assert Menu().classify([])==('unknown',None)

def test_blank_frame_no_player():
    _,_,_,_,confidence=Vision(C).process(np.zeros((540,960,3),dtype=np.uint8),.033)
    assert confidence==0

def test_synthetic_jelly_pattern():
    im=np.zeros((540,960,3),np.uint8)
    for x in (400,440,480):cv2.circle(im,(x,300),8,(255,255,255),-1)
    _,_,objects,_,_=Vision(C).process(im,.033)
    assert len([o for o in objects if o.kind=='jelly'])==3
    assert not any(o.kind=='obstacle' for o in objects)

def test_store(tmp_path):
    s=Store(tmp_path/'r.db');s.frame({'collision':None});s.finish(10,'stopped');assert s.stats()==(1,10.,10.);s.close()

def test_unverified_policy_rejected():
    base=[dict(scenario=str(i),verified=True,survival=10,collisions=1) for i in range(30)]
    candidate=[dict(x,survival=12,verified=False) for x in base]
    assert not evaluate_candidate(base,candidate)
    assert evaluate_candidate(base,[dict(x,survival=12) for x in base])
