document.addEventListener("DOMContentLoaded", () => {
  // ───── Auto-hide flash messages ─────
  const alerts = document.querySelectorAll(".alert-dismissible");
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.classList.remove("show");
      alert.classList.add("fade");
      setTimeout(() => alert.remove(), 500); // remove do DOM
    }, 4000);
  });

  // ───── Bootstrap tooltips ─────
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.forEach(el => {
    new bootstrap.Tooltip(el);
  });

  // ───── Bootstrap popovers (opcional) ─────
  const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  popoverTriggerList.forEach(el => {
    new bootstrap.Popover(el);
  });
});
