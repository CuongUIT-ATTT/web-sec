import sys,json,tempfile,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from backend.tests.test_authorization_model import lab,config
from backend.app.persistence.models import Identity,IdentitySecret,IdentityVerification,Resource
from backend.app.services.authorization_model import preview
results=[]
for count in (3,5):
 g=lab.__wrapped__(Path(tempfile.mkdtemp(prefix='qa-coverage-')));s,p,t,a,o,rt,r=next(g)
 for i,actor in enumerate(a): actor.role=['user','reviewer','admin'][i]
 for i in range(3,count):
  actor=Identity(project_id=p.id,display_name=f'actor-{i}',role=['auditor','operator'][i-3],principal_pointer='/id',expected_principal=f'fixture-{i}');s.add(actor);s.flush();a.append(actor)
  s.add(IdentitySecret(identity_id=actor.id,ciphertext='test-only',fingerprint=f'qa-extra-{i}'));s.add(IdentityVerification(identity_id=actor.id,target_id=t.id,authentication_passed=True,principal_matched=True,execution_status='COMPLETED_RESPONSE'))
  for j in range(2):
   resource=Resource(resource_type_id=rt.id,external_id=f'qa-extra-{i}-{j}',owner_identity_id=actor.id,path_parameter='id');s.add(resource);r.append(resource)
 s.commit();v=preview(s,p.id,t,config(a,o,rt,r));counts={actor.id:sum(x['actor_identity_id']==actor.id for x in v['cases']) for actor in a};assert len(v['cases'])==count*(2*count+3);assert all(n==2*count+3 for n in counts.values());assert not v['exclusions'];results.append({'identities':count,'roles':count,'resources':len(r),'bola':sum(x['kind']=='BOLA' for x in v['cases']),'bfla':sum(x['kind']=='BFLA' for x in v['cases']),'per_identity':counts,'exclusions':v['exclusions'],'policy_revision':v['policy_revision']});g.close()
Path('audit-final/autoauth-qa-04/coverage.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
