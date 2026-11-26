import io,json,time,wave,sqlite3,sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from server import create_app,connect,uid
from manage import backup,restore,sha
ORIGIN={'Origin':'http://localhost'}
@pytest.fixture
def app(tmp_path):
 a=create_app(tmp_path/'data');a.config['TESTING']=True;return a
@pytest.fixture
def client(app):return app.test_client()
def post(c,url,body,method='post',headers=None):return getattr(c,method)(url,json=body,headers=headers or ORIGIN)
def setup(app,c):
 r=post(c,'/api/setup',{'name':'admin','password':'disposable-password'},headers={**ORIGIN,'X-Setup-Token':app.config['SETUP_TOKEN']});assert r.status_code==200
 return c

def track(app):
 data=app.config['DATA'];folder=data/'media'/'a';folder.mkdir(exist_ok=True);(folder/'0.mp3').write_bytes(b'0123456789'*10000)
 with connect(data) as db:
  db.execute("INSERT OR IGNORE INTO albums VALUES('a','Album','Artist','2026',NULL,'hash')")
  db.execute("INSERT OR IGNORE INTO tracks VALUES('t','a','Track',0,60,'a/0.mp3')")
 return data

def test_setup_atomic_and_csrf(app,client):
 assert post(client,'/api/setup',{'name':'admin','password':'disposable-password'}).status_code==403
 setup(app,client)
 assert post(client,'/api/setup',{'name':'other','password':'disposable-password'},headers={**ORIGIN,'X-Setup-Token':app.config['SETUP_TOKEN']}).status_code==409
 assert client.post('/api/logout',json={}).status_code==403
 assert post(client,'/api/admin/users/x',{'state':'revoked'},'patch').status_code==404
 u=client.get('/api/admin/users').json[0]
 assert post(client,'/api/admin/users/'+u['id'],{'state':'revoked'},'patch').status_code==409

def test_access_ranges_and_revoke(app,client):
 setup(app,client);track(app);anonymous=app.test_client()
 for p in ('/api/catalog','/media/audio/t','/media/cover/a'):
  assert anonymous.get(p,headers={'Range':'bytes=0-9'}).status_code==401
 assert post(anonymous,'/api/register',{'name':'listener','password':'disposable-password'}).status_code==200
 assert post(anonymous,'/api/login',{'name':'listener','password':'disposable-password'}).status_code==401
 u=next(u for u in client.get('/api/admin/users').json if u['name']=='listener')
 post(client,'/api/admin/users/'+u['id'],{'state':'active'},'patch')
 assert post(anonymous,'/api/login',{'name':'listener','password':'disposable-password'}).status_code==200
 assert anonymous.get('/api/admin/users').status_code==403
 r=anonymous.get('/media/audio/t',headers={'Range':'bytes=10-19'});assert r.status_code==206 and r.data==b'0123456789'
 assert anonymous.head('/media/audio/t').headers['Content-Length']=='100000'
 assert anonymous.get('/media/audio/t',headers={'Range':'bytes=100000-'}).status_code==416
 stream=anonymous.get('/media/audio/t',buffered=False);next(stream.response)
 post(client,'/api/admin/users/'+u['id'],{'state':'revoked'},'patch')
 assert list(stream.response)==[]
 assert anonymous.get('/media/audio/t').status_code==401

def event(app,c,attempt,seq,pos,typ='progress',elapsed=5,eid=None):
 with connect(app.config['DATA']) as db:db.execute('UPDATE attempts SET last=? WHERE id=?',(time.time()-elapsed,attempt))
 return post(c,f'/api/attempts/{attempt}/events',dict(id=eid or uid(),seq=seq,position=pos,type=typ))
@pytest.mark.parametrize('seconds,valid',[(20,0),(35,1)])
def test_listen_threshold(app,client,seconds,valid):
 setup(app,client);track(app);a=post(client,'/api/attempts',{'track':'t'}).json['id']
 r=event(app,client,a,1,seconds,elapsed=seconds);assert r.status_code==200;assert r.json['seconds']==seconds
 assert client.get('/api/attempts/'+a).json['valid']==valid

def test_metrics_seek_duplicates_coverage(app,client):
 setup(app,client);track(app);a=post(client,'/api/attempts',{'track':'t'}).json['id']
 assert event(app,client,a,1,50,'seek',50).json['seconds']==0
 eid=uid();r=event(app,client,a,2,60,'ended',10,eid);assert not r.json['complete']
 for _ in range(10):assert event(app,client,a,2,60,'ended',10,eid).json['duplicate']
 assert client.get('/api/attempts/'+a).json['seconds']==10
 b=post(client,'/api/attempts',{'track':'t'}).json['id']
 event(app,client,b,1,54,elapsed=54);assert event(app,client,b,2,60,'ended',6).json['complete']
 assert event(app,client,b,3,60).status_code==409
 assert client.get('/api/admin/summary').json['rows']

def test_backup_restore(app,client,tmp_path):
 setup(app,client);data=track(app);manifest=backup(data,tmp_path/'backup');restore(tmp_path/'backup',tmp_path/'restored')
 with connect(tmp_path/'restored') as db:
  assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0
 assert sha(data/'media/a/0.mp3')==sha(tmp_path/'restored/media/a/0.mp3')
 with pytest.raises(ValueError):restore(tmp_path/'backup',tmp_path/'restored')
 (tmp_path/'backup/media/a/0.mp3').write_bytes(b'bad')
 with pytest.raises(ValueError):restore(tmp_path/'backup',tmp_path/'bad')

def wav():
 b=io.BytesIO()
 with wave.open(b,'wb') as w:w.setparams((1,2,8000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*8000)
 return b.getvalue()
def test_import_corrupt_duplicate(app,client):
 setup(app,client)
 def upload():
  id=post(client,'/api/imports',{}).json['id']
  assert client.put(f'/api/imports/{id}/files/0',data=b'broken',headers=ORIGIN).status_code==400
  assert client.put(f'/api/imports/{id}/files/cover',data=b'<svg/>',headers=ORIGIN).status_code==400
  assert client.put(f'/api/imports/{id}/files/0',data=wav(),headers=ORIGIN).status_code==200
  assert post(client,f'/api/imports/{id}/start',{'title':'Test','artist':'Synthetic','tracks':[{'slot':0,'title':'One'}]}).status_code==200
  for _ in range(100):
   j=next(j for j in client.get('/api/imports').json if j['id']==id)
   if j['state'] in ('failed','ready'):break
   time.sleep(.05)
  assert j['state']=='ready';return j
 a=upload();b=upload();assert a['album']==b['album'];assert len(client.get('/api/catalog').json)==1
 assert client.get('/media/audio/'+client.get('/api/catalog').json[0]['tracks'][0]['id']).data[:3] in (b'ID3',b'\xff\xfb\x90')

def test_login_limit(app,client):
 setup(app,client)
 for _ in range(10):assert post(client,'/api/login',{'name':'wrong','password':'wrong'}).status_code==401
 assert post(client,'/api/login',{'name':'wrong','password':'wrong'}).status_code==429

def test_concurrent_setup(app):
 from concurrent.futures import ThreadPoolExecutor
 def run(n):
  return post(app.test_client(),'/api/setup',{'name':'admin'+str(n),'password':'disposable-password'},headers={**ORIGIN,'X-Setup-Token':app.config['SETUP_TOKEN']}).status_code
 with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(run,[1,2]))==[200,409]

def test_failed_conversion_restart_and_disk(app,client,monkeypatch):
 import server,collections
 setup(app,client);track(app);id=post(client,'/api/imports',{}).json['id']
 monkeypatch.setattr(server.shutil,'disk_usage',lambda _:collections.namedtuple('Disk','total used free')(100,100,0))
 assert client.put(f'/api/imports/{id}/files/0',data=wav(),headers=ORIGIN).status_code==507
 monkeypatch.undo()
 assert client.put(f'/api/imports/{id}/files/0',data=wav(),headers=ORIGIN).status_code==200
 monkeypatch.setattr(server.subprocess,'run',lambda *a,**kw:(_ for _ in ()).throw(OSError('simulated')))
 post(client,f'/api/imports/{id}/start',{'title':'Broken','artist':'Test','tracks':[{'slot':0,'title':'One'}]})
 for _ in range(100):
  j=next(j for j in client.get('/api/imports').json if j['id']==id)
  if j['state']=='failed':break
  time.sleep(.01)
 assert j['state']=='failed';assert len(client.get('/api/catalog').json)==1
 with connect(app.config['DATA']) as db:db.execute("UPDATE jobs SET state='converting' WHERE id=?",(id,))
 create_app(app.config['DATA'])
 with connect(app.config['DATA']) as db:assert db.execute('SELECT state FROM jobs WHERE id=?',(id,)).fetchone()[0]=='failed'

def test_album_edit_preserves_ids(app,client):
 setup(app,client);track(app)
 assert post(client,'/api/admin/albums/a',{'title':'Changed','artist':'Changed','tracks':[{'id':'t','title':'Renamed'}]},'patch').status_code==200
 assert client.get('/api/catalog').json[0]['tracks'][0]['id']=='t'
 assert post(client,'/api/admin/albums/a',{'title':'Oops','artist':'Oops','tracks':[]},'patch').status_code==400
 assert client.get('/api/catalog').json[0]['title']=='Changed'

def test_stream_missing_and_bad_events(app,client):
 setup(app,client);data=track(app)
 a=post(client,'/api/attempts',{'track':'t'}).json['id']
 assert event(app,client,a,2,20).status_code==409
 assert event(app,client,a,1,float('inf')).status_code==400
 assert client.get('/media/audio/missing').status_code==404
 (data/'media/a/0.mp3').unlink();assert client.get('/media/audio/t').status_code==404

def test_replace_cover_and_limits(app,client):
 from PIL import Image
 setup(app,client);track(app);b=io.BytesIO();Image.new('RGB',(32,32),'purple').save(b,'PNG')
 assert client.put('/api/admin/albums/a/cover',data=b.getvalue(),headers=ORIGIN).status_code==200
 cover=client.get('/api/catalog').json[0]['cover']
 assert client.get('/media/cover/a').mimetype=='image/jpeg'
 assert client.put('/api/admin/albums/a/cover',data=b'bad',headers=ORIGIN).status_code==400
 assert client.get('/api/catalog').json[0]['cover']==cover
 (app.config['DATA']/'settings.json').write_text('{"tracks":2}')
 assert create_app(app.config['DATA'])
 (app.config['DATA']/'settings.json').write_text('{"tracks":0}')
 with pytest.raises(ValueError):create_app(app.config['DATA'])
