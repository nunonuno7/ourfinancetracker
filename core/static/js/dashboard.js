document.addEventListener("DOMContentLoaded", () => {
  let columns = [];
  let rows = [];
  let allPeriods = [];
  let fullPeriods = [];
  let allYears = [];
  let selectedYearRange = [];

  const yearSlider = document.getElementById("year-range");
  const yearStartLbl = document.getElementById("year-start-label");
  const yearEndLbl = document.getElementById("year-end-label");
  const periodSlider = document.getElementById("period-range");
  const periodStartLbl = document.getElementById("period-start-label");
  const periodEndLbl = document.getElementById("period-end-label");

  const parsePeriod = (p) => {
    const [mon, yy] = p.split("/");
    const months = { Jan:0, Feb:1, Mar:2, Apr:3, May:4, Jun:5, Jul:6, Aug:7, Sep:8, Oct:9, Nov:10, Dec:11 };
    return new Date(2000 + parseInt(yy), months[mon]);
  };

  const sliderRange = (sl) => sl.noUiSlider.get();

  const initYearSlider = (years) => {
    if (yearSlider.noUiSlider) yearSlider.noUiSlider.destroy();
    noUiSlider.create(yearSlider, {
      start: [years[0], years.at(-1)],
      connect: true,
      step: 1,
      range: { min: years[0], max: years.at(-1) },
      format: {
        to: value => Math.round(value),
        from: value => parseInt(value),
      },
    });
    const [s, e] = yearSlider.noUiSlider.get();
    yearStartLbl.textContent = s;
    yearEndLbl.textContent = e;
    selectedYearRange = [+s, +e];

    yearSlider.noUiSlider.on("update", (values) => {
      yearStartLbl.textContent = values[0];
      yearEndLbl.textContent = values[1];
      selectedYearRange = values.map(v => parseInt(v));
    });

    yearSlider.noUiSlider.on("change", () => {
      fullPeriods = allPeriods.filter(p => {
        const y = 2000 + parseInt(p.split("/")[1]);
        return y >= selectedYearRange[0] && y <= selectedYearRange[1];
      });
      initPeriodSlider(fullPeriods, true, 12);
    });
  };

  const initPeriodSlider = (periods, preselectLast = true, numMonths = 12) => {
    if (periodSlider.noUiSlider) periodSlider.noUiSlider.destroy();
    let startIdx = 0;
    let endIdx = periods.length - 1;
    if (preselectLast && periods.length > numMonths) {
      endIdx = periods.length - 1;
      startIdx = Math.max(0, endIdx - (numMonths - 1));
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

    periodSlider.noUiSlider.set([periods[startIdx], periods[endIdx]]);
    renderTable();  // render inicial
    periodSlider.noUiSlider.on("set", renderTable);
    periodSlider.noUiSlider.on("change", renderTable);

    periodSlider.noUiSlider.on("update", (values) => {
      periodStartLbl.textContent = values[0];
      periodEndLbl.textContent = values[1];
    });
  };

  const renderTable = () => {
    if (!rows.length) return;
    const [start, end] = sliderRange(periodSlider);
    const iStart = allPeriods.indexOf(start);
    const iEnd = allPeriods.indexOf(end);
    const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);
    const normVis = visiblePeriods.map(p => p.trim().toLowerCase());
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
        if (!isNaN(val)) td.classList.add("text-end");
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
        const sum = normVis.includes(col.trim().toLowerCase())
          ? rows.reduce((acc, row) => {
              const v = row[col];
              return acc + (v !== null && v !== undefined ? +v : 0);
            }, 0)
          : 0;
        td.textContent = `€ ${sum.toLocaleString("pt-PT", { minimumFractionDigits: 2 })}`;
        td.classList.add("text-end", "fw-bold");
      }
      totalRow.appendChild(td);
    });
    tbody.appendChild(totalRow);
  };

  fetch("/account-balances/json/")
    .then(res => res.json())
    .then(data => {
      console.log("🔍 Dados recebidos:", data);
      columns = data.columns;
      rows = data.rows;

      // CONVERSÃO: strings numéricas para números
      columns.slice(2).forEach(p =>
        rows.forEach(r => {
          if (r[p] !== null && r[p] !== undefined) r[p] = +r[p];
        })
      );

      allPeriods = columns.slice(2).sort((a, b) => parsePeriod(a) - parsePeriod(b));
      allYears = [...new Set(allPeriods.map(p => 2000 + parseInt(p.split("/")[1])))]
        .sort((a, b) => a - b);

      const minYear = allYears[0];
      const maxYear = allYears.at(-1);
      selectedYearRange = [minYear, maxYear];

      fullPeriods = allPeriods;
      initYearSlider(allYears);
      initPeriodSlider(fullPeriods, true, 12);
    });
});
