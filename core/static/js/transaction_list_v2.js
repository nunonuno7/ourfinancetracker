// Transactions 2.0 JavaScript - Advanced functionality
class TransactionManager {
  constructor() {
    console.log("🚀 [TransactionManager] Initializing Transaction Manager...");
    this.currentPage = 1;
    this.pageSize = 25;
    this.totalRecords = 0;
    this.filters = {};
    this.cache = new Map();
    this.selectedRows = new Set();
    this.bulkMode = false;
    this.maxPageSize = 1000; // Maximum safety limit

    // Sorting state
    this.sortField = "date";
    this.sortDirection = "desc"; // 'asc' or 'desc'

    console.log("⚙️ [TransactionManager] Initial configuration:", {
      currentPage: this.currentPage,
      pageSize: this.pageSize,
      cacheSize: this.cache.size,
      sortField: this.sortField,
      sortDirection: this.sortDirection,
    });

    this.init();
  }

  init() {
    console.log("🔧 [init] Starting complete initialization...");

    this.initDatePickers();
    console.log("📅 [init] Date pickers initialized");

    this.loadPageSizePreference();
    console.log("📄 [init] Page size loaded from storage");

    this.loadFiltersFromStorage();
    console.log("💾 [init] Filters loaded from storage");

    this.bindEvents();
    console.log("🔗 [init] Event listeners connected");

    this.loadTransactions();
    this.loadTotals();

    // Initialize sort indicators
    this.updateSortIndicators();

    // Initialize checkbox column as hidden (since bulk mode starts as false)
    $("#transactions-table thead th:first-child").css("display", "none");

    console.log("✅ [init] Complete initialization finished");
  }

  loadPageSizePreference() {
    const savedPageSize = localStorage.getItem("transaction_page_size");
    if (savedPageSize) {
      $("#page-size-selector").val(savedPageSize);
      if (savedPageSize === "all") {
        this.pageSize = this.maxPageSize;
      } else {
        this.pageSize = parseInt(savedPageSize);
      }
      console.log(
        `📄 [loadPageSizePreference] Page size restaurado: ${savedPageSize} (${this.pageSize})`,
      );
    }
  }

  initDatePickers() {
    flatpickr("#date-start", {
      dateFormat: "Y-m-d",
      defaultDate: "2025-01-01",
      onChange: () => this.onFilterChange(),
    });

    flatpickr("#date-end", {
      dateFormat: "Y-m-d",
      defaultDate: new Date(),
      onChange: () => this.onFilterChange(),
    });
  }

  bindEvents() {
    // Filter changes
    $("#filter-type, #filter-account, #filter-category, #filter-period").on(
      "change",
      () => this.onFilterChange(),
    );
    $("#filter-amount-min, #filter-amount-max, #filter-tags").on(
      "input",
      this.debounce(() => this.onFilterChange(), 500),
    );
    $("#global-search").on(
      "input",
      this.debounce(() => this.onFilterChange(), 300),
    );
    $("#include-system-toggle").on("change", () => {
      this.onFilterChange();
      // Show/hide legend based on toggle
      $("#synthetic-legend").toggle($("#include-system-toggle").is(":checked"));
    });

    // Page size selector
    $("#page-size-selector").on("change", (e) =>
      this.changePageSize(e.target.value),
    );

    // Buttons
    $("#apply-filters-btn").on("click", () => this.loadTransactions());
    $("#clear-filters-btn").on("click", () => this.clearFilters());
    $("#clear-cache-btn").on("click", () => this.clearCache());

    $("#export-btn").on("click", () => this.exportData());
    $("#import-btn").on("click", () => this.importData());

    // Bulk actions
    $("#bulk-mode-toggle").on("change", (e) =>
      this.toggleBulkMode(e.target.checked),
    );
    $("#select-all").on("change", (e) => this.selectAll(e.target.checked));
    $("#bulk-mark-cleared").on("click", () => this.bulkMarkCleared());
    $("#bulk-duplicate").on("click", () => this.bulkDuplicate());
    $("#bulk-delete").on("click", () => this.bulkDelete());

    // Row selection
    $(document).on("change", ".row-select", (e) => this.handleRowSelect(e));
    $(document).on("click", ".transaction-row", (e) => this.handleRowClick(e));

    // Column sorting
    $(document).on("click", ".sortable-header", (e) => this.handleSort(e));
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
    console.group("🔄 [onFilterChange] FILTERS CHANGED");
    console.log("Timestamp:", new Date().toISOString());
    this.currentPage = 1;

    const currentFilters = this.getFilters();
    console.log("🎯 CURRENT FILTERS:");
    console.table(currentFilters);

    const typeMapping = {
      'Income': 'IN',
      'Expense': 'EX', 
      'Investment': 'IV',
      'Transfer': 'TR',
      'Adjustment': 'AJ'
    };
    
    console.log("🔧 DOM ELEMENT VALUES:");
    console.table({
      dateStart: $("#date-start").val(),
      dateEnd: $("#date-end").val(),
      type: $("#filter-type").val(),
      typeMapped: typeMapping[$("#filter-type").val()] || $("#filter-type").val(),
      account: $("#filter-account").val(),
      category: $("#filter-category").val(),
      period: $("#filter-period").val(),
      amountMin: $("#filter-amount-min").val(),
      amountMax: $("#filter-amount-max").val(),
      tags: $("#filter-tags").val(),
      search: $("#global-search").val(),
    });

    // Show visual feedback that filters are being applied
    this.showFilterFeedback();

    this.saveFiltersToStorage();
    console.log("💾 Filters saved to session");

    // Excel-style: Invalidate cache when filters change
    console.log(
      "🗑️ Clearing cache (Excel style) - cache size before:",
      this.cache.size,
    );
    this.cache.clear();
    console.log("🗑️ Cache size after:", this.cache.size);

    console.log("🚀 Starting loadTransactions...");
    this.loadTransactions();

    console.log("💰 Starting loadTotals...");
    this.loadTotals();

    console.groupEnd();
  }

  showFilterFeedback() {
    // Add visual feedback to show filters are active (Excel-style)
    const filters = this.getFilters();
    const activeFilters = Object.keys(filters).filter((key) => {
      // Exclude pagination and system params
      const excludeKeys = ['page', 'page_size', 'sort_field', 'sort_direction', 'include_system'];
      return !excludeKeys.includes(key) && filters[key] && filters[key] !== "";
    });
    
    const indicator = $("#filter-indicator");

    if (activeFilters.length > 0) {
      // Build detailed filter description
      const filterDescriptions = activeFilters.map(key => {
        const value = filters[key];
        const displayKey = key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
        return `${displayKey}: ${value}`;
      }).join(', ');

      if (indicator.length === 0) {
        $("#filters-row").prepend(`
          <div id="filter-indicator" class="col-12">
            <div class="alert alert-info alert-sm mb-2">
              <i class="fas fa-filter"></i> <span id="filter-count">${activeFilters.length}</span> active filter(s) - Excel-style cascading
              <small class="d-block mt-1" id="filter-details">${filterDescriptions}</small>
            </div>
          </div>
        `);
      } else {
        $("#filter-count").text(activeFilters.length);
        $("#filter-details").text(filterDescriptions);
      }
    } else {
      indicator.remove();
    }
  }

  getFilters() {
    // Map frontend display values to backend enum values
    const typeMapping = {
      'Income': 'IN',
      'Expense': 'EX', 
      'Investment': 'IV',
      'Transfer': 'TR',
      'Adjustment': 'AJ'
    };

    const selectedType = $("#filter-type").val();
    const mappedType = typeMapping[selectedType] || selectedType;

    const filters = {
      date_start: $("#date-start").val(),
      date_end: $("#date-end").val(),
      type: mappedType, // Use mapped type
      account: $("#filter-account").val(),
      category: $("#filter-category").val(),
      period: $("#filter-period").val(),
      amount_min: $("#filter-amount-min").val(),
      amount_max: $("#filter-amount-max").val(),
      tags: $("#filter-tags").val(),
      search: $("#global-search").val(),
      page: this.currentPage,
      page_size: this.pageSize,
      sort_field: this.sortField,
      sort_direction: this.sortDirection,
      include_system: $("#include-system-toggle").is(":checked"),
    };

    // Filter out empty values to prevent backend filter issues
    const cleanFilters = {};
    Object.keys(filters).forEach((key) => {
      const value = filters[key];
      if (value !== "" && value !== null && value !== undefined) {
        cleanFilters[key] = value;
      }
    });

    // Always include required pagination and sorting params
    cleanFilters.page = this.currentPage;
    cleanFilters.page_size = this.pageSize;
    cleanFilters.sort_field = this.sortField;
    cleanFilters.sort_direction = this.sortDirection;
    cleanFilters.include_system = $("#include-system-toggle").is(":checked");

    return cleanFilters;
  }

  saveFiltersToStorage() {
    const filters = this.getFilters();
    sessionStorage.setItem("transaction_filters_v2", JSON.stringify(filters));
  }

  loadFiltersFromStorage() {
    const saved = sessionStorage.getItem("transaction_filters_v2");
    if (saved) {
      const filters = JSON.parse(saved);
      Object.keys(filters).forEach((key) => {
        const element = $(`#${key.replace("_", "-")}`);
        if (element.length && filters[key]) {
          element.val(filters[key]);
        }
      });
    }
  }

  clearFilters() {
    $("#date-start").val("2024-01-01");
    $("#date-end").val(new Date().toISOString().split("T")[0]);
    $("#filter-type, #filter-account, #filter-category, #filter-period").val("");
    $("#filter-amount-min, #filter-amount-max, #filter-tags, #global-search").val("");
    $("#include-system-toggle").prop("checked", true);

    sessionStorage.removeItem("transaction_filters_v2");
    this.currentPage = 1;
    this.cache.clear(); // Clear cache when clearing filters
    this.loadTransactions();
    this.loadTotals();
  }

  generateCacheKey() {
    const filters = this.getFilters();
    const key = Object.keys(filters)
      .sort()
      .map((k) => `${k}:${filters[k]}`)
      .join("|");
    const cacheKey = `tx_v2_${btoa(key)}`;
    console.log("🔑 [generateCacheKey] Cache key gerada:", {
      filters: filters,
      keyString: key,
      finalCacheKey: cacheKey,
    });
    return cacheKey;
  }

  async loadTransactions() {
    console.log("🔄 [loadTransactions] LOADING START");

    try {
      this.showLoader(true);

      const filters = this.getFilters();
      const params = new URLSearchParams();

      // Add all filters to params
      Object.keys(filters).forEach((key) => {
        if (
          filters[key] !== "" &&
          filters[key] !== null &&
          filters[key] !== undefined
        ) {
          params.append(key, filters[key]);
        }
      });

      const url = `/transactions/json-v2/?${params.toString()}`;
      console.log("🌐 [loadTransactions] Request URL:", url);

      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken":
            $("[name=csrfmiddlewaretoken]").val() || window.csrfToken || "",
        },
      });

      console.log("📡 [loadTransactions] Response status:", response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ HTTP Error Response:", errorText);
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log("📊 [loadTransactions] Full response data:", data);

      if (!data.transactions) {
        console.log("⚠️ [loadTransactions] No transactions key in response");
        this.transactions = [];
        this.totalCount = 0;
      } else if (data.transactions.length === 0) {
        console.log("⚠️ [loadTransactions] Empty transactions array");
        this.transactions = [];
        this.totalCount = data.total_count || 0;
      } else {
        this.transactions = data.transactions;
        this.totalCount = data.total_count || 0;
        console.log(
          `✅ [loadTransactions] Loaded ${this.transactions.length} of ${this.totalCount} transactions`,
        );
      }

      // Update filters if provided
      if (data.filters) {
        this.availableFilters = data.filters;
        this.updateFilterOptions(data.filters);
      }

      this.renderTransactions(data);
      this.updatePagination(data.total_count, data.current_page);
    } catch (error) {
      console.error("❌ [loadTransactions] Error:", error);
      this.showError("Failed to load transactions: " + error.message);
      this.transactions = [];
      this.totalCount = 0;
      this.renderTransactions({
        transactions: [],
        total_count: 0,
        current_page: 1,
      }); // Show empty state
    } finally {
      this.showLoader(false);
    }
  }

  async loadTotals() {
    console.log("💰 [loadTotals] Iniciando carregamento de totais...");
    try {
      const filters = this.getFilters();
      
      // Remove pagination and sorting params for totals calculation
      const totalsFilters = { ...filters };
      delete totalsFilters.page;
      delete totalsFilters.page_size;
      delete totalsFilters.sort_field;
      delete totalsFilters.sort_direction;
      
      console.log("🔍 [loadTotals] Filtros para totais (limpos):", totalsFilters);

      const response = await fetch("/transactions/totals-v2/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken":
            window.csrfToken ||
            $("[name=csrfmiddlewaretoken]").val() ||
            $("meta[name=csrf-token]").attr("content"),
        },
        body: JSON.stringify(totalsFilters),
      });

      console.log(
        "📡 [loadTotals] Resposta dos totais recebida, status:",
        response.status,
      );

      if (!response.ok) throw new Error("Failed to load totals");

      const totals = await response.json();
      console.log("📊 [loadTotals] Totais recebidos:", totals);

      this.renderTotals(totals);
      console.log(
        "✅ [loadTotals] Totais carregados e renderizados com sucesso",
      );
    } catch (error) {
      console.error("❌ [loadTotals] Erro ao carregar totais:", error);
    }
  }

  renderTransactions(data) {
    console.group("🎨 [renderTransactions] RENDERIZAÇÃO INICIADA");
    console.log("Timestamp:", new Date().toISOString());

    console.log("📋 VALIDAÇÃO DOS DADOS:");
    console.table({
      hasData: !!data,
      hasTransactions: !!(data && data.transactions),
      transactionCount: data?.transactions?.length || 0,
      totalCount: data?.total_count || 0,
      currentPage: data?.current_page || 0,
      dataKeys: data ? Object.keys(data) : [],
    });

    const tbody = $("#transactions-tbody");
    const currentRowCount = tbody.find("tr").length;
    console.log("🗂️ DOM - Linhas antes de limpar:", currentRowCount);
    console.log("🗂️ DOM - Element exists:", tbody.length > 0);

    tbody.empty();
    console.log("🧹 Tabela limpa");

    if (!data || !data.transactions || data.transactions.length === 0) {
      console.warn("⚠️ SEM TRANSAÇÕES - Exibindo mensagem vazia");
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
      $("#total-count").text("No transactions found");
      console.groupEnd();
      return;
    }

    console.log("✏️ CRIANDO", data.transactions.length, "LINHAS DA TABELA");

    // Performance optimization for large datasets
    const batchSize = 50;
    const transactions = data.transactions;

    if (transactions.length > batchSize) {
      // Render in batches for better performance
      console.log(
        `📊 [renderTransactions] Renderização em lotes: ${transactions.length} transações, lotes de ${batchSize}`,
      );

      let index = 0;
      const renderBatch = () => {
        const endIndex = Math.min(index + batchSize, transactions.length);
        const batch = transactions.slice(index, endIndex);

        batch.forEach((tx, batchIndex) => {
          try {
            const row = this.createTransactionRow(tx, index + batchIndex);
            tbody.append(row);
          } catch (error) {
            console.error(
              `❌ Erro ao criar linha ${index + batchIndex + 1}:`,
              error,
            );
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
        if (index < 3) {
          // Only log first 3 for brevity
          console.log(`📝 Transaction ${index + 1}:`, tx);
        }
        try {
          const row = this.createTransactionRow(tx, index);
          tbody.append(row);
          if (index < 3) {
            console.log(`✅ Row ${index + 1} added successfully`);
          }
        } catch (error) {
          console.error(`❌ Erro ao criar linha ${index + 1}:`, error);
        }
      });

      this.finishRendering(data);
    }
  }

  finishRendering(data) {
    const finalRowCount = $("#transactions-tbody tr").length;
    console.log("📊 DOM - Linhas finais:", finalRowCount);

    this.totalRecords = data.total_count;
    this.updatePagination(data.total_count, data.current_page);

    const showingAll = this.pageSize >= data.total_count;
    const countMessage = showingAll
      ? `All ${data.total_count} transactions shown`
      : `${data.total_count} transactions found (showing ${data.transactions.length} on this page)`;

    $("#total-count").text(countMessage);
    console.log("📊 Count message set:", countMessage);
    console.log("✅ RENDERIZAÇÃO CONCLUÍDA");
    console.groupEnd();
  }

  createTransactionRow(tx, index) {
    const isSelected = this.selectedRows.has(tx.id);

    // Format type display
    let typeDisplay = tx.type;

    // Style for system transactions and adjust type display
    const isSystemRow = tx.is_system;
    const rowClass = isSystemRow ? "table-warning" : "";
    let systemBadge = "";

    if (isSystemRow) {
      systemBadge = '<span class="badge bg-info ms-1">AUTO</span>';

      // Keep the type display as received from backend, don't modify it
      // The backend already maps 'AJ' -> 'Adjustment' correctly
    }

    // Disable actions for non-editable system transactions
    const actionsHtml = tx.editable
      ? `
      <div class="btn-group btn-group-sm">
        <a href="/transactions/${tx.id}/edit/" class="btn btn-outline-primary btn-sm" title="Edit">
          <i class="fas fa-edit"></i>
        </a>
        <a href="/transactions/${tx.id}/delete/" class="btn btn-outline-danger btn-sm" title="Delete">
          <i class="fas fa-trash"></i>
        </a>
      </div>
    `
      : `
      <div class="btn-group btn-group-sm">
        <button class="btn btn-outline-secondary btn-sm" disabled title="System transaction - read only">
          <i class="fas fa-lock"></i>
        </button>
      </div>
    `;

    // Sempre criar a coluna do checkbox, mas controlar visibilidade
    const checkboxVisibility = this.bulkMode ? "" : 'style="display: none;"';

    return `
      <tr data-id="${tx.id}" class="${rowClass}">
        <td ${checkboxVisibility}><input type="checkbox" class="form-check-input row-select" value="${tx.id}" ${isSelected ? "checked" : ""}></td>
        <td>${tx.date}</td>
        <td class="d-none d-md-table-cell">${tx.period}</td>
        <td>${tx.type}${systemBadge}</td>
        <td class="text-end">${tx.amount_formatted}</td>
        <td class="d-none d-lg-table-cell">${tx.category}</td>
        <td class="d-none d-xl-table-cell">${tx.tags}</td>
        <td class="d-none d-md-table-cell">${tx.account}</td>
        <td class="text-end">${actionsHtml}</td>
      </tr>
    `;
  }

  getTypeIcon(type) {
    const icons = {
      Expense: "💸",
      Income: "💰",
      Investment: "📈",
      Transfer: "🔁",
      "System adjustment": "🧮",
    };
    return icons[type] || "📄";
  }

  getTypeBadgeClass(type) {
    const classes = {
      Expense: "bg-danger",
      Income: "bg-success",
      Investment: "bg-info",
      Transfer: "bg-warning text-dark",
      "System adjustment": "bg-warning text-dark",
    };
    return classes[type] || "bg-secondary";
  }

  renderTotals(totals) {
    console.log("💰 [renderTotals] Renderizando totais:", totals);

    const income = this.formatCurrency(totals.income || 0);
    const expenses = this.formatCurrency(totals.expenses || 0);
    const investments = this.formatCurrencyPortuguese(totals.investments || 0);
    const balance = this.formatCurrencyPortuguese(totals.balance || 0);

    console.log("💰 [renderTotals] Valores formatados:", {
      income,
      expenses,
      investments,
      balance,
    });

    $("#total-income").text(income);
    $("#total-expenses").text(expenses);
    $("#total-investments").text(investments);
    $("#total-balance").text(balance);

    console.log("✅ [renderTotals] Totais atualizados na interface");
  }

  formatCurrency(amount) {
    return new Intl.NumberFormat("pt-PT", {
      style: "currency",
      currency: "EUR",
    }).format(amount);
  }

  formatCurrencyPortuguese(amount) {
    // Format number in Portuguese style: -1.234,56 €
    const isNegative = amount < 0;
    const absAmount = Math.abs(amount);

    // Format with Portuguese locale
    const formatted = absAmount
      .toFixed(2)
      .replace(".", ",") // Decimal separator
      .replace(/\B(?=(\d{3})+(?!\d))/g, "."); // Thousands separator

    return `${isNegative ? "-" : ""}${formatted} €`;
  }

  formatDisplayAmount(amount) {
    // Format amount for display in table
    const isNegative = amount < 0;
    const absAmount = Math.abs(amount);

    // Format with Portuguese locale
    const formatted = absAmount
      .toFixed(2)
      .replace(".", ",") // Decimal separator
      .replace(/\B(?=(\d{3})+(?!\d))/g, "."); // Thousands separator

    return `€ ${isNegative ? "-" : ""}${formatted}`;
  }

  updateFilterOptions(filters) {
    console.log(
      "🔧 [updateFilterOptions] Atualizando opções dos filtros (estilo Excel)",
    );
    if (!filters) {
      console.warn("⚠️ [updateFilterOptions] Nenhum dado de filtros recebido");
      return;
    }

    console.log(
      "📝 [updateFilterOptions] Filtros disponíveis (apenas com transações visíveis):",
      {
        types: filters.types?.length || 0,
        categories: filters.categories?.length || 0,
        accounts: filters.accounts?.length || 0,
        periods: filters.periods?.length || 0,
      },
    );

    console.log("📋 [updateFilterOptions] Detalhes dos filtros:", {
      typesList: filters.types || [],
      categoriesList: filters.categories || [],
      accountsList: filters.accounts || [],
      periodsList: filters.periods || [],
    });

    // Update filter options while preserving current selections (Excel-style)
    this.updateSelectOptions(
      "#filter-type",
      filters.types || [],
      "type",
    );
    this.updateSelectOptions(
      "#filter-category",
      filters.categories || [],
      "category",
    );
    this.updateSelectOptions(
      "#filter-account",
      filters.accounts || [],
      "account",
    );
    this.updateSelectOptions("#filter-period", filters.periods || [], "period");

    console.log(
      "✅ [updateFilterOptions] Opções de filtros atualizadas (estilo Excel)",
    );
  }

  updateFilterDropdowns() {
    // Alias for updateFilterOptions for compatibility
    this.updateFilterOptions(this.availableFilters);
  }

  updateSelectOptions(selector, options, filterType) {
    const select = $(selector);
    const currentValue = select.val();

    console.log(
      `🔧 [updateSelectOptions] Atualizando ${filterType} - valor atual: '${currentValue}', opções disponíveis:`,
      options,
    );

    // Clear and rebuild options
    select.empty();
    select.append(
      `<option value="">All ${filterType ? filterType.charAt(0).toUpperCase() + filterType.slice(1) + "s" : "Options"}</option>`,
    );

    // Add available options (Excel-style - only those with data in current filter context)
    options.forEach((option) => {
      const selected = option === currentValue ? " selected" : "";
      select.append(`<option value="${option}"${selected}>${option}</option>`);
    });

    // Excel behavior: Keep current selection if it exists in filtered data
    // Only clear if the current value is not in the available options
    if (currentValue && !options.includes(currentValue)) {
      select.val("");
      console.log(
        `🔄 [updateSelectOptions] Filtro ${filterType} resetado - valor '${currentValue}' não existe nos dados filtrados (estilo Excel)`,
      );

      // Trigger change event to update other filters
      setTimeout(() => {
        console.log(
          `🔄 [updateSelectOptions] Triggering change event for ${filterType} reset`,
        );
        select.trigger("change");
      }, 100);
    } else if (currentValue && options.includes(currentValue)) {
      console.log(
        `✅ [updateSelectOptions] Filtro ${filterType} mantido - valor '${currentValue}' existe nos dados filtrados`,
      );
    }

    console.log(
      `📋 [updateSelectOptions] ${filterType}: ${options.length} opções disponíveis (estilo Excel)`,
    );
  }

  changePageSize(newSize) {
    console.log(`📄 [changePageSize] Alterando page size para: ${newSize}`);

    if (newSize === "all") {
      // Para "all", usar um número muito alto mas limitado por segurança
      this.pageSize = Math.min(
        this.totalRecords || this.maxPageSize,
        this.maxPageSize,
      );
      console.log(
        `📄 [changePageSize] Page size "all" definido como: ${this.pageSize}`,
      );
    } else {
      this.pageSize = parseInt(newSize);
      console.log(`📄 [changePageSize] Page size numérico: ${this.pageSize}`);
    }

    // Reset para primeira página quando mudar o tamanho
    this.currentPage = 1;

    // Limpar cache porque mudou a paginação
    this.cache.clear();
    console.log(
      `📄 [changePageSize] Cache limpo devido a mudança de page size`,
    );

    // Recarregar transações
    this.loadTransactions();

    // Guardar preferência no localStorage
    if (newSize === "all") {
      localStorage.setItem("transaction_page_size", "all");
    } else {
      localStorage.setItem("transaction_page_size", newSize);
    }
  }

  updatePagination(totalRecords, currentPage) {
    const totalPages = Math.ceil(totalRecords / this.pageSize);
    const paginationUl = $("#pagination-ul");
    paginationUl.empty();

    // Update page info
    $("#page-info").text(
      `Page ${currentPage} of ${totalPages} (${totalRecords} total)`,
    );

    // Se estamos mostrando todas as transações, não mostrar paginação
    if (this.pageSize >= totalRecords) {
      $("#pagination-nav").hide();
      return;
    }

    $("#pagination-nav").show();

    if (totalPages <= 1) return;

    // Previous button
    paginationUl.append(`
      <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
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
        paginationUl.append(
          `<li class="page-item disabled"><span class="page-link">...</span></li>`,
        );
      }
    }

    // Page numbers around current page
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    for (let i = startPage; i <= endPage; i++) {
      paginationUl.append(`
        <li class="page-item ${i === currentPage ? "active" : ""}">
          <button class="page-link" onclick="transactionManager.goToPage(${i})">${i}</button>
        </li>
      `);
    }

    // Last page
    if (currentPage < totalPages - 2) {
      if (currentPage < totalPages - 3) {
        paginationUl.append(
          `<li class="page-item disabled"><span class="page-link">...</span></li>`,
        );
      }
      paginationUl.append(`
        <li class="page-item">
          <button class="page-link" onclick="transactionManager.goToPage(${totalPages})">${totalPages}</button>
        </li>
      `);
    }

    // Next button
    paginationUl.append(`
      <li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
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
    $("#select-all").toggle(enabled);
    $("#bulk-actions").toggleClass("d-none", !enabled);

    // Mostrar/ocultar a coluna inteira do checkbox no cabeçalho
    const checkboxHeader = $("#transactions-table thead th:first-child");
    if (enabled) {
      checkboxHeader.css("display", "");
    } else {
      checkboxHeader.css("display", "none");
    }

    // Mostrar/ocultar todas as células da primeira coluna no tbody
    $("#transactions-tbody tr").each(function () {
      const firstCell = $(this).find("td:first-child");
      if (enabled) {
        firstCell.css("display", "");
      } else {
        firstCell.css("display", "none");
      }
    });

    if (!enabled) {
      this.selectedRows.clear();
      $(".row-select").prop("checked", false);
    }

    this.loadTransactions(); // Reload to show/hide checkboxes
  }

  selectAll(checked) {
    $(".row-select").prop("checked", checked);
    this.selectedRows.clear();

    if (checked) {
      $(".row-select").each((i, el) => {
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
    const totalVisible = $(".row-select").length;
    const selectedVisible = $(".row-select:checked").length;
    $("#select-all").prop(
      "checked",
      totalVisible === selectedVisible && totalVisible > 0,
    );
  }

  updateSelectionCount() {
    $("#selection-count").text(`${this.selectedRows.size} selected`);
  }

  async bulkMarkCleared() {
    if (this.selectedRows.size === 0) {
      alert("Please select transactions first.");
      return;
    }

    const confirmed = confirm(
      `Mark ${this.selectedRows.size} transactions as cleared/confirmed?`,
    );
    if (!confirmed) return;

    try {
      const response = await fetch("/transactions/bulk-update/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": $("[name=csrfmiddlewaretoken]").val(),
        },
        body: JSON.stringify({
          action: "mark_estimated",
          transaction_ids: Array.from(this.selectedRows),
        }),
      });

      if (response.ok) {
        this.cache.clear();
        this.loadTransactions();
        this.showSuccess("Transactions marked as cleared");
      } else {
        throw new Error("Failed to update transactions");
      }
    } catch (error) {
      this.showError("Failed to update transactions");
    }
  }

  async bulkDuplicate() {
    if (this.selectedRows.size === 0) {
      alert("Please select transactions first.");
      return;
    }

    const confirmed = confirm(
      `Duplicate ${this.selectedRows.size} transactions?`,
    );
    if (!confirmed) return;

    // Show simple loading indicator
    this.showLoading(true);
    const loadingToast = this.showToast(
      `Duplicating ${this.selectedRows.size} transactions...`,
      "info",
      0,
    );

    try {
      const startTime = performance.now();

      const response = await fetch("/transactions/bulk-duplicate/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": $("[name=csrfmiddlewaretoken]").val(),
        },
        body: JSON.stringify({
          transaction_ids: Array.from(this.selectedRows),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to duplicate transactions");
      }

      const result = await response.json();
      const endTime = performance.now();
      const duration = ((endTime - startTime) / 1000).toFixed(1);

      // Clear cache and reload data
      this.cache.clear();
      await Promise.all([this.loadTransactions(), this.loadTotals()]);

      // Hide loading toast
      if (loadingToast) loadingToast.remove();

      this.showSuccess(
        `✅ ${result.created} transactions duplicated successfully in ${duration}s`,
      );
    } catch (error) {
      console.error("Bulk duplicate error:", error);
      if (loadingToast) loadingToast.remove();
      this.showError(`❌ Failed to duplicate transactions: ${error.message}`);
    } finally {
      this.showLoading(false);
    }
  }

  async bulkDelete() {
    if (this.selectedRows.size === 0) {
      alert("Please select transactions first.");
      return;
    }

    const confirmed = confirm(
      `⚠️ Delete ${this.selectedRows.size} transactions? This action cannot be undone.`,
    );
    if (!confirmed) return;

    // Show simple loading indicator instead of fake progress
    this.showLoading(true);
    const loadingToast = this.showToast(
      `Deleting ${this.selectedRows.size} transactions...`,
      "info",
      0,
    ); // No auto-hide

    try {
      const startTime = performance.now();

      const response = await fetch("/transactions/bulk-delete/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": $("[name=csrfmiddlewaretoken]").val(),
        },
        body: JSON.stringify({
          transaction_ids: Array.from(this.selectedRows),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to delete transactions");
      }

      const result = await response.json();
      const endTime = performance.now();
      const duration = ((endTime - startTime) / 1000).toFixed(1);

      // Clear selections and cache immediately
      this.selectedRows.clear();
      this.cache.clear();
      this.updateSelectionCount();

      // Reload data
      await Promise.all([this.loadTransactions(), this.loadTotals()]);

      // Hide loading toast
      if (loadingToast) loadingToast.remove();

      this.showSuccess(
        `✅ ${result.deleted} transactions deleted successfully in ${duration}s`,
      );
    } catch (error) {
      console.error("Bulk delete error:", error);
      if (loadingToast) loadingToast.remove();
      this.showError(`❌ Failed to delete transactions: ${error.message}`);
    } finally {
      this.showLoading(false);
    }
  }

  async clearCache() {
    try {
      console.log("🧹 [clearCache] Starting cache clear operation...");

      const response = await fetch("/transactions/clear-cache/", {
        method: "GET",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken":
            $("[name=csrfmiddlewaretoken]").val() || window.csrfToken || "",
        },
      });

      console.log("📡 [clearCache] Response status:", response.status);

      if (response.ok) {
        const result = await response.json();
        console.log("📋 [clearCache] Server response:", result);

        if (result.success) {
          // Clear local cache
          this.cache.clear();
          console.log("🗑️ [clearCache] Local cache cleared");

          // Reload both transactions and totals to reflect updated estimates
          await Promise.all([this.loadTransactions(), this.loadTotals()]);

          this.showSuccess("✅ Cache cleared successfully!");
          console.log("✅ [clearCache] Operation completed successfully");
        } else {
          throw new Error(result.error || "Unknown error occurred");
        }
      } else {
        const errorData = await response.json();
        console.error("❌ [clearCache] Server response error:", errorData);
        throw new Error(
          errorData.error || `HTTP ${response.status}: ${response.statusText}`,
        );
      }
    } catch (error) {
      console.error("❌ [clearCache] Error:", error);
      this.showError(`Failed to clear cache: ${error.message}`);
    }
  }

  exportData() {
    const filters = this.getFilters();
    const params = new URLSearchParams(filters);
    window.open(`/transactions/export-excel/?${params}`, "_blank");
  }

  importData() {
    window.location.href = "/transactions/import-excel/";
  }

  showLoader(show) {
    $("#loading-spinner").toggleClass("d-none", !show);
    $("#transactions-table").toggleClass("d-none", show);
  }

  showLoading(show) {
    $("#loading-spinner").toggleClass("d-none", !show);
    $("#transactions-table").toggleClass("d-none", show);
  }

  showSuccess(message) {
    this.showToast(message, "success");
  }

  showError(message) {
    this.showToast(message, "danger");
  }

  showToast(message, type, delay = 3000) {
    const toastId = `toast-${Date.now()}-${Math.random()}`;
    const toast = $(`
      <div class="toast position-fixed top-0 end-0 m-3" id="${toastId}" style="z-index: 9999;">
        <div class="toast-body bg-${type} text-white">
          ${message}
        </div>
      </div>
    `);

    $("body").append(toast);

    if (delay > 0) {
      toast.toast({ delay: delay }).toast("show");
      toast.on("hidden.bs.toast", () => toast.remove());
    } else {
      // Persistent toast - won't auto-hide
      toast.show();
    }

    return toast; // Return toast element for manual control
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
    $("#progressModal").remove();

    $("body").append(modal);
    modal.modal("show");
  }

  updateProgress(percent, message) {
    const progressBar = $("#bulk-progress-bar");
    const progressText = $("#progress-text");
    const progressMessage = $("#progress-message");

    if (progressBar.length) {
      progressBar.css("width", percent + "%");
      progressText.text(percent + "%");
      progressMessage.text(message);

      // Add success styling when complete
      if (percent >= 100) {
        progressBar.removeClass("bg-primary").addClass("bg-success");
        progressBar.removeClass("progress-bar-animated");
        progressMessage.html(
          '<i class="fas fa-check-circle text-success me-1"></i>' + message,
        );
      }
    }
  }

  hideProgressModal() {
    const modal = $("#progressModal");
    if (modal.length) {
      modal.modal("hide");
      // Remove modal after animation completes
      setTimeout(() => modal.remove(), 300);
    }
  }

  handleSort(e) {
    const header = $(e.currentTarget);
    const sortField = header.data("sort");

    console.log("🔤 [handleSort] Column clicked:", sortField);

    // Toggle sort direction if same field, otherwise default to desc for most fields, asc for text fields
    if (this.sortField === sortField) {
      this.sortDirection = this.sortDirection === "asc" ? "desc" : "asc";
    } else {
      // Default sorting directions
      const textFields = ["type", "category", "account", "tags", "period"];
      this.sortDirection = textFields.includes(sortField) ? "asc" : "desc";
    }

    this.sortField = sortField;
    this.currentPage = 1; // Reset to first page when sorting

    console.log("🔤 [handleSort] New sort state:", {
      field: this.sortField,
      direction: this.sortDirection,
    });

    // Update visual indicators
    this.updateSortIndicators();

    // Clear cache and reload data
    this.cache.clear();
    this.loadTransactions();
  }

  updateSortIndicators() {
    // Remove all active states and reset icons
    $(".sortable-header").removeClass("active sort-asc sort-desc");
    $(".sort-icon").removeClass("fa-sort-up fa-sort-down").addClass("fa-sort");

    // Add active state to current sort column
    const activeHeader = $(`.sortable-header[data-sort="${this.sortField}"]`);
    activeHeader.addClass("active");

    if (this.sortDirection === "asc") {
      activeHeader.addClass("sort-asc");
      activeHeader
        .find(".sort-icon")
        .removeClass("fa-sort")
        .addClass("fa-sort-up");
    } else {
      activeHeader.addClass("sort-desc");
      activeHeader
        .find(".sort-icon")
        .removeClass("fa-sort")
        .addClass("fa-sort-down");
    }

    console.log("🔤 [updateSortIndicators] Visual indicators updated for:", {
      field: this.sortField,
      direction: this.sortDirection,
    });
  }
}

// Global functions
let transactionManager;

$(document).ready(() => {
  transactionManager = new TransactionManager();
});

async function deleteTransaction(id) {
  const confirmed = confirm(
    "⚠️ Delete this transaction? This action cannot be undone.",
  );
  if (!confirmed) return;

  try {
    const response = await fetch(`/transactions/${id}/delete/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": $("[name=csrfmiddlewaretoken]").val(),
      },
    });

    if (response.ok) {
      transactionManager.cache.clear();
      transactionManager.loadTransactions();
      transactionManager.loadTotals();
      transactionManager.showSuccess("Transaction deleted successfully");
    } else {
      throw new Error("Failed to delete transaction");
    }
  } catch (error) {
    transactionManager.showError("Failed to delete transaction");
  }
}

function syncPeriodFields(tr) {
  const dateInput = tr.querySelector("input[name='date']");
  const periodInput = tr.querySelector("input[name='period']");
  const periodDisplay = tr.querySelector("input[name='period_display']");

  if (!dateInput?.value) return;

  // Parse da data corretamente
  const dateParts = dateInput.value.split("-");
  if (dateParts.length !== 3) return;

  const yyyy = parseInt(dateParts[0]);
  const mm = String(parseInt(dateParts[1])).padStart(2, "00");
  const monthIndex = parseInt(dateParts[1]) - 1; // Month index para array (0-11)

  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  const monthName = monthNames[monthIndex];

  if (periodInput) {
    periodInput.value = `${yyyy}-${mm}`;
  }

  if (periodDisplay) {
    periodDisplay.value = `${monthName.charAt(0).toUpperCase() + monthName.slice(1)} ${yyyy}`;
  }

  console.log(
    `🔄 syncPeriodFields: Data ${dateInput.value} → Período ${yyyy}-${mm} (${monthName} ${yyyy})`,
  );
}

// Type mapping
const typeMapping = {
  IN: "Income",
  EX: "Expense",
  IV: "Investment",
  TR: "Transfer",
  AJ: "Adjustment",
};
