document.addEventListener("DOMContentLoaded", () => {
  let columns = [];
  let rows = [];
  let allPeriods = [];
  let fullPeriods = [];
  let allYears = [];
  let selectedYearRange = [];

  const STORAGE_KEY = "dashboardFilters";

  const yearSlider = document.getElementById("year-range");
  const yearStartLabel = document.getElementById("year-start-label");
  const yearEndLabel = document.getElementById("year-end-label");
  const periodSlider = document.getElementById("period-range");
  const periodStartLabel = document.getElementById("period-start-label");
  const periodEndLabel = document.getElementById("period-end-label");

  const parsePeriod = (p) => {
    const [monStr, yy] = p.split("/");
    const months = { Jan:0, Feb:1, Mar:2, Apr:3, May:4, Jun:5, Jul:6, Aug:7, Sep:8, Oct:9, Nov:10, Dec:11 };
    return new Date(2000 + parseInt(yy), months[monStr]);
  };

  const getSliderRange = (slider) => slider.noUiSlider.get();

  const saveFiltersToStorage = () => {
    const [yearStart, yearEnd] = selectedYearRange;
    const [periodStart, periodEnd] = getSliderRange(periodSlider);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ yearStart, yearEnd, periodStart, periodEnd }));
  };

  const loadFiltersFromStorage = () => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  };

  const initYearSlider = (years) => {
    if (yearSlider.noUiSlider) yearSlider.noUiSlider.destroy();
    noUiSlider.create(yearSlider, {
      start: [years[0], years[years.length - 1]],
      connect: true,
      step: 1,
      range: { min: years[0], max: years[years.length - 1] },
      format: {
        to: value => Math.round(value),
        from: value => parseInt(value),
      },
    });
    const [start, end] = yearSlider.noUiSlider.get();
    yearStartLabel.textContent = start;
    yearEndLabel.textContent = end;
    selectedYearRange = [parseInt(start), parseInt(end)];
    yearSlider.noUiSlider.on("update", (values) => {
      yearStartLabel.textContent = values[0];
      yearEndLabel.textContent = values[1];
      selectedYearRange = values.map(v => parseInt(v));
    });
    yearSlider.noUiSlider.on("change", () => {
      fullPeriods = allPeriods.filter(p => {
        const y = 2000 + parseInt(p.split("/")[1]);
        return y >= selectedYearRange[0] && y <= selectedYearRange[1];
      });
      console.log("📅 fullPeriods carregados:", fullPeriods);
      initPeriodSlider(fullPeriods, false);
      saveFiltersToStorage();
      renderTable();
    });
  };

  const initPeriodSlider = (periods, preselectLast = true) => {
    if (periodSlider.noUiSlider) periodSlider.noUiSlider.destroy();
    let startIdx = 0;
    let endIdx = periods.length - 1;
    if (preselectLast && periods.length > 2) {
      endIdx = periods.length - 1;
      startIdx = Math.max(0, endIdx - 2);
    }
    noUiSlider.create(periodSlider, {
      start: [startIdx, endIdx],
      connect: true,
      step: 1,
      range: { min: 0, max: periods.length - 1 },
      format: {
        to: value => periods[Math.round(value)],
        from: val => periods.indexOf(val),
      },
    });
    const [initialStart, initialEnd] = periodSlider.noUiSlider.get();
    periodStartLabel.textContent = initialStart;
    periodEndLabel.textContent = initialEnd;
    periodSlider.noUiSlider.on("update", (values) => {
      periodStartLabel.textContent = values[0];
      periodEndLabel.textContent = values[1];
    });
    periodSlider.noUiSlider.on("change", () => {
      saveFiltersToStorage();
      renderTable();
    });
  };

  const renderTable = () => {
    let visiblePeriods = fullPeriods.slice().sort((a, b) => parsePeriod(a) - parsePeriod(b));
    const [startPeriod, endPeriod] = getSliderRange(periodSlider);
    visiblePeriods = visiblePeriods.filter(p => {
      const i = allPeriods.indexOf(p);
      const iStart = allPeriods.indexOf(startPeriod);
      const iEnd = allPeriods.indexOf(endPeriod);
      return i >= iStart && i <= iEnd;
    });
    const selectedCols = ["type", "currency", ...visiblePeriods];
    const theadTop = document.getElementById("balance-header-top");
    const theadBottom = document.getElementById("balance-header-bottom");
    const tbody = document.querySelector("#balance-table tbody");
    theadTop.innerHTML = "";
    theadBottom.innerHTML = "";
    tbody.innerHTML = "";
    ["type", "currency"].forEach(col => {
      const thTop = document.createElement("th");
      thTop.rowSpan = 2;
      thTop.textContent = col;
      theadTop.appendChild(thTop);
      const thBottom = document.createElement("th");
      thBottom.style.display = "none";
      theadBottom.appendChild(thBottom);
    });
    const yearMap = {};
    visiblePeriods.forEach(p => {
      const [mon, yy] = p.split("/");
      const year = "20" + yy;
      yearMap[year] = yearMap[year] || [];
      yearMap[year].push(p);
    });
    Object.entries(yearMap).forEach(([year, periods]) => {
      const th = document.createElement("th");
      th.colSpan = periods.length;
      th.textContent = year;
      th.classList.add("text-center");
      theadTop.appendChild(th);
    });
    Object.values(yearMap).flat().forEach(p => {
      const th = document.createElement("th");
      th.textContent = p.split("/")[0];
      theadBottom.appendChild(th);
    });
    rows.forEach(row => {
      const tr = document.createElement("tr");
      selectedCols.forEach(col => {
        const td = document.createElement("td");
        const val = row[col] ?? 0;
        td.textContent = typeof val === "number"
          ? `€ ${val.toLocaleString("pt-PT", { minimumFractionDigits: 2 })}`
          : val || "–";
        if (typeof val === "number") td.classList.add("text-end");
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    const totalRow = document.createElement("tr");
    selectedCols.forEach(col => {
      const td = document.createElement("td");
      if (col === "type") {
        td.textContent = "Total";
        td.classList.add("fw-bold");
      } else if (col === "currency") {
        td.textContent = "EUR";
        td.classList.add("fw-bold");
      } else {
        const colSum = rows.reduce((acc, row) => acc + (typeof row[col] === "number" ? row[col] : 0), 0);
        td.textContent = `€ ${colSum.toLocaleString("pt-PT", { minimumFractionDigits: 2 })}`;
        td.classList.add("text-end", "fw-bold");
      }
      totalRow.appendChild(td);
    });
    tbody.appendChild(totalRow);
  };

  fetch("/account-balances/json/")
    .then(res => res.json())
    .then(data => {
      columns = data.columns;
      rows = data.rows;
      allPeriods = columns.slice(2).sort((a, b) => parsePeriod(a) - parsePeriod(b));
      allYears = [...new Set(allPeriods.map(p => 2000 + parseInt(p.split("/")[1])))]
        .sort((a, b) => a - b);

      const saved = loadFiltersFromStorage();

      if (saved) {
        selectedYearRange = [saved.yearStart, saved.yearEnd];
        fullPeriods = allPeriods.filter(p => {
          const y = 2000 + parseInt(p.split("/")[1]);
          return y >= saved.yearStart && y <= saved.yearEnd;
        });
      } else {
        const minYear = allYears[0];
        const maxYear = allYears[allYears.length - 1];
        selectedYearRange = [minYear, maxYear];
        fullPeriods = allPeriods.filter(p => {
          const y = 2000 + parseInt(p.split("/")[1]);
          return y >= minYear && y <= maxYear;
        });
        console.log("✅ Períodos visíveis por omissão:", fullPeriods);
      }

      initYearSlider(allYears);
      initPeriodSlider(fullPeriods, false);

      if (saved && periodSlider.noUiSlider) {
        const idxStart = fullPeriods.indexOf(saved.periodStart);
        const idxEnd = fullPeriods.indexOf(saved.periodEnd);
        if (idxStart !== -1 && idxEnd !== -1) {
          periodSlider.noUiSlider.set([idxStart, idxEnd]);
        }
      }

      renderTable();

      document.getElementById("apply-filters").addEventListener("click", renderTable);
      document.getElementById("reset-filters").addEventListener("click", () => {
        sessionStorage.removeItem(STORAGE_KEY);
        const minYear = allYears[0];
        const maxYear = allYears[allYears.length - 1];
        selectedYearRange = [minYear, maxYear];
        fullPeriods = allPeriods.filter(p => {
          const y = 2000 + parseInt(p.split("/")[1]);
          return y >= minYear && y <= maxYear;
        });
        initYearSlider(allYears);
        initPeriodSlider(fullPeriods, false);
        renderTable();
      });
    });
});