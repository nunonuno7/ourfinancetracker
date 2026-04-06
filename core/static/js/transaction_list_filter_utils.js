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

  const CTRL_MULTI_SELECT_DATA_ATTR = "ctrlMultiselect";
  const CTRL_MULTI_SELECT_VALUES_ATTR = "selected-values";
  const CTRL_MULTI_SELECT_PLACEHOLDER_ATTR = "placeholderLabel";
  const CTRL_MULTI_SELECT_HINT = "Hold Ctrl to select multiple options";
  const CHECKMARK_PREFIX = "\u2713 ";
  const CTRL_MULTI_SELECT_STATE_KEY = "ctrlMultiSelectState";

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
    return (
      value === "" ||
      value === null ||
      value === undefined ||
      (Array.isArray(value) && value.length === 0)
    );
  }

  function normalizeStringArray(rawValue) {
    const values = [];
    const seen = new Set();

    const addValue = (value) => {
      const stringValue = String(value ?? "").trim();
      if (!stringValue || seen.has(stringValue)) {
        return;
      }
      seen.add(stringValue);
      values.push(stringValue);
    };

    const visit = (value) => {
      if (Array.isArray(value)) {
        value.forEach(visit);
        return;
      }

      if (isBlank(value)) {
        return;
      }

      addValue(value);
    };

    visit(rawValue);
    return values;
  }

  function toScalarOrArray(rawValue) {
    const values = normalizeStringArray(rawValue);
    if (values.length === 0) {
      return "";
    }
    if (values.length === 1) {
      return values[0];
    }
    return values;
  }

  function normalizeFilterState(filters) {
    if (!filters || typeof filters !== "object") {
      return {};
    }

    const normalized = { ...filters };

    if (Array.isArray(normalized.type)) {
      normalized.type = normalized.type
        .map((value) => TRANSACTION_TYPE_LABEL_TO_CODE[value] || value)
        .filter((value) => !isBlank(value));
    } else if (
      !isBlank(normalized.type) &&
      TRANSACTION_TYPE_LABEL_TO_CODE[normalized.type]
    ) {
      normalized.type = TRANSACTION_TYPE_LABEL_TO_CODE[normalized.type];
    }

    Object.entries(LEGACY_FILTER_KEY_MAP).forEach(([legacyKey, currentKey]) => {
      if (isBlank(normalized[currentKey]) && !isBlank(normalized[legacyKey])) {
        normalized[currentKey] = normalized[legacyKey];
      }
    });

    return normalized;
  }

  function isCtrlMultiSelect(selector) {
    return $(selector).data(CTRL_MULTI_SELECT_DATA_ATTR) === true;
  }

  function getOptionBaseLabel(option) {
    if (!option) {
      return "";
    }

    const currentText = String(option.text || "");
    if (!option.dataset.baseLabel) {
      option.dataset.baseLabel = currentText.startsWith(CHECKMARK_PREFIX)
        ? currentText.slice(CHECKMARK_PREFIX.length)
        : currentText;
    }

    return option.dataset.baseLabel;
  }

  function appendSelectOption(select, value, label) {
    const option = new Option(String(label), String(value), false, false);
    option.dataset.baseLabel = String(label);
    select.append(option);
  }

  function getCtrlMultiSelectPlaceholderLabel(selector) {
    const select = $(selector);
    if (!select.length) {
      return "";
    }

    const configuredLabel = select.data(CTRL_MULTI_SELECT_PLACEHOLDER_ATTR);
    if (!isBlank(configuredLabel)) {
      return String(configuredLabel);
    }

    const firstOption = select.find("option").get(0);
    return getOptionBaseLabel(firstOption);
  }

  function sortValuesByOptionOrder(select, rawValues) {
    const requestedValues = normalizeStringArray(rawValues);
    if (requestedValues.length === 0) {
      return [];
    }

    const orderIndex = new Map();
    select.find("option").each((_index, option) => {
      const value = String(option.value || "");
      if (value && !orderIndex.has(value)) {
        orderIndex.set(value, orderIndex.size);
      }
    });

    return [...requestedValues].sort((left, right) => {
      const leftIndex = orderIndex.has(left)
        ? orderIndex.get(left)
        : Number.MAX_SAFE_INTEGER;
      const rightIndex = orderIndex.has(right)
        ? orderIndex.get(right)
        : Number.MAX_SAFE_INTEGER;
      if (leftIndex === rightIndex) {
        return left.localeCompare(right);
      }
      return leftIndex - rightIndex;
    });
  }

  function getCtrlMultiSelectValues(selector) {
    const select = $(selector);
    if (!select.length) {
      return [];
    }

    const rawValues = select.attr(`data-${CTRL_MULTI_SELECT_VALUES_ATTR}`);
    if (rawValues) {
      try {
        return sortValuesByOptionOrder(select, JSON.parse(rawValues));
      } catch (error) {
        console.warn("[getCtrlMultiSelectValues] Failed to parse stored values", {
          selector,
          error,
        });
      }
    }

    return sortValuesByOptionOrder(select, select.val());
  }

  function setCtrlMultiSelectValues(selector, rawValues) {
    const select = $(selector);
    if (!select.length) {
      return [];
    }

    const values = sortValuesByOptionOrder(select, rawValues);
    select.attr(`data-${CTRL_MULTI_SELECT_VALUES_ATTR}`, JSON.stringify(values));
    syncCtrlMultiSelectUI(selector);
    return values;
  }

  function setFilterElementValue(selector, rawValue) {
    const element = $(selector);
    if (!element.length) {
      return rawValue;
    }

    if (isCtrlMultiSelect(selector)) {
      const values = setCtrlMultiSelectValues(selector, rawValue);
      return values.length <= 1 ? values[0] || "" : values;
    }

    const value = Array.isArray(rawValue) ? rawValue[0] || "" : rawValue;
    element.val(value);
    return value;
  }

  function getFilterElementValue(selector) {
    const element = $(selector);
    if (!element.length) {
      return "";
    }

    if (isCtrlMultiSelect(selector)) {
      return toScalarOrArray(getCtrlMultiSelectValues(selector));
    }

    return element.val();
  }

  function getFilterElementValues(selector) {
    const element = $(selector);
    if (!element.length) {
      return [];
    }

    if (isCtrlMultiSelect(selector)) {
      return getCtrlMultiSelectValues(selector);
    }

    return normalizeStringArray(element.val());
  }

  function getCtrlMultiSelectState(selector) {
    const select = $(selector);
    if (!select.length) {
      return null;
    }
    return select.data(CTRL_MULTI_SELECT_STATE_KEY) || null;
  }

  function createCtrlMultiSelectItem({
    value,
    label,
    checked = false,
    showCheckbox = true,
    extraClass = "",
  }) {
    const item = $(
      '<button type="button" class="dropdown-item tx-filter-dropdown-item d-flex align-items-center gap-2"></button>',
    );
    item.attr("data-filter-value", String(value));
    item.toggleClass("active", checked);
    if (extraClass) {
      item.addClass(extraClass);
    }

    const text = $('<span class="tx-filter-dropdown-label"></span>');
    text.text(label);

    if (showCheckbox) {
      const checkbox = $(
        '<input type="checkbox" class="form-check-input mt-0 tx-filter-dropdown-checkbox" tabindex="-1" aria-hidden="true">',
      );
      checkbox.prop("checked", checked);
      item.append(checkbox);
    }

    item.append(text);
    return item;
  }

  function syncCtrlMultiSelectMenuGeometry(state) {
    if (!state?.button?.length || !state?.menu?.length) {
      return;
    }

    const buttonWidth = Math.ceil(state.button.outerWidth() || 0);
    if (!buttonWidth) {
      return;
    }

    state.menu.css({
      width: `${buttonWidth}px`,
      minWidth: `${buttonWidth}px`,
      maxWidth: `${buttonWidth}px`,
    });
  }

  function updateFiltersLayerState() {
    $(".transactions-filters-card").each((_index, element) => {
      const card = $(element);
      const hasOpenDropdown =
        card.find(".tx-filter-dropdown.tx-filter-dropdown-open").length > 0;
      card.toggleClass("tx-filters-layer-open", hasOpenDropdown);
    });
  }

  function buildCtrlMultiSelectDropdown(selector) {
    const select = $(selector);
    if (!select.length || !isCtrlMultiSelect(selector)) {
      return null;
    }

    const existingState = getCtrlMultiSelectState(selector);
    if (existingState) {
      return existingState;
    }

    const wrapper = $('<div class="dropdown tx-filter-dropdown"></div>');
    const button = $(
      '<button type="button" class="form-select form-select-sm tx-filter-dropdown-toggle text-start" aria-expanded="false"></button>',
    );
    button.attr("data-bs-toggle", "dropdown");

    const menu = $('<div class="dropdown-menu tx-filter-dropdown-menu p-0"></div>');
    const list = $('<div class="tx-filter-dropdown-options py-1"></div>');
    menu.append(list);
    wrapper.append(button, menu);

    select.after(wrapper);
    select.addClass("tx-filter-native-select");
    select.attr("aria-hidden", "true");

    const dropdownInstance =
      global.bootstrap?.Dropdown?.getOrCreateInstance(button.get(0), {
        autoClose: "outside",
        popperConfig(defaultConfig) {
          return {
            ...defaultConfig,
            strategy: "fixed",
          };
        },
      }) || null;

    const state = {
      wrapper,
      button,
      menu,
      list,
      dropdownInstance,
    };
    select.data(CTRL_MULTI_SELECT_STATE_KEY, state);

    button.on("show.bs.dropdown", () => {
      wrapper.addClass("tx-filter-dropdown-open");
      updateFiltersLayerState();
      syncCtrlMultiSelectMenuGeometry(state);
      renderCtrlMultiSelectDropdown(selector);
    });

    button.on("hide.bs.dropdown", () => {
      wrapper.removeClass("tx-filter-dropdown-open");
      updateFiltersLayerState();
    });

    $(global).on("resize.ctrlMultiSelect", () => {
      syncCtrlMultiSelectMenuGeometry(state);
    });

    list.on("click.ctrlMultiSelect", "[data-filter-value]", (event) => {
      event.preventDefault();
      event.stopPropagation();

      const item = $(event.target).closest("[data-filter-value]");
      const value = item.attr("data-filter-value") || "";
      const keepOpen = !!(event.ctrlKey || event.metaKey);

      if (!value) {
        setCtrlMultiSelectValues(selector, []);
      } else if (keepOpen) {
        applyCtrlMultiSelectChoice(selector, value, true);
      } else {
        setCtrlMultiSelectValues(selector, value);
      }

      select.trigger("change");

      if (!keepOpen) {
        state.dropdownInstance?.hide();
      }
    });

    return state;
  }

  function renderCtrlMultiSelectDropdown(selector) {
    const state = buildCtrlMultiSelectDropdown(selector);
    if (!state) {
      return;
    }

    const select = $(selector);
    const list = state.list;
    const selectedValues = new Set(getCtrlMultiSelectValues(selector));
    const placeholderLabel = getCtrlMultiSelectPlaceholderLabel(selector);

    list.empty();
    list.append(
      createCtrlMultiSelectItem({
        value: "",
        label: placeholderLabel,
        checked: selectedValues.size === 0,
        showCheckbox: false,
        extraClass: "tx-filter-dropdown-clear",
      }),
    );

    select.find("option").each((index, option) => {
      if (index === 0 || !option.value) {
        return;
      }

      const value = String(option.value);
      list.append(
        createCtrlMultiSelectItem({
          value,
          label: getOptionBaseLabel(option),
          checked: selectedValues.has(value),
        }),
      );
    });
  }

  function syncCtrlMultiSelectDropdown(selector, { placeholderLabel, values, labels }) {
    const state = buildCtrlMultiSelectDropdown(selector);
    if (!state) {
      return;
    }

    let summary = placeholderLabel;
    if (values.length === 1) {
      summary = labels[0] || placeholderLabel;
    } else if (values.length > 1) {
      summary = `${values.length} selected`;
    }

    const select = $(selector);
    state.button.text(summary);
    state.button.attr("title", select.attr("title") || summary);
    state.button.attr("aria-label", summary);
    renderCtrlMultiSelectDropdown(selector);
  }

  function syncCtrlMultiSelectUI(selector) {
    const select = $(selector);
    if (!select.length || !isCtrlMultiSelect(selector)) {
      return {
        values: [],
        labels: [],
      };
    }

    const placeholderLabel = getCtrlMultiSelectPlaceholderLabel(selector);
    const currentValues = getCtrlMultiSelectValues(selector);
    const availableValues = new Set();

    select.find("option").each((index, option) => {
      const baseLabel = getOptionBaseLabel(option);
      if (index === 0) {
        option.text = placeholderLabel;
        option.selected = false;
        return;
      }

      option.text = baseLabel;
      option.selected = false;
      availableValues.add(String(option.value));
    });

    const values = currentValues.filter((value) => availableValues.has(value));
    select.attr(`data-${CTRL_MULTI_SELECT_VALUES_ATTR}`, JSON.stringify(values));

    if (values.length === 0) {
      select.val("");
      select.attr("title", `${placeholderLabel}. ${CTRL_MULTI_SELECT_HINT}`);
      syncCtrlMultiSelectDropdown(selector, {
        placeholderLabel,
        values: [],
        labels: [],
      });
      return {
        values: [],
        labels: [],
      };
    }

    const valueSet = new Set(values);
    const labels = [];

    select.find("option").each((index, option) => {
      if (index === 0) {
        return;
      }

      const optionValue = String(option.value);
      if (valueSet.has(optionValue)) {
        labels.push(getOptionBaseLabel(option));
        if (values.length > 1) {
          option.text = `${CHECKMARK_PREFIX}${getOptionBaseLabel(option)}`;
        }
      }
    });

    if (values.length === 1) {
      select.val(values[0]);
      select.attr("title", labels[0] || placeholderLabel);
      syncCtrlMultiSelectDropdown(selector, {
        placeholderLabel,
        values,
        labels,
      });
      return {
        values,
        labels,
      };
    }

    const summaryOption = select.find("option").get(0);
    if (summaryOption) {
      summaryOption.text = `${values.length} selected`;
    }

    select.val("");
    select.attr("title", labels.join(", "));
    syncCtrlMultiSelectDropdown(selector, {
      placeholderLabel,
      values,
      labels,
    });
    return {
      values,
      labels,
    };
  }

  function initializeCtrlMultiSelect(selector) {
    const select = $(selector);
    if (!select.length || !isCtrlMultiSelect(selector)) {
      return;
    }

    buildCtrlMultiSelectDropdown(selector);

    if (!select.attr(`data-${CTRL_MULTI_SELECT_VALUES_ATTR}`)) {
      select.attr(`data-${CTRL_MULTI_SELECT_VALUES_ATTR}`, "[]");
    }

    select.find("option").each((_index, option) => {
      getOptionBaseLabel(option);
    });

    if (!select.attr("title")) {
      const placeholderLabel = getCtrlMultiSelectPlaceholderLabel(selector);
      select.attr("title", `${placeholderLabel}. ${CTRL_MULTI_SELECT_HINT}`);
    }

    syncCtrlMultiSelectUI(selector);
  }

  function ensureSelectOption(selector, rawValue, rawLabel = null) {
    const element = $(selector);
    if (!element.length || !element.is("select") || isBlank(rawValue)) {
      return;
    }

    const values = normalizeStringArray(rawValue);
    values.forEach((value) => {
      const label = rawLabel === null ? value : String(rawLabel);
      const hasOption =
        element
          .find("option")
          .filter((_index, option) => option.value === value).length > 0;

      if (!hasOption) {
        appendSelectOption(element, value, label);
      }
    });

    if (isCtrlMultiSelect(selector)) {
      syncCtrlMultiSelectUI(selector);
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
    const currentValues = normalizeStringArray(currentValue);
    const currentValueSet = new Set(currentValues);
    const availableByValue = new Map(
      normalizedOptions.map((option) => [option.value, option]),
    );
    const availableByLabel = new Map(
      normalizedOptions.map((option) => [option.label, option.value]),
    );
    const placeholderLabel =
      getCtrlMultiSelectPlaceholderLabel(selector) ||
      `All ${FILTER_OPTION_LABELS[filterType] || "Options"}`;

    select.empty();
    appendSelectOption(select, "", placeholderLabel);

    normalizedOptions.forEach((option) => {
      appendSelectOption(select, option.value, option.label);
    });

    const matchedValues = currentValues
      .map((value) => availableByLabel.get(value) || value)
      .filter((value) => availableByValue.has(value));
    const reset = matchedValues.length !== currentValueSet.size;

    if (isCtrlMultiSelect(selector)) {
      const selectedValues = setCtrlMultiSelectValues(selector, matchedValues);
      return {
        reset,
        selectedValue: toScalarOrArray(selectedValues),
      };
    }

    const selectedValue = matchedValues[0] || "";
    select.val(selectedValue);
    return {
      reset: !!currentValues.length && !selectedValue,
      selectedValue,
    };
  }

  function buildQueryParams(filters, extraParams = {}) {
    const params = new URLSearchParams();

    [filters, extraParams].forEach((source) => {
      Object.entries(source || {}).forEach(([key, value]) => {
        if (Array.isArray(value)) {
          value.forEach((entry) => {
            if (!isBlank(entry)) {
              params.append(key, entry);
            }
          });
          return;
        }

        if (!isBlank(value)) {
          params.append(key, value);
        }
      });
    });

    return params;
  }

  function applyCtrlMultiSelectChoice(selector, rawValue, keepExisting = false) {
    const selectedValue = String(rawValue || "").trim();
    if (!selectedValue) {
      return setCtrlMultiSelectValues(selector, []);
    }

    const currentValues = getCtrlMultiSelectValues(selector);
    let nextValues = [selectedValue];

    if (keepExisting) {
      const currentSet = new Set(currentValues);
      if (currentSet.has(selectedValue)) {
        nextValues = currentValues.filter((value) => value !== selectedValue);
      } else {
        nextValues = [...currentValues, selectedValue];
      }
    }

    return setCtrlMultiSelectValues(selector, nextValues);
  }

  global.TransactionListFilterUtils = {
    applyCtrlMultiSelectChoice,
    buildFallbackTransactionListDefaults,
    buildQueryParams,
    ensureSelectOption,
    filterFieldSelectors: FILTER_FIELD_SELECTORS,
    getCtrlMultiSelectValues,
    getFilterElementValue,
    getFilterElementValues,
    initializeCtrlMultiSelect,
    isBlank,
    isCtrlMultiSelect,
    nonActiveFilterKeys: NON_ACTIVE_FILTER_KEYS,
    normalizeFilterState,
    normalizeStringArray,
    readJsonScript,
    setFilterElementValue,
    transactionTypeCodeToLabel: TRANSACTION_TYPE_CODE_TO_LABEL,
    transactionTypeLabelToCode: TRANSACTION_TYPE_LABEL_TO_CODE,
    updateSelectOptions,
  };
})(window);
