fetch("/api/menu/")
  .then(res => res.json())
  .then(data => {
    document.getElementById("user-name").textContent = data.username;
    // preencher links dinamicamente se quiseres
  });
