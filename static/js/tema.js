// Alternância entre tema claro e escuro (Bootstrap 5.3 - data-bs-theme).
// Carregado no <head> para aplicar o tema antes da página aparecer.
(() => {
  const CHAVE = "gestorbar-tema";

  const temaPreferido = () => {
    try {
      const salvo = localStorage.getItem(CHAVE);
      if (salvo === "light" || salvo === "dark") return salvo;
    } catch (e) {
      /* localStorage indisponível: segue o sistema */
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  const aplicar = (tema) => {
    document.documentElement.setAttribute("data-bs-theme", tema);
    document.querySelectorAll("[data-tema-icone]").forEach((icone) => {
      icone.className = tema === "dark" ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
    });
  };

  aplicar(temaPreferido());

  document.addEventListener("DOMContentLoaded", () => {
    aplicar(temaPreferido());
    const botao = document.getElementById("alternar-tema");
    if (!botao) return;
    botao.addEventListener("click", () => {
      const atual = document.documentElement.getAttribute("data-bs-theme");
      const novo = atual === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(CHAVE, novo);
      } catch (e) {
        /* ignora */
      }
      aplicar(novo);
    });
  });
})();
