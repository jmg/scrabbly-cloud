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
      cell.classList.remove("filled", "pending");
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
        cell.classList.add("filled", "pending");
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

  function onCellClick(e) {
    var cell = e.currentTarget;
    var row = parseInt(cell.dataset.row, 10);
    var col = parseInt(cell.dataset.col, 10);

    // Clicking a pending tile recalls it.
    var existing = pending.findIndex(function (p) { return p.row === row && p.col === col; });
    if (existing !== -1) {
      pending.splice(existing, 1);
      refreshControls();
      renderBoard();
      renderRack();
      return;
    }
    if (selectedRackIdx === null || !isPlayer || exchangeMode) return;
    if (occupied(row, col)) return;

    var letter = rack[selectedRackIdx];
    var isBlank = letter === BLANK;
    if (isBlank) {
      var chosen = (prompt("Letra para la ficha comodín:") || "").toUpperCase();
      if (!chosen || !POINTS.hasOwnProperty(chosen)) return;
      letter = chosen;
    }
    pending.push({ row: row, col: col, letter: letter, isBlank: isBlank, rackIdx: selectedRackIdx });
    selectedRackIdx = null;
    refreshControls();
    renderBoard();
    renderRack();
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
      li.innerHTML = '<span class="pname">' + esc(p.name) + " · " + p.rating + delta +
        '</span><span class="pscore">' + p.score + '</span>' +
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
  renderAll();
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
