document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form.delete-form").forEach(form => {
    form.addEventListener("submit", function (e) {
      const name = form.dataset.name || "this transaction";
      if (!confirm(`⚠ Confirm delete ${name}?`)) {
        e.preventDefault();
      }
    });
  });
});
