(function(){
  function clamp(x){ return Math.max(0, Math.min(100, Math.round(x))); }
  function parseNumberLike(text){
    return parseFloat((text||"").replace(/[^\d.,-]/g,"" ).replace(/\./g,"").replace(",","."))
           || parseFloat((text||"").replace(/[^\d.-]/g,"")) || 0;
  }
  function pctFor(actual, goal, mode){
    if (!goal || goal <= 0) return 0;
    if (mode === "higher") return clamp((actual/goal)*100);
    if (mode === "lower") return clamp(100 - Math.max(0, ((actual-goal)/goal)*100));
    return clamp((1 - Math.abs(actual-goal)/goal)*100);
  }
  function setWidthClass(el, pct){
    [...el.classList].forEach(c=>{ if (c.startsWith("w-")) el.classList.remove(c); });
    el.classList.add(`w-${pct}`);
    el.setAttribute("aria-valuenow", String(pct));
  }
  function formatFooter(actual, goal, mode, pct){
    const overPct = goal>0 ? clamp(Math.max(0, ((actual-goal)/goal)*100)) : 0;
    const remaining = Math.max(0, goal - actual);
    const fmt = new Intl.NumberFormat(undefined,{style:"currency",currency:"EUR"});
    const a = fmt.format(actual);
    const g = fmt.format(goal);
    if (mode === "lower" && actual > goal){
      return `${pct}% of goal — ${overPct}% over (spent ${a} / goal ${g})`;
    }
    if (mode === "higher" && actual < goal){
      const rem = fmt.format(remaining);
      return `${pct}% of goal — ${rem} to goal (${a} / ${g})`;
    }
    return `${pct}% of goal (${a} / ${g})`;
  }
  async function fetchGoals(){
    try{
      const r = await fetch("/kpi/goals/", {credentials:"same-origin"});
      if (!r.ok) return {};
      const j = await r.json();
      return j.kpi_goals || {};
    }catch{ return {}; }
  }
  function recomputeCard(card, goals){
    const btn = card.querySelector(".kpi-config-btn");
    const key = btn?.getAttribute("data-kpi-key");
    const modeAttr = btn?.getAttribute("data-kpi-mode") || "closest";
    if (!key) return;
    const cfg = goals[key] || {};
    const mode = cfg.mode || modeAttr || "closest";
    const goal = parseFloat(cfg.goal ?? 0);
    const actualEl = card.querySelector(".kpi-value");
    const progressEl = card.querySelector(".progress-bar");
    const footerEl = card.querySelector(".kpi-footer");
    if (!actualEl || !progressEl || !footerEl) return;
    const actual = parseNumberLike(actualEl.textContent);
    const pct = pctFor(actual, goal, mode);
    setWidthClass(progressEl, pct);
    footerEl.textContent = formatFooter(actual, goal, mode, pct);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    let goals = await fetchGoals();
    document.querySelectorAll(".kpi-card").forEach(card => recomputeCard(card, goals));

    const modalEl = document.getElementById("kpiGoalsModal");
    const form = document.getElementById("kpiGoalsForm");
    const keyInput = document.getElementById("kpiKeyInput");
    const goalInput = document.getElementById("kpiGoalInput");
    const modeSelect = document.getElementById("kpiModeSelect");
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    let currentCard = null;
    const modal = modalEl ? new bootstrap.Modal(modalEl) : null;

    document.querySelectorAll('.kpi-config-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.getAttribute('data-kpi-key');
        const modeAttr = btn.getAttribute('data-kpi-mode') || 'closest';
        const cfg = goals[key] || {};
        keyInput.value = key;
        goalInput.value = cfg.goal ?? '';
        modeSelect.value = cfg.mode || modeAttr;
        currentCard = btn.closest('.kpi-card');
        modal?.show();
      });
    });

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        kpi_key: keyInput.value,
        goal: parseFloat(goalInput.value),
        mode: modeSelect.value
      };
      try{
        const r = await fetch('/kpi/goals/update/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify(payload)
        });
        if (r.ok){
          goals[payload.kpi_key] = {goal: payload.goal, mode: payload.mode};
          if (currentCard) recomputeCard(currentCard, goals);
          modal?.hide();
        }
      }catch(err){ console.error(err); }
    });
  });
})();
