"""Isolated synthetic browser fixture; never reads environment or persistent DB."""
import sys, tempfile, ipaddress, json, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, str(Path.cwd()))
from cryptography.fernet import Fernet
from sqlalchemy import select
from fastapi.staticfiles import StaticFiles
from backend.tests.test_authorization_model import lab, config
from backend.app.core.settings import Settings
from backend.app.core.secrets import SecretBox
from backend.app.main import create_app
from backend.app.persistence.models import IdentitySecret, ProjectAuthorizationRevision
from backend.app.services.authorization_model import revision, ResponseEvidence
import uvicorn
root=Path(tempfile.mkdtemp(prefix='autoauth-qa-06-'))
fixture=lab.__wrapped__(root)
s,p,t,a,o,rt,r=next(fixture)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  token=self.headers.get('Authorization','').removeprefix('Bearer ')
  if self.path=='/me':
   threading.Event().wait(12)
   body={'id':token}
  elif self.path=='/reports': body={'id':'report','secret':{'result':'synthetic-protected'}}
  else: body={'id':self.path.rsplit('/',1)[-1],'secret':{'result':'synthetic-protected'}}
  data=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
key=Fernet.generate_key().decode();box=SecretBox.from_key(key)
for i,actor in enumerate(a):
 secret=s.scalar(select(IdentitySecret).where(IdentitySecret.identity_id==actor.id))
 secret.ciphertext,secret.fingerprint=box.encrypt_bearer(f'fixture-{i}')
t.timeout_seconds=20
t.base_url=f'http://127.0.0.1:{server.server_port}'
c=config(a,o,rt,r);c.operations[1].evidence=ResponseEvidence(result_pointer='/id',result_value='report',protected_pointers=['/secret'])
s.add(ProjectAuthorizationRevision(project_id=p.id,revision=revision(c),configuration=c.model_dump()));s.commit();target_url=t.base_url;s.close()
settings=Settings(database_path=root/'isolated.sqlite',admin_password='synthetic-browser-only',session_secret='synthetic-isolated-session-key-32characters',secret_encryption_key=key,target_networks=(ipaddress.ip_network('127.0.0.1/32'),),allowed_ports=frozenset([server.server_port]),max_response_bytes=32768,default_timeout_seconds=20)
app=create_app(settings)
app.mount('/',StaticFiles(directory=Path.cwd()/'frontend/dist',html=True),name='isolated-ui')
Path('audit-final/autoauth-qa-06/cancel-environment.json').write_text(json.dumps({'database':str(root/'isolated.sqlite'),'app':'http://127.0.0.1:18986','target':target_url,'synthetic':True}))
uvicorn.run(app,host='127.0.0.1',port=18986,log_level='warning')
