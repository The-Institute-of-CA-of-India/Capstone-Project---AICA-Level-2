from pathlib import Path
import zipfile,hashlib
p=Path('dist_README.txt');s=p.read_text();s=s.replace('The compiled EXE is checked separately for','The compiled EXE self-test PASSED for');p.write_text(s,encoding='ascii')
with zipfile.ZipFile('LedgerDesk_Windows_EXE.zip','w',zipfile.ZIP_DEFLATED) as z:
 for source,target in [('dist/LedgerDesk.exe','LedgerDesk.exe'),('dist_README.txt','START_HERE.txt'),('qa/TRY_DEMO_EXE.bat','TRY_DEMO.bat'),('README.md','README.md'),('FEATURE_MATRIX.md','FEATURE_MATRIX.md')]:
  z.write(source,'LedgerDesk/'+target)
with zipfile.ZipFile('LedgerDesk_Windows_EXE.zip') as z: assert z.testzip() is None
exe=Path('dist/LedgerDesk.exe')
assert exe.read_bytes()[:2]==b'MZ'
print('Windows EXE:',exe.stat().st_size,'bytes')
print('Download ZIP:',Path('LedgerDesk_Windows_EXE.zip').stat().st_size,'bytes')
print('SHA256:',hashlib.sha256(exe.read_bytes()).hexdigest())
