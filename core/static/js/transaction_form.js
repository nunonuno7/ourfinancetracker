// transaction_form.js (versão oficial completa)

document.addEventListener("DOMContentLoaded", initTransactionForm);
document.body.addEventListener("htmx:afterSwap", initTransactionForm);

function initTransactionForm() {
  const dateInput = document.getElementById("id_date");
  const periodInput = document.getElementById("id_period");
  const monthSelector = document.getElementById("period-selector");
  const prevBtn = document.getElementById("prev-month");
  const nextBtn = document.getElementById("next-month");

  if (!dateInput || !periodInput || !monthSelector) return;

  // 📅 Inicializar data com hoje se estiver vazia
  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];
  if (!dateInput.value) {
    dateInput.value = todayStr;
  }

  // 📅 Flatpickr + sincronização com período
  if (dateInput._flatpickr) dateInput._flatpickr.destroy();
  flatpickr(dateInput, {
    dateFormat: "Y-m-d",
    defaultDate: dateInput.value,
    altInput: true,
    altFormat: "d/m/Y",
    allowInput: true,
    onChange: function ([selected]) {
      if (!selected) return;
      const year = selected.getFullYear();
      const month = String(selected.getMonth() + 1).padStart(2, "0");
      const period = `${year}-${month}`;
      monthSelector.value = period;
      periodInput.value = period;
    },
  });

  // 📆 Alterar manualmente o período
  monthSelector.addEventListener("change", () => {
    const [year, month] = monthSelector.value.split("-");
    const newDate = `${year}-${month}-01`;
    dateInput.value = newDate;
    periodInput.value = `${year}-${month}`;
    if (dateInput._flatpickr) {
      dateInput._flatpickr.setDate(newDate, true);
    }
  });

  // ⬅➡ Botões anterior e seguinte
  prevBtn?.addEventListener("click", () => changeMonth(-1));
  nextBtn?.addEventListener("click", () => changeMonth(1));

  function changeMonth(delta) {
    const [year, month] = monthSelector.value.split("-").map(Number);
    const newDate = new Date(year, month - 1 + delta, 1);
    const newYear = newDate.getFullYear();
    const newMonth = String(newDate.getMonth() + 1).padStart(2, "0");
    const period = `${newYear}-${newMonth}`;
    const dateStr = `${period}-01`;

    monthSelector.value = period;
    periodInput.value = period;
    dateInput.value = dateStr;
    if (dateInput._flatpickr) {
      dateInput._flatpickr.setDate(dateStr, true);
    }
  }

  // 🏷️ Tom Select: Categoria
  const categoryInput = document.getElementById("id_category");
  if (categoryInput) {
    if (categoryInput.tomselect) {
      categoryInput.tomselect.destroy();
    }

    const rawList = categoryInput.dataset.categoryList || "";
    const options = rawList
      .split(",")
      .map(name => name.trim())
      .filter(name => name.length > 0)
      .map(name => ({ value: name, text: name }));

    new TomSelect(categoryInput, {
      create: true,
      persist: false,
      maxItems: 1,
      options,
      items: categoryInput.value ? [categoryInput.value] : [],
      sortField: { field: "text", direction: "asc" },
    });
  }

  // 🏷️ Tom Select: Tags
  const tagsInput = document.getElementById("id_tags_input");
  if (tagsInput) {
    if (tagsInput.tomselect) {
      tagsInput.tomselect.destroy();
    }

    const initialTags = tagsInput.value
      .split(",")
      .map(t => t.trim())
      .filter(t => t.length > 0);

    new TomSelect(tagsInput, {
      plugins: ["remove_button"],
      delimiter: ",",
      persist: false,
      create: true,
      placeholder: "Add tags...",
      valueField: "name",
      labelField: "name",
      searchField: "name",
      preload: true,
      options: initialTags.map(name => ({ name })),
      items: initialTags,
      load: (query, callback) => {
        if (!query.length) return callback();
        fetch(`/tags/autocomplete/?q=${encodeURIComponent(query)}`)
          .then(res => res.json())
          .then(data => callback(data))
          .catch(() => callback());
      },
    });
  }

  // 💰 Formatar campo amount
  const amountInput = document.getElementById("id_amount");
  if (amountInput) {
    const formatNumber = (value) => {
      if (value.endsWith(",") || value.endsWith(".")) return value;
      const clean = value.replace(/[^\d,.-]/g, "").replace(",", ".");
      const num = parseFloat(clean);
      if (isNaN(num)) return value;
      return num.toLocaleString("pt-PT", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    };

    amountInput.addEventListener("blur", () => {
      amountInput.value = formatNumber(amountInput.value);
    });

    const form = document.getElementById("transaction-form");
    form.addEventListener("submit", () => {
      amountInput.value = amountInput.value
        .replace(/\s/g, "")
        .replace(/\./g, "")
        .replace(",", ".");
    });
  }
}
