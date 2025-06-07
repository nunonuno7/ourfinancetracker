$(document).ready(function() {
  // Popular dropdown categoria via AJAX
  $.ajax({
    url: '/categories/autocomplete/',
    success: function(data) {
      data.forEach(cat => {
        $('#filter-category').append(new Option(cat.name, cat.id));
      });
    }
  });

  // Popular dropdown períodos via AJAX
  $.ajax({
    url: '/periods/autocomplete/',
    success: function(data) {
      data.forEach(p => {
        $('#filter-period').append(new Option(p.display_name, p.value));
      });
    }
  });

  // Inicializar DataTable
  const table = $('#transaction-table').DataTable({
    serverSide: true,
    ajax: {
      url: '/transactions/json/',
      data: function(d) {
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
      { data: 'amount', render: (data, type, row) => data + (row.currency ? ' ' + row.currency : '') },
      { data: 'category' },
      { 
        data: 'tags',
        render: function(data) {
          if (!data || data.length === 0) return '–';
          return data.map(t => `<span class="badge bg-secondary">${t}</span>`).join(' ');
        }
      },
      { data: 'account' },
      { 
        data: 'id',
        orderable: false,
        render: function(data, type, row) {
          return `
            <div class="d-flex gap-2 justify-content-center">
              <a href="/transactions/${data}/edit/" class="btn btn-sm btn-outline-primary" title="Edit">✏️</a>
              <form method="post" action="/transactions/${data}/delete/" class="delete-form d-inline" data-name="transaction on ${row.date}">
                <input type="hidden" name="csrfmiddlewaretoken" value="${window.CSRF_TOKEN}">
                <button type="submit" class="btn btn-sm btn-outline-danger" title="Delete">🗑</button>
              </form>
            </div>`;
        }
      }
    ]
  });

  // Atualizar tabela quando filtros mudam
  $('#filter-type, #filter-account, #filter-category, #filter-period').on('change', function() {
    table.ajax.reload();
  });

  // Confirmação antes de apagar
  $(document).on('submit', 'form.delete-form', function(e) {
    const name = $(this).data('name') || 'this transaction';
    if (!confirm(`⚠ Confirm delete ${name}?`)) {
      e.preventDefault();
    }
  });
});
