/* Tiny, dependency-free animated diagrams.
   Every <div class="viz" data-type="flow|tables|seq" data-spec="{json}"> becomes a
   step-by-step animation with Play / Step / Reset. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, html) => {
    const n = document.createElement(tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (html !== undefined) n.innerHTML = html;
    return n;
  };
  const sv = (tag, attrs = {}, text) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (text !== undefined) n.textContent = text;
    return n;
  };

  /* ---------- shared player: owns the buttons, caption and timer ---------- */
  function player(root, total, onStep, onReset, captions) {
    const bar = el("div", { class: "viz-bar" });
    const play = el("button", { class: "viz-btn primary" }, "▶ Play");
    const next = el("button", { class: "viz-btn" }, "Next step");
    const reset = el("button", { class: "viz-btn" }, "Reset");
    const count = el("span", { class: "viz-count" }, "");
    const cap = el("div", { class: "viz-cap" }, captions.intro || "Press Play, or click Next step.");
    bar.append(play, next, reset, count);
    root.append(bar, cap);
    let i = -1, timer = null;
    const stop = () => { clearInterval(timer); timer = null; play.textContent = "▶ Play"; };
    const go = () => {
      if (i + 1 >= total) { stop(); return false; }
      i++; onStep(i);
      cap.innerHTML = captions.steps[i] || "";
      count.textContent = (i + 1) + " / " + total;
      return true;
    };
    play.onclick = () => {
      if (timer) { stop(); return; }
      if (i + 1 >= total) { i = -1; onReset(); }
      play.textContent = "❚❚ Pause";
      go();
      timer = setInterval(() => { if (!go()) stop(); }, 2200);
    };
    next.onclick = () => { stop(); if (i + 1 >= total) { i = -1; onReset(); } go(); };
    reset.onclick = () => { stop(); i = -1; onReset(); cap.innerHTML = captions.intro || ""; count.textContent = ""; };
  }

  /* ---------- flow: boxes, arrows, little packets travelling along arrows ---------- */
  function flow(root, s) {
    const W = s.width || 720, H = s.height || 260;
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "viz-svg", role: "img" });
    const defs = sv("defs");
    const mk = sv("marker", { id: "ar" + Math.random().toString(36).slice(2, 7), markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: "auto" });
    mk.append(sv("path", { d: "M0,0 L8,4 L0,8 z", class: "viz-arrowhead" }));
    defs.append(mk); svg.append(defs);
    const N = {};
    (s.nodes || []).forEach(n => { N[n.id] = n; n.w = n.w || 130; n.h = n.h || 52; });
    const edgeEls = [];
    const pt = (n, tx, ty) => { // point on the node border towards (tx,ty)
      const cx = n.x + n.w / 2, cy = n.y + n.h / 2, dx = tx - cx, dy = ty - cy;
      const k = Math.min((n.w / 2) / Math.abs(dx || 1e-6), (n.h / 2) / Math.abs(dy || 1e-6));
      return [cx + dx * k, cy + dy * k];
    };
    (s.edges || []).forEach((e, idx) => {
      const a = N[e.from], b = N[e.to];
      const ac = [a.x + a.w / 2, a.y + a.h / 2], bc = [b.x + b.w / 2, b.y + b.h / 2];
      const p1 = pt(a, bc[0], bc[1]), p2 = pt(b, ac[0], ac[1]);
      const line = sv("line", { x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1], class: "viz-edge" + (e.dashed ? " dashed" : ""), "marker-end": `url(#${mk.id})` });
      svg.append(line);
      if (e.label) {
        const t = sv("text", { x: (p1[0] + p2[0]) / 2, y: (p1[1] + p2[1]) / 2 - 7, class: "viz-edge-label", "text-anchor": "middle" }, e.label);
        svg.append(t);
      }
      edgeEls.push({ line, p1, p2, e });
    });
    const nodeEls = {};
    (s.nodes || []).forEach(n => {
      const g = sv("g", { class: "viz-node " + (n.kind || "") });
      g.append(sv("rect", { x: n.x, y: n.y, width: n.w, height: n.h, rx: 10 }));
      const lines = String(n.label).split("\n");
      const y0 = n.y + n.h / 2 - (lines.length - 1) * 9 + (n.sub ? -6 : 5);
      lines.forEach((ln, i) => g.append(sv("text", { x: n.x + n.w / 2, y: y0 + i * 18, "text-anchor": "middle", class: "viz-node-t" }, ln)));
      if (n.sub) g.append(sv("text", { x: n.x + n.w / 2, y: n.y + n.h - 11, "text-anchor": "middle", class: "viz-node-s" }, n.sub));
      svg.append(g); nodeEls[n.id] = g;
    });
    root.append(svg);
    const packets = [];
    const clear = () => {
      packets.splice(0).forEach(p => p.remove());
      edgeEls.forEach(x => x.line.classList.remove("on"));
      Object.values(nodeEls).forEach(g => g.classList.remove("on"));
      (s.nodes || []).forEach(n => { if (n.badge) { const b = nodeEls[n.id].querySelector(".viz-badge"); if (b) b.remove(); } });
    };
    const send = (ei, label, delay) => {
      const x = edgeEls[ei]; if (!x) return;
      x.line.classList.add("on");
      const g = sv("g", { class: "viz-packet" });
      g.append(sv("circle", { r: 9 }));
      if (label) g.append(sv("text", { y: -14, "text-anchor": "middle" }, label));
      g.style.opacity = 0; svg.append(g); packets.push(g);
      const dur = 1300, t0 = performance.now() + (delay || 0);
      (function tick(now) {
        const u = Math.min(1, Math.max(0, (now - t0) / dur));
        const e = u < .5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
        g.setAttribute("transform", `translate(${x.p1[0] + (x.p2[0] - x.p1[0]) * e},${x.p1[1] + (x.p2[1] - x.p1[1]) * e})`);
        g.style.opacity = now < t0 ? 0 : 1;
        if (u < 1) requestAnimationFrame(tick);
      })(performance.now());
    };
    const steps = s.steps || [];
    player(root, steps.length, (i) => {
      clear();
      const st = steps[i];
      (st.edges || []).forEach((ei, k) => send(ei, (st.labels || [])[k], k * 250));
      (st.nodes || []).forEach(id => nodeEls[id] && nodeEls[id].classList.add("on"));
      (st.badges || []).forEach(b => {
        const n = N[b.node], g = nodeEls[b.node];
        const t = sv("text", { x: n.x + n.w / 2, y: n.y - 8, "text-anchor": "middle", class: "viz-badge" }, b.text);
        g.append(t);
      });
    }, clear, { intro: s.intro, steps: steps.map(x => x.text) });
  }

  /* ---------- tables: side-by-side tables, highlight / dim rows, draw join links ---------- */
  function tables(root, s) {
    const wrap = el("div", { class: "viz-tables" });
    const holders = [];
    s.tables.forEach(t => {
      const box = el("div", { class: "viz-tbl" });
      box.append(el("div", { class: "viz-tbl-name" }, t.name));
      const tb = el("table");
      tb.append(el("thead", {}, "<tr>" + t.columns.map(c => `<th>${c}</th>`).join("") + "</tr>"));
      const body = el("tbody");
      t.rows.forEach((r) => body.append(el("tr", {}, r.map(c => `<td>${c === null ? "<i>NULL</i>" : c}</td>`).join(""))));
      tb.append(body); box.append(tb); wrap.append(box); holders.push({ box, body });
    });
    const overlay = sv("svg", { class: "viz-links" });
    const stage = el("div", { class: "viz-stage" }); stage.append(wrap, overlay); root.append(stage);
    const reset = () => {
      holders.forEach(h => [...h.body.children].forEach(tr => tr.className = ""));
      overlay.innerHTML = "";
    };
    const draw = (links) => {
      overlay.innerHTML = "";
      const sr = stage.getBoundingClientRect();
      overlay.setAttribute("viewBox", `0 0 ${sr.width} ${sr.height}`);
      (links || []).forEach(([ta, ra, tb, rb]) => {
        const A = holders[ta].body.children[ra], B = holders[tb].body.children[rb];
        if (!A || !B) return;
        const a = A.getBoundingClientRect(), b = B.getBoundingClientRect();
        const left = a.left < b.left;
        const x1 = (left ? a.right : a.left) - sr.left, y1 = a.top + a.height / 2 - sr.top;
        const x2 = (left ? b.left : b.right) - sr.left, y2 = b.top + b.height / 2 - sr.top;
        const p = sv("path", { d: `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`, class: "viz-link" });
        overlay.append(p);
        const len = p.getTotalLength(); p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
        requestAnimationFrame(() => { p.style.transition = "stroke-dashoffset .9s ease"; p.style.strokeDashoffset = 0; });
      });
    };
    const steps = s.steps || [];
    player(root, steps.length, (i) => {
      reset();
      const st = steps[i];
      Object.entries(st.hl || {}).forEach(([t, rows]) => rows.forEach(r => holders[t].body.children[r] && holders[t].body.children[r].classList.add("hl")));
      Object.entries(st.dim || {}).forEach(([t, rows]) => rows.forEach(r => holders[t].body.children[r] && holders[t].body.children[r].classList.add("dim")));
      Object.entries(st.add || {}).forEach(([t, rows]) => rows.forEach(r => holders[t].body.children[r] && holders[t].body.children[r].classList.add("new")));
      if (st.links) setTimeout(() => draw(st.links), 60);
    }, reset, { intro: s.intro, steps: steps.map(x => x.text) });
    window.addEventListener("resize", () => reset());
  }

  /* ---------- seq: lifelines with messages that appear one by one ---------- */
  function seq(root, s) {
    const n = s.actors.length, W = s.width || 720, colW = W / n, rowH = 46;
    const H = 70 + s.messages.length * rowH;
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "viz-svg" });
    const defs = sv("defs"), id = "sq" + Math.random().toString(36).slice(2, 7);
    const mk = sv("marker", { id, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: "auto" });
    mk.append(sv("path", { d: "M0,0 L8,4 L0,8 z", class: "viz-arrowhead" })); defs.append(mk); svg.append(defs);
    const cx = (i) => colW * i + colW / 2;
    s.actors.forEach((a, i) => {
      svg.append(sv("line", { x1: cx(i), y1: 44, x2: cx(i), y2: H - 6, class: "viz-life" }));
      const g = sv("g", { class: "viz-node " + (a.kind || "") });
      g.append(sv("rect", { x: cx(i) - 62, y: 6, width: 124, height: 34, rx: 8 }));
      g.append(sv("text", { x: cx(i), y: 28, "text-anchor": "middle", class: "viz-node-t" }, a.name || a));
      svg.append(g);
    });
    const items = s.messages.map((m, k) => {
      const y = 70 + k * rowH, g = sv("g", { class: "viz-msg" });
      const x1 = cx(m.from), x2 = m.to === undefined || m.to === m.from ? x1 : cx(m.to);
      if (x1 === x2) {
        g.append(sv("rect", { x: x1 - 80, y: y - 14, width: 160, height: 26, rx: 6, class: "viz-note " + (m.kind || "") }));
        g.append(sv("text", { x: x1, y: y + 4, "text-anchor": "middle", class: "viz-note-t" }, m.text));
      } else {
        g.append(sv("line", { x1, y1: y, x2: x2 + (x2 > x1 ? -4 : 4), y2: y, class: "viz-edge on" + (m.dashed ? " dashed" : ""), "marker-end": `url(#${id})` }));
        g.append(sv("text", { x: (x1 + x2) / 2, y: y - 8, "text-anchor": "middle", class: "viz-edge-label" }, m.text));
      }
      g.style.opacity = 0; svg.append(g); return g;
    });
    root.append(svg);
    const reset = () => items.forEach(g => { g.style.opacity = 0; g.classList.remove("fresh"); });
    player(root, s.messages.length, (i) => {
      items.forEach((g, k) => g.classList.toggle("fresh", k === i));
      items[i].style.opacity = 1;
    }, reset, { intro: s.intro, steps: s.messages.map(m => m.caption || "") });
  }

  function boot() {
    document.querySelectorAll(".viz").forEach(r => {
      if (r.dataset.ready) return; r.dataset.ready = 1;
      let spec; try { spec = JSON.parse(r.dataset.spec); } catch (e) { r.textContent = "Diagram error: " + e.message; return; }
      const t = r.dataset.type; (t === "flow" ? flow : t === "tables" ? tables : seq)(r, spec);
    });
    // copy buttons on code blocks
    document.querySelectorAll("pre").forEach(p => {
      if (p.querySelector(".copy")) return;
      const b = el("button", { class: "copy" }, "Copy");
      b.onclick = () => { navigator.clipboard.writeText(p.innerText.replace(/Copy$/, "").trim()); b.textContent = "Copied"; setTimeout(() => b.textContent = "Copy", 1200); };
      p.append(b);
    });
  }
  window.bootCourseVisualizations = boot;
  document.addEventListener("DOMContentLoaded", boot);
})();
