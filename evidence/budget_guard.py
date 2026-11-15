"""Conservative INR reservations for future Gnani requests, not verified provider billing."""
import json, math, os, threading, uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
LOCK=threading.Lock()
@contextmanager
def file_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_suffix('.lock').open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)
def reserve(project, kind, units, attempts=1):
    if not math.isfinite(units) or units<0 or attempts<1:raise ValueError('Invalid usage units or attempt count')
    amount=units*(.03/3.6 if kind=='asr' else .11/61)*attempts*1.2
    return reserve_fixed(project,amount,kind=kind,units=units)

def reserve_fixed(project, amount, *, kind='call', units=None, prior_override=None):
    snapshot=Path(project)/'results/reconciliation/gnani_latest.json'
    candidates=[]
    if snapshot.exists():
        reading=json.loads(snapshot.read_text())
        if str(reading.get('covers_all_evaluation_usage')).lower()=='true':candidates.append(float(reading['observed_spend_inr']))
    supplied=prior_override if prior_override is not None else os.getenv('GNANI_SPENT_TO_DATE_INR')
    if supplied is not None and str(supplied).strip():candidates.append(float(supplied))
    if not candidates:raise RuntimeError('Import a complete Gnani dashboard reading or set reconciled prior spend before new calls')
    if any(not math.isfinite(v) or v<0 for v in [amount,*candidates]):raise ValueError('Usage and balances must be finite and non-negative')
    prior=max(candidates)
    path=Path(project)/'results/budget_reservations.json'
    with LOCK, file_lock(path):
        ledger=json.loads(path.read_text()) if path.exists() else {'prior_spend_inr':prior,'reserved_inr':0,'requests':[]}
        ledger['prior_spend_inr']=max(prior,ledger['prior_spend_inr'])
        if ledger['prior_spend_inr']+ledger['reserved_inr']+amount>500:raise RuntimeError('INR 500 planning ceiling reached')
        ledger['reserved_inr']+=amount
        reservation={'reservation_id':uuid.uuid4().hex,'created_at_utc':datetime.now(timezone.utc).isoformat(),
                     'kind':kind,'units':units,'reserved_inr':amount}
        ledger['requests'].append(reservation)
        path.parent.mkdir(exist_ok=True)
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(ledger,indent=2));temp.replace(path)
        return reservation['reservation_id']
