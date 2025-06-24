// Transactions 2.0 JavaScript - Advanced functionality
class TransactionManager {
  constructor() {
    console.log('🚀 [TransactionManager] Inicializando Transaction Manager...');
    this.currentPage = 1;
    this.pageSize = 25;
    this.totalRecords = 0;
    this.filters = {};
    this.cache = new Map();
    this.selectedRows = new Set();
    this.bulkMode = false;
    this.maxPageSize = 1000; // Limite máximo de segurança

    console.log('⚙️ [TransactionManager] Configuração inicial:', {
      currentPage: this.currentPage,
      pageSize: this.pageSize,
      cacheSize: this.cache.size
    });

    this.init();
  }

  init() {
    console.log('🔧 [init] Iniciando inicialização completa...');

    this.initDatePickers();
    console.log('📅 [init] Date pickers inicializados');

    this.loadPageSizePreference();
    console.log('📄 [init] Page size carregado do storage');

    this.loadFiltersFromStorage();
    console.log('💾 [init] Filtros carregados do storage');

    this.bindEvents();
    console.log('🔗 [init] Event listeners conectados');

    this.loadTransactions();
    this.loadTotals();
    console.log('✅ [init] Inicialização completa finalizada');
  }

  loadPageSizePreference() {
    const savedPageSize = localStorage.getItem('transaction_page_size');
    if (savedPageSize) {
      $('#page-size-selector').val(savedPageSize);
      if (savedPageSize === 'all') {
        this.pageSize = this.maxPageSize;
      } else {
        this.pageSize = parseInt(savedPageSize);
      }
      console.log(`📄 [loadPageSizePreference] Page size restaurado: ${savedPageSize} (${this.pageSize})`);
    }
  }

  initDatePickers() {
    flatpickr("#date-start", {
      dateFormat: "Y-m-d",
      defaultDate: "2025-01-01",
      onChange: () => this.onFilterChange()
    });

    flatpickr("#date-end", {
      dateFormat: "Y-m-d", 
      defaultDate: new Date(),
      onChange: () => this.onFilterChange()
    });
  }

  bindEvents() {
    // Filter changes
    $('#filter-type, #filter-account, #filter-category, #filter-period').on('change', () => this.onFilterChange());
    $('#filter-amount-min, #filter-amount-max, #filter-tags').on('input', this.debounce(() => this.onFilterChange(), 500));
    $('#global-search').on('input', this.debounce(() => this.onFilterChange(), 300));

    // Page size selector
    $('#page-size-selector').on('change', (e) => this.changePageSize(e.target.value));

    // Buttons
    $('#apply-filters-btn').on('click', () => this.loadTransactions());
    $('#clear-filters-btn').on('click', () => this.clearFilters());
    $('#clear-cache-btn').on('click', () => this.clearCache());
    $('#export-btn').on('click', () => this.exportData());
    $('#import-btn').on('click', () => this.importData());

    // Bulk actions
    $('#bulk-mode-toggle').on('change', (e) => this.toggleBulkMode(e.target.checked));
    $('#select-all').on('change', (e) => this.selectAll(e.target.checked));
    $('#bulk-mark-cleared').on('click', () => this.bulkMarkCleared());
    $('#bulk-duplicate').on('click', () => this.bulkDuplicate());
    $('#bulk-delete').on('click', () => this.bulkDelete());

    // Row selection
    $(document).on('change', '.row-select', (e) => this.handleRowSelect(e));
    $(document).on('click', '.transaction-row', (e) => this.handleRowClick(e));
  }

  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  onFilterChange() {
    console.group('🔄 [onFilterChange] FILTROS ALTERADOS');
    console.log('Timestamp:', new Date().toISOString());
    this.currentPage = 1;

    const currentFilters = this.getFilters();
    console.log('🎯 FILTROS ATUAIS:');
    console.table(currentFilters);

    console.log('🔧 DOM ELEMENT VALUES:');
    console.table({
      dateStart: $('#date-start').val(),
      dateEnd: $('#date-end').val(),
      type: $('#filter-type').val(),
      account: $('#filter-account').val(),
      category: $('#filter-category').val(),
      period: $('#filter-period').val(),
      amountMin: $('#filter-amount-min').val(),
      amountMax: $('#filter-amount-max').val(),
      tags: $('#filter-tags').val(),
      search: $('#global-search').val()
    });

    // Show visual feedback that filters are being applied
    this.showFilterFeedback();

    this.saveFiltersToStorage();
    console.log('💾 Filtros guardados na sessão');

    // Excel-style: Invalidate cache when filters change
    console.log('🗑️ Limpando cache (estilo Excel) - cache size antes:', this.cache.size);
    this.cache.clear();
    console.log('🗑️ Cache size depois:', this.cache.size);

    console.log('🚀 Iniciando loadTransactions...');
    this.loadTransactions();

    console.log('💰 Iniciando loadTotals...');
    this.loadTotals();

    console.groupEnd();
  }

  showFilterFeedback() {
    // Add visual feedback to show filters are active (Excel-style)
    const activeFilters = Object.values(this.getFilters()).filter(val => val && val !== '').length - 2; // subtract page and page_size
    const indicator = $('#filter-indicator');

    if (activeFilters > 0) {
      if (indicator.length === 0) {
        $('#filters-row').prepend(`
          <div id="filter-indicator" class="col-12">
            <div class="alert alert-info alert-sm mb-2">
              <i class="fas fa-filter"></i> <span id="filter-count">${activeFilters}</span> filtro(s) ativo(s) - Apenas valores com transações são mostrados
            </div>
          </div>
        `);
      } else {
        $('#filter-count').text(activeFilters);
      }
    } else {
      indicator.remove();
    }
  }

  getFilters() {
    return {
      date_start: $('#date-start').val(),
      date_end: $('#date-end').val(),
      type: $('#filter-type').val(),
      account: $('#filter-account').val(),
      category: $('#filter-category').val(),
      period: $('#filter-period').val(),
      amount_min: $('#filter-amount-min').val(),
      amount_max: $('#filter-amount-max').val(),
      tags: $('#filter-tags').val(),
      search: $('#global-search').val(),
      page: this.currentPage,
      page_size: this.pageSize
    };
  }

  saveFiltersToStorage() {
    const filters = this.getFilters();
    sessionStorage.setItem('transaction_filters_v2', JSON.stringify(filters));
  }

  loadFiltersFromStorage() {
    const saved = sessionStorage.getItem('transaction_filters_v2');
    if (saved) {
      const filters = JSON.parse(saved);
      Object.keys(filters).forEach(key => {
        const element = $(`#${key.replace('_', '-')}`);
        if (element.length && filters[key]) {
          element.val(filters[key]);
        }
      });
    }
  }

  clearFilters() {
    $('#date-start').val('2025-01-01');
    $('#date-end').val(new Date().toISOString().split('T')[0]);
    $('#filter-type, #filter-account, #filter-category, #filter-period').val('');
    $('#filter-amount-min, #filter-amount-max, #filter-tags, #global-search').val('');

    sessionStorage.removeItem('transaction_filters_v2');
    this.currentPage = 1;
    this.loadTransactions();
    this.loadTotals();
  }

  generateCacheKey() {
    const filters = this.getFilters();
    const key = Object.keys(filters)
      .sort()
      .map(k => `${k}:${filters[k]}`)
      .join('|');
    const cacheKey = `tx_v2_${btoa(key)}`;
    console.log('🔑 [generateCacheKey] Cache key gerada:', {
      filters: filters,
      keyString: key,
      finalCacheKey: cacheKey
    });
    return cacheKey;
  }

  async loadTransactions() {
    console.group('🔄 [loadTransactions] INÍCIO DO CARREGAMENTO');
    console.log('Timestamp:', new Date().toISOString());

    const cacheKey = this.generateCacheKey();
    console.log('🗝️ Cache key gerada:', cacheKey);

    // Check cache first
    if (this.cache.has(cacheKey)) {
      console.log('✅ CACHE HIT - usando dados do cache');
      console.groupEnd();
      this.renderTransactions(this.cache.get(cacheKey));
      return;
    }

    console.log('🌐 CACHE MISS - fazendo pedido à API');
    this.showLoading(true);

    try {
      const filters = this.getFilters();
      console.table(filters);

      console.log('📤 Enviando request para /transactions/json-v2/');
      const response = await fetch('/transactions/json-v2/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
        },
        body: JSON.stringify(filters)
      });

      console.log('📡 Response status:', response.status, response.statusText);
      console.log('📡 Response headers:', Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const errorText = await response.text();
        console.error('🚨 HTTP Error Response:', errorText);
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('📊 RAW API RESPONSE:');
      console.log(JSON.stringify(data, null, 2));

      console.log('📊 SUMMARY:', {
        transactionCount: data.transactions?.length || 0,
        totalCount: data.total_count,
        currentPage: data.current_page,
        pageSize: data.page_size,
        hasFilters: !!data.filters,
        filtersCount: data.filters ? Object.keys(data.filters).length : 0
      });

      if (data.transactions && data.transactions.length > 0) {
        console.log('📝 PRIMEIRA TRANSAÇÃO:');
        console.table([data.transactions[0]]);
      } else {
        console.warn('⚠️ NENHUMA TRANSAÇÃO RETORNADA!');
      }

      // Cache the result
      this.cache.set(cacheKey, data);
      console.log('💾 Dados guardados no cache');

      // Update filter options
      this.updateFilterOptions(data.filters);

      this.renderTransactions(data);

    } catch (error) {
      console.group('❌ ERRO NO CARREGAMENTO');
      console.error('Error object:', error);
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
      console.groupEnd();
      this.showError('Failed to load transactions. Please try again.');
    } finally {
      this.showLoading(false);
      console.log('✅ PROCESSO FINALIZADO');
      console.groupEnd();
    }
  }

  async loadTotals() {
    console.log('💰 [loadTotals] Iniciando carregamento de totais...');
    try {
      const filters = this.getFilters();
      console.log('🔍 [loadTotals] Filtros para totais:', filters);

      const response = await fetch('/transactions/totals-v2/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
        },
        body: JSON.stringify(filters)
      });

      console.log('📡 [loadTotals] Resposta dos totais recebida, status:', response.status);

      if (!response.ok) throw new Error('Failed to load totals');

      const totals = await response.json();
      console.log('📊 [loadTotals] Totais recebidos:', totals);

      this.renderTotals(totals);
      console.log('✅ [loadTotals] Totais carregados e renderizados com sucesso');

    } catch (error) {
      console.error('❌ [loadTotals] Erro ao carregar totais:', error);
    }
  }

  renderTransactions(data) {
    console.group('🎨 [renderTransactions] RENDERIZAÇÃO INICIADA');
    console.log('Timestamp:', new Date().toISOString());

    console.log('📋 VALIDAÇÃO DOS DADOS:');
    console.table({
      hasData: !!data,
      hasTransactions: !!(data && data.transactions),
      transactionCount: data?.transactions?.length || 0,
      totalCount: data?.total_count || 0,
      currentPage: data?.current_page || 0,
      dataKeys: data ? Object.keys(data) : []
    });

    const tbody = $('#transactions-tbody');
    const currentRowCount = tbody.find('tr').length;
    console.log('🗂️ DOM - Linhas antes de limpar:', currentRowCount);
    console.log('🗂️ DOM - Element exists:', tbody.length > 0);

    tbody.empty();
    console.log('🧹 Tabela limpa');

    if (!data || !data.transactions || data.transactions.length === 0) {
      console.warn('⚠️ SEM TRANSAÇÕES - Exibindo mensagem vazia');
      const emptyMessage = `
        <tr>
          <td colspan="9" class="text-center py-4 text-muted">
            <i class="fas fa-inbox fa-2x mb-2"></i><br>
            No transactions found with current filters
          </td>
        </tr>
      `;
      tbody.append(emptyMessage);
      this.updatePagination(0, 0);
      $('#total-count').text('No transactions found');
      console.groupEnd();
      return;
    }

    console.log('✏️ CRIANDO', data.transactions.length, 'LINHAS DA TABELA');

    // Performance optimization for large datasets
    const batchSize = 50;
    const transactions = data.transactions;

    if (transactions.length > batchSize) {
      // Render in batches for better performance
      console.log(`📊 [renderTransactions] Renderização em lotes: ${transactions.length} transações, lotes de ${batchSize}`);

      let index = 0;
      const renderBatch = () => {
        const endIndex = Math.min(index + batchSize, transactions.length);
        const batch = transactions.slice(index, endIndex);

        batch.forEach((tx, batchIndex) => {
          try {
            const row = this.createTransactionRow(tx, index + batchIndex);
            tbody.append(row);
          } catch (error) {
            console.error(`❌ Erro ao criar linha ${index + batchIndex + 1}:`, error);
          }
        });

        index = endIndex;

        if (index < transactions.length) {
          // Continue rendering next batch
          setTimeout(renderBatch, 10);
        } else {
          // Finished rendering all transactions
          this.finishRendering(data);
        }
      };

      renderBatch();
    } else {
      // Render all at once for smaller datasets
      transactions.forEach((tx, index) => {
        if (index < 3) { // Only log first 3 for brevity
          console.log(`📝 Transação ${index + 1}:`, tx);
        }
        try {
          const row = this.createTransactionRow(tx, index);
          tbody.append(row);
          if (index < 3) {
            console.log(`✅ Linha ${index + 1} adicionada com sucesso`);
          }
        } catch (error) {
          console.error(`❌ Erro ao criar linha ${index + 1}:`, error);
        }
      });

      this.finishRendering(data);
    }
  }

  finishRendering(data) {
    const finalRowCount = $('#transactions-tbody tr').length;
    console.log('📊 DOM - Linhas finais:', finalRowCount);

    this.totalRecords = data.total_count;
    this.updatePagination(data.total_count, data.current_page);

    const showingAll = this.pageSize >= data.total_count;
    const countMessage = showingAll 
      ? `All ${data.total_count} transactions shown`
      : `${data.total_count} transactions found (showing ${data.transactions.length} on this page)`;

    $('#total-count').text(countMessage);
    console.log('📊 Count message set:', countMessage);
    console.log('✅ RENDERIZAÇÃO CONCLUÍDA');
    console.groupEnd();
  }

  createTransactionRow(tx, index) {
    const amountClass = tx.amount >= 0 ? 'amount-positive' : 'amount-negative';
    const typeIcon = this.getTypeIcon(tx.type);

    return `
      <tr class="transaction-row" data-id="${tx.id}">
        <td>
          ${this.bulkMode ? 
            `<input type="checkbox" class="form-check-input row-select" value="${tx.id}">` : 
            index + 1 + (this.currentPage - 1) * this.pageSize
          }
        </td>
        <td>
          <span class="fw-bold">${tx.date}</span>
        </td>
        <td class="d-none d-md-table-cell">
          <span class="badge bg-secondary">${tx.period}</span>
        </td>
        <td>
          <span class="badge ${this.getTypeBadgeClass(tx.type)}">
            ${typeIcon} ${tx.type}
          </span>
        </td>
        <td>
          <span class="transaction-amount ${amountClass}">
            ${tx.amount_formatted}
          </span>
        </td>
        <td class="d-none d-lg-table-cell">
          <span class="badge bg-light text-dark">${tx.category || 'Uncategorized'}</span>
        </td>
        <td class="d-none d-xl-table-cell">
          ${tx.tags ? tx.tags.split(',').map(tag => 
            `<span class="badge bg-info me-1">${tag.trim()}</span>`
          ).join('') : ''}
        </td>
        <td class="d-none d-md-table-cell">
          <span class="text-muted">${tx.account || 'No account'}</span>
        </td>
        <td>
          <div class="btn-group btn-group-sm">
            <a href="/transactions/${tx.id}/edit/" class="btn btn-outline-primary btn-sm">
              <i class="fas fa-edit"></i>
            </a>
            <button class="btn btn-outline-danger btn-sm" onclick="deleteTransaction(${tx.id})">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }

  getTypeIcon(type) {
    const icons = {
      'Expense': '💸',
      'Income': '💰',
      'Investment': '📈',
      'Transfer': '🔁'
    };
    return icons[type] || '📄';
  }

  getTypeBadgeClass(type) {
    const classes = {
      'Expense': 'bg-danger',
      'Income': 'bg-success',
      'Investment': 'bg-info', 
      'Transfer': 'bg-warning text-dark'
    };
    return classes[type] || 'bg-secondary';
  }

  renderTotals(totals) {
    console.log('💰 [renderTotals] Renderizando totais:', totals);

    const income = this.formatCurrency(totals.income || 0);
    const expenses = this.formatCurrency(totals.expenses || 0);
    const investments = this.formatCurrency(totals.investments || 0);
    const balance = this.formatCurrency(totals.balance || 0);

    console.log('💰 [renderTotals] Valores formatados:', {
      income, expenses, investments, balance
    });

    $('#total-income').text(income);
    $('#total-expenses').text(expenses);
    $('#total-investments').text(investments);
    $('#total-balance').text(balance);

    console.log('✅ [renderTotals] Totais atualizados na interface');
  }

  formatCurrency(amount) {
    return new Intl.NumberFormat('pt-PT', {
      style: 'currency',
      currency: 'EUR'
    }).format(amount);
  }

  updateFilterOptions(filters) {
    console.log('🔧 [updateFilterOptions] Atualizando opções dos filtros (estilo Excel)');
    if (!filters) {
      console.warn('⚠️ [updateFilterOptions] Nenhum dado de filtros recebido');
      return;
    }

    console.log('📝 [updateFilterOptions] Filtros disponíveis (apenas com transações):', {
      categories: filters.categories?.length || 0,
      accounts: filters.accounts?.length || 0,
      periods: filters.periods?.length || 0
    });

    console.log('📋 [updateFilterOptions] Detalhes dos filtros:', {
      categoriesList: filters.categories || [],
      accountsList: filters.accounts || [],
      periodsList: filters.periods || []
    });

    // Update filter options while preserving current selections
    this.updateSelectOptions('#filter-category', filters.categories || [], 'category');
    this.updateSelectOptions('#filter-account', filters.accounts || [], 'account');
    this.updateSelectOptions('#filter-period', filters.periods || [], 'period');

    console.log('✅ [updateFilterOptions] Opções de filtros atualizadas (estilo Excel)');
  }

  updateSelectOptions(selector, options, filterType) {
    const select = $(selector);
    const currentValue = select.val();

    console.log(`🔧 [updateSelectOptions] Atualizando ${filterType} - valor atual: '${currentValue}', opções disponíveis:`, options);

    // Clear and rebuild options
    select.empty();
    select.append(`<option value="">All ${filterType ? filterType.charAt(0).toUpperCase() + filterType.slice(1) + 's' : 'Options'}</option>`);

    // Add available options (Excel-style - only those with data in current filter context)
    options.forEach(option => {
      const selected = option === currentValue ? ' selected' : '';
      select.append(`<option value="${option}"${selected}>${option}</option>`);
    });

    // Excel behavior: Keep current selection if it exists in filtered data
    // Only clear if the current value is not in the available options
    if (currentValue && !options.includes(currentValue)) {
      select.val('');
      console.log(`🔄 [updateSelectOptions] Filtro ${filterType} resetado - valor '${currentValue}' não existe nos dados filtrados (estilo Excel)`);

      // Trigger change event to update other filters
      setTimeout(() => {
        console.log(`🔄 [updateSelectOptions] Triggering change event for ${filterType} reset`);
        select.trigger('change');
      }, 100);
    } else if (currentValue && options.includes(currentValue)) {
      console.log(`✅ [updateSelectOptions] Filtro ${filterType} mantido - valor '${currentValue}' existe nos dados filtrados`);
    }

    console.log(`📋 [updateSelectOptions] ${filterType}: ${options.length} opções disponíveis (estilo Excel)`);
  }

  changePageSize(newSize) {
    console.log(`📄 [changePageSize] Alterando page size para: ${newSize}`);

    if (newSize === 'all') {
      // Para "all", usar um número muito alto mas limitado por segurança
      this.pageSize = Math.min(this.totalRecords || this.maxPageSize, this.maxPageSize);
      console.log(`📄 [changePageSize] Page size "all" definido como: ${this.pageSize}`);
    } else {
      this.pageSize = parseInt(newSize);
      console.log(`📄 [changePageSize] Page size numérico: ${this.pageSize}`);
    }

    // Reset para primeira página quando mudar o tamanho
    this.currentPage = 1;

    // Limpar cache porque mudou a paginação
    this.cache.clear();
    console.log(`📄 [changePageSize] Cache limpo devido a mudança de page size`);

    // Recarregar transações
    this.loadTransactions();

    // Guardar preferência no localStorage
    if (newSize === 'all') {
      localStorage.setItem('transaction_page_size', 'all');
    } else {
      localStorage.setItem('transaction_page_size', newSize);
    }
  }

  updatePagination(totalRecords, currentPage) {
    const totalPages = Math.ceil(totalRecords / this.pageSize);
    const paginationUl = $('#pagination-ul');
    paginationUl.empty();

    // Update page info
    $('#page-info').text(`Page ${currentPage} of ${totalPages} (${totalRecords} total)`);

    // Se estamos mostrando todas as transações, não mostrar paginação
    if (this.pageSize >= totalRecords) {
      $('#pagination-nav').hide();
      return;
    }

    $('#pagination-nav').show();

    if (totalPages <= 1) return;

    // Previous button
    paginationUl.append(`
      <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
        <button class="page-link" onclick="transactionManager.goToPage(${currentPage - 1})">
          <i class="fas fa-chevron-left"></i> Previous
        </button>
      </li>
    `);

    // First page
    if (currentPage > 3) {
      paginationUl.append(`
        <li class="page-item">
          <button class="page-link" onclick="transactionManager.goToPage(1)">1</button>
        </li>
      `);
      if (currentPage > 4) {
        paginationUl.append(`<li class="page-item disabled"><span class="page-link">...</span></li>`);
      }
    }

    // Page numbers around current page
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    for (let i = startPage; i <= endPage; i++) {
      paginationUl.append(`
        <li class="page-item ${i === currentPage ? 'active' : ''}">
          <button class="page-link" onclick="transactionManager.goToPage(${i})">${i}</button>
        </li>
      `);
    }

    // Last page
    if (currentPage < totalPages - 2) {
      if (currentPage < totalPages - 3) {
        paginationUl.append(`<li class="page-item disabled"><span class="page-link">...</span></li>`);
      }
      paginationUl.append(`
        <li class="page-item">
          <button class="page-link" onclick="transactionManager.goToPage(${totalPages})">${totalPages}</button>
        </li>
      `);
    }

    // Next button
    paginationUl.append(`
      <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
        <button class="page-link" onclick="transactionManager.goToPage(${currentPage + 1})">
          Next <i class="fas fa-chevron-right"></i>
        </button>
      </li>
    `);
  }

  goToPage(page) {
    if (page < 1 || page > Math.ceil(this.totalRecords / this.pageSize)) return;
    this.currentPage = page;
    this.loadTransactions();
  }

  toggleBulkMode(enabled) {
    this.bulkMode = enabled;
    $('#select-all').toggle(enabled);
    $('#bulk-actions').toggleClass('d-none', !enabled);

    if (!enabled) {
      this.selectedRows.clear();
      $('.row-select').prop('checked', false);
    }

    this.loadTransactions(); // Reload to show/hide checkboxes
  }

  selectAll(checked) {
    $('.row-select').prop('checked', checked);
    this.selectedRows.clear();

    if (checked) {
      $('.row-select').each((i, el) => {
        this.selectedRows.add(parseInt(el.value));
      });
    }

    this.updateSelectionCount();
  }

  handleRowSelect(e) {
    const id = parseInt(e.target.value);
    if (e.target.checked) {
      this.selectedRows.add(id);
    } else {
      this.selectedRows.delete(id);
    }

    this.updateSelectionCount();

    // Update select all checkbox
    const totalVisible = $('.row-select').length;
    const selectedVisible = $('.row-select:checked').length;
    $('#select-all').prop('checked', totalVisible === selectedVisible && totalVisible > 0);
  }

  updateSelectionCount() {
    $('#selection-count').text(`${this.selectedRows.size} selected`);
  }

  async bulkMarkEstimated() {
    if (this.selectedRows.size === 0) {
      alert('Please select transactions first.');
      return;
    }

    const confirmed = confirm(`Mark ${this.selectedRows.size} transactions as estimated?`);
    if (!confirmed) return;

    try {
      const response = await fetch('/transactions/bulk-update/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
        },
        body: JSON.stringify({
          action: 'mark_estimated',
          transaction_ids: Array.from(this.selectedRows)
        })
      });

      if (response.ok) {
        this.cache.clear();
        this.loadTransactions();
        this.showSuccess('Transactions marked as estimated');
      } else {
        throw new Error('Failed to update transactions');
      }
    } catch (error) {
      this.showError('Failed to update transactions');
    }
  }

  simulateProgressForBulkOperation(operationType, itemCount) {
    let progress = 0;
    const totalSteps = Math.max(itemCount / 3, 15); // Steps para progresso mais controlado
    const baseIncrement = 60 / totalSteps; // Só vai até 60% na simulação inicial

    const messages = {
      'delete': [
        'Validating selected transactions...',
        'Checking permissions...',
        'Removing transactions from database...',
        'Updating account balances...',
        'Clearing transaction cache...',
        'Finalizing operation...'
      ],
      'duplicate': [
        'Reading original transactions...',
        'Creating duplicates...',
        'Copying transaction data...',
        'Assigning to current period...',
        'Updating cache...',
        'Finalizing operation...'
      ]
    };

    const interval = setInterval(() => {
      // Progresso mais lento conforme se aproxima do fim
      let increment = baseIncrement;
      if (progress > 30) increment *= 0.8;
      if (progress > 45) increment *= 0.6;

      progress += increment;

      if (progress >= 60) {
        clearInterval(interval);
        // Progresso mais lento e realista no final
        this.finalProgressSteps(operationType, messages[operationType]);
        return;
      }

      const messageIndex = Math.floor(progress / 12);
      const message = messages[operationType][messageIndex] || `Processing ${itemCount} transactions...`;

      this.updateProgress(Math.min(progress, 60), `${message} (${Math.floor(progress)}%)`);
    }, 250);

    return interval;
  }

  finalProgressSteps(operationType, messages) {
    // Passos finais mais lentos e realistas (de 60% para 93%)
    const finalSteps = [
      { percent: 65, message: messages[3] || `Processing ${operationType}...`, delay: 500 },
      { percent: 72, message: messages[4] || `Finishing ${operationType}...`, delay: 700 },
      { percent: 78, message: messages[5] || `Almost done...`, delay: 600 },
      { percent: 84, message: `Completing operation...`, delay: 800 },
      { percent: 89, message: `Finalizing...`, delay: 600 },
      { percent: 93, message: `Preparing final response...`, delay: 500 }
    ];

    let stepIndex = 0;
    const stepInterval = setInterval(() => {
      if (stepIndex >= finalSteps.length) {
        clearInterval(stepInterval);
        return;
      }

      const step = finalSteps[stepIndex];
      this.updateProgress(step.percent, step.message);
      stepIndex++;
    }, finalSteps[stepIndex]?.delay || 600);
  }

  async bulkDuplicate() {
    if (this.selectedRows.size === 0) {
      alert('Please select transactions first.');
      return;
    }

    const confirmed = confirm(`Duplicate ${this.selectedRows.size} transactions?`);
    if (!confirmed) return;

    this.showProgressModal('Duplicating Transactions', 'Preparing to duplicate transactions...');

    try {
      this.updateProgress(10, 'Sending request...');
      const progressInterval = this.simulateProgressForBulkOperation('duplicate', this.selectedRows.size);


      const response = await fetch('/transactions/bulk-duplicate/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
        },
        body: JSON.stringify({
          transaction_ids: Array.from(this.selectedRows)
        })
      });

      clearInterval(progressInterval);
      this.updateProgress(95, 'Processing duplicates...');


      if (response.ok) {
        this.updateProgress(96, 'Clearing cache...');
        this.cache.clear();

        this.updateProgress(97, 'Reloading data...');
        await Promise.all([
          this.loadTransactions(),
          this.loadTotals()
        ]);

        this.updateProgress(100, 'Complete!');
        setTimeout(() => {
          this.hideProgressModal();
          this.showSuccess('Transactions duplicated successfully');
        }, 500);
      } else {
        throw new Error('Failed to duplicate transactions');
      }
    } catch (error) {
      this.hideProgressModal();
      this.showError('Failed to duplicate transactions');
    }
  }

  async bulkDelete() {
    if (this.selectedRows.size === 0) {
      alert('Please select transactions first.');
      return;
    }

    const confirmed = confirm(`⚠️ Delete ${this.selectedRows.size} transactions? This action cannot be undone.`);
    if (!confirmed) return;

    this.showProgressModal('Deleting Transactions', 'Preparing to delete transactions...');

    try {
      this.updateProgress(10, 'Sending delete request...');
      const progressInterval = this.simulateProgressForBulkOperation('delete', this.selectedRows.size);

      const response = await fetch('/transactions/bulk-delete/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
        },
        body: JSON.stringify({
          transaction_ids: Array.from(this.selectedRows)
        })
      });

      clearInterval(progressInterval);
      this.updateProgress(95, 'Processing deletions...');


      if (response.ok) {
        this.updateProgress(96, 'Updating cash balances...');

        this.updateProgress(97, 'Clearing cache and selections...');
        this.cache.clear();
        this.selectedRows.clear();

        this.updateProgress(98, 'Reloading data...');
        await Promise.all([
          this.loadTransactions(),
          this.loadTotals()
        ]);

        this.updateProgress(100, 'Complete!');
        setTimeout(() => {
          this.hideProgressModal();
          this.showSuccess('Transactions deleted successfully');
        }, 500);
      } else {
        throw new Error('Failed to delete transactions');
      }
    } catch (error) {
      this.hideProgressModal();
      this.showError('Failed to delete transactions');
    }
  }

  async clearCache() {
    try {
      const response = await fetch('/transactions/clear-cache/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
        }
      });

      if (response.ok) {
        this.cache.clear();
        this.loadTransactions();
        this.showSuccess('Cache cleared successfully');
      }
    } catch (error) {
      this.showError('Failed to clear cache');
    }
  }

  exportData() {
    const filters = this.getFilters();
    const params = new URLSearchParams(filters);
    window.open(`/transactions/export-excel/?${params}`, '_blank');
  }

  importData() {
    window.location.href = '/transactions/import-excel/';
  }

  showLoading(show) {
    $('#loading-spinner').toggleClass('d-none', !show);
    $('#transactions-table').toggleClass('d-none', show);
  }

  showSuccess(message) {
    this.showToast(message, 'success');
  }

  showError(message) {
    this.showToast(message, 'danger');
  }

  showToast(message, type) {
    const toast = $(`
      <div class="toast position-fixed top-0 end-0 m-3" style="z-index: 9999;">
        <div class="toast-body bg-${type} text-white">
          ${message}
        </div>
      </div>
    `);

    $('body').append(toast);
    toast.toast({ delay: 3000 }).toast('show');

    toast.on('hidden.bs.toast', () => toast.remove());
  }

  showProgressModal(title, initialMessage) {
    const modal = $(`
      <div class="modal fade" id="progressModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">
                <i class="fas fa-cog fa-spin me-2"></i>
                ${title}
              </h5>
            </div>
            <div class="modal-body text-center">
              <div class="progress mb-3" style="height: 25px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
                     role="progressbar" style="width: 0%" id="bulk-progress-bar">
                  <span id="progress-text">0%</span>
                </div>
              </div>
              <div id="progress-message" class="text-muted">
                ${initialMessage}
              </div>
              <div class="mt-3">
                <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                  <span class="visually-hidden">Loading...</span>
                </div>
                <small class="text-muted">Please wait, do not close this window...</small>
              </div>
            </div>
          </div>
        </div>
      </div>
    `);

    // Remove any existing progress modal
    $('#progressModal').remove();

    $('body').append(modal);
    modal.modal('show');
  }

  updateProgress(percent, message) {
    const progressBar = $('#bulk-progress-bar');
    const progressText = $('#progress-text');
    const progressMessage = $('#progress-message');

    if (progressBar.length) {
      progressBar.css('width', percent + '%');
      progressText.text(percent + '%');
      progressMessage.text(message);

      // Add success styling when complete
      if (percent >= 100) {
        progressBar.removeClass('bg-primary').addClass('bg-success');
        progressBar.removeClass('progress-bar-animated');
        progressMessage.html('<i class="fas fa-check-circle text-success me-1"></i>' + message);
      }
    }
  }

  hideProgressModal() {
    const modal = $('#progressModal');
    if (modal.length) {
      modal.modal('hide');
      // Remove modal after animation completes
      setTimeout(() => modal.remove(), 300);
    }
  }
}

// Global functions
let transactionManager;

$(document).ready(() => {
  transactionManager = new TransactionManager();
});

async function deleteTransaction(id) {
  const confirmed = confirm('⚠️ Delete this transaction? This action cannot be undone.');
  if (!confirmed) return;

  try {
    const response = await fetch(`/transactions/${id}/delete/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
      }
    });

    if (response.ok) {
      transactionManager.cache.clear();
      transactionManager.loadTransactions();
      transactionManager.loadTotals();
      transactionManager.showSuccess('Transaction deleted successfully');
    } else {
      throw new Error('Failed to delete transaction');
    }
  } catch (error) {
    transactionManager.showError('Failed to delete transaction');
  }
}