document.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("id_date");
  const periodInput = document.getElementById("id_period");
  const monthSelector = document.getElementById("period-selector");
  const prevBtn = document.getElementById("prev-month");
  const nextBtn = document.getElementById("next-month");

  let fp; // flatpickr instance

  // ─── Inicializa o flatpickr ───
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

  // ─── Quando muda o período, atualizar a data para dia 1 ───
  if (monthSelector && periodInput && fp) {
    monthSelector.addEventListener("change", () => {
      const [year, month] = monthSelector.value.split("-");
      const dateStr = `${year}-${month}-01`;
      fp.setDate(dateStr, true); // atualiza a data e o campo hidden
      periodInput.value = `${year}-${month}`;
    });
  }

  // ─── Botões ‹ e › para navegar mês ───
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

  prevBtn?.addEventListener("click", () => shiftMonth(-1));
  nextBtn?.addEventListener("click", () => shiftMonth(1));

  // ─── Tom Select para categoria ───
  const categoryInput = document.getElementById("id_category");
  if (categoryInput) {
    const currentValue = categoryInput.value.trim();
    const select = new TomSelect(categoryInput, {
      create: true,
      maxItems: 1,
      valueField: "name",
      labelField: "name",
      searchField: "name",
      preload: true,
      load: (query, callback) => {
        if (!query.length) return callback();
        fetch(`/categories/autocomplete/?q=${encodeURIComponent(query)}`)
          .then(res => res.json())
          .then(data => callback(data))
          .catch(() => callback());
      },
    });

    if (currentValue && !select.options[currentValue]) {
      select.addOption({ name: currentValue });
      select.setValue(currentValue);
    }
  }

  // ─── Tom Select para tags ───
  const tagsInput = document.getElementById("id_tags_input");
  if (tagsInput) {
    new TomSelect(tagsInput, {
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
      },
    });
  }

  // ─── Formatador para o campo "amount" ───
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
});
