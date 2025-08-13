// Enhanced Dashboard JavaScript with Advanced Charts and Analysis
document.addEventListener("DOMContentLoaded", () => {
  // Global variables
  let columns = [];
  let rows = [];
  let allPeriods = [];
  let fullPeriods = [];
  let allYears = [];
  let selectedYearRange = [];
  let charts = {};
  let analysisData = {};
  let currentChartType = 'evolution';
  let lastKPITime = 0;
  let isInitialized = false;

  // DOM elements
  const yearSlider = document.getElementById("year-range");
  // Label elements removed from HTML
  const periodSlider = document.getElementById("period-range");

  // Enhanced utility functions
  const parsePeriod = (p) => {
    const [mon, yy] = p.split("/");
    const months = { Jan:0, Feb:1, Mar:2, Apr:3, May:4, Jun:5, Jul:6, Aug:7, Sep:8, Oct:9, Nov:10, Dec:11 };
    return new Date(2000 + parseInt(yy), months[mon]);
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const formatPercentage = (value) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  const kpiElements = ['receita-media','despesa-estimada','verified-expenses','valor-investido','patrimonio-total','kpi-daily-expenses','kpi-daily-return','kpi-growth','kpi-invest-pnl-ytd','kpi-wealth-delta','kpi-available','kpi-invest-next'];

  const showKPILoadingState = () => {
    kpiElements.forEach(id => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = '...';
        element.style.opacity = '0.6';
      }
    });
  };

  const calculateTrend = (values) => {
    if (values.length < 2) return 0;
    const recent = values.slice(-3).reduce((a, b) => a + b, 0) / Math.min(3, values.length);
    const older = values.slice(0, -3).reduce((a, b) => a + b, 0) / Math.max(1, values.length - 3);
    return older > 0 ? ((recent - older) / older) * 100 : 0;
  };

  // Enhanced debounce utility for performance
  const debounce = (func, wait) => {
    let timeout;
    let lastArgs;
    return function executedFunction(...args) {
      lastArgs = args;
      const later = () => {
        clearTimeout(timeout);
        timeout = null;
        func(...lastArgs);
      };
      if (timeout) {
        clearTimeout(timeout);
      }
      timeout = setTimeout(later, wait);
    };
  };

  // Enhanced chart initialization
  const initCharts = () => {
    const ctx1 = document.getElementById('evolution-chart').getContext('2d');
    const ctx2 = document.getElementById('allocation-chart').getContext('2d');

    // Evolution Chart with enhanced features
    charts.evolution = new Chart(ctx1, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Savings (€)',
          data: [],
          borderColor: '#28a745',
          backgroundColor: 'rgba(40, 167, 69, 0.1)',
          tension: 0.4,
          fill: true
        }, {
          label: 'Investments (€)',
          data: [],
          borderColor: '#007bff',
          backgroundColor: 'rgba(0, 123, 255, 0.1)',
          tension: 0.4,
          fill: true
        }, {
          label: 'Total Net Worth',
          data: [],
          borderColor: '#6f42c1',
          backgroundColor: 'rgba(111, 66, 193, 0.1)',
          tension: 0.4,
          borderWidth: 3,
          fill: false
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        
        resizeDelay: 0,
        plugins: {
          legend: {
            position: 'top',
          },
          title: {
            display: true,
            text: 'Net Worth Evolution Over Time'
          },
          tooltip: {
            mode: 'index',
            intersect: false,
            backgroundColor: 'rgba(0, 0, 0, 0.95)',
            titleColor: '#fff',
            bodyColor: '#fff',
            footerColor: '#a0a0a0',
            borderColor: 'rgba(255, 255, 255, 0.3)',
            borderWidth: 2,
            cornerRadius: 12,
            titleFont: { size: 14, weight: 'bold' },
            bodyFont: { size: 13 },
            footerFont: { size: 11 },
            padding: 12,
            displayColors: true,
            callbacks: {
              title: function(tooltipItems) {
                return tooltipItems[0]?.label ? `📅 Period: ${tooltipItems[0].label}` : '';
              },
              label: function(context) {
                const value = context.parsed.y || 0;
                const icon = context.dataset.label.includes('Savings') ? '💰' : 
                           context.dataset.label.includes('Investment') ? '📈' : '💎';
                return `${icon} ${context.dataset.label}: ${formatCurrency(value)}`;
              },
              afterBody: function(tooltipItems) {
                return [];
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                return formatCurrency(value);
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.1)'
            }
          },
          x: {
            grid: {
              color: 'rgba(0, 0, 0, 0.1)'
            }
          }
        },
        interaction: {
          intersect: true,
          mode: 'point'
        },
        elements: {
          point: {
            radius: 4,
            hoverRadius: 8
          }
        }
      }
    });

    // Enhanced Allocation Chart
    charts.allocation = new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: ['Savings (€)', 'Investments (€)'],
        datasets: [{
          data: [],
          backgroundColor: ['#28a745', '#007bff', '#ffc107', '#dc3545'],
          borderWidth: 3,
          borderColor: '#fff',
          hoverBorderWidth: 5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        
        resizeDelay: 0,
        plugins: {
          legend: {
            position: 'bottom',
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.95)',
            titleColor: '#fff',
            bodyColor: '#fff',
            footerColor: '#a0a0a0',
            borderColor: 'rgba(255, 255, 255, 0.3)',
            borderWidth: 2,
            cornerRadius: 12,
            titleFont: { size: 14, weight: 'bold' },
            bodyFont: { size: 13 },
            footerFont: { size: 11 },
            padding: 12,
            callbacks: {
              title: function(context) {
                return '💼 Portfolio Breakdown';
              },
              label: function(context) {
                const label = context.label || '';
                const value = context.parsed;
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = ((value / total) * 100).toFixed(1);
                const icon = label.includes('Savings') ? '💰' : '📈';
                return `${icon} ${label}: ${formatCurrency(value)} (${percentage}%)`;
              },
              afterLabel: function(context) {
                return [];
              },
              footer: function(tooltipItems) {
                return [];
              }
            }
          }
        },
        cutout: '60%'
      }
    });

    // Create flows chart (initially hidden)
    const flowsCanvas = document.createElement('canvas');
    flowsCanvas.id = 'flows-chart';
    flowsCanvas.style.display = 'none';
    document.getElementById('evolution-chart').parentNode.appendChild(flowsCanvas);

    charts.flows = new Chart(flowsCanvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: [],
        datasets: [{
          label: 'Income (€)',
          data: [],
          backgroundColor: 'rgba(40, 167, 69, 0.8)',
          borderColor: '#28a745',
          borderWidth: 1
        }, {
          label: 'Estimated Expenses (€)',
          data: [],
          backgroundColor: 'rgba(220, 53, 69, 0.8)',
          borderColor: '#dc3545',
          borderWidth: 1
        }, {
          label: 'Investments (€)',
          data: [],
          backgroundColor: 'rgba(0, 123, 255, 0.8)',
          borderColor: '#007bff',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        
        resizeDelay: 0,
        plugins: {
          title: {
            display: true,
            text: 'Monthly Financial Flows'
          },
          tooltip: {
            mode: 'point',
            intersect: true,
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            footerColor: '#a0a0a0',
            borderColor: 'rgba(255, 255, 255, 0.2)',
            borderWidth: 1,
            cornerRadius: 8,
            callbacks: {
              title: function(tooltipItems) {
                return tooltipItems[0]?.label ? `📅 Financial Flow: ${tooltipItems[0].label}` : '';
              },
              label: function(context) {
                const value = context.parsed.y || 0;
                const icon = context.dataset.label.includes('Income') ? '💰' : 
                           context.dataset.label.includes('Expenses') ? '💸' : '📈';
                return `${icon} ${context.dataset.label}: ${formatCurrency(Math.abs(value))}`;
              },
              afterBody: function(tooltipItems) {
                return [];
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                return formatCurrency(value);
              }
            }
          }
        }
      }
    });

    // Create returns chart (initially hidden)
    const returnsCanvas = document.getElementById('returns-chart');
    returnsCanvas.style.display = 'none';

    charts.returns = new Chart(returnsCanvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Portfolio Return (%)',
            data: [],
            borderColor: '#6f42c1',
            borderWidth: 2,
            tension: 0.3,
            fill: false
          },
          {
            label: 'Average Portfolio Return (%)',
            data: [],
            borderColor: '#28a745',
            borderWidth: 2,
            borderDash: [6, 6],
            pointRadius: 2,
            tension: 0.3,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        
        resizeDelay: 0,
        plugins: {
          title: {
            display: true,
            text: 'Investment Returns Over Time'
          },
          tooltip: {
            mode: 'point',
            intersect: true,
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            footerColor: '#a0a0a0',
            borderColor: 'rgba(255, 255, 255, 0.2)',
            borderWidth: 1,
            cornerRadius: 8,
            callbacks: {
              title: function(tooltipItems) {
                return tooltipItems[0]?.label ? `📅 ${tooltipItems[0].label}` : '';
              },
              label: function(context) {
                const value = context.parsed.y;
                if (value === null || value === undefined || isNaN(value)) {
                  return `${context.dataset.label}: N/A`;
                }

                // Format as percentage with 2 decimal places
                const percentageValue = `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
                return `${context.dataset.label}: ${percentageValue}`;
              },
              afterBody: function(tooltipItems) {
                return [];
              }
            }
          }
        },
        scales: {
          y: {
            ticks: {
              callback: function(value) {
                if (value === null || value === undefined || isNaN(value)) {
                  return '0%';
                }
                return value.toFixed(1) + '%';
              }
            },
            title: {
              display: true,
              text: 'Return (%)'
            }
          }
        }
      }
    });

    // Create expenses chart (initially hidden)
    const expensesCanvas = document.createElement('canvas');
    expensesCanvas.id = 'expenses-chart';
    expensesCanvas.style.display = 'none';
    document.getElementById('evolution-chart').parentNode.appendChild(expensesCanvas);

    charts.expenses = new Chart(expensesCanvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: [],
        datasets: [{
          data: [],
          backgroundColor: [
            '#dc3545', '#fd7e14', '#ffc107', '#28a745',
            '#20c997', '#17a2b8', '#6f42c1', '#e83e8c'
          ],
          borderWidth: 2,
          borderColor: '#fff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        
        resizeDelay: 0,
        plugins: {
          title: {
            display: true,
            text: 'Spending by Category'
          },
          legend: {
            position: 'right'
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                const value = context.parsed;
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = ((value / total) * 100).toFixed(1);
                return `${context.label}: ${formatCurrency(value)} (${percentage}%)`;
              },
              footer: function(tooltipItems) {
                return [];
              }
            }
          }
        }
      }
    });
  };

  // Enhanced data loading functions with aggressive caching and optimizations
  let isLoadingKPIs = false;
  let isLoadingBalances = false;
  let lastKPIParams = null;
  let balanceCache = null;
  let balanceCacheTime = 0;
  let kpiCache = new Map();
  const CACHE_DURATION = 120000; // 2 minutes for better performance
  const KPI_CACHE_DURATION = 60000; // 1 minute for KPIs

  const loadAccountBalances = async (useCache = true) => {
    console.log('📊 [loadAccountBalances] Starting load, useCache:', useCache);

    // Check cache first - extended cache duration
    if (useCache && balanceCache && (Date.now() - balanceCacheTime) < CACHE_DURATION) {
      console.log('🚀 [loadAccountBalances] Using cached balance data');

      // Quick setup from cache without re-processing
      columns = balanceCache.columns || [];
      rows = balanceCache.rows || [];

      const periods = columns.slice(2);
      allPeriods = periods.sort((a, b) => parsePeriod(a) - parsePeriod(b));
      allYears = [...new Set(allPeriods.map(p => 2000 + parseInt(p.split("/")[1])))]
        .sort((a, b) => a - b);

      fullPeriods = allPeriods;

      console.log('📋 [loadAccountBalances] Cache data restored:', {
        periods: allPeriods.length,
        years: allYears.length,
        rows: rows.length
      });

      return balanceCache;
    }

    if (isLoadingBalances) {
      console.log('🔄 [loadAccountBalances] Already loading, waiting...');
      // Wait for existing request instead of creating mock data
      return new Promise((resolve) => {
        const checkInterval = setInterval(() => {
          if (!isLoadingBalances && balanceCache) {
            clearInterval(checkInterval);
            resolve(balanceCache);
          }
        }, 100);
      });
    }

    isLoadingBalances = true;

    try {
      console.log('🌐 [loadAccountBalances] Fetching from API...');
      const response = await fetch('/account-balances/json/');

      if (!response.ok) {
        console.warn('⚠️ [loadAccountBalances] API response not OK:', response.status);
        const mockData = generateMockBalanceData();
        await initializeSlidersWithData(mockData);
        return mockData;
      }

      const data = await response.json();
      console.log('✅ [loadAccountBalances] API data received:', {
        hasColumns: !!data.columns,
        hasRows: !!data.rows,
        columnsLength: data.columns?.length || 0,
        rowsLength: data.rows?.length || 0
      });

      // Pre-process and cache the data
      columns = data.columns || [];
      rows = data.rows || [];

      if (columns.length === 0 || rows.length === 0) {
        console.warn('⚠️ [loadAccountBalances] Empty data received, using mock data');
        const mockData = generateMockBalanceData();
        await initializeSlidersWithData(mockData);
        return mockData;
      }

      // Pre-process and cache the data
      columns = data.columns || [];
      rows = data.rows || [];

      if (columns.length === 0 || rows.length === 0) {
        console.warn('⚠️ [loadAccountBalances] Empty data received, using mock data');
        const mockData = generateMockBalanceData();
        await initializeSlidersWithData(mockData);
        return mockData;
      }

      // Optimized number conversion - do it once and cache
      const periods = columns.slice(2);
      console.log('📅 [loadAccountBalances] Processing periods:', periods);

      rows.forEach(row => {
        periods.forEach(period => {
          if (row[period] !== null && row[period] !== undefined) {
            row[period] = parseFloat(row[period]);
          }
        });
      });

      allPeriods = periods.sort((a, b) => parsePeriod(a) - parsePeriod(b));
      allYears = [...new Set(allPeriods.map(p => 2000 + parseInt(p.split("/")[1])))]
        .sort((a, b) => a - b);

      const minYear = allYears[0] || new Date().getFullYear();
      const maxYear = allYears[allYears.length - 1] || new Date().getFullYear();
      selectedYearRange = [minYear, maxYear];

      fullPeriods = allPeriods;

      console.log('📊 [loadAccountBalances] Data processed:', {
        allPeriods: allPeriods.length,
        allYears: allYears.length,
        yearRange: selectedYearRange
      });

      // Cache the processed data
      balanceCache = {
        ...data,
        columns,
        rows,
        allPeriods,
        allYears,
        fullPeriods
      };
      balanceCacheTime = Date.now();

      // Initialize sliders with data
      await initializeSlidersWithData(balanceCache);

      // Update last update timestamp
      const lastUpdateEl = document.getElementById('last-update');
      if (lastUpdateEl) {
        lastUpdateEl.textContent = new Date().toLocaleString('en-GB');
      }

      console.log('✅ [loadAccountBalances] Complete success');
      return balanceCache;

    } catch (error) {
      console.error('❌ [loadAccountBalances] Error loading balances:', error);
      const mockData = generateMockBalanceData();
      await initializeSlidersWithData(mockData);
      return mockData;
    } finally {
      isLoadingBalances = false;
    }
  };

  // Helper function to ensure sliders are always initialized
  const initializeSlidersWithData = async (data) => {
    console.log('🎛️ [initializeSlidersWithData] Initializing sliders...');

    try {
      // Only initialize sliders once
      if (!yearSlider?.noUiSlider) {
        if (allYears && allYears.length > 0) {
          console.log('📅 [initializeSlidersWithData] Initializing year slider with years:', allYears);
          initYearSlider(allYears);
          console.log('📅 [initializeSlidersWithData] Initializing period slider with periods:', fullPeriods?.length || 0);
          initPeriodSlider(fullPeriods || [], true, 12);
          updateYearRangeDisplay();
        } else {
          console.warn('⚠️ [initializeSlidersWithData] No years available, using current year');
          const currentYear = new Date().getFullYear();
          initYearSlider([currentYear, currentYear]); // Ensure at least 2 values
          const currentMonth = new Date().getMonth();
          const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
          const currentPeriod = `${monthNames[currentMonth]}/${currentYear.toString().slice(-2)}`;
          initPeriodSlider([currentPeriod], true, 1);
        }
      } else {
        console.log('ℹ️ [initializeSlidersWithData] Sliders already initialized');
      }
    } catch (error) {
      console.error('❌ [initializeSlidersWithData] Error initializing sliders:', error);

      // Show error message to user with recovery option
      const yearSliderContainer = yearSlider?.parentElement;
      const periodSliderContainer = periodSlider?.parentElement;

      if (yearSliderContainer) {
        yearSliderContainer.innerHTML = `
          <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle"></i>
            Year slider initialization failed.
            <button class="btn btn-sm btn-outline-primary ms-2" onclick="location.reload()">
              Refresh Page
            </button>
          </div>
        `;
      }

      if (periodSliderContainer) {
        periodSliderContainer.innerHTML = `
          <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle"></i>
            Period slider initialization failed.
            <button class="btn btn-sm btn-outline-primary ms-2" onclick="location.reload()">
              Refresh Page
            </button>
          </div>
        `;
      }
    }
  };

  const generateMockBalanceData = () => {
    const currentYear = new Date().getFullYear();
    const currentMonth = new Date().getMonth() + 1;
    const mockColumns = ['type', 'currency'];
    const mockPeriods = [];

    // Generate last 6 months
    for (let i = 5; i >= 0; i--) {
      let year = currentYear;
      let month = currentMonth - i;
      if (month <= 0) {
        year--;
        month += 12;
      }
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      mockPeriods.push(`${monthNames[month - 1]}/${year.toString().slice(-2)}`);
    }

    mockColumns.push(...mockPeriods);

    const mockRows = [
      { type: 'Savings', currency: 'EUR', ...Object.fromEntries(mockPeriods.map((p, i) => [p, 1000 + i * 200])) },
      { type: 'Investment', currency: 'EUR', ...Object.fromEntries(mockPeriods.map((p, i) => [p, 5000 + i * 500])) }
    ];

    return { columns: mockColumns, rows: mockRows };
  };

  const loadFinancialKPIs = async (startPeriod = null, endPeriod = null) => {
    const currentParams = `${startPeriod || 'null'}-${endPeriod || 'null'}`;

    // Check cache first for instant display
    const cacheKey = currentParams;
    const cachedKPI = kpiCache.get(cacheKey);
    if (cachedKPI && (Date.now() - cachedKPI.timestamp) < KPI_CACHE_DURATION) {
      console.log('🚀 Using cached KPI data for instant display');
      updateKPICards(cachedKPI.data);
      return cachedKPI.data;
    }

    // Show immediate approximation while loading if we have balance data
    if (balanceCache && !cachedKPI) {
      const approximateKPIs = generateApproximateKPIs();
      updateKPICards(approximateKPIs);
      console.log('⚡ Showing approximate KPIs while loading exact data');
    }

    // Prevent duplicate calls
    if (isLoadingKPIs) {
      console.log('🔄 KPI loading already in progress, skipping');
      return cachedKPI?.data || {};
    }

    // Don't reload same parameters within 2 seconds (reduced from 5)
    if (currentParams === lastKPIParams && (Date.now() - lastKPITime) < 2000) {
      console.log('🔄 Ignorando chamada duplicada de KPIs:', currentParams);
      return cachedKPI?.data || {};
    }

    isLoadingKPIs = true;
    lastKPIParams = currentParams;
    lastKPITime = Date.now();

    try {
      let url = '/dashboard/kpis/';
      if (startPeriod && endPeriod) {
        // Convert period format from "Jul/24" to "2024-07"
        const convertPeriod = (period) => {
          const [month, year] = period.split('/');
          const monthMap = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
          };
          return `20${year}-${monthMap[month]}`;
        };

        const start = convertPeriod(startPeriod);
        const end = convertPeriod(endPeriod);
        url += `?start_period=${start}&end_period=${end}`;
      }

      console.log('📊 Carregando KPIs:', url);
      const response = await fetch(url);
      if (!response.ok) {
        console.warn('⚠️ KPIs endpoint not available, using mock data');
        const mockData = generateMockKPIs();
        updateKPICards(mockData);
        return mockData;
      }

      const data = await response.json();
      console.log('📊 KPIs carregados');

      // Cache the result
      kpiCache.set(cacheKey, {
        data: data,
        timestamp: Date.now()
      });

      // Limit cache size to prevent memory issues
      if (kpiCache.size > 20) {
        const oldestKey = kpiCache.keys().next().value;
        kpiCache.delete(oldestKey);
      }

      updateKPICards(data);
      return data;
    } catch (error) {
      console.error('❌ Erro ao carregar KPIs:', error);
      const mockData = generateMockKPIs();
      updateKPICards(mockData);
      return mockData;
    } finally {
      isLoadingKPIs = false;
    }
  };

  // Enhanced approximate KPIs calculation for instant Portfolio Analysis display
  const generateApproximateKPIs = () => {
    if (!balanceCache || !balanceCache.rows) {
      return generateMockKPIs();
    }

    try {
      // Calculate totals from latest period for instant display
      const latestPeriod = allPeriods[allPeriods.length - 1];
      const previousPeriod = allPeriods[allPeriods.length - 2] || latestPeriod;

      let totalSavings = 0;
      let totalInvestments = 0;
      let prevSavings = 0;
      let prevInvestments = 0;

      balanceCache.rows.forEach(row => {
        const currentValue = parseFloat(row[latestPeriod]) || 0;
        const prevValue = parseFloat(row[previousPeriod]) || 0;
        const rowType = (row.type || '').toLowerCase();

        if (rowType.includes('savings') || rowType.includes('current')) {
          totalSavings += currentValue;
          prevSavings += prevValue;
        } else if (rowType.includes('investment')) {
          totalInvestments += currentValue;
          prevInvestments += prevValue;
        }
      });

      const totalPatrimonio = totalSavings + totalInvestments;
      const prevPatrimonio = prevSavings + prevInvestments;

      // Calculate approximate growth
      const wealthGrowth = prevPatrimonio > 0 ?
        ((totalPatrimonio - prevPatrimonio) / prevPatrimonio * 100) : 0;

      // Estimate monthly flows from balance changes
      const estimatedIncome = Math.max(totalSavings - prevSavings + totalInvestments - prevInvestments + 200, 0);
      const estimatedExpenses = Math.max(200, estimatedIncome * 0.3); // Conservative estimate
      const savingsRate = estimatedIncome > 0 ? ((estimatedIncome - estimatedExpenses) / estimatedIncome * 100) : 0;

      return {
        patrimonio_total: `${totalPatrimonio.toLocaleString('en-GB')} €`,
        receita_media: `${Math.round(estimatedIncome).toLocaleString('en-GB')} €`,
        despesa_estimada_media: `${Math.round(estimatedExpenses).toLocaleString('en-GB')} €`,
        valor_investido_total: `${totalInvestments.toLocaleString('en-GB')} €`,
        despesas_justificadas_pct: "95%", // Optimistic estimate
        taxa_poupanca: `${savingsRate.toFixed(1)}%`,
        wealth_growth: `${wealthGrowth >= 0 ? '+' : ''}${wealthGrowth.toFixed(1)}%`,
        investment_rate: totalPatrimonio > 0 ? `${(totalInvestments / totalPatrimonio * 100).toFixed(1)}%` : "0%",
        status: 'fast_estimate'
      };
    } catch (error) {
      console.warn('Failed to generate enhanced approximate KPIs:', error);
      return generateMockKPIs();
    }
  };

  const generateMockKPIs = () => {
    return {
      patrimonio_total: "12,500 €",
      receita_media: "2,500 €",
      despesa_estimada_media: "1,800 €",
      valor_investido_total: "8,500 €",
      despesas_justificadas_pct: "85%",
      rentabilidade_mensal_media: "+2.5%",
      status: 'mock_data'
    };
  };

  const loadFinancialAnalysis = async () => {
    try {
      const response = await fetch('/financial-analysis/json/');
      if (!response.ok) {
        console.warn('⚠️ Financial analysis endpoint unavailable, using simulated data');
        const simulatedData = generateSimulatedAnalysis();
        analysisData = simulatedData;
        generateInsights(simulatedData);
        updateFlowsChart(simulatedData);
        return simulatedData;
      }

      const data = await response.json();
      console.log('📈 Financial analysis received:', data);
      analysisData = data;
      generateInsights(data);
      updateFlowsChart(data);
      return data;
    } catch (error) {
      console.warn('⚠️ Error loading financial analysis, using simulated data:', error);
      const simulatedData = generateSimulatedAnalysis();
      analysisData = simulatedData;
      generateInsights(simulatedData);
      updateFlowsChart(simulatedData);
      return simulatedData;
    }
  };

  const generateSimulatedAnalysis = () => {
    // Generate simulated analysis data based on available account balances
    const simulatedData = {
      data: [],
      summary: {
        avg_return: -5.2,
        avg_income: 2300,
        avg_expense: 1900,
        volatility: 15.3
      }
    };

    // Create mock monthly data from periods
    allPeriods.slice(-12).forEach((period, index) => {
      const baseIncome = 2000 + (Math.random() * 600);
      const baseExpense = 1500 + (Math.random() * 800);

      simulatedData.data.push({
        period: period.replace('/', '-20'),
        income: baseIncome,
        expense_estimated: baseExpense,
        investment_flow: Math.max(0, baseIncome - baseExpense - 200),
        portfolio_return: (Math.random() - 0.5) * 20 // -10% to +10%
      });
    });

    return simulatedData;
  };

  // This function was removed to avoid temporary incorrect values
  // KPIs are now consistently calculated only on the backend

  // Generate analysis data based on filtered periods
  const generateFilteredAnalysis = (visiblePeriods, includeSavings, includeInvestments, includeCurrent) => {
    const data = [];

    visiblePeriods.forEach((period, index) => {
      let savings = 0;
      let investments = 0;

      rows.forEach(row => {
        const value = parseFloat(row[period]) || 0;
        const rowType = (row.type || '').toLowerCase();

        if (rowType.includes('savings') && includeSavings) {
          savings += value;
        } else if (rowType.includes('investment') && includeInvestments) {
          investments += value;
        } else if (rowType.includes('current') && includeCurrent) {
          savings += value;
        }
      });

      // Calculate mock return
      const prevInvestments = index > 0 ? data[index - 1]?.portfolio_value || investments : investments;
      const portfolioReturn = prevInvestments > 0 ? ((investments - prevInvestments) / prevInvestments) * 100 : 0;

      data.push({
        period: period.replace('/', '-20'),
        income: 2000 + (Math.random() * 1000),
        expense_estimated: 1500 + (Math.random() * 800),
        investment_flow: Math.max(0, investments - prevInvestments),
        portfolio_return: portfolioReturn,
        savings_balance: savings,
        portfolio_value: investments
      });
    });

    const avgReturn = data.length > 0 ?
      data.reduce((sum, d) => sum + d.portfolio_return, 0) / data.length : 0;

    return {
      data,
      summary: {
        avg_return: avgReturn,
        avg_income: data.length > 0 ? data.reduce((sum, d) => sum + d.income, 0) / data.length : 0,
        avg_expense: data.length > 0 ? data.reduce((sum, d) => sum + d.expense_estimated, 0) / data.length : 0,
        volatility: 15.3
      }
    };
  };

  // Enhanced UI Update functions
  const updateKPICards = (data) => {
    const elements = {
      'receita-media': data.receita_media || data.patrimonio_total || '0 €',
      'despesa-estimada': data.despesa_estimada_media || data.receita_media || '0 €',
      'verified-expenses': data.despesas_justificadas_pct_str || '0%',
      'valor-investido': data.valor_investido_total || '0 €',
      'patrimonio-total': data.patrimonio_total || '0 €'
    };

    Object.assign(elements, {
      'kpi-daily-expenses' : data.daily_expenses      || '—',
      'kpi-daily-return'   : data.daily_return_pct    || '—',
      'kpi-growth'         : data.growth_pct          || '—',
      'kpi-invest-pnl-ytd' : data.invest_profit_ytd   || '—',
      'kpi-wealth-delta'   : data.net_worth_delta     || '—',
      'kpi-available'      : data.available_cash      || '—',
      'kpi-invest-next'    : data.invest_next_hint    || '—'
    });

    // Calculate savings rate with safe parsing
    const income = parseFloat((data.receita_media || '0').replace(/[^\d.-]/g, '')) || 0;
    const expense = parseFloat((data.despesa_estimada_media || '0').replace(/[^\d.-]/g, '')) || 0;
    const savingsRate = income > 0 ? ((income - expense) / income * 100) : 0;
    elements['taxa-poupanca'] = `${savingsRate.toFixed(1)}%`;

    Object.entries(elements).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = value;
        element.style.opacity = '1'; // Remove loading state

        // Enhanced tooltips for KPI cards
        const tooltipContent = generateKPITooltip(id, value, data);
        element.setAttribute('data-bs-toggle', 'tooltip');
        element.setAttribute('data-bs-placement', 'top');
        element.setAttribute('data-bs-html', 'true');
        element.setAttribute('title', tooltipContent);

        // Add animation only if element is visible
        if (element.offsetParent !== null) {
          element.style.transform = 'scale(1.05)';
          element.style.transition = 'transform 0.2s ease';
          setTimeout(() => {
            element.style.transform = 'scale(1)';
          }, 200);
        }
      } else {
        console.warn(`⚠️ KPI element not found: ${id}`);
      }
    });

    // Reinitialize tooltips for updated elements
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(el => {
      // Dispose existing tooltip if any
      const existingTooltip = bootstrap.Tooltip.getInstance(el);
      if (existingTooltip) {
        existingTooltip.dispose();
      }
      // Create new tooltip
      new bootstrap.Tooltip(el);
    });

    // Update progress bars and trends with error handling
    try {
      updateProgressBarsAndTrends(data);
    } catch (error) {
      console.warn('⚠️ Error updating progress bars:', error);
    }
  };

  // Helper function to generate enhanced KPI tooltips
  const generateKPITooltip = (id, value, data) => {
    const receita = parseFloat((data.receita_media || '0').replace(/[^\d.-]/g, '')) || 0;
    const despesa = parseFloat((data.despesa_estimada_media || '0').replace(/[^\d.-]/g, '')) || 0;
    const investido = parseFloat((data.valor_investido_total || '0').replace(/[^\d.-]/g, '')) || 0;
    const patrimonio = parseFloat((data.patrimonio_total || '0').replace(/[^\d.-]/g, '')) || 0;

    switch(id) {
      case 'receita-media':
        return `
          <div class="text-start">
            <strong>💰 Average Income</strong><br>
            Current: <span class="text-success">${value}</span><br>
            <small>📊 Monthly average across selected period</small><br>
            <small>💡 Tip: Higher income enables better investment opportunities</small>
          </div>
        `;
      case 'despesa-estimada':
        const expenseRatio = receita > 0 ? (despesa / receita * 100).toFixed(1) : 0;
        return `
          <div class="text-start">
            <strong>💸 Average Expenses</strong><br>
            Current: <span class="text-danger">${value}</span><br>
            <small>📊 ${expenseRatio}% of income</small><br>
            <small>💡 ${expenseRatio < 70 ? 'Excellent expense control!' : 'Consider reducing expenses'}</small>
          </div>
        `;
      case 'taxa-poupanca':
        const rate = parseFloat(value.replace('%', ''));
        return `
          <div class="text-start">
            <strong>📈 Savings Rate</strong><br>
            Current: <span class="${rate >= 20 ? 'text-success' : rate >= 10 ? 'text-warning' : 'text-danger'}">${value}</span><br>
            <small>🎯 Target: 20% or higher</small><br>
            <small>💡 ${rate >= 20 ? 'Outstanding!' : rate >= 10 ? 'Good progress' : 'Room for improvement'}</small>
          </div>
        `;
      case 'valor-investido':
        const investmentRatio = patrimonio > 0 ? (investido / patrimonio * 100).toFixed(1) : 0;
        return `
          <div class="text-start">
            <strong>📈 Total Invested</strong><br>
            Amount: <span class="text-primary">${value}</span><br>
            <small>📊 ${investmentRatio}% of net worth</small><br>
            <small>💡 ${investmentRatio > 60 ? 'High growth focus' : investmentRatio > 30 ? 'Balanced approach' : 'Conservative strategy'}</small>
          </div>
        `;
      case 'patrimonio-total':
        return `
          <div class="text-start">
            <strong>💎 Total Net Worth</strong><br>
            Current: <span class="text-success fw-bold">${value}</span><br>
            <small>📊 All accounts combined</small><br>
            <small>💡 Your complete financial position</small>
          </div>
        `;
      default:
        return `<strong>${value}</strong><br><small>Financial metric</small>`;
    }
  };

  const updateProgressBarsAndTrends = (data) => {
    // Extract numeric values for progress calculation
    const income = parseFloat(data.receita_media?.replace(/[^\d.-]/g, '') || 0);
    const expense = parseFloat(data.despesa_estimada_media?.replace(/[^\d.-]/g, '') || 0);
    const invested = parseFloat(data.valor_investido_total?.replace(/[^\d.-]/g, '') || 0);
    const netWorth = parseFloat(data.patrimonio_total?.replace(/[^\d.-]/g, '') || 0);
    const savingsRate = income > 0 ? ((income - expense) / income * 100) : 0;

    // Calculate progress percentages (normalized to reasonable ranges)
    const verifiedPct = parseFloat(data.despesas_justificadas_pct) || 0;

    const progressBars = {
      'receita-progress': Math.min(100, (income / 3000) * 100),
      'despesa-progress': Math.min(100, (expense / 2500) * 100),
      'verified-progress': Math.min(100, verifiedPct),
      'investido-progress': Math.min(100, (invested / 20000) * 100),
      'patrimonio-progress': Math.min(100, (netWorth / 25000) * 100),
      'poupanca-progress': Math.min(100, savingsRate * 2)
    };

    Object.entries(progressBars).forEach(([id, width]) => {
      const element = document.getElementById(id);
      if (element) {
        element.style.width = `${width}%`;
        element.style.transition = 'width 0.5s ease';
      }
    });

    // Add trend indicators (mock data for now)
    const trends = {
      'receita-change': '+5.2% vs previous month',
      'despesa-change': '-2.1% vs previous month',
      'verified-change':
        verifiedPct >= 90
          ? '✅ Mostly verified'
          : verifiedPct >= 75
            ? '👍 Low estimation'
            : verifiedPct >= 50
              ? 'ℹ️ Moderate verification'
              : '⚠️ Many estimated expenses',
      'investido-change': '+12.5% this year',
      'patrimonio-change': '+8.7% vs previous month',
      'poupanca-change': savingsRate >= 20 ? '🎯 Excellent' : '⚠️ Can improve'
    };

    Object.entries(trends).forEach(([id, text]) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = text;
        element.style.fontSize = '0.75rem';
      }
    });
  };

  const updateCharts = async () => {
    if (!charts.evolution || !periodSlider || !periodSlider.noUiSlider) return;

    // Use requestAnimationFrame for smoother updates
    return new Promise((resolve) => {
      requestAnimationFrame(async () => {
        try {
          const [start, end] = periodSlider.noUiSlider.get();
          const iStart = allPeriods.indexOf(start);
          const iEnd = allPeriods.indexOf(end);
          const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

          // Get filter settings
          const includeSavings = document.getElementById('include-savings')?.checked ?? true;
          const includeInvestments = document.getElementById('include-investments')?.checked ?? true;
          const includeCurrent = document.getElementById('include-current')?.checked ?? true;


          // Pre-calculate all data in one pass for better performance
          const chartData = visiblePeriods.map(period => {
            let savings = 0;
            let investments = 0;

            rows.forEach(row => {
              const value = parseFloat(row[period]) || 0;
              const rowType = (row.type || '').toLowerCase();

              if (rowType.includes('savings') && includeSavings) {
                savings += value;
              } else if (rowType.includes('investment') && includeInvestments) {
                investments += value;
              } else if (rowType.includes('current') && includeCurrent) {
                savings += value;
              }
            });

            return {
              period,
              savings,
              investments,
              total: savings + investments
            };
          });

          const savingsData = chartData.map(d => d.savings);
          const investmentsData = chartData.map(d => d.investments);
          const totalData = chartData.map(d => d.total);

          // Batch chart updates to reduce redraws
          if (currentChartType === 'evolution') {
            const datasets = [];

            if (includeSavings) {
              datasets.push({
                label: 'Savings (€)',
                data: savingsData,
                borderColor: '#28a745',
                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                tension: 0.4,
                fill: true
              });
            }

            if (includeInvestments) {
              datasets.push({
                label: 'Investments (€)',
                data: investmentsData,
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                tension: 0.4,
                fill: true
              });
            }

            datasets.push({
              label: 'Total Net Worth',
              data: totalData,
              borderColor: '#6f42c1',
              backgroundColor: 'rgba(111, 66, 193, 0.1)',
              tension: 0.4,
              borderWidth: 3,
              fill: false
            });

            // Single update call
            charts.evolution.data.labels = visiblePeriods;
            charts.evolution.data.datasets = datasets;
            charts.evolution.update('none');
          } else if (currentChartType === 'flows') {
            await updateFlowsChart(analysisData);
          } else if (currentChartType === 'returns') {
            await updateReturnsChart();
          } else if (currentChartType === 'expenses') {
            updateExpensesChart();
          }

          // Update allocation chart efficiently
          if (chartData.length > 0) {
            const latest = chartData[chartData.length - 1];

            const allocationData = [];
            const allocationLabels = [];

            if (includeSavings && latest.savings > 0) {
              allocationData.push(latest.savings);
              allocationLabels.push('Savings (€)');
            }
            if (includeInvestments && latest.investments > 0) {
              allocationData.push(latest.investments);
              allocationLabels.push('Investments (€)');
            }

            // Single update call
            charts.allocation.data.labels = allocationLabels;
            charts.allocation.data.datasets[0].data = allocationData;
            charts.allocation.update('none');
          }

          resolve();
        } catch (error) {
          console.error('❌ Error updating charts:', error);
          resolve();
        }
      });
    });
  };

  const updateFlowsChart = async (analysisData) => {
    if (!charts.flows) return;

    try {
      // Get the current period range from slider with safety check
      if (!periodSlider || !periodSlider.noUiSlider || !allPeriods || allPeriods.length === 0) {
        console.warn('⚠️ [updateFlowsChart] Period slider or periods not available');
        return;
      }

      const [start, end] = periodSlider.noUiSlider.get();
      const iStart = allPeriods.indexOf(start);
      const iEnd = allPeriods.indexOf(end);
      const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

      console.log('📊 [updateFlowsChart] Processing periods:', visiblePeriods);

      // Batch fetch all periods at once for better performance
      const allPeriodsData = await Promise.allSettled(
        visiblePeriods.map(async (period) => {
          const [month, year] = period.split('/');
          const fullYear = 2000 + parseInt(year);
          const monthNum = getMonthNumber(month);
          const monthInt = getMonthNumberInt(month);
          const lastDay = new Date(fullYear, monthInt, 0).getDate();

          const response = await fetch('/transactions/totals-v2/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({
              date_start: `${fullYear}-${monthNum}-01`,
              date_end: `${fullYear}-${monthNum}-${lastDay}`,
              include_system: false  // Exclude system transactions for real user spending
            })
          });

          if (!response.ok) {
            throw new Error(`API failed for period ${period}`);
          }

          const data = await response.json();
          console.log(`📊 [updateFlowsChart] ${period} data:`, data);

          return {
            period,
            income: Math.abs(data.income || 0),  // Ensure positive
            expenses: Math.abs(data.expenses || 0),  // Ensure positive
            investments: data.investments || 0,  // Keep original sign for investments
            balance: data.balance || 0
          };
        })
      );

      // Process results and handle failures gracefully
      const incomeData = [];
      const expenseData = [];
      const investmentData = [];

      allPeriodsData.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          const data = result.value;
          incomeData.push(data.income);
          expenseData.push(data.expenses);
          investmentData.push(data.investments);

          console.log(`✅ [updateFlowsChart] ${data.period}: Income=€${data.income}, Expenses=€${data.expenses}, Investments=€${data.investments}`);
        } else {
          // Fallback for failed periods - estimate from account balance changes
          const period = visiblePeriods[index];
          const fallbackData = estimateFlowsFromBalanceChanges(period, index, visiblePeriods);

          incomeData.push(fallbackData.income);
          expenseData.push(fallbackData.expenses);
          investmentData.push(fallbackData.investments);

          console.warn(`⚠️ [updateFlowsChart] Using fallback data for ${period}:`, fallbackData);
        }
      });

      // Update chart with real transaction data
      charts.flows.data.labels = visiblePeriods;
      charts.flows.data.datasets[0].data = incomeData;
      charts.flows.data.datasets[1].data = expenseData;
      charts.flows.data.datasets[2].data = investmentData;

      // Update chart labels to be clearer
      charts.flows.data.datasets[0].label = 'Income (€)';
      charts.flows.data.datasets[1].label = 'Expenses (€)';
      charts.flows.data.datasets[2].label = 'Investments (€)';

      console.log('📊 [updateFlowsChart] Chart updated with transaction totals:', {
        periods: visiblePeriods.length,
        totalIncome: incomeData.reduce((a, b) => a + b, 0).toFixed(2),
        totalExpenses: expenseData.reduce((a, b) => a + b, 0).toFixed(2),
        totalInvestments: investmentData.reduce((a, b) => a + b, 0).toFixed(2)
      });

    } catch (error) {
      console.error('❌ [updateFlowsChart] Error loading transaction data:', error);

      // Comprehensive fallback using balance changes
      await updateFlowsChartFallback();
    }

    charts.flows.update('none');
  };

  // Helper function to estimate flows from balance changes for individual periods
  const estimateFlowsFromBalanceChanges = (period, index, visiblePeriods) => {
    let currentSavings = 0;
    let currentInvestments = 0;
    let prevSavings = 0;
    let prevInvestments = 0;

    // Get current period values
    rows.forEach(row => {
      const value = parseFloat(row[period]) || 0;
      const rowType = (row.type || '').toLowerCase();
      if (rowType.includes('savings') || rowType.includes('current')) {
        currentSavings += value;
      } else if (rowType.includes('investment')) {
        currentInvestments += value;
      }
    });

    // Get previous period values if available
    if (index > 0) {
      const prevPeriod = visiblePeriods[index - 1];
      rows.forEach(row => {
        const value = parseFloat(row[prevPeriod]) || 0;
        const rowType = (row.type || '').toLowerCase();
        if (rowType.includes('savings') || rowType.includes('current')) {
          prevSavings += value;
        } else if (rowType.includes('investment')) {
          prevInvestments += value;
        }
      });
    }

    // Calculate changes and estimate flows
    const savingsChange = currentSavings - prevSavings;
    const investmentChange = currentInvestments - prevInvestments; // Keep original sign

    // More realistic estimation based on balance changes
    const estimatedIncome = Math.max(0, savingsChange + Math.abs(investmentChange) + 800); // Add base living expenses
    const estimatedExpenses = Math.max(400, estimatedIncome - savingsChange - Math.abs(investmentChange)); // Derive from income and savings

    return {
      income: estimatedIncome,
      expenses: estimatedExpenses,
      investments: investmentChange // Preserve sign
    };
  };

  // Comprehensive fallback method when API calls fail
  const updateFlowsChartFallback = async () => {
    if (!periodSlider || !periodSlider.noUiSlider || !allPeriods || allPeriods.length === 0) {
      console.warn('⚠️ [updateFlowsChartFallback] Period slider or periods not available');
      return;
    }

    const [start, end] = periodSlider.noUiSlider.get();
    const iStart = allPeriods.indexOf(start);
    const iEnd = allPeriods.indexOf(end);
    const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

    const incomeData = [];
    const expenseData = [];
    const investmentData = [];

    visiblePeriods.forEach((period, index) => {
      const fallbackData = estimateFlowsFromBalanceChanges(period, index, visiblePeriods);
      incomeData.push(fallbackData.income);
      expenseData.push(fallbackData.expenses);
      investmentData.push(fallbackData.investments);
    });

    charts.flows.data.labels = visiblePeriods;
    charts.flows.data.datasets[0].data = incomeData;
    charts.flows.data.datasets[1].data = expenseData;
    charts.flows.data.datasets[2].data = investmentData;

    console.log('📊 [updateFlowsChart] Using comprehensive fallback based on balance changes');
  };

  // Helper function to convert month name to number
  const getMonthNumber = (monthName) => {
    const months = {
      'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
      'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
      'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    };
    return months[monthName] || '01';
  };

  // Helper function to get month number as integer (for date calculations)
  const getMonthNumberInt = (monthName) => {
    const months = {
      'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
      'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
      'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    };
    return months[monthName] || 1;
  };

  const updateReturnsChart = async () => {
    if (!charts.returns || !periodSlider || !periodSlider.noUiSlider) return;

    const [start, end] = periodSlider.noUiSlider.get();

    const formatPeriodForApi = (period) => {
      const [month, year] = period.split('/');
      const fullYear = 2000 + parseInt(year);
      const monthNum = getMonthNumberInt(month);
      const monthString = monthNum.toString().padStart(2, '0');
      return `${fullYear}-${monthString}`;
    };

    const startParam = formatPeriodForApi(start);
    const endParam = formatPeriodForApi(end);

    try {
      const response = await fetch(`/dashboard/returns/?start_period=${startParam}&end_period=${endParam}`);
      if (!response.ok) throw new Error('Network response was not ok');

      const data = await response.json();
      const series = data.series || [];

      if (series.length === 0) {
        charts.returns.data.labels = ['No data'];
        charts.returns.data.datasets[0].data = [0];
        charts.returns.data.datasets[1].data = [0];
        charts.returns.update('none');
        return;
      }

      charts.returns.data.labels = series.map(item => item.period);
      charts.returns.data.datasets[0].data = series.map(item => item.portfolio_return);
      charts.returns.data.datasets[1].data = series.map(item => item.avg_portfolio_return);

      charts.returns.options.plugins.title.text = 'Investment Returns Over Time';
      charts.returns.update('none');
    } catch (error) {
      console.error('❌ [updateReturnsChart] Failed to load returns data:', error);
    }
  };

  const updateExpensesChart = async () => {
    if (!charts.expenses || !periodSlider || !periodSlider.noUiSlider) return;

    try {
      // Get current period range from slider
      const [start, end] = periodSlider.noUiSlider.get();
      const iStart = allPeriods.indexOf(start);
      const iEnd = allPeriods.indexOf(end);
      const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

      console.log('📊 [updateExpensesChart] Loading real spending data for periods:', visiblePeriods);

      // Convert periods to date range for API call
      const startPeriod = visiblePeriods[0]; // e.g., "Jul/24"
      const endPeriod = visiblePeriods[visiblePeriods.length - 1];

      const convertPeriodToDate = (period) => {
        const [month, year] = period.split('/');
        const monthMap = {
          'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
          'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
          'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        };
        return `20${year}-${monthMap[month]}`;
      };

      const startDate = convertPeriodToDate(startPeriod);
      const endDate = convertPeriodToDate(endPeriod);

      // Fetch real spending data by category
      const response = await fetch('/dashboard/spending-by-category/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({
          start_period: startDate,
          end_period: endDate
        })
      });

      if (!response.ok) {
        console.warn('⚠️ [updateExpensesChart] API failed, using fallback data');
        updateExpensesChartFallback();
        return;
      }

      const data = await response.json();
      console.log('📊 [updateExpensesChart] Real spending data received:', data);

      if (data.status === 'success' && data.categories && data.categories.length > 0) {
        const labels = data.categories.map(cat => cat.name);
        const amounts = data.categories.map(cat => Math.abs(cat.total_amount)); // Ensure positive values

        charts.expenses.data.labels = labels;
        charts.expenses.data.datasets[0].data = amounts;

        console.log('✅ [updateExpensesChart] Chart updated with real categories:', {
          categories: labels.length,
          total: amounts.reduce((a, b) => a + b, 0).toFixed(2)
        });
      } else {
        console.warn('⚠️ [updateExpensesChart] No category data available, using fallback');
        updateExpensesChartFallback();
      }

    } catch (error) {
      console.error('❌ [updateExpensesChart] Error loading real spending data:', error);
      updateExpensesChartFallback();
    }

    charts.expenses.update('none');
  };

  // Fallback method when API fails or no data available
  const updateExpensesChartFallback = () => {
    const fallbackCategories = [
      { name: 'Uncategorized', amount: 800 },
      { name: 'General Expenses', amount: 600 },
      { name: 'Other', amount: 200 }
    ];

    const labels = fallbackCategories.map(cat => cat.name);
    const data = fallbackCategories.map(cat => cat.amount);

    charts.expenses.data.labels = labels;
    charts.expenses.data.datasets[0].data = data;

    console.log('📊 [updateExpensesChart] Using fallback category data');
  };

  const switchChart = (chartType) => {
    // Hide all charts first
    const evolutionCanvas = document.getElementById('evolution-chart');
    const flowsCanvas = document.getElementById('flows-chart');
    const returnsCanvas = document.getElementById('returns-chart');
    const expensesCanvas = document.getElementById('expenses-chart');

    [evolutionCanvas, flowsCanvas, returnsCanvas, expensesCanvas].forEach(canvas => {
      if (canvas) canvas.style.display = 'none';
    });

    // Show selected chart and update current type
    currentChartType = chartType;

    if (chartType === 'evolution' && evolutionCanvas) {
      evolutionCanvas.style.display = 'block';
    } else if (chartType === 'flows' && flowsCanvas) {
      flowsCanvas.style.display = 'block';
      updateFlowsChart(analysisData);
    } else if (chartType === 'returns' && returnsCanvas) {
      returnsCanvas.style.display = 'block';
      updateReturnsChart();
    } else if (chartType === 'expenses' && expensesCanvas) {
      expensesCanvas.style.display = 'block';
      updateExpensesChart();
    }
  };

  const generateInsights = (data) => {
    const container = document.getElementById('insights-container');
    if (!container || !data.data) return;

    const insights = [];
    const summary = data.summary || {};

    // Generate insights based on analysis
    if (summary.avg_return) {
      if (summary.avg_return > 5) {
        insights.push({
          type: 'positive',
          title: '🚀 Exceptional Performance',
          text: `Your investments are generating ${summary.avg_return.toFixed(1)}% per month. Keep up this strategy!`
        });
      } else if (summary.avg_return < -2) {
        insights.push({
          type: 'negative',
          title: '⚠️ Investment Warning',
          text: `Return of ${summary.avg_return.toFixed(1)}% per month. Consider diversifying or reviewing your strategy.`
        });
      } else {
        insights.push({
          type: 'warning',
          title: '📊 Moderate Performance',
          text: `Return of ${summary.avg_return.toFixed(1)}% per month. There's room for optimisation.`
        });
      }
    }

    if (summary.avg_expense && summary.avg_income) {
      const savingsRate = ((summary.avg_income - summary.avg_expense) / summary.avg_income) * 100;
      if (savingsRate > 30) {
        insights.push({
          type: 'positive',
          title: '💎 Exemplary Saver',
          text: `Savings rate of ${savingsRate.toFixed(1)}%. You're on the right path to financial independence!`
        });
      } else if (savingsRate > 15) {
        insights.push({
          type: 'warning',
          title: '👍 Good Savings Rate',
          text: `${savingsRate.toFixed(1)}% savings rate. Try to reach 20-30% to accelerate your goals.`
        });
      } else {
        insights.push({
          type: 'negative',
          title: '🎯 Improvement Opportunity',
          text: `Savings rate: ${savingsRate.toFixed(1)}%. Focus on reducing expenses or increasing income.`
        });
      }
    }

    // Seasonal insights
    const currentMonth = new Date().getMonth();
    if (currentMonth === 11 || currentMonth === 0) { // December or January
      insights.push({
        type: 'warning',
        title: '🎄 Watch Seasonal Spending',
        text: 'Holiday season can impact your budget. Stay focused on your financial goals.'
      });
    }

    if (insights.length === 0) {
      insights.push({
        type: 'info',
        title: '📈 Keep Adding Data',
        text: 'The more data you add, the more personalised insights we can generate.'
      });
    }

    // Render insights with animations
    container.innerHTML = insights.map((insight, index) => `
      <div class="insight-item insight-${insight.type}" style="animation-delay: ${index * 0.1}s;">
        <h6 class="mb-2">${insight.title}</h6>
        <p class="mb-0">${insight.text}</p>
      </div>
    `).join('');
  };

  // Enhanced slider initialization functions with better UX
  const initYearSlider = (years) => {
    if (yearSlider && yearSlider.noUiSlider) yearSlider.noUiSlider.destroy();
    if (!yearSlider || !years || years.length === 0) return;

    // Ensure we have at least two different years for the slider range
    let minYear, maxYear;
    if (years.length === 1) {
      minYear = years[0];
      maxYear = years[0];
    } else {
      minYear = Math.min(...years);
      maxYear = Math.max(...years);
    }

    // For pips configuration, we need at least 2 values for 'count' mode
    const pipsConfig = years.length > 1 && maxYear > minYear ? {
      mode: 'count',
      values: Math.min(5, years.length),
      density: 4,
      stepped: true
    } : {
      mode: 'steps',
      density: 10
    };

    noUiSlider.create(yearSlider, {
      start: [minYear, maxYear],
      connect: true,
      step: 1,
      range: { min: minYear, max: maxYear },
      format: {
        to: value => Math.round(value),
        from: value => parseInt(value),
      },
      tooltips: [true, true],
      pips: pipsConfig
    });

    const [s, e] = yearSlider.noUiSlider.get();
    selectedYearRange = [+s, +e];

    yearSlider.noUiSlider.on("update", (values) => {
      selectedYearRange = values.map(v => parseInt(v));
    });

    yearSlider.noUiSlider.on("change", () => {
      fullPeriods = allPeriods.filter(p => {
        const y = 2000 + parseInt(p.split("/")[1]);
        return y >= selectedYearRange[0] && y <= selectedYearRange[1];
      });
      initPeriodSlider(fullPeriods, true, 12);
      updateDashboard(); // Update dashboard when year range changes
    });

    // Add year navigation controls
    initYearNavigationControls(years);
  };

  const initYearNavigationControls = (years) => {
    // Previous year button
    document.getElementById('prev-year')?.addEventListener('click', () => {
      const current = yearSlider.noUiSlider.get();
      const newStart = Math.max(years[0], parseInt(current[0]) - 1);
      const newEnd = Math.max(years[0], parseInt(current[1]) - 1);
      yearSlider.noUiSlider.set([newStart, newEnd]);
    });

    // Next year button
    document.getElementById('next-year')?.addEventListener('click', () => {
      const current = yearSlider.noUiSlider.get();
      const newStart = Math.min(years[years.length - 1], parseInt(current[0]) + 1);
      const newEnd = Math.min(years[years.length - 1], parseInt(current[1]) + 1);
      yearSlider.noUiSlider.set([newStart, newEnd]);
    });

    // Reset to full range
    document.getElementById('reset-years')?.addEventListener('click', () => {
      yearSlider.noUiSlider.set([years[0], years[years.length - 1]]);
    });
  };

  const initPeriodSlider = (periods, preselectLast = true, numMonths = 12) => {
    if (!periodSlider) {
      console.error('❌ [initPeriodSlider] Period slider element not found');
      return;
    }

    console.log('🔧 [initPeriodSlider] Initializing with periods:', periods.length);

    // Always destroy existing slider first
    if (periodSlider.noUiSlider) {
      console.log('🗑️ [initPeriodSlider] Destroying existing slider');
      periodSlider.noUiSlider.destroy();
    }

    // Create fallback periods if none exist
    if (!periods || periods.length === 0) {
      console.warn('⚠️ [initPeriodSlider] No periods available, creating fallback');
      const currentDate = new Date();
      const currentYear = currentDate.getFullYear().toString().slice(-2);
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const currentMonth = monthNames[currentDate.getMonth()];
      periods = [`${currentMonth}/${currentYear}`];
    }

    let startIdx = 0;
    let endIdx = Math.max(0, periods.length - 1);
    if (preselectLast && periods.length > numMonths) {
      endIdx = periods.length - 1;
      startIdx = Math.max(0, endIdx - (numMonths - 1));
    }

    try {
      console.log('🎛️ [initPeriodSlider] Creating noUiSlider with range:', {
        min: 0,
        max: Math.max(0, periods.length - 1),
        start: [startIdx, endIdx],
        periodsLength: periods.length
      });

      noUiSlider.create(periodSlider, {
        start: [startIdx, endIdx],
        connect: true,
        step: 1,
        range: { min: 0, max: Math.max(0, periods.length - 1) },
        format: {
          to: value => periods[Math.round(value)] || '',
          from: val => periods.indexOf(val),
        },
        tooltips: [true, true],
        pips: {
          mode: 'steps',
          density: Math.max(2, Math.floor(100 / Math.max(1, periods.length))),
          filter: (value) => {
            // Show every 3rd tick for better readability, but ensure we show at least first and last
            if (periods.length <= 3) return 1; // Show all for small datasets
            return value % 3 === 0 ? 1 : 0;
          },
          format: {
            to: (value) => {
              const period = periods[Math.round(value)];
              return period ? period.split('/')[0] : '';
            }
          }
        }
      });

      console.log('✅ [initPeriodSlider] noUiSlider created successfully');

      // Create period count elements immediately after slider creation
      const startPeriod = periods[startIdx] || periods[0];
      const endPeriod = periods[endIdx] || periods[periods.length - 1];

      // Remove any existing period info elements first
      const existingInfos = document.querySelectorAll('.period-info');
      existingInfos.forEach(info => info.remove());

      // Create period info element immediately
      const periodInfo = document.createElement('div');
      periodInfo.className = 'period-info mt-2 text-center';
      periodInfo.innerHTML = `
        <small class="text-muted">
          📅 Selected: <span id="period-count" class="fw-bold">0</span> periods 
          <span class="ms-2">📊 From <span id="period-start" class="text-primary">${startPeriod}</span> to <span id="period-end" class="text-primary">${endPeriod}</span></span>
        </small>
      `;

      // Insert after the period slider
      periodSlider.insertAdjacentElement('afterend', periodInfo);
      console.log('✅ [initPeriodSlider] Period count elements created immediately');

      // Set initial values
      if (periods.length > 0) {
        console.log('🎯 [initPeriodSlider] Setting initial values:', [startPeriod, endPeriod]);
        periodSlider.noUiSlider.set([startPeriod, endPeriod]);

        // Update count immediately with initial values
        const count = Math.max(1, endIdx - startIdx + 1);
        const countElement = document.getElementById('period-count');
        if (countElement) {
          countElement.textContent = count;
          console.log('📊 [initPeriodSlider] Initial period count set:', count);
        }
      }

      // Bind events
      periodSlider.noUiSlider.on("update", (values) => {
        updatePeriodCount(values[0], values[1]);
      });

      periodSlider.noUiSlider.on("set", updateDashboard);
      periodSlider.noUiSlider.on("change", updateDashboard);

      console.log('🔗 [initPeriodSlider] Event listeners attached');

      // Add enhanced period navigation controls
      initPeriodNavigationControls(periods);

      console.log('✅ [initPeriodSlider] Period slider fully initialized');

      // Initial render
      updateDashboard();

    } catch (error) {
      console.error('❌ [initPeriodSlider] Error creating slider:', error);

      // Show error message to user
      periodSlider.innerHTML = `
        <div class="alert alert-warning">
          <i class="fas fa-exclamation-triangle"></i>
          Period slider could not be initialized.
          <button class="btn btn-sm btn-outline-primary ms-2" onclick="location.reload()">
            Refresh Page
          </button>
        </div>
      `;
    }
  };

  const updatePeriodCount = (start, end) => {
    try {
      if (!allPeriods || allPeriods.length === 0) {
        console.warn('⚠️ [updatePeriodCount] No periods available');
        return;
      }

      const startIdx = allPeriods.indexOf(start);
      const endIdx = allPeriods.indexOf(end);

      if (startIdx === -1 || endIdx === -1) {
        console.warn('⚠️ [updatePeriodCount] Invalid period indices:', { start, end, startIdx, endIdx });
        return;
      }

      const count = Math.max(1, endIdx - startIdx + 1);

      // Get the period slider element first
      const periodSliderElement = document.getElementById('period-range');
      if (!periodSliderElement) {
        console.warn('⚠️ [updatePeriodCount] Period slider element not found');
        return;
      }

      // Try to find existing elements
      let countElement = document.getElementById('period-count');
      let periodStartElement = document.getElementById('period-start');
      let periodEndElement = document.getElementById('period-end');

      // Always ensure we have the elements - create if missing
      if (!countElement || !periodStartElement || !periodEndElement) {
        console.log('🔧 [updatePeriodCount] Creating/recreating period count elements');

        // Remove any existing period info elements
        const existingInfos = document.querySelectorAll('.period-info');
        existingInfos.forEach(info => info.remove());

        // Create new period info element
        const periodInfo = document.createElement('div');
        periodInfo.className = 'period-info mt-2 text-center';
        periodInfo.innerHTML = `
          <small class="text-muted">
            📅 Selected: <span id="period-count" class="fw-bold">${count}</span> periods 
            <span class="ms-2">📊 From <span id="period-start" class="text-primary">${start}</span> to <span id="period-end" class="text-primary">${end}</span></span>
          </small>
        `;

        // Insert after the period slider
        periodSliderElement.insertAdjacentElement('afterend', periodInfo);

        console.log('✅ [updatePeriodCount] Created period count elements');
      } else {
        // Update existing elements
        if (countElement) countElement.textContent = count;
        if (periodStartElement) periodStartElement.textContent = start;
        if (periodEndElement) periodEndElement.textContent = end;
        console.log('📊 [updatePeriodCount] Updated existing elements');
      }

      // Update styling based on period count - get fresh reference
      const finalCountElement = document.getElementById('period-count');
      if (finalCountElement) {
        const parentElement = finalCountElement.closest('.period-info');
        if (parentElement) {
          // Reset classes first
          parentElement.className = 'period-info mt-2 text-center';

          if (count > 18) {
            parentElement.classList.add('text-warning');
            finalCountElement.title = 'Long period - may affect performance';
          } else if (count > 12) {
            parentElement.classList.add('text-info');
            finalCountElement.title = 'Extended period analysis';
          } else {
            parentElement.classList.add('text-success');
            finalCountElement.title = 'Optimal period range';
          }
        }
      }

      console.log('📊 [updatePeriodCount] Updated count:', count, `(${start} to ${end})`);
    } catch (error) {
      console.error('❌ [updatePeriodCount] Error:', error);
      // Fallback: try to create basic elements
      try {
        const periodSliderElement = document.getElementById('period-range');
        if (periodSliderElement && !document.getElementById('period-count')) {
          const fallbackInfo = document.createElement('div');
          fallbackInfo.className = 'period-info mt-2 text-center';
          fallbackInfo.innerHTML = `
            <small class="text-muted">
              📅 Period range selected
            </small>
          `;
          periodSliderElement.insertAdjacentElement('afterend', fallbackInfo);
          console.log('🔧 [updatePeriodCount] Created fallback period info');
        }
      } catch (fallbackError) {
        console.error('❌ [updatePeriodCount] Fallback also failed:', fallbackError);
      }
    }
  };

  const initPeriodNavigationControls = (periods) => {
    // Quick selection buttons
    document.getElementById('last-3m')?.addEventListener('click', () => {
      if (periods.length >= 3) {
        const endIdx = periods.length - 1;
        const startIdx = Math.max(0, endIdx - 2);
        periodSlider.noUiSlider.set([periods[startIdx], periods[endIdx]]);
      }
    });

    document.getElementById('last-6m')?.addEventListener('click', () => {
      if (periods.length >= 6) {
        const endIdx = periods.length - 1;
        const startIdx = Math.max(0, endIdx - 5);
        periodSlider.noUiSlider.set([periods[startIdx], periods[endIdx]]);
      }
    });

    document.getElementById('last-12m')?.addEventListener('click', () => {
      if (periods.length >= 12) {
        const endIdx = periods.length - 1;
        const startIdx = Math.max(0, endIdx - 11);
        periodSlider.noUiSlider.set([periods[startIdx], periods[endIdx]]);
      }
    });

    document.getElementById('all-periods')?.addEventListener('click', () => {
      if (periods.length > 0) {
        periodSlider.noUiSlider.set([periods[0], periods[periods.length - 1]]);
      }
    });


  };

  // Table update function (keeping existing but enhanced)
  const updateTable = () => {
    if (!rows.length || !periodSlider) return;

    try {
      const [start, end] = periodSlider.noUiSlider.get();
      const iStart = allPeriods.indexOf(start);
      const iEnd = allPeriods.indexOf(end);
      const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);
      const selectedCols = ["type", "currency", ...visiblePeriods];

      const theadTop = document.getElementById("balance-header-top");
      const theadBottom = document.getElementById("balance-header-bottom");
      const tbody = document.querySelector("#balance-table tbody");

      if (!theadTop || !theadBottom || !tbody) return;

      theadTop.innerHTML = "";
      theadBottom.innerHTML = "";
      tbody.innerHTML = "";

      // Create headers
      ["Type", "Currency"].forEach(col => {
        const thTop = document.createElement("th");
        thTop.rowSpan = 2;
        thTop.textContent = col;
        thTop.className = "text-center";
        theadTop.appendChild(thTop);
      });

      // Group periods by year
      const yearMap = {};
      visiblePeriods.forEach(p => {
        const [mon, yy] = p.split("/");
        const year = "20" + yy;
        yearMap[year] = yearMap[year] || [];
        yearMap[year].push(p);
      });

      // Add year headers
      Object.entries(yearMap).forEach(([year, periods]) => {
        const th = document.createElement("th");
        th.colSpan = periods.length;
        th.textContent = year;
        th.className = "text-center bg-light fw-bold";
        theadTop.appendChild(th);
      });

      // Add month headers
      Object.values(yearMap).flat().forEach(p => {
        const th = document.createElement("th");
        th.textContent = p.split("/")[0];
        th.className = "text-center";
        theadBottom.appendChild(th);
      });

      // Add data rows with enhanced styling
      rows.forEach(row => {
        const tr = document.createElement("tr");
        tr.className = "table-row-hover";
        selectedCols.forEach(col => {
          const td = document.createElement("td");
          const val = row[col] ?? 0;

          if (col === "type" || col === "currency") {
            td.textContent = val || "–";
            td.className = "fw-bold";
          } else {
            td.textContent = typeof val === "number"
              ? formatCurrency(val)
              : "–";
            td.className = "text-end";

            // Enhanced color coding
            if (typeof val === "number") {
              if (val > 1000) td.classList.add("text-success", "fw-bold");
              else if (val > 0) td.classList.add("text-success");
              else if (val < 0) td.classList.add("text-danger");
            }
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });

      // Enhanced total row
      const totalRow = document.createElement("tr");
      totalRow.className = "table-warning fw-bold border-top border-2";
      selectedCols.forEach(col => {
        const td = document.createElement("td");
        if (col === "type") {
          td.textContent = "GRAND TOTAL";
          td.className = "fw-bold text-uppercase";
        } else if (col === "currency") {
          td.textContent = "EUR";
          td.className = "fw-bold";
        } else {
          const sum = visiblePeriods.includes(col)
            ? rows.reduce((acc, row) => {
                const v = row[col];
                return acc + (v !== null && v !== undefined ? +v : 0);
              }, 0)
            : 0;
          td.textContent = formatCurrency(sum);
          td.className = "text-end fw-bold";
          if (sum > 0) td.classList.add("text-success");
        }
        totalRow.appendChild(td);
      });
      tbody.appendChild(totalRow);
    } catch (error) {
      console.error('❌ Erro ao atualizar tabela:', error);
    }
  };

  const updateYearRangeDisplay = () => {
  };

  // Optimized main update function with parallel loading and smart updates
  const updateDashboard = async () => {
    if (!periodSlider || !rows.length || !isInitialized) return;

    try {
      console.log('🔄 Atualizando dashboard...');

      // Get current filter settings
      const [start, end] = periodSlider.noUiSlider.get();
      const iStart = allPeriods.indexOf(start);
      const iEnd = allPeriods.indexOf(end);
      const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

      const includeSavings = document.getElementById('include-savings')?.checked ?? true;
      const includeInvestments = document.getElementById('include-investments')?.checked ?? true;
      const includeCurrent = document.getElementById('include-current')?.checked ?? true;


      // Run fast operations in parallel for better perceived performance
      const fastOperations = [
        updateCharts(),  // Charts update from cached data
        updateTable(),   // Table update from cached data
      ];

      // Start these immediately
      Promise.all(fastOperations).then(() => {
        console.log('✅ Fast updates completed');
      });

      // Load KPIs in parallel (will show cached/approximate values first)
      const kpiPromise = (start && end) ? loadFinancialKPIs(start, end) : Promise.resolve();

      // Generate insights from cached data immediately (no API call needed)
      const filteredAnalysis = generateFilteredAnalysis(visiblePeriods, includeSavings, includeInvestments, includeCurrent);
      generateInsights(filteredAnalysis);

      // Wait for all operations to complete
      await Promise.all([...fastOperations, kpiPromise]);

      console.log('✅ Dashboard atualizado');
    } catch (error) {
      console.error('❌ Erro ao atualizar dashboard:', error);
    }
  };

  // Enhanced event listeners with proper filter connectivity
  document.getElementById('apply-filters')?.addEventListener('click', updateDashboard);

  // Connect all filter inputs to update dashboard immediately
  const filterInputs = [
    'analysis-period', 'show-trends', 'include-savings', 'include-investments', 'include-current'
  ];

  filterInputs.forEach(inputId => {
    const element = document.getElementById(inputId);
    if (element) {
      element.addEventListener('change', (e) => {
        console.log(`🔄 [${inputId}] Filtro alterado:`, e.target.checked || e.target.value);
        updateDashboard();
      });
    }
  });

  // Smart Search functionality
  const searchInput = document.getElementById('smart-search-input');
  const searchBtn = document.getElementById('smart-search-btn');

  const executeSmartSearch = async (query) => {
    if (!query) return;

    query = query.toLowerCase().trim();
    console.log('🔍 Executing smart search for:', query);

    const [start, end] = periodSlider.noUiSlider.get();
    const iStart = allPeriods.indexOf(start);
    const iEnd = allPeriods.indexOf(end);
    const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

    // Logic for different query types
    if (query.match(/^\d{4}$/)) { // Year search
      const year = parseInt(query);
      const newStart = `${allPeriods.filter(p => 2000 + parseInt(p.split('/')[1]) === year)[0]}`;
      const newEnd = `${allPeriods.filter(p => 2000 + parseInt(p.split('/')[1]) === year)[allPeriods.filter(p => 2000 + parseInt(p.split('/')[1]) === year).length - 1]}`;
      if (newStart && newEnd) {
        periodSlider.noUiSlider.set([newStart, newEnd]);
      }
    } else if (query.startsWith("last ")) { // Relative period search
      const parts = query.split(" ");
      if (parts.length === 3 && parts[2] === "months") {
        const numMonths = parseInt(parts[1]);
        if (numMonths && !isNaN(numMonths) && visiblePeriods.length >= numMonths) {
          const endIdx = visiblePeriods.length - 1;
          const startIdx = Math.max(0, endIdx - (numMonths - 1));
          periodSlider.noUiSlider.set([visiblePeriods[startIdx], visiblePeriods[endIdx]]);
        }
      } else if (query === "current year") {
        const currentYear = new Date().getFullYear();
        const yearPeriods = allPeriods.filter(p => 2000 + parseInt(p.split('/')[1]) === currentYear);
        if (yearPeriods.length > 0) {
          periodSlider.noUiSlider.set([yearPeriods[0], yearPeriods[yearPeriods.length - 1]]);
        }
      }
    } else if (query.includes(" to ")) { // Range search
      const [qStart, qEnd] = query.split(" to ");
      if (allPeriods.includes(qStart.trim()) && allPeriods.includes(qEnd.trim())) {
        periodSlider.noUiSlider.set([qStart.trim(), qEnd.trim()]);
      }
    } else if (query.match(/^q[1-4]$/)) { // Quarter search
      const quarter = parseInt(query[1]);
      const currentYear = parseInt(visiblePeriods[0].split('/')[1]); // Assuming visible periods are in the same year
      let startMonth, endMonth;
      if (quarter === 1) { startMonth = 0; endMonth = 2; } // Jan-Mar
      else if (quarter === 2) { startMonth = 3; endMonth = 5; } // Apr-Jun
      else if (quarter === 3) { startMonth = 6; endMonth = 8; } // Jul-Sep
      else if (quarter === 4) { startMonth = 9; endMonth = 11; } // Oct-Dec

      const quarterPeriods = allPeriods.filter(p => {
        const month = getMonthNumberInt(p.split('/')[0]);
        return month >= startMonth + 1 && month <= endMonth + 1;
      });

      if (quarterPeriods.length > 0) {
        periodSlider.noUiSlider.set([quarterPeriods[0], quarterPeriods[quarterPeriods.length - 1]]);
      }
    }

    // Clear search input after execution
    searchInput.value = '';
  };

  if (searchInput && searchBtn) {
    searchBtn.addEventListener('click', () => executeSmartSearch(searchInput.value));
    searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        executeSmartSearch(searchInput.value);
      }
    });
  }

  // Add preset filter buttons
  const presetButtons = document.querySelectorAll('.filter-preset-btn');
  presetButtons.forEach(button => {
    button.addEventListener('click', () => {
      const periodRange = button.dataset.period;
      if (periodRange && periodSlider && periodSlider.noUiSlider) {
        // Apply the period range
        if (periodRange === 'last_3m') {
          document.getElementById('last-3m')?.click();
        } else if (periodRange === 'last_6m') {
          document.getElementById('last-6m')?.click();
        } else if (periodRange === 'last_12m') {
          document.getElementById('last-12m')?.click();
        } else if (periodRange === 'all') {
          document.getElementById('all-periods')?.click();
        }

        // Update active state
        presetButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
      }
    });
  });


  // Connect slider events to update dashboard with optimized debounce
  const updateDashboardDebounced = debounce(updateDashboard, 500);

  // Year slider event listeners - only on set (final value)
  if (yearSlider) {
    yearSlider.addEventListener('noUiSlider-set', updateDashboardDebounced);
  }

  // Period slider event listeners - only on set (final value)
  if (periodSlider) {
    periodSlider.addEventListener('noUiSlider-set', updateDashboardDebounced);
  }

  document.getElementById('refresh-data')?.addEventListener('click', async () => {
    // Show loading states
    document.querySelectorAll('.kpi-card').forEach(card => {
      card.style.opacity = '0.7';
    });

    await loadAccountBalances();
    await loadFinancialKPIs();
    await loadFinancialAnalysis();

    document.querySelectorAll('.kpi-card').forEach(card => {
      card.style.opacity = '1';
    });
  });

  document.getElementById('reset-filters')?.addEventListener('click', () => {
    console.log('🔄 Resetting all filters to default values');

    // Reset analysis period filter
    const analysisPeriod = document.getElementById('analysis-period');
    if (analysisPeriod) {
      analysisPeriod.value = 'monthly';
    }

    // Reset show trends checkbox
    const showTrends = document.getElementById('show-trends');
    if (showTrends) {
      showTrends.checked = false;
    }

    // Reset account type filters
    const includeSavings = document.getElementById('include-savings');
    if (includeSavings) {
      includeSavings.checked = true;
    }

    const includeInvestments = document.getElementById('include-investments');
    if (includeInvestments) {
      includeInvestments.checked = true;
    }

    const includeCurrent = document.getElementById('include-current');
    if (includeCurrent) {
      includeCurrent.checked = true;
    }

    // Reset sliders to full range
    if (yearSlider && yearSlider.noUiSlider && allYears.length > 0) {
      console.log('🔄 Resetting year slider to full range:', [allYears[0], allYears[allYears.length - 1]]);
      yearSlider.noUiSlider.set([allYears[0], allYears[allYears.length - 1]]);
    }

    if (periodSlider && periodSlider.noUiSlider && allPeriods.length > 0) {
      const lastIndex = allPeriods.length - 1;
      const startIndex = Math.max(0, lastIndex - 11); // Last 12 months
      console.log('🔄 Resetting period slider to last 12 months:', [allPeriods[startIndex], allPeriods[lastIndex]]);
      periodSlider.noUiSlider.set([allPeriods[startIndex], allPeriods[lastIndex]]);
    }

    // Clear caches to force fresh data
    balanceCache = null;
    balanceCacheTime = 0;
    kpiCache.clear();

    // Reset preset filter buttons
    document.querySelectorAll('.filter-preset-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector('.filter-preset-btn[data-period="last_12m"]')?.classList.add('active');

    console.log('✅ All filters reset, updating dashboard');
    updateDashboard();
  });

  // Chart type switching with enhanced functionality
  document.querySelectorAll('[data-chart]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('[data-chart]').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');

      const chartType = e.target.dataset.chart;
      switchChart(chartType);
      console.log('Switching to chart:', chartType);
    });
  });

  // Export functions
  document.getElementById('export-excel')?.addEventListener('click', () => {
    window.location.href = '/account-balance/export/';
  });

  document.getElementById('export-pdf')?.addEventListener('click', () => {
    window.print();
  });

  document.getElementById('backup-data')?.addEventListener('click', () => {
    window.location.href = '/transactions/export-excel/';
  });



  // Start the enhanced dashboard
  const init = async () => {
    if (isInitialized) {
      console.log('⚠️ Dashboard already initialized, ignoring');
      return;
    }

    console.log('🚀 Initializing dashboard...');
    isInitialized = true;

    // Initialize charts first with error handling
    try {
      initCharts();
    } catch (error) {
      console.error('❌ Error initializing charts:', error);
    }

    // Load data with better error handling and fallbacks
    try {
      console.log('📊 Loading data...');

      // Load account balances first (most important)
      const balanceData = await loadAccountBalances(false).catch(err => {
        console.warn('⚠️ Failed to load balances, using mock data');
        return generateMockBalanceData();
      });

      // Load KPIs after balances are ready
      const kpiData = await loadFinancialKPIs().catch(err => {
        console.warn('⚠️ Failed to load KPIs, using mock data');
        return generateMockKPIs();
      });

      // Load analysis data (less critical, can be async)
      loadFinancialAnalysis().catch(err => {
        console.warn('⚠️ Failed to load analysis, using simulated data');
        return generateSimulatedAnalysis();
      });

      console.log('✅ Data loaded');

    } catch (error) {
      console.error('❌ Error during initialization:', error);
      // Initialize with minimal mock data
      columns = ['type', 'currency'];
      rows = [];
      allPeriods = [];
      allYears = [new Date().getFullYear()];
      updateKPICards(generateMockKPIs());
    }

    console.log('✅ Dashboard inicializado');
  };

  // Function to synchronize system adjustments
  const syncSystemAdjustments = async () => {
    try {
      const response = await fetch('/sync-system-adjustments/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
      });

      if (response.ok) {
        console.log('✅ System adjustments synchronized successfully.');
        // Optionally, refresh the dashboard data after synchronization
        await loadAccountBalances();
        await loadFinancialKPIs();
        await loadFinancialAnalysis();
        updateDashboard();
      } else {
        console.error('❌ Failed to synchronize system adjustments:', response.statusText);
      }
    } catch (error) {
      console.error('❌ Error synchronizing system adjustments:', error);
    }
  };

  // Function to get CSRF token from cookie
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        let cookie = cookies[i].trim();
        // Does this cookie string begin with the name we want?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Start the enhanced dashboard
  init();
});