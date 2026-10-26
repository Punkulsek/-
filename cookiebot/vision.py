import cv2
import numpy as np
from .core import Object,Player,Tracker

class Vision:
    """Untrained motion/geometry baseline; labels are hypotheses, not game semantics."""
    def __init__(self, config):
        self.c=config; self.prev=None; self.tracker=Tracker(); self.last_y=None
    def process(self, image, dt):
        image=cv2.resize(image,(960,540)); gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        ground=int(self.c['ground_y']*540); px=int(self.c['player_x']*960)
        edges=cv2.Canny(gray,70,150)
        mask=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        objects=[]; candidates=[]
        for c in contours:
            x,y,w,h=cv2.boundingRect(c)
            if w<5 or h<5 or w>220 or h>230 or y<70 or y>ground: continue
            area=cv2.contourArea(c); solidity=area/max(1,w*h)
            if abs(x+w/2-px)<65 and h>28 and y+h>ground-160:
                candidates.append((x,y,w,h)); continue
            if x<px+20: continue
            motion=0.
            if self.prev is not None:
                motion=float(np.mean(cv2.absdiff(gray[y:y+h,x:x+w],self.prev[y:y+h,x:x+w])))/255
            roundness=4*np.pi*area/max(1,cv2.arcLength(c,True)**2)
            # Compact repeated shapes are only tentative collectibles.
            jelly=8<=w<=26 and 8<=h<=26 and roundness>.55 and solidity>.45
            kind='jelly' if jelly else ('obstacle' if h>30 and motion>.035 else 'unknown')
            confidence=.55 if jelly else (.65 if kind=='obstacle' else .3)
            objects.append(Object(kind,x,y,w,h,confidence))
        # Repeated compact shapes strengthen the jelly hypothesis.
        for o in objects:
            if o.kind=='jelly' and sum(p.kind=='jelly' and abs(p.w-o.w)<5 and abs(p.h-o.h)<5 for p in objects)>=3:
                o.confidence=.72
            elif o.kind=='jelly': o.kind='unknown'; o.confidence=.3
        # Ground discontinuity needs visible support on both sides.
        band=edges[max(0,ground-5):ground+6,:]
        support=np.mean(band>0,axis=0)>.15
        support=cv2.morphologyEx(support.astype(np.uint8)[None,:],cv2.MORPH_CLOSE,np.ones((1,15),np.uint8))[0]
        borders=np.flatnonzero(np.diff(np.r_[1,support,1]))
        for a,b in zip(borders[::2],borders[1::2]):
            if a>px and 25<b-a<400 and a>5 and b<950 and support[a-5:a].any() and support[b:b+5].any():
                objects.append(Object('hole',float(a),ground,float(b-a),540-ground,.55))
        if candidates:
            x,y,w,h=min(candidates,key=lambda b:abs(b[0]+b[2]/2-px)+abs(b[1]+b[3]-ground)*.3)
            vy=0. if self.last_y is None else (y-self.last_y)/max(dt,.001)
            player=Player(x,y,w,h,vy,y+h<ground-12); self.last_y=y
            confidence=.7
        else:
            player=Player(px,ground-54); confidence=0.; self.last_y=None
        self.prev=gray
        return image,player,self.tracker.update(objects,dt),ground,confidence

class Menu:
    """OCR navigation is restricted to explicitly FREE start/retry buttons."""
    def __init__(self): self.engine=None; self.last=None; self.stable=0
    def read(self,image):
        if self.engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self.engine=RapidOCR()
        result,_=self.engine(image)
        return [(str(text).lower(),float(score),box) for box,text,score in (result or [])]
    def classify(self, lines):
        text=' '.join(t for t,s,b in lines if s>.85)
        if any(t in text for t in ['purchase','buy','payment','crystal','diamond','구매','결제','보석']):
            self.last=None; self.stable=0; return 'payment',None
        choices=[]
        for t,s,b in lines:
            if s>.92 and t.strip() in ('free start','free retry','free restart','무료 시작','무료 재시작'):
                choices.append((t,b))
        if len(choices)!=1:
            self.last=None; self.stable=0
            return ('loading' if 'loading' in text else 'unknown'),None
        t,b=choices[0]; center=(sum(p[0] for p in b)/4,sum(p[1] for p in b)/4)
        signature=(t,round(center[0]/10),round(center[1]/10))
        self.stable=self.stable+1 if signature==self.last else 1; self.last=signature
        return ('result' if 'retry' in t or 'restart' in t or '재시작' in t else 'main'), center if self.stable>=3 else None
