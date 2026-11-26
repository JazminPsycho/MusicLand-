"""Persisted recovery after browser/process loss, including concurrent editors."""
import fcntl
import time

from test_app import app,client,setup,post,wav,ORIGIN
from server import create_app,connect

META={'title':'Recovered','artist':'Synthetic','year':'2026','tracks':[{'slot':1,'title':'Second first'},{'slot':0,'title':'First second'}]}

def wait_job(c,id):
 for _ in range(100):
  row=c.get('/api/imports/'+id).json
  if row['state'] in ('ready','failed'):return row
  time.sleep(.02)
 raise AssertionError('Worker did not settle')

def test_resume_partial_upload_after_restart(app,client):
 setup(app,client);id=post(client,'/api/imports',{}).json['id']
 saved=post(client,f'/api/imports/{id}/draft',{**META,'revision':0},'put')
 assert saved.status_code==200
 assert client.put(f'/api/imports/{id}/files/1',data=wav(),headers=ORIGIN).status_code==200
 resumed=create_app(app.config['DATA']).test_client()
 assert post(resumed,'/api/login',{'name':'admin','password':'disposable-password'}).status_code==200
 state=resumed.get('/api/imports/'+id).json
 assert state['metadata']==META and state['revision']==1
 assert set(state['received'])=={'1'} and state['received']['1']['duration']==1
 assert post(resumed,f'/api/imports/{id}/start',{}).status_code==400
 assert resumed.put(f'/api/imports/{id}/files/0',data=wav(),headers=ORIGIN).status_code==200
 assert post(resumed,f'/api/imports/{id}/start',{}).status_code==200
 assert wait_job(resumed,id)['state']=='ready'
 album=resumed.get('/api/catalog').json[0]
 assert [t['title'] for t in album['tracks']]==['Second first','First second']
 assert resumed.get('/media/audio/'+album['tracks'][0]['id']).status_code==200
 assert post(resumed,f'/api/imports/{id}/start',{}).status_code==409
 assert post(resumed,f'/api/imports/{id}/draft',{**META,'revision':2},'put').status_code==409

def test_draft_conflict_and_invalid_slots(app,client):
 setup(app,client);id=post(client,'/api/imports',{}).json['id'];url=f'/api/imports/{id}/draft'
 assert post(client,url,{**META,'revision':0},'put').status_code==200
 assert post(client,url,{**META,'title':'Stale','revision':0},'put').status_code==409
 assert client.get('/api/imports/'+id).json['metadata']['title']=='Recovered'
 assert post(client,f'/api/imports/{id}/start',{**META,'revision':0}).status_code==409
 for slots in [('../x',),('0','0'),('00',),('-1',),('100',),('١',)]:
  bad={**META,'revision':1,'tracks':[{'slot':s,'title':'Bad'} for s in slots]}
  assert post(client,url,bad,'put').status_code==400
 assert client.get('/api/imports/'+id).json['revision']==1

def test_retry_failed_conversion_without_uploading_again(app,client,monkeypatch):
 import server
 setup(app,client);id=post(client,'/api/imports',{}).json['id']
 assert client.put(f'/api/imports/{id}/files/0',data=wav(),headers=ORIGIN).status_code==200
 raw={**META,'tracks':[{'slot':0,'title':'Preserved'}]}
 with monkeypatch.context() as patch:
  patch.setattr(server.subprocess,'run',lambda *a,**kw:(_ for _ in ()).throw(OSError('simulated')))
  assert post(client,f'/api/imports/{id}/start',raw).status_code==200
  assert wait_job(client,id)['state']=='failed'
 assert client.get('/api/catalog').json==[]
 again=create_app(app.config['DATA']).test_client()
 post(again,'/api/login',{'name':'admin','password':'disposable-password'})
 state=again.get('/api/imports/'+id).json
 assert state['metadata']==raw and set(state['received'])=={'0'}
 assert post(again,f'/api/imports/{id}/start',{}).status_code==200
 assert wait_job(again,id)['state']=='ready'
 assert len(again.get('/api/catalog').json)==1
 assert again.get('/api/catalog').json[0]['tracks'][0]['title']=='Preserved'

def test_import_write_exclusion_and_access(app,client):
 setup(app,client);id=post(client,'/api/imports',{}).json['id']
 with (app.config['DATA']/'staging'/id/'write.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  assert client.put(f'/api/imports/{id}/files/0',data=wav(),headers=ORIGIN).status_code==409
  assert post(client,f'/api/imports/{id}/draft',{**META,'revision':0},'put').status_code==409
  assert post(client,f'/api/imports/{id}/start',META).status_code==409
 anonymous=app.test_client()
 assert anonymous.get('/api/imports/'+id).status_code==401
 assert post(anonymous,f'/api/imports/{id}/draft',{**META,'revision':0},'put').status_code==401
 post(anonymous,'/api/register',{'name':'listener','password':'disposable-password'})
 u=next(u for u in client.get('/api/admin/users').json if u['name']=='listener')
 post(client,'/api/admin/users/'+u['id'],{'state':'active'},'patch')
 post(anonymous,'/api/login',{'name':'listener','password':'disposable-password'})
 assert anonymous.get('/api/imports/'+id).status_code==403
 assert post(anonymous,f'/api/imports/{id}/draft',{**META,'revision':0},'put').status_code==403

def test_invalid_replacement_preserves_received_audio(app,client):
 setup(app,client);id=post(client,'/api/imports',{}).json['id']
 post(client,f'/api/imports/{id}/draft',{**META,'revision':0},'put')
 path=app.config['DATA']/'staging'/id/'0.wav'
 assert client.put(f'/api/imports/{id}/files/0',data=wav(),headers=ORIGIN).status_code==200
 before=path.read_bytes()
 assert client.put(f'/api/imports/{id}/files/0',data=b'broken',headers=ORIGIN).status_code==400
 assert path.read_bytes()==before
 assert '0' in client.get('/api/imports/'+id).json['received']

def test_failed_cover_write_preserves_previous_image(app,client,monkeypatch):
 import io
 from PIL import Image
 setup(app,client);id=post(client,'/api/imports',{}).json['id'];payload=io.BytesIO();Image.new('RGB',(16,16),'purple').save(payload,'PNG')
 url=f'/api/imports/{id}/files/cover'
 assert client.put(url,data=payload.getvalue(),headers=ORIGIN).status_code==200
 path=app.config['DATA']/'staging'/id/'cover.jpg';previous=path.read_bytes()
 monkeypatch.setattr(Image.Image,'save',lambda *a,**kw:(_ for _ in ()).throw(OSError(28,'simulated disk full')))
 assert client.put(url,data=payload.getvalue(),headers=ORIGIN).status_code==507
 assert path.read_bytes()==previous
 assert not list(path.parent.glob('*.part'))
