import tempfile,json
from pathlib import Path
import accounting as a
import demo
with tempfile.TemporaryDirectory(dir=a.ROOT) as tmp:
 a.DB=Path(tmp)/'demo.sqlite3';a.init();demo.seed()
 with a.connection() as c: companies=[dict(r) for r in c.execute('SELECT * FROM companies')]
 state=a.state(companies[0]['id']);report=a.reports(companies[0]['id'],'2026-01-01','2026-10-24')
 Path('qa/fixture.json').write_text(json.dumps(dict(state=state,report=report,companies=companies)),encoding='utf-8')
 print('Demo fixture: balanced ledger,',len(state['vouchers']),'vouchers; profit',report['summary']['profit']/100)
 assert report['summary']['trial_difference']==0
