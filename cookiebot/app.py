import argparse, json, logging, os, sys, threading, time, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def setup_logging():
    for name in ('logs','crash_logs','recordings'): (ROOT/name).mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT/'logs/run.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')

def load_config():
    c=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    if not 1<=c['fps']<=120: raise ValueError('fps must be 1..120')
    if not .05<c['player_x']<.8 or not .2<c['ground_y']<.98: raise ValueError('Invalid normalized game geometry')
    for k in ('jump_key','slide_key'):
        if c[k] not in ('capslock','enter','space'): raise ValueError('Unsupported key: '+c[k])
    if c['jump_key']==c['slide_key']: raise ValueError('Jump and slide keys must differ')
    return c

def check():
    import cv2,numpy,mss
    from rapidocr_onnxruntime import RapidOCR
    import tkinter
    c=load_config()
    print('Python:',sys.version,'Platform:',sys.platform)
    print('OpenCV:',cv2.__version__,'NumPy:',numpy.__version__)
    print('Configuration: OK; OCR engine initialization ...')
    engine=RapidOCR(); engine(numpy.zeros((100,300,3),dtype=numpy.uint8))
    print('OCR: OK')
    if os.name!='nt': print('Live Windows input and GUI were not validated on this platform.')
    return 0

class Worker:
    def __init__(self,c,hwnd,report):
        self.c=c;self.hwnd=hwnd;self.report=report;self.stop=threading.Event();self.heartbeat=time.monotonic();self.lock=threading.RLock()
    def run(self):
        import cv2, numpy as np, mss
        from .platform import Windows
        from .core import InputScheduler,Planner
        from .vision import Vision,Menu
        from .storage import Store
        backend=Windows(self.c['dry_run']); scheduler=InputScheduler(backend,self.c['jump_key'],self.c['slide_key'])
        vision=Vision(self.c); planner=Planner(self.c); menu=Menu()
        store=Store(ROOT/'recordings/play.sqlite3') if self.c['record'] else None
        start=time.monotonic(); last=start; next_menu=0.;next_click=0.;last_image=0.; outcome='stopped'; state='unknown';point=None; stable_play=0
        def guard():
            while not self.stop.wait(.01):
                try:
                    now=time.monotonic()
                    if backend.emergency() or (ROOT/'STOP').exists() or now-self.heartbeat>1.5:
                        self.stop.set()
                    with self.lock:
                        if self.stop.is_set() or not backend.focused(self.hwnd): scheduler.release()
                        else: scheduler.tick(now)
                except Exception:
                    logging.exception('Input watchdog failed'); self.stop.set()
        watcher=threading.Thread(target=guard,daemon=True);watcher.start()
        try:
            with mss.mss() as cap:
                while not self.stop.is_set():
                    now=time.monotonic();dt=now-last;last=now;self.heartbeat=now
                    region=backend.region(self.hwnd)
                    frame=np.asarray(cap.grab(region))[:,:,:3].copy()
                    stamp=time.monotonic()
                    image,p,objects,ground,confidence=vision.process(frame,dt)
                    moving=sum(o.vx< -40 and o.track>0 and o.confidence>.6 for o in objects)
                    stable_play=stable_play+1 if confidence>=self.c['confidence'] and moving>=2 else 0
                    if stable_play>=5:
                        state='playing';point=None
                    elif now>=next_menu:
                        with self.lock: scheduler.release()
                        state,point=menu.classify(menu.read(image));next_menu=now+1.
                    decision=planner.choose(p,objects,ground)
                    focused=backend.focused(self.hwnd)
                    # Never act on stale frames or after stop, even if OCR returns late.
                    fresh=time.monotonic()-stamp<.15
                    latency=None
                    with self.lock:
                        if self.stop.is_set() or not focused or not fresh or state!='playing' or stable_play<5:
                            scheduler.release()
                        else:
                            before=time.perf_counter();scheduler.request(decision,time.monotonic());latency=(time.perf_counter()-before)*1000
                        if not self.stop.is_set() and focused and state in ('main','result') and point and self.c['auto_restart'] and now>=next_click:
                            backend.click(region['left']+point[0]*region['width']/960,region['top']+point[1]*region['height']/540)
                            next_click=now+5.;point=None;menu.stable=0
                    if state=='payment':
                        outcome='payment_blocked';self.report('유료 재화 관련 화면 감지: 중단');break
                    if store:
                        store.frame(dict(timestamp=stamp,state=state,action=decision.action,risk=decision.risk,ttc=None if decision.ttc==float('inf') else decision.ttc,
                            player=vars(p),objects=[vars(o) for o in objects],input_latency_ms=latency,held=list(scheduler.held),score=None,collision=None))
                        if now-last_image>1.:
                            cv2.imwrite(str(ROOT/'recordings'/f'{store.session}-{int((now-start)*1000)}.jpg'),image);last_image=now
                    colors={'jelly':(0,255,255),'hole':(255,0,255),'obstacle':(0,0,255),'unknown':(150,150,150)}
                    for o in objects:
                        cv2.rectangle(image,(int(o.x),int(o.y)),(int(o.x+o.w),int(o.y+o.h)),colors[o.kind],2)
                        cv2.putText(image,f'{o.kind} {o.confidence:.2f}',(int(o.x),max(15,int(o.y)-4)),0,.4,colors[o.kind],1)
                    cv2.rectangle(image,(int(p.x),int(p.y)),(int(p.x+p.w),int(p.y+p.h)),(0,255,0),2)
                    text=f'{state} {decision.action} FPS {1/max(dt,.001):.1f} TTC {decision.ttc:.2f} dry={self.c["dry_run"]}'
                    cv2.putText(image,text,(10,25),0,.55,(255,255,255),1)
                    self.report(text)
                    if self.c['debug']:
                        cv2.imshow('CookieBot debug (F8 stops)',image)
                        if cv2.waitKey(1)&255==27: self.stop.set()
                    self.stop.wait(max(0.,1/self.c['fps']-(time.monotonic()-now)))
        except Exception:
            outcome='error';logging.exception('Worker failed')
            error=traceback.format_exc();(ROOT/'crash_logs'/f'{time.time_ns()}.txt').write_text(error,encoding='utf-8');self.report(error)
        finally:
            self.stop.set();watcher.join(timeout=2)
            with self.lock:scheduler.release()
            cv2.destroyAllWindows()
            if store:store.finish(time.monotonic()-start,outcome);store.close()
            self.report('정지됨: '+outcome)

def gui():
    import tkinter as tk
    from tkinter import ttk,messagebox
    import queue
    from .platform import Windows
    c=load_config();platform=Windows();root=tk.Tk();root.title('CookieBot — experimental');root.geometry('760x440')
    events=queue.Queue();active=[None];thread=[None];windows=[]
    title=tk.StringVar(value=c['window_title']);selection=tk.StringVar();status=tk.StringVar(value='게임 화면 검증 전: 기본값은 입력 없는 관찰 모드입니다.')
    flags={k:tk.BooleanVar(value=c[k]) for k in ('dry_run','auto_restart','record','debug')}
    ttk.Label(root,text='창 제목 검색').pack();ttk.Entry(root,textvariable=title).pack(fill='x')
    combo=ttk.Combobox(root,textvariable=selection,state='readonly');combo.pack(fill='x')
    def refresh():
        windows[:]=[(h,t) for h,t in platform.windows() if title.get().lower() in t.lower() and 'CookieBot' not in t]
        combo['values']=[f'{h}: {t}' for h,t in windows]
        if windows:combo.current(0)
        else:status.set('일치하는 창이 없습니다. 에뮬레이터 창 제목으로 검색하세요.')
    ttk.Button(root,text='게임 창 검색',command=refresh).pack()
    for key,label in [('dry_run','관찰 모드 (키 입력 안 함)'),('auto_restart','무료 버튼 자동 시작/재시작'),('record','기록 저장'),('debug','디버깅 창')]:
        ttk.Checkbutton(root,text=label,variable=flags[key]).pack(anchor='w')
    def start():
        if thread[0] and thread[0].is_alive():return
        if combo.current()<0:messagebox.showerror('창 선택','게임 창을 먼저 선택하세요.');return
        (ROOT/'STOP').unlink(missing_ok=True)
        config=dict(c,**{k:v.get() for k,v in flags.items()})
        active[0]=Worker(config,windows[combo.current()][0],events.put)
        def guarded_run():
            try: active[0].run()
            except Exception:
                error=traceback.format_exc();logging.exception('Worker initialization failed')
                (ROOT/'crash_logs'/f'{time.time_ns()}.txt').write_text(error,encoding='utf-8');events.put(error)
        thread[0]=threading.Thread(target=guarded_run,daemon=False);thread[0].start()
        status.set('게임 창을 클릭해 포커스를 주세요. F8: 긴급 종료')
    def stop():
        if active[0]:active[0].stop.set()
    def reset():
        stop()
        for k,v in {'dry_run':True,'auto_restart':False,'record':True,'debug':True}.items():flags[k].set(v)
        title.set(c['window_title'])
    ttk.Button(root,text='자동 플레이 시작',command=start).pack();ttk.Button(root,text='정지 (F8)',command=stop).pack()
    ttk.Button(root,text='로그 폴더 열기',command=lambda:os.startfile(ROOT/'logs')).pack()
    ttk.Button(root,text='UI 설정 초기화',command=reset).pack();ttk.Label(root,textvariable=status,wraplength=720).pack(pady=12)
    def poll():
        while not events.empty():status.set(events.get_nowait())
        root.after(100,poll)
    def close():
        stop()
        if thread[0] and thread[0].is_alive(): root.after(100,close)
        else:root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);refresh();poll();root.mainloop()

def main():
    setup_logging()
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    try:return check() if args.check else gui()
    except Exception:
        error=traceback.format_exc();logging.exception('Startup failed')
        (ROOT/'crash_logs'/f'{time.time_ns()}.txt').write_text(error,encoding='utf-8');print(error,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
