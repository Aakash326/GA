"""Check/start the phone test without printing secrets; no call is placed."""
import argparse, importlib.util, json, os, secrets, subprocess, sys
from pathlib import Path
from dotenv import load_dotenv
P=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',action='store_true');ap.add_argument('--init-token',action='store_true');args=ap.parse_args()
    load_dotenv(P/'.env')
    if args.init_token and not os.getenv('CALL_ACCESS_TOKEN','').strip():
        token=secrets.token_urlsafe(24)
        from dotenv import set_key
        set_key(P/'.env','CALL_ACCESS_TOKEN',token)
        os.environ['CALL_ACCESS_TOKEN']=token
        print('Private call access token configured in .env; value omitted.')
    required=['GNANI_API_KEY','GEMINI_API_KEY','CALL_ACCESS_TOKEN']
    checks={key:bool(os.getenv(key,'').strip()) for key in required}
    snapshot=P/'results/reconciliation/gnani_latest.json'
    checks['reconciled_gnani_spend']=snapshot.exists() or bool(os.getenv('CALL_SPENT_TO_DATE_INR','').strip())
    checks['GNANI_LIVE_1']=os.getenv('GNANI_LIVE')=='1'
    python=P/'call_test/.venv/Scripts/python.exe';checks['call_environment_exists']=python.exists()
    print(json.dumps({'checks':checks,'ready_to_start':all(checks.values()),'calls_placed':0}))
    if args.start:
        if not all(checks.values()):raise SystemExit('Complete the missing checks in .env or the reconciliation workflow first.')
        subprocess.run([str(python),str(P/'call_test/gnani_call_bot.py')],cwd=P,check=True)
if __name__=='__main__':main()
