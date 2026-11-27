import subprocess,json,hashlib,pathlib,datetime,sys
root=pathlib.Path.cwd(); out=root/'audit-final/autoauth-qa-04'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[p for base in ['backend/app','frontend/src'] for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in str(p)]
before={str(p.relative_to(root)):digest(p) for p in sources}
records=[]
for label,cmd in [('inventory','date --iso-8601=seconds; git rev-parse HEAD; .venv/bin/python --version; node --version; npm --version'),('backend','.venv/bin/python -m pytest backend/tests -q'),('frontend','npm --prefix frontend test'),('lint','npm --prefix frontend run lint'),('build','npm --prefix frontend run build'),('diff','git diff --check')]:
 start=datetime.datetime.now(datetime.timezone.utc).isoformat();r=subprocess.run(cmd,shell=True,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/(label+'.log')).write_text(r.stdout);records.append(dict(label=label,command=cmd,exit=r.returncode,start=start,end=datetime.datetime.now(datetime.timezone.utc).isoformat()));print(label,r.returncode,r.stdout[-400:],flush=True)
checks=[]
for folder in ['results/autoauth-model-matrix-01','results/autoauth-exec-eval-02','results/autoauth-web-03']:
 p=root/folder/'SHA256SUMS'
 if p.exists():
  r=subprocess.run(['sha256sum','-c',str(p)],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/(pathlib.Path(folder).name+'-hashes.log')).write_text(r.stdout);checks.append({'manifest':str(p.relative_to(root)),'exit':r.returncode,'ok':r.stdout.count(': OK')})
result={'commands':records,'handoff_hashes':checks,'source_before':before,'source_after':{str(p.relative_to(root)):digest(p) for p in sources},'persistent_db_opened':False,'lab_digest':'NOT_RUN; existing lab not accessed','openapi_fixture':'backend/tests/test_authorization_model.py embedded fixture','fixture_sha256':digest(root/'backend/tests/test_authorization_model.py')}
(out/'execution.json').write_text(json.dumps(result,indent=2));print('hashes',checks,flush=True)
