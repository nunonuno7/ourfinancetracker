function initTransactionForm() {
  const dateInput = document.getElementById("id_date");
  const periodInput = document.getElementById("id_period");
  const monthSelector = document.getElementById("period-selector");
  const prevBtn = document.getElementById("prev-month");
  const nextBtn = document.getElementById("next-month");

  if (!dateInput || !periodInput || !monthSelector) return;

  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];
  const isNewTransaction = window.location.pathname.endsWith("/transactions/new/");

  if (isNewTransaction && !dateInput.value) {
    dateInput.value = todayStr;
  }

  if (dateInput._flatpickr) dateInput._flatpickr.destroy();
  flatpickr(dateInput, {
    dateFormat: "Y-m-d",
    defaultDate: dateInput.value,
    altInput: true,
    altFormat: "d/m/Y",
    allowInput: true,
    onChange: function (selectedDates) {
      const selected = selectedDates[0];
      if (!selected) return;
      const year = selected.getFullYear();
      const month = String(selected.getMonth() + 1).padStart(2, "0");
      monthSelector.value = `${year}-${month}`;
      periodInput.value = `${year}-${month}`;
    },
  });

  monthSelector.addEventListener("change", () => {
    const [year, month] = monthSelector.value.split("-");
    const newDate = `${year}-${month}-01`;
    dateInput.value = newDate;
    periodInput.value = `${year}-${month}`;
    if (dateInput._flatpickr) {
      dateInput._flatpickr.setDate(newDate, true);
    }
  });

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

    new TomSelect(categoryInput, {
      create: true,
      persist: false,
      maxItems: 1,
      options,
      items: categoryInput.value ? [categoryInput.value] : [],
      sortField: { field: "text", direction: "asc" },
    });
  }

  const tagsInput = document.getElementById("id_tags_input");
  if (tagsInput) {
    if (tagsInput.tomselect) tagsInput.tomselect.destroy();

    const initialTags = tagsInput.value
      .split(",")
      .map(t => t.trim())
      .filter(t => t.length > 0);

    const allTags = initialTags.map(name => ({ name }));

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
  const typeRadios = document.querySelectorAll('input[name="type"]');
  if (flowDiv && typeRadios.length) {
    function toggleFlow() {
      const selected = document.querySelector('input[name="type"]:checked');
      flowDiv.style.display = (selected?.value === "IV") ? "" : "none";
    }
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
