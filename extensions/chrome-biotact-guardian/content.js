(function(){
  const host = location.hostname;
  const key  = "biotact_allow_" + host;
  const now  = Date.now();
  if (Number(localStorage.getItem(key)||0) > now) return;

  fetch("http://127.0.0.1:8000/policy/check?url=" + encodeURIComponent(host))
    .then(r=>r.json()).then(d=>{
      const dec = (d&&d.decision)||{};
      if (d&&d.ignored) return;      // вне области контроля — не вмешиваемся
      if (!dec.violation) return;

      const reasons = (dec.reason||[]).join(", ") || "policy";
      const s=document.createElement("style");
      s.textContent="#biotact-overlay{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:2147483647;display:flex;align-items:center;justify-content:center}#biotact-box{background:#fff;border-radius:14px;max-width:560px;width:92%;padding:20px;font-family:system-ui}#biotact-box h3{margin:0 0 10px}#biotact-box .row{display:flex;gap:10px;margin-top:8px;flex-wrap:wrap}#biotact-box button{padding:10px 14px;border-radius:10px;border:1px solid #ccc;background:#fafafa;cursor:pointer}";
      const w=document.createElement("div");
      w.id="biotact-overlay";
      w.innerHTML=`<div id="biotact-box"><h3>Biotact — ограничено</h3><p>Причина: <b>${reasons}</b>. Домен: ${host}</p><div class="row"><button id="b-ok">Продолжить 2 минуты</button><button id="b-close">Закрыть вкладку</button></div></div>`;
      document.documentElement.append(s,w);
      w.querySelector("#b-ok").onclick=()=>{ localStorage.setItem(key, String(Date.now()+2*60*1000)); fetch("http://127.0.0.1:8000/event",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:"overlay",target:host,device:"pc",override:true})}).catch(()=>{}); w.remove(); };
      w.querySelector("#b-close").onclick=()=>{ window.close(); history.back(); };
    }).catch(()=>{});
})();