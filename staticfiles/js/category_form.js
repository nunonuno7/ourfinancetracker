document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("category-form");
  const confirmField = document.getElementById("confirm_merge");
  const submitBtn = document.getElementById("submit-btn");

  if (form && confirmField && submitBtn) {
    submitBtn.addEventListener("click", () => {
      const errorEl = document.querySelector(".nonfield ul li, .nonfield li, .text-danger");
      const isMergeWarning = errorEl && errorEl.innerText.includes("Queres fundir os saldos");

      if (isMergeWarning) {
        if (confirm("⚠ Já existe uma conta com esse nome. Queres fundir os saldos?")) {
          confirmField.value = "true";
          form.submit();
        }
      } else {
        form.submit();
      }
    });
  }
});
