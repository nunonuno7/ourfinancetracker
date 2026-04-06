(function initializeTransactionListStateUtils(global) {
  const STORAGE_KEY = "transaction_filters_v2";

  function isBlank(value) {
    return value === "" || value === null || value === undefined;
  }

  function shouldLogDebug() {
    return global.DEBUG_TRANSACTIONS === true;
  }

  function callConsole(method, args, { always = false } = {}) {
    if (!always && !shouldLogDebug()) {
      return;
    }

    if (!global.console || typeof global.console[method] !== "function") {
      return;
    }

    global.console[method].call(global.console, ...args);
  }

  function createLogger() {
    const api = {
      log(...args) {
        callConsole("log", args);
      },
      info(...args) {
        callConsole("info", args);
      },
      warn(...args) {
        callConsole("warn", args, { always: true });
      },
      error(...args) {
        callConsole("error", args, { always: true });
      },
      table(...args) {
        callConsole("table", args);
      },
      group(...args) {
        callConsole("group", args);
      },
      groupEnd(...args) {
        callConsole("groupEnd", args);
      },
    };

    api.consoleProxy = {
      log: (...args) => api.log(...args),
      info: (...args) => api.info(...args),
      warn: (...args) => api.warn(...args),
      error: (...args) => api.error(...args),
      table: (...args) => api.table(...args),
      group: (...args) => api.group(...args),
      groupEnd: (...args) => api.groupEnd(...args),
    };

    return api;
  }

  function buildFilters({
    currentPage,
    pageSize,
    sortField,
    sortDirection,
    filterSelectors,
    typeLabelToCode,
  }) {
    const selectedType = $(filterSelectors.type).val();
    const mappedType = typeLabelToCode[selectedType] || selectedType;
    const filters = {
      date_start: $(filterSelectors.date_start).val(),
      date_end: $(filterSelectors.date_end).val(),
      type: mappedType,
      account_id: $(filterSelectors.account_id).val(),
      category_id: $(filterSelectors.category_id).val(),
      period: $(filterSelectors.period).val(),
      amount_min: $(filterSelectors.amount_min).val(),
      amount_max: $(filterSelectors.amount_max).val(),
      tags: $(filterSelectors.tags).val(),
      search: $(filterSelectors.search).val(),
      page: currentPage,
      page_size: pageSize,
      sort_field: sortField,
      sort_direction: sortDirection,
      include_system: true,
    };

    const cleanFilters = {};
    Object.entries(filters).forEach(([key, value]) => {
      if (!isBlank(value)) {
        cleanFilters[key] = value;
      }
    });

    cleanFilters.page = currentPage;
    cleanFilters.page_size = pageSize;
    cleanFilters.sort_field = sortField;
    cleanFilters.sort_direction = sortDirection;
    cleanFilters.include_system = true;

    return cleanFilters;
  }

  function buildTotalsFilters(filters, { force = false } = {}) {
    const totalsFilters = { ...filters };
    delete totalsFilters.page;
    delete totalsFilters.page_size;
    delete totalsFilters.sort_field;
    delete totalsFilters.sort_direction;

    if (force) {
      totalsFilters.force = true;
    }

    return totalsFilters;
  }

  function saveFilters(filters, storage = global.sessionStorage) {
    storage.setItem(STORAGE_KEY, JSON.stringify(filters));
  }

  function loadFilters(storage = global.sessionStorage) {
    const saved = storage.getItem(STORAGE_KEY);
    if (!saved) {
      return { filters: null, error: null };
    }

    try {
      return {
        filters: JSON.parse(saved),
        error: null,
      };
    } catch (error) {
      storage.removeItem(STORAGE_KEY);
      return {
        filters: null,
        error,
      };
    }
  }

  function clearSavedFilters(storage = global.sessionStorage) {
    storage.removeItem(STORAGE_KEY);
  }

  function activeFilterKeys(filters, { nonActiveFilterKeys, isDefaultFilterValue }) {
    return Object.keys(filters).filter((key) => {
      return (
        !nonActiveFilterKeys.has(key) &&
        !isBlank(filters[key]) &&
        !isDefaultFilterValue(key, filters[key])
      );
    });
  }

  function updateFilterFeedback({
    filters,
    nonActiveFilterKeys,
    isDefaultFilterValue,
    countSelector = "#active-filters-count",
    filtersCollapseSelector = "#filtersCollapse",
    filtersChevronSelector = "#filters-chevron",
    filtersToggleSelector = "#filters-toggle",
  }) {
    const activeFilters = activeFilterKeys(filters, {
      nonActiveFilterKeys,
      isDefaultFilterValue,
    });

    const countElement = $(countSelector);
    if (activeFilters.length > 0) {
      countElement.text(
        `${activeFilters.length} active filter${activeFilters.length > 1 ? "s" : ""}`,
      );
      countElement.removeClass("text-muted").addClass("text-primary fw-bold");
    } else {
      countElement.text("No active filters");
      countElement.removeClass("text-primary fw-bold").addClass("text-muted");
    }

    const isCollapsed = !$(filtersCollapseSelector).hasClass("show");
    const filtersChevron = $(filtersChevronSelector);
    if (isCollapsed) {
      filtersChevron.removeClass("fa-chevron-up").addClass("fa-chevron-down");
      $(filtersToggleSelector).attr("aria-expanded", "false");
    } else {
      filtersChevron.removeClass("fa-chevron-down").addClass("fa-chevron-up");
      $(filtersToggleSelector).attr("aria-expanded", "true");
    }

    return activeFilters.length;
  }

  global.TransactionListStateUtils = {
    activeFilterKeys,
    buildFilters,
    buildTotalsFilters,
    clearSavedFilters,
    createLogger,
    loadFilters,
    saveFilters,
    updateFilterFeedback,
  };
})(window);
