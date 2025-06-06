// ✅ JavaScript v5 otimizado - transaction_list_optimized.js

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

  // Inicializar DataTable otimizado
  const table = document.getElementById("transaction-table");
  if (table && typeof $ !== "undefined" && $.fn.dataTable) {
    $(table).DataTable({
      pageLength: 10,
      order: [[1, 'desc']],
      deferRender: true,
      retrieve: true
    });
  }

  const toggle = document.getElementById("toggle-edit-mode");
  const editActions = document.getElementById("edit-actions");
  const addRowContainer = document.getElementById("add-row-container");
  const tableBody = document.querySelector("#transaction-table tbody");
  const rowTemplate = document.getElementById("inline-template");

  function syncPeriodFields(tr) {
    const dateInput = tr.querySelector("input[name='date']");
    const periodInput = tr.querySelector("input[name='period']");
    const periodDisplay = tr.querySelector("input[name='period_display']");

    if (!dateInput || !periodInput || !periodDisplay) return;

    const date = new Date(dateInput.value);
    if (isNaN(date)) return;

    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const monthName = date.toLocaleString("pt-PT", { month: "long" });

    periodInput.value = `${yyyy}-${mm}`;
    periodDisplay.value = `${monthName.charAt(0).toUpperCase() + monthName.slice(1)} ${yyyy}`;
  }

  function syncDateFromPeriod(tr) {
    const dateInput = tr.querySelector("input[name='date']");
    const periodInput = tr.querySelector("input[name='period']");

    const match = periodInput.value.match(/(\d{4})-(\d{2})/);
    if (match) {
      dateInput.value = `${match[1]}-${match[2]}-01`;
      syncPeriodFields(tr);
    }
  }

  function addInlineRow() {
    const clone = rowTemplate.content.firstElementChild.cloneNode(true);
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    const dd = String(now.getDate()).padStart(2, "0");

    clone.querySelector("input[name='date']").value = `${yyyy}-${mm}-${dd}`;
    syncPeriodFields(clone);

    // Não inicializar Tom Select aqui para evitar lentidão!

    clone.querySelector("input[name='date']")?.addEventListener("change", () => syncPeriodFields(clone));
    clone.querySelector("input[name='period_display']")?.addEventListener("change", () => syncDateFromPeriod(clone));
    clone.querySelector(".remove-inline-row")?.addEventListener("click", () => clone.remove());

    tableBody.appendChild(clone);
  }

  if (toggle && addRowContainer) {
    toggle.addEventListener("change", () => {
      const isEditing = toggle.checked;
      editActions.classList.toggle("d-none", !isEditing);
      addRowContainer.classList.toggle("d-none", !isEditing);

      if (isEditing) {
        document.querySelectorAll("#transaction-table tbody tr").forEach(row => {
          row.querySelectorAll("[data-field]").forEach(cell => {
            const field = cell.dataset.field;
            const value = cell.textContent.trim();
            let input;

            if (field === "type") {
              input = document.createElement("select");
              input.className = "form-control";
              ["IN", "EX", "IV"].forEach(v => {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = { IN: "Income", EX: "Expense", IV: "Investment" }[v];
                if (opt.textContent === value) opt.selected = true;
                input.appendChild(opt);
              });
            } else if (field === "date") {
              input = document.createElement("input");
              input.type = "date";
              input.className = "form-control";
              input.value = value;
            } else if (field === "period") {
              input = document.createElement("input");
              input.type = "month";
              input.className = "form-control";
              input.value = cell.dataset.raw || "";
            } else {
              input = document.createElement("input");
              input.type = "text";
              input.className = "form-control";
              input.value = value;
            }

            input.dataset.field = field;
            cell.innerHTML = "";
            cell.appendChild(input);

            // Inicializar Tom Select APENAS aqui para linhas existentes
            if (field === "category") {
              new TomSelect(input, {
                create: true,
                maxItems: 1,
                valueField: "name",
                labelField: "name",
                searchField: "name",
                load: (query, callback) => {
                  if (!query.length) return callback();
                  fetch(`/categories/autocomplete/?q=${encodeURIComponent(query)}`)
                    .then(res => res.json())
                    .then(data => callback(data))
                    .catch(() => callback());
                }
              });
            }
            if (field === "tags_input") {
              new TomSelect(input, {
                plugins: ["remove_button"],
                delimiter: ",",
                persist: false,
                create: true,
                placeholder: "Add tags...",
                valueField: "name",
                labelField: "name",
                searchField: "name",
                load: (query, callback) => {
                  if (!query.length) return callback();
                  fetch(`/tags/autocomplete/?q=${encodeURIComponent(query)}`)
                    .then(res => res.json())
                    .then(data => callback(data))
                    .catch(() => callback());
                }
              });
            }
          });
        });
      } else {
        location.reload();
      }
    });
  }

  document.getElementById("show-inline-form")?.addEventListener("click", addInlineRow);

  const saveBtn = document.querySelector("#edit-actions .btn-success");
  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      const payload = [];

      document.querySelectorAll("#transaction-table tbody tr").forEach(row => {
        const editLink = row.querySelector("a[href*='/edit/']");
        if (!editLink) return;

        const idMatch = editLink.getAttribute("href").match(/\/transactions\/(\d+)\/edit/);
        const id = idMatch?.[1];
        if (!id) return;

        const data = { id: parseInt(id) };
        row.querySelectorAll("[data-field]").forEach(cell => {
          const input = cell.querySelector("input, select");
          if (input) {
            data[input.dataset.field] = input.value;
          }
        });

        payload.push(data);
      });

      document.querySelectorAll("#transaction-table tbody tr").forEach(row => {
        if (row.querySelector("a[href*='/edit/']")) return;

        syncPeriodFields(row); // Corrigir antes de guardar

        const data = {};
        row.querySelectorAll("input, select").forEach(input => {
          if (input.name && input.value !== undefined) {
            data[input.name] = input.value;
          }
        });

        if (Object.keys(data).length > 2) {
          payload.push(data);
        }
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
          alert("❌ Erro inesperado: " + err.message);
        });
    });
  }
});
