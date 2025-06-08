function initTransactionForm() {
  const dateInput = document.getElementById("id_date");
  const periodInput = document.getElementById("id_period");
  const monthSelector = document.getElementById("period-selector");
  const prevBtn = document.getElementById("prev-month");
  const nextBtn = document.getElementById("next-month");

  // Destrói instância flatpickr anterior (se existir)
  if (dateInput && dateInput._flatpickr) {
    dateInput._flatpickr.destroy();
  }

  let fp;

  if (dateInput) {
    const defaultDate = dateInput.value || new Date().toISOString().split("T")[0];
    fp = flatpickr(dateInput, {
      altInput: true,
      altFormat: "d/m/Y",
      dateFormat: "Y-m-d",
      defaultDate,
      locale: "en",
      allowInput: true,
      onChange: ([selected]) => {
        if (selected) {
          const y = selected.getFullYear();
          const m = String(selected.getMonth() + 1).padStart(2, "0");
          const period = `${y}-${m}`;
          if (monthSelector) monthSelector.value = period;
          if (periodInput) periodInput.value = period;
        }
      }
    });
  }

  if (monthSelector && periodInput && fp) {
    // Remove handlers antigos substituindo elementos
    monthSelector.replaceWith(monthSelector.cloneNode(true));
    const newMonthSelector = document.getElementById("period-selector");
    newMonthSelector.addEventListener("change", () => {
      const [year, month] = newMonthSelector.value.split("-");
      const dateStr = `${year}-${month}-01`;
      fp.setDate(dateStr, true);
      periodInput.value = `${year}-${month}`;
    });

    prevBtn?.replaceWith(prevBtn.cloneNode(true));
    document.getElementById("prev-month").addEventListener("click", () => shiftMonth(-1));

    nextBtn?.replaceWith(nextBtn.cloneNode(true));
    document.getElementById("next-month").addEventListener("click", () => shiftMonth(1));
  }

  function shiftMonth(delta) {
    if (!monthSelector || !fp) return;
    let [year, month] = monthSelector.value.split("-").map(Number);
    month += delta;
    if (month > 12) { month = 1; year++; }
    if (month < 1) { month = 12; year--; }
    const newMonth = String(month).padStart(2, "0");
    const newPeriod = `${year}-${newMonth}`;
    monthSelector.value = newPeriod;
    const newDate = `${year}-${newMonth}-01`;
    fp.setDate(newDate, true);
    periodInput.value = newPeriod;
  }

  // Tom Select categoria
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

  // Tom Select tags
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

  // Formata o campo amount
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
      const formatted = formatNumber(amountInput.value);
      amountInput.value = formatted;
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

// Inicializa na primeira carga da página
document.addEventListener("DOMContentLoaded", initTransactionForm);

// Inicializa após cada swap do HTMX no formulário
document.body.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target.id === "transaction-form") {
    initTransactionForm();
  }
});
