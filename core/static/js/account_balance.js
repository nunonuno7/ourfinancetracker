let availableAccounts = [];

function populateAccountSelect(select) {
  select.innerHTML = '<option value="">Select account</option>';
  availableAccounts.forEach(acc => {
    const opt = document.createElement('option');
    opt.value = acc.id;
    opt.textContent = acc.name;
    select.appendChild(opt);
  });
}

function removeAccountFromAvailable(accountId, excludeSelect) {
  availableAccounts = availableAccounts.filter(acc => acc.id !== accountId);
  document.querySelectorAll('.account-select').forEach(sel => {
    if (sel !== excludeSelect) {
      const opt = sel.querySelector(`option[value="${accountId}"]`);
      if (opt) opt.remove();
    }
  });
}

function addAccountToAvailable(account) {
  if (!account) return;
  availableAccounts.push(account);
  availableAccounts.sort((a, b) => a.name.localeCompare(b.name));
  document.querySelectorAll('.account-select').forEach(sel => {
    const exists = sel.querySelector(`option[value="${account.id}"]`);
    if (!exists) {
      const opt = document.createElement('option');
      opt.value = account.id;
      opt.textContent = account.name;
      sel.appendChild(opt);
    }
  });
}

function handleAccountSelect(event) {
  const select = event.target;
  const row = select.closest('tr');
  const hidden = row.querySelector('input[name$="-account"]');
  const selectedId = parseInt(select.value);

  // Return previous selection to available list
  const previousId = parseInt(select.dataset.previousId);
  if (previousId && previousId !== selectedId) {
    const previousName = select.dataset.previousName;
    addAccountToAvailable({ id: previousId, name: previousName });
  }

  if (!selectedId) {
    if (hidden) hidden.value = '';
    row.dataset.accountId = '';
    row.dataset.accountName = '';
    select.dataset.previousId = '';
    select.dataset.previousName = '';
    return;
  }

  const selectedAccount = availableAccounts.find(acc => acc.id === selectedId);
  if (selectedAccount) {
    if (hidden) hidden.value = selectedAccount.name;
    row.dataset.accountId = selectedAccount.id;
    row.dataset.accountName = selectedAccount.name;
    select.dataset.previousId = selectedAccount.id;
    select.dataset.previousName = selectedAccount.name;
    removeAccountFromAvailable(selectedAccount.id, select);
  }
}

function addRow() {
  console.log("🔄 [addRow] Adding new account row");

  if (availableAccounts.length === 0) {
    showNotification("No available accounts", "info");
    return;
  }
  
  const totalForms = document.getElementById("id_form-TOTAL_FORMS");
  if (!totalForms) {
    console.error("❌ [addRow] TOTAL_FORMS not found");
    return;
  }

  const newIndex = parseInt(totalForms.value);
  console.log("📊 [addRow] New form index:", newIndex);

  const template = document.getElementById("empty-form-template");
  if (!template) {
    console.error("❌ [addRow] Template not found");
    return;
  }

  // Clone the template
  const clone = template.content.cloneNode(true);
  const newRow = clone.querySelector("tr");
  
  // Replace __prefix__ with the actual form index
  const html = newRow.innerHTML.replace(/__prefix__/g, newIndex);
  newRow.innerHTML = html;

  // Find a suitable table to add the row to
  let targetTable = null;
  
  // First try to find the balance-table (EUR Savings)
  targetTable = document.getElementById("balance-table");
  
  if (!targetTable) {
    // If no balance-table, find any sortable table
    targetTable = document.querySelector(".sortable-table");
  }
  
  if (!targetTable) {
    // If no tables exist, create a new one
    const form = document.querySelector("form");
    if (!form) {
      console.error("❌ [addRow] Form not found");
      return;
    }
    
    // Find insertion point (before action bar)
    const actionBar = form.querySelector(".card:last-child");
    if (!actionBar) {
      console.error("❌ [addRow] Could not find insertion point");
      return;
    }
    
    // Create new table structure
    const newTableCard = document.createElement('div');
    newTableCard.className = 'card shadow-sm mb-3';
    newTableCard.innerHTML = `
      <div class="card-header bg-light py-2">
        <div class="d-flex justify-content-between align-items-center">
          <h6 class="mb-0">💼 Savings – EUR</h6>
          <span class="badge bg-primary">€ 0,00</span>
        </div>
      </div>
      <div class="card-body p-0">
        <div class="table-responsive">
          <table class="table table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th style="width: 40px;" class="text-center">📱</th>
                <th>Account Name</th>
                <th class="text-end" style="width: 180px;">Balance</th>
                <th style="width: 60px;" class="text-center">Actions</th>
              </tr>
            </thead>
            <tbody class="sortable-table" id="balance-table" data-reorder-url="/account-reorder/">
            </tbody>
          </table>
        </div>
      </div>
    `;
    
    // Insert before action bar
    actionBar.insertAdjacentElement('beforebegin', newTableCard);
    targetTable = document.getElementById("balance-table");
  }

  // Add the new row to the target table
  if (targetTable) {
    targetTable.appendChild(newRow);
    totalForms.value = newIndex + 1;

    const select = newRow.querySelector('.account-select');
    if (select) {
      populateAccountSelect(select);
      select.addEventListener('change', handleAccountSelect);
    }

    // Make the new row draggable by reinitializing sortable
    setTimeout(() => {
      const event = new CustomEvent('reinitializeSortable');
      document.dispatchEvent(event);
    }, 100);

    console.log("✅ [addRow] Row added successfully, new total forms:", newIndex + 1);
    updateTotalBalance();
  } else {
    console.error("❌ [addRow] Could not find or create target table");
  }
}

function deleteAccount(balanceId, button) {
  if (!confirm("Are you sure you want to delete this balance?")) return;

  // Disable button to prevent multiple clicks
  button.disabled = true;
  button.innerHTML = '⏳';

  fetch(`/account-balance/delete/${balanceId}/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
    },
  })
  .then(response => {
    if (response.ok || response.redirected) {
      // Remove row from DOM and return account to available list
      const row = button.closest("tr");
      const accountId = parseInt(row.dataset.accountId || row.dataset.id);
      const accountName = row.dataset.accountName;
      row.remove();
      updateTotalBalance();
      if (accountId && accountName) {
        addAccountToAvailable({ id: accountId, name: accountName });
      }

      // Show success notification
      showNotification("✅ Balance deleted successfully", "success");
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  })
  .catch(error => {
    console.error('Delete error:', error);
    showNotification("❌ Error deleting balance", "error");
    
    // Re-enable button on error
    button.disabled = false;
    button.innerHTML = '🗑️';
  });
}

function updateTotalBalance() {
  let total = 0;
  let validInputs = 0;
  
  // Use more efficient selector and processing
  const inputs = document.querySelectorAll("input[name$='-reported_balance']");
  
  for (const input of inputs) {
    const val = parseFloat(input.value);
    if (!isNaN(val)) {
      total += val;
      validInputs++;
    }
  }

  const totalElement = document.getElementById("total-balance");
  if (totalElement) {
    // Use faster formatting for better performance
    const formattedTotal = new Intl.NumberFormat("pt-PT", {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(total);
    
    // Only update if value changed to avoid unnecessary DOM manipulation
    if (totalElement.textContent !== formattedTotal) {
      totalElement.textContent = formattedTotal;
      
      // Optimized visual feedback using requestAnimationFrame
      requestAnimationFrame(() => {
        totalElement.classList.add("text-primary");
        setTimeout(() => {
          requestAnimationFrame(() => {
            totalElement.classList.remove("text-primary");
          });
        }, 400);
      });
    }
  }
  
  // Update group totals efficiently
  updateGroupTotals();
}

function updateGroupTotals() {
  // Cache DOM queries
  const groupElements = document.querySelectorAll('[data-group-total]');
  
  groupElements.forEach(element => {
    const groupKey = element.dataset.groupTotal;
    const groupInputs = document.querySelectorAll(`[data-group="${groupKey}"] input[name$='-reported_balance']`);
    
    let groupTotal = 0;
    groupInputs.forEach(input => {
      const val = parseFloat(input.value);
      if (!isNaN(val)) {
        groupTotal += val;
      }
    });
    
    const formattedGroupTotal = new Intl.NumberFormat("pt-PT", {
      style: "currency", 
      currency: "EUR"
    }).format(groupTotal);
    
    if (element.textContent !== formattedGroupTotal) {
      element.textContent = formattedGroupTotal;
    }
  });
}

// Event listeners
document.addEventListener("DOMContentLoaded", function() {
  // Add row button
  document.getElementById("add-row-btn")?.addEventListener("click", addRow);
  
  
  
  // Copy previous month button
  document.getElementById("copy-previous-btn")?.addEventListener("click", copyPreviousMonth);
  
  // Toggle zeros button
  document.getElementById("toggle-zeros-btn")?.addEventListener("click", function() {
    const btn = this;
    const rows = document.querySelectorAll("#balance-table tr");
    
    if (btn.dataset.state === "hide") {
      // Show all rows
      rows.forEach(row => row.style.display = "");
      btn.textContent = "👁 Hide Zeros";
      btn.dataset.state = "show";
    } else {
      // Hide zero balance rows
      rows.forEach(row => {
        const balanceInput = row.querySelector("input[name$='-reported_balance']");
        if (balanceInput && parseFloat(balanceInput.value) === 0) {
          row.style.display = "none";
        }
      });
      btn.textContent = "👁 Show All";
      btn.dataset.state = "hide";
    }
  });
  
  // Ultra-optimized real-time balance updates with minimal overhead
  let updateTimeout;
  let isUpdating = false;
  
  document.addEventListener("input", function(e) {
    if (e.target.name && e.target.name.includes("reported_balance")) {
      // Skip if already updating
      if (isUpdating) return;
      
      // Clear previous timeout
      clearTimeout(updateTimeout);
      
      // Ultra-minimal visual feedback
      e.target.style.borderColor = "#28a745";
      
      // Ultra-aggressive debouncing - wait for user to stop typing
      updateTimeout = setTimeout(() => {
        if (isUpdating) return;
        isUpdating = true;
        
        // Use requestAnimationFrame for smooth updates
        requestAnimationFrame(() => {
          updateTotalBalance();
          
          // Reset visual feedback
          e.target.style.borderColor = "";
          isUpdating = false;
        });
      }, 150); // Slightly longer debounce for better batching
    }
  });

  // Ultra-optimized form submission with minimal overhead
  document.querySelector('form')?.addEventListener('submit', function(e) {
    console.log("⚡ [form] Ultra-fast form submission");
    const startTime = performance.now();
    
    const submitBtn = document.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.innerHTML = '⚡ Saving...';
      submitBtn.disabled = true;
      
      // Simplified progress without expensive intervals
      setTimeout(() => {
        if (submitBtn.innerHTML.includes('Saving')) {
          submitBtn.innerHTML = '⚡ Processing...';
        }
      }, 500);
    }
    
    // Minimal UI blocking - only disable submit button and form
    const form = document.querySelector('form');
    if (form) {
      form.style.pointerEvents = 'none';
      form.style.opacity = '0.8';
    }
    
    // Lightweight overlay without heavy animations
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(255,255,255,0.7); z-index: 1000;
      display: flex; align-items: center; justify-content: center;
      font-size: 16px; color: #333;
    `;
    overlay.innerHTML = '⚡ Saving balances...';
    document.body.appendChild(overlay);
    
    // Auto-cleanup after reasonable timeout
    setTimeout(() => {
      if (overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
      if (form) {
        form.style.pointerEvents = 'auto';
        form.style.opacity = '1';
      }
    }, 10000);
  });
  
  // Initial total calculation
  updateTotalBalance();
});

function validateForm() {
  const rows = document.querySelectorAll("#balance-table tr");
  for (let row of rows) {
    const input = row.querySelector("input[name$='-account']");
    const balance = row.querySelector("input[name$='-reported_balance']");
    if (input && input.value.trim() === "") {
      alert("Please fill in all account names.");
      return false;
    }
    if (balance && isNaN(parseFloat(balance.value))) {
      alert("All balances must be valid numbers.");
      return false;
    }
  }
  return true;
}

function showSaveLoading(show = true) {
  const saveBtn = document.querySelector('button[type="submit"]');
  const form = document.querySelector('form');
  
  if (show) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '⏳ Saving...';
    form.style.opacity = '0.7';
    form.style.pointerEvents = 'none';
  } else {
    saveBtn.disabled = false;
    saveBtn.innerHTML = '💾 Save';
    form.style.opacity = '1';
    form.style.pointerEvents = 'auto';
  }
}

function copyPreviousMonth() {
  console.log("🔄 [copyPreviousMonth] Starting optimized copy operation");
  
  const selector = document.getElementById("selector");
  if (!selector) {
    console.error("❌ [copyPreviousMonth] Selector not found");
    showNotification("Error: Could not find month selector", "error");
    return;
  }

  const [year, month] = selector.value.split("-").map(Number);
  console.log("📅 [copyPreviousMonth] Target period:", year, month);
  
  // Enhanced loading state with better UX
  const copyBtn = document.getElementById("copy-previous-btn");
  const originalText = copyBtn.textContent;
  const originalClass = copyBtn.className;
  
  copyBtn.textContent = "⏳ Copying...";
  copyBtn.disabled = true;
  copyBtn.className = copyBtn.className.replace('btn-outline-info', 'btn-info');
  
  // Add loading overlay for better UX
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.1); z-index: 1000;
    display: flex; align-items: center; justify-content: center;
  `;
  overlay.innerHTML = '<div class="spinner-border text-primary" role="status"></div>';
  document.body.appendChild(overlay);
  
  const startTime = performance.now();
  
  fetch(`/account-balance/copy/?year=${year}&month=${month}`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
      'Content-Type': 'application/json',
    },
  })
    .then(res => {
      console.log("📡 [copyPreviousMonth] Response status:", res.status);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      return res.json();
    })
    .then(data => {
      const duration = Math.round(performance.now() - startTime);
      console.log("📊 [copyPreviousMonth] Response data:", data, `(${duration}ms)`);
      
      if (data.success) {
        const message = data.message || `Copied ${data.created || 0} balances successfully!`;
        showNotification(`✅ ${message} (${duration}ms)`, "success");
        console.log("✅ [copyPreviousMonth] Success, reloading page");
        
        // Optimized reload - only reload if we actually copied data
        if (data.created > 0 || data.updated > 0) {
          setTimeout(() => location.reload(), 800);
        }
      } else {
        const error = data.error || "Could not copy previous balances.";
        console.error("❌ [copyPreviousMonth] Error:", error);
        showNotification(`❌ ${error}`, "error");
      }
    })
    .catch((error) => {
      console.error('❌ [copyPreviousMonth] Network error:', error);
      showNotification("❌ Network error whilst copying balances. Please try again.", "error");
    })
    .finally(() => {
      // Reset button state
      copyBtn.textContent = originalText;
      copyBtn.disabled = false;
      copyBtn.className = originalClass;
      
      // Remove loading overlay
      document.body.removeChild(overlay);
    });
}

// Helper function for better notifications
function showNotification(message, type = "info") {
  // Create toast notification instead of alert for better UX
  const toast = document.createElement('div');
  toast.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} position-fixed`;
  toast.style.cssText = 'top: 20px; right: 20px; z-index: 2000; min-width: 300px;';
  toast.textContent = message;
  
  document.body.appendChild(toast);
  
  // Auto remove after 5 seconds
  setTimeout(() => {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
  }, 5000);
  
  // Add click to dismiss
  toast.addEventListener('click', () => {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
  });
}

function resetFormChanges() {
  if (confirm("Are you certain you want to discard all changes?")) {
    location.reload();
  }
}

function toggleZeroBalances() {
  const btn = document.getElementById("toggle-zeros-btn");
  const rows = document.querySelectorAll("input[name$='-reported_balance']");
  const isHiding = btn.dataset.state === "hide";

  rows.forEach(input => {
    const row = input.closest("tr");
    const value = parseFloat(input.value || 0);
    
    if (value === 0) {
      row.style.display = isHiding ? "none" : "";
    }
  });

  btn.textContent = isHiding ? "👁 Show All" : "🙈 Hide Zeros";
  btn.dataset.state = isHiding ? "show" : "hide";
}

// Initialize everything when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  console.log("🚀 [account_balance.js] Initializing");

  const dataEl = document.getElementById('available-accounts');
  if (dataEl) {
    try {
      availableAccounts = JSON.parse(dataEl.textContent);
    } catch (e) {
      availableAccounts = [];
    }
  }
  
  // Add row button
  const addBtn = document.getElementById("add-row-btn");
  if (addBtn) {
    addBtn.addEventListener("click", addRow);
    console.log("✅ [account_balance.js] Add row button initialized");
  }

  // Copy previous button
  const copyBtn = document.getElementById("copy-previous-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", copyPreviousMonth);
    console.log("✅ [account_balance.js] Copy previous button initialized");
  }

  // Toggle zeros button
  const toggleBtn = document.getElementById("toggle-zeros-btn");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", toggleZeroBalances);
    console.log("✅ [account_balance.js] Toggle zeros button initialized");
  }

  // Reset button
  const resetBtn = document.getElementById("reset-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", resetFormChanges);
    console.log("✅ [account_balance.js] Reset button initialized");
  }

  // Form submission
  const form = document.querySelector("form");
  if (form) {
    form.addEventListener("submit", function (e) {
      if (!validateForm()) {
        e.preventDefault();
        return;
      }
      
      showSaveLoading(true);
      
      // Set a timeout to re-enable if something goes wrong
      setTimeout(() => {
        showSaveLoading(false);
      }, 10000);
    });
    console.log("✅ [account_balance.js] Form submission handler initialized");
  }

  // Delete and remove buttons (event delegation) - single handler only
  document.addEventListener("click", function (event) {
    const target = event.target;

    // Prevent multiple handlers
    if (target.dataset.processing === 'true') {
      event.preventDefault();
      return;
    }

    if (target.classList.contains("delete-btn")) {
      event.preventDefault();
      const balanceId = target.dataset.id;
      if (balanceId && !target.disabled) {
        target.dataset.processing = 'true';
        deleteAccount(balanceId, target);
        
        // Reset processing flag after a delay
        setTimeout(() => {
          target.dataset.processing = 'false';
        }, 2000);
      }
    }

    if (target.classList.contains("remove-row-btn")) {
      event.preventDefault();
      if (!target.disabled) {
        const row = target.closest("tr");
        const accountId = parseInt(row.dataset.accountId);
        const accountName = row.dataset.accountName;
        target.disabled = true;
        row.remove();
        updateTotalBalance();
        if (accountId && accountName) {
          addAccountToAvailable({ id: accountId, name: accountName });
        }
      }
    }
  });

  // Initial total calculation
  updateTotalBalance();
  console.log("✅ [account_balance.js] Initialization complete");
});