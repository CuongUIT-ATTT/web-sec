import os, sys, socket, subprocess, tempfile, hashlib, json, platform
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from contextlib import ExitStack
root=Path.cwd()
sys.path[:0]=[str(root),str(root/'tools/authorization-lab/src')]
files=sorted(set(list(Path('backend/app/comparison').glob('*.py'))+list(Path('tools/authorization-lab/src/authz_lab/evaluation').glob('*.py'))+list(Path('tools/authorization-lab/tests/evaluation').glob('test_*.py'))+[Path(p) for p in ['backend/app/api/comparison_routes.py','backend/app/services/comparison_evidence.py','backend/app/persistence/models.py','backend/tests/test_comparison_store_api.py','backend/tests/test_research_comparison.py','backend/tests/test_research_matrix_contract.py','tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json','tools/authorization-lab/src/authz_lab/fixtures/ownership.csv','deploy/labs/vampi-bfla-disposable.compose.yaml']]))
def hashes(): return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before=hashes()
results=[]
def deny(*a,**kw): raise AssertionError('QA forbidden network/DNS/process')
async def noop(*a,**kw): pass
with tempfile.TemporaryDirectory(prefix='cmp05-independent-') as temp, ExitStack() as stack:
    for name in ['socket.socket.connect','socket.socket.connect_ex','socket.socket.sendto','socket.create_connection','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyname_ex','subprocess.Popen','os.system','os.posix_spawn','os.posix_spawnp','os.fork']:
        stack.enter_context(patch(name,deny))
    import pytest
    stack.enter_context(patch('backend.app.main.worker_loop',noop))
    groups=[['tools/authorization-lab/tests/evaluation/test_'+n+'.py' for n in ['importer','case_manifest','observations','metrics','exports','comparison','timing']],['backend/tests/test_comparison_store_api.py','backend/tests/test_research_comparison.py','backend/tests/test_research_matrix_contract.py']]
    for i, group in enumerate(groups):
        args=group+['-q','-p','no:cacheprovider','--basetemp',temp+'/'+str(i)]
        code=int(pytest.main(args)); results.append({'args':args,'exit':code})
after=hashes()
record={'timestamp':datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),'python':sys.version,'platform':platform.platform(),'results':results,'before':before,'after':after,'hashes_match':before==after}
Path('audit-final/cmp05-independent-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
print('HASHES_MATCH',before==after,'COUNT',len(before),flush=True)
raise SystemExit(max([r['exit'] for r in results]+[0 if before==after else 1]))
