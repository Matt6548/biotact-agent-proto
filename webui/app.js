// ====== helpers ======
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

// ====== global state ======
let CAM_STREAM = null;
let SCR_STREAM = null;
let rafIdCam = null;
let rafIdScr = null;
const LOG = [];

const workCanvas = $("workCanvas");
const ctx = workCanvas.getContext("2d", { willReadFrequently: true });

// Per-source trackers
function makeTracker() {
  return {
    lastFrameData: null,
    lastWidth: 0,
    lastHeight: 0,
    lastFrameAt: 0,
    frames: 0,
    fpsWindow: [],
    lastAnnounceFps: 0,
  };
}
const TRK = {
  cam: makeTracker(),
  scr: makeTracker(),
};

// ====== analysis parameters (read from UI) ======
const params = {
  // toggles
  get blackOn() { return $("chkBlack").checked; },
  get freezeOn() { return $("chkFreeze").checked; },
  get resChangeOn() { return $("chkResChange").checked; },
  get fpsDropOn() { return $("chkFpsDrop").checked; },
  get idleOn() { return $("chkIdle").checked; },
  // thresholds
  get thBlack() { return Math.max(1, Math.min(50, Number($("thBlack").value || 10))); },  // percent
  get thFps() { return Math.max(1, Math.min(60, Number($("thFps").value || 8))); },
  get idleSec() { return Math.max(2, Math.min(60, Number($("idleSec").value || 6))); },
};

// ====== stream controls ======
$("btnCamStart").addEventListener("click", async () => {
  try {
    CAM_STREAM = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    $("camVideo").srcObject = CAM_STREAM;
    $("btnCamStart").disabled = true;
    $("btnCamStop").disabled = false;
    addLog("cam", "info", "Камера запущена");
    setStatus("run", "Идёт наблюдение");
    analyzeLoop("cam", $("camVideo"), $("camRes"), $("camFps"));
  } catch (e) {
    console.error(e);
    setStatus("error", "Камера: доступ отклонён/ошибка");
    addLog("cam", "error", "Не удалось запустить камеру", { error: String(e) });
  }
});

$("btnCamStop").addEventListener("click", () => stopSource("cam"));

$("btnScrStart").addEventListener("click", async () => {
  try {
    SCR_STREAM = await navigator.mediaDevices.getDisplayMedia({
      video: { displaySurface: "monitor" },
      audio: false,
      preferCurrentTab: true,
    });
    $("scrVideo").srcObject = SCR_STREAM;
    $("btnScrStart").disabled = true;
    $("btnScrStop").disabled = false;
    addLog("scr", "info", "Захват экрана запущен");
    setStatus("run", "Идёт наблюдение");
    analyzeLoop("scr", $("scrVideo"), $("scrRes"), $("scrFps"));

    // handle manual stop by user via browser UI
    SCR_STREAM.getVideoTracks()[0].addEventListener("ended", () => {
      stopSource("scr");
      addLog("scr", "info", "Экран остановлен пользователем");
    });
  } catch (e) {
    console.error(e);
    setStatus("error", "Экран: доступ отклонён/ошибка");
    addLog("scr", "error", "Не удалось запустить захват экрана", { error: String(e) });
  }
});

$("btnScrStop").addEventListener("click", () => stopSource("scr"));

function stopSource(kind) {
  if (kind === "cam" && CAM_STREAM) {
    CAM_STREAM.getTracks().forEach(t => t.stop());
    CAM_STREAM = null;
    $("camVideo").srcObject = null;
    $("btnCamStart").disabled = false;
    $("btnCamStop").disabled = true;
    cancelAnimationFrame(rafIdCam);
    TRK.cam = Object.assign(TRK.cam, makeTracker());
    addLog("cam", "info", "Камера остановлена");
  }
  if (kind === "scr" && SCR_STREAM) {
    SCR_STREAM.getTracks().forEach(t => t.stop());
    SCR_STREAM = null;
    $("scrVideo").srcObject = null;
    $("btnScrStart").disabled = false;
    $("btnScrStop").disabled = true;
    cancelAnimationFrame(rafIdScr);
    TRK.scr = Object.assign(TRK.scr, makeTracker());
    addLog("scr", "info", "Захват экрана остановлен");
  }
  if (!CAM_STREAM && !SCR_STREAM) {
    setStatus("idle", "Ожидание");
  }
}

// ====== analysis loop ======
function analyzeLoop(kind, videoEl, resLabelEl, fpsLabelEl) {
  const tracker = TRK[kind];
  const step = () => {
    if (!videoEl.srcObject) return; // stopped

    const vw = videoEl.videoWidth || 0;
    const vh = videoEl.videoHeight || 0;
    if (vw && vh) {
      // Resize canvas to small preview for faster analysis
      const targetW = 320;
      const targetH = Math.max(180, Math.round(targetW * vh / vw));
      if (workCanvas.width !== targetW || workCanvas.height !== targetH) {
        workCanvas.width = targetW;
        workCanvas.height = targetH;
      }
      ctx.drawImage(videoEl, 0, 0, workCanvas.width, workCanvas.height);
      const imgData = ctx.getImageData(0, 0, workCanvas.width, workCanvas.height);
      const isBlack = detectBlack(imgData);
      const isFrozen = detectFrozen(tracker, imgData);
      const resChanged = detectResChange(tracker, vw, vh);
      const fps = estimateFps(tracker);
      const fpsDrop = params.fpsDropOn && fps > 0 && fps < params.thFps;
      const idle = detectIdle(tracker);

      // UI meta
      resLabelEl.textContent = `${vw}×${vh}`;
      fpsLabelEl.textContent = `${fps.toFixed(1)} fps`;

      // Events & logging
      if (params.blackOn && isBlack) addOncePer(kind, "black", () =>
        addLog(kind, "warn", `Обнаружен «чёрный кадр» (яркость < ${params.thBlack}% )`)
      );

      if (params.freezeOn && isFrozen) addOncePer(kind, "frozen", () =>
        addLog(kind, "warn", "Похоже, кадр «замёрз» (нет изменений)")
      );

      if (params.resChangeOn && resChanged) addLog(kind, "info", `Изменение разрешения: ${tracker.lastWidth}×${tracker.lastHeight} → ${vw}×${vh}`);

      if (params.fpsDropOn && fpsDrop && Math.abs(fps - tracker.lastAnnounceFps) > 1) {
        tracker.lastAnnounceFps = fps;
        addLog(kind, "warn", `Падение FPS: ${fps.toFixed(1)} < ${params.thFps}`);
      }

      if (params.idleOn && idle) addOncePer(kind, "idle", () =>
        addLog(kind, "warn", `Простой источника > ${params.idleSec}с (нет новых кадров)`)
      );

      // status LED escalation
      if (isBlack || isFrozen || fpsDrop || idle) {
        setStatus("warn", "Обнаружены предупреждения");
      } else {
        setStatus("run", "Идёт наблюдение");
      }
    }

    if (kind === "cam") rafIdCam = requestAnimationFrame(step);
    else rafIdScr = requestAnimationFrame(step);
  };
  step();
}

// ====== detectors ======
function detectBlack(imgData) {
  if (!imgData) return false;
  const { data, width, height } = imgData;
  // sample pixels (stride) for speed
  const stride = 4 * 4; // skip 3 pixels between
  let sum = 0;
  let count = 0;
  for (let i = 0; i < data.length; i += stride) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    // perceived luminance (approx)
    const y = 0.2126*r + 0.7152*g + 0.0722*b;
    sum += y;
    count++;
  }
  const avg = sum / count; // 0..255
  const percent = (avg / 255) * 100;
  return percent < params.thBlack;
}

function detectFrozen(tracker, imgData) {
  const now = performance.now();
  const delta = now - tracker.lastFrameAt;
  tracker.lastFrameAt = now;

  // difference with last frame
  let frozen = false;
  if (tracker.lastFrameData) {
    const a = tracker.lastFrameData;
    const b = imgData.data;
    // quick coarse diff
    let diffCount = 0;
    const step = 16; // skip for speed
    for (let i = 0; i < b.length; i += step) {
      if (b[i] !== a[i]) { diffCount++; if (diffCount > 50) break; }
    }
    // if almost no difference across many samples -> frozen
    frozen = diffCount <= 50 && delta > 200; // at least ~5 fps timeframe
  }
  tracker.lastFrameData = new Uint8ClampedArray(imgData.data); // clone
  return frozen;
}

function detectResChange(tracker, w, h) {
  if (tracker.lastWidth === 0 && tracker.lastHeight === 0) {
    tracker.lastWidth = w; tracker.lastHeight = h; return false;
  }
  if (tracker.lastWidth !== w || tracker.lastHeight !== h) {
    const changed = true;
    tracker.lastWidth = w; tracker.lastHeight = h;
    return changed;
  }
  return false;
}

function estimateFps(tracker) {
  const now = performance.now();
  tracker.frames++;
  tracker.fpsWindow.push(now);
  // keep last 1.5s
  const horizon = 1500;
  while (tracker.fpsWindow.length && now - tracker.fpsWindow[0] > horizon) {
    tracker.fpsWindow.shift();
  }
  const dt = tracker.fpsWindow.length > 1 ? (tracker.fpsWindow[tracker.fpsWindow.length - 1] - tracker.fpsWindow[0]) / 1000 : 0.001;
  const fps = (tracker.fpsWindow.length - 1) / dt;
  return isFinite(fps) ? Math.max(0, fps) : 0;
}

function detectIdle(tracker) {
  if (!tracker.lastFrameAt) return false;
  const idleMs = performance.now() - tracker.lastFrameAt;
  return idleMs > params.idleSec * 1000;
}

// prevent spamming repeating logs of the same kind
const onceState = { cam: {}, scr: {} };
function addOncePer(kind, key, cb) {
  const map = onceState[kind];
  const now = Date.now();
  const prev = map[key] || 0;
  if (now - prev > 4000) { // 4s cooldown
    map[key] = now; cb();
  }
}

// ====== log controls ======
$("btnClearLog").addEventListener("click", () => {
  LOG.length = 0;
  $("logBox").innerHTML = "";
  addLog("cam", "info", "Лог очищен");
});

$("btnDownloadLog").addEventListener("click", () => {
  const payload = {
    exported_at: nowIso(),
    user_agent: navigator.userAgent,
    settings: {
      black: params.blackOn, freeze: params.freezeOn, resChange: params.resChangeOn, fpsDrop: params.fpsDropOn, idle: params.idleOn,
      thBlack: params.thBlack, thFps: params.thFps, idleSec: params.idleSec,
    },
    entries: LOG,
  };
  downloadJson(`local-safety-log-${Date.now()}.json`, payload);
});
// ====== snapshots (PNG) ======
function snapshot(kind) {
  const videoEl = kind === "cam" ? $("camVideo") : $("scrVideo");
  if (!videoEl || !videoEl.srcObject) {
    addLog(kind, "warn", "Нечего снимать — источник не активен");
    return;
  }

  // подгоняем рабочий холст под текущий размер видео
  const vw = videoEl.videoWidth || 0;
  const vh = videoEl.videoHeight || 0;
  if (!vw || !vh) {
    addLog(kind, "warn", "Источник ещё не отдал кадры");
    return;
  }
  workCanvas.width = vw;
  workCanvas.height = vh;
  ctx.drawImage(videoEl, 0, 0, vw, vh);

  workCanvas.toBlob((blob) => {
    if (!blob) {
      addLog(kind, "error", "Не удалось сформировать PNG");
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    a.href = url;
    a.download = `snapshot-${kind}-${ts}.png`;
    a.click();
    URL.revokeObjectURL(url);
    addLog(kind, "info", "Снимок сохранён (PNG)");
  }, "image/png");
}

// кнопки снимков
$("btnSnapCam").addEventListener("click", () => snapshot("cam"));
$("btnSnapScr").addEventListener("click", () => snapshot("scr"));


// ====== safe defaults ======
setStatus("idle", "Ожидание");
addLog("cam", "info", "Демо загружено. Запустите камеру и/или экран.");
