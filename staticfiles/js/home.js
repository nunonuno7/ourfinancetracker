document.addEventListener("DOMContentLoaded", () => {
  console.log("🏠 Home page loaded!");

  // Exemplo: realce suave de botões ao carregar
  document.querySelectorAll(".btn").forEach(btn => {
    btn.classList.add("shadow");
    btn.addEventListener("mouseenter", () => btn.classList.add("btn-glow"));
    btn.addEventListener("mouseleave", () => btn.classList.remove("btn-glow"));
  });
});
