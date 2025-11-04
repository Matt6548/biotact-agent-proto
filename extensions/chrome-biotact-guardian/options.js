document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.sync.get({ serverUrl: "http://127.0.0.1:8000" }, (cfg) => {
    document.getElementById("serverUrl").value = cfg.serverUrl;
  });
  document.getElementById("save").addEventListener("click", () => {
    const v = document.getElementById("serverUrl").value.trim();
    chrome.storage.sync.set({ serverUrl: v || "http://127.0.0.1:8000" }, () => {
      document.getElementById("msg").textContent = "Saved";
      setTimeout(()=>document.getElementById("msg").textContent="",1500);
    });
  });
});