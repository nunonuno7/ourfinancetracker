$(document).ready(function () {
  console.log('JavaScript carregado e $(document).ready() executado');

  // 🧠 Recuperar filtro guardado do período (se existir)
  const savedPeriod = sessionStorage.getItem("tx_filter_period");
  if (savedPeriod) {
    $('#filter-period').val(savedPeriod);
  } else {
    // Se não há valor guardado, define o mês atual como default
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const currentPeriod = `${yyyy}-${mm}`;

    const filter = document.getElementById("filter-period");
    const exists = Array.from(filter.options).some(opt => opt.value === currentPeriod);
    if (!exists) {
      const opt = new Option(currentPeriod, currentPeriod, true, true); // selected
      filter.add(opt);
    } else {
      filter.value = currentPeriod;
    }

    sessionStorage.setItem("tx_filter_period", currentPeriod);
  }

  // 💾 Guardar no sessionStorage quando o utilizador mudar o período
  $('#filter-period').on('change', function () {
    sessionStorage.setItem("tx_filter_period", this.value);
  });

  // 🛠️ Preencher "end-date" com hoje se estiver vazio
  const endInput = document.getElementById("end-date");
  if (endInput && !endInput.value) {
    const today = new Date().toISOString().split("T")[0];
    endInput.value = today;
  }

  // 🗓️ Inicializar flatpickr
  const startFlatpickr = flatpickr("#start-date", {
    dateFormat: "Y-m-d",
    locale: "default"
  });
  const endFlatpickr = flatpickr("#end-date", {
    dateFormat: "Y-m-d",
    locale: "default"
  });

  // 📊 Inicializar DataTable
  const table = $('#transaction-table').DataTable({
    serverSide: true,
    processing: true,
    ajax: {
      url: '/transactions/json/',
      dataSrc: 'data',
      data: function (d) {
        const clean = val => val?.replace('⭘', '').trim() || '';
        d.date_start = $('#start-date').val();
        d.date_end = $('#end-date').val();
        d.type = clean($('#filter-type').val());
        d.account = clean($('#filter-account').val());
        d.category = clean($('#filter-category').val());
        d.period = clean($('#filter-period').val());
      }
    },
    pageLength: 10,
    order: [[1, 'desc']],
    columns: [
      { data: 'period', orderable: true },
      { data: 'date', type: 'date', orderable: true },
      { data: 'type', orderable: true },
      { data: 'amount', type: 'num', orderable: true },
      { data: 'category', orderable: true },
      { data: 'tags', orderable: false },
      { data: 'account', orderable: true },
      { data: 'actions', orderable: false }
    ]
  });

  window.transactionTable = table;

  // 🔄 Recarregar tabela ao mudar datas
  startFlatpickr.config.onChange.push(() => table.ajax.reload());
  endFlatpickr.config.onChange.push(() => table.ajax.reload());

  // 🔁 Recarregar tabela ao mudar filtros
  $('#filter-type, #filter-account, #filter-category, #filter-period').on('change', function () {
    if (this.id === 'filter-period') {
      sessionStorage.setItem("tx_filter_period", $(this).val());
    }
    table.ajax.reload();
  });

  // 🧹 Atualizar dropdowns com valores visíveis (estilo Excel)
  table.on('xhr.dt', function (e, settings, json) {
    if (!json) return;

    const updateDropdown = (selector, values, current) => {
      const select = $(selector);
      const set = new Set(values || []);
      select.empty().append(`<option value="">All</option>`);
      set.forEach(v => {
        const selected = current === v ? ' selected' : '';
        select.append(`<option value="${v}"${selected}>${v}</option>`);
      });
    };

    updateDropdown('#filter-type', json.available_types, $('#filter-type').val());
    updateDropdown('#filter-account', json.available_accounts, $('#filter-account').val());
    updateDropdown('#filter-category', json.available_categories, $('#filter-category').val());
    updateDropdown('#filter-period', json.available_periods, $('#filter-period').val());
  });
});