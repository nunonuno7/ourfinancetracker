$(document).ready(function () {
  console.log('JavaScript carregado e $(document).ready() executado');

  // Cache management - declare early to avoid initialization errors
  let currentDateRange = {
    start: null,
    end: null
  };

  // 🧠 Recuperar filtro guardado do período (se existir)
  const savedPeriod = sessionStorage.getItem("tx_filter_period");
  if (savedPeriod) {
    $('#filter-period').val(savedPeriod);
  } else {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const currentPeriod = `${yyyy}-${mm}`;
    const filter = document.getElementById("filter-period");
    const exists = Array.from(filter.options).some(opt => opt.value === currentPeriod);
    if (!exists) {
      const opt = new Option(currentPeriod, currentPeriod, true, true);
      filter.add(opt);
    } else {
      filter.value = currentPeriod;
    }
    sessionStorage.setItem("tx_filter_period", currentPeriod);
  }

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
      dataSrc: function(json) {
        // Update results count
        $('#results-count').text(`${json.recordsFiltered} transactions found`);
        return json.data;
      },
      data: function (d) {
        const clean = val => val?.replace('⭘', '').trim() || '';
        d.date_start = $('#start-date').val();
        d.date_end = $('#end-date').val();
        d.type = clean($('#filter-type').val());
        d.account = clean($('#filter-account').val());
        d.category = clean($('#filter-category').val());
        d.period = clean($('#filter-period').val());
        d.amount_min = $('#filter-amount-min').val();
        d.amount_max = $('#filter-amount-max').val();
        d.tags = $('#filter-tags').val();
      }
    },
    pageLength: 50,
    lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
    order: [[2, 'desc']], // Order by date column (index 2) in descending order
    responsive: true,
    columns: [
      { 
        data: 'id', 
        orderable: false,
        searchable: false,
        width: '40px',
        render: function(data) {
          return `<input type="checkbox" class="form-check-input row-select" value="${data}" style="display: none;">`;
        }
      },
      { data: 'period', orderable: true, className: 'd-none d-md-table-cell' },
      { 
        data: 'date', 
        type: 'date', 
        orderable: true,
        render: function(data, type, row) {
          if (type === 'display') {
            return `<span class="fw-bold">${data}</span>
                    <br><small class="text-muted d-md-none">${row.period}</small>`;
          }
          if (type === 'type' || type === 'sort') {
            // Convert DD/MM/YYYY to YYYY-MM-DD for proper sorting
            const parts = data.split('/');
            if (parts.length === 3) {
              return `${parts[2]}-${parts[1]}-${parts[0]}`;
            }
          }
          return data;
        }
      },
      { 
        data: 'type', 
        orderable: true,
        render: function(data, type, row) {
          const badges = {
            'Income': 'bg-success',
            'Expense': 'bg-danger', 
            'Investment': 'bg-primary',
            'Transfer': 'bg-warning text-dark'
          };

          // Use type_display for investments to show direction
          const displayText = row.type_display || data;
          const badgeClass = badges[data] || 'bg-secondary';

          return `<span class="badge ${badgeClass}">${displayText}</span>`;
        }
      },
      { 
        data: 'amount', 
        type: 'num', 
        orderable: true, 
        className: 'text-end fw-bold',
        render: function(data, type, row) {
          if (type === 'display') {
            return `${data}<br><small class="text-muted d-lg-none">${row.category}</small>`;
          }
          return data;
        }
      },
      { data: 'category', orderable: true, className: 'd-none d-lg-table-cell' },
      { data: 'account', orderable: true, className: 'd-none d-md-table-cell' },
      { 
        data: 'tags', 
        orderable: false, 
        className: 'd-none d-xl-table-cell',
        render: function(data) {
          if (!data) return '';
          return data.split(', ').map(tag => 
            `<span class="badge bg-light text-dark me-1">${tag}</span>`
          ).join('');
        }
      },
      { 
        data: 'actions', 
        orderable: false,
        render: function(data, type, row) {
          return `
            <div class="btn-group">
              <button class="btn btn-sm btn-outline-info view-details" data-id="${row.id}" data-bs-toggle="modal" data-bs-target="#transactionModal">
                <i class="fas fa-eye d-md-none"></i>
                <span class="d-none d-md-inline">👁️</span>
              </button>
              <a href="/transactions/${row.id}/edit/" class="btn btn-sm btn-outline-primary">
                <i class="fas fa-edit"></i>
              </a>
              <a href="/transactions/${row.id}/delete/" class="btn btn-sm btn-outline-danger">
                <i class="fas fa-trash"></i>
              </a>
            </div>
          `;
        }
      }
    ]
  });

  window.transactionTable = table;

  // Initialize date range tracking
  updateDateRange($('#start-date').val(), $('#end-date').val());

  // Periodic check for cache status (only when needed)
  function checkCacheStatus() {
    fetch('/transactions/cache-status/')
      .then(response => response.json())
      .then(data => {
        if (data.cache_cleared) {
          console.log('🔄 Cache was cleared by server - reloading table');
          table.ajax.reload();
        } else {
          console.debug('✅ Cache status OK - no reload needed');
        }
      })
      .catch(err => {
        console.debug('Cache status check failed (normal if no changes):', err);
      });
  }

  // Check cache status every 30 seconds (less frequent)
  setInterval(checkCacheStatus, 30000);

  // 🔄 Bulk selection functionality
  $('#bulk-select-mode').on('change', function() {
    const isChecked = $(this).is(':checked');
    $('.row-select, #select-all').toggle(isChecked);
    $('#bulk-actions').toggleClass('d-none', !isChecked);

    if (!isChecked) {
      $('.row-select, #select-all').prop('checked', false);
    }
  });

  // Select all functionality
  $('#select-all').on('change', function() {
    $('.row-select').prop('checked', $(this).is(':checked'));
  });

  // Individual row selection
  $(document).on('change', '.row-select', function() {
    const totalRows = $('.row-select').length;
    const checkedRows = $('.row-select:checked').length;
    $('#select-all').prop('checked', totalRows === checkedRows);
  });

  // Helper function to get selected transaction IDs
  function getSelectedTransactions() {
    return $('.row-select:checked').map(function() { return parseInt(this.value); }).get();
  }

  // Bulk mark cleared
  $('#bulk-mark-cleared').on('click', function() {
    const selected = getSelectedTransactions();
    if (selected.length === 0) {
      alert('Por favor seleciona transações primeiro');
      return;
    }

    if (confirm(`Marcar ${selected.length} transação(ões) como cleared?`)) {
      fetch('/transactions/bulk-update/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: JSON.stringify({
          action: 'mark_cleared',
          transaction_ids: selected
        })
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          alert(`✅ ${data.updated} transação(ões) marcadas como cleared!`);
          clearCacheAndReload(); // Limpar cache e recarregar
          $('#bulk-select-mode').prop('checked', false).trigger('change');
        } else {
          alert('❌ Erro: ' + (data.error || 'Operação falhou'));
        }
      })
      .catch(err => {
        console.error('Bulk update error:', err);
        alert('❌ Erro inesperado');
      });
    }
  });

  // Bulk duplicate
  $('#bulk-duplicate').on('click', function() {
    const selected = getSelectedTransactions();
    if (selected.length === 0) {
      alert('Por favor seleciona transações primeiro');
      return;
    }

    if (confirm(`Duplicar ${selected.length} transação(ões)?`)) {
      fetch('/transactions/bulk-duplicate/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: JSON.stringify({
          transaction_ids: selected
        })
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          alert(`✅ ${data.created} transação(ões) duplicadas!`);
          clearCacheAndReload(); // Limpar cache e recarregar
          $('#bulk-select-mode').prop('checked', false).trigger('change');
        } else {
          alert('❌ Erro: ' + (data.error || 'Operação falhou'));
        }
      })
      .catch(err => {
        console.error('Bulk duplicate error:', err);
        alert('❌ Erro inesperado');
      });
    }
  });

  // Bulk delete
  $('#bulk-delete').on('click', function() {
    const selected = getSelectedTransactions();
    if (selected.length === 0) {
      alert('Por favor seleciona transações primeiro');
      return;
    }

    if (confirm(`❌ ATENÇÃO: Eliminar ${selected.length} transação(ões)? Esta ação NÃO pode ser desfeita!`)) {
      fetch('/transactions/bulk-delete/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: JSON.stringify({
          transaction_ids: selected
        })
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          alert(`✅ ${data.deleted} transação(ões) eliminadas!`);
          clearCacheAndReload(); // Limpar cache e recarregar
          $('#bulk-select-mode').prop('checked', false).trigger('change');
        } else {
          alert('❌ Erro: ' + (data.error || 'Operação falhou'));
        }
      })
      .catch(err => {
        console.error('Bulk delete error:', err);
        alert('❌ Erro inesperado');
      });
    }
  });

  // View details modal
  $(document).on('click', '.view-details', function() {
    const transactionId = $(this).data('id');
    const rowData = table.row($(this).closest('tr')).data();

    const detailsHTML = `
        <div class="row">
          <div class="col-6"><strong>Date:</strong></div>
          <div class="col-6">${rowData.date}</div>
          <div class="col-6"><strong>Type:</strong></div>
          <div class="col-6">${rowData.type_display}</div>
          <div class="col-6"><strong>Amount:</strong></div>
          <div class="col-6">${rowData.amount}</div>
          <div class="col-6"><strong>Category:</strong></div>
          <div class="col-6">${rowData.category}</div>
          <div class="col-6"><strong>Account:</strong></div>
          <div class="col-6">${rowData.account}</div>
          <div class="col-6"><strong>Tags:</strong></div>
          <div class="col-6">${rowData.tags || 'None'}</div>
          <div class="col-6"><strong>Period:</strong></div>
          <div class="col-6">${rowData.period}</div>
        </div>
      `;

    $('#transaction-details').html(detailsHTML);
    $('#modal-edit-btn').attr('href', `/transactions/${transactionId}/edit/`);
  });

  // Advanced filters with debounce for better performance (no cache clear)
  let filterTimeout;
  $('#filter-amount-min, #filter-amount-max, #filter-tags').on('change input', function() {
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(() => {
      console.log('🔍 Advanced filter applied (no cache clear):', {
        amount_min: $('#filter-amount-min').val(),
        amount_max: $('#filter-amount-max').val(),
        tags: $('#filter-tags').val()
      });
      table.ajax.reload();
    }, 500); // 500ms debounce
  });

  // 🔄 Recarregar tabela ao mudar datas (com cache inteligente)
  startFlatpickr.config.onChange.push(() => {
    const newStart = $('#start-date').val();
    const newEnd = $('#end-date').val();
    
    if (shouldClearCache(newStart, newEnd)) {
      console.log('🔄 Date range changed significantly - clearing cache');
      clearCacheAndReload();
      updateDateRange(newStart, newEnd);
    } else {
      console.log('🔄 Date range within cache - reloading table only');
      table.ajax.reload();
      updateDateRange(newStart, newEnd);
    }
  });
  
  endFlatpickr.config.onChange.push(() => {
    const newStart = $('#start-date').val();
    const newEnd = $('#end-date').val();
    
    if (shouldClearCache(newStart, newEnd)) {
      console.log('🔄 Date range changed significantly - clearing cache');
      clearCacheAndReload();
      updateDateRange(newStart, newEnd);
    } else {
      console.log('🔄 Date range within cache - reloading table only');
      table.ajax.reload();
      updateDateRange(newStart, newEnd);
    }
  });

  // 🔁 Recarregar tabela ao mudar filtros (sem limpar cache)
  $('#filter-type, #filter-account, #filter-category, #filter-period').on('change', function () {
    if (this.id === 'filter-period') {
      sessionStorage.setItem("tx_filter_period", $(this).val());
    }
    console.log('🔄 Filter changed - reloading table without cache clear');
    table.ajax.reload();
  });

// 🧼 Clear Filters
$('#clear-filters').on('click', function () {
  // Clear dropdown filters
  $('#filter-type').val('');
  $('#filter-account').val('');
  $('#filter-category').val('');
  $('#filter-period').val('');

  // Clear input fields
  $('#filter-amount-min').val('');
  $('#filter-amount-max').val('');
  $('#filter-tags').val('');

  // Clear session storage
  sessionStorage.removeItem("tx_filter_period");

  // Reload table
  table.ajax.reload();
});

  // 📋 Show all entries
  $('#show-all-entries').on('click', function() {
    table.page.len(-1).draw();
    $(this).html('<i class="fas fa-check"></i> Showing All');
    setTimeout(() => {
      $(this).html('<i class="fas fa-list"></i> Show All Entries');
    }, 2000);
  });

  // 🧹 Função para limpar cache e recarregar automaticamente (só quando necessário)
  function clearCacheAndReload() {
    console.log('🔄 Limpando cache e recarregando lista...');

    fetch('/transactions/clear-cache/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        'Content-Type': 'application/json',
      },
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'ok') {
        // Force complete table reload without reset paging
        table.ajax.reload(null, false);
        console.log('✅ Cache limpo e tabela recarregada automaticamente');
      }
    })
    .catch(err => {
      console.error('Auto cache clear error:', err);
      // Fallback: just reload table without clearing cache
      table.ajax.reload(null, false);
    });
  }

  // 🧹 Botão manual para limpar cache
  $('#clear-cache-btn').on('click', function (e) {
    e.preventDefault();

    // Show loading state
    const btn = $(this);
    const originalText = btn.html();
    btn.html('🔄 Limpando...').prop('disabled', true);

    fetch('/transactions/clear-cache/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        'Content-Type': 'application/json',
      },
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'ok') {
          // Clear all filters and reload table
          $('#filter-type').val('');
          $('#filter-account').val('');
          $('#filter-category').val('');
          $('#filter-period').val('');
          sessionStorage.removeItem("tx_filter_period");

          // Force complete table reload
          table.ajax.reload(null, false);

          // Show success message
          alert('✅ Cache limpo com sucesso! Tabela recarregada.');
        } else {
          alert('❌ Erro ao limpar cache.');
        }
      })
      .catch(err => {
        console.error('Cache clear error:', err);
        alert('❌ Erro inesperado ao limpar cache.');
      })
      .finally(() => {
        // Restore button state
        btn.html(originalText).prop('disabled', false);
      });
  });

// 🔄 Atualizar filtros com valores recebidos do backend
table.on('xhr.dt', function (e, settings, json) {
  if (!json) return;

  const updateDropdown = (selector, values, current) => {
    const select = $(selector);
    const set = new Set((values || []).filter(v => v));  // ⬅️ remove valores vazios
    select.empty().append(`<option value="">All</option>`);
    set.forEach(v => {
      const selected = current === v ? ' selected' : '';
      select.append(`<option value="${v}"${selected}>${v}</option>`);
    });
  };

  updateDropdown('#filter-type', json.filters.types, $('#filter-type').val());
  updateDropdown('#filter-account', json.filters.accounts, $('#filter-account').val());
  updateDropdown('#filter-category', json.filters.categories, $('#filter-category').val());
  updateDropdown('#filter-period', json.filters.periods, $('#filter-period').val());
});

// 🗑️ Intercept delete form submissions to reload table
$(document).on('submit', 'form[action*="/delete/"]', function(e) {
  const form = this;
  const formData = new FormData(form);

  e.preventDefault();

  if (!confirm('Are you sure you want to delete this transaction?')) {
    return;
  }

  fetch(form.action, {
    method: 'POST',
    body: formData,
    headers: {
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
    }
  })
  .then(response => {
    if (response.ok) {
      // Clear cache and reload table
      clearCacheAndReload();
      alert('✅ Transaction deleted successfully!');
    } else {
      alert('❌ Error deleting transaction.');
    }
  })
  .catch(err => {
    console.error('Delete error:', err);
    alert('❌ Unexpected error occurred.');
  });
});

// 🔄 Auto-reload quando regressa de páginas de edição/criação/eliminação (só se transação foi alterada)
window.addEventListener('pageshow', function(event) {
  const referrer = document.referrer;
  const wasTransactionPage = referrer.includes('/delete/') || 
    referrer.includes('/edit/') || 
    referrer.includes('/new/');

  // Only clear cache if we actually modified transactions
  if (wasTransactionPage && window.transactionTable) {
    // Check if there's a flag indicating transaction was modified
    if (sessionStorage.getItem('transaction_modified') === 'true') {
      console.log('🔄 Transaction was modified - clearing cache');
      clearCacheAndReload();
      sessionStorage.removeItem('transaction_modified');
    } else {
      console.log('🔄 Returned from transaction page - reloading table only');
      window.transactionTable.ajax.reload();
    }
  }
});

// Cache management - only clear when necessary
function shouldClearCache(newStart, newEnd) {
  // Don't clear cache on first load
  if (!currentDateRange.start || !currentDateRange.end) {
    return false;
  }
  
  // Only clear if new range extends significantly beyond current cached range
  const startDiff = new Date(currentDateRange.start) - new Date(newStart);
  const endDiff = new Date(newEnd) - new Date(currentDateRange.end);
  
  // Clear cache only if extending more than 30 days in either direction
  const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
  
  if (startDiff > thirtyDaysMs || endDiff > thirtyDaysMs) {
    return true;
  }
  
  return false;
}

function updateDateRange(start, end) {
  currentDateRange.start = start;
  currentDateRange.end = end;
}

  // 💰 Cash auto-update toggle
  $('#cash-auto-update').on('change', function() {
    const enabled = $(this).is(':checked');

    fetch('/cash/toggle-auto-update/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: `enabled=${enabled}`
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        alert(`✅ ${data.message}`);
      } else {
        alert(`❌ Erro: ${data.error}`);
        // Revert checkbox state
        $(this).prop('checked', !enabled);
      }
    })
    .catch(err => {
      console.error('Cash toggle error:', err);
      alert('❌ Erro inesperado ao alterar configuração');
      $(this).prop('checked', !enabled);
      });
    });
});