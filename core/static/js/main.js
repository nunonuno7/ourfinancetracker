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

  // Debug navigation issues
  console.log('🔍 Main.js loaded, current path:', window.location.pathname);

  // Debug logout links
  document.addEventListener('DOMContentLoaded', function() {
    const logoutLinks = document.querySelectorAll('a[href*="logout"]');
    logoutLinks.forEach(link => {
      console.log('🔍 Found logout link with href:', link.href);
      link.addEventListener('click', function(e) {
        console.log('🔍 Logout link clicked, href:', this.href);
      });
    });
  });
});