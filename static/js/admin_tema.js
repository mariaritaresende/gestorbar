// Botão de alternar tema claro/escuro no painel administrativo.
// O Jazzmin 3 aplica o tema pelo atributo data-bs-theme do <html>
// (com default_theme_mode = "auto" ele segue o sistema operacional).
// Este script deixa o usuário escolher e lembra a escolha no navegador.
(() => {
  const CHAVE = "gestorbar-tema-admin";
  const raiz = document.documentElement;

  const lerEscolha = () => {
    try {
      const salvo = localStorage.getItem(CHAVE);
      return salvo === "light" || salvo === "dark" ? salvo : null;
    } catch (e) {
      return null;
    }
  };

  const temaAtual = () => {
    const tema = raiz.getAttribute("data-bs-theme");
    if (tema === "light" || tema === "dark") return tema;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  const aplicar = (tema, botao) => {
    raiz.setAttribute("data-bs-theme", tema);
    if (botao) {
      botao.innerHTML = tema === "dark" ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
      botao.title = tema === "dark" ? "Usar tema claro" : "Usar tema escuro";
    }
  };

  const escolha = lerEscolha();
  if (escolha) aplicar(escolha);

  const iniciar = () => {
    const botao = document.createElement("button");
    botao.type = "button";
    botao.id = "alternar-tema-admin";
    botao.className = "btn btn-warning";
    botao.setAttribute("aria-label", "Alternar tema claro/escuro");
    aplicar(lerEscolha() || temaAtual(), botao);
    botao.addEventListener("click", () => {
      const novo = temaAtual() === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(CHAVE, novo);
      } catch (e) {
        /* sem localStorage: vale só até recarregar */
      }
      aplicar(novo, botao);
    });
    document.body.appendChild(botao);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
