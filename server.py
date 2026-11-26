"""JAPs Música: local library. Data never belongs in the source tree."""
import argparse, contextlib, datetime as dt, fcntl, hashlib, io, json, math, os, secrets, shutil, sqlite3, subprocess, threading, time, uuid, wave
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, send_from_directory, Response, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, UnidentifiedImageError

ROOT=Path(__file__).resolve().parent
SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS albums(id TEXT PRIMARY KEY,title TEXT,artist TEXT,year TEXT,cover TEXT,fingerprint TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS tracks(id TEXT PRIMARY KEY,album TEXT,title TEXT,position INTEGER,duration REAL,file TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT,state TEXT,detail TEXT,album TEXT);
CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,user TEXT,track TEXT,started REAL,last REAL,seq INTEGER DEFAULT 0,position REAL DEFAULT 0,seconds REAL DEFAULT 0,intervals TEXT DEFAULT '[]',closed TEXT,valid INTEGER DEFAULT 0,complete INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,attempt TEXT,seq INTEGER,type TEXT,position REAL,seconds REAL,received REAL,UNIQUE(attempt,seq));
CREATE TABLE IF NOT EXISTS spans(attempt TEXT,start REAL,end REAL,seconds REAL);
CREATE TABLE IF NOT EXISTS hourly(day TEXT,hour INTEGER,seconds REAL,version INTEGER DEFAULT 1,PRIMARY KEY(day,hour));
PRAGMA user_version=1;
'''

def uid(): return uuid.uuid4().hex
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def connect(data):
 c=sqlite3.connect(data/'music.sqlite',timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def create_app(data=None):
 data=Path(data or os.environ.get('JAPS_DATA',Path.home()/'.local/share/japs-musica')).expanduser().resolve()
 data.mkdir(parents=True,exist_ok=True,mode=0o700)
 for d in ('media','staging'): (data/d).mkdir(exist_ok=True,mode=0o700)
 with connect(data) as c:
  if c.execute('PRAGMA user_version').fetchone()[0] not in (0,1):raise RuntimeError('Esquema incompatible; recuperá una copia con la versión correspondiente.')
  c.executescript(SCHEMA)
  c.execute("UPDATE jobs SET state='failed',detail='Importación interrumpida. Los archivos se conservan para reintentar.' WHERE state NOT IN ('ready','failed','draft')")
 app=Flask(__name__,static_folder=None);app.config.update(DATA=data,MAX_CONTENT_LENGTH=512*1024*1024,TESTING=False)
 app.config['SETUP_TOKEN']=secrets.token_urlsafe(32)
 settings={'wav_mib':512,'cover_mib':10,'tracks':99,'duration_seconds':7200}
 config=data/'settings.json'
 if config.exists():
  loaded=json.loads(config.read_text())
  for key,value in loaded.items():
   if key not in settings or not isinstance(value,int) or value<=0:raise ValueError('Configuración de límite inválida')
  settings.update(loaded)
 app.config['MAX_CONTENT_LENGTH']=max(settings['wav_mib'],settings['cover_mib'])*1024*1024
 attempts={};guard=threading.Lock()
 def db():
  if 'db' not in g:g.db=connect(data)
  return g.db
 @app.teardown_appcontext
 def close(error):
  if 'db' in g:g.db.close()
 def error(message,status=400): return jsonify(error=message),status
 @app.errorhandler(400)
 def bad(e):return error('Solicitud no válida.')
 @app.errorhandler(413)
 def large(e):return error('El archivo supera el límite configurado.',413)
 @app.errorhandler(404)
 def missing(e):return error('No se encontró el recurso.',404)
 @app.before_request
 def protect():
  g.user=None
  token=request.cookies.get('japs','')
  if token:
   g.user=db().execute("SELECT u.* FROM users u JOIN sessions s ON s.user=u.id WHERE s.token=? AND s.expires>? AND u.state='active'",(digest(token),time.time())).fetchone()
  if request.method not in ('GET','HEAD','OPTIONS'):
   if request.headers.get('Origin')!=request.host_url.rstrip('/'):return error('Origen no permitido.',403)
  public={'/api/session','/api/login','/api/register','/api/setup'}
  if request.path.startswith(('/api/','/media/')) and request.path not in public:
   if not g.user:return error('Iniciá sesión con una cuenta aprobada.',401)
   if (request.path.startswith('/api/admin/') or request.path.startswith('/api/imports')) and g.user['role']!='admin':return error('Se requiere administración.',403)
 @app.after_request
 def headers(r):
  r.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'"})
  return r
 @app.get('/')
 def index():return send_from_directory(ROOT/'web','index.html')
 @app.get('/<path:p>')
 def assets(p):return send_from_directory(ROOT/'web',p)
 @app.get('/api/session')
 def session():return jsonify(user={k:g.user[k] for k in ('id','name','role')} if g.user else None,setup=db().execute('SELECT count(*) FROM users').fetchone()[0]==0,portfolio=os.environ.get('JAPS_PORTFOLIO','https://jazmin-schurrer-maqueta.centeredazure8.chatgpt.site'))
 def credentials():
  raw=request.get_json();name=str(raw.get('name','')).strip();password=raw.get('password','')
  if not 2<=len(name)<=64 or not isinstance(password,str) or not 12<=len(password)<=256:abort(400)
  return name,password
 def login_response(user):
  token=secrets.token_urlsafe(32)
  with db():
   old=request.cookies.get('japs')
   if old:db().execute('DELETE FROM sessions WHERE token=?',(digest(old),))
   db().execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),user,time.time()+86400))
  r=jsonify(ok=True);r.set_cookie('japs',token,httponly=True,samesite='Strict',secure=request.is_secure,max_age=86400);return r
 @app.post('/api/setup')
 def setup():
  if request.remote_addr not in ('127.0.0.1','::1') or not secrets.compare_digest(request.headers.get('X-Setup-Token',''),app.config['SETUP_TOKEN']):return error('Usá el token mostrado por el lanzador en este equipo.',403)
  name,password=credentials();user=uid()
  try:
   db().execute('BEGIN IMMEDIATE')
   if db().execute('SELECT count(*) FROM users').fetchone()[0]:db().rollback();return error('La primera cuenta ya fue creada.',409)
   db().execute('INSERT INTO users VALUES(?,?,?,?,?)',(user,name,generate_password_hash(password),'admin','active'));db().commit()
  except Exception:db().rollback();raise
  return login_response(user)
 @app.post('/api/register')
 def register():
  if not db().execute('SELECT 1 FROM users').fetchone():return error('Primero se configura la administración.',409)
  name,password=credentials()
  try:
   with db():db().execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid(),name,generate_password_hash(password),'listener','pending'))
  except sqlite3.IntegrityError:return error('No se pudo solicitar esa cuenta.',409)
  return jsonify(ok=True,message='Solicitud enviada. Esperá la aprobación de la administradora.')
 @app.post('/api/login')
 def login():
  key=request.remote_addr;now=time.time()
  with guard:
   recent=[t for t in attempts.get(key,[]) if t>now-300];attempts[key]=recent
   if len(recent)>=10:return error('Demasiados intentos. Esperá cinco minutos.',429)
   recent.append(now)
  raw=request.get_json();u=db().execute('SELECT * FROM users WHERE name=?',(str(raw.get('name',''))[:64],)).fetchone()
  password=str(raw.get('password',''))[:256]
  if not u or not check_password_hash(u['password'],password) or u['state']!='active':return error('Cuenta o contraseña incorrecta, pendiente o revocada.',401)
  return login_response(u['id'])
 @app.post('/api/logout')
 def logout():
  with db():db().execute('DELETE FROM sessions WHERE token=?',(digest(request.cookies.get('japs','')),))
  r=jsonify(ok=True);r.delete_cookie('japs');return r
 @app.get('/api/admin/users')
 def users():return jsonify([dict(r) for r in db().execute('SELECT id,name,role,state FROM users ORDER BY name')])
 @app.patch('/api/admin/users/<id>')
 def user_edit(id):
  state=request.get_json().get('state')
  if state not in ('active','revoked'):abort(400)
  with db():
   db().execute('BEGIN IMMEDIATE');u=db().execute('SELECT * FROM users WHERE id=?',(id,)).fetchone()
   if not u:abort(404)
   if u['role']=='admin' and state!='active' and db().execute("SELECT count(*) FROM users WHERE role='admin' AND state='active'").fetchone()[0]<=1:return error('Se conserva la última administradora activa.',409)
   db().execute('UPDATE users SET state=? WHERE id=?',(state,id));db().execute('DELETE FROM sessions WHERE user=?',(id,))
  return jsonify(ok=True)
 @app.get('/api/catalog')
 def catalog():
  albums=[dict(a) for a in db().execute('SELECT * FROM albums ORDER BY artist,title')]
  for a in albums:a['tracks']=[dict(t) for t in db().execute('SELECT * FROM tracks WHERE album=? ORDER BY position',(a['id'],))]
  return jsonify(albums)
 @app.post('/api/imports')
 def new_job():
  id=uid();(data/'staging'/id).mkdir(mode=0o700)
  with db():db().execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(id,g.user['id'],'draft','Borrador',None))
  return jsonify(id=id)
 def job(id):
  r=db().execute('SELECT * FROM jobs WHERE id=?',(id,)).fetchone()
  if not r:abort(404)
  return r
 @app.get('/api/imports')
 def jobs():return jsonify([dict(r) for r in db().execute('SELECT * FROM jobs ORDER BY rowid DESC LIMIT 50')])
 @app.put('/api/imports/<id>/files/<slot>')
 def upload(id,slot):
  if job(id)['state'] not in ('draft','failed'):return error('El trabajo ya está en curso.',409)
  if slot!='cover' and (not slot.isdigit() or not 0<=int(slot)<settings['tracks']):abort(400)
  folder=data/'staging'/id
  if shutil.disk_usage(data).free<max(request.content_length or 0,0)+256*1024*1024:return error('Falta espacio libre para importar.',507)
  temp=folder/(uid()+'.part');size=0
  try:
   with temp.open('wb') as f:
    while block:=request.stream.read(1024*1024):
     size+=len(block)
     if size>settings['cover_mib' if slot=='cover' else 'wav_mib']*1024*1024:abort(413)
     f.write(block)
   if slot=='cover':
    if size>settings['cover_mib']*1024*1024:abort(413)
    with Image.open(temp) as image:
     if image.format not in ('JPEG','PNG') or image.width*image.height>16000000:raise ValueError('Portada no válida')
     image.convert('RGB').resize((800,800)).save(folder/'cover.jpg','JPEG',quality=85)
    temp.unlink()
   else:
    with wave.open(str(temp),'rb') as w:
     duration=w.getnframes()/w.getframerate()
     if w.getcomptype()!='NONE' or w.getnchannels() not in (1,2) or not 0<duration<=settings['duration_seconds'] or w.getsampwidth() not in (1,2,3,4):raise ValueError('WAV PCM no compatible')
     expected=w.getnframes()*w.getnchannels()*w.getsampwidth();actual=0
     while block:=w.readframes(65536):actual+=len(block)
     if actual!=expected:raise ValueError('WAV truncado')
    temp.replace(folder/(slot+'.wav'))
   return jsonify(ok=True)
  except (ValueError,wave.Error,EOFError,UnidentifiedImageError,Image.DecompressionBombError):return error('Archivo inválido. Usá WAV PCM o una portada JPEG/PNG.')
  finally:temp.unlink(missing_ok=True)
 @app.post('/api/imports/<id>/start')
 def start_job(id):
  j=job(id);raw=request.get_json();tracks=raw.get('tracks',[])
  if j['state'] not in ('draft','failed'):return error('Trabajo ya iniciado.',409)
  if not 1<=len(tracks)<=settings['tracks'] or not str(raw.get('title','')).strip() or not str(raw.get('artist','')).strip():abort(400)
  slots=[str(t.get('slot','')) for t in tracks]
  if len(set(slots))!=len(slots) or any(not s.isdigit() or not (data/'staging'/id/(s+'.wav')).is_file() for s in slots):abort(400)
  lock=(data/'import.lock').open('a+')
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:lock.close();return error('Hay otra importación o copia en curso.',409)
  with db():db().execute("UPDATE jobs SET state='validating',detail='Validando audio' WHERE id=?",(id,))
  threading.Thread(target=convert,args=(data,id,raw,lock),daemon=True).start();return jsonify(ok=True)
 @app.patch('/api/admin/albums/<id>')
 def edit_album(id):
  raw=request.get_json()
  with db():
   old=db().execute('SELECT * FROM albums WHERE id=?',(id,)).fetchone()
   if not old:abort(404)
   tracks=raw.get('tracks',[]);existing={r['id'] for r in db().execute('SELECT id FROM tracks WHERE album=?',(id,))}
   if {t.get('id') for t in tracks}!=existing or len(tracks)!=len(existing):abort(400)
   if not str(raw.get('title','')).strip() or not str(raw.get('artist','')).strip():abort(400)
   db().execute('UPDATE albums SET title=?,artist=?,year=? WHERE id=?',(str(raw['title'])[:200],str(raw['artist'])[:200],str(raw.get('year',''))[:4],id))
   for i,t in enumerate(tracks):db().execute('UPDATE tracks SET title=?,position=? WHERE id=?',(str(t['title'])[:200],i,t['id']))
  return jsonify(ok=True)
 @app.put('/api/admin/albums/<id>/cover')
 def replace_cover(id):
  if not db().execute('SELECT 1 FROM albums WHERE id=?',(id,)).fetchone():abort(404)
  if not request.content_length or request.content_length>settings['cover_mib']*1024*1024:abort(413)
  name=id+'/'+uid()+'.jpg';path=data/'media'/name
  try:
   payload=request.get_data(cache=False)
   with Image.open(io.BytesIO(payload)) as image:
    if image.format not in ('JPEG','PNG') or image.width*image.height>16000000:raise ValueError()
    image.convert('RGB').resize((800,800)).save(path,'JPEG',quality=85)
   with db():db().execute('UPDATE albums SET cover=? WHERE id=?',(name,id))
   return jsonify(ok=True)
  except (ValueError,UnidentifiedImageError,Image.DecompressionBombError):
   path.unlink(missing_ok=True);return error('Portada inválida; se conservó la anterior.')
 @app.route('/media/<kind>/<id>',methods=['GET','HEAD'])
 def media(kind,id):
  if kind=='cover':r=db().execute('SELECT cover AS file FROM albums WHERE id=?',(id,)).fetchone();mime='image/jpeg'
  elif kind=='audio':r=db().execute('SELECT file FROM tracks WHERE id=?',(id,)).fetchone();mime='audio/mpeg'
  else:abort(404)
  if not r or not r['file']:abort(404)
  path=data/'media'/r['file']
  if not path.is_file():abort(404)
  size=path.stat().st_size;start=0;end=size-1;status=200
  if request.headers.get('Range'):
   try:
    value=request.headers['Range'];assert value.startswith('bytes=') and ',' not in value
    a,b=value[6:].split('-');start=int(a) if a else max(0,size-int(b));end=min(int(b),size-1) if a and b else size-1
    assert 0<=start<=end<size
    status=206
   except (ValueError,AssertionError):return Response(status=416,headers={'Content-Range':f'bytes */{size}'})
  token=digest(request.cookies.get('japs',''));user=g.user['id']
  def stream():
   with path.open('rb') as f,connect(data) as c:
    f.seek(start);remaining=end-start+1
    while remaining:
     if not c.execute("SELECT 1 FROM sessions s JOIN users u ON s.user=u.id WHERE s.token=? AND u.id=? AND u.state='active' AND s.expires>?",(token,user,time.time())).fetchone():break
     block=f.read(min(16384,remaining))
     if not block:break
     remaining-=len(block);yield block
  h={'Content-Length':str(end-start+1),'Accept-Ranges':'bytes'}
  if status==206:h['Content-Range']=f'bytes {start}-{end}/{size}'
  return Response(None if request.method=='HEAD' else stream(),status=status,headers=h,mimetype=mime)
 @app.post('/api/attempts')
 def new_attempt():
  track=request.get_json().get('track')
  if not db().execute('SELECT 1 FROM tracks WHERE id=?',(track,)).fetchone():abort(404)
  id=uid();now=time.time()
  with db():db().execute('INSERT INTO attempts(id,user,track,started,last) VALUES(?,?,?,?,?)',(id,g.user['id'],track,now,now))
  return jsonify(id=id)
 @app.post('/api/attempts/<id>/events')
 def event(id):
  raw=request.get_json();now=time.time();seq=raw.get('seq');position=raw.get('position');typ=raw.get('type');eid=raw.get('id')
  if not isinstance(seq,int) or not isinstance(eid,str) or len(eid)>100 or typ not in ('progress','pause','resume','seek','waiting','ended','skip','interrupted','error'):abort(400)
  if not isinstance(position,(int,float)) or not math.isfinite(position):abort(400)
  with db():
   db().execute('BEGIN IMMEDIATE');a=db().execute('SELECT a.*,t.duration FROM attempts a JOIN tracks t ON a.track=t.id WHERE a.id=? AND a.user=?',(id,g.user['id'])).fetchone()
   if not a:abort(404)
   if db().execute('SELECT 1 FROM events WHERE id=? OR (attempt=? AND seq=?)',(eid,id,seq)).fetchone():return jsonify(ok=True,duplicate=True)
   if a['closed'] or seq!=a['seq']+1:return error('Secuencia desactualizada. Recuperá el intento.',409)
   if not 0<=position<=a['duration']+0.5:abort(400)
   # Progress only measures contiguous forward playback since the previous signal.
   delta=position-a['position'];elapsed=max(0,now-a['last']);seconds=min(delta,elapsed,a['duration']) if typ in ('progress','pause','ended') and 0<=delta<=elapsed+1 else 0
   intervals=json.loads(a['intervals'])
   if seconds:intervals.append([max(a['position'],position-seconds),min(position,a['duration'])])
   merged=[]
   for x,y in sorted(intervals):
    if merged and x<=merged[-1][1]:merged[-1][1]=max(y,merged[-1][1])
    else:merged.append([x,y])
   total=a['seconds']+seconds;coverage=sum(y-x for x,y in merged)
   closed=typ if typ in ('ended','skip','interrupted','error') else None
   complete=int(typ=='ended' and coverage>=a['duration']*.9 and position>=a['duration']-.5)
   db().execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',(eid,id,seq,typ,position,seconds,now))
   if seconds:db().execute('INSERT INTO spans VALUES(?,?,?,?)',(id,now-seconds,now,seconds))
   db().execute('UPDATE attempts SET last=?,seq=?,position=?,seconds=?,intervals=?,closed=?,valid=?,complete=? WHERE id=?',(now,seq,position,total,json.dumps(merged),closed,int(total>=min(30,a['duration']/2)),complete,id))
  return jsonify(ok=True,seconds=total,complete=bool(complete))
 @app.get('/api/attempts/<id>')
 def attempt(id):
  r=db().execute('SELECT * FROM attempts WHERE id=? AND user=?',(id,g.user['id'])).fetchone()
  if not r:abort(404)
  return jsonify(dict(r))
 @app.get('/api/admin/summary')
 def summary():
  zone=ZoneInfo('America/Argentina/Cordoba')
  try:
   start=dt.datetime.fromisoformat(request.args.get('from',dt.date.today().replace(day=1).isoformat())).replace(tzinfo=zone).timestamp()
   end=(dt.datetime.fromisoformat(request.args.get('to',dt.date.today().isoformat()))+dt.timedelta(days=1)).replace(tzinfo=zone).timestamp()
  except ValueError:abort(400)
  rows=[dict(r) for r in db().execute('SELECT a.*,t.title,t.album,l.title album_title,l.artist,u.name FROM attempts a JOIN tracks t ON t.id=a.track JOIN albums l ON l.id=t.album JOIN users u ON u.id=a.user WHERE started>=? AND started<?',(start,end))]
  hourly=[0.0]*24
  for s in db().execute('SELECT start,end,seconds FROM spans WHERE end>? AND start<?',(start,end)):
   cursor=max(s['start'],start);stop=min(s['end'],end)
   while cursor<stop:
    local=dt.datetime.fromtimestamp(cursor,zone);boundary=min(stop,cursor+(3600-local.minute*60-local.second-local.microsecond/1e6))
    hourly[local.hour]+=boundary-cursor;cursor=boundary
  for row in db().execute('SELECT day,hour,seconds FROM hourly'):
   stamp=dt.datetime.fromisoformat(row['day']).replace(tzinfo=zone).timestamp()
   if start<=stamp<end:hourly[row['hour']]+=row['seconds']
  active={}
  for r in rows:
   if r['valid']:active.setdefault(r['user'],set()).add(dt.datetime.fromtimestamp(r['started'],zone).date().isoformat())
  return jsonify(zone=str(zone),from_utc=start,to_utc=end,rows=rows,hours=hourly,returning=sum(len(days)>=2 for days in active.values()),active_days={u:len(days) for u,days in active.items()})
 return app

def convert(data,id,raw,lock):
 folder=data/'staging'/id;dest=data/'media'/id
 try:
  fingerprint=hashlib.sha256();metadata=[]
  for t in raw['tracks']:
   with wave.open(str(folder/(str(t['slot'])+'.wav')),'rb') as w:
    fingerprint.update(str((w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())).encode())
    while block:=w.readframes(65536):fingerprint.update(block)
    metadata.append(w.getnframes()/w.getframerate())
  fp=fingerprint.hexdigest()
  with connect(data) as c:existing=c.execute('SELECT id FROM albums WHERE fingerprint=?',(fp,)).fetchone()
  if existing:
   with connect(data) as c:c.execute("UPDATE jobs SET state='ready',detail='Álbum ya existente',album=? WHERE id=?",(existing['id'],id))
   return
  dest.mkdir(exist_ok=True)
  for i,t in enumerate(raw['tracks']):
   with connect(data) as c:c.execute("UPDATE jobs SET state='converting',detail=? WHERE id=?",(f'Preparando pista {i+1}/{len(raw["tracks"])}',id))
   out=dest/(str(i)+'.mp3')
   subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-threads','1','-i',str(folder/(str(t['slot'])+'.wav')),'-vn','-ac','2','-codec:a','libmp3lame','-b:a','192k','-threads','1',str(out)],check=True,timeout=600,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   if out.stat().st_size<100:raise ValueError('Salida vacía')
  cover=None
  if (folder/'cover.jpg').exists():shutil.copy2(folder/'cover.jpg',dest/'cover.jpg');cover=id+'/cover.jpg'
  with connect(data) as c:
   c.execute('INSERT INTO albums VALUES(?,?,?,?,?,?)',(id,str(raw['title'])[:200],str(raw['artist'])[:200],str(raw.get('year',''))[:4],cover,fp))
   for i,t in enumerate(raw['tracks']):c.execute('INSERT INTO tracks VALUES(?,?,?,?,?,?)',(uid(),id,str(t.get('title',f'Pista {i+1}'))[:200],i,metadata[i],f'{id}/{i}.mp3'))
   c.execute("UPDATE jobs SET state='ready',detail='Álbum listo',album=? WHERE id=?",(id,id))
  shutil.rmtree(folder)
 except Exception as exc:
  print('Importación fallida: '+type(exc).__name__,flush=True)
  with connect(data) as c:c.execute("UPDATE jobs SET state='failed',detail='No se pudo preparar el álbum. Revisá archivos, espacio y FFmpeg; podés reintentar.' WHERE id=?",(id,))
 finally:lock.close()

if __name__=='__main__':
 from waitress import serve
 parser=argparse.ArgumentParser();parser.add_argument('--strictPort',action='store_true',help=argparse.SUPPRESS);parser.add_argument('--data');parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',default=8765,type=int);parser.add_argument('--desktop',action='store_true');args=parser.parse_args()
 os.umask(0o077);data=Path(args.data or os.environ.get('JAPS_DATA',Path.home()/'.local/share/japs-musica')).expanduser().resolve();data.mkdir(parents=True,exist_ok=True,mode=0o700)
 instance=(data/'server.lock').open('a+')
 try:fcntl.flock(instance,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('JAPs Música ya está abierto con estos datos.')
 if not shutil.which('ffmpeg'):raise SystemExit('Falta FFmpeg. Debian: sudo apt install ffmpeg · EndeavourOS: sudo pacman -S ffmpeg')
 app=create_app(data);url=f'http://127.0.0.1:{args.port}'
 with connect(data) as c:first=not c.execute('SELECT 1 FROM users').fetchone()
 print(f'JAPs Música · {url}\nDatos: {data}\nPara detener: Ctrl+C',flush=True)
 if first:print('Token local de configuración: '+app.config['SETUP_TOKEN'],flush=True)
 if args.desktop:
  import webbrowser
  threading.Timer(1,lambda:webbrowser.open(url)).start()
 serve(app,host=args.host,port=args.port,threads=6,channel_timeout=60,max_request_body_size=512*1024*1024)
