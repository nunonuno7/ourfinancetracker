(function initializeTransactionListFilterUtils(global) {
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
    account_id: "#filter-account",
    category_id: "#filter-category",
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

  const LEGACY_FILTER_KEY_MAP = {
    account: "account_id",
    category: "category_id",
  };

  const FILTER_OPTION_LABELS = {
    type: "Types",
    account_id: "Accounts",
    category_id: "Categories",
    period: "Periods",
  };

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

  function isBlank(value) {
    return value === "" || value === null || value === undefined;
  }

  function normalizeFilterState(filters) {
    if (!filters || typeof filters !== "object") {
      return {};
    }

    const normalized = { ...filters };
    if (!isBlank(normalized.type) && TRANSACTION_TYPE_LABEL_TO_CODE[normalized.type]) {
      normalized.type = TRANSACTION_TYPE_LABEL_TO_CODE[normalized.type];
    }

    Object.entries(LEGACY_FILTER_KEY_MAP).forEach(([legacyKey, currentKey]) => {
      if (isBlank(normalized[currentKey]) && !isBlank(normalized[legacyKey])) {
        normalized[currentKey] = normalized[legacyKey];
      }
    });

    return normalized;
  }

  function ensureSelectOption(selector, rawValue, rawLabel = null) {
    const element = $(selector);
    if (!element.length || !element.is("select") || isBlank(rawValue)) {
      return;
    }

    const value = String(rawValue);
    const label = rawLabel === null ? value : String(rawLabel);
    const hasOption =
      element.find("option").filter((_index, option) => option.value === value).length >
      0;

    if (!hasOption) {
      element.append(new Option(label, value, false, false));
    }
  }

  function toOptionRecord(option) {
    if (option && typeof option === "object" && !Array.isArray(option)) {
      const value = option.value ?? option.id ?? option.name ?? "";
      const label = option.label ?? option.name ?? option.value ?? option.id ?? "";
      return {
        value: String(value),
        label: String(label),
      };
    }

    return {
      value: String(option),
      label: String(option),
    };
  }

  function updateSelectOptions({ selector, options = [], currentValue = "", filterType }) {
    const select = $(selector);
    if (!select.length) {
      return { reset: false, selectedValue: currentValue };
    }

    const normalizedOptions = options.map(toOptionRecord);
    const currentValueString = isBlank(currentValue) ? "" : String(currentValue);
    let selectedValue = currentValueString;
    let matched = false;

    select.empty();
    select.append(
      new Option(`All ${FILTER_OPTION_LABELS[filterType] || "Options"}`, "", false, false),
    );

    normalizedOptions.forEach((option) => {
      if (option.value === currentValueString) {
        matched = true;
      }
      if (!matched && option.label === currentValueString) {
        selectedValue = option.value;
        matched = true;
      }
      select.append(new Option(option.label, option.value, false, false));
    });

    if (matched) {
      select.val(selectedValue);
      return { reset: false, selectedValue };
    }

    select.val("");
    return { reset: !!currentValueString, selectedValue: "" };
  }

  function buildQueryParams(filters, extraParams = {}) {
    const params = new URLSearchParams();

    [filters, extraParams].forEach((source) => {
      Object.entries(source || {}).forEach(([key, value]) => {
        if (!isBlank(value)) {
          params.append(key, value);
        }
      });
    });

    return params;
  }

  global.TransactionListFilterUtils = {
    buildFallbackTransactionListDefaults,
    buildQueryParams,
    ensureSelectOption,
    filterFieldSelectors: FILTER_FIELD_SELECTORS,
    nonActiveFilterKeys: NON_ACTIVE_FILTER_KEYS,
    normalizeFilterState,
    readJsonScript,
    transactionTypeCodeToLabel: TRANSACTION_TYPE_CODE_TO_LABEL,
    transactionTypeLabelToCode: TRANSACTION_TYPE_LABEL_TO_CODE,
    updateSelectOptions,
  };
})(window);
