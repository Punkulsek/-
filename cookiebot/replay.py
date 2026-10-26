"""Offline video analysis: never sends inputs. JSONL contains predicted actions only."""
import argparse,json,time
from pathlib import Path
import cv2
from .vision import Vision
from .core import Planner
from .app import load_config

def main():
    p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('--output',default='replay.jsonl');a=p.parse_args()
    cap=cv2.VideoCapture(a.video)
    if not cap.isOpened():raise RuntimeError('Cannot open video: '+a.video)
    c=load_config();v=Vision(c);planner=Planner(c);fps=cap.get(cv2.CAP_PROP_FPS) or 30;count=0;start=time.perf_counter()
    try:
        with open(a.output,'w',encoding='utf-8') as f:
            while True:
                ok,frame=cap.read()
                if not ok:break
                _,player,objects,ground,confidence=v.process(frame,1/fps)
                decision=planner.choose(player,objects,ground)
                row=dict(frame=count,time=count/fps,player_confidence=confidence,action=decision.action,risk=decision.risk,objects=[vars(o) for o in objects])
                f.write(json.dumps(row)+'\n');count+=1
    finally:cap.release()
    if count==0:raise RuntimeError('Video contains no decodable frames')
    print(json.dumps(dict(frames=count,processing_fps=count/(time.perf_counter()-start),output=a.output)))
if __name__=='__main__':main()
