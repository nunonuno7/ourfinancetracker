document.addEventListener("DOMContentLoaded", () => {
  // Confirmação antes de apagar
  document.querySelectorAll("form.delete-form").forEach(form => {
    form.addEventListener("submit", function (e) {
      const name = form.dataset.name || "this transaction";
      if (!confirm(`⚠ Confirm delete ${name}?`)) {
        e.preventDefault();
      }
    });
  });

  // Inicializar DataTable (se jQuery estiver disponível)
  const table = document.getElementById("transaction-table");
  if (table && typeof $ !== "undefined" && $.fn.dataTable) {
    $(table).DataTable({
      pageLength: 25,
      order: [[0, 'desc']], // ordenar por data desc
    });
  }
});
