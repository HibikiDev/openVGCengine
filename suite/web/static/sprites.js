




(async () => {
  const KEY = "vn-icons", MODES = ["only", "names", "off"], LABEL = { only: "icons only", names: "icons with names", off: "off" };
  let mode = "only";
  try { mode = MODES.includes(localStorage.getItem(KEY)) ? localStorage.getItem(KEY) : "only"; } catch (e) {   }
  let names;
  try {
    const r = await fetch("/sprites/index.json");
    if (!r.ok) return;
    names = await r.json();
  } catch (e) { return; }
  const list = Object.keys(names).sort((a, b) => b.length - a.length);
  if (!list.length) return;
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const re = new RegExp("(?<![A-Za-z0-9\\-])(" + list.map(esc).join("|") + ")(?![A-Za-z0-9]|-[A-Za-z])", "g");
  const SKIP = new Set(["SCRIPT", "STYLE", "PRE", "CODE", "TEXTAREA", "INPUT", "SELECT", "OPTION", "BUTTON", "svg", "TITLE"]);
  const root = document.documentElement;
  const apply = () => { root.dataset.icons = mode; };
  apply();

  const icon = name => {
    const w = document.createElement("span");
    w.className = "pkm"; w.title = name;
    const img = document.createElement("img");
    img.src = names[name]; img.alt = ""; img.loading = "lazy"; img.decoding = "async";
    const t = document.createElement("span");
    t.className = "pkm-n"; t.textContent = name;
    w.append(img, t);
    return w;
  };
  const visit = node => {
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
      acceptNode: t => {
        for (let e = t.parentElement; e; e = e.parentElement) {
          if (SKIP.has(e.tagName) || e.classList.contains("pkm") || e.hasAttribute("data-no-icons")) return NodeFilter.FILTER_REJECT;
        }
        re.lastIndex = 0;
        return re.test(t.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    const hits = [];
    while (walker.nextNode()) hits.push(walker.currentNode);
    for (const t of hits) {
      const frag = document.createDocumentFragment();
      let last = 0;
      re.lastIndex = 0;
      for (const m of t.data.matchAll(re)) {
        if (m.index > last) frag.append(t.data.slice(last, m.index));
        frag.append(icon(m[1]));
        last = m.index + m[1].length;
      }
      if (last < t.data.length) frag.append(t.data.slice(last));
      t.replaceWith(frag);
    }
  };
  const main = document.querySelector("main") || document.body;
  visit(main);

  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => {
    if (n.nodeType === 1 && !n.classList.contains("pkm")) visit(n);
    else if (n.nodeType === 3 && n.parentElement && !n.parentElement.closest(".pkm")) visit(n.parentElement);
  }))).observe(main, { childList: true, subtree: true });

  const foot = document.querySelector("footer");
  if (foot) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "icons-toggle";
    const label = () => { b.textContent = "Pokémon icons: " + LABEL[mode]; };
    label();
    b.addEventListener("click", () => {
      mode = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
      try { localStorage.setItem(KEY, mode); } catch (e) {   }
      apply(); label();
    });
    foot.append(" · ", b);
  }
})();
