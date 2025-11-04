const $ = (id) => document.getElementById(id);
const nowIso = () => new Date().toISOString();

function setStatus(mode, text) {
  const dot = $("statusDot");
  dot.className = "dot " + (mode === "run" ? "dot-run" : mode === "warn" ? "dot-warn" : mode === "error" ? "dot-error" : "dot-idle");
  $("statusText").textContent = text;
}
function addLog(source, level, message, extra = {}) {
  LOG.push({ t: Date.now(), source, level, message, ...extra });
  const row = document.createElement("div");
  row.className = "row";
  const tagClass = source === "cam" ? "tag tag-cam" : "tag tag-scr";
  const sevClass = level === "warn" ? "sev-warn" : level === "error" ? "sev-err" : "sev-info";
  row.innerHTML = `<span class="ts">[${new Date().toLocaleTimeString()}]</span>
                   <span class="${tagClass}">${source.toUpperCase()}</span>
                   <span class="${sevClass}">${message}</span>`;
  $("logBox").prepend(row);
}
function downloadJson(filename, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

// ===== globals =====
let CAM_STREAM = null, SCR_STREAM = null;
let rafIdCam = null, rafIdScr = null;
const LOG = [];
const workCanvas = $("workCanvas");
const ctx = workCanvas.getContext("2d", { willReadFrequently: true });

// Желательное состояние источников (что пользователь хочет сейчас)
const DESIRED = { cam: false, scr: false };

// Управление рестартами с бэкоффом
const RESTART = {
  cam: { timer: null, attempts: 0 },
  scr: { timer: null, attempts: 0 }
};
function clearRestart(kind) {
  clearTimeout(RESTART[kind].timer); RESTART[kind].timer = null; RESTART[kind].attempts = 0;
}
function scheduleRestart(kind) {
  // Перезапускаем только если:
  // 1) включён автоперезапуск,
  // 2) пользователь действительно «хочет» этот источник,
  // 3) сейчас нет активного потока.
  if (!params.autoRestart || !DESIRED[kind]) return;
  const active = (kind === "cam" ? CAM_STREAM : SCR_STREAM);
  if (active) return;

  const a = ++RESTART[kind].attempts;
  const delay = Math.min(30000, 1000 * Math.pow(2, a - 1)); // 1s -> 2s -> 4s -> 8s -> 16s -> 30s...
  addLog(kind, "info", `Автоперезапуск через ${Math.round(delay / 1000)}с (попытка ${a})`);
  clearTimeout(RESTART[kind].timer);
  RESTART[kind].timer = setTimeout(() => {
    if (!DESIRED[kind]) return; // вдруг пользователь успел отменить
    if (kind === "cam") startCam(true); else startScr(true);
  }, delay);
}

// ===== FPS sparkline =====
const fpsCanvas = { cam: document.getElementById("fpsCam"), scr: document.getElementById("fpsScr") };
const fpsCtx = {
  cam: fpsCanvas.cam ? fpsCanvas.cam.getContext("2d") : null,
  scr: fpsCanvas.scr ? fpsCanvas.scr.getContext("2d") : null
};
const FPS_SERIES = { cam: [], scr: [] };
const FPS_MAX_POINTS = 120, FPS_CLAMP = 60;

// Трекеры кадров
function makeTracker(){ return { lastFrameData:null, lastWidth:0, lastHeight:0, lastFrameAt:0, frames:0, fpsWindow:[], lastAnnounceFps:0 }; }
const TRK = { cam: makeTracker(), scr: makeTracker() };

// Параметры
const params = {
  get blackOn(){ return $("chkBlack").checked; },
  get freezeOn(){ return $("chkFreeze").checked; },
  get resChangeOn(){ return $("chkResChange").checked; },
  get fpsDropOn(){ return $("chkFpsDrop").checked; },
  get idleOn(){ return $("chkIdle").checked; },
  get thBlack(){ return Math.max(1, Math.min(50, Number($("thBlack").value || 10))); },
  get thFps(){ return Math.max(1, Math.min(60, Number($("thFps").value || 8))); },
  get idleSec(){ return Math.max(2, Math.min(60, Number($("idleSec").value || 6))); },
  get autoRestart(){ return $("chkAutoRestart")?.checked ?? true; }
};

// ===== start/stop с аккуратной обработкой ошибок и событий =====
async function startCam(isAuto = false){
  DESIRED.cam = true; // пользователь/авто хотят камеру активной
  try{
    CAM_STREAM = await navigator.mediaDevices.getUserMedia({ video:{ width:{ideal:1280}, height:{ideal:720} }, audio:false });
    $("camVideo").srcObject = CAM_STREAM;
    $("btnCamStart").disabled = true; $("btnCamStop").disabled = false;
    addLog("cam","info", isAuto ? "Камера перезапущена" : "Камера запущена");
    clearRestart("cam");
    bindTrackEvents("cam", CAM_STREAM);
    setStatus("run","Идёт наблюдение");
    analyzeLoop("cam", $("camVideo"), $("camRes"), $("camFps"));
  }catch(e){
    // Если пользователь запретил доступ/закрыл выбор — не надо перезапускать
    if (e && (e.name === "NotAllowedError" || e.name === "AbortError")) {
      addLog("cam","info","Камера: доступ отклонён пользователем");
      DESIRED.cam = false; // больше не хотим автоперезапуск
      clearRestart("cam");
      $("btnCamStart").disabled = false; $("btnCamStop").disabled = true;
      if (!SCR_STREAM) setStatus("idle","Ожидание");
      return;
    }
    setStatus("error","Камера: ошибка запуска");
    addLog("cam","error","Не удалось запустить камеру",{error:String(e)});
    scheduleRestart("cam");
  }
}
function stopCam(){
  DESIRED.cam = false; // пользователь НЕ хочет камеру
  clearRestart("cam");
  if (CAM_STREAM){
    CAM_STREAM.getTracks().forEach(t=>t.stop());
    CAM_STREAM = null; $("camVideo").srcObject = null;
  }
  $("btnCamStart").disabled = false; $("btnCamStop").disabled = true;
  cancelAnimationFrame(rafIdCam);
  Object.assign(TRK.cam, makeTracker());
  addLog("cam","info","Камера остановлена");
  if (!SCR_STREAM) setStatus("idle","Ожидание");
}

async function startScr(isAuto = false){
  DESIRED.scr = true; // пользователь/авто хотят экран активным
  try{
    SCR_STREAM = await navigator.mediaDevices.getDisplayMedia({ video:{displaySurface:"monitor"}, audio:false, preferCurrentTab:true });
    $("scrVideo").srcObject = SCR_STREAM;
    $("btnScrStart").disabled = true; $("btnScrStop").disabled = false;
    addLog("scr","info", isAuto ? "Захват экрана перезапущен" : "Захват экрана запущен");
    clearRestart("scr");
    bindTrackEvents("scr", SCR_STREAM);
    setStatus("run","Идёт наблюдение");
    analyzeLoop("scr", $("scrVideo"), $("scrRes"), $("scrFps"));
  }catch(e){
    // Отмена выбора экрана — НЕ ошибка, перезапускать не нужно
    if (e && (e.name === "NotAllowedError" || e.name === "AbortError")) {
      addLog("scr","info","Пользователь отменил выбор экрана");
      DESIRED.scr = false;
      clearRestart("scr");
      $("btnScrStart").disabled = false; $("btnScrStop").disabled = true;
      if (!CAM_STREAM) setStatus("idle","Ожидание");
      return;
    }
    setStatus("error","Экран: ошибка запуска");
    addLog("scr","error","Не удалось запустить захват экрана",{error:String(e)});
    scheduleRestart("scr");
  }
}
function stopScr(){
  DESIRED.scr = false; // пользователь НЕ хочет экран
  clearRestart("scr");
  if (SCR_STREAM){
    SCR_STREAM.getTracks().forEach(t=>t.stop());
    SCR_STREAM = null; $("scrVideo").srcObject = null;
  }
  $("btnScrStart").disabled = false; $("btnScrStop").disabled = true;
  cancelAnimationFrame(rafIdScr);
  Object.assign(TRK.scr, makeTracker());
  addLog("scr","info","Захват экрана остановлен");
  if (!CAM_STREAM) setStatus("idle","Ожидание");
}

// Навешиваем события на трек: неожиданный обрыв → можно перезапускать
function bindTrackEvents(kind, stream){
  const track = stream.getVideoTracks()[0];
  if (!track) return;
  track.addEventListener("ended", () => {
    addLog(kind,"warn","Трек завершён (ended)");
    if (kind==="cam") { CAM_STREAM=null; $("camVideo").srcObject=null; $("btnCamStart").disabled=false; $("btnCamStop").disabled=true; cancelAnimationFrame(rafIdCam); Object.assign(TRK.cam, makeTracker()); }
    else { SCR_STREAM=null; $("scrVideo").srcObject=null; $("btnScrStart").disabled=false; $("btnScrStop").disabled=true; cancelAnimationFrame(rafIdScr); Object.assign(TRK.scr, makeTracker()); }
    if (!CAM_STREAM && !SCR_STREAM) setStatus("idle","Ожидание");
    scheduleRestart(kind); // только если DESIRED[kind] и autoRestart=true
  });
  track.addEventListener("mute",  () => addLog(kind,"warn","Трек «приглушён» (mute)"));
  track.addEventListener("unmute",() => addLog(kind,"info","Трек восстановлен (unmute)"));
  stream.addEventListener?.("inactive", () => {
    addLog(kind,"warn","Поток стал inactive");
    if (kind==="cam") { stopCam(); DESIRED.cam && scheduleRestart("cam"); }
    else { stopScr(); DESIRED.scr && scheduleRestart("scr"); }
  });
}

// Кнопки UI
$("btnCamStart").addEventListener("click", () => startCam(false));
$("btnCamStop").addEventListener("click", () => stopCam());
$("btnScrStart").addEventListener("click", () => startScr(false));
$("btnScrStop").addEventListener("click", () => stopScr());

// ===== анализ =====
function analyzeLoop(kind, videoEl, resLabelEl, fpsLabelEl){
  const tracker = TRK[kind];
  const step = () => {
    if (!videoEl.srcObject) return;
    const vw = videoEl.videoWidth||0, vh = videoEl.videoHeight||0;
    if (vw && vh){
      const targetW=320, targetH=Math.max(180, Math.round(targetW*vh/vw));
      if (workCanvas.width!==targetW || workCanvas.height!==targetH){ workCanvas.width=targetW; workCanvas.height=targetH; }
      ctx.drawImage(videoEl,0,0,workCanvas.width,workCanvas.height);
      const imgData = ctx.getImageData(0,0,workCanvas.width,workCanvas.height);
      const isBlack = detectBlack(imgData);
      const isFrozen = detectFrozen(tracker,imgData);
      const resChanged = detectResChange(tracker,vw,vh);
      const fps = estimateFps(tracker);
      const fpsDrop = params.fpsDropOn && fps>0 && fps<params.thFps;
      const idle = detectIdle(tracker);

      resLabelEl.textContent = `${vw}×${vh}`;
      fpsLabelEl.textContent = `${fps.toFixed(1)} fps`;

      if (params.blackOn && isBlack) addOncePer(kind,"black",()=>addLog(kind,"warn",`Обнаружен «чёрный кадр» (яркость < ${params.thBlack}% )`));
      if (params.freezeOn && isFrozen) addOncePer(kind,"frozen",()=>addLog(kind,"warn","Похоже, кадр «замёрз» (нет изменений)"));
      if (params.resChangeOn && resChanged) addLog(kind,"info",`Изменение разрешения: ${tracker.lastWidth}×${tracker.lastHeight} → ${vw}×${vh}`);
      if (params.fpsDropOn && fpsDrop && Math.abs(fps - tracker.lastAnnounceFps) > 1){ tracker.lastAnnounceFps=fps; addLog(kind,"warn",`Падение FPS: ${fps.toFixed(1)} < ${params.thFps}`); }
      if (params.idleOn && idle) addOncePer(kind,"idle",()=>addLog(kind,"warn",`Простой источника > ${params.idleSec}с (нет новых кадров)`));

      // FPS sparkline
      if (fpsCtx[kind]){
        FPS_SERIES[kind].push(Math.min(FPS_CLAMP,fps));
        if (FPS_SERIES[kind].length>FPS_MAX_POINTS) FPS_SERIES[kind].shift();
        drawFps(kind);
      }

      if (isBlack || isFrozen || fpsDrop || idle) setStatus("warn","Обнаружены предупреждения");
      else setStatus("run","Идёт наблюдение");
    }
    if (kind==="cam") rafIdCam=requestAnimationFrame(step); else rafIdScr=requestAnimationFrame(step);
  };
  step();
}

// Детекторы
function detectBlack(imgData){
  if (!imgData) return false;
  const { data } = imgData; const stride = 16;
  let sum=0, count=0;
  for (let i=0;i<data.length;i+=stride){
    const r=data[i], g=data[i+1], b=data[i+2];
    const y=0.2126*r + 0.7152*g + 0.0722*b;
    sum+=y; count++;
  }
  const avg=sum/count; const percent=(avg/255)*100;
  return percent < params.thBlack;
}
function detectFrozen(tracker,imgData){
  const now=performance.now(); const delta=now-tracker.lastFrameAt; tracker.lastFrameAt=now;
  let frozen=false;
  if (tracker.lastFrameData){
    const a=tracker.lastFrameData, b=imgData.data; let diffCount=0; const step=16;
    for (let i=0;i<b.length;i+=step){ if (b[i]!==a[i]){ diffCount++; if (diffCount>50) break; } }
    frozen = diffCount<=50 && delta>200;
  }
  tracker.lastFrameData=new Uint8ClampedArray(imgData.data);
  return frozen;
}
function detectResChange(tracker,w,h){
  if (tracker.lastWidth===0 && tracker.lastHeight===0){ tracker.lastWidth=w; tracker.lastHeight=h; return false; }
  if (tracker.lastWidth!==w || tracker.lastHeight!==h){ const changed=true; tracker.lastWidth=w; tracker.lastHeight=h; return changed; }
  return false;
}
function estimateFps(tracker){
  const now=performance.now(); tracker.frames++; tracker.fpsWindow.push(now);
  const horizon=1500; while(tracker.fpsWindow.length && now-tracker.fpsWindow[0]>horizon){ tracker.fpsWindow.shift(); }
  const dt = tracker.fpsWindow.length>1 ? (tracker.fpsWindow[tracker.fpsWindow.length-1]-tracker.fpsWindow[0])/1000 : 0.001;
  const fps = (tracker.fpsWindow.length-1)/dt; return isFinite(fps)?Math.max(0,fps):0;
}
function detectIdle(tracker){ if (!tracker.lastFrameAt) return false; const idleMs=performance.now()-tracker.lastFrameAt; return idleMs>params.idleSec*1000; }
const onceState={cam:{},scr:{}};
function addOncePer(kind,key,cb){ const map=onceState[kind]; const now=Date.now(); const prev=map[key]||0; if (now-prev>4000){ map[key]=now; cb(); } }

$("btnClearLog").addEventListener("click",()=>{ LOG.length=0; $("logBox").innerHTML=""; addLog("cam","info","Лог очищен"); });
$("btnDownloadLog").addEventListener("click",()=>{
  const payload={ exported_at:nowIso(), user_agent:navigator.userAgent,
    settings:{ black:params.blackOn, freeze:params.freezeOn, resChange:params.resChangeOn, fpsDrop:params.fpsDropOn, idle:params.idleOn, thBlack:params.thBlack, thFps:params.thFps, idleSec:params.idleSec, autoRestart: params.autoRestart },
    entries:LOG };
  downloadJson(`local-safety-log-${Date.now()}.json`, payload);
});

// FPS график
function drawFps(kind){
  const c=fpsCanvas[kind], g=fpsCtx[kind]; if (!c||!g) return;
  const w=c.width, h=c.height; g.clearRect(0,0,w,h);
  const y30 = mapFpsToY(30,h);
  g.globalAlpha=0.4; g.beginPath(); g.moveTo(0,y30); g.lineTo(w,y30); g.strokeStyle="#2a3442"; g.stroke(); g.globalAlpha=1;
  const data=FPS_SERIES[kind]; if (!data.length) return;
  g.beginPath();
  for(let i=0;i<data.length;i++){ const x=Math.round((i/(FPS_MAX_POINTS-1))*(w-1)); const y=mapFpsToY(data[i],h); if(i===0) g.moveTo(x,y); else g.lineTo(x,y); }
  g.lineWidth=2; g.strokeStyle="#70e1ff"; g.stroke();
  g.fillStyle="#9aa7b5"; g.font="12px ui-monospace, monospace"; const last=data[data.length-1]??0; g.fillText(`${last.toFixed(1)} fps`,6,14);
}
function mapFpsToY(fps,height){ const clamped=Math.max(0,Math.min(60,fps)); return Math.round((1 - clamped/60) * (height - 2)) + 1; }

// Снимки PNG
function snapshot(kind){
  const videoEl = kind==="cam" ? $("camVideo") : $("scrVideo");
  if (!videoEl || !videoEl.srcObject){ addLog(kind,"warn","Нечего снимать — источник не активен"); return; }
  const vw=videoEl.videoWidth||0, vh=videoEl.videoHeight||0;
  if (!vw || !vh){ addLog(kind,"warn","Источник ещё не отдал кадры"); return; }
  workCanvas.width=vw; workCanvas.height=vh; ctx.drawImage(videoEl,0,0,vw,vh);
  workCanvas.toBlob((blob)=>{
    if(!blob){ addLog(kind,"error","Не удалось сформировать PNG"); return; }
    const url=URL.createObjectURL(blob); const a=document.createElement("a");
    const ts=new Date().toISOString().replace(/[:.]/g,"-");
    a.href=url; a.download=`snapshot-${kind}-${ts}.png`; a.click(); URL.revokeObjectURL(url);
    addLog(kind,"info","Снимок сохранён (PNG)");
  }, "image/png");
}
$("btnSnapCam").addEventListener("click",()=>snapshot("cam"));
$("btnSnapScr").addEventListener("click",()=>snapshot("scr"));

setStatus("idle","Ожидание");
addLog("cam","info","Демо загружено. Запустите камеру и/или экран.");
