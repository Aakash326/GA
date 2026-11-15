"""Serve review pages/audio on localhost. Never serves environment files or source code."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
P=Path(__file__).resolve().parents[1]
class ReviewHandler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(P),**kw)
    def send_head(self):
        if self.path=='/':self.path='/data/listening/remaining_verifications.html'
        target=Path(self.translate_path(self.path)).resolve()
        if not target.is_relative_to(P) or target.suffix.lower() not in ['.html','.wav','.md']:
            self.send_error(403,'Review pages, audio and instructions only');return None
        return super().send_head()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8765);args=ap.parse_args()
    print(f'Review page: http://127.0.0.1:{args.port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),ReviewHandler).serve_forever()
if __name__=='__main__':main()
