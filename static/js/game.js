/* Scrabbly live game client — vanilla JS, no dependencies. */
(function () {
  "use strict";

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

  function renderBoard() {
    for (var key in cells) {
      var cell = cells[key];
      cell.classList.remove("filled", "pending", "drop-in");
      cell.draggable = false;
      var lbl = cell.dataset.label;
      cell.innerHTML = lbl ? '<span class="premium-label">' + lbl + "</span>" : "";
    }
    state.grid.forEach(function (g) {
      var cell = cells[g.row + "," + g.col];
      if (cell) {
        cell.classList.add("filled");
        cell.innerHTML = tileHTML(g.letter, g.blank);
      }
    });
    pending.forEach(function (p) {
      var cell = cells[p.row + "," + p.col];
      if (cell) {
        cell.classList.add("filled", "pending", "drop-in");
        cell.draggable = true;
        cell.innerHTML = tileHTML(p.letter, p.isBlank);
      }
    });
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
      if (!used && isPlayer && !exchangeMode) {
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
    if (!isPlayer || used) return;
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
    refreshControls();
    renderBoard();
    renderRack();
  }

  function pendingIndexAt(row, col) {
    return pending.findIndex(function (p) { return p.row === row && p.col === col; });
  }

  // Place a rack tile (by index) onto an empty cell. Returns true on success.
  function placeFromRack(rackIdx, row, col) {
    if (!isPlayer || exchangeMode) return false;
    if (occupied(row, col)) return false;
    if (pending.some(function (p) { return p.rackIdx === rackIdx; })) return false;
    var letter = rack[rackIdx];
    var isBlank = letter === BLANK;
    if (isBlank) {
      var chosen = (prompt("Letra para la ficha comodín:") || "").toUpperCase();
      if (!chosen || !POINTS.hasOwnProperty(chosen) || chosen === BLANK) return false;
      letter = chosen;
    }
    pending.push({ row: row, col: col, letter: letter, isBlank: isBlank, rackIdx: rackIdx });
    return true;
  }

  function onCellClick(e) {
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
      li.innerHTML = '<span class="pname">' + esc(p.name) + " · " + p.rating + delta +
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
      } else if (m.kind === "pass") { desc = "pasó";
      } else if (m.kind === "exchange") { desc = "cambió fichas";
      } else { desc = "abandonó"; }
      li.innerHTML = "<b>" + esc(m.player) + "</b> " + esc(desc);
      movesEl.appendChild(li);
    });

    var banner = "";
    if (state.status === "waiting") banner = "Esperando rival…";
    else if (state.status === "finished") {
      var w = state.players.find(function (p) { return p.user_id === state.winner_id; });
      banner = w ? "Ganó " + esc(w.name) : "Empate";
    } else if (state.status === "aborted") banner = "Partida abortada";
    else if (state.turn_user_id === meId) banner = "¡Es tu turno!";
    else banner = "Turno del rival";
    bannerEl.textContent = banner;
    bannerEl.className = "status-banner s-" + state.status;
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
    var myTurn = isPlayer && state.status === "active" && state.turn_user_id === meId;
    document.getElementById("btn-play").disabled = !(myTurn && pending.length > 0);
    document.getElementById("btn-recall").disabled = pending.length === 0;
    document.getElementById("btn-pass").disabled = !myTurn;
    document.getElementById("btn-exchange").disabled = !myTurn;
    document.getElementById("btn-resign").disabled =
      !(isPlayer && (state.status === "active" || state.status === "waiting"));
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
      if (res.ok) { pending = []; flash("Jugada enviada", false); }
      else flash(res.j.error || "Jugada inválida", true);
    });
  }

  function doExchange() {
    if (!exchangeMode) {
      exchangeMode = true; exchangeSel = []; recall();
      flash("Elegí fichas para cambiar y tocá «Cambiar» de nuevo.", false);
      document.getElementById("btn-exchange").textContent = "Confirmar cambio";
      renderRack();
      return;
    }
    var letters = exchangeSel.map(function (i) { return rack[i]; });
    exchangeMode = false;
    document.getElementById("btn-exchange").textContent = "Cambiar";
    if (letters.length === 0) { renderRack(); return; }
    post("/game/" + gameId + "/exchange/", { letters: letters }).then(function (res) {
      if (!res.ok) flash(res.j.error || "No se pudo cambiar", true);
    });
  }

  // ---- WebSocket (single connection for state + chat) ----------------------
  var ws = null;
  function connect() {
    var proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws/game/" + gameId + "/");
    ws.onmessage = function (ev) {
      var data = JSON.parse(ev.data);
      if (data.type === "state") {
        var prevStatus = state.status;
        state = data.state;
        POINTS = state.points || POINTS;
        rack = data.rack;
        syncClock();
        // Drop pending tiles that are no longer ours to place.
        pending = pending.filter(function (p) { return p.rackIdx < rack.length; });
        if (state.turn_user_id !== meId) { pending = []; }
        renderAll();
        if (prevStatus !== state.status && state.status === "active") flash("", false);
      } else if (data.type === "chat") {
        appendChat(data.author, data.text);
      }
    };
    ws.onclose = function () { setTimeout(connect, 2000); };
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

  // ---- Init ----------------------------------------------------------------
  buildBoard();
  setupRackDropZone();
  syncClock();
  renderAll();
  setInterval(tickClocks, 200);
  document.getElementById("btn-play").addEventListener("click", submitPlay);
  document.getElementById("btn-recall").addEventListener("click", recall);
  document.getElementById("btn-pass").addEventListener("click", function () {
    post("/game/" + gameId + "/pass/", {}).then(function (res) {
      if (!res.ok) flash(res.j.error || "Error", true);
    });
  });
  document.getElementById("btn-exchange").addEventListener("click", doExchange);
  document.getElementById("btn-resign").addEventListener("click", function () {
    if (confirm("¿Abandonar la partida?")) {
      post("/game/" + gameId + "/resign/", {});
    }
  });
  connect();
  setupChat();
})();
