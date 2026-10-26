import json, sqlite3, time
from pathlib import Path

class Store:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS frames(t REAL, session TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS runs(session TEXT, seconds REAL, outcome TEXT, score REAL);
        CREATE TABLE IF NOT EXISTS policies(id INTEGER PRIMARY KEY, data TEXT, status TEXT, evidence TEXT);''')
        self.session=str(time.time_ns()); self.count=0
    def frame(self,data):
        self.db.execute('INSERT INTO frames VALUES(?,?,?)',(time.time(),self.session,json.dumps(data))); self.count+=1
        if self.count%30==0:self.db.commit()
    def finish(self,seconds,outcome):
        self.db.execute('INSERT INTO runs VALUES(?,?,?,NULL)',(self.session,seconds,outcome)); self.db.commit()
    def stats(self):
        return self.db.execute('SELECT COUNT(*),COALESCE(AVG(seconds),0),COALESCE(MAX(seconds),0) FROM runs').fetchone()
    def close(self): self.db.commit(); self.db.close()

def evaluate_candidate(baseline,candidate,min_samples=30):
    """Paired observed outcomes only. Never turn failure into a detection label.
    Records must have matching scenario IDs and externally measured outcomes.
    Offline trajectory scores alone cannot establish causal game improvement.
    """
    if len(baseline)<min_samples or len(baseline)!=len(candidate): return False
    if any(a['scenario']!=b['scenario'] for a,b in zip(baseline,candidate)): return False
    if any(not r.get('verified',False) for r in baseline+candidate): return False
    if sum(r['collisions'] for r in candidate)>sum(r['collisions'] for r in baseline): return False
    return sum(r['survival'] for r in candidate)>sum(r['survival'] for r in baseline)*1.05
