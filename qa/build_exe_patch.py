from pathlib import Path
p=Path('accounting.py');s=p.read_text(encoding='utf-8-sig');s=s.replace('import sqlite3, json, calendar','import sqlite3, json, calendar, sys');s=s.replace("DB=ROOT/'data'/'ledgerdesk.sqlite3'", "DATA_ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else ROOT\nDB=DATA_ROOT/'data'/'ledgerdesk.sqlite3'");p.write_text(s,encoding='utf-8')
p=Path('server.py');s=p.read_text(encoding='utf-8-sig');s=s.replace('ac.DB=ac.ROOT/"data"/"demo.sqlite3"','ac.DB=ac.DATA_ROOT/"data"/"demo.sqlite3"');s=s.replace('    global PORT\n', '''    global PORT
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
''');p.write_text(s,encoding='utf-8')
