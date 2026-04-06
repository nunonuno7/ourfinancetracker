document.addEventListener("DOMContentLoaded", () => {
  console.log("🏠 Home page loaded!");

  // Example: subtle button highlight on load
  document.querySelectorAll(".btn").forEach(btn => {
    btn.classList.add("shadow");
    btn.addEventListener("mouseenter", () => btn.classList.add("btn-glow"));
    btn.addEventListener("mouseleave", () => btn.classList.remove("btn-glow"));
  });
});
