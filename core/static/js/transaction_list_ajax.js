// 📁 static/js/transaction_list_ajax.js

$(document).ready(function () {
  console.log('JavaScript carregado e $(document).ready() executado');

  // 🧠 Recuperar filtro guardado do período (se existir)
  const savedPeriod = sessionStorage.getItem("tx_filter_period");
  if (savedPeriod) {
    $('#filter-period').val(savedPeriod);
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
        // ✅ Remove símbolo ⭘ dos filtros ativos
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
  })
  
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
      if (current && !set.has(current)) {
        select.append(`<option value="${current}" selected>${current} ⭘</option>`);
      }
      Array.from(set).sort().forEach(val => {
        const selected = (val === current) ? 'selected' : '';
        select.append(`<option value="${val}" ${selected}>${val}</option>`);
      });
    };

    updateDropdown('#filter-type', json.unique_types, $('#filter-type').val());
    updateDropdown('#filter-category', json.unique_categories, $('#filter-category').val());
    updateDropdown('#filter-account', json.unique_accounts, $('#filter-account').val());
    updateDropdown('#filter-period', json.available_periods, $('#filter-period').val());
  });

  // 🗑️ Confirmação ao apagar transações
  $(document).on('submit', 'form.delete-form', function (e) {
    e.preventDefault();
    const form = this;
    const name = $(form).data('name') || 'this transaction';
    if (!confirm(`⚠ Confirm delete ${name}?`)) return;

    fetch(form.action, {
      method: 'POST',
      headers: {
        'X-CSRFToken': window.CSRF_TOKEN,
        'X-Requested-With': 'XMLHttpRequest',
      }
    })
    .then(response => {
      if (response.ok) {
        table.ajax.reload(null, false);
      } else {
        alert('❌ Erro ao eliminar.');
      }
    })
    .catch(() => alert('❌ Erro ao contactar o servidor.'));
  });

  // ✨ Botão "Clear Filters"
  $('#clear-filters').on('click', function () {
    $('#filter-type').val('');
    $('#filter-account').val('');
    $('#filter-category').val('');
    $('#filter-period').val('');
    table.ajax.reload();
  });

  // 🔍 Debug ordenação
  table.off('order.dt').on('order.dt', function () {
    const order = table.order();
    if (order.length > 0) {
      console.log('Coluna ordenada:', order[0][0], 'Direção:', order[0][1]);
    }
  });

  // 🔄 Navegação entre meses
  $('#prev-month').on('click', function () {
    const currentDate = startFlatpickr.selectedDates[0];
    if (currentDate) {
      const prev = new Date(currentDate);
      prev.setMonth(prev.getMonth() - 1);
      startFlatpickr.setDate(prev);
      endFlatpickr.setDate(prev);
      table.ajax.reload();
    }
  });

  $('#next-month').on('click', function () {
    const currentDate = startFlatpickr.selectedDates[0];
    if (currentDate) {
      const next = new Date(currentDate);
      next.setMonth(next.getMonth() + 1);
      startFlatpickr.setDate(next);
      endFlatpickr.setDate(next);
      table.ajax.reload();
    }
  });

  // 🔄 Limpar cache e recarregar tabela com os filtros atuais
  $('#clear-cache-btn').on('click', function (e) {
    e.preventDefault();

    console.log("🧪 Clique detectado no botão #clear-cache-btn");

fetch("/transactions/clear-cache/", {
  method: "GET",
  credentials: "same-origin",
  headers: {
    "X-Requested-With": "XMLHttpRequest",
  },
})
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log("✅ Cache limpa com sucesso");
      setTimeout(() => {
        table.ajax.reload(null, false);
      }, 100);
    } else {
      alert("❌ Erro ao limpar cache.");
    }
  })
      .catch(error => {
        console.error("Erro ao contactar o servidor:", error);
        alert("❌ Erro ao contactar o servidor.");
      });
  });

});
