"""Bounded Report-4 controlled TTS trial. Paid collection requires --live.

Five successful REST repeats per model/text after separate warm-ups. Failures
remain recorded; at most two replacement trials per cell. Separate warm WS
TTFA trials use only the short prompt and do not redefine REST latency.
"""
import argparse,csv,hashlib,json,os,random,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
O=P/'results/report4';MODELS=[('3','timbre-v3.0','Tarika'),('25','timbre-v2.5','Kaveri')]


def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def logs():
    path=O/'attempts.jsonl'
    return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()] if path.exists() else []


def latest(cid):
    found=[r for r in logs() if r.get('case_id')==cid]
    return found[-1] if found else None


def protocol():
    with (P/'data/tts_cases.csv').open(encoding='utf-8-sig',newline='') as f:source={r['case_id']:r for r in csv.DictReader(f)}
    prompts=[dict(length=length,text=source[cid]['input_text'],source_case_id=cid,
                  input_chars=len(source[cid]['input_text']),input_words=len(source[cid]['input_text'].split()),
                  text_sha256=hashlib.sha256(source[cid]['input_text'].encode('utf8')).hexdigest())
             for length,cid in [('short','T31'),('medium','T23'),('long','T25')]]
    rng=random.Random(4104);order=[]
    for repetition in range(1,6):
        lengths=list(prompts);rng.shuffle(lengths)
        for prompt in lengths:
            configs=list(MODELS);rng.shuffle(configs)
            for key,model,voice in configs:
                order.append(dict(case_id=f'R4-R-{key}-{prompt["length"]}-{repetition}',phase='measured_rest',
                                  repetition=repetition,model=model,voice=voice,**prompt))
    result=dict(protocol_version=1,random_seed=4104,successful_repetitions_per_cell=5,max_replacement_trials_per_cell=2,
                language='en-IN',speed=1.,sample_rate_hz=24000,encoding='linear_pcm',sample_width=2,channels=1,
                rest_container='wav',stream_container='raw',prompts=prompts,rest_order=order,
                warmup_policy='One short REST request per model before measured REST; cold WS short warm-up excluded from warm TTFA.',
                ws_scope='Five measured warm short-prompt repetitions per model, model blocks; no same-voice isolation.',
                limits='Different catalog voices; region, queueing, compute and network component timings unavailable; fixed client/account.')
    path=O/'protocol.json'
    if path.exists() and json.loads(path.read_text(encoding='utf8'))!=result:raise ValueError('Frozen Report-4 protocol changed')
    dump(path,result);return result


def run():
    import gnani_api as g
    p=protocol();O.mkdir(parents=True,exist_ok=True)
    g.ATTEMPTS=O/'attempts.jsonl';g.RAW=O/'raw';g.TTS_AUDIO=O/'audio'
    prior=P/'results/reconciliation/user_reported_spend.json'
    if not os.getenv('GNANI_SPENT_TO_DATE_INR') and prior.exists():os.environ['GNANI_SPENT_TO_DATE_INR']=str(json.loads(prior.read_text())['amount_inr'])
    def rest(cid,text,model,voice):
        record=latest(cid)
        if record:return record
        record=g.synthesize(cid,text,'en-IN',run_tag='report4',model=model,voice=voice,speed=1.,sample_rate=24000,live=True)
        print(cid,record.get('http_status'),record.get('ok'),record.get('latency_ms'),record.get('audio_duration_s'),flush=True)
        time.sleep(.25);return record
    short=p['prompts'][0]['text']
    for key,model,voice in MODELS:rest(f'R4-WARM-R-{key}',short,model,voice)
    for row in p['rest_order']:rest(row['case_id'],row['text'],row['model'],row['voice'])
    for prompt in p['prompts']:
        for key,model,voice in MODELS:
            ids=[f'R4-R-{key}-{prompt["length"]}-{i}' for i in range(1,6)]
            successes=sum(bool((latest(cid) or {}).get('ok')) for cid in ids)
            for index in range(1,3):
                if successes>=5:break
                cid=f'R4-REPLACE-{key}-{prompt["length"]}-{index}'
                successes+=bool(rest(cid,prompt['text'],model,voice).get('ok'))
    # A separate established socket per version; no concurrent synthesis.
    for key,model,voice in MODELS:
        targets=[f'R4-WS-{key}-short-{i}' for i in range(1,6)]
        if all(latest(cid) for cid in targets):continue
        try:
            with g.TTSWebSocket(live=True) as ws:
                warm=f'R4-WARM-WS-{key}-{len([r for r in logs() if r.get("case_id","").startswith("R4-WARM-WS-"+key+"-")])+1}'
                result=ws.synthesize(warm,short,'en-IN',run_tag='report4',model=model,voice=voice,speed=1.,sample_rate=24000)
                print(warm,result.get('ok'),'cold / excluded',flush=True)
                for cid in targets:
                    if latest(cid):continue
                    result=ws.synthesize(cid,short,'en-IN',run_tag='report4',model=model,voice=voice,speed=1.,sample_rate=24000)
                    print(cid,result.get('ok'),'TTFA',result.get('ttfa_ms'),'gaps',result.get('stalls'),flush=True)
                    time.sleep(.25)
        except Exception as e:
            dump(O/f'ws_setup_error_{key}.json',dict(model=model,error_type=type(e).__name__,error=str(e)[:220]))
            print('WS setup/collection failed',model,type(e).__name__,flush=True)
    print('Report-4 bounded collection finished',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');args=ap.parse_args()
    if args.live:run()
    else:print(json.dumps(protocol(),indent=2,ensure_ascii=False))
