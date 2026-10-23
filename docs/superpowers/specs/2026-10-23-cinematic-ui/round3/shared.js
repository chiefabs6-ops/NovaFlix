// Scale the 1920x1080 stage to fit the window, so a preview can be resized.
(function () {
  var stage = document.getElementById('stage');
  function fit() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = 'translate(-50%,-50%) scale(' + s + ')';
  }
  window.addEventListener('resize', fit);
  fit();
  // Arrow keys move focus between focusable items, like a TV remote.
  document.addEventListener('keydown', function (e) {
    var keys = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1] };
    var d = keys[e.key];
    if (!d) return;
    var items = Array.prototype.slice.call(document.querySelectorAll('[tabindex]'));
    var cur = document.activeElement;
    if (items.indexOf(cur) < 0) { items[0] && items[0].focus(); return; }
    var a = cur.getBoundingClientRect(), best = null, bestScore = Infinity;
    items.forEach(function (el) {
      if (el === cur) return;
      var b = el.getBoundingClientRect();
      var dx = (b.left + b.width / 2) - (a.left + a.width / 2);
      var dy = (b.top + b.height / 2) - (a.top + a.height / 2);
      if (d[0] && Math.sign(dx) !== d[0]) return;
      if (d[1] && Math.sign(dy) !== d[1]) return;
      if (d[0] && Math.abs(dx) < 4) return;
      if (d[1] && Math.abs(dy) < 4) return;
      var score = d[0] ? Math.abs(dx) + Math.abs(dy) * 3 : Math.abs(dy) + Math.abs(dx) * 3;
      if (score < bestScore) { bestScore = score; best = el; }
    });
    if (best) { e.preventDefault(); best.focus(); }
  });
  var start = document.querySelector('[data-start]');
  if (start) start.focus();
})();
