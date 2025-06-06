document.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("id_date");
  const periodInput = document.getElementById("id_period");
  const monthSelector = document.getElementById("period-selector");
  const prevBtn = document.getElementById("prev-month");
  const nextBtn = document.getElementById("next-month");

  if (dateInput && monthSelector && periodInput) {
    // Inicializar seletor com base na data
    const initialDate = new Date(dateInput.value || new Date());
    const initYear = initialDate.getFullYear();
    const initMonth = String(initialDate.getMonth() + 1).padStart(2, "0");
    monthSelector.value = `${initYear}-${initMonth}`;
    periodInput.value = `${initYear}-${initMonth}`;

    // Atualizar campo oculto "period"
    function updatePeriodField() {
      const [year, month] = monthSelector.value.split("-");
      periodInput.value = `${year}-${month}`;
    }

    // Quando a data muda → atualiza o período
    dateInput.addEventListener("change", () => {
      const d = new Date(dateInput.value);
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      monthSelector.value = `${y}-${m}`;
      updatePeriodField();
    });

    // Quando o período muda → ajusta a data se necessário
    monthSelector.addEventListener("change", () => {
      const [year, month] = monthSelector.value.split("-");
      updatePeriodField();

      const selectedMonth = parseInt(month);
      const selectedYear = parseInt(year);

      const currentDate = new Date(dateInput.value);
      if (
        currentDate.getFullYear() !== selectedYear ||
        currentDate.getMonth() + 1 !== selectedMonth
      ) {
        dateInput.value = `${year}-${month}-01`;
      }
    });

    // Botões de navegação
    function shiftMonth(delta) {
      let [year, month] = monthSelector.value.split("-").map(Number);
      month += delta;

      if (month > 12) {
        month = 1;
        year += 1;
      } else if (month < 1) {
        month = 12;
        year -= 1;
      }

      const newVal = `${year}-${String(month).padStart(2, "0")}`;
      monthSelector.value = newVal;
      monthSelector.dispatchEvent(new Event("change"));
    }

    prevBtn?.addEventListener("click", () => shiftMonth(-1));
    nextBtn?.addEventListener("click", () => shiftMonth(1));
  }

  // Tom Select para o campo de categoria (apenas uma)
  const categoryInput = document.getElementById("id_category");
  if (categoryInput) {
    const currentValue = categoryInput.value.trim();  // valor já existente no input (ex: "Groceries")

    const select = new TomSelect(categoryInput, {
      create: true,
      maxItems: 1,
      valueField: "name",
      labelField: "name",
      searchField: "name",
      preload: true,
      load: function (query, callback) {
        if (!query.length) return callback();
        fetch(`/categories/autocomplete/?q=${encodeURIComponent(query)}`)
          .then((res) => res.json())
          .then((data) => callback(data))
          .catch(() => callback());
      },
    });

    // Adiciona a opção inicial manualmente se for necessário
    if (currentValue && !select.options[currentValue]) {
      select.addOption({ name: currentValue });  // ⚠️ só funciona se o campo for do tipo "name"
      select.setValue(currentValue);
    }
  }


  // Tom Select para o campo de tags (múltiplas)
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
      load: function (query, callback) {
        if (!query.length) return callback();
        fetch(`/tags/autocomplete/?q=${encodeURIComponent(query)}`)
          .then((res) => res.json())
          .then((data) => callback(data))
          .catch(() => callback());
      },
    });
  }
});
