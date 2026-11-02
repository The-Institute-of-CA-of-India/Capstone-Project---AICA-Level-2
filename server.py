"""Loopback-only HTTP service. No third-party packages required."""
import json, secrets, sqlite3, sys, threading, webbrowser, traceback, urllib.parse, tempfile, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import accounting as ac
TOKEN=secrets.token_urlsafe(32)
PORT=8765
class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
    def send(self,status,body,ctype='application/json; charset=utf-8',download=None):
        if not isinstance(body,bytes): body=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if download: self.send_header('Content-Disposition','attachment; filename="'+download+'"')
        self.end_headers();self.wfile.write(body)
    def do_GET(self): self.route('GET')
    def do_POST(self): self.route('POST')
    def route(self,method):
        try:
            host=self.headers.get('Host','')
            if host not in (f'127.0.0.1:{PORT}',f'localhost:{PORT}'): return self.send(403,{'error':'Invalid host.'})
            path=urllib.parse.urlsplit(self.path).path
            if path.startswith('/api/'):
                if not secrets.compare_digest(self.headers.get('X-Ledger-Token',''),TOKEN): return self.send(403,{'error':'Session expired. Reopen the application from the launcher.'})
                origin=self.headers.get('Origin')
                if origin and origin not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'): return self.send(403,{'error':'Invalid request origin.'})
                query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                d={}
                if method=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if length<0 or length>2_000_000: raise ValueError('Request too large.')
                    d=json.loads(self.rfile.read(length) or b'{}')
                    if not isinstance(d,dict): raise ValueError('Expected an object.')
                parts=path.strip('/').split('/')
                if path=='/api/companies':
                    if method=='POST': return self.send(200,ac.create_company(d))
                    with ac.connection() as c: return self.send(200,[dict(r) for r in c.execute('SELECT * FROM companies ORDER BY name')])
                if path=='/api/group' and method=='POST': return self.send(200,ac.group_report(d))
                if path=='/api/backup' and method=='GET':
                    fd,name=tempfile.mkstemp(suffix='.sqlite3',dir=ac.DB.parent);os.close(fd)
                    try:
                        with ac.connection() as c:
                            dest=sqlite3.connect(name);c.backup(dest);dest.close()
                        return self.send(200,Path(name).read_bytes(),'application/octet-stream','LedgerDesk-backup.sqlite3')
                    finally: Path(name).unlink(missing_ok=True)
                if len(parts)>=4 and parts[1]=='company':
                    cid=int(parts[2]);action=parts[3]
                    if method=='GET' and action=='state': return self.send(200,ac.state(cid))
                    if method=='GET' and action=='reports': return self.send(200,ac.reports(cid,query.get('start',['1900-01-01'])[0],query.get('end',['9999-12-31'])[0]))
                    if method=='POST':
                        if action in ('accounts','contacts','items'): return self.send(200,ac.master(cid,action,d))
                        if action=='preview':
                            with ac.connection() as c: return self.send(200,ac.build(c,cid,d))
                        if action=='draft': return self.send(200,ac.save_draft(cid,d))
                        if action=='post': return self.send(200,ac.post(cid,int(d['id'])))
                        if action=='reverse': return self.send(200,ac.reverse(cid,int(d['id']),d))
                        if action=='assets': return self.send(200,ac.add_asset(cid,d))
                        if action=='depreciate': return self.send(200,ac.depreciate(cid,int(d['id']),d))
                        if action=='lock': return self.send(200,ac.lock(cid,d))
                        if action=='reconcile': return self.send(200,ac.reconcile(cid,d))
                return self.send(404,{'error':'Unknown API route.'})
            if method!='GET': return self.send(405,{'error':'Method not allowed.'})
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if path not in files: return self.send(404,{'error':'Not found.'})
            filename,ctype=files[path];data=(ac.ROOT/'static'/filename).read_bytes()
            if path=='/': data=data.replace(b'__SESSION_TOKEN__',TOKEN.encode())
            self.send(200,data,ctype)
        except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e: self.send(400,{'error':str(e)})
        except Exception:
            traceback.print_exc();self.send(500,{'error':'Unexpected error. See the launcher window for details.'})
def main():
    global PORT
    if '--self-test' in sys.argv:
        # Exercise the packaged runtime without opening or modifying live books.
        with tempfile.TemporaryDirectory(dir=ac.DATA_ROOT) as folder:
            original=ac.DB
            try:
                ac.DB=Path(folder)/'self-test.sqlite3'
                ac.init()
                import demo
                demo.seed()
                with ac.connection() as conn:
                    cid=conn.execute('SELECT MIN(id) FROM companies').fetchone()[0]
                report=ac.reports(cid,'2026-01-01','2026-12-31')
                assert report['summary']['trial_difference']==0
                assert report['summary']['balance_difference']==0
                for asset in ('index.html','app.js','style.css'):
                    assert (ac.ROOT/'static'/asset).stat().st_size>0
                print('Packaged runtime self-test PASSED: SQLite, Decimal, demo postings, reports and embedded interface.')
            finally:
                ac.DB=original
        return
    if "--demo" in sys.argv: ac.DB=ac.DATA_ROOT/"data"/"demo.sqlite3"
    ac.init()
    if "--demo" in sys.argv:
        import demo
        demo.seed()
    server=None
    for p in range(8765,8786):
        try: server=ThreadingHTTPServer(('127.0.0.1',p),Handler);PORT=p;break
        except OSError: continue
    if not server: raise RuntimeError('No available local port between 8765 and 8785.')
    url=f'http://127.0.0.1:{PORT}'
    print('\nLedgerDesk | Local accounting\n'+url+'\nData: '+str(ac.DB)+'\nKeep this window open. Press Ctrl+C to stop.\n',flush=True)
    if '--no-browser' not in sys.argv: threading.Timer(0.7,lambda:webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nStopped safely.')
    finally: server.server_close()
if __name__=='__main__': main()

