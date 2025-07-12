
// static/js/drag_reorder.js

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".sortable-table").forEach((tableBody) => {
    const endpoint = tableBody.dataset.reorderUrl;
    if (!endpoint) return;

    new Sortable(tableBody, {
      animation: 150,
      handle: ".handle",
      onEnd: function () {
        const rows = [...tableBody.querySelectorAll("tr")];
        const order = rows.map((row, index) => ({
          id: row.dataset.id,
          position: index
        }));

        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
        if (!csrfToken) {
          console.error("❌ CSRF token not found");
          return;
        }

        fetch(endpoint, {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ order })
        })
        .then(res => {
          if (!res.ok) throw new Error("Failed to save order");
        })
        .catch(err => {
          console.error("❌ Drag save failed:", err);
        });
      }
    });
  });
});
