/* Live in-app notifications: connects a per-user WebSocket and shows toasts. */
(function () {
  "use strict";
  var host = document.getElementById("toast-host");
  var badge = document.getElementById("notif-badge");

  function bumpBadge() {
    if (!badge) return;
    var n = parseInt(badge.textContent, 10) || 0;
    badge.textContent = n + 1;
    badge.hidden = false;
  }

  function toast(text, url) {
    if (!host) return;
    var el = document.createElement("div");
    el.className = "toast";
    if (url) {
      var a = document.createElement("a");
      a.href = url; a.textContent = text;
      el.appendChild(a);
    } else {
      el.textContent = text;
    }
    host.appendChild(el);
    setTimeout(function () { el.classList.add("show"); }, 10);
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () { el.remove(); }, 300);
    }, 6000);
  }

  function connect() {
    var proto = location.protocol === "https:" ? "wss" : "ws";
    var ws;
    try {
      ws = new WebSocket(proto + "://" + location.host + "/ws/notifications/");
    } catch (e) { return; }
    ws.onmessage = function (ev) {
      try {
        var data = JSON.parse(ev.data);
        bumpBadge();
        toast(data.text, data.url);
      } catch (e) {}
    };
    // Reconnect after a drop.
    ws.onclose = function () { setTimeout(connect, 5000); };
  }
  connect();
})();
