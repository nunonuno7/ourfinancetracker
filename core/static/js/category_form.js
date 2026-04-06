document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("category-form");
  const confirmField = document.getElementById("confirm_merge");
  const submitBtn = document.getElementById("submit-btn");
  const mergePrompt =
    "A category with this name already exists. Do you want to merge into it?";
  const mergeHint = "Do you want to merge into it?";

  if (form && confirmField && submitBtn) {
    submitBtn.addEventListener("click", () => {
      const errorEl = document.querySelector(".nonfield ul li, .nonfield li, .text-danger");
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
});
