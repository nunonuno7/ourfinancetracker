// ✅ JavaScript completo para transaction_list.js

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

  // Inicializar DataTable
  const table = document.getElementById("transaction-table");
  if (table && typeof $ !== "undefined" && $.fn.dataTable) {
    $(table).DataTable({
      pageLength: 25,
      order: [[1, 'desc']], // ordenar por data desc
    });
  }

  // Botão para mostrar linha de nova transação
  const showBtn = document.getElementById("show-inline-form");
  const row = document.getElementById("new-transaction-row");
  const cancelBtn = document.getElementById("cancel-inline");

  if (showBtn && row) {
    showBtn.addEventListener("click", () => {
      row.classList.remove("d-none");
      showBtn.classList.add("d-none");

      const now = new Date();
      const yyyy = now.getFullYear();
      const mm = String(now.getMonth() + 1).padStart(2, "0");
      const dd = String(now.getDate()).padStart(2, "0");
      const today = `${yyyy}-${mm}-${dd}`;
      const period = `${yyyy}-${mm}`;

      const dateInput = document.querySelector("#inline-transaction-form input[name='date']");
      const periodInput = document.querySelector("#inline-transaction-form input[name='period']");
      const periodDisplay = document.querySelector("#inline-transaction-form input[name='period_display']");

      if (dateInput) dateInput.value = today;
      if (periodInput) periodInput.value = period;
      if (periodDisplay) periodDisplay.value = period;

      const catEl = document.getElementById("inline-category");
      if (catEl && !catEl.classList.contains("ts-wrapper")) {
        new TomSelect(catEl, {
          create: true,
          maxItems: 1,
          valueField: "name",
          labelField: "name",
          searchField: "name",
          load: function (query, callback) {
            if (!query.length) return callback();
            fetch(`/categories/autocomplete/?q=${encodeURIComponent(query)}`)
              .then(res => res.json())
              .then(data => callback(data))
              .catch(() => callback());
          }
        });
      }

      const tagsEl = document.getElementById("inline-tags");
      if (tagsEl && !tagsEl.classList.contains("ts-wrapper")) {
        new TomSelect(tagsEl, {
          plugins: ["remove_button"],
          delimiter: ",",
          persist: false,
          create: true,
          placeholder: "Add tags...",
          valueField: "name",
          labelField: "name",
          searchField: "name",
          load: function (query, callback) {
            if (!query.length) return callback();
            fetch(`/tags/autocomplete/?q=${encodeURIComponent(query)}`)
              .then(res => res.json())
              .then(data => callback(data))
              .catch(() => callback());
          }
        });
      }
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      row.classList.add("d-none");
      showBtn.classList.remove("d-none");
      document.getElementById("inline-transaction-form").reset();
    });
  }

  // Ativar/Desativar edição de todas as linhas
  const toggle = document.getElementById("toggle-edit-mode");
  const editActions = document.getElementById("edit-actions");

  if (toggle && editActions) {
    toggle.addEventListener("change", () => {
      const isEditing = toggle.checked;
      editActions.classList.toggle("d-none", !isEditing);

      const rows = document.querySelectorAll("#transaction-table tbody tr");

      if (isEditing) {
        rows.forEach(row => {
          row.querySelectorAll("[data-field]").forEach(cell => {
            const field = cell.dataset.field;
            const original = cell.textContent.trim();

            if (field === "type") {
              const select = document.createElement("select");
              ["IN", "EX", "IV"].forEach(v => {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = { IN: "Income", EX: "Expense", IV: "Investment" }[v];
                if (opt.textContent === original) opt.selected = true;
                select.appendChild(opt);
              });
              cell.innerHTML = "";
              cell.appendChild(select);
            } else if (field === "date") {
              const input = document.createElement("input");
              input.type = "date";
              input.value = original;
              input.className = "form-control";
              cell.innerHTML = "";
              cell.appendChild(input);
            } else {
              const input = document.createElement("input");
              input.type = "text";
              input.value = original;
              input.className = "form-control";
              cell.innerHTML = "";
              cell.appendChild(input);
            }
          });
        });
      } else {
        // Recarrega a página para limpar edição
        location.reload();
      }
    });
  }
});
