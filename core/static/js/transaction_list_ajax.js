$(document).ready(function () {
  console.log('JavaScript carregado e $(document).ready() executado');

  // 🛠️ 0. Preencher "end-date" com hoje se estiver vazio
  const endInput = document.getElementById("end-date");
  if (endInput && !endInput.value) {
    const today = new Date().toISOString().split("T")[0];
    endInput.value = today;
  }

  // 🗓️ 1. Inicializar flatpickr com formato DD/MM/YYYY e calendário em inglês
  const startFlatpickr = flatpickr("#start-date", {
    altInput: true,
    altFormat: "d/m/Y",
    dateFormat: "Y-m-d",
    locale: "default"
  });

  const endFlatpickr = flatpickr("#end-date", {
    altInput: true,
    altFormat: "d/m/Y",
    dateFormat: "Y-m-d",
    locale: "default"
  });

  // 🔄 2. Popular dropdown de categorias via AJAX
  $.ajax({
    url: '/categories/autocomplete/',
    success: function (data) {
      data.forEach(cat => {
        $('#filter-category').append(new Option(cat.name, cat.name));
      });
    }
  });

  // 🔄 3. Popular dropdown de períodos via AJAX
  $.ajax({
    url: '/periods/autocomplete/',
    success: function (data) {
      data.forEach(p => {
        $('#filter-period').append(new Option(p.display_name, p.value));
      });
    }
  });

  // 📊 4. Inicializar DataTable com AJAX + filtros
  const table = $('#transaction-table').DataTable({
    serverSide: true,
    processing: true,
    ajax: {
      url: '/transactions/json/',
      dataSrc: 'data',
      data: function (d) {
        d.date_start = $('#start-date').val();
        d.date_end = $('#end-date').val();
        d.type = $('#filter-type').val();
        d.account = $('#filter-account').val();
        d.category = $('#filter-category').val();
        d.period = $('#filter-period').val();
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

  // 🔁 5. Recarregar tabela quando filtros mudam
  $('#filter-type, #filter-account, #filter-category, #filter-period').on('change', function () {
    table.ajax.reload();
  });

  // 🗑️ 6. Confirmação ao apagar transação
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

  // ✨ 7. Limpar filtros (exceto datas)
  $('#clear-filters').on('click', function() {
    $('#filter-type').val('');
    $('#filter-account').val('');
    $('#filter-category').val('');
    $('#filter-period').val('');
    table.ajax.reload();
  });

  // 🔄 8. Botão Refresh: reaplica filtros e recarrega
  $('#refresh-table').on('click', function () {
    table.ajax.reload();
  });

  // 📦 9. Debug: regista ordenação (opcional)
  table.off('order.dt').on('order.dt', function() {
    const order = table.order();
    if (order.length > 0) {
      console.log('Coluna ordenada:', order[0][0], 'Direção:', order[0][1]);
    }
  });

  // ⬅️ 10. Mês anterior
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

  // ➡️ 11. Mês seguinte
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
