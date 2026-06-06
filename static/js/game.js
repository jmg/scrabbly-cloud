/* Scrabbly live game client — vanilla JS, no dependencies. */
(function () {
  "use strict";

  // i18n: Django's JavaScriptCatalog defines window.gettext/interpolate; fall
  // back to identity helpers so the client still works without the catalog.
  var gettext = window.gettext || function (s) { return s; };
  var interpolate = window.interpolate || function (fmt, obj, named) {
    return fmt.replace(/%(?:\((\w+)\)s|s)/g, function (m, k) {
      return String(named ? obj[k] : obj.shift());
    });
  };

  var BOARD_SIZE = 15;
  var BLANK = "?";

  // Canonical premium layout (matches game/engine.py PREMIUMS).
  var PREMIUM_ROWS = [
    "T..d...T...d..T",
    ".D...t...t...D.",
    "..D...d.d...D..",
    "d..D...d...D..d",
    "....D.....D....",
    ".t...t...t...t.",
    "..d...d.d...d..",
    "T..d...D...d..T",
    "..d...d.d...d..",
    ".t...t...t...t.",
    "....D.....D....",
    "d..D...d...D..d",
    "..D...d.d...D..",
    ".D...t...t...D.",
    "T..d...T...d..T",
  ];
  var PREMIUM_CLASS = { T: "tw", D: "dw", t: "tl", d: "dl" };
  var PREMIUM_LABEL = { T: "3P", D: "2P", t: "3L", d: "2L", "*": "★" };

  var layout = document.querySelector(".game-layout");
  var gameId = layout.dataset.gameId;
  var meId = parseInt(layout.dataset.meId, 10);
  var isPlayer = layout.dataset.isPlayer === "1";

  var boardEl = document.getElementById("board");
  var rackEl = document.getElementById("rack");
  var feedbackEl = document.getElementById("feedback");
  var playersEl = document.getElementById("players");
  var movesEl = document.getElementById("moves");
  var bagEl = document.getElementById("bag-count");
  var bannerEl = document.getElementById("status-banner");
  var chatEl = document.getElementById("chat");
  var offerBox = document.getElementById("offer-box");
  var connEl = document.getElementById("conn");
  var historyBar = document.getElementById("history-bar");
  var hLabel = document.getElementById("h-label");

  var state = JSON.parse(document.getElementById("bootstrap-state").textContent);
  var rack = JSON.parse(document.getElementById("bootstrap-rack").textContent);
  // Letter point values for the game's language (sent in the state payload).
  var POINTS = state.points || {};

  // pending[idx] -> {row, col, letter, isBlank} for tiles placed this turn.
  var pending = [];
  var selectedRackIdx = null;
  var exchangeMode = false;
  var exchangeSel = [];
  var serverOffset = 0;   // serverNow - clientNow, to sync the countdown
  var flagClaimed = false; // guard so we POST /flag/ at most once per timeout
  var dragData = null;     // active drag-and-drop payload
  var reviewIndex = null;  // null = live; otherwise show board after move N
  var wasMyTurn = false;
  var redirecting = false;

  var PENDING_KEY = "scrabbly_pending_" + gameId;
  var MUTE_KEY = "scrabbly_muted";
  var muted = localStorage.getItem(MUTE_KEY) === "1";

  // ---- Board rendering -----------------------------------------------------
  var cells = {};
  function buildBoard() {
    boardEl.innerHTML = "";
    for (var r = 0; r < BOARD_SIZE; r++) {
      for (var c = 0; c < BOARD_SIZE; c++) {
        var cell = document.createElement("div");
        cell.className = "cell";
        var p = PREMIUM_ROWS[r][c];
        if (r === 7 && c === 7) {
          cell.classList.add("center");
          cell.dataset.label = PREMIUM_LABEL["*"];
        } else if (PREMIUM_CLASS[p]) {
          cell.classList.add(PREMIUM_CLASS[p]);
          cell.dataset.label = PREMIUM_LABEL[p];
        }
        cell.dataset.row = r;
        cell.dataset.col = c;
        cell.addEventListener("click", onCellClick);
        cell.addEventListener("dragstart", onCellDragStart);
        cell.addEventListener("dragover", function (e) { e.preventDefault(); });
        cell.addEventListener("drop", onCellDrop);
        boardEl.appendChild(cell);
        cells[r + "," + c] = cell;
      }
    }
  }

  function tileHTML(letter, isBlank) {
    var pts = isBlank ? 0 : (POINTS[letter] || 0);
    return '<span class="tl">' + letter + "</span><span class=\"pt\">" + pts + "</span>";
  }

  // Rebuild the board grid as it stood right after move index `idx`.
  function reconstructGrid(idx) {
    var out = [];
    for (var i = 0; i <= idx && i < state.moves.length; i++) {
      var m = state.moves[i];
      if (m.kind === "play" && m.placements) {
        m.placements.forEach(function (p) {
          out.push({ row: p.row, col: p.col, letter: p.letter, blank: !!p.is_blank });
        });
      }
    }
    return out;
  }

  // Cells placed by the move at index `idx` (to highlight in review mode).
  function placedAt(idx) {
    var m = state.moves[idx];
    var set = {};
    if (m && m.kind === "play" && m.placements) {
      m.placements.forEach(function (p) { set[p.row + "," + p.col] = true; });
    }
    return set;
  }

  function renderBoard() {
    for (var key in cells) {
      var cell = cells[key];
      cell.classList.remove("filled", "pending", "drop-in", "last");
      cell.draggable = false;
      var lbl = cell.dataset.label;
      cell.innerHTML = lbl ? '<span class="premium-label">' + lbl + "</span>" : "";
    }
    var reviewing = reviewIndex !== null;
    var grid = reviewing ? reconstructGrid(reviewIndex) : state.grid;
    var highlight = reviewing ? placedAt(reviewIndex) : {};
    grid.forEach(function (g) {
      var cell = cells[g.row + "," + g.col];
      if (cell) {
        cell.classList.add("filled");
        if (highlight[g.row + "," + g.col]) cell.classList.add("last");
        cell.innerHTML = tileHTML(g.letter, g.blank);
      }
    });
    if (!reviewing) {
      pending.forEach(function (p) {
        var cell = cells[p.row + "," + p.col];
        if (cell) {
          cell.classList.add("filled", "pending", "drop-in");
          cell.draggable = true;
          cell.innerHTML = tileHTML(p.letter, p.isBlank);
        }
      });
    }
  }

  function occupied(row, col) {
    if (state.grid.some(function (g) { return g.row === row && g.col === col; })) return true;
    return pending.some(function (p) { return p.row === row && p.col === col; });
  }

  // ---- Rack rendering ------------------------------------------------------
  function renderRack() {
    rackEl.innerHTML = "";
    rack.forEach(function (letter, idx) {
      var used = pending.some(function (p) { return p.rackIdx === idx; });
      var tile = document.createElement("div");
      tile.className = "rack-tile";
      if (used) tile.classList.add("used");
      if (selectedRackIdx === idx) tile.classList.add("selected");
      if (exchangeMode && exchangeSel.indexOf(idx) !== -1) tile.classList.add("ex-selected");
      var display = letter === BLANK ? "·" : letter;
      tile.innerHTML = tileHTML(display, letter === BLANK);
      tile.addEventListener("click", function () { onRackClick(idx, used); });
      if (!used && isPlayer && !exchangeMode && reviewIndex === null) {
        tile.draggable = true;
        tile.addEventListener("dragstart", function (e) {
          dragData = { source: "rack", rackIdx: idx };
          if (e.dataTransfer) {
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", "tile");
          }
        });
        tile.addEventListener("dragend", function () { dragData = null; });
      }
      rackEl.appendChild(tile);
    });
  }

  function onRackClick(idx, used) {
    if (!isPlayer || used || reviewIndex !== null) return;
    if (exchangeMode) {
      var pos = exchangeSel.indexOf(idx);
      if (pos === -1) exchangeSel.push(idx); else exchangeSel.splice(pos, 1);
      renderRack();
      return;
    }
    selectedRackIdx = (selectedRackIdx === idx) ? null : idx;
    renderRack();
  }

  function afterChange() {
    savePending();
    refreshControls();
    renderBoard();
    renderRack();
  }

  function pendingIndexAt(row, col) {
    return pending.findIndex(function (p) { return p.row === row && p.col === col; });
  }

  // Place a rack tile (by index) onto an empty cell. Returns true on success.
  function placeFromRack(rackIdx, row, col) {
    if (!isPlayer || exchangeMode || reviewIndex !== null) return false;
    if (occupied(row, col)) return false;
    if (pending.some(function (p) { return p.rackIdx === rackIdx; })) return false;
    var letter = rack[rackIdx];
    var isBlank = letter === BLANK;
    if (isBlank) {
      var chosen = (prompt(gettext("Letra para la ficha comodín:")) || "").toUpperCase();
      if (!chosen || !POINTS.hasOwnProperty(chosen) || chosen === BLANK) return false;
      letter = chosen;
    }
    pending.push({ row: row, col: col, letter: letter, isBlank: isBlank, rackIdx: rackIdx });
    return true;
  }

  function onCellClick(e) {
    if (reviewIndex !== null) return;
    var cell = e.currentTarget;
    var row = parseInt(cell.dataset.row, 10);
    var col = parseInt(cell.dataset.col, 10);

    // Clicking a pending tile recalls it.
    var existing = pendingIndexAt(row, col);
    if (existing !== -1) {
      pending.splice(existing, 1);
      afterChange();
      return;
    }
    if (selectedRackIdx === null) return;
    if (placeFromRack(selectedRackIdx, row, col)) {
      selectedRackIdx = null;
      afterChange();
    }
  }

  // ---- Drag & drop ---------------------------------------------------------
  function onCellDragStart(e) {
    var cell = e.currentTarget;
    var row = parseInt(cell.dataset.row, 10);
    var col = parseInt(cell.dataset.col, 10);
    var idx = pendingIndexAt(row, col);
    if (idx === -1) { e.preventDefault(); return; }
    dragData = { source: "board", pendingIdx: idx };
    if (e.dataTransfer) { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", "tile"); }
  }

  function onCellDrop(e) {
    e.preventDefault();
    var cell = e.currentTarget;
    var row = parseInt(cell.dataset.row, 10);
    var col = parseInt(cell.dataset.col, 10);
    if (!dragData) return;
    var changed = false;
    if (dragData.source === "rack") {
      if (placeFromRack(dragData.rackIdx, row, col)) { selectedRackIdx = null; changed = true; }
    } else if (dragData.source === "board") {
      var p = pending[dragData.pendingIdx];
      if (p && !occupied(row, col)) { p.row = row; p.col = col; changed = true; }
    }
    dragData = null;
    if (changed) afterChange();
  }

  function setupRackDropZone() {
    rackEl.addEventListener("dragover", function (e) { e.preventDefault(); });
    rackEl.addEventListener("drop", function (e) {
      e.preventDefault();
      if (dragData && dragData.source === "board") {
        pending.splice(dragData.pendingIdx, 1);
        afterChange();
      }
      dragData = null;
    });
  }

  function recall() {
    pending = [];
    selectedRackIdx = null;
    savePending();
    refreshControls();
    renderBoard();
    renderRack();
  }

  // ---- Players / moves / status -------------------------------------------
  function renderSide() {
    playersEl.innerHTML = "";
    state.players.forEach(function (p) {
      var li = document.createElement("li");
      var isTurn = state.turn_user_id === p.user_id;
      li.className = "player" + (isTurn ? " turn" : "");
      var delta = "";
      if (p.rating_delta !== null && p.rating_delta !== undefined) {
        var sign = p.rating_delta >= 0 ? "+" : "";
        delta = ' <em class="delta">(' + sign + p.rating_delta + ")</em>";
      }
      var clock = "";
      if (state.clock && state.clock.enabled && p.time_left_ms !== null) {
        clock = '<span class="clock" data-uid="' + p.user_id + '">' +
          formatTime(liveTimeFor(p)) + "</span>";
      }
      var crown = p.premium ? ' <span class="crown crown-' + (p.tier || "gold") +
        '" title="' + (p.tier === "diamond" ? "Diamond" : "Gold") + '">👑</span>' : "";
      li.innerHTML = '<span class="pname">' + avatarTag(p.name) + esc(p.name) + crown +
        " · " + p.rating + delta +
        "</span>" + clock + '<span class="pscore">' + p.score + '</span>' +
        '<span class="ptiles">' + p.tiles_left + " fichas</span>";
      playersEl.appendChild(li);
    });

    bagEl.textContent = state.bag_count;

    movesEl.innerHTML = "";
    state.moves.slice().reverse().forEach(function (m) {
      var li = document.createElement("li");
      var desc;
      if (m.kind === "play") {
        desc = m.words.map(function (w) { return w[0]; }).join(", ") + " (+" + m.points + ")";
      } else if (m.kind === "pass") { desc = gettext("pasó");
      } else if (m.kind === "exchange") { desc = gettext("cambió fichas");
      } else { desc = gettext("abandonó"); }
      li.innerHTML = "<b>" + esc(m.player) + "</b> " + esc(desc);
      movesEl.appendChild(li);
    });

    var banner = "";
    if (state.status === "waiting") banner = gettext("Esperando rival…");
    else if (state.status === "finished") {
      var w = state.players.find(function (p) { return p.user_id === state.winner_id; });
      banner = w ? interpolate(gettext("Ganó %s"), [esc(w.name)]) : gettext("Empate");
    } else if (state.status === "aborted") banner = gettext("Partida abortada");
    else if (state.turn_user_id === meId) banner = gettext("¡Es tu turno!");
    else banner = gettext("Turno del rival");
    bannerEl.textContent = banner;
    bannerEl.className = "status-banner s-" + state.status;

    renderOfferBox();
    renderHistoryBar();
  }

  // ---- Draw offers, rematch & sharing -------------------------------------
  function renderOfferBox() {
    var html = "";
    var amPlayer = isPlayer;
    if (state.status === "active" && state.draw_offer_by) {
      if (state.draw_offer_by === meId) {
        html = '<div class="offer">' + gettext("Ofreciste tablas…") + '</div>';
      } else if (amPlayer) {
        html = '<div class="offer">' + gettext("El rival ofrece tablas") + ' ' +
          '<button class="btn-small" id="o-draw-yes">' + gettext("Aceptar") + '</button> ' +
          '<button class="btn-small" id="o-draw-no">' + gettext("Rechazar") + '</button></div>';
      }
    } else if (state.status === "finished" || state.status === "aborted") {
      html += '<div class="offer analysis-cta">📊 <a href="/game/' + gameId +
        '/analysis/">' + gettext("Ver análisis") + '</a> <span class="crown">👑</span></div>';
      if (state.rematch && state.rematch.next_game_id) {
        html += '<div class="offer">' + gettext("Revancha lista.") + ' ' +
          '<a class="btn-small" href="/game/' + state.rematch.next_game_id + '/">' + gettext("Ir") + ' →</a></div>';
      } else if (amPlayer) {
        if (state.rematch && state.rematch.offer_by === meId) {
          html += '<div class="offer">' + gettext("Esperando que el rival acepte la revancha…") + '</div>';
        } else if (state.rematch && state.rematch.offer_by) {
          html += '<div class="offer">' + gettext("El rival quiere revancha") + ' ' +
            '<button class="btn-small" id="o-rematch">' + gettext("Aceptar") + '</button></div>';
        } else {
          html += '<div class="offer"><button class="btn-small" id="o-rematch">' + gettext("Revancha") + '</button></div>';
        }
      }
    }
    offerBox.innerHTML = html;
    offerBox.hidden = html === "";
    bind("o-draw-yes", function () { post(url("respond-draw"), { accept: true }); });
    bind("o-draw-no", function () { post(url("respond-draw"), { accept: false }); });
    bind("o-rematch", function () {
      post(url("rematch"), {}).then(function (res) {
        if (res.ok && res.j.next_game_id) location.href = "/game/" + res.j.next_game_id + "/";
      });
    });
  }

  function bind(id, fn) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("click", fn);
  }

  function url(action) { return "/game/" + gameId + "/" + action + "/"; }

  // ---- History review ------------------------------------------------------
  function renderHistoryBar() {
    var n = state.moves.length;
    historyBar.hidden = n === 0;
    if (n === 0) return;
    if (reviewIndex === null) {
      hLabel.textContent = gettext("En vivo");
    } else {
      hLabel.textContent = interpolate(
        gettext("Jugada %(n)s / %(t)s"), { n: reviewIndex + 1, t: n }, true);
    }
    document.getElementById("h-prev").disabled = reviewIndex === 0;
    document.getElementById("h-next").disabled = reviewIndex === null;
    document.getElementById("h-first").disabled = reviewIndex === 0;
    document.getElementById("h-live").disabled = reviewIndex === null;
  }

  function reviewGo(idx) {
    var n = state.moves.length;
    if (n === 0) return;
    if (idx === null || idx >= n - 1) {
      reviewIndex = null;          // back to live
    } else {
      reviewIndex = Math.max(0, idx);
    }
    renderBoard();
    renderHistoryBar();
    refreshControls();
  }

  function setupHistory() {
    document.getElementById("h-first").addEventListener("click", function () { reviewGo(0); });
    document.getElementById("h-prev").addEventListener("click", function () {
      var cur = reviewIndex === null ? state.moves.length - 1 : reviewIndex;
      reviewGo(cur - 1);
    });
    document.getElementById("h-next").addEventListener("click", function () {
      if (reviewIndex === null) return;
      reviewGo(reviewIndex + 1);
    });
    document.getElementById("h-live").addEventListener("click", function () { reviewGo(null); });
  }

  // ---- Sounds (WebAudio, no asset files) -----------------------------------
  var audioCtx = null;
  function beep(freq, durMs, type) {
    if (muted) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      var osc = audioCtx.createOscillator();
      var gain = audioCtx.createGain();
      osc.type = type || "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + durMs / 1000);
      osc.connect(gain); gain.connect(audioCtx.destination);
      osc.start(); osc.stop(audioCtx.currentTime + durMs / 1000);
    } catch (e) { /* audio not available */ }
  }
  function sound(kind) {
    if (kind === "move") beep(440, 90, "triangle");
    else if (kind === "turn") { beep(660, 110, "sine"); setTimeout(function () { beep(880, 120, "sine"); }, 120); }
    else if (kind === "end") { beep(523, 160); setTimeout(function () { beep(392, 220); }, 160); }
  }

  // ---- "Your turn" notification & tab title ---------------------------------
  function notifyTurn() {
    if (document.hidden && "Notification" in window && Notification.permission === "granted") {
      try { new Notification("Scrabbly", { body: gettext("¡Es tu turno!") }); } catch (e) {}
    }
  }
  function updateTitle() {
    var myTurn = state.status === "active" && state.turn_user_id === meId;
    document.title = (myTurn ? "🔔 " + gettext("Tu turno") + " · " : "") +
      interpolate(gettext("Partida #%s"), [gameId]) + " · Scrabbly";
  }

  // ---- Pending placement persistence (survives reloads) --------------------
  function savePending() {
    if (reviewIndex !== null) return;
    if (pending.length === 0) { localStorage.removeItem(PENDING_KEY); return; }
    localStorage.setItem(PENDING_KEY, JSON.stringify({ rack: rack, pending: pending }));
  }
  function restorePending() {
    try {
      var raw = localStorage.getItem(PENDING_KEY);
      if (!raw) return;
      var data = JSON.parse(raw);
      // Only restore if it's still my turn and the rack is unchanged.
      if (state.turn_user_id !== meId || JSON.stringify(data.rack) !== JSON.stringify(rack)) {
        localStorage.removeItem(PENDING_KEY);
        return;
      }
      pending = data.pending || [];
    } catch (e) { localStorage.removeItem(PENDING_KEY); }
  }

  // ---- Clocks --------------------------------------------------------------
  function liveTimeFor(p) {
    var base = p.time_left_ms;
    if (state.clock && state.clock.enabled &&
        state.turn_user_id === p.user_id && state.clock.turn_started_at) {
      var nowServer = Date.now() + serverOffset;
      base = p.time_left_ms - (nowServer - state.clock.turn_started_at);
    }
    return Math.max(0, base);
  }

  function formatTime(ms) {
    var total = Math.ceil(ms / 1000);
    var m = Math.floor(total / 60);
    var s = total % 60;
    if (ms < 20000) {  // show tenths under 20s, like Lichess
      var tenths = Math.floor((ms % 1000) / 100);
      return m + ":" + (s < 10 ? "0" : "") + s + "." + tenths;
    }
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function syncClock() {
    serverOffset = (state.clock && state.clock.server_now)
      ? state.clock.server_now - Date.now() : 0;
    flagClaimed = false;  // a fresh state means the previous timeout is moot
  }

  function tickClocks() {
    if (!state.clock || !state.clock.enabled) return;
    state.players.forEach(function (p) {
      var el = playersEl.querySelector('.clock[data-uid="' + p.user_id + '"]');
      if (!el) return;
      var ms = liveTimeFor(p);
      el.textContent = formatTime(ms);
      var active = state.turn_user_id === p.user_id && state.status === "active";
      el.classList.toggle("active", active);
      el.classList.toggle("low", active && ms < 15000);
      if (active && ms <= 0 && state.status === "active" && !flagClaimed) {
        flagClaimed = true;  // claim the win on time (server is authoritative)
        post("/game/" + gameId + "/flag/", {});
      }
    });
  }

  function refreshControls() {
    var reviewing = reviewIndex !== null;
    var active = state.status === "active";
    var myTurn = isPlayer && active && state.turn_user_id === meId && !reviewing;
    document.getElementById("btn-play").disabled = !(myTurn && pending.length > 0);
    document.getElementById("btn-recall").disabled = reviewing || pending.length === 0;
    document.getElementById("btn-pass").disabled = !myTurn;
    document.getElementById("btn-exchange").disabled = !myTurn;
    var drawBtn = document.getElementById("btn-draw");
    drawBtn.disabled = !(isPlayer && active && !reviewing && !state.draw_offer_by);
    drawBtn.hidden = !active;
    document.getElementById("btn-resign").disabled =
      !(isPlayer && (active || state.status === "waiting"));
    document.getElementById("btn-resign").hidden = !(active || state.status === "waiting");
  }

  // ---- Server actions ------------------------------------------------------
  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
      body: JSON.stringify(body || {}),
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); });
  }

  function flash(msg, isError) {
    feedbackEl.textContent = msg;
    feedbackEl.className = "feedback" + (isError ? " error" : " ok");
  }

  function submitPlay() {
    var placements = pending.map(function (p) {
      return { letter: p.letter, row: p.row, col: p.col, is_blank: p.isBlank };
    });
    post("/game/" + gameId + "/play/", { placements: placements }).then(function (res) {
      if (res.ok) { pending = []; localStorage.removeItem(PENDING_KEY); flash(gettext("Jugada enviada"), false); }
      else flash(res.j.error || gettext("Jugada inválida"), true);
    });
  }

  function doExchange() {
    if (!exchangeMode) {
      exchangeMode = true; exchangeSel = []; recall();
      flash(gettext("Elegí fichas para cambiar y tocá «Cambiar» de nuevo."), false);
      document.getElementById("btn-exchange").textContent = gettext("Confirmar cambio");
      renderRack();
      return;
    }
    var letters = exchangeSel.map(function (i) { return rack[i]; });
    exchangeMode = false;
    document.getElementById("btn-exchange").textContent = gettext("Cambiar");
    if (letters.length === 0) { renderRack(); return; }
    post("/game/" + gameId + "/exchange/", { letters: letters }).then(function (res) {
      if (!res.ok) flash(res.j.error || gettext("No se pudo cambiar"), true);
    });
  }

  // ---- WebSocket (single connection for state + chat) ----------------------
  var ws = null;
  var reconnectDelay = 1000;
  function setConn(stateName) {
    connEl.className = "conn " + stateName;
    connEl.title = stateName === "online" ? gettext("Conectado")
      : stateName === "offline" ? gettext("Reconectando…") : gettext("Conectando…");
  }
  function connect() {
    setConn("connecting");
    var proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws/game/" + gameId + "/");
    ws.onopen = function () { setConn("online"); reconnectDelay = 1000; };
    ws.onmessage = function (ev) {
      var data = JSON.parse(ev.data);
      if (data.type === "state") {
        applyState(data);
      } else if (data.type === "chat") {
        appendChat(data.author, data.text);
      }
    };
    ws.onclose = function () {
      setConn("offline");
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 15000);  // exponential backoff
    };
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }

  function applyState(data) {
    var prevStatus = state.status;
    var prevMoveCount = state.moves.length;
    var prevTurn = state.turn_user_id;
    state = data.state;
    POINTS = state.points || POINTS;
    rack = data.rack;
    syncClock();

    // Drop pending tiles that are no longer ours to place.
    pending = pending.filter(function (p) { return p.rackIdx < rack.length; });
    if (state.turn_user_id !== meId) { pending = []; }
    savePending();

    // A new move arrived from the server.
    if (state.moves.length > prevMoveCount) {
      if (reviewIndex !== null) reviewIndex = null;  // jump back to live on new move
      if (state.turn_user_id !== prevTurn || prevTurn === undefined) sound("move");
    }
    // Transition into my turn -> alert.
    var myTurnNow = state.status === "active" && state.turn_user_id === meId;
    if (myTurnNow && !wasMyTurn) { sound("turn"); notifyTurn(); }
    wasMyTurn = myTurnNow;

    if (prevStatus !== state.status &&
        (state.status === "finished" || state.status === "aborted")) {
      sound("end");
    }
    // Auto-jump to a freshly created rematch.
    if (state.rematch && state.rematch.next_game_id && !redirecting) {
      redirecting = true;
      setTimeout(function () { location.href = "/game/" + state.rematch.next_game_id + "/"; }, 1200);
    }

    renderAll();
    updateTitle();
    if (prevStatus !== state.status && state.status === "active") flash("", false);
  }

  function appendChat(author, text) {
    var line = document.createElement("div");
    line.className = "chat-line";
    line.innerHTML = "<b>" + esc(author) + ":</b> " + esc(text);
    chatEl.appendChild(line);
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function setupChat() {
    document.getElementById("chat-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var input = document.getElementById("chat-input");
      var text = input.value.trim();
      if (text && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "chat", text: text }));
        input.value = "";
      }
    });
  }

  // A small initials avatar with a deterministic colour from the name.
  function avatarTag(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) & 0xffffff;
    var hue = hash % 360;
    var initial = esc((name[0] || "?").toUpperCase());
    return '<span class="p-av" style="background:hsl(' + hue + ',55%,48%)">' + initial + "</span>";
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function renderAll() {
    renderBoard();
    renderRack();
    renderSide();
    refreshControls();
  }

  function updateSoundBtn() {
    document.getElementById("btn-sound").textContent = muted ? "🔇" : "🔊";
  }

  // ---- Init ----------------------------------------------------------------
  buildBoard();
  setupRackDropZone();
  setupHistory();
  syncClock();
  restorePending();
  wasMyTurn = state.status === "active" && state.turn_user_id === meId;
  renderAll();
  updateTitle();
  updateSoundBtn();
  setInterval(tickClocks, 200);

  document.getElementById("btn-play").addEventListener("click", submitPlay);
  document.getElementById("btn-recall").addEventListener("click", recall);
  document.getElementById("btn-pass").addEventListener("click", function () {
    post("/game/" + gameId + "/pass/", {}).then(function (res) {
      if (!res.ok) flash(res.j.error || gettext("Error"), true);
    });
  });
  document.getElementById("btn-exchange").addEventListener("click", doExchange);
  document.getElementById("btn-draw").addEventListener("click", function () {
    post(url("offer-draw"), {}).then(function (res) {
      if (!res.ok) flash(res.j.error || gettext("Error"), true);
    });
  });
  document.getElementById("btn-resign").addEventListener("click", function () {
    if (confirm(gettext("¿Abandonar la partida?"))) post("/game/" + gameId + "/resign/", {});
  });
  document.getElementById("btn-sound").addEventListener("click", function () {
    muted = !muted;
    localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
    updateSoundBtn();
    if (!muted) sound("move");
  });
  document.getElementById("btn-share").addEventListener("click", function () {
    var link = location.href;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(link).then(function () { flash(gettext("Enlace copiado"), false); });
    } else { prompt(gettext("Copiá el enlace:"), link); }
  });

  // Ask for notification permission once a player interacts with the page.
  if (isPlayer && "Notification" in window && Notification.permission === "default") {
    document.body.addEventListener("click", function once() {
      Notification.requestPermission();
      document.body.removeEventListener("click", once);
    }, { once: true });
  }
  // Refresh the title when the tab regains focus.
  document.addEventListener("visibilitychange", updateTitle);

  connect();
  setupChat();
})();
