$(document).ready(function () {
  // 1. Popular dropdown categoria via AJAX
  $.ajax({
    url: '/categories/autocomplete/',
    success: function (data) {
      data.forEach(cat => {
        $('#filter-category').append(new Option(cat.name, cat.name));
      });
    }
  });

  // 2. Popular dropdown períodos via AJAX
  $.ajax({
    url: '/periods/autocomplete/',
    success: function (data) {
      data.forEach(p => {
        $('#filter-period').append(new Option(p.display_name, p.value));
      });
    }
  });

  // 3. Inicializar DataTable com filtros enviados ao backend
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
      { data: 'period' },
      { data: 'date' },
      { data: 'type' },
      { data: 'amount' },
      { data: 'category', defaultContent: '–' },
      {
        data: 'tags',
        render: function (data, type, row) {
          return typeof data === 'string' ? data : '–';
        }
      },
      { data: 'account', defaultContent: '–' },
      { data: 'actions', orderable: false, defaultContent: '' }
    ]
  });

  // 4. Recarregar tabela quando filtros mudam
  $('#filter-type, #filter-account, #filter-category, #filter-period, #start-date, #end-date').on('change', function () {
    table.ajax.reload();
  });

  // 5. Substituir submit por fetch com confirmação e recarregamento automático
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
});
