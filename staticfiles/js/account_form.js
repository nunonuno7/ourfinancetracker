document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("account-form");
  const confirmField = document.getElementById("confirm_merge");

  if (form && confirmField) {
    const btn = form.querySelector("button.btn-success");
    if (btn) {
      btn.addEventListener("click", () => {
        const errorEl = document.querySelector(".nonfield ul li");
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
  }
});
