// Transactions 2.0 JavaScript - Advanced functionality
const DynamicCSS = (() => {
  let sheet;
  const created = new Set();

  function ensureSheet() {
    if (sheet) return sheet;
    let nonce = window.CSP_NONCE;
    if (!nonce) {
      const meta = document.querySelector('meta[name="csp-nonce"]');
      if (meta) nonce = meta.getAttribute('content');
    }
    if (!nonce) {
      const script = document.querySelector('script[nonce]');
      if (script) nonce = script.getAttribute('nonce');
    }
    const el = document.createElement('style');
    if (nonce) el.setAttribute('nonce', nonce);
    document.head.appendChild(el);
    sheet = el.sheet;
    return sheet;
  }

  function safeClassName(prop, value) {
    return `dyn-${prop.replace(/[^a-z]/gi, '')}-${String(value).replace(/[^a-z0-9_-]/gi, '')}`;
  }

  function classFor(prop, value, important = true) {
    const cn = safeClassName(prop, value);
    if (!created.has(cn)) {
      const rule = `.${cn}{${prop}:${value}${important ? ' !important' : ''};}`;
      ensureSheet().insertRule(rule, sheet.cssRules.length);
      created.add(cn);
    }
    return cn;
  }

  return { classFor };
})();

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (s) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[s]));
}

function readJsonScript(id, fallback = {}) {
  const payload = document.getElementById(id);
  if (!payload) {
    return fallback;
  }

  try {
    return JSON.parse(payload.textContent || "{}");
  } catch (error) {
    console.error(`[readJsonScript] Failed to parse ${id}`, error);
    return fallback;
  }
}

function buildFallbackTransactionListDefaults() {
  const today = new Date();
  return {
    date_start: `${today.getFullYear() - 2}-01-01`,
    date_end: today.toISOString().split("T")[0],
  };
}

const TRANSACTION_TYPE_CODE_TO_LABEL = {
  IN: "Income",
  EX: "Expense",
  IV: "Investment",
  TR: "Transfer",
  AJ: "Adjustment",
};

const TRANSACTION_TYPE_LABEL_TO_CODE = Object.fromEntries(
  Object.entries(TRANSACTION_TYPE_CODE_TO_LABEL).map(([code, label]) => [
    label,
    code,
  ]),
);

const FILTER_FIELD_SELECTORS = {
  date_start: "#date-start",
  date_end: "#date-end",
  type: "#filter-type",
  account: "#filter-account",
  category: "#filter-category",
  period: "#filter-period",
  amount_min: "#filter-amount-min",
  amount_max: "#filter-amount-max",
  tags: "#filter-tags",
  search: "#global-search",
};

const NON_ACTIVE_FILTER_KEYS = new Set([
  "page",
  "page_size",
  "sort_field",
  "sort_direction",
  "include_system",
]);

class TransactionManager {
  constructor() {
    console.log("🚀 [TransactionManager] Initializing Transaction Manager...");
    this.filterDefaults = readJsonScript(
      "transaction-list-defaults",
      buildFallbackTransactionListDefaults(),
    );
    this.currentPage = 1;
    this.pageSize = 25;
    this.totalRecords = 0;
    this.filters = {};
    this.cache = new Map();
    this.selectedRows = new Set();
    this.bulkMode = false;
    this.maxPageSize = 1000; // Maximum safety limit

    this.groupBy = 'none';
    this.lastData = null;

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
    const hasInitialFilters = this.loadInitialFiltersFromPage();
    if (hasInitialFilters) {
      this.saveFiltersToStorage();
    }
    console.log("💾 [init] Filters loaded from storage");

    this.showFilterFeedback();
    this.bindEvents();
    console.log("🔗 [init] Event listeners connected");

    if (window.innerWidth < 992) {
      this.groupBy = 'category';
      $('#group-by-selector').val('category');
    }

    const forceInitialRefresh = window.transactionListShouldForceRefresh === true;
    if (forceInitialRefresh) {
      this.cache.clear();
      console.log("[init] Forcing one fresh reload after transaction changes");
    }

    this.loadTransactions(forceInitialRefresh);
    this.loadTotals(forceInitialRefresh);

    // Initialize sort indicators
    this.updateSortIndicators();

    // Initialize checkbox column as hidden (since bulk mode starts as false)
    $("#transactions-table thead th:first-child").addClass("d-none");

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
    const defaultDates = this.getDefaultDateRange();

    flatpickr("#date-start", {
      dateFormat: "Y-m-d",
      defaultDate: defaultDates.date_start,
      onChange: () => this.onFilterChange(),
    });

    flatpickr("#date-end", {
      dateFormat: "Y-m-d",
      defaultDate: defaultDates.date_end,
      onChange: () => this.onFilterChange(),
    });
  }

  getDefaultDateRange() {
    return {
      date_start:
        this.filterDefaults?.date_start ||
        buildFallbackTransactionListDefaults().date_start,
      date_end:
        this.filterDefaults?.date_end ||
        buildFallbackTransactionListDefaults().date_end,
    };
  }

  resetFiltersToDefaults() {
    const defaultDates = this.getDefaultDateRange();
    this.setDateFilterValue("#date-start", defaultDates.date_start);
    this.setDateFilterValue("#date-end", defaultDates.date_end);
    $("#filter-type, #filter-account, #filter-category, #filter-period").val("");
    $("#filter-amount-min, #filter-amount-max, #filter-tags, #global-search").val("");
  }

  getFilterElement(key) {
    const selector = FILTER_FIELD_SELECTORS[key];
    if (!selector) {
      return $();
    }
    return $(selector);
  }

  ensureSelectOption(selector, value, label = value) {
    const element = $(selector);
    if (!element.length || !element.is("select") || value === "") {
      return;
    }

    const normalizedValue = String(value);
    const hasOption =
      element.find("option").filter((_index, option) => option.value === normalizedValue)
        .length > 0;

    if (!hasOption) {
      element.append(new Option(label, normalizedValue, false, false));
    }
  }

  applyFilterState(filters) {
    if (!filters || typeof filters !== "object") {
      return false;
    }

    let applied = false;

    Object.entries(filters).forEach(([key, rawValue]) => {
      if (rawValue === "" || rawValue === null || rawValue === undefined) {
        return;
      }

      if (key === "page") {
        const parsedPage = parseInt(rawValue, 10);
        if (!Number.isNaN(parsedPage) && parsedPage > 0) {
          this.currentPage = parsedPage;
          applied = true;
        }
        return;
      }

      if (key === "page_size") {
        const parsedSize = parseInt(rawValue, 10);
        if (String(rawValue) === "all" || (!Number.isNaN(parsedSize) && parsedSize >= this.maxPageSize)) {
          this.pageSize = this.maxPageSize;
          $("#page-size-selector").val("all");
          applied = true;
          return;
        }

        if (!Number.isNaN(parsedSize) && parsedSize > 0) {
          this.pageSize = parsedSize;
          $("#page-size-selector").val(String(parsedSize));
          applied = true;
        }
        return;
      }

      if (key === "sort_field") {
        this.sortField = String(rawValue);
        applied = true;
        return;
      }

      if (key === "sort_direction") {
        this.sortDirection = String(rawValue).toLowerCase() === "asc" ? "asc" : "desc";
        applied = true;
        return;
      }

      const element = this.getFilterElement(key);
      if (!element.length) {
        return;
      }

      let value = String(rawValue);
      if (key === "type") {
        value = TRANSACTION_TYPE_CODE_TO_LABEL[value] || value;
      }

      if (key === "date_start" || key === "date_end") {
        this.setDateFilterValue(FILTER_FIELD_SELECTORS[key], value);
        applied = true;
        return;
      }

      if (element.is("select")) {
        this.ensureSelectOption(FILTER_FIELD_SELECTORS[key], value);
      }

      element.val(value);
      applied = true;
    });

    return applied;
  }

  loadInitialFiltersFromPage() {
    const payload = document.getElementById("transaction-list-initial-filters");
    if (!payload) {
      return false;
    }

    try {
      const filters = JSON.parse(payload.textContent || "{}");
      return this.applyFilterState(filters);
    } catch (error) {
      console.error("[loadInitialFiltersFromPage] Failed to parse initial filters", error);
      return false;
    }
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
    $("#filter-form").on("submit", (e) => {
      e.preventDefault();
      this.onFilterChange();
    });

    // Page size selector
    $("#page-size-selector").on("change", (e) =>
      this.changePageSize(e.target.value),
    );

    $("#group-by-selector").on("change", (e) => {
      this.groupBy = e.target.value;
      if (this.lastData) {
        this.renderTransactions(this.lastData);
      }
    });

    // Buttons
    $("#apply-filters-btn").on("click", (e) => {
      e.preventDefault();
      this.onFilterChange();
    });
    $("#clear-filters-btn").on("click", () => this.clearFilters());
    $("#refresh-btn").on("click", () => this.refreshData());

    $("#export-btn").on("click", () => this.exportData());
    $("#import-btn").on("click", () => this.importData());

    $("#pagination-ul").on("click", ".page-link[data-page]", (e) => {
      e.preventDefault();
      const page = Number(e.currentTarget.dataset.page);
      if (!Number.isNaN(page)) {
        this.goToPage(page);
      }
    });

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
    $(document).on("click", "[data-action='edit-transaction']", (e) => {
      const id = Number(e.currentTarget.dataset.transactionId);
      if (!Number.isNaN(id)) {
        this.logEditNavigation(id);
      }
    });
    $(document).on("click", "[data-action='delete-transaction']", (e) => {
      e.preventDefault();
      const id = Number(e.currentTarget.dataset.transactionId);
      if (!Number.isNaN(id)) {
        deleteTransaction(id);
      }
    });

    // Initialize collapse state tracking with timing controls
    this.collapseStates = {
      mainFilters: false,
      advancedFilters: false,
      mainFiltersProcessing: false,
      advancedFiltersProcessing: false
    };

    // Main filters collapse handlers - with robust event control
    $('#filtersCollapse').on('show.bs.collapse', (e) => {
      e.stopPropagation();
      if (this.collapseStates.mainFiltersProcessing) {
        console.log('🚧 Main filters already processing, skipping...');
        return false;
      }
      
      this.collapseStates.mainFiltersProcessing = true;
      this.collapseStates.mainFilters = true;
      
      $('#filters-chevron').removeClass('fa-chevron-down').addClass('fa-chevron-up');
      $('#filters-toggle').attr('aria-expanded', 'true');
      console.log('🔄 Main filters expanding...');
      
      // Release processing lock after animation
      setTimeout(() => {
        this.collapseStates.mainFiltersProcessing = false;
      }, 100);
    });
    
    $('#filtersCollapse').on('shown.bs.collapse', (e) => {
      e.stopPropagation();
      console.log('✅ Main filters opened');
    });
    
    $('#filtersCollapse').on('hide.bs.collapse', (e) => {
      e.stopPropagation();
      if (this.collapseStates.mainFiltersProcessing) {
        console.log('🚧 Main filters already processing, skipping...');
        return false;
      }
      
      this.collapseStates.mainFiltersProcessing = true;
      this.collapseStates.mainFilters = false;
      
      $('#filters-chevron').removeClass('fa-chevron-up').addClass('fa-chevron-down');
      $('#filters-toggle').attr('aria-expanded', 'false');
      console.log('🔄 Main filters collapsing...');
      
      // Release processing lock after animation
      setTimeout(() => {
        this.collapseStates.mainFiltersProcessing = false;
      }, 100);
    });
    
    $('#filtersCollapse').on('hidden.bs.collapse', (e) => {
      e.stopPropagation();
      console.log('✅ Main filters closed');
    });

    // Advanced filters collapse handlers - with robust event control
    $('#advancedFilters').on('show.bs.collapse', (e) => {
      e.stopPropagation();
      if (this.collapseStates.advancedFiltersProcessing) {
        console.log('🚧 Advanced filters already processing, skipping...');
        return false;
      }
      
      this.collapseStates.advancedFiltersProcessing = true;
      this.collapseStates.advancedFilters = true;
      
      $('#advanced-chevron').removeClass('fa-chevron-down').addClass('fa-chevron-up');
      $('#advanced-filters-toggle').attr('aria-expanded', 'true');
      console.log('🔄 Advanced filters expanding...');
      
      // Release processing lock after animation
      setTimeout(() => {
        this.collapseStates.advancedFiltersProcessing = false;
      }, 100);
    });
    
    $('#advancedFilters').on('shown.bs.collapse', (e) => {
      e.stopPropagation();
      console.log('✅ Advanced filters opened');
    });
    
    $('#advancedFilters').on('hide.bs.collapse', (e) => {
      e.stopPropagation();
      if (this.collapseStates.advancedFiltersProcessing) {
        console.log('🚧 Advanced filters already processing, skipping...');
        return false;
      }
      
      this.collapseStates.advancedFiltersProcessing = true;
      this.collapseStates.advancedFilters = false;
      
      $('#advanced-chevron').removeClass('fa-chevron-up').addClass('fa-chevron-down');
      $('#advanced-filters-toggle').attr('aria-expanded', 'false');
      console.log('🔄 Advanced filters collapsing...');
      
      // Release processing lock after animation
      setTimeout(() => {
        this.collapseStates.advancedFiltersProcessing = false;
      }, 100);
    });
    
    $('#advancedFilters').on('hidden.bs.collapse', (e) => {
      e.stopPropagation();
      console.log('✅ Advanced filters closed');
    });

    // Initialize collapse states properly after DOM is ready
    this.initializeCollapseStates();
  }

  initializeCollapseStates() {
    // Wait for DOM to be fully ready before checking states
    setTimeout(() => {
      // Set initial states without triggering events
      const mainFiltersOpen = $('#filtersCollapse').hasClass('show');
      const advancedFiltersOpen = $('#advancedFilters').hasClass('show');
      
      // Initialize the state tracking variables
      this.collapseStates.mainFilters = mainFiltersOpen;
      this.collapseStates.advancedFilters = advancedFiltersOpen;
      
      console.log('🔧 Initializing collapse states:', {
        mainFilters: mainFiltersOpen,
        advancedFilters: advancedFiltersOpen
      });
      
      // Set main filters chevron and aria attributes
      const filtersToggle = $('#filters-toggle');
      const filtersChevron = $('#filters-chevron');
      
      if (mainFiltersOpen) {
        filtersChevron.removeClass('fa-chevron-down').addClass('fa-chevron-up');
        filtersToggle.attr('aria-expanded', 'true');
      } else {
        filtersChevron.removeClass('fa-chevron-up').addClass('fa-chevron-down');
        filtersToggle.attr('aria-expanded', 'false');
      }
      
      // Set advanced filters chevron and aria attributes
      const advancedToggle = $('#advanced-filters-toggle');
      const advancedChevron = $('#advanced-chevron');
      
      if (advancedFiltersOpen) {
        advancedChevron.removeClass('fa-chevron-down').addClass('fa-chevron-up');
        advancedToggle.attr('aria-expanded', 'true');
      } else {
        advancedChevron.removeClass('fa-chevron-up').addClass('fa-chevron-down');
        advancedToggle.attr('aria-expanded', 'false');
      }
      
      console.log('✅ Collapse states initialized with proper state tracking');
    }, 100);
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

    
    console.log("🔧 DOM ELEMENT VALUES:");
    console.table({
      dateStart: $("#date-start").val(),
      dateEnd: $("#date-end").val(),
      type: $("#filter-type").val(),
      typeMapped:
        TRANSACTION_TYPE_LABEL_TO_CODE[$("#filter-type").val()] || $("#filter-type").val(),
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

  isDefaultFilterValue(key, value) {
    const defaultDates = this.getDefaultDateRange();
    if (key === "date_start") {
      return value === defaultDates.date_start;
    }
    if (key === "date_end") {
      return value === defaultDates.date_end;
    }
    return false;
  }

  showFilterFeedback() {
    // Add visual feedback to show filters are active (Excel-style)
    const filters = this.getFilters();
    const activeFilters = Object.keys(filters).filter((key) => {
      return (
        !NON_ACTIVE_FILTER_KEYS.has(key) &&
        filters[key] &&
        filters[key] !== "" &&
        !this.isDefaultFilterValue(key, filters[key])
      );
    });
    
    const countElement = $("#active-filters-count");
    const collapseButton = $('[data-bs-target="#filtersCollapse"]');
    const chevron = collapseButton.find('.fa-chevron-down, .fa-chevron-up');

    if (activeFilters.length > 0) {
      countElement.text(`${activeFilters.length} active filter${activeFilters.length > 1 ? 's' : ''}`);
      countElement.removeClass('text-muted').addClass('text-primary fw-bold');
    } else {
      countElement.text('No active filters');
      countElement.removeClass('text-primary fw-bold').addClass('text-muted');
    }

    // Update collapse button chevron based on actual state
    const isCollapsed = !$('#filtersCollapse').hasClass('show');
    const filtersChevron = $('#filters-chevron');
    if (isCollapsed) {
      filtersChevron.removeClass('fa-chevron-up').addClass('fa-chevron-down');
      $('#filters-toggle').attr('aria-expanded', 'false');
    } else {
      filtersChevron.removeClass('fa-chevron-down').addClass('fa-chevron-up');
      $('#filters-toggle').attr('aria-expanded', 'true');
    }
  }

  getFilters() {
    const selectedType = $("#filter-type").val();
    const mappedType =
      TRANSACTION_TYPE_LABEL_TO_CODE[selectedType] || selectedType;

    const filters = {
      date_start: $("#date-start").val(),
      date_end: $("#date-end").val(),
      type: mappedType,
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
      include_system: true,
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
    cleanFilters.include_system = true;

    return cleanFilters;
  }

  buildQueryParams(filters, extraParams = {}) {
    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) {
        params.append(key, value);
      }
    });

    Object.entries(extraParams).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) {
        params.append(key, value);
      }
    });

    return params;
  }

  getTotalsFilters(force = false) {
    const totalsFilters = { ...this.getFilters() };
    delete totalsFilters.page;
    delete totalsFilters.page_size;
    delete totalsFilters.sort_field;
    delete totalsFilters.sort_direction;

    if (force) {
      totalsFilters.force = true;
    }

    return totalsFilters;
  }

  saveFiltersToStorage() {
    const filters = this.getFilters();
    sessionStorage.setItem("transaction_filters_v2", JSON.stringify(filters));
  }

  loadFiltersFromStorage() {
    const saved = sessionStorage.getItem("transaction_filters_v2");
    if (!saved) {
      return false;
    }

    try {
      const filters = JSON.parse(saved);
      return this.applyFilterState(filters);
    } catch (error) {
      console.error("[loadFiltersFromStorage] Failed to parse saved filters", error);
      sessionStorage.removeItem("transaction_filters_v2");
      return false;
    }
  }

  logEditNavigation(id) {
    console.info("[edit-transaction] Navigating to edit", {
      id,
      currentPage: this.currentPage,
      totalCount: this.totalCount || 0,
      visibleRows: this.transactions ? this.transactions.length : 0,
      sortField: this.sortField,
      sortDirection: this.sortDirection,
      filters: this.getFilters(),
      hasLastData: !!this.lastData,
    });
  }

  clearFilters() {
    this.resetFiltersToDefaults();
    sessionStorage.removeItem("transaction_filters_v2");
    this.currentPage = 1;
    this.cache.clear(); // Clear cache when clearing filters
    this.showFilterFeedback();
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

  async loadTransactions(force = false) {
    console.log("🔄 [loadTransactions] LOADING START");

    try {
      this.showLoader(true);

      const filters = this.getFilters();
      const params = this.buildQueryParams(
        filters,
        force ? { force: "true", _ts: Date.now().toString() } : {},
      );
      const url = `/transactions/json-v2/?${params.toString()}`;
      console.log("🌐 [loadTransactions] Request URL:", url);

      const response = await fetch(url, {
        method: "GET",
        cache: force ? "no-store" : "default",
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
      this.lastData = data;

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

  async loadTotals(force = false) {
    console.log("💰 [loadTotals] Starting totals load...");
    try {
      const totalsFilters = this.getTotalsFilters(force);
      
      
      console.log("🔍 [loadTotals] Filters for totals (cleaned):", totalsFilters);

      const csrfToken =
        document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
        getCookie("csrftoken");

      const response = await fetch("/transactions/totals-v2/", {
        method: "POST",
        cache: force ? "no-store" : "default",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(totalsFilters),
      });

      console.log(
        "📡 [loadTotals] Totals response received, status:",
        response.status,
      );

      if (!response.ok) throw new Error("Failed to load totals");

      const totals = await response.json();
      console.log("📊 [loadTotals] Totals received:", totals);

      this.renderTotals(totals);
      console.log(
        "✅ [loadTotals] Totals loaded and rendered successfully",
      );
    } catch (error) {
      console.error("❌ [loadTotals] Error loading totals:", error);
    }
  }

  renderTransactions(data) {
    console.group("🎨 [renderTransactions] RENDERING STARTED");
    console.log("Timestamp:", new Date().toISOString());

    this.lastData = data;

    console.log("📋 DATA VALIDATION:");
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
    console.log("🗂️ DOM - Rows before clearing:", currentRowCount);
    console.log("🗂️ DOM - Element exists:", tbody.length > 0);

    tbody.empty();
    console.log("🧹 Table cleared");

    if (!data || !data.transactions || data.transactions.length === 0) {
      console.warn("⚠️ No transactions - displaying empty message");
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

    console.log("✏️ CREATING", data.transactions.length, "TABLE ROWS");

    const transactions = data.transactions.slice();

    if (this.groupBy && this.groupBy !== 'none') {
      const groups = new Map();
      transactions.forEach((tx) => {
        const key = this.getGroupKey(tx);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(tx);
      });

      const sorted = Array.from(groups.entries()).sort((a, b) =>
        a[0].localeCompare(b[0])
      );

      sorted.forEach(([key, items]) => {
        const total = items.reduce(
          (sum, t) => sum + parseFloat(t.amount),
          0
        );
        const header = this.createGroupHeader(key, items.length, total);
        tbody.append(header);
        items.forEach((tx, idx) => {
          try {
            const row = this.createTransactionRow(tx, idx);
            tbody.append(row);
          } catch (error) {
            console.error(`❌ Error creating row:`, error);
          }
        });
      });

      this.finishRendering(data);
      return;
    }

    // Performance optimization for large datasets
    const batchSize = 50;

    if (transactions.length > batchSize) {
      // Render in batches for better performance
      console.log(
        `📊 [renderTransactions] Batch rendering: ${transactions.length} transactions, batches of ${batchSize}`,
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
              `❌ Error creating row ${index + batchIndex + 1}:`,
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
          console.error(`❌ Error creating row ${index + 1}:`, error);
        }
      });

      this.finishRendering(data);
    }
  }

  finishRendering(data) {
    const finalRowCount = $("#transactions-tbody tr").length;
    console.log("📊 DOM - Final rows:", finalRowCount);

    this.totalRecords = data.total_count;
    this.updatePagination(data.total_count, data.current_page);

    const showingAll = this.pageSize >= data.total_count;
    const countMessage = showingAll
      ? `All ${data.total_count} transactions shown`
      : `${data.total_count} transactions found (showing ${data.transactions.length} on this page)`;

    $("#total-count").text(countMessage);
    console.log("📊 Count message set:", countMessage);
    console.log("✅ RENDERING COMPLETED");
    this.checkInlineStyles();
    console.groupEnd();
  }

  checkInlineStyles() {
    const container = document.getElementById("transactions-table");
    if (!container) return;
    const styled = container.querySelectorAll("[style]");
    if (styled.length > 0) {
      console.warn("[CSP] Inline styles detected:", styled);
    }
  }

  createTransactionRow(tx, index) {
    const isSelected = this.selectedRows.has(tx.id);

    // Style for system transactions and estimated transactions
    const isSystemRow = tx.is_system;
    const isEstimatedRow = tx.is_estimated;
    const rowClass = isSystemRow ? "table-warning" : "";
    let systemBadge = "";

    if (isSystemRow) {
      systemBadge = '<span class="badge bg-info ms-1" title="Automatically calculated">AUTO</span>';
    } else if (isEstimatedRow) {
      systemBadge = '<span class="badge bg-warning ms-1" title="Estimated transaction - edit via /transactions/estimate/">EST</span>';
    }

    // Format type with colored badge
    const getTypeBadge = (type) => {
      const typeClasses = {
        'Income': 'type-badge type-income',
        'Expense': 'type-badge type-expense',
        'Investment': 'type-badge type-investment',
        'Transfer': 'type-badge type-transfer'
      };
      const className = typeClasses[type] || 'type-badge';
      return `<span class="${className}">${this.getTypeIcon(type)} ${escapeHtml(type)}</span>`;
    };

    // Format amount with proper styling
    const formatAmount = (amount, type) => {
      // For investments, determine color based on actual amount value
      let amountClass = 'amount-neutral';
      
      if (type === 'Income') {
        amountClass = 'amount-positive';
      } else if (type === 'Expense') {
        amountClass = 'amount-negative';
      } else if (type === 'Investment') {
        // For investments, check if the original amount is positive or negative
        const numAmount = parseFloat(tx.amount);
        amountClass = numAmount >= 0 ? 'amount-positive' : 'amount-negative';
      }
      
      return `<span class="transaction-amount ${amountClass}">${escapeHtml(tx.amount_formatted)}</span>`;
    };

    // Format category as pill
    const formatCategory = (category) => {
      if (!category || category === '') return '<span class="text-muted">-</span>';
      const safe = escapeHtml(category);
      return `<span class="category-pill" title="${safe}">${safe}</span>`;
    };

    // Format account as pill
    const formatAccount = (account) => {
      if (!account || account === 'No account') return '<span class="text-muted">-</span>';
      const safe = escapeHtml(account);
      return `<span class="account-pill" title="${safe}">${safe}</span>`;
    };

    // Format tags as pills
    const formatTags = (tags) => {
      if (!tags || tags === '') return '<span class="text-muted">-</span>';
      
      const tagList = tags.split(', ').filter(tag => tag.trim());
      if (tagList.length === 0) return '<span class="text-muted">-</span>';

      const tagPills = tagList.slice(0, 2).map(tag => {
        const safe = escapeHtml(tag);
        return `<span class="tag-pill" title="${safe}">${safe}</span>`;
      }).join(' ');

      const moreCount = tagList.length - 2;
      const moreIndicator = moreCount > 0 ? `<span class="badge bg-secondary ms-1" title="${escapeHtml(tagList.slice(2).join(', '))}">+${moreCount}</span>` : '';
      
      return `<div class="tags-container">${tagPills}${moreIndicator}</div>`;
    };

    // Format date with better display
    const formatDate = (dateStr) => {
      const date = new Date(dateStr);
      const day = date.getDate().toString().padStart(2, '0');
      const month = (date.getMonth() + 1).toString().padStart(2, '0');
      const year = date.getFullYear().toString().substr(-2);
      return `<span class="text-nowrap">${escapeHtml(`${day}/${month}/${year}`)}</span>`;
    };

    // Handle actions based on transaction type and editability
    let actionsHtml = '';
    
    console.log(`🔍 [createTransactionRow] Transaction ${tx.id}: editable=${tx.editable}, is_estimated=${tx.is_estimated}, is_system=${tx.is_system}`);
    
    if (!tx.editable) {
      // System transactions - completely read only
      actionsHtml = `
        <div class="btn-group btn-group-sm">
          <button class="btn btn-outline-secondary btn-sm" disabled title="System transaction - read only">
            <i class="fas fa-lock"></i>
          </button>
        </div>
      `;
    } else if (tx.is_estimated === true || tx.is_estimated === 'true' || tx.is_estimated === 1) {
      // Estimated transactions - can delete but not edit directly
      console.log(`🧮 [createTransactionRow] Detected estimated transaction ${tx.id}`);
      actionsHtml = `
        <div class="btn-group btn-group-sm" role="group">
          <button class="btn btn-outline-secondary btn-sm" disabled title="Estimated transaction - edit via /transactions/estimate/">
            <i class="fas fa-calculator"></i>
          </button>
          <a href="/transactions/${tx.id}/delete/" class="btn btn-outline-danger btn-sm" data-action="delete-transaction" data-transaction-id="${tx.id}" title="Delete estimated transaction">
            <i class="fas fa-trash"></i>
          </a>
        </div>
      `;
    } else {
      // Regular transactions - full edit capabilities
      console.log(`✏️ [createTransactionRow] Regular editable transaction ${tx.id}`);
      actionsHtml = `
        <div class="btn-group btn-group-sm" role="group">
          <a href="/transactions/${tx.id}/edit/" class="btn btn-outline-primary btn-sm" data-action="edit-transaction" data-transaction-id="${tx.id}" title="Edit transaction">
            <i class="fas fa-edit"></i>
          </a>
          <a href="/transactions/${tx.id}/delete/" class="btn btn-outline-danger btn-sm" data-action="delete-transaction" data-transaction-id="${tx.id}" title="Delete transaction">
            <i class="fas fa-trash"></i>
          </a>
        </div>
      `;
    }

    // Sempre criar a coluna do checkbox, mas controlar visibilidade
    const checkboxClass = this.bulkMode ? "" : " d-none";

    const template = document.createElement('template');
    template.innerHTML = `
      <tr data-id="${tx.id}" class="${rowClass}">
        <td class="text-center${checkboxClass}">
          <input type="checkbox" class="form-check-input row-select" value="${tx.id}" ${isSelected ? "checked" : ""}>
        </td>
        <td class="text-nowrap">${formatDate(tx.date)}</td>
        <td class="d-none d-md-table-cell text-muted">${escapeHtml(tx.period)}</td>
        <td>${getTypeBadge(tx.type)}${systemBadge}</td>
        <td class="text-end">${formatAmount(tx.amount_formatted, tx.type)}</td>
        <td class="d-none d-lg-table-cell">${formatCategory(tx.category)}</td>
        <td class="d-none d-xl-table-cell">${formatTags(tx.tags)}</td>
        <td class="d-none d-md-table-cell">${formatAccount(tx.account)}</td>
        <td class="text-center">${actionsHtml}</td>
      </tr>
    `;
    const row = template.content.firstElementChild;
    row.querySelectorAll('[style]').forEach(el => el.removeAttribute('style'));
    return row;
  }

  createGroupHeader(name, count, total) {
    const template = document.createElement('template');
    const totalFormatted = parseFloat(total).toFixed(2);
    template.innerHTML = `
      <tr class="group-header d-lg-none">
        <td colspan="9">
          <div class="group-header-content">
            <span class="group-header-name">${escapeHtml(name)}</span>
            <span class="group-header-meta">${count} transactions · € ${totalFormatted}</span>
          </div>
        </td>
      </tr>`;
    const row = template.content.firstElementChild;
    row.querySelectorAll('[style]').forEach(el => el.removeAttribute('style'));
    return row;
  }

  getGroupKey(tx) {
    if (this.groupBy === 'category') {
      return tx.category || 'Uncategorized';
    }
    if (this.groupBy === 'month') {
      return tx.date ? tx.date.slice(0, 7) : 'Unknown';
    }
    if (this.groupBy === 'account') {
      return tx.account || 'No account';
    }
    if (this.groupBy === 'type') {
      return tx.type || 'No type';
    }
    if (this.groupBy === 'period') {
      return tx.period || 'No period';
    }
    return '';
  }

  getTypeIcon(type) {
    const icons = {
      'Expense': "💸",
      'Income': "💰", 
      'Investment': "📈",
      'Transfer': "🔁",
      'Adjustment': "🧮",
      'System adjustment': "🧮",
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

    // Update values with animation
    this.updateCardValue("#total-income", income, ".income-card");
    this.updateCardValue("#total-expenses", expenses, ".expense-card");
    this.updateCardValue("#total-investments", investments, ".investment-card");
    this.updateCardValue("#total-balance", balance, ".balance-card");

    // Handle negative balance styling
    const balanceCard = $(".balance-card");
    if (totals.balance < 0) {
      balanceCard.addClass("negative");
    } else {
      balanceCard.removeClass("negative");
    }

    console.log("✅ [renderTotals] Totais atualizados na interface");
  }

  updateCardValue(selector, newValue, cardSelector) {
    const element = $(selector);
    const card = $(cardSelector);
    
    // Only animate if value has changed
    if (element.text() !== newValue) {
      // Add updated animation class
      card.addClass("updated");
      
      // Update the value
      element.text(newValue);
      
      // Remove animation class after animation completes
      setTimeout(() => {
        card.removeClass("updated");
      }, 600);
    } else {
      element.text(newValue);
    }
  }

  formatCurrency(amount) {
    // Use our custom Portuguese formatting for consistency
    return this.formatCurrencyPortuguese(amount);
  }

  formatCurrencyPortuguese(amount) {
    // Format number in Portuguese style: 1.234,56 €
    const isNegative = amount < 0;
    const absAmount = Math.abs(amount);

    // Convert to string with 2 decimals
    let formatted = absAmount.toFixed(2);
    
    // Split into integer and decimal parts
    const parts = formatted.split('.');
    const integerPart = parts[0];
    const decimalPart = parts[1];
    
    // Add thousands separators (dots) to integer part
    const withThousands = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    
    // Combine with comma as decimal separator
    const finalFormatted = `${withThousands},${decimalPart}`;

    return `${isNegative ? "-" : ""}${finalFormatted} €`;
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
      "🔧 [updateFilterOptions] Updating filter options (Excel-style)",
    );
    if (!filters) {
      console.warn("⚠️ [updateFilterOptions] No filter data received");
      return;
    }

    console.log(
      "📝 [updateFilterOptions] Available filters (only with visible transactions):",
      {
        types: filters.types?.length || 0,
        categories: filters.categories?.length || 0,
        accounts: filters.accounts?.length || 0,
        periods: filters.periods?.length || 0,
      },
    );

    console.log("📋 [updateFilterOptions] Filter details:", {
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
      "✅ [updateFilterOptions] Filter options updated (Excel-style)",
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
      `🔧 [updateSelectOptions] Updating ${filterType} - current value: '${currentValue}', available options:`,
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
        `🔄 [updateSelectOptions] Filter ${filterType} reset - value '${currentValue}' not present in filtered data (Excel-style)`,
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
        `✅ [updateSelectOptions] Filter ${filterType} kept - value '${currentValue}' exists in filtered data`,
      );
    }

    console.log(
      `📋 [updateSelectOptions] ${filterType}: ${options.length} options available (Excel-style)`,
    );
  }

  changePageSize(newSize) {
    console.log(`📄 [changePageSize] Changing page size to: ${newSize}`);

    if (newSize === "all") {
      // For "all", use a very high number but limit for safety
      this.pageSize = Math.min(
        this.totalRecords || this.maxPageSize,
        this.maxPageSize,
      );
      console.log(
        `📄 [changePageSize] Page size "all" set to: ${this.pageSize}`,
      );
    } else {
      this.pageSize = parseInt(newSize);
      console.log(`📄 [changePageSize] Numeric page size: ${this.pageSize}`);
    }

    // Reset to first page when changing size
    this.currentPage = 1;

    // Clear cache because pagination changed
    this.cache.clear();
    console.log(
      `📄 [changePageSize] Cache cleared due to page size change`,
    );

    // Reload transactions
    this.loadTransactions();

    // Save preference to localStorage
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

    // If showing all transactions, hide pagination
    if (this.pageSize >= totalRecords) {
      $("#pagination-nav").addClass("is-hidden");
      return;
    }

    $("#pagination-nav").removeClass("is-hidden");

    if (totalPages <= 1) return;

    // Previous button
    paginationUl.append(`
      <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
        <button type="button" class="page-link" data-page="${currentPage - 1}" ${currentPage === 1 ? "disabled" : ""}>
          <i class="fas fa-chevron-left"></i> Previous
        </button>
      </li>
    `);

    // First page
    if (currentPage > 3) {
      paginationUl.append(`
        <li class="page-item">
          <button type="button" class="page-link" data-page="1">1</button>
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
          <button type="button" class="page-link" data-page="${i}" ${i === currentPage ? "disabled" : ""}>${i}</button>
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
          <button type="button" class="page-link" data-page="${totalPages}">${totalPages}</button>
        </li>
      `);
    }

    // Next button
    paginationUl.append(`
      <li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
        <button type="button" class="page-link" data-page="${currentPage + 1}" ${currentPage === totalPages ? "disabled" : ""}>
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
    $("#select-all").toggleClass("is-hidden", !enabled);
    $("#bulk-actions").toggleClass("d-none", !enabled);

    // Show/hide the entire checkbox column in the header
    const checkboxHeader = $("#transactions-table thead th:first-child");
    if (enabled) {
      checkboxHeader.removeClass("d-none");
    } else {
      checkboxHeader.addClass("d-none");
    }

    // Show/hide all cells of the first column in the tbody
    $("#transactions-tbody tr").each(function () {
      const firstCell = $(this).find("td:first-child");
      if (enabled) {
        firstCell.removeClass("d-none");
      } else {
        firstCell.addClass("d-none");
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
        await this.loadTransactions(true);
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

    const targetPeriod = await this.promptDuplicateTargetPeriod();
    if (!targetPeriod) return;

    // Show simple loading indicator
    this.showLoading(true);
    const loadingToast = this.showToast(
      `Duplicating ${this.selectedRows.size} transactions to ${targetPeriod}...`,
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
          target_period: targetPeriod,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to duplicate transactions");
      }

      const result = await response.json();
      const endTime = performance.now();
      const duration = ((endTime - startTime) / 1000).toFixed(1);

      const adjustedFilters = this.adjustFiltersForDuplicatedPeriod(targetPeriod);

      // Clear cache and reload data
      this.cache.clear();
      this.selectedRows.clear();
      this.updateSelectionCount();
      this.saveFiltersToStorage();
      await Promise.all([this.loadTransactions(true), this.loadTotals(true)]);

      // Hide loading toast
      if (loadingToast) loadingToast.remove();

      this.showSuccess(
        `${result.created} transactions duplicated successfully in ${duration}s${
          adjustedFilters ? ` (showing ${targetPeriod})` : ""
        }`,
      );
    } catch (error) {
      console.error("Bulk duplicate error:", error);
      if (loadingToast) loadingToast.remove();
      this.showError(`❌ Failed to duplicate transactions: ${error.message}`);
    } finally {
      this.showLoading(false);
    }
  }

  getDefaultDuplicatePeriod() {
    const selectedPeriod = String($("#filter-period").val() || "").trim();
    if (/^\d{4}-(0[1-9]|1[0-2])$/.test(selectedPeriod)) {
      return selectedPeriod;
    }

    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  }

  setDateFilterValue(selector, value) {
    const input = document.querySelector(selector);
    if (!input) return;

    if (input._flatpickr) {
      input._flatpickr.setDate(value, false);
      return;
    }

    $(input).val(value);
  }

  getPeriodBounds(periodValue) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(periodValue)) {
      return null;
    }

    const [yearText, monthText] = periodValue.split("-");
    const year = Number(yearText);
    const month = Number(monthText);
    const lastDay = new Date(year, month, 0).getDate();

    return {
      start: `${periodValue}-01`,
      end: `${periodValue}-${String(lastDay).padStart(2, "0")}`,
    };
  }

  adjustFiltersForDuplicatedPeriod(targetPeriod) {
    const bounds = this.getPeriodBounds(targetPeriod);
    if (!bounds) return false;

    let changed = false;
    const currentStart = String($("#date-start").val() || "").trim();
    const currentEnd = String($("#date-end").val() || "").trim();
    const currentPeriod = String($("#filter-period").val() || "").trim();

    if (!currentStart || currentStart > bounds.start) {
      this.setDateFilterValue("#date-start", bounds.start);
      changed = true;
    }

    if (!currentEnd || currentEnd < bounds.end) {
      this.setDateFilterValue("#date-end", bounds.end);
      changed = true;
    }

    if (currentPeriod && currentPeriod !== targetPeriod) {
      $("#filter-period").val(targetPeriod);
      changed = true;
    }

    return changed;
  }

  promptDuplicateTargetPeriod() {
    const modalElement = document.getElementById("duplicateMonthModal");
    const formElement = document.getElementById("duplicate-month-form");
    const inputElement = document.getElementById("duplicate-target-month");
    const countElement = document.getElementById("duplicate-selection-count");

    if (
      !modalElement ||
      !formElement ||
      !inputElement ||
      typeof bootstrap === "undefined" ||
      !bootstrap.Modal
    ) {
      const value = window.prompt(
        "Which month should the duplicated transactions go to? Use YYYY-MM.",
        this.getDefaultDuplicatePeriod(),
      );
      if (value && /^\d{4}-(0[1-9]|1[0-2])$/.test(value.trim())) {
        return Promise.resolve(value.trim());
      }
      return Promise.resolve(null);
    }

    inputElement.value = this.getDefaultDuplicatePeriod();
    if (countElement) {
      countElement.textContent = this.selectedRows.size;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    return new Promise((resolve) => {
      let settled = false;

      const cleanup = () => {
        formElement.removeEventListener("submit", handleSubmit);
        modalElement.removeEventListener("hidden.bs.modal", handleHidden);
      };

      const finish = (value) => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(value);
      };

      const handleSubmit = (event) => {
        event.preventDefault();
        if (!inputElement.value) {
          inputElement.reportValidity();
          return;
        }

        finish(inputElement.value);
        modal.hide();
      };

      const handleHidden = () => {
        finish(null);
      };

      formElement.addEventListener("submit", handleSubmit);
      modalElement.addEventListener("hidden.bs.modal", handleHidden);

      modal.show();
      setTimeout(() => inputElement.focus(), 150);
    });
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
      await Promise.all([this.loadTransactions(true), this.loadTotals(true)]);

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

  async refreshData() {
    try {
      console.log("🔄 [refreshData] Refreshing data...");

      const response = await fetch(`/transactions/clear-cache/?_ts=${Date.now()}`, {
        method: "GET",
        cache: "no-store",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken":
            $("[name=csrfmiddlewaretoken]").val() || window.csrfToken || "",
        },
      });

      console.log("📡 [refreshData] Response status:", response.status);

      if (response.ok) {
        const result = await response.json();
        console.log("📋 [refreshData] Server response:", result);

        if (result.success) {
          // Clear local cache
          this.cache.clear();
          console.log("🗑️ [refreshData] Local cache cleared");

          // Reload both transactions and totals, forcing fresh queries
          await Promise.all([
            this.loadTransactions(true),
            this.loadTotals(true),
          ]);

          this.showSuccess("✅ Data refreshed successfully!");
          console.log("✅ [refreshData] Operation completed successfully");
        } else {
          throw new Error(result.error || "Unknown error occurred");
        }
      } else {
        const errorData = await response.json();
        console.error("❌ [refreshData] Server response error:", errorData);
        throw new Error(
          errorData.error || `HTTP ${response.status}: ${response.statusText}`,
        );
      }
    } catch (error) {
      console.error("❌ [refreshData] Error:", error);
      this.showError(`Failed to refresh data: ${error.message}`);
    }
  }

  exportData() {
    const filters = this.getFilters();
    const params = this.buildQueryParams(filters);
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
    const offset = document.querySelectorAll('.toast').length * 80;
    const offsetClass = DynamicCSS.classFor('top', `${offset}px`);
    const toast = $(`
      <div class="toast position-fixed ${offsetClass} end-0 m-3 toast-high" id="${toastId}">
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
      toast.toast({ autohide: false }).toast("show");
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
              <div class="progress mb-3 h-25">
                <progress id="bulk-progress-bar" class="w-100" value="0" max="100"></progress>
                <div id="progress-text">0%</div>
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
      progressBar.attr("value", percent);
      progressText.text(percent + "%");
      progressMessage.text(message);

      if (percent >= 100) {
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
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": $("[name=csrfmiddlewaretoken]").val(),
      },
    });

    if (response.ok) {
      transactionManager.selectedRows.delete(id);
      transactionManager.updateSelectionCount();
      transactionManager.cache.clear();
      transactionManager.loadTransactions(true);
      transactionManager.loadTotals(true);
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
    `🔄 syncPeriodFields: Date ${dateInput.value} → Period ${yyyy}-${mm} (${monthName} ${yyyy})`,
  );
}

// Function to get CSRF token from cookies
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Type mapping
const typeMapping = {
  IN: "Income",
  EX: "Expense",
  IV: "Investment",
  TR: "Transfer",
  AJ: "Adjustment",
};
