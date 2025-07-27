class EstimationManager {
    constructor() {
        console.log('🧮 [EstimationManager] Initializing...');
        this.summaries = [];
        this.loading = false;
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
        this.selectedYear = new Date().getFullYear(); // Current year as default
        this.init();
    }

    async init() {
        // First load summaries for current year, then setup year filter
        await this.loadEstimationSummaries();
        await this.setupYearFilterFromData();
        this.bindEvents();
        console.log('✅ [EstimationManager] Initialized successfully');
    }

    async setupYearFilterFromData() {
        const yearSelect = $('#year-filter');
        const currentYear = new Date().getFullYear();

        try {
            // Get available years from database periods
            const response = await fetch('/transactions/estimate/years/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': window.csrfToken || $('[name=csrfmiddlewaretoken]').val() || ''
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.years) {
                    const availableYears = data.years.sort((a, b) => b - a); // Sort descending

                    console.log('📅 [setupYearFilterFromData] Available years with balances:', availableYears);

                    // Clear existing options
                    yearSelect.empty();

                    // Add years that have balance periods
                    availableYears.forEach(year => {
                        const option = $(`<option value="${year}">${year}</option>`);
                        if (year === currentYear) {
                            option.prop('selected', true);
                        }
                        yearSelect.append(option);
                    });

                    // Set selected year (current year if available, otherwise first available)
                    if (availableYears.includes(currentYear)) {
                        this.selectedYear = currentYear;
                    } else if (availableYears.length > 0) {
                        this.selectedYear = availableYears[0];
                        yearSelect.val(this.selectedYear);
                        // Reload summaries if year changed
                        await this.loadEstimationSummaries();
                    } else {
                        // Fallback: no years available
                        this.selectedYear = currentYear;
                        yearSelect.append($(`<option value="${currentYear}">${currentYear}</option>`));
                    }

                    console.log('✅ [setupYearFilterFromData] Year filter initialized with available years');
                    return;
                }
            }
        } catch (error) {
            console.warn('⚠️ [setupYearFilterFromData] Failed to load available years:', error);
        }

        // Fallback: use current year if API fails
        console.log('🔄 [setupYearFilterFromData] Using fallback: current year only');
        yearSelect.empty();
        yearSelect.append($(`<option value="${currentYear}">${currentYear}</option>`));
        this.selectedYear = currentYear;
    }

    bindEvents() {
        // Year filter change
        $('#year-filter').on('change', (e) => {
            this.selectedYear = parseInt(e.target.value);
            console.log(`📅 [EstimationManager] Year filter changed to: ${this.selectedYear}`);
            this.loadEstimationSummaries(true); // Force refresh with new year
        });

        // Refresh button - force refresh
        $('#refresh-summaries-btn').on('click', () => this.loadEstimationSummaries(true));

        // Event delegation for dynamic buttons
        $(document).on('click', '.estimate-btn', (e) => this.handleEstimate(e));
        $(document).on('click', '.delete-estimated-btn', (e) => this.handleDeleteEstimated(e));
        $(document).on('click', '.view-details-btn', (e) => this.handleViewDetails(e));
    }

    async loadEstimationSummaries(forceRefresh = false) {
        console.log('📊 [loadEstimationSummaries] Loading estimation summaries...');

        // Prevent duplicate requests
        if (this.loading) {
            console.log('⏳ [loadEstimationSummaries] Already loading, skipping...');
            return;
        }

        // Check cache first
        const cacheKey = `estimation_summaries_${this.selectedYear}`;
        const cached = this.cache.get(cacheKey);
        if (!forceRefresh && cached && (Date.now() - cached.timestamp < this.cacheTimeout)) {
            console.log('💾 [loadEstimationSummaries] Using cached data');
            this.summaries = cached.data;
            this.renderSummaries();
            return;
        }

        try {
            this.loading = true;
            this.showLoading(true);

            const response = await fetch(`/transactions/estimate/summaries/?year=${this.selectedYear}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': window.csrfToken || $('[name=csrfmiddlewaretoken]').val() || ''
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('📋 [loadEstimationSummaries] Received data:', data);

            if (data.success) {
                // Filter summaries by selected year and sort by period (most recent first)
                this.summaries = data.summaries
                    .filter(summary => {
                        const parts = summary.period.split(' ');
                        return parts.length === 2 && parseInt(parts[1]) === this.selectedYear;
                    })
                    .sort((a, b) => {
                        const parseDate = (periodStr) => {
                            const parts = periodStr.split(' ');
                            if (parts.length === 2) {
                                const months = {
                                    'January': 1, 'February': 2, 'March': 3, 'April': 4,
                                    'May': 5, 'June': 6, 'July': 7, 'August': 8,
                                    'September': 9, 'October': 10, 'November': 11, 'December': 12
                                };
                                return new Date(parseInt(parts[1]), months[parts[0]] - 1);
                            }
                            return new Date(0);
                        };
                        return parseDate(b.period) - parseDate(a.period);
                    });

                // Cache the data
                this.cache.set(cacheKey, {
                    data: this.summaries,
                    timestamp: Date.now()
                });

                this.renderSummaries();
            } else {
                throw new Error(data.error || 'Failed to load summaries');
            }

        } catch (error) {
            console.error('❌ [loadEstimationSummaries] Error:', error);
            this.showError('Failed to load estimation summaries: ' + error.message);
        } finally {
            this.loading = false;
            this.showLoading(false);
        }
    }

    renderSummaries() {
        console.log('🎨 [renderSummaries] Rendering summaries...');

        const tbody = $('#estimation-summaries-tbody');
        tbody.empty();

        if (!this.summaries || this.summaries.length === 0) {
            tbody.append(`
                <tr>
                    <td colspan="5" class="text-center py-4 text-muted">
                        <i class="fas fa-info-circle fa-2x mb-2"></i><br>
                        No periods with account balances found for ${this.selectedYear}.<br>
                        <small>Try a different year or go to <a href="/account-balance/" class="text-decoration-none">Account Balances</a> to add balance data.</small>
                    </td>
                </tr>
            `);
            return;
        }

        this.summaries.forEach(summary => {
            const row = this.createSummaryRow(summary);
            tbody.append(row);
        });

        console.log(`✅ [renderSummaries] Rendered ${this.summaries.length} summary rows`);
    }

    createSummaryRow(summary) {
        const statusBadge = this.getStatusBadge(summary.status);
        const typeBadge = this.getTypeBadge(summary.estimated_type);
        const amountFormatted = this.formatCurrency(summary.estimated_amount);

        // Action buttons based on status
        let actionButtons = '';

        if (summary.has_estimated_transaction) {
            actionButtons = `
                <button class="btn btn-outline-danger btn-sm delete-estimated-btn me-1" 
                        data-transaction-id="${summary.estimated_transaction_id}"
                        data-period="${summary.period}">
                    <i class="fas fa-trash"></i> Delete
                </button>
            `;
        }

        actionButtons += `
            <button class="btn btn-outline-primary btn-sm estimate-btn me-1" 
                    data-period-id="${summary.period_id}"
                    data-period="${summary.period}">
                <i class="fas fa-calculator"></i> ${summary.has_estimated_transaction ? 'Re-estimate' : 'Estimate'}
            </button>
            <button class="btn btn-outline-info btn-sm view-details-btn" 
                    data-summary='${JSON.stringify(summary)}'>
                <i class="fas fa-eye"></i> Details
            </button>
        `;

        return `
            <tr data-period-id="${summary.period_id}">
                <td>
                    <strong>${summary.period}</strong>
                </td>
                <td>
                    ${statusBadge}
                    <small class="text-muted d-block">${summary.status_message}</small>
                </td>
                <td>${typeBadge}</td>
                <td class="text-end">
                    <strong class="${summary.estimated_amount > 0 ? 'text-warning' : 'text-muted'}">${amountFormatted}</strong>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        ${actionButtons}
                    </div>
                </td>
            </tr>
        `;
    }

    getStatusBadge(status) {
        const badges = {
            'balanced': '<span class="badge bg-success">✅ Balanced</span>',
            'missing_expenses': '<span class="badge bg-warning text-dark">⚠️ Missing Expenses</span>',
            'missing_income': '<span class="badge bg-warning text-dark">⚠️ Missing Income</span>',
            'error': '<span class="badge bg-danger">❌ Error</span>'
        };
        return badges[status] || '<span class="badge bg-secondary">Unknown</span>';
    }

    getTypeBadge(type) {
        const badges = {
            'EX': '<span class="badge bg-danger">Expense</span>',
            'IN': '<span class="badge bg-success">Income</span>',
            'IV': '<span class="badge bg-info">Investment</span>'
        };
        return badges[type] || '<span class="badge bg-secondary">-</span>';
    }

    async handleEstimate(e) {
        const button = $(e.currentTarget);
        const periodId = button.data('period-id');
        const periodName = button.data('period');

        console.log(`🧮 [handleEstimate] Estimating for period ${periodId} (${periodName})`);

        const confirmed = confirm(`Estimate missing transaction for ${periodName}?\n\nThis action will create/update an estimated transaction based on your account balances.`);
        if (!confirmed) return;

        try {
            button.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Estimating...');

            // Try to delete any existing estimated transaction first (ignore errors if none exists)
            try {
                const deleteResponse = await fetch(`/transactions/estimate/period/${periodId}/delete/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.csrfToken || $('[name=csrfmiddlewaretoken]').val() || ''
                    }
                });

                if (deleteResponse.ok) {
                    console.log('✅ [handleEstimate] Deleted existing estimated transaction');
                } else {
                    console.log('ℹ️ [handleEstimate] No existing estimated transaction to delete');
                }
            } catch (deleteError) {
                console.log('ℹ️ [handleEstimate] No existing estimated transaction to delete:', deleteError.message);
                // Continue with estimation even if deletion fails
            }

            // Proceed to estimate the transaction
            const response = await fetch('/transactions/estimate/period/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken || $('[name=csrfmiddlewaretoken]').val() || ''
                },
                body: JSON.stringify({
                    period_id: periodId
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to estimate transaction');
            }

            const result = await response.json();
            console.log('✅ [handleEstimate] Estimation result:', result);

            if (result.success) {
                this.showSuccess(result.message);

                // Clear cache and reload summaries to reflect changes
                this.cache.clear();
                await this.loadEstimationSummaries();
            } else {
                throw new Error(result.error || 'Estimation failed');
            }

        } catch (error) {
            console.error('❌ [handleEstimate] Error:', error);
            this.showError('Failed to estimate transaction: ' + error.message);
        } finally {
            button.prop('disabled', false).html('<i class="fas fa-calculator"></i> Re-estimate');
        }
    }

    async handleDeleteEstimated(e) {
        const button = $(e.currentTarget);
        const transactionId = button.data('transaction-id');
        const periodName = button.data('period');

        console.log(`🗑️ [handleDeleteEstimated] Deleting estimated transaction ${transactionId} for ${periodName}`);

        const confirmed = confirm(`Delete estimated transaction for ${periodName}?\n\nThis action cannot be undone.`);
        if (!confirmed) return;

        try {
            button.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Deleting...');

            const response = await fetch(`/transactions/estimate/${transactionId}/delete/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken || $('[name=csrfmiddlewaretoken]').val() || ''
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete transaction');
            }

            const result = await response.json();
            console.log('✅ [handleDeleteEstimated] Delete result:', result);

            if (result.success) {
                this.showSuccess(result.message);

                // Clear cache and reload summaries to reflect changes
                this.cache.clear();
                await this.loadEstimationSummaries();
            } else {
                throw new Error(result.error || 'Delete failed');
            }

        } catch (error) {
            console.error('❌ [handleDeleteEstimated] Error:', error);
            this.showError('Failed to delete estimated transaction: ' + error.message);
        } finally {
            button.prop('disabled', false).html('<i class="fas fa-trash"></i> Delete');
        }
    }

    handleViewDetails(e) {
        const button = $(e.currentTarget);
        const summary = JSON.parse(button.attr('data-summary'));

        console.log('👁️ [handleViewDetails] Showing details for:', summary);

        // Populate modal with details
        const details = summary.details;

        // Set period title
        $('#modal-period-title').text(summary.period);

        // Estimated Transactions
        const estimatedIncome = details.estimated_income || 0;
        const estimatedExpenses = details.estimated_expenses_tx || 0;
        const estimatedInvestments = details.estimated_investments || 0;
        
        $('#detail-estimated-income').text(this.formatCurrency(estimatedIncome));
        $('#detail-estimated-expenses-tx').text(this.formatCurrency(estimatedExpenses));
        $('#detail-estimated-investments').text(this.formatCurrencyWithSign(estimatedInvestments));
        
        // Calculate and display estimated total
        const estimatedTotal = estimatedIncome - estimatedExpenses + estimatedInvestments;
        $('#detail-estimated-total').text(this.formatCurrencyWithSign(estimatedTotal));

        // Combined Totals
        const combinedIncome = (details.real_income || 0) + (details.estimated_income || 0);
        const combinedExpenses = (details.real_expenses || 0) + (details.estimated_expenses_tx || 0);
        const combinedInvestments = (details.real_investments || 0) + (details.estimated_investments || 0);
        
        $('#detail-income-inserted').text(this.formatCurrency(combinedIncome));
        $('#detail-expense-inserted').text(this.formatCurrency(combinedExpenses));
        $('#detail-investment-inserted').text(this.formatCurrencyWithSign(combinedInvestments));
        
        // Calculate and display combined total using transaction formula: Income - Expenses - Investments
        const combinedTotal = combinedIncome - combinedExpenses - combinedInvestments;
        $('#detail-combined-total').text(this.formatCurrencyWithSign(combinedTotal));

        // Savings Analysis
        $('#detail-savings-current').text(this.formatCurrency(details.savings_current || 0));
        $('#detail-savings-next').text(this.formatCurrency(details.savings_next || 0));

        const savingsDiff = (details.savings_next || 0) - (details.savings_current || 0);
        const savingsDiffElement = $('#detail-savings-diff');
        savingsDiffElement.text(this.formatCurrencyWithSign(savingsDiff));

        // Update badge color based on savings change
        savingsDiffElement.removeClass('bg-primary bg-success bg-danger bg-warning');
        if (savingsDiff > 0) {
            savingsDiffElement.addClass('bg-success');
        } else if (savingsDiff < 0) {
            savingsDiffElement.addClass('bg-danger');
        } else {
            savingsDiffElement.addClass('bg-secondary');
        }

        // Calculation Results
        $('#detail-estimated-expenses').text(this.formatCurrency(details.estimated_expenses || 0));
        $('#detail-missing-expenses').text(this.formatCurrency(details.missing_expenses || 0));
        $('#detail-missing-income').text(this.formatCurrency(details.missing_income || 0));

        // Show modal
        $('#estimationDetailsModal').modal('show');
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('pt-PT', {
            style: 'currency',
            currency: 'EUR'
        }).format(amount || 0);
    }

    // Function to format amount to include sign
    formatCurrencyWithSign(amount) {
        return new Intl.NumberFormat('pt-PT', {
            style: 'currency',
            currency: 'EUR',
            signDisplay: 'always',
        }).format(amount || 0);
    }

    // Legacy function for backward compatibility
    formatAmount(amount) {
        return this.formatCurrencyWithSign(amount);
    }

    showLoading(show) {
        $('#loading-estimation').toggleClass('d-none', !show);
        $('#estimation-summaries-tbody').closest('.card').toggleClass('d-none', show);
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'danger');
    }

    showToast(message, type, delay = 3000) {
        const toastId = `toast-${Date.now()}`;
        const toast = $(`
            <div class="toast position-fixed top-0 end-0 m-3" id="${toastId}" style="z-index: 9999;">
                <div class="toast-body bg-${type} text-white">
                    ${message}
                </div>
            </div>
        `);

        $('body').append(toast);
        toast.toast({ delay: delay }).toast('show');
        toast.on('hidden.bs.toast', () => toast.remove());
    }
}

// Initialize when document ready - with jQuery availability check
function initializeEstimationManager() {
    if (typeof $ === 'undefined') {
        console.warn('jQuery not loaded yet, retrying...');
        setTimeout(initializeEstimationManager, 100);
        return;
    }

    $(document).ready(() => {
        window.estimationManager = new EstimationManager();
    });
}

// Start initialization
initializeEstimationManager();