$(document).ready(function () {
  const table = $('#transaction-table').DataTable({
    serverSide: true,
    ajax: '/transactions/json/', // URL da tua view que retorna JSON
    pageLength: 10,
    order: [[1, 'desc']],
    columns: [
      { data: 'period' },
      { data: 'date' },
      { data: 'type' },
      {
        data: 'amount',
        render: function (data, type, row) {
          return data + (row.currency ? ' ' + row.currency : '');
        }
      },
      { data: 'category' },
      {
        data: 'tags',
        render: function (data) {
          if (!data || data.length === 0) return '–';
          return data.map(tag => `<span class="badge bg-secondary">${tag}</span>`).join(' ');
        }
      },
      { data: 'account' },
      {
        data: 'id',
        orderable: false,
        searchable: false,
        render: function (data, type, row) {
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
    ],
    // Opcional: traduzir ou customizar labels
    language: {
      search: "Search:",
      lengthMenu: "Show _MENU_ entries",
      info: "Showing _START_ to _END_ of _TOTAL_ transactions",
      paginate: {
        next: "Next",
        previous: "Previous"
      },
      zeroRecords: "No matching transactions found",
    }
  });

  // Confirmação antes de apagar (delegada para elementos dinâmicos)
  $(document).on('submit', 'form.delete-form', function (e) {
    const name = $(this).data('name') || 'this transaction';
    if (!confirm(`⚠ Confirm delete ${name}?`)) {
      e.preventDefault();
    }
  });
});
