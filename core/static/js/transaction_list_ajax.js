$(document).ready(function () {
  // 🛠️ 0. Preencher "end-date" com hoje se estiver vazio
  const endInput = document.getElementById("end-date");
  if (endInput && !endInput.value) {
    const today = new Date().toISOString().split("T")[0];
    endInput.value = today;
  }

  // 🗓️ 1. Inicializar flatpickr com formato DD/MM/YYYY e calendário em inglês
  flatpickr("#start-date", {
    altInput: true,         // mostra data formatada
    altFormat: "d/m/Y",     // o que o utilizador vê
    dateFormat: "Y-m-d",    // o que é enviado para o backend
    locale: "default"       // usa idioma do navegador (inglês se estiver en)
  });

  flatpickr("#end-date", {
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
      { data: 'period' },
      { data: 'date' },
      { data: 'type' },
      { data: 'amount' },
      { data: 'category', defaultContent: '–' },
      {
        data: 'tags',
        render: function (data, type, row, meta) {
          return data || '–';
        }
      },
      { data: 'account', defaultContent: '–' },
      { data: 'actions', orderable: false, defaultContent: '' }
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
        table.ajax.reload(null, false);  // 🔄 mantém página atual
      } else {
        alert('❌ Erro ao eliminar.');
      }
    })
    .catch(() => alert('❌ Erro ao contactar o servidor.'));
  });

  // Função para limpar os filtros
  $('#clear-filters').on('click', function() {
    // Limpar todos os filtros, exceto os de data (start-date e end-date)
    $('#filter-type').val('');
    $('#filter-account').val('');
    $('#filter-category').val('');
    $('#filter-period').val('');

    // Atualizar a tabela após limpar os filtros
    table.ajax.reload();
  });
});
