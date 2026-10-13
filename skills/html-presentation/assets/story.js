(() => {
  "use strict";
  const chapters = [...document.querySelectorAll("[data-chapter]")];
  const header = document.querySelector(".story-header");
  const progress = document.querySelector(".scroll-progress");
  const navLinks = [...document.querySelectorAll("[data-chapter-link]")];
  const status = document.getElementById("status");
  const inspectors = new Map();
  function report(message) {
    if (status) status.textContent = message;
    console.error(message);
  }
  document.querySelectorAll("[data-inspector]").forEach(group => {
    const controls = [...group.querySelectorAll("[data-inspect]")];
    const panels = [...group.querySelectorAll("[data-inspection]")];
    if (!controls.length || controls.length !== panels.length ||
        new Set(controls.map(control => control.dataset.inspect)).size !== controls.length ||
        controls.some(control => !panels.some(panel => panel.id === control.dataset.inspect))) {
      report("This explorer could not initialize. All explanations remain visible.");
      return;
    }
    function select(id) {
      controls.forEach(control => control.setAttribute("aria-pressed", String(control.dataset.inspect === id)));
      panels.forEach(panel => { panel.hidden = panel.id !== id; });
      group.dataset.selection = id;
    }
    controls.forEach(control => {
      control.disabled = false;
      control.setAttribute("aria-controls", control.dataset.inspect);
      control.addEventListener("click", () => select(control.dataset.inspect));
    });
    group.dataset.enhanced = "";
    inspectors.set(group, select);
    select(controls[0].dataset.inspect);
  });
  function expose(target) {
    if (!target) return;
    let ancestor = target;
    while (ancestor) {
      if (ancestor.tagName === "DETAILS") ancestor.open = true;
      ancestor = ancestor.parentElement;
    }
    const panel = target.closest("[data-inspection]");
    if (panel) inspectors.get(panel.closest("[data-inspector]"))?.(panel.id);
  }
  function fragmentTarget() {
    try { return document.getElementById(decodeURIComponent(location.hash.slice(1))); }
    catch { return null; }
  }
  document.querySelectorAll("[data-source]").forEach(link => {
    link.addEventListener("click", () => expose(document.getElementById(link.dataset.source)));
  });
  window.addEventListener("hashchange", () => {
    const target = fragmentTarget();
    expose(target);
    target?.scrollIntoView();
  });
  const sources = document.getElementById("sources");
  if (sources?.tagName === "DETAILS") sources.open = false;
  expose(fragmentTarget());
  if (location.hash) requestAnimationFrame(() => fragmentTarget()?.scrollIntoView());

  let frame = 0;
  function updatePosition() {
    frame = 0;
    const point = (header?.getBoundingClientRect().bottom || 0) + 140;
    let current = chapters[0];
    chapters.forEach(chapter => {
      if (chapter.getBoundingClientRect().top <= point) current = chapter;
    });
    navLinks.forEach(link => {
      if (link.hash.slice(1) === current?.id) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
    const extent = document.documentElement.scrollHeight - window.innerHeight;
    if (progress) progress.style.transform = `scaleX(${extent > 0 ? Math.min(1, Math.max(0, window.scrollY / extent)) : 1})`;
  }
  function schedulePosition() {
    if (!frame) frame = requestAnimationFrame(updatePosition);
  }
  window.addEventListener("scroll", schedulePosition, { passive: true });
  window.addEventListener("resize", schedulePosition);
  document.addEventListener("toggle", schedulePosition, true);
  updatePosition();
  let printDetails = [];
  window.addEventListener("beforeprint", () => {
    printDetails = [...document.querySelectorAll("details")].map(detail => [detail, detail.open]);
    printDetails.forEach(([detail]) => { detail.open = true; });
  });
  window.addEventListener("afterprint", () => {
    printDetails.forEach(([detail, open]) => { detail.open = open; });
    printDetails = [];
  });
})();
