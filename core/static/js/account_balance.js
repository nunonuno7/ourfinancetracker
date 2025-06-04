function addRow() {
  const table = document.getElementById("balance-table");
  const totalForms = document.getElementById("id_form-TOTAL_FORMS");
  const newIndex = parseInt(totalForms.value);

  const template = document.getElementById("empty-form-template");
  const newRow = template.content.cloneNode(true).children[0];
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
      const row = button.closest("tr");
      row.remove();
      updateTotalBalance();
    } else {
      alert("Error deleting balance.");
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

  fetch(`/account-balance/copy/?year=${year}&month=${month}`)
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        alert(`✅ ${data.created} balances copied from previous month.`);
        location.reload();
      } else {
        alert(data.error || "❌ Could not copy previous balances.");
      }
    })
    .catch(() => {
      alert("❌ Network error while copying balances.");
    });
}

function resetFormChanges() {
  if (confirm("Are you sure you want to discard all changes?")) {
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

// ───── Bind estático + delegação ─────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("add-row-btn")?.addEventListener("click", addRow);
  document.getElementById("reset-btn")?.addEventListener("click", resetFormChanges);
  document.getElementById("copy-previous-btn")?.addEventListener("click", copyPreviousMonth);
  document.getElementById("toggle-zeros-btn")?.addEventListener("click", toggleZeroBalances);
  updateTotalBalance();

  document.querySelector("form")?.addEventListener("submit", function (e) {
    if (!validateForm()) e.preventDefault();
  });

  // ───── Delegação para botões dinâmicos ─────
  document.addEventListener("click", function (event) {
    const target = event.target;

    // Botão "×" para apagar saldo existente
    if (target.classList.contains("delete-btn")) {
      const balanceId = target.dataset.id;
      if (balanceId) {
        deleteAccount(balanceId, target);
      }
    }

    // Botão "×" para apagar linha nova (sem pk)
    if (target.classList.contains("remove-row-btn")) {
      target.closest("tr").remove();
      updateTotalBalance();
    }
  });
});
