function initTransactionForm() {
  const dateInput = document.getElementById("id_date");
  const periodInput = document.getElementById("id_period");
  const monthSelector = document.getElementById("id_period");
  const prevBtn = document.getElementById("prev-month");
  const nextBtn = document.getElementById("next-month");

  if (!dateInput || !periodInput || !monthSelector) return;

  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];
  const isNewTransaction = window.location.pathname.endsWith("/transactions/new/");

  if (isNewTransaction && !dateInput.value) {
    dateInput.value = todayStr;
  }

  // Função para sincronizar período com base na data
  function syncPeriodFromDate() {
    if (!dateInput.value) return;

    let date;
    
    // Tentar diferentes formatos de data
    if (dateInput.value.includes('/')) {
      // Formato DD/MM/YYYY ou MM/DD/YYYY
      const parts = dateInput.value.split('/');
      if (parts.length === 3) {
        // Assumir DD/MM/YYYY (formato português)
        const day = parseInt(parts[0]);
        const month = parseInt(parts[1]);
        const year = parseInt(parts[2]);
        date = new Date(year, month - 1, day); // month é 0-indexed no JavaScript
      }
    } else {
      // Formato YYYY-MM-DD (ISO)
      date = new Date(dateInput.value);
    }

    if (!date || isNaN(date.getTime())) return;

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const periodValue = `${year}-${month}`;

    monthSelector.value = periodValue;
    periodInput.value = periodValue;

    console.log(`📅 Sincronização: Data ${dateInput.value} → Período ${periodValue} (${year}/${month})`);
  }

  // Flatpickr com sincronização corrigida
  if (dateInput._flatpickr) dateInput._flatpickr.destroy();
  
  // Converter valor inicial se necessário
  let initialDate = dateInput.value;
  if (initialDate && initialDate.includes('/')) {
    const parts = initialDate.split('/');
    if (parts.length === 3) {
      // Converter DD/MM/YYYY para YYYY-MM-DD
      initialDate = `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
      dateInput.value = initialDate; // Atualizar o input com formato correto
    }
  }
  
  // ✅ Guard against missing Flatpickr (e.g. offline or CDN failure)
  if (typeof flatpickr === "function") {
    flatpickr(dateInput, {
      dateFormat: "Y-m-d",
      defaultDate: initialDate,
      altInput: true,
      altFormat: "d/m/Y",
      allowInput: true,
      onChange: function (selectedDates) {
        if (selectedDates.length > 0) {
          syncPeriodFromDate();
        }
      },
      onReady: function () {
        // Sincronizar período ao carregar
        syncPeriodFromDate();
      }
    });
  } else {
    console.warn("⏭️ Flatpickr not loaded; skipping date picker init");
  }

  // Event listener para mudanças manuais na data
  dateInput.addEventListener('change', syncPeriodFromDate);
  dateInput.addEventListener('blur', syncPeriodFromDate);

  monthSelector.addEventListener("change", () => {
    const [year, month] = monthSelector.value.split("-");
    const newDate = `${year}-${month}-01`;
    dateInput.value = newDate;
    periodInput.value = `${year}-${month}`;
    if (dateInput._flatpickr) {
      dateInput._flatpickr.setDate(newDate, true);
    }

    console.log(`📅 Month selector change: Período ${monthSelector.value} → Data ${newDate}`);
  });

  // Sincronização inicial
  syncPeriodFromDate();

  prevBtn?.addEventListener("click", () => changeMonth(-1));
  nextBtn?.addEventListener("click", () => changeMonth(1));

  function changeMonth(delta) {
    const [year, month] = monthSelector.value.split("-").map(Number);
    const newDate = new Date(year, month - 1 + delta, 1);
    const newYear = newDate.getFullYear();
    const newMonth = String(newDate.getMonth() + 1).padStart(2, "0");
    const newMonthValue = `${newYear}-${newMonth}`;
    const newDateStr = `${newYear}-${newMonth}-01`;
    monthSelector.value = newMonthValue;
    periodInput.value = newMonthValue;
    dateInput.value = newDateStr;
    if (dateInput._flatpickr) {
      dateInput._flatpickr.setDate(newDateStr, true);
    }
  }

  const categoryInput = document.getElementById("id_category");
  if (categoryInput) {
    if (categoryInput.tomselect) categoryInput.tomselect.destroy();

    const rawList = categoryInput.dataset.categoryList || "";
    const options = rawList.split(",").map(name => ({ value: name.trim(), text: name.trim() }));

    if (typeof TomSelect === "function") {
      new TomSelect(categoryInput, {
        create: true,
        persist: false,
        maxItems: 1,
        options,
        items: categoryInput.value ? [categoryInput.value] : [],
        sortField: { field: "text", direction: "asc" },
      });
    } else {
      console.warn("⏭️ TomSelect not loaded; skipping category selector");
    }
  }

  const tagsInput = document.getElementById("id_tags_input");
  if (tagsInput) {
    if (tagsInput.tomselect) tagsInput.tomselect.destroy();

    const initialTags = tagsInput.value
      .split(",")
      .map(t => t.trim())
      .filter(t => t.length > 0);

    const allTags = initialTags.map(name => ({ name }));

    if (typeof TomSelect === "function") {
      fetch("/tags/autocomplete/?q=")
        .then(res => res.json())
        .then(data => {
          const tagOptions = [...new Set([...allTags, ...data])];

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
            options: tagOptions,
            items: initialTags,
          });
        });
    } else {
      console.warn("⏭️ TomSelect not loaded; skipping tags selector");
    }
  }

  const amountInput = document.getElementById("id_amount");
  if (amountInput) {
    const formatNumber = (value) => {
      if (!value) return "";
      const raw = value.trim().replace(/\s/g, "").replace("\u00A0", "");

      let numeric;
      if (raw.includes(",") && raw.includes(".")) {
        numeric = parseFloat(raw.replace(/\./g, "").replace(",", "."));
      } else if (raw.includes(",")) {
        numeric = parseFloat(raw.replace(",", "."));
      } else {
        numeric = parseFloat(raw);
      }

      if (isNaN(numeric)) return value;

      return numeric.toLocaleString("pt-PT", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    };

    amountInput.addEventListener("blur", () => {
      const raw = amountInput.value.trim().replace(/\s/g, "").replace("\u00A0", "");
      if (raw.startsWith("-")) return;  // ⛔ do not auto-format negative input
      const formatted = formatNumber(raw);
      if (formatted !== "") {
        amountInput.value = formatted;
      }
    });

    const form = document.getElementById("transaction-form");
    form?.addEventListener("submit", () => {
      const raw = amountInput.value.trim().replace(/\s/g, "").replace("\u00A0", "");
      let numeric;
      if (raw.includes(",") && raw.includes(".")) {
        numeric = raw.replace(/\./g, "").replace(",", ".");
      } else if (raw.includes(",")) {
        numeric = raw.replace(",", ".");
      } else {
        numeric = raw;
      }
      amountInput.value = numeric;
    });
  }

  const flowDiv = document.getElementById("investment-flow");
  const typeSelect = document.getElementById("id_type");
  const typeRadios = document.querySelectorAll('input[name="type"]');
  if (flowDiv) {
    const getTypeValue = () => {
      if (typeSelect) return typeSelect.value;
      const selected = document.querySelector('input[name="type"]:checked');
      return selected ? selected.value : null;
    };
    function toggleFlow() {
      flowDiv.classList.toggle("d-none", getTypeValue() !== "IV");
    }
    typeSelect?.addEventListener("change", toggleFlow);
    typeRadios.forEach(r => r.addEventListener("change", toggleFlow));
    toggleFlow();
  }
}

document.addEventListener("DOMContentLoaded", initTransactionForm);

document.body.addEventListener("htmx:afterSwap", function (event) {
  const targetId = event.detail?.target?.id;
  if (targetId === "transaction-form") {
    initTransactionForm();
    if (window.transactionTable) {
      window.transactionTable.ajax.reload(null, false);
    }
  }
});