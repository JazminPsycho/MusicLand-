"""Offline, consistent backups: stop server first; never restore over existing data."""
import argparse, fcntl, hashlib, json, os, shutil, sqlite3, tempfile
from pathlib import Path

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while block:=f.read(1024*1024):h.update(block)
 return h.hexdigest()

def backup(data,dest):
 data=Path(data).resolve();dest=Path(dest).resolve()
 if dest.exists():raise ValueError('El destino debe ser nuevo.')
 if dest.is_relative_to(data):raise ValueError('El destino debe estar fuera de los datos.')
 with (data/'server.lock').open('a+') as server,(data/'import.lock').open('a+') as worker:
  fcntl.flock(server,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB)
  dest.mkdir(mode=0o700)
  try:
   with sqlite3.connect(data/'music.sqlite') as src,sqlite3.connect(dest/'music.sqlite') as out:src.backup(out)
   shutil.copytree(data/'media',dest/'media')
   if (data/'settings.json').exists():shutil.copy2(data/'settings.json',dest/'settings.json')
   manifest={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()}
   (dest/'manifest.json').write_text(json.dumps({'schema':1,'files':manifest},indent=2))
  except Exception:shutil.rmtree(dest);raise
 return manifest

def restore(source,dest):
 source=Path(source).resolve();dest=Path(dest).resolve()
 if dest.exists():raise ValueError('El destino debe ser nuevo.')
 manifest=json.loads((source/'manifest.json').read_text())
 for name,h in manifest['files'].items():
  p=(source/name).resolve()
  if not p.is_relative_to(source) or not p.is_file() or sha(p)!=h:raise ValueError('Integridad incorrecta: '+name)
 dest.mkdir(mode=0o700)
 try:
  for name in manifest['files']:
   target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name,target)
  with sqlite3.connect(dest/'music.sqlite') as c:
   if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite inválido')
   if c.execute('PRAGMA user_version').fetchone()[0]!=1:raise ValueError('Esquema incompatible')
   c.execute('DELETE FROM sessions')
  (dest/'staging').mkdir()
 except Exception:shutil.rmtree(dest);raise

if __name__=='__main__':
 os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('action',choices=['backup','restore']);p.add_argument('source');p.add_argument('destination');a=p.parse_args()
 try:
  (backup if a.action=='backup' else restore)(a.source,a.destination);print('Operación verificada.')
 except (ValueError,BlockingIOError) as e:raise SystemExit('No se hizo la operación: '+str(e))
