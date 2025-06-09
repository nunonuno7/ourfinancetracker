$(document).ready(function () {

  // 🧠 Recuperar filtro guardado do período (se existir)
  const savedPeriod = sessionStorage.getItem("tx_filter_period");
  if (savedPeriod) {
    $('#filter-period').val(savedPeriod);
  }

  // 💾 Guardar no sessionStorage quando o utilizador mudar o período
  $('#filter-period').on('change', function () {
    sessionStorage.setItem("tx_filter_period", this.value);
  });

  console.log('JavaScript carregado e $(document).ready() executado');

  // 🛠️ Preencher "end-date" com hoje se estiver vazio
  const endInput = document.getElementById("end-date");
  if (endInput && !endInput.value) {
    const today = new Date().toISOString().split("T")[0];
    endInput.value = today;
  }

// 🗓️ Inicializar flatpickr
const startFlatpickr = flatpickr("#start-date", {
  dateFormat: "Y-m-d",  // ✅ formato compatível com o input real
  locale: "default"
});

const endFlatpickr = flatpickr("#end-date", {
  dateFormat: "Y-m-d",  // ✅ mantém o formato simples e funcional
  locale: "default"
});

// 🔄 Recarregar tabela ao mudar datas
startFlatpickr.config.onChange.push(function () {
  table.ajax.reload();
});
endFlatpickr.config.onChange.push(function () {
  table.ajax.reload();
});




  // 📊 Inicializar DataTable
  const table = $('#transaction-table').DataTable({
    serverSide: true,
    processing: true,
    ajax: {
      url: '/transactions/json/',
      dataSrc: 'data',
      data: function (d) {
        // ✅ Remove o símbolo ⭘ dos valores selecionados
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

  // 🔁 Recarregar tabela quando filtros mudam
  $('#filter-type, #filter-account, #filter-category, #filter-period').on('change', function () {
    if (this.id === 'filter-period') {
      sessionStorage.setItem("tx_filter_period", $(this).val());
    }
    table.ajax.reload();
  });

  // 🧹 Atualizar filtros estilo Excel
  table.on('xhr.dt', function (e, settings, json) {
    if (!json) return;

    // 🔁 Categoria
    const catSelect = $('#filter-category');
    const currentCat = catSelect.val();
    const catSet = new Set(json.unique_categories || []);
    catSelect.empty().append(`<option value="">All Categories</option>`);
    if (currentCat && !catSet.has(currentCat)) {
      catSelect.append(`<option value="${currentCat}" selected>${currentCat} ⭘</option>`);
    }
    Array.from(catSet).sort().forEach(c => {
      const selected = (c === currentCat) ? 'selected' : '';
      catSelect.append(`<option value="${c}" ${selected}>${c}</option>`);
    });

    // 🔁 Período
    const perSelect = $('#filter-period');
    const currentPer = perSelect.val();
    const perSet = new Set(json.available_periods || []);
    perSelect.empty().append(`<option value="">All Periods</option>`);
    if (currentPer && !perSet.has(currentPer)) {
      perSelect.append(`<option value="${currentPer}" selected>${currentPer} ⭘</option>`);
    }
    Array.from(perSet).forEach(p => {
      const selected = (p === currentPer) ? 'selected' : '';
      perSelect.append(`<option value="${p}" ${selected}>${p}</option>`);
    });
  });

  // 🗑️ Confirmação ao apagar
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

  // ✨ Limpar filtros
  $('#clear-filters').on('click', function () {
    $('#filter-type').val('');
    $('#filter-account').val('');
    $('#filter-category').val('');
    $('#filter-period').val('');
    table.ajax.reload();
  });

  // Logs de ordenação
  table.off('order.dt').on('order.dt', function () {
    var order = table.order();
    if (order.length > 0) {
      console.log('Coluna ordenada:', order[0][0], 'Direção:', order[0][1]);
    }
  });

  // Navegação entre meses
  $('#prev-month').on('click', function () {
    const currentDate = startFlatpickr.selectedDates[0];
    if (currentDate) {
      const prevDate = new Date(currentDate);
      prevDate.setMonth(prevDate.getMonth() - 1);
      startFlatpickr.setDate(prevDate);
      endFlatpickr.setDate(prevDate);
      table.ajax.reload();
    }
  });

  $('#next-month').on('click', function () {
    const currentDate = startFlatpickr.selectedDates[0];
    if (currentDate) {
      const nextDate = new Date(currentDate);
      nextDate.setMonth(nextDate.getMonth() + 1);
      startFlatpickr.setDate(nextDate);
      endFlatpickr.setDate(nextDate);
      table.ajax.reload();
    }
  });

});
