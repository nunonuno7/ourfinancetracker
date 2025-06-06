document.addEventListener("DOMContentLoaded", () => {
  const deleteForms = document.querySelectorAll(".delete-form");

  deleteForms.forEach(form => {
    form.addEventListener("submit", function (event) {
      const itemName = form.dataset.name || "this transaction";
      const confirmed = confirm(`Are you sure you want to delete ${itemName}?`);
      if (!confirmed) {
        event.preventDefault();
      }
    });
  });
});
