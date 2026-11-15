"""Dependency-free call instrumentation; server timings do not imply caller-side playback timing."""
import json, time
from pathlib import Path
def event(folder, name, **fields):
    if folder is None:return
    record={'event':name,'monotonic_s':time.monotonic(),**fields}
    with (Path(folder)/'events.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(record)+'\n')

class TurnEvidence:
    def __init__(self, folder):
        self.folder=folder;self.bot_active=False;self.interruption_at=None
    def record(self,name,at=None):
        at=time.monotonic() if at is None else at
        extra={}
        if name=='user_started' and self.bot_active:
            self.interruption_at=at;event(self.folder,'barge_in_started',server_time_s=at)
        elif name=='interruption':
            if self.interruption_at is not None:extra['since_user_started_ms']=round((at-self.interruption_at)*1000,1)
        elif name=='bot_started':self.bot_active=True
        elif name=='bot_stopped':
            self.bot_active=False
            if self.interruption_at is not None:
                extra['server_stop_after_barge_in_ms']=round((at-self.interruption_at)*1000,1);self.interruption_at=None
        event(self.folder,name,server_time_s=at,**extra)
