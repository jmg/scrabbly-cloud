/* Scrabbly puzzle board — standalone, no websocket. */
(function () {
  "use strict";
  var gettext = window.gettext || function (s) { return s; };
  var interpolate = window.interpolate || function (f, o, n) {
    return f.replace(/%(?:\((\w+)\)s|s)/g, function (m, k) { return String(n ? o[k] : o.shift()); });
  };

  var SIZE = 15, BLANK = "?";
  var PREMIUM_ROWS = [
    "T..d...T...d..T", ".D...t...t...D.", "..D...d.d...D..", "d..D...d...D..d",
    "....D.....D....", ".t...t...t...t.", "..d...d.d...d..", "T..d...D...d..T",
    "..d...d.d...d..", ".t...t...t...t.", "....D.....D....", "d..D...d...D..d",
    "..D...d.d...D..", ".D...t...t...D.", "T..d...T...d..T",
  ];
  var PREMIUM_CLASS = { T: "tw", D: "dw", t: "tl", d: "dl" };
  var PREMIUM_LABEL = { T: "3P", D: "2P", t: "3L", d: "2L", "*": "★" };

  var root = document.querySelector(".puzzle-layout");
  var boardEl = document.getElementById("board");
  var rackEl = document.getElementById("rack");
  var feedbackEl = document.getElementById("feedback");
  var resultEl = document.getElementById("puzzle-result");
  var S = JSON.parse(document.getElementById("puzzle-state").textContent);
  var POINTS = S.points || {};

  var grid = S.grid || {};                 // fixed board letters "r,c" -> letter
  var pending = [];                        // {row,col,letter,isBlank,rackIdx}
  var rackUsed = {};                       // rackIdx -> true
  var selected = null;                     // selected rack index
  var solved = false;

  function tileHTML(letter, isBlank) {
    var pts = isBlank ? 0 : (POINTS[letter] || 0);
    return '<span class="tl">' + letter + '</span><span class="pt">' + pts + "</span>";
  }

  function pendingAt(r, c) {
    for (var i = 0; i < pending.length; i++)
      if (pending[i].row === r && pending[i].col === c) return pending[i];
    return null;
  }

  function buildBoard() {
    boardEl.innerHTML = "";
    for (var r = 0; r < SIZE; r++) {
      for (var c = 0; c < SIZE; c++) {
        var cell = document.createElement("div");
        cell.className = "cell";
        var p = PREMIUM_ROWS[r][c];
        var lbl = "";
        if (r === 7 && c === 7) { cell.classList.add("center"); lbl = PREMIUM_LABEL["*"]; }
        else if (PREMIUM_CLASS[p]) { cell.classList.add(PREMIUM_CLASS[p]); lbl = PREMIUM_LABEL[p]; }
        var key = r + "," + c;
        var pend = pendingAt(r, c);
        if (grid[key]) {
          cell.classList.add("filled");
          cell.innerHTML = tileHTML(grid[key], false);
        } else if (pend) {
          cell.classList.add("filled", "pending");
          cell.innerHTML = tileHTML(pend.letter, pend.isBlank);
          (function (pp) { cell.addEventListener("click", function () { removePending(pp); }); })(pend);
        } else {
          if (lbl) cell.innerHTML = '<span class="premium-label">' + lbl + "</span>";
          if (!solved) {
            (function (rr, cc) { cell.addEventListener("click", function () { placeAt(rr, cc); }); })(r, c);
          }
        }
        boardEl.appendChild(cell);
      }
    }
  }

  function buildRack() {
    rackEl.innerHTML = "";
    S.rack.forEach(function (letter, idx) {
      var tile = document.createElement("div");
      tile.className = "rack-tile";
      if (rackUsed[idx]) tile.classList.add("used");
      if (selected === idx) tile.classList.add("selected");
      var disp = letter === BLANK ? "·" : letter;
      tile.innerHTML = tileHTML(disp, letter === BLANK);
      if (!rackUsed[idx] && !solved) {
        tile.addEventListener("click", function () {
          selected = (selected === idx) ? null : idx;
          buildRack();
        });
      }
      rackEl.appendChild(tile);
    });
  }

  function placeAt(r, c) {
    if (selected === null) { flash(gettext("Elegí una ficha del atril primero.")); return; }
    var letter = S.rack[selected], isBlank = false;
    if (letter === BLANK) {
      var ch = (prompt(gettext("Letra para la ficha comodín:")) || "").toUpperCase();
      if (!ch) return;
      letter = ch; isBlank = true;
    }
    pending.push({ row: r, col: c, letter: letter, isBlank: isBlank, rackIdx: selected });
    rackUsed[selected] = true;
    selected = null;
    render();
  }

  function removePending(p) {
    pending = pending.filter(function (x) { return x !== p; });
    delete rackUsed[p.rackIdx];
    render();
  }

  function recall() { pending = []; rackUsed = {}; selected = null; render(); }

  function flash(msg) { feedbackEl.textContent = msg; }

  function render() { buildBoard(); buildRack(); }

  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
      body: JSON.stringify(body),
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); });
  }

  document.getElementById("btn-recall").addEventListener("click", recall);
  document.getElementById("btn-submit").addEventListener("click", function () {
    if (!pending.length) { flash(gettext("Colocá fichas para formar una palabra.")); return; }
    var placements = pending.map(function (p) {
      return { letter: p.letter, row: p.row, col: p.col, is_blank: p.isBlank };
    });
    postJSON(root.dataset.solveUrl, { placements: placements }).then(function (res) {
      if (!res.ok) { flash(res.j.error || gettext("Jugada inválida")); return; }
      flash("");
      var msg = interpolate(gettext("Tu jugada: %(you)s · Mejor: %(best)s"),
        { you: res.j.your_score, best: res.j.best_score }, true);
      if (res.j.solved) {
        solved = true;
        resultEl.innerHTML = '<div class="puzzle-win">🎉 ' + gettext("¡Resuelto!") + " " + msg + "</div>";
        render();
      } else {
        resultEl.innerHTML = '<div class="puzzle-miss">' + msg + " — " +
          gettext("¡seguí buscando!") + "</div>";
      }
    });
  });
  document.getElementById("btn-reveal").addEventListener("click", function () {
    fetch(root.dataset.revealUrl).then(function (r) { return r.json(); }).then(function (j) {
      recall();
      solved = true;
      pending = j.best_move.map(function (p) {
        return { row: p.row, col: p.col, letter: p.letter, isBlank: p.is_blank, rackIdx: -1 };
      });
      render();
      resultEl.innerHTML = '<div class="puzzle-miss">' +
        interpolate(gettext("Solución: %(w)s (+%(s)s)"), { w: j.best_word, s: j.best_score }, true) +
        "</div>";
    });
  });

  render();
})();
