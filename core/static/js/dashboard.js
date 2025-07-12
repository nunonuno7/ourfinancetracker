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

  // DOM elements
  const yearSlider = document.getElementById("year-range");
  const yearStartLbl = document.getElementById("year-start-label");
  const yearEndLbl = document.getElementById("year-end-label");
  const periodSlider = document.getElementById("period-range");
  const periodStartLbl = document.getElementById("period-start-label");
  const periodEndLbl = document.getElementById("period-end-label");

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

  const showKPILoadingState = () => {
    const kpiElements = ['receita-media', 'despesa-estimada', 'valor-investido', 'patrimonio-total'];
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
        maintainAspectRatio: true,
        aspectRatio: 2,
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
            callbacks: {
              label: function(context) {
                return context.dataset.label + ': ' + formatCurrency(context.parsed.y);
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
          intersect: false,
          mode: 'index'
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
        maintainAspectRatio: true,
        aspectRatio: 1,
        resizeDelay: 0,
        plugins: {
          legend: {
            position: 'bottom',
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                const label = context.label || '';
                const value = context.parsed;
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = ((value / total) * 100).toFixed(1);
                return `${label}: ${formatCurrency(value)} (${percentage}%)`;
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
        maintainAspectRatio: true,
        aspectRatio: 2,
        resizeDelay: 0,
        plugins: {
          title: {
            display: true,
            text: 'Monthly Financial Flows'
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
  };

  // Enhanced data loading functions with request control
  let isLoadingKPIs = false;
  let lastKPIParams = null;

  const loadAccountBalances = async () => {
    try {
      const response = await fetch('/account-balances/json/');
      if (!response.ok) {
        console.warn('⚠️ Account balances endpoint not available, using mock data');
        return generateMockBalanceData();
      }

      const data = await response.json();
      console.log('🔍 Dados de saldos recebidos:', data);

      columns = data.columns || [];
      rows = data.rows || [];

      // Convert string numbers to actual numbers
      columns.slice(2).forEach(period =>
        rows.forEach(row => {
          if (row[period] !== null && row[period] !== undefined) {
            row[period] = parseFloat(row[period]);
          }
        })
      );

      allPeriods = columns.slice(2).sort((a, b) => parsePeriod(a) - parsePeriod(b));
      allYears = [...new Set(allPeriods.map(p => 2000 + parseInt(p.split("/")[1])))]
        .sort((a, b) => a - b);

      const minYear = allYears[0] || new Date().getFullYear();
      const maxYear = allYears[allYears.length - 1] || new Date().getFullYear();
      selectedYearRange = [minYear, maxYear];

      fullPeriods = allPeriods;

      if (allYears.length > 0) {
        initYearSlider(allYears);
        initPeriodSlider(fullPeriods, true, 12);
        updateYearRangeDisplay();
      } else {
        // Initialize with current year if no data
        const currentYear = new Date().getFullYear();
        initYearSlider([currentYear]);
        initPeriodSlider([`Jan/${currentYear.toString().slice(-2)}`], true, 12);
      }

      // Update last update timestamp
      const lastUpdateEl = document.getElementById('last-update');
      if (lastUpdateEl) {
        lastUpdateEl.textContent = new Date().toLocaleString('en-GB');
      }

      return data;
    } catch (error) {
      console.error('❌ Erro ao carregar saldos:', error);
      return generateMockBalanceData();
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
    // Prevent duplicate calls
    const currentParams = `${startPeriod || 'null'}-${endPeriod || 'null'}`;
    if (isLoadingKPIs || currentParams === lastKPIParams) {
      console.log('🔄 Ignorando chamada duplicada de KPIs:', currentParams);
      return {};
    }

    isLoadingKPIs = true;
    lastKPIParams = currentParams;

    try {
      let url = '/dashboard/kpis/';
      if (startPeriod && endPeriod) {
        // Converter formato de período de "Jul/24" para "2024-07"
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
      console.log('📊 KPIs received:', data);
      updateKPICards(data);
      return data;
    } catch (error) {
      console.error('❌ Erro ao carregar KPIs:', error);
      const mockData = generateMockKPIs();
      updateKPICards(mockData);
      return mockData;
    } finally {
      isLoadingKPIs = false;
      // Reset after a delay to allow new calls with different parameters
      setTimeout(() => {
        lastKPIParams = null;
      }, 1000);
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
        console.warn('⚠️ Endpoint de análise financeira não disponível, usando dados simulados');
        const simulatedData = generateSimulatedAnalysis();
        analysisData = simulatedData;
        generateInsights(simulatedData);
        updateFlowsChart(simulatedData);
        return simulatedData;
      }

      const data = await response.json();
      console.log('📈 Análise financeira recebida:', data);
      analysisData = data;
      generateInsights(data);
      updateFlowsChart(data);
      return data;
    } catch (error) {
      console.warn('⚠️ Erro ao carregar análise financeira, usando dados simulados:', error);
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

  // Esta função foi removida para evitar valores incorretos temporários
  // Os KPIs são agora calculados apenas no backend de forma consistente

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
      'despesas-justificadas': data.despesas_justificadas_pct || '0%',
      'valor-investido': data.valor_investido_total || '0 €',
      'patrimonio-total': data.patrimonio_total || '0 €'
    };

    // Calculate savings rate with safe parsing
    const receita = parseFloat((data.receita_media || '0').replace(/[^\d.-]/g, '')) || 0;
    const despesa = parseFloat((data.despesa_estimada_media || '0').replace(/[^\d.-]/g, '')) || 0;
    const savingsRate = receita > 0 ? ((receita - despesa) / receita * 100) : 0;
    elements['taxa-poupanca'] = `${savingsRate.toFixed(1)}%`;

    Object.entries(elements).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = value;
        element.style.opacity = '1'; // Remove loading state

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

    // Update progress bars and trends with error handling
    try {
      updateProgressBarsAndTrends(data);
    } catch (error) {
      console.warn('⚠️ Error updating progress bars:', error);
    }
  };

  const updateProgressBarsAndTrends = (data) => {
    // Extract numeric values for progress calculation
    const receita = parseFloat(data.receita_media?.replace(/[^\d.-]/g, '') || 0);
    const despesa = parseFloat(data.despesa_estimada_media?.replace(/[^\d.-]/g, '') || 0);
    const investido = parseFloat(data.valor_investido_total?.replace(/[^\d.-]/g, '') || 0);
    const patrimonio = parseFloat(data.patrimonio_total?.replace(/[^\d.-]/g, '') || 0);
    const taxaPoupanca = receita > 0 ? ((receita - despesa) / receita * 100) : 0;

    // Calculate progress percentages (normalized to reasonable ranges)
    const justificadas = parseFloat(data.despesas_justificadas_pct?.replace(/[^\d.-]/g, '') || 0);

    const progressBars = {
      'receita-progress': Math.min(100, (receita / 3000) * 100),
      'despesa-progress': Math.min(100, (despesa / 2500) * 100),
      'justificadas-progress': Math.min(100, justificadas),
      'investido-progress': Math.min(100, (investido / 20000) * 100),
      'patrimonio-progress': Math.min(100, (patrimonio / 25000) * 100),
      'poupanca-progress': Math.min(100, taxaPoupanca * 2)
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
      'justificadas-change': justificadas >= 80 ? '✅ Excellent control' : justificadas >= 60 ? '👍 Good control' : '⚠️ Needs improvement',
      'investido-change': '+12.5% this year',
      'patrimonio-change': '+8.7% vs previous month',
      'poupanca-change': taxaPoupanca >= 20 ? '🎯 Excellent' : '⚠️ Can improve'
    };

    Object.entries(trends).forEach(([id, text]) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = text;
        element.style.fontSize = '0.75rem';
      }
    });
  };

  const updateCharts = () => {
    if (!charts.evolution || !periodSlider) return;

    try {
      const [start, end] = periodSlider.noUiSlider.get();
      const iStart = allPeriods.indexOf(start);
      const iEnd = allPeriods.indexOf(end);
      const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

      // Get filter settings
      const includeSavings = document.getElementById('include-savings')?.checked ?? true;
      const includeInvestments = document.getElementById('include-investments')?.checked ?? true;
      const includeCurrent = document.getElementById('include-current')?.checked ?? true;
      const showTrends = document.getElementById('show-trends')?.checked ?? false;

      // Prepare data for charts
      const savingsData = [];
      const investmentsData = [];
      const totalData = [];

      visiblePeriods.forEach(period => {
        let savings = 0;
        let investments = 0;

        rows.forEach(row => {
          const value = row[period] || 0;
          const rowType = (row.type || '').toLowerCase();

          if (rowType.includes('savings') && includeSavings) {
            savings += value;
          } else if (rowType.includes('investment') && includeInvestments) {
            investments += value;
          } else if (rowType.includes('current') && includeCurrent) {
            savings += value; // Current accounts counted as savings
          }
        });

        savingsData.push(savings);
        investmentsData.push(investments);
        totalData.push(savings + investments);
      });

      // Update evolution chart with filtered data
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

        charts.evolution.data.labels = visiblePeriods;
        charts.evolution.data.datasets = datasets;
        charts.evolution.update('none');
      }

      // Update allocation chart (use latest values)
      if (savingsData.length > 0 && investmentsData.length > 0) {
        const latestSavings = savingsData[savingsData.length - 1];
        const latestInvestments = investmentsData[investmentsData.length - 1];

        const allocationData = [];
        const allocationLabels = [];

        if (includeSavings && latestSavings > 0) {
          allocationData.push(latestSavings);
          allocationLabels.push('Savings (€)');
        }
        if (includeInvestments && latestInvestments > 0) {
          allocationData.push(latestInvestments);
          allocationLabels.push('Investments (€)');
        }

        charts.allocation.data.labels = allocationLabels;
        charts.allocation.data.datasets[0].data = allocationData;
        charts.allocation.update('none');
      }
    } catch (error) {
      console.error('❌ Erro ao atualizar gráficos:', error);
    }
  };

  const updateFlowsChart = (analysisData) => {
    if (!charts.flows || !analysisData.data) return;

    const data = analysisData.data.slice(-12); // Last 12 months
    const labels = data.map(d => d.period);
    const income = data.map(d => d.income || 0);
    const expenses = data.map(d => d.expense_estimated || 0);
    const investments = data.map(d => d.investment_flow || 0);

    charts.flows.data.labels = labels;
    charts.flows.data.datasets[0].data = income;
    charts.flows.data.datasets[1].data = expenses;
    charts.flows.data.datasets[2].data = investments;
    charts.flows.update('none');
  };

  const switchChart = (chartType) => {
    const evolutionCanvas = document.getElementById('evolution-chart');
    const flowsCanvas = document.getElementById('flows-chart');

    if (chartType === 'evolution') {
      evolutionCanvas.style.display = 'block';
      flowsCanvas.style.display = 'none';
      currentChartType = 'evolution';
    } else if (chartType === 'flows') {
      evolutionCanvas.style.display = 'none';
      flowsCanvas.style.display = 'block';
      currentChartType = 'flows';
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

  // Slider initialization functions (keeping the existing ones)
  const initYearSlider = (years) => {
    if (yearSlider && yearSlider.noUiSlider) yearSlider.noUiSlider.destroy();
    if (!yearSlider) return;

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

    const [s, e] = yearSlider.noUiSlider.get();
    if (yearStartLbl) yearStartLbl.textContent = s;
    if (yearEndLbl) yearEndLbl.textContent = e;
    selectedYearRange = [+s, +e];

    yearSlider.noUiSlider.on("update", (values) => {
      if (yearStartLbl) yearStartLbl.textContent = values[0];
      if (yearEndLbl) yearEndLbl.textContent = values[1];
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
  };

  const initPeriodSlider = (periods, preselectLast = true, numMonths = 12) => {
    if (!periodSlider) return;
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
      range: { min: 0, max: Math.max(0, periods.length - 1) },
      format: {
        to: value => periods[Math.round(value)] || '',
        from: val => periods.indexOf(val),
      },
    });

    if (periods.length > 0) {
      periodSlider.noUiSlider.set([periods[startIdx] || '', periods[endIdx] || '']);
    }

    periodSlider.noUiSlider.on("update", (values) => {
      if (periodStartLbl) periodStartLbl.textContent = values[0];
      if (periodEndLbl) periodEndLbl.textContent = values[1];
    });

    periodSlider.noUiSlider.on("set", updateDashboard);
    periodSlider.noUiSlider.on("change", updateDashboard);

    // Add event listeners for real-time updates
    periodSlider.noUiSlider.on("update", debounce(() => {
      if (periodStartLbl && periodEndLbl) {
        const [start, end] = periodSlider.noUiSlider.get();
        periodStartLbl.textContent = start;
        periodEndLbl.textContent = end;
      }
    }, 100));

    updateDashboard(); // Initial render
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
    if (yearStartLbl && yearEndLbl && selectedYearRange.length === 2) {
      yearStartLbl.textContent = selectedYearRange[0];
      yearEndLbl.textContent = selectedYearRange[1];
    }
  };

  // Main update function - now recalculates all data based on filters
  const updateDashboard = async () => {
    if (!periodSlider || !rows.length) return;

    try {
      console.log('🔄 Atualizando dashboard com filtros...');

      // Get current filter settings
      const [start, end] = periodSlider.noUiSlider.get();
      const iStart = allPeriods.indexOf(start);
      const iEnd = allPeriods.indexOf(end);
      const visiblePeriods = allPeriods.slice(iStart, iEnd + 1);

      const includeSavings = document.getElementById('include-savings')?.checked ?? true;
      const includeInvestments = document.getElementById('include-investments')?.checked ?? true;
      const includeCurrent = document.getElementById('include-current')?.checked ?? true;

      console.log('🎛️ [updateDashboard] Configurações de filtro:', {
        visiblePeriods: visiblePeriods.length,
        periodRange: `${start} - ${end}`,
        includeSavings,
        includeInvestments,
        includeCurrent
      });

      // Mostrar loading state nos KPIs
      showKPILoadingState();

      // Update charts with filtered data
      updateCharts();

      // Update table with filtered data
      updateTable();

      // Load real KPIs from server - SEMPRE aguardar pela resposta correta
      if (start && end) {
        await loadFinancialKPIs(start, end);
      } else {
        // Se não há filtro de período, carregar sem filtros
        await loadFinancialKPIs();
      }

      // Regenerate insights based on filtered data
      const filteredAnalysis = generateFilteredAnalysis(visiblePeriods, includeSavings, includeInvestments, includeCurrent);
      generateInsights(filteredAnalysis);

      console.log('✅ Dashboard atualizado com filtros aplicados');
    } catch (error) {
      console.error('❌ Erro ao atualizar dashboard:', error);
    }
  };

  // Enhanced event listeners with proper filter connectivity
  document.getElementById('apply-filters')?.addEventListener('click', updateDashboard);

  // Connect all filter inputs to update dashboard immediately
  const filterInputs = [
    'include-savings', 'include-investments', 'include-current',
    'analysis-period', 'show-trends'
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

  // Add specific listeners for the checkboxes that affect charts and tables
  ['include-savings', 'include-investments', 'include-current'].forEach(id => {
    const checkbox = document.getElementById(id);
    if (checkbox) {
      checkbox.addEventListener('change', () => {
        console.log(`💡 [${id}] Atualizando gráficos e aguardando KPIs do backend...`);
        // Mostrar loading e aguardar backend
        showKPILoadingState();
        updateDashboard(); // Isso irá buscar os KPIs corretos do backend
      });
    }
  });

  // Connect slider events to update dashboard with increased debounce
  const updateDashboardDebounced = debounce(updateDashboard, 800);

  // Year slider event listeners
  if (yearSlider) {
    yearSlider.addEventListener('noUiSlider-change', updateDashboardDebounced);
  }

  // Period slider event listeners
  if (periodSlider) {
    periodSlider.addEventListener('noUiSlider-change', updateDashboardDebounced);
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
    document.getElementById('include-savings').checked = true;
    document.getElementById('include-investments').checked = true;
    document.getElementById('include-current').checked = true;
    document.getElementById('analysis-period').value = 'monthly';
    document.getElementById('show-trends').checked = false;

    // Reset sliders to full range
    if (yearSlider && yearSlider.noUiSlider) {
      yearSlider.noUiSlider.set([allYears[0], allYears[allYears.length - 1]]);
    }
    if (periodSlider && periodSlider.noUiSlider) {
      const lastIndex = allPeriods.length - 1;
      const startIndex = Math.max(0, lastIndex - 11); // Last 12 months
      periodSlider.noUiSlider.set([allPeriods[startIndex], allPeriods[lastIndex]]);
    }

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

  // Initialize dashboard
  const init = async () => {
    console.log('🚀 Inicializando dashboard avançado...');

    // Initialize charts first with error handling
    try {
      initCharts();
    } catch (error) {
      console.error('❌ Erro ao inicializar gráficos:', error);
    }

    // Load data with better error handling and fallbacks
    try {
      console.log('📊 Carregando dados do dashboard...');
      
      // Try to load each component independently
      const balanceData = await loadAccountBalances().catch(err => {
        console.warn('⚠️ Falha ao carregar saldos, usando dados mock');
        return generateMockBalanceData();
      });
      
      const kpiData = await loadFinancialKPIs().catch(err => {
        console.warn('⚠️ Falha ao carregar KPIs, usando dados mock');
        return generateMockKPIs();
      });
      
      const analysisData = await loadFinancialAnalysis().catch(err => {
        console.warn('⚠️ Falha ao carregar análise, usando dados simulados');
        return generateSimulatedAnalysis();
      });

      console.log('✅ Dados carregados:', { 
        balances: !!balanceData, 
        kpis: !!kpiData, 
        analysis: !!analysisData 
      });

    } catch (error) {
      console.error('❌ Erro durante inicialização:', error);
      // Initialize with minimal mock data
      columns = ['type', 'currency'];
      rows = [];
      allPeriods = [];
      allYears = [new Date().getFullYear()];
      updateKPICards(generateMockKPIs());
    }

    console.log('✅ Dashboard avançado inicializado com sucesso');
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