/* Comportamentos leves das páginas. Tudo funciona sem JS, exceto o mapa e a galeria com setas. */
(function () {
  "use strict";

  // ------------------------------------------------------------ Avisos (toasts)
  function fecharAviso(aviso) {
    aviso.classList.add("saindo");
    setTimeout(function () { aviso.remove(); }, 200);
  }
  document.querySelectorAll(".aviso").forEach(function (aviso) {
    aviso.querySelector(".aviso__fechar").addEventListener("click", function () { fecharAviso(aviso); });
    setTimeout(function () { if (aviso.isConnected) fecharAviso(aviso); }, 6000);
  });

  // ------------------------------------------------------------ Mostrar senha
  document.querySelectorAll("[data-mostrar-senha]").forEach(function (botao) {
    var campo = document.getElementById(botao.dataset.mostrarSenha);
    var icone = botao.querySelector(".icon");
    botao.addEventListener("click", function () {
      var visivel = campo.type === "text";
      campo.type = visivel ? "password" : "text";
      icone.textContent = visivel ? "visibility" : "visibility_off";
      botao.setAttribute("aria-label", visivel ? "Mostrar senha" : "Ocultar senha");
      botao.title = botao.getAttribute("aria-label");
    });
  });

  // ------------------------------------------------- Envio automático de filtros
  document.querySelectorAll("form[data-auto-enviar]").forEach(function (form) {
    var espera;
    form.querySelectorAll("select").forEach(function (s) {
      s.addEventListener("change", function () { form.submit(); });
    });
    form.querySelectorAll('input[type="search"]').forEach(function (campo) {
      // Mantém o cursor no fim ao recarregar com a busca preenchida.
      if (campo.value) { campo.focus(); campo.setSelectionRange(campo.value.length, campo.value.length); }
      campo.addEventListener("input", function () {
        clearTimeout(espera);
        espera = setTimeout(function () { form.submit(); }, 500);
      });
    });
  });

  // ------------------------------------------------------------ Confirmações
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirmar)) e.preventDefault();
    });
  });

  // Evita envio duplo (ex.: dois cliques em "Fazer check-in").
  document.querySelectorAll('form[method="post"]').forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (e.defaultPrevented) return;
      form.querySelectorAll('button[type="submit"]').forEach(function (b) { b.disabled = true; });
    });
  });

  // ------------------------------------------------------------ Galeria
  document.querySelectorAll("[data-galeria]").forEach(function (galeria) {
    var trilho = galeria.querySelector("[data-trilho]");
    var fotos = trilho.children;
    var pontos = galeria.querySelectorAll("[data-pontos] span");
    var legenda = galeria.querySelector("[data-legenda-atual]");
    var atual = 0;

    function marcar(i) {
      atual = i;
      pontos.forEach(function (p, j) { p.classList.toggle("ativo", j === i); });
      if (legenda) legenda.textContent = fotos[i].dataset.legenda || "";
    }
    trilho.addEventListener("scroll", function () {
      var i = Math.round(trilho.scrollLeft / trilho.clientWidth);
      if (i !== atual && fotos[i]) marcar(i);
    }, { passive: true });
    galeria.querySelectorAll("[data-ir]").forEach(function (seta) {
      seta.addEventListener("click", function () {
        var i = (atual + Number(seta.dataset.ir) + fotos.length) % fotos.length;
        trilho.scrollTo({ left: i * trilho.clientWidth });
      });
    });
    // Foto quebrada: some do carrossel em vez de mostrar o ícone do navegador.
    trilho.querySelectorAll(".galeria__img").forEach(function (img) {
      img.addEventListener("error", function () { img.closest("figure").style.background = "var(--preto)"; img.remove(); });
    });
  });
})();
