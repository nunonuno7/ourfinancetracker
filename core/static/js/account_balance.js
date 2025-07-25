function addRow() {
  const table = document.getElementById("balance-table");
  const totalForms = document.getElementById("id_form-TOTAL_FORMS");
  const newIndex = parseInt(totalForms.value);

  const template = document.getElementById("empty-form-template");
  if (!template) {
    console.error("❌ Template não encontrado");
    return;
  }

  const clone = template.content.cloneNode(true);
  const newRow = clone.querySelector("tr");
  const html = newRow.innerHTML.replace(/__prefix__/g, newIndex);
  newRow.innerHTML = html;

  table.appendChild(newRow);
  totalForms.value = newIndex + 1;
  updateTotalBalance();
}

function deleteAccount(balanceId, button) {
  if (!confirm("Are you sure you want to delete this balance?")) return;

  fetch(`/account-balance/delete/${balanceId}/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
    },
  })
  .then(response => {
    if (response.ok) {
      button.closest("tr").remove();
      updateTotalBalance();
    } else {
      alert("Error whilst deleting balance.");
    }
  });
}

function updateTotalBalance() {
  let total = 0;
  document.querySelectorAll("input[name$='-reported_balance']").forEach(input => {
    const val = parseFloat(input.value);
    if (!isNaN(val)) total += val;
  });

  document.getElementById("total-balance").innerText = total.toLocaleString("pt-PT", {
    style: "currency",
    currency: "EUR"
  });
}

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

function copyPreviousMonth() {
  const [year, month] = document.getElementById("selector").value.split("-").map(Number);
  
  fetch(`/account-balance/copy/?year=${year}&month=${month}`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
      'Content-Type': 'application/json',
    },
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        alert(`✅ ${data.message || 'Balances copied successfully!'}`);
        location.reload();
      } else {
        alert(data.error || "❌ Could not copy previous balances.");
      }
    })
    .catch((error) => {
      console.error('Error:', error);
      alert("❌ Network error whilst copying balances.");
    });
}

function resetFormChanges() {
  if (confirm("Are you certain you want to discard all changes?")) {
    location.reload();
  }
}

function toggleZeroBalances() {
  const btn = document.getElementById("toggle-zeros-btn");
  const rows = document.querySelectorAll("#balance-table tr");
  const show = btn.dataset.state !== "all";

  rows.forEach(row => {
    const balanceInput = row.querySelector("input[name$='-reported_balance']");
    if (balanceInput && parseFloat(balanceInput.value || 0) === 0) {
      row.style.display = show ? "" : "none";
    }
  });

  btn.textContent = show ? "🙈 Hide Zeros" : "👁 Show All";
  btn.dataset.state = show ? "all" : "hide";
}

function openExportModal() {
  const modal = new bootstrap.Modal(document.getElementById("exportModal"));
  modal.show();
}

document.addEventListener("DOMContentLoaded", () => {
  const addBtn = document.getElementById("add-row-btn");
  if (addBtn) {
    addBtn.addEventListener("click", addRow);
  }

  document.getElementById("reset-btn")?.addEventListener("click", resetFormChanges);
  document.getElementById("copy-previous-btn")?.addEventListener("click", copyPreviousMonth);
  document.getElementById("toggle-zeros-btn")?.addEventListener("click", toggleZeroBalances);
  updateTotalBalance();

  document.querySelector("form")?.addEventListener("submit", function (e) {
    if (!validateForm()) e.preventDefault();
  });

  document.addEventListener("click", function (event) {
    const target = event.target;

    if (target.classList.contains("delete-btn")) {
      const balanceId = target.dataset.id;
      if (balanceId) deleteAccount(balanceId, target);
    }

    if (target.classList.contains("remove-row-btn")) {
      target.closest("tr").remove();
      updateTotalBalance();
    }
  });
});