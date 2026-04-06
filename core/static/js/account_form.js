document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("account-form");
  const confirmField = document.getElementById("confirm_merge");
  const mergePrompt =
    "An account with this name already exists. Do you want to merge the balances?";
  const mergeHint = "Do you want to merge the balances?";

  if (form && confirmField) {
    const btn = form.querySelector("button.btn-success");
    if (btn) {
      btn.addEventListener("click", () => {
        const errorEl = document.querySelector(".nonfield ul li");
        const isMergeWarning = errorEl && errorEl.innerText.includes(mergeHint);

        if (isMergeWarning) {
          if (confirm(mergePrompt)) {
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
