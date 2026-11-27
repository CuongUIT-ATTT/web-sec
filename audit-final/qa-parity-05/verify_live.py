import subprocess,json,hashlib,pathlib,urllib.request,http.cookiejar,re,datetime
out={'time':datetime.datetime.now().astimezone().isoformat()}
def run(*args):return subprocess.check_output(args).decode().strip()
cid=run('docker','ps','-q','--filter','label=com.docker.compose.project=t18-qa-parity-05')
info=json.loads(run('docker','inspect',cid))[0]
out['container']={k:info[k] for k in ('Id','Image','Mounts')}
out['state']={k:info['State'][k] for k in ('Status','Running','Restarting','ExitCode')}
out['isolation']={k:info['HostConfig'][k] for k in ('ReadonlyRootfs','CapDrop','SecurityOpt','PortBindings','Tmpfs')}
out['networks']={n:json.loads(run('docker','network','inspect',n))[0]['Internal'] for n in info['NetworkSettings']['Networks']}
base='http://127.0.0.1:18080'
c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
out['health']=json.load(c.open(base+'/api/health'))
pw=pathlib.Path('/tmp/t18-qa-parity-05.password').read_text()
r=c.open(urllib.request.Request(base+'/api/auth/login',data=json.dumps({'password':pw}).encode(),headers={'Content-Type':'application/json'}));out['login_status']=r.status
for path in ('/api/projects/1/identities','/api/runs/1/results','/api/projects/1/runs/1/comparison'):
 data=json.load(c.open(base+path));out[path]={'count':len(data['cases'] if isinstance(data,dict) else data)}
try:c.open(urllib.request.Request(base+'/api/projects/1/runs',data=b'{}',headers={'Content-Type':'application/json'}))
except urllib.error.HTTPError as e:out['mutation_status']=e.code
html=c.open(base+'/').read().decode();assets=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',html)
out['assets']=[]
for a in assets:
 served=hashlib.sha256(c.open(base+a).read()).hexdigest()
 image=run('docker','exec',cid,'sha256sum','/app/frontend_dist'+a).split()[0]
 out['assets'].append(dict(path=a,served=served,image=image,parity=served==image))
out['sources']=[]
for p in list(pathlib.Path('backend/app').rglob('*.py'))+[pathlib.Path('audit-final/qa-parity-05/qa_app.py')]:
 target='/app/qa_app.py' if p.name=='qa_app.py' else '/app/'+str(p)
 h=hashlib.sha256(p.read_bytes()).hexdigest();ih=run('docker','exec',cid,'sha256sum',target).split()[0]
 out['sources'].append(dict(path=str(p),sha256=h,parity=h==ih))
out['frontend_sources']=[]
for line in run('docker','exec',cid,'cat','/app/frontend-source.sha256').splitlines():
 h,relative=line.split(None,1)
 local=hashlib.sha256((pathlib.Path('frontend')/relative).read_bytes()).hexdigest()
 out['frontend_sources'].append(dict(path=relative,sha256=h,parity=h==local))
assert all(s['parity'] for s in out['frontend_sources'])
assert all(out['networks'].values()) and len(out['networks'])==1
assert out['isolation']['ReadonlyRootfs'] and out['isolation']['CapDrop']==['ALL']
assert all(m['Type']=='tmpfs' for m in info['Mounts'])
runtime=json.loads(run('docker','inspect','deploy-authz-web-1'))[0]
before=json.loads(pathlib.Path('audit-final/qa-parity-05/runtime-before.json').read_text())
out['runtime_unchanged']=all(runtime[k]==before[k] for k in ('Id','Image','State'))
assert out['runtime_unchanged']
assert out['login_status']==200 and out['mutation_status']==403
assert all(a['parity'] for a in out['assets'])
assert all(s['parity'] for s in out['sources'])
print(json.dumps(out,indent=2))
