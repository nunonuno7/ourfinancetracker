(function(){
  const modalEl = document.getElementById('kpiGoalsModal');
  if (!modalEl) return;

  function toWidthClass(pct){
    const p = Math.max(0, Math.min(100, Math.round(pct)));
    return `w-${p}`;
  }

  async function fetchGoals(){
    const r = await fetch('/kpi/goals/', { credentials: 'same-origin' });
    if (!r.ok) return {};
    const j = await r.json();
    return j.kpi_goals || {};
  }

  // Open modal with current values
  document.querySelectorAll('.kpi-config-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const key = btn.getAttribute('data-kpi-key');
      const goals = await fetchGoals();
      const cfg = goals[key] || {};
      document.getElementById('kpi_key').value = key;
      document.getElementById('kpi_goal').value = cfg.goal ?? '';
      document.getElementById('kpi_mode').value = cfg.mode ?? 'closest';
      const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
      bsModal.show();
    });
  });

  // Save form
  document.getElementById('kpi-goal-form').addEventListener('submit', async ev => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const r = await fetch('/kpi/goals/update/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: fd,
    });
    if (!r.ok) return; // TODO: handle errors
    const j = await r.json();

    document.querySelectorAll('.kpi-card').forEach(card => {
      const key = card.querySelector('.kpi-config-btn')?.getAttribute('data-kpi-key');
      if (!key) return;
      const cfg = j.kpi_goals[key];
      if (!cfg) return;
      const actualEl = card.querySelector('.h4');
      if (!actualEl) return;
      const actual = parseFloat((actualEl.textContent || '0').replace(/[^\d.,-]/g, '').replace(',', '.')) || 0;
      const goal = parseFloat(cfg.goal) || 0;
      const mode = cfg.mode || 'closest';

      function clamp(x){ return Math.max(0, Math.min(100, Math.round(x))); }
      let pct = 0;
      if (goal > 0){
        if (mode === 'higher'){
          pct = clamp((actual/goal)*100);
        } else if (mode === 'lower'){
          const over = Math.max(0, ((actual - goal)/goal)*100);
          pct = clamp(100 - over);
        } else {
          const diff = Math.abs(actual - goal)/goal;
          pct = clamp((1 - diff)*100);
        }
      }

      const bar = card.querySelector('.progress-bar');
      if (!bar) return;
      bar.classList.forEach(cls => { if (cls.startsWith('w-')) bar.classList.remove(cls); });
      bar.classList.add(toWidthClass(pct));
      bar.setAttribute('aria-valuenow', String(pct));
    });

    bootstrap.Modal.getInstance(modalEl)?.hide();
  });
})();
