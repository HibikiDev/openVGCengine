
(function () {

  var T = function (s) { return (window.T && window.T[s]) || s; };
  var w = document.querySelector("[data-job]");
  if (w) {
    var t0 = Date.now(), el = document.getElementById("elapsed");
    var tick = function () {
      if (el) el.textContent = (w.dataset.tSec || "{n}s").replace("{n}", Math.round((Date.now() - t0) / 1000));
      fetch("/api/job/" + w.dataset.job).then(function (r) { return r.json(); }).then(function (j) {
        if (j.status === "done" || j.status === "error" || j.status === "missing") location.reload(); else setTimeout(tick, 2000);
        var pg = document.getElementById("progress");
        if (pg && j.progress) pg.textContent = j.progress;

        var bar = document.getElementById("pbar"), eta = document.getElementById("eta");
        if (bar && j.bar) {
          bar.hidden = false;
          bar.classList.toggle("busy", !!j.bar.busy);
          bar.querySelector("i").style.width = j.bar.busy ? "" : (100 * j.bar.frac).toFixed(1) + "%";
          bar.querySelector("span").textContent = j.bar.busy ? "" : Math.round(100 * j.bar.frac) + "%";
          if (eta) eta.textContent = j.bar.busy ? "" : j.bar.left == null ? ""
            : (w.dataset.tLeft || "· about {time} left").replace("{time}", j.bar.left < 90 ? (w.dataset.tS || "{n} s").replace("{n}", j.bar.left)
                                                                     : (w.dataset.tMin || "{n} min").replace("{n}", Math.round(j.bar.left / 60)));
        } else if (bar) { bar.hidden = true; if (eta) eta.textContent = ""; }
      }).catch(function () { setTimeout(tick, 4000); });
    };
    setTimeout(tick, 1500);
  }



  var SHARED = {lab: {a: "a", mine: "a", team: "a", b: "b", theirs: "b"}, rep: {replay: "replay", paste_p1: "p1", paste_p2: "p2"}, team: {team: "team"}};
  var grp = document.querySelector(".subnav .subclear");
  if (grp) {
    var g = grp.dataset.clear, map = SHARED[g], form = document.querySelector("main form");
    var key = function (k) { return "suite:" + g + ":" + k; };
    var store = function (k, v) { try { if (v) localStorage.setItem(key(k), v); else localStorage.removeItem(key(k)); } catch (e) {} };
    if (form) Object.keys(map).forEach(function (name) {
      var el = form.querySelector('textarea[name="' + name + '"]');
      if (!el) return;
      var v = null;
      try { v = localStorage.getItem(key(map[name])); } catch (e) {}
      if (!el.value.trim() && v) { el.value = v; el.dispatchEvent(new Event("input", {bubbles: true})); }
      el.addEventListener("input", function () { store(map[name], el.value.trim() ? el.value : ""); });
    });
    grp.addEventListener("click", function () {
      Object.keys(map).forEach(function (name) {
        store(map[name], "");
        var el = form && form.querySelector('textarea[name="' + name + '"]');
        if (el) { el.value = ""; el.dispatchEvent(new Event("input", {bubbles: true})); }
      });
    });
  }


  document.querySelectorAll('input[type="number"]').forEach(function (el) {
    el.addEventListener("invalid", function () {
      var v = el.valueAsNumber, lo = el.min !== "" ? +el.min : null, hi = el.max !== "" ? +el.max : null;
      el.setCustomValidity(isNaN(v) ? "Enter a number." : lo !== null && v < lo ? "At least " + lo + "." : hi !== null && v > hi ? "At most " + hi + "."
                           : "Enter a whole number.");
    });
    el.addEventListener("input", function () { el.setCustomValidity(""); });
  });




  document.querySelectorAll("select.fmt-pick, select.sheets-pick").forEach(function (fp) {
    var key = fp.classList.contains("sheets-pick") ? "openvgc.sheets" : "openvgc.format";
    var remember = function () { try { localStorage.setItem(key, fp.value); } catch (e) {} };
    var saved = null;
    try { saved = localStorage.getItem(key); } catch (e) {}
    if (fp.hasAttribute("data-given")) remember();
    else if (saved && saved !== fp.value && Array.prototype.some.call(fp.options, function (o) { return o.value === saved; })) {
      fp.value = saved;
      fp.dispatchEvent(new Event("change"));
    }
    fp.addEventListener("change", remember);
  });


  document.querySelectorAll("select.fmt-pick").forEach(function (fp) {
    function apply() {
      var fs = fp.form && fp.form.querySelector("select[name=field]");
      if (!fs) return;
      var first = null;
      fs.querySelectorAll("option[data-format]").forEach(function (o) {
        var ok = o.dataset.format === fp.value;
        o.hidden = !ok; o.disabled = !ok;
        if (ok && !first) first = o;
      });
      if (fs.selectedOptions[0] && fs.selectedOptions[0].disabled && first) fs.value = first.value;
    }
    fp.addEventListener("change", apply);
    apply();
  });


  var boxes = document.querySelectorAll("textarea[data-team]");
  if (boxes.length) {
    fetch("/api/buckets").then(function (r) { return r.json(); }).then(function (bks) {
      if (!bks.length) return;
      boxes.forEach(function (ta) {
        var sel = document.createElement("select");
        sel.className = "bucket-pick";
        sel.style.cssText = "width:100%; max-width:100%; min-width:0; margin:0 0 6px; font-size:.85rem; text-overflow:ellipsis";


        var form = ta.form, fsel = form && (form.querySelector("select[name=format]") || form.querySelector("select[name=team_fmt]"));
        function build() {
          var fmt = fsel ? fsel.value : document.body.dataset.currentFormat;
          sel.textContent = "";
          var head = document.createElement("option");
          head.value = ""; head.textContent = T("fill from a bucket…");
          sel.appendChild(head);
          var n = 0;
          bks.forEach(function (b, i) {
            if ((b.format || document.body.dataset.currentFormat) !== fmt) return;
            n++;
            var g = document.createElement("optgroup");
            g.label = b.name;
            if (ta.dataset.team === "whole") {
              var w = document.createElement("option");
              w.value = "bucket:" + b.name; w.textContent = T("the whole bucket (a team drawn per game)");
              g.appendChild(w);
            }
            b.teams.forEach(function (t, j) {
              var o = document.createElement("option");
              o.value = i + ":" + j;
              o.textContent = t.label + " - " + t.species.join(" / ");
              g.appendChild(o);
            });
            sel.appendChild(g);
          });
          sel.hidden = !n;
        }
        build();
        if (fsel) fsel.addEventListener("change", build);
        sel.addEventListener("change", function () {
          var v = sel.value;
          if (!v) return;
          if (v.indexOf("bucket:") === 0) ta.value = v;
          else { var k = v.split(":"); ta.value = bks[+k[0]].teams[+k[1]].src; }
          ta.dispatchEvent(new Event("input", { bubbles: true }));
          sel.value = "";
        });
        ta.parentNode.insertBefore(sel, ta);
      });
    }).catch(function () {});
  }
  document.querySelectorAll(".filters button").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll(".filters button").forEach(function (x) { x.classList.toggle("on", x === b); });
      document.getElementById("turns").classList.toggle("hide-agree", b.dataset.f === "diff");
    });
  });
})();
