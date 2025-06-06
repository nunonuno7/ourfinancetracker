// ✅ Versão funcional: listener ativado após o toggle revelar o botão

console.log("🧪 transaction_bulk_edit.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const editToggle = document.getElementById("toggle-edit-mode");

  editToggle?.addEventListener("change", () => {
    setTimeout(() => {
      const saveButton = document.getElementById("save-all-btn");
      if (!saveButton) return;

      saveButton.addEventListener("click", async (e) => {
        e.preventDefault();
        console.log("🧪 Save All clicked. Sending updates...");

        const rows = document.querySelectorAll("#transaction-table tbody tr[data-id]");
        const updates = [];

        rows.forEach(row => {
          const id = row.dataset.id;
          if (!id) return;

          const update = { id };
          const cells = row.querySelectorAll("[data-field]");

          cells.forEach(cell => {
            const field = cell.dataset.field;
            const input = cell.querySelector("input, select");
            if (!input) return;

            let value = input.value;

            if (field === "amount") {
              value = value.replace(/[€\s]/g, "").replace(",", ".");
            }

            update[field] = value;
          });

          updates.push(update);
        });

        const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;

        try {
          const response = await fetch("/transactions/bulk-update/", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ updates })
          });

          const data = await response.json();

          if (response.ok) {
            location.reload();
          } else {
            alert("❌ Error saving changes: " + (data.message || "Unknown error"));
            console.error("❌ Backend error:", data);
          }

        } catch (err) {
          console.error("❌ Network or JS error:", err);
          alert("❌ Could not send updates. Check your internet or console.");
        }
      });
    }, 100);
  });
});
