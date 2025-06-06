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

      const dateInput = document.querySelector("#new-transaction-row input[name='date']");
      const periodInput = document.querySelector("#new-transaction-row input[name='period']");
      const periodDisplay = document.querySelector("#new-transaction-row input[name='period_display']");

      if (dateInput) dateInput.value = today;
      if (periodInput) periodInput.value = period;
      if (periodDisplay) {
        const monthName = now.toLocaleString("pt-PT", { month: "long" });
        periodDisplay.value = `${monthName.charAt(0).toUpperCase() + monthName.slice(1)} ${yyyy}`;
      }

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
              .then
          

              (res => res.json())
              .then(data => callback(data))
              .catch(() => callback());
          }
        });
      }
    });
  }

  // Botão "cancelar" oculta linha inline
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      row.classList.add("d-none");
      showBtn.classList.remove("d-none");

      // Limpa inputs
      document.querySelectorAll("#new-transaction-row input, #new-transaction-row select").forEach(el => {
        if (el.type === "text" || el.type === "date" || el.tagName === "SELECT") el.value = "";
      });

      // Limpa Tom Selects
      const catEl = document.getElementById("inline-category");
      const tagsEl = document.getElementById("inline-tags");
      if (catEl?.tomselect) catEl.tomselect.clear();
      if (tagsEl?.tomselect) tagsEl.tomselect.clear();
    });
  }

  // Sincronização entre data e período
  function setInitialPeriod() {
    const dateInput = document.querySelector("#new-transaction-row input[name='date']");
    const periodInput = document.querySelector("#new-transaction-row input[name='period']");
    const periodDisplay = document.querySelector("#new-transaction-row input[name='period_display']");

    if (!dateInput || !periodInput || !periodDisplay) return;

    const date = new Date(dateInput.value);
    if (isNaN(date)) return;

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const period = `${year}-${month}`;
    const monthName = date.toLocaleString("pt-PT", { month: "long" });

    periodInput.value = period;
    periodDisplay.value = `${monthName.charAt(0).toUpperCase() + monthName.slice(1)} ${year}`;
  }

  // Atualizar período quando a data muda
  document.querySelector("#new-transaction-row input[name='date']")
    ?.addEventListener("change", setInitialPeriod);

  // Atualizar data quando o período muda (inverso)
  document.querySelector("#new-transaction-row input[name='period_display']")
    ?.addEventListener("change", () => {
      const val = document.querySelector("#new-transaction-row input[name='period_display']").value;
      const match = val.match(/(\d{4})-(\d{2})/);
      if (match) {
        const newDate = `${match[1]}-${match[2]}-01`;
        const dateInput = document.querySelector("#new-transaction-row input[name='date']");
        if (dateInput) dateInput.value = newDate;
        setInitialPeriod();
      }
    });

  // Submeter a nova transação
  const submitBtn = document.getElementById("submit-inline");
  if (submitBtn) {
    submitBtn.addEventListener("click", () => {
      const row = document.getElementById("new-transaction-row");
      const data = new FormData();

      row.querySelectorAll("input, select").forEach(input => {
        if (input.name && input.value !== undefined) {
          data.append(input.name, input.value);
        }
      });

      fetch("/transactions/new/", {
        method: "POST",
        body: data,
        headers: {
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")?.value || "",
        },
      })
        .then(res => {
          if (!res.ok) throw new Error("Erro ao submeter.");
          return res.text(); // ou .json() se retornas isso
        })
        .then(() => location.reload())
        .catch(err => alert("❌ Erro ao submeter: " + err.message));
    });
  }
  // Edição em massa (toggle + guardar)
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

            let input;
            if (field === "type") {
              input = document.createElement("select");
              input.className = "form-control";
              ["IN", "EX", "IV"].forEach(v => {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = { IN: "Income", EX: "Expense", IV: "Investment" }[v];
                if (opt.textContent === original) opt.selected = true;
                input.appendChild(opt);
              });
            } else if (field === "date") {
              input = document.createElement("input");
              input.type = "date";
              input.className = "form-control";
              input.value = original;
            } else if (field === "period") {
              input = document.createElement("input");
              input.type = "month";
              input.className = "form-control";
              input.value = cell.dataset.raw || "";
            } else {
              input = document.createElement("input");
              input.type = "text";
              input.className = "form-control";
              input.value = original;
            }

            input.dataset.field = field;
            cell.innerHTML = "";
            cell.appendChild(input);
          });
        });
      } else {
        location.reload(); // limpar edição
      }
    });
  }

  // Guardar edições em massa
  const saveBtn = document.querySelector("#edit-actions button.btn-success");
  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      const payload = [];

      document.querySelectorAll("#transaction-table tbody tr").forEach(row => {
        const idMatch = row.querySelector("a[href*='/edit/']")
          ?.getAttribute("href")
          ?.match(/\/(\d+)\/edit\//);
        const id = idMatch?.[1];
        if (!id) return;

        const data = { id: parseInt(id) };

        row.querySelectorAll("[data-field]").forEach(cell => {
          const field = cell.dataset.field;
          const input = cell.querySelector("input, select");
          if (input) {
            data[field] = input.value;
          }
        });

        payload.push(data);
      });

      fetch("/transactions/bulk-update/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")?.value || "",
        },
        body: JSON.stringify({ updates: payload }),
      })
        .then(res => {
          if (!res.ok) throw new Error("Erro ao guardar.");
          return res.json();
        })
        .then(data => {
          if (data.success) {
            alert(`💾 ${data.updated} transação(ões) atualizadas`);
            location.reload();
          } else {
            alert("❌ Erro ao guardar alterações.");
          }
        })
        .catch(err => {
          console.error(err);
          alert("❌ Erro inesperado ao guardar.");
        });
    });
  }
});
