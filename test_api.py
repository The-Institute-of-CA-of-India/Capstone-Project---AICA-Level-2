import io,json,tempfile,unittest
from pathlib import Path
from http.client import HTTPMessage
import accounting as a
import server
class APITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=a.ROOT);self.old=a.DB;a.DB=Path(self.tmp.name)/'api.sqlite3';a.init()
 def tearDown(self): a.DB=self.old;self.tmp.cleanup()
 def req(self,path,method='GET',body=None,token=True,host=None):
  h=object.__new__(server.Handler);h.path=path;h.headers=HTTPMessage();h.headers['Host']=host or f'127.0.0.1:{server.PORT}'
  if token: h.headers['X-Ledger-Token']=server.TOKEN
  raw=json.dumps(body or {}).encode();h.headers['Content-Length']=str(len(raw));h.rfile=io.BytesIO(raw)
  result=[];h.send=lambda status,body,ctype='application/json',download=None:result.append((status,body,ctype,download));h.route(method);return result[0]
 def test_security(self):
  self.assertEqual(self.req('/api/companies',token=False)[0],403);self.assertEqual(self.req('/api/companies',host='evil.example')[0],403)
 def test_http_company_and_report_routes(self):
  r=self.req('/api/companies','POST',dict(name='API company',country='UAE',currency='AED',fy_start='2026-01-01'));self.assertEqual(r[0],200);cid=r[1]['id']
  self.assertEqual(self.req(f'/api/company/{cid}/state')[1]['company']['name'],'API company')
  self.assertEqual(self.req(f'/api/company/{cid}/reports?start=2026-01-01&end=2026-12-31')[1]['summary']['trial_difference'],0)
 def test_backup_and_static(self):
  r=self.req('/api/backup');self.assertEqual(r[0],200);self.assertTrue(r[1].startswith(b'SQLite format 3'));self.assertEqual(r[3],'LedgerDesk-backup.sqlite3')
  for path in ('/','/app.js','/style.css'): self.assertEqual(self.req(path)[0],200)
  self.assertNotIn(b'__SESSION_TOKEN__',self.req('/')[1]);self.assertEqual(self.req('/../accounting.py')[0],404)
 def test_invalid_payload(self):
  self.assertEqual(self.req('/api/companies','POST',{})[0],400)
if __name__=='__main__': unittest.main(verbosity=2)
