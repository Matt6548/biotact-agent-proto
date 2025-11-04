const BIOTACT_URL = "http://127.0.0.1:8000";
function host(u){ try{ return new URL(u).hostname.toLowerCase(); }catch{ return ""; } }
function local(h){ return !h || h==="127.0.0.1" || h==="localhost"; }

async function send(h){
  if (!h || local(h)) return;
  try{
    await fetch(`${BIOTACT_URL}/event`,{
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({source:"browser", target:h, device:"pc"})
    });
  }catch(e){}
}

chrome.webNavigation.onCommitted.addListener(d=>{ if(d.frameId===0){ send(host(d.url)); }});
chrome.tabs.onUpdated.addListener((id,info,tab)=>{ if(info.status==="complete"){ send(host(tab.url||"")); }});
chrome.tabs.onActivated.addListener(async ({tabId})=>{ try{ const t=await chrome.tabs.get(tabId); send(host(t.url||"")); }catch(e){} });