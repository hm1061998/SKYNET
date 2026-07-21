export function initializeLegacyEngine() {
"use strict";
const visual = (detail) => window.dispatchEvent(new CustomEvent('javis:visual', { detail }));
const COLORS=[[80,246,200],[79,227,255],[232,92,255],[138,108,255],[255,154,60],[235,245,255]];
const rgba=(c,a)=>`rgba(${c[0]|0},${c[1]|0},${c[2]|0},${a})`;
const STATES={
  idle:{mood:[80,246,200],label:'\u0110ang ch\u1edd'}, listening:{mood:[79,227,255],label:'S\u1eb5n s\u00e0ng'},
  thinking:{mood:[150,110,255],label:'\u0110ang suy ngh\u0129\u2026'}, speaking:{mood:[120,240,220],label:'\u0110ang tr\u1ea3 l\u1eddi\u2026'},
  working:{mood:[255,150,80],label:'\u0110ang th\u1ef1c thi\u2026'}
};
let state='idle', active=false;
const stateLabelEl=document.getElementById('stateLabel');
function labelFor(){ if(state==='idle')return active?'S\u1eb5n s\u00e0ng':'\u0110ang ch\u1edd'; if(state==='listening')return'S\u1eb5n s\u00e0ng'; return STATES[state].label; }
function setState(next){ if(!STATES[next])return; state=next; const target=STATES[next]; stateLabelEl.textContent=labelFor();
  const dot=document.getElementById('dot'); dot.style.background=rgba(target.mood,1); dot.style.boxShadow=`0 0 10px ${rgba(target.mood,1)}`; visual({type:'state',state:next}); }
function flash(color){ visual({type:'flash',color}); }
function buildNodes(names){ visual({type:'skills',skills:names}); }
let audioCtx,analyser,micBuf,micReady=false,boundarySpike=0;
async function initMic(){ if(micReady)return true; try{ const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  audioCtx=new (window.AudioContext||window.webkitAudioContext)(); const src=audioCtx.createMediaStreamSource(stream);
  analyser=audioCtx.createAnalyser(); analyser.fftSize=256; micBuf=new Uint8Array(analyser.frequencyBinCount); src.connect(analyser); micReady=true;
  }catch(_){ micReady=false; } return micReady; }
setState('idle');

// =====================================================================
//  Hội thoại
// =====================================================================
const inp=document.getElementById('inp'), transcript=document.getElementById('transcript');
let ttsOn=true, idleTimer=null;
let busy=false, lastReady=0;
function setBusy(b){ busy=b; if(!b) lastReady=Date.now(); }
const api=(p,b)=>fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})}).then(r=>r.json());
function showTranscript(){ transcript.classList.remove('hidden'); }
// chỉ tự cuộn xuống đáy khi người dùng đang ở gần đáy → giữ được vị trí khi họ cuộn lên đọc lại
function nearBottom(){ return transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 80; }
function scroll(force){ if(force || nearBottom()) transcript.scrollTop=transcript.scrollHeight; }
// cuộn bằng con lăn chuột không làm ảnh hưởng phần nền phía sau
transcript.addEventListener('wheel', e=>{ e.stopPropagation(); }, {passive:true});
function bubble(text,me){ showTranscript(); const r=document.createElement('div'); r.className='row '+(me?'me':'bot');
  const b=document.createElement('div'); b.className='bubble'; b.textContent=text; r.appendChild(b); transcript.appendChild(r); scroll(me); return b; }
function botRow(){ showTranscript(); const r=document.createElement('div'); r.className='row bot'; transcript.appendChild(r); return r; }
function esc(s){ return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function goIdle(){ active=false; setState('idle'); setBusy(false); }   // hết phiên -> quay lại "Đang chờ"

// giọng nói ra
function pickVoice(){
  const vs=speechSynthesis.getVoices()||[];
  return vs.find(v=>/hoai\s*_?my/i.test(v.name))                                  // Microsoft HoaiMy (Natural)
      || vs.find(v=>/vi([-_]|$)/i.test(v.lang)&&/natural|online|neural/i.test(v.name))
      || vs.find(v=>/vi([-_]|$)/i.test(v.lang)) || null;
}
let srvTTS=true;           // giọng HoaiMy từ server (edge-tts); hỏng thì tự rơi về giọng trình duyệt
let curAudio=null;
function speakBrowser(text,done){
  if(!('speechSynthesis'in window)){ done(); return; }
  speechSynthesis.cancel(); const u=new SpeechSynthesisUtterance(text);
  const vi=pickVoice(); if(vi)u.voice=vi; u.lang=vi?vi.lang:'vi-VN'; u.rate=1.18;
  u.onboundary=()=>{ boundarySpike=1; visual({type:'voice-pulse',strength:1}); };
  u.onend=done; u.onerror=done;
  speechSynthesis.speak(u);
}
async function speak(text,after){
  if(!ttsOn||!text){ if(after)after(); else goIdle(); return; }
  if(curAudio){ try{curAudio.pause();}catch(_){} curAudio=null; }
  if('speechSynthesis'in window) speechSynthesis.cancel();
  setState('speaking'); setBusy(true);
  const done=()=>{ curAudio=null; if(after)after(); else goIdle(); };
  if(srvTTS){
    let r=null;
    try{
      r=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},
                                body:JSON.stringify({text:String(text).slice(0,800)})});
    }catch(e){ console.warn('[tts] không gọi được server:',e); r=null; }
    if(r&&r.ok){
      try{
        const a=new Audio(URL.createObjectURL(await r.blob()));
        curAudio=a; a.onended=done;
        a.onerror=e=>{ console.warn('[tts] audio lỗi:',e); speakBrowser(text,done); };
        const tick=setInterval(()=>{ if(!curAudio){clearInterval(tick);return;} boundarySpike=1; visual({type:'voice-pulse',strength:.85}); },180);
        a.onpause=()=>clearInterval(tick);
        await a.play(); return;            // giọng HoaiMy từ server OK
      }catch(e){
        // autoplay bị chặn... — KHÔNG tắt srvTTS, chỉ fallback lần này
        console.warn('[tts] không phát được audio (autoplay?):',e);
        speakBrowser(text,done); return;
      }
    }else if(r){
      let msg=''; try{ msg=(await r.json()).error||''; }catch(_){}
      console.warn('[tts] server trả lỗi:',r.status,msg);
      srvTTS=false;                        // server TTS hỏng thật → lần sau khỏi thử
      bubble('⚠️ TTS server lỗi: '+(msg||r.status)+' — tạm dùng giọng trình duyệt. Mở 127.0.0.1:8765/api/tts-check để xem chi tiết.',false);
    }else{ srvTTS=false; }
  }
  speakBrowser(text,done);
}
function say(text){ bubble(text,false); if(ttsOn){ speak(text); } else { setState('speaking'); clearTimeout(idleTimer); idleTimer=setTimeout(goIdle,900); } }

// ===== Giọng nói vào: TỪ KHOÁ ĐÁNH THỨC (rảnh tay) =====
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
const micBtn=document.getElementById('mic');
const HINT_WAIT='Đang chờ · gọi “Javis / Em ơi/ Tùng ơi / Xin chào”';
const WAKES=['javis','jarvis','em ơi','em ei','em ê','yên nhi','yến nhi','yên như','yên nhí','tùng ơi','tùng ei','tùng',
  'xin chào','chào javis','chào em','ê javis','ơi javis','gia vít','gia vis','gia vi','da vít','za vít','javit'];
function norm(s){ return (s||'').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g,'').replace(/đ/g,'d').replace(/[^0-9a-z\s]/g,'').replace(/\s+/g,' ').trim(); }
const WAKES_N=WAKES.map(norm);
let rec=null, wakeOn=false, armed=false, armTimer=null;
function hint(txt){ const el=document.getElementById('wakehint'); el.textContent=txt; el.style.opacity=txt?'1':'0'; }
function parseUtterance(raw){
  const words=raw.trim().split(/\s+/), low=words.map(norm);
  for(let i=0;i<words.length;i++){ for(let len=Math.min(3,words.length-i); len>=1; len--){
    if(WAKES_N.includes(low.slice(i,i+len).join(' '))) return {wake:true, rest:words.slice(i+len).join(' ')}; } }
  return {wake:false, rest:raw};
}
function disarm(){ armed=false; clearTimeout(armTimer); micBtn.classList.remove('rec'); }
function arm(){ armed=true; active=true; clearTimeout(armTimer); micBtn.classList.add('rec'); if(!busy)setState('listening'); hint('Nghe rồi — mời bạn nói lệnh…');
  armTimer=setTimeout(()=>{ disarm(); active=false; if(wakeOn&&!busy){ setState('idle'); hint(HINT_WAIT); } }, 12000); }
function handleSpeech(text){
  if(busy || Date.now()-lastReady < 600) return;
  const raw=(text||'').trim(); if(!raw) return;
  const u=parseUtterance(raw);
  if(u.wake){ const rest=u.rest.replace(/^[\s,.:!?-]+/,'').trim();
    if(rest){ active=true; disarm(); inp.value=rest; send(); } else { arm(); } }
  else if(armed){ active=true; disarm(); inp.value=raw; send(); }
  else { hint('Nghe: “'+raw+'” · gọi “Javis / Em ơi …” để kích hoạt'); }
}
if(SR){
  rec=new SR(); rec.lang='vi-VN'; rec.continuous=true; rec.interimResults=false; rec.maxAlternatives=1;
  rec.onresult=e=>{ for(let i=e.resultIndex;i<e.results.length;i++){ if(e.results[i].isFinal) handleSpeech(e.results[i][0].transcript); } };
  rec.onerror=ev=>{ if(ev.error==='not-allowed'||ev.error==='service-not-allowed'){ wakeOn=false; micBtn.classList.remove('on','rec'); hint(''); bubble('Chưa cấp quyền micro. Hãy bấm "Cho phép" khi trình duyệt hỏi rồi bật lại 🎙️.',false); } };
  rec.onend=()=>{ if(wakeOn){ setTimeout(()=>{ try{ rec.start(); }catch(_){} }, 250); } };
  micBtn.onclick=async()=>{
    wakeOn=!wakeOn;
    if(wakeOn){ await initMic(); try{ rec.start(); }catch(_){}
      micBtn.classList.add('on'); micBtn.title='Đang luôn nghe — bấm để tắt'; active=false; hint(HINT_WAIT); if(!busy)setState('idle'); }
    else { disarm(); wakeOn=false; active=false; try{ rec.stop(); }catch(_){} micBtn.classList.remove('on','rec'); micBtn.title='Bật nghe rảnh tay'; hint(''); goIdle(); }
  };
} else { micBtn.onclick=()=>bubble('Trình duyệt không hỗ trợ nhận giọng nói (hãy dùng Chrome).',false); }

// logs
function cls(l){ return l.startsWith('[✓]')?'lg-ok':l.startsWith('[✗]')?'lg-no':l.startsWith('[!]')?'lg-warn':l.startsWith('[+]')?'lg-add':l.startsWith('[>]')?'lg-run':l.startsWith('[~]')?'lg-fix':l.startsWith('[TASK]')?'lg-task':'lg-dim'; }
function renderLogs(card,logs){ let pre=card.querySelector('pre.logs'); if(!pre){ pre=document.createElement('pre'); pre.className='logs'; card.appendChild(pre); }
  pre.innerHTML=''; (logs||[]).forEach(l=>{ const s=document.createElement('span'); s.className=cls(l); s.textContent=l+'\n'; pre.appendChild(s); }); scroll(); }

// kế hoạch
function renderPlan(data){ const r=botRow(); const card=document.createElement('div'); card.className='card';
  card.dataset.task=data.task; visual({type:'task',task:data.task,status:'pending'});
  const steps=(data.steps||[]).map((s,i)=>`<li><span class="n">${i+1}</span><span class="t">${esc(s)}</span></li>`).join('');
  card.innerHTML=`<div class="tag">Kế hoạch — chờ duyệt</div><h3>${esc(data.task)}</h3><ul class="steps">${steps}</ul>
    <div class="acts"><button class="btn ok">✅ Đồng ý</button><button class="btn no">✖ Từ chối</button><a class="open" href="${data.plan_url}" target="_blank">Mở ↗</a></div>`;
  r.appendChild(card); scroll(); const [ok,no]=card.querySelectorAll('button');
  ok.onclick=()=>approve(data.task,ok,no,card,data.steps); no.onclick=()=>{ ok.disabled=no.disabled=true; api('/api/reject',{task:data.task}); visual({type:'task',task:data.task,status:'error'}); goIdle(); };
  goIdle();
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function appendLogs(card,logs){ let pre=card.querySelector('pre.logs'); if(!pre){ pre=document.createElement('pre'); pre.className='logs'; card.appendChild(pre); }
  (logs||[]).forEach(l=>{ const s=document.createElement('span'); s.className=cls(l); s.textContent=l+'\n'; pre.appendChild(s); }); scroll(); }
function finishTask(res,card){
  if(res.needs_input && res.needs_input.length){ flash([255,200,90]);
    visual({type:'task',task:card.dataset.task||'Task',status:'pending'});
    bubble('❓ '+(res.ask||'Mình cần thêm thông tin để tiếp tục.'),false);
    speak(res.ask||'Mình cần thêm thông tin.'); inp.focus(); return; }
  const good=res.success; flash(good?[80,246,150]:[255,90,90]);
  visual({type:'task',task:card.dataset.task||res.skill||'Task',status:good?'done':'error'});
  const summary=good?`✅ ${res.skill}${res.generated?' (mới sinh)':''}: `+brief(res.result):`❌ Thất bại: `+brief(res.error);
  bubble(summary,false); speak(good?`Xong. ${plain(res.result)}`:'Tác vụ thất bại.'); }
async function approve(task,ok,no,card,steps){ ok.disabled=no.disabled=true; setState('working'); setBusy(true); visual({type:'task',task,status:'running'});
  const start=await api('/api/approve',{task,steps});
  if(!start.job){ renderLogs(card,start.logs); finishTask(start,card); return; }   // server cũ
  let from=0, res=null, miss=0;
  while(true){
    let j=null;
    try{ j=await fetch('/api/job?id='+start.job+'&from='+from).then(r=>r.json()); }
    catch(_){ if(++miss>30){ break; } await sleep(2000); continue; }   // mạng chớp: job vẫn chạy, thử lại
    miss=0;
    if(j.error){ break; }
    if(j.logs && j.logs.length){ appendLogs(card,j.logs); from=j.total; }
    if(j.status==='done'){ res=j.result; break; }
    await sleep(1000);
  }
  finishTask(res||{success:false,error:'Mất kết nối tới job (server có thể vẫn đang chạy — xem cửa sổ console).'},card); }
function brief(v){ if(v==null)return''; const s=(typeof v==='string')?v:JSON.stringify(v); return s.length>420?s.slice(0,420)+'…':s; }
function plain(v){ if(v==null)return''; return (typeof v==='string')?v:JSON.stringify(v); }

// gửi
async function send(){ const text=inp.value.trim(); if(!text)return; bubble(text,true); inp.value='';
  setState('thinking'); setBusy(true); const tr=botRow(); tr.innerHTML='<div class="bubble">…</div>';
  let data; try{ data=await api('/api/message',{text}); }catch(e){ tr.querySelector('.bubble').textContent='Lỗi kết nối: '+e; goIdle(); return; }
  tr.remove();
  if(data.mode==='plan'){ renderPlan(data); } else { say(data.reply||'…'); } }
document.getElementById('send').onclick=send;
inp.addEventListener('keydown',e=>{ if(e.key==='Enter'){ e.preventDefault(); send(); }});
document.getElementById('tts').onclick=function(){ ttsOn=!ttsOn; this.classList.toggle('on',ttsOn);
  if(!ttsOn){ if('speechSynthesis'in window)speechSynthesis.cancel(); if(curAudio){ try{curAudio.pause();}catch(_){} curAudio=null; } } };

// số kỹ năng thật -> số node/vector
fetch('/api/health').then(r=>r.json()).then(d=>{ if(d&&Array.isArray(d.skills)&&d.skills.length) buildNodes(d.skills); }).catch(()=>{});
if('speechSynthesis'in window) speechSynthesis.onvoiceschanged=()=>{};
inp.focus();

}
