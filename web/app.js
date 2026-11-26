'use strict';
const $=s=>document.querySelector(s),content=$('#content'),audio=$('#audio');
let user=null,catalog=[],queue=[],index=-1,attempt=null,eventChain=Promise.resolve(),seq=0,lastSent=0,draft=null;
const randomID=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),x=>x.toString(16).padStart(2,'0')).join('');
const time=s=>`${Math.floor((s||0)/60)}:${String(Math.floor((s||0)%60)).padStart(2,'0')}`;
const notice=s=>{$('#notice').textContent=s;};
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function button(text,fn,cls){const b=el('button',text,cls);b.type='button';b.onclick=()=>Promise.resolve(fn()).catch(e=>notice(e.message));return b;}
function input(label,type='text',value=''){const l=el('label',label),i=el('input');i.type=type;i.value=value;l.append(i);return [l,i];}
async function api(path,body,method){const r=await fetch(path,{method:method||(body?'POST':'GET'),headers:body instanceof File?{}:{'Content-Type':'application/json'},body:body instanceof File?body:body?JSON.stringify(body):undefined});const result=await r.json();if(!r.ok){if(r.status===401&&user){audio.pause();user=null;$('#player').hidden=true;}throw Error(result.error||'No se pudo completar la solicitud.');}return result;}
async function init(){const s=await api('/api/session');user=s.user;$('#portfolio').href=s.portfolio;$('#logout').hidden=!user;for(const id of ['import','summary','users'])$('#'+id).hidden=user?.role!=='admin';if(user)await library();else auth(s.setup);}
function auth(setup=false,register=false){content.replaceChildren();$('#heading').textContent=setup?'Tu primera cuenta.':register?'Solicitá tu acceso.':'Tu música te espera.';const f=el('form'),[nl,name]=input('Nombre de usuario'),[pl,password]=input('Contraseña · al menos 12 caracteres','password');name.required=password.required=true;password.minLength=12;name.autocomplete='username';password.autocomplete=register||setup?'new-password':'current-password';f.append(nl,pl);let token;if(setup){const [l,i]=input('Token local que muestra el lanzador');token=i;f.append(l);}const submit=el('button',setup?'Crear administradora':register?'Solicitar cuenta':'Entrar');f.append(submit);f.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{const body={name:name.value,password:password.value};if(setup){const r=await fetch('/api/setup',{method:'POST',headers:{'Content-Type':'application/json','X-Setup-Token':token.value},body:JSON.stringify(body)});const j=await r.json();if(!r.ok)throw Error(j.error);}else{const j=await api(register?'/api/register':'/api/login',body);if(register){notice(j.message);auth();return;}}notice('');await init();}catch(e){notice(e.message);}finally{submit.disabled=false;}};content.append(f);if(!setup)content.append(button(register?'Ya tengo cuenta':'Solicitar una cuenta',()=>auth(false,!register),'secondary'));}
async function library(){catalog=await api('/api/catalog');$('#heading').textContent='La música que elegís.';content.replaceChildren();const [l,q]=input('Buscá por álbum, artista o canción','search'),grid=el('div',undefined,'grid');function render(){grid.replaceChildren();const text=q.value.toLocaleLowerCase();const filtered=catalog.filter(a=>[a.title,a.artist,...a.tracks.map(t=>t.title)].join(' ').toLocaleLowerCase().includes(text));for(const a of filtered){const b=button('',()=>album(a),'album');if(a.cover){const img=el('img',undefined,'art');img.src='/media/cover/'+a.id;img.alt='Portada de '+a.title;b.append(img);}else b.append(el('span','♫','art'));b.append(el('strong',a.title),el('small',a.artist+' · '+a.tracks.length+' pistas'));grid.append(b);}if(!filtered.length)grid.append(el('p',catalog.length?'No hay coincidencias. Probá otra búsqueda.':'Tu biblioteca está lista para su primer álbum.'));}q.oninput=render;content.append(l,grid);render();}
function album(a){$('#heading').textContent=a.title;content.replaceChildren(button('Volver a Biblioteca',library,'secondary'));const d=el('div',undefined,'detail'),art=el(a.cover?'img':'div',a.cover?undefined:'♫','art');if(a.cover){art.src='/media/cover/'+a.id;art.alt='Portada de '+a.title;}const list=el('section');list.append(el('h2',a.artist));for(const [i,t] of a.tracks.entries()){const b=button('',()=>play(a.tracks,i,a.artist),'track');b.append(el('span',`${i+1}. ${t.title}`),el('span',time(t.duration)));list.append(b);}d.append(art,list);content.append(d);if(user.role==='admin')content.append(button('Editar títulos y orden',()=>edit(a),'secondary'));}
function edit(a){const f=el('form'),[tl,title]=input('Álbum','text',a.title),[al,artist]=input('Artista','text',a.artist);const [cl,cover]=input('Cambiar portada (opcional)','file');cover.accept='image/jpeg,image/png';f.append(tl,al,cl);const tracks=a.tracks.map(t=>({...t})),holder=el('div');function render(){holder.replaceChildren();tracks.forEach((t,i)=>{const row=el('div',undefined,'draft-track'),[l,v]=input('Título '+(i+1),'text',t.title);v.oninput=()=>t.title=v.value;if(t.duration)l.append(el('small',time(t.duration)+' · '+(t.status||'Listo para subir')));row.append(l,button('Subir',()=>{if(i){[tracks[i-1],tracks[i]]=[tracks[i],tracks[i-1]];render();}}),button('Bajar',()=>{if(i<tracks.length-1){[tracks[i+1],tracks[i]]=[tracks[i],tracks[i+1]];render();}}));holder.append(row);});}render();f.append(holder);const save=el('button','Guardar cambios');f.append(save);f.onsubmit=async e=>{e.preventDefault();try{await api('/api/admin/albums/'+a.id,{title:title.value,artist:artist.value,year:a.year,tracks},'PATCH');if(cover.files[0])await api('/api/admin/albums/'+a.id+'/cover',cover.files[0],'PUT');await library();notice('Cambios guardados. Se conservaron IDs y estadísticas.');}catch(e){notice(e.message);}};content.replaceChildren(f);}
async function emit(type){if(!attempt)return;const current=attempt,position=audio.currentTime||0;const event={id:randomID(),seq:++seq,type,position};lastSent=Date.now();sessionStorage.setItem('japs-attempt',JSON.stringify({id:current,track:queue[index]?.id,seq,position}));eventChain=eventChain.catch(()=>{}).then(async()=>{for(let i=0;i<2;i++){try{return await api('/api/attempts/'+current+'/events',event);}catch(e){if(i)notice('Se perdió una señal de escucha: '+e.message);}}});return eventChain;}
let playChain=Promise.resolve();
function play(tracks,i,artist=''){playChain=playChain.catch(()=>{}).then(()=>switchTrack(tracks,i,artist));return playChain;}
async function switchTrack(tracks,i,artist=''){if(i<0||i>=tracks.length)return;if(attempt){await emit('skip');attempt=null;}audio.pause();queue=tracks;index=i;seq=0;attempt=(await api('/api/attempts',{track:tracks[i].id})).id;audio.src='/media/audio/'+tracks[i].id;$('#player').hidden=false;$('#now').textContent=tracks[i].title;$('#artist').textContent=artist;try{await audio.play();await emit('resume');}catch(e){notice('Tocá Reproducir para comenzar.');}}
$('#toggle').onclick=async()=>{if(audio.paused){try{await audio.play();await emit('resume');}catch(e){notice(e.message);}}else{await emit('pause');audio.pause();}};$('#previous').onclick=()=>play(queue,index-1);$('#next').onclick=()=>play(queue,index+1);audio.onplay=()=>$('#toggle').textContent='Pausar';audio.onpause=()=>$('#toggle').textContent='Reproducir';audio.ontimeupdate=()=>{$('#elapsed').textContent=time(audio.currentTime);$('#duration').textContent=time(audio.duration);$('#seek').value=Number.isFinite(audio.duration)?audio.currentTime/audio.duration*100:0;if(!audio.paused&&Date.now()-lastSent>5000)emit('progress');};$('#seek').onchange=async e=>{await emit('pause');if(Number.isFinite(audio.duration)){audio.currentTime=audio.duration*e.target.value/100;await emit('seek');}};audio.onwaiting=()=>emit('waiting');audio.onplaying=()=>emit('resume');audio.onended=async()=>{await emit('ended');attempt=null;sessionStorage.removeItem('japs-attempt');if(index+1<queue.length)play(queue,index+1);};audio.onerror=()=>{emit('error');attempt=null;notice('No se pudo reproducir. Comprobá la conexión y tu acceso.');};window.addEventListener('pagehide',()=>{if(attempt){const body=new Blob([JSON.stringify({id:randomID(),seq:++seq,type:'pause',position:audio.currentTime||0})],{type:'application/json'});navigator.sendBeacon('/api/attempts/'+attempt+'/events',body);}});
async function imports(id=null) {
  $('#heading').textContent='Dale lugar a un álbum.';
  content.replaceChildren();
  const remembered=id||draft?.id||localStorage.getItem('japs-import-id');
  let state=draft&&draft.id===remembered?draft:null;
  if (!state&&remembered) {
    const saved=await api('/api/imports/'+remembered);
    if (['draft','failed'].includes(saved.state)) {
      state={id:saved.id,revision:saved.revision,...saved.metadata,
        tracks:saved.metadata.tracks.map(t=>({...t})),received:saved.received,hasCover:saved.cover};
    } else localStorage.removeItem('japs-import-id');
  }
  if(!state){
    let legacy=null;try{legacy=JSON.parse(localStorage.getItem('japs-draft')||'null');}catch{}
    state={id:null,revision:0,title:legacy?.title||'',artist:legacy?.artist||'',year:legacy?.year||'',
      tracks:(legacy?.tracks||[]).map((t,slot)=>({slot,title:t.title})),received:{},hasCover:false};
  }
  draft=state;
  const f=el('form'),[tl,title]=input('Álbum','text',state.title),
    [al,artist]=input('Artista','text',state.artist),[yl,year]=input('Año (opcional)','text',state.year),
    [wl,wavs]=input('Agregar pistas WAV PCM','file'),[cl,cover]=input('Portada JPEG o PNG (opcional)','file');
  wavs.multiple=true;wavs.accept='.wav';cover.accept='image/jpeg,image/png';
  const tracks=el('div'),savedStatus=el('p',state.id?'Borrador recuperado. Las pistas recibidas no necesitan subirse otra vez.':''),
    submit=el('button','Preparar álbum');
  savedStatus.setAttribute('role','status');
  let busy=false,saveChain=Promise.resolve();
  const metadata=()=>({title:state.title,artist:state.artist,year:state.year,
    tracks:state.tracks.map(t=>({slot:t.slot,title:t.title}))});
  function save() {
    const snapshot=metadata();
    saveChain=saveChain.catch(()=>{}).then(async()=>{
      if(!state.id){state.id=(await api('/api/imports',{})).id;localStorage.setItem('japs-import-id',state.id);}
      const result=await api('/api/imports/'+state.id+'/draft',{...snapshot,revision:state.revision},'PUT');
      state.revision=result.revision;savedStatus.textContent='Borrador guardado en el servidor.';
    });
    return saveChain;
  }
  function changed(){save().catch(e=>{savedStatus.textContent=e.message;});}
  function render() {
    tracks.replaceChildren();
    state.tracks.forEach((t,i)=>{
      const row=el('div',undefined,'import-track'),[label,value]=input('Pista '+(i+1),'text',t.title);
      value.disabled=busy;value.oninput=()=>{t.title=value.value;changed();};
      const received=state.received[String(t.slot)];
      row.append(label,el('p',received?'Recibida · '+time(received.duration):t.file?'Seleccionada · pendiente de subir':'Falta seleccionar el WAV'));
      const controls=el('div',undefined,'actions');
      const up=button('Subir',()=>{if(i){[state.tracks[i-1],state.tracks[i]]=[state.tracks[i],state.tracks[i-1]];render();changed();}}),
        down=button('Bajar',()=>{if(i<state.tracks.length-1){[state.tracks[i+1],state.tracks[i]]=[state.tracks[i],state.tracks[i+1]];render();changed();}});
      up.disabled=busy||i===0;down.disabled=busy||i===state.tracks.length-1;controls.append(up,down);
      const [fileLabel,picker]=input(received?'Reemplazar WAV (opcional)':'Seleccionar este WAV','file');
      picker.accept='.wav';picker.disabled=busy;
      picker.onchange=()=>{if(picker.files[0]){t.file=picker.files[0];delete state.received[String(t.slot)];render();}};
      row.append(controls,fileLabel);tracks.append(row);
    });
  }
  for(const [field,name] of [[title,'title'],[artist,'artist'],[year,'year']])field.oninput=()=>{state[name]=field.value;changed();};
  wavs.onchange=()=>{
    let next=Math.max(-1,...state.tracks.map(t=>t.slot))+1;
    for(const file of wavs.files)state.tracks.push({slot:next++,title:file.name.replace(/\.wav$/i,''),file});
    wavs.value='';render();changed();
  };
  cover.onchange=()=>{state.coverFile=cover.files[0]||null;};
  f.append(tl,al,yl,wl,cl,savedStatus,tracks,submit);render();
  if(state.hasCover)f.append(el('p','La portada recibida se conserva.'));
  f.onsubmit=async e=>{
    e.preventDefault();if(busy)return;
    if(!state.tracks.length||!state.title.trim()||!state.artist.trim()){notice('Completá artista, álbum y al menos una pista.');return;}
    const missing=state.tracks.filter(t=>!state.received[String(t.slot)]&&!t.file);
    if(missing.length){notice('Seleccioná los WAV pendientes. Las pistas ya recibidas se conservan.');return;}
    busy=true;for(const element of f.querySelectorAll('input,button'))element.disabled=true;render();
    try {
      await save();
      for(const [i,t] of state.tracks.entries()) {
        if(state.received[String(t.slot)])continue;
        notice(`Subiendo pista ${i+1}/${state.tracks.length}…`);
        await api(`/api/imports/${state.id}/files/${t.slot}`,t.file,'PUT');
        state.received[String(t.slot)]={duration:0};render();
      }
      if(state.coverFile){await api(`/api/imports/${state.id}/files/cover`,state.coverFile,'PUT');state.coverFile=null;state.hasCover=true;}
      await api(`/api/imports/${state.id}/start`,{...metadata(),revision:state.revision});
      localStorage.removeItem('japs-import-id');draft=null;
      notice('Álbum en preparación. Podés seguir navegando.');
      await imports();
    } catch(e) {
      notice(e.message+' Podés volver a abrir esta importación: las pistas recibidas se conservan.');
      busy=false;for(const element of f.querySelectorAll('input,button'))element.disabled=false;render();
    }
  };
  content.append(f);await showJobs();
}
async function showJobs() {
  let list=$('#jobs');if(!list){list=el('section');list.id='jobs';content.append(list);}
  const jobs=await api('/api/imports');list.replaceChildren(el('h2','Importaciones'));
  for(const j of jobs) {
    const row=el('div',undefined,'user');row.append(el('span',`${j.state} · ${j.detail}`));
    if(['draft','failed'].includes(j.state))row.append(button('Abrir y continuar',()=>{draft=null;return imports(j.id);},'secondary'));
    if(j.state==='failed')row.append(button('Reintentar conversión',async()=>{
      await api(`/api/imports/${j.id}/start`,{});notice('Reintento en preparación, sin volver a subir las pistas.');await showJobs();
    }));
    list.append(row);
  }
  list.append(button('Actualizar estado',showJobs,'secondary'));
}
async function users(){ $('#heading').textContent='Tu espacio, compartido.';content.replaceChildren();for(const u of await api('/api/admin/users')){const row=el('div',undefined,'user');row.append(el('span',`${u.name} · ${u.role} · ${u.state}`));row.append(button(u.state==='active'?'Revocar':'Aprobar',async()=>{await api('/api/admin/users/'+u.id,{state:u.state==='active'?'revoked':'active'},'PATCH');await users();}));content.append(row);}}
async function summary(){ $('#heading').textContent='Lo que suena en tu espacio.';content.replaceChildren();const f=el('form'),[fl,from]=input('Desde','date',new Date().toISOString().slice(0,8)+'01'),[tl,to]=input('Hasta','date',new Date().toISOString().slice(0,10));f.append(fl,tl,el('button','Ver resumen'));const dimension=el('select');dimension.setAttribute('aria-label','Agrupar resumen');for(const [value,label] of [['track','Canción'],['album','Álbum'],['artist','Artista'],['user','Usuario']])dimension.append(new Option(label,value));f.append(dimension);const results=el('section');async function load(){const s=await api(`/api/admin/summary?from=${from.value}&to=${to.value}`);results.replaceChildren(el('p',`${from.value} — ${to.value} · ${s.zone}`));const grid=el('div',undefined,'grid');for(const [label,value] of [['Escuchas',s.rows.reduce((n,r)=>n+r.valid,0)],['Tiempo efectivo',time(s.rows.reduce((n,r)=>n+r.seconds,0))],['Finalizaciones',s.rows.reduce((n,r)=>n+r.complete,0)],['Saltos',s.rows.filter(r=>r.closed==='skip').length],['Usuarios que vuelven',s.returning],['Errores',s.rows.filter(r=>r.closed==='error').length]]){const card=el('div',label,'stat');card.append(el('strong',value));grid.append(card);}results.append(grid);const grouped=new Map();for(const r of s.rows){const key=r[dimension.value];if(!grouped.has(key))grouped.set(key,{...r,seconds:0,valid:0});const g=grouped.get(key);g.seconds+=r.seconds;g.valid+=r.valid;}const table=el('table'),head=el('tr');for(const label of ['Canción','Álbum','Artista','Escuchas','Tiempo'])head.append(el('th',label));table.append(head);for(const r of grouped.values()){const tr=el('tr');for(const val of [dimension.value==='track'?r.title:dimension.value==='album'?r.album_title:dimension.value==='artist'?r.artist:r.name,dimension.value==='track'?r.album_title:'—',dimension.value==='track'||dimension.value==='album'?r.artist:'—',r.valid,time(r.seconds)])tr.append(el('td',val));table.append(tr);}const wrap=el('div',undefined,'table-wrap');wrap.append(table);results.append(wrap,el('h2','Tiempo por hora local'));const hours=el('p',s.hours.map((v,h)=>`${String(h).padStart(2,'0')}:00 · ${time(v)}`).join(' | '));results.append(hours);}f.onsubmit=e=>{e.preventDefault();load().catch(e=>notice(e.message));};content.append(f,results);await load();}
$('#library').onclick=()=>user?library().catch(e=>notice(e.message)):init();$('#import').onclick=()=>imports().catch(e=>notice(e.message));$('#summary').onclick=()=>summary().catch(e=>notice(e.message));$('#users').onclick=()=>users().catch(e=>notice(e.message));$('#logout').onclick=async()=>{await emit('pause');audio.pause();audio.removeAttribute('src');audio.load();attempt=null;sessionStorage.clear();draft=null;localStorage.removeItem('japs-import-id');localStorage.removeItem('japs-draft');await api('/api/logout',{});$('#player').hidden=true;await init();};
init().then(async()=>{if(!user)return;const saved=JSON.parse(sessionStorage.getItem('japs-attempt')||'null');if(!saved)return;try{const a=await api('/api/attempts/'+saved.id);if(a.closed)return;const album=catalog.find(a=>a.tracks.some(t=>t.id===saved.track));if(!album)return;queue=album.tracks;index=queue.findIndex(t=>t.id===saved.track);seq=a.seq;attempt=a.id;audio.src='/media/audio/'+a.track;audio.addEventListener('loadedmetadata',()=>{audio.currentTime=a.position;emit('seek');},{once:true});$('#now').textContent=queue[index].title;$('#artist').textContent=album.artist;$('#player').hidden=false;}catch{sessionStorage.removeItem('japs-attempt');}}).catch(e=>notice(e.message));
