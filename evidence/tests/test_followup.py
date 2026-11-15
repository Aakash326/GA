import ast, asyncio, base64, json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import requests
import gnani_api as g

class CacheRegressions(unittest.TestCase):
    def test_changed_input_keeps_old_response_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audio=root/'clip.wav';audio.write_bytes(b'old')
            def response(text):
                r=requests.Response();r.status_code=200;r._content=json.dumps({'transcript':text}).encode();return r
            with patch.multiple(g,PROJECT=root,RAW=root/'raw',ATTEMPTS=root/'attempts.jsonl'),patch.object(g,'_key',return_value='test'),patch.object(g,'reserve_budget'),patch.object(g.sf,'info',return_value=SimpleNamespace(duration=1)),patch.object(g._session,'post',side_effect=[response('old answer'),response('new answer')]):
                first=g.transcribe('X',audio,'en-IN',live=True)
                audio.write_bytes(b'new');second=g.transcribe('X',audio,'en-IN',live=True)
                self.assertNotEqual(first['raw_path'],second['raw_path'])
                self.assertEqual(g.latest_success('asr','X',fingerprint=first['fingerprint'])['transcript'],'old answer')

    def test_decode_failure_invalidates_http_success(self):
        r=dict(case_id='X',run_tag='run1',kind='tts',request_id='r',ok=True,fingerprint='f')
        with patch.object(g,'attempts',return_value=[r,{**r,'ok':False,'event':'decode_failure'}]):
            self.assertIsNone(g.latest_success('tts','X',fingerprint='f'))

class BargeInRegression(unittest.TestCase):
    def test_interruption_closes_old_socket(self):
        class Base:
            def __init__(self,sample_rate,**kw):self.sample_rate=sample_rate
            async def start_ttfb_metrics(self):pass
            async def stop_ttfb_metrics(self):pass
        class Frame:
            def __init__(self,audio,*a,**kw):self.audio=audio
        class WS:
            close_code=None
            def __init__(self,payload):
                self.msg=[{'type':'start'},{'type':'audio','data':{'audio':base64.b64encode(payload).decode()}},{'type':'complete'}]
            async def send(self,s):pass
            async def recv(self):return json.dumps(self.msg.pop(0))
            async def close(self):self.close_code=1000
        async def connect(*a,**kw):return WS(b'NEW')
        path=Path(__file__).resolve().parents[1]/'call_test/gnani_call_bot.py'
        cls=next(n for n in ast.parse(path.read_text(encoding='utf8')).body if isinstance(n,ast.ClassDef) and n.name=='GnaniTTS')
        ns=dict(TTSService=Base,TTSSettings=lambda **kw:kw,TTSAudioRawFrame=Frame,asyncio=asyncio,json=json,base64=base64,
                TTS_MODEL='test',TTS_VOICE='test',TTS_BUFFER_S=0,KEY='test',evidence_event=lambda *a,**kw:None,websockets=SimpleNamespace(connect=connect))
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'GnaniTTS','exec'),ns)
        async def exercise():
            tts=ns['GnaniTTS'](16000);old_socket=WS(b'OLD');tts.ws=old_socket
            gen=tts.run_tts('old','a');self.assertEqual((await anext(gen)).audio,b'OLD');await gen.aclose()
            self.assertEqual(old_socket.close_code,1000);self.assertIsNone(tts.ws)
            gen=tts.run_tts('new','b');self.assertEqual((await anext(gen)).audio,b'NEW');await gen.aclose()
        asyncio.run(exercise())

if __name__=='__main__':unittest.main()
