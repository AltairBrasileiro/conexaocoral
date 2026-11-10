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

  // ------------------------------------------------------- Menu do perfil
  // O <details> nativo só fecha clicando na bolinha; aqui ele também fecha ao
  // tocar fora, com Esc, ao sair pelo Tab e ao voltar à página pelo histórico.
  document.querySelectorAll("details.perfil").forEach(function (menu) {
    var gatilho = menu.querySelector("summary");
    function fechar(devolverFoco) {
      if (!menu.open) return;
      menu.open = false;
      if (devolverFoco) gatilho.focus();
    }
    // pointerdown em vez de click: no iOS, toques em áreas "não clicáveis" não geram click no document.
    document.addEventListener("pointerdown", function (e) {
      if (!menu.contains(e.target)) fechar(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") fechar(true);
    });
    menu.addEventListener("focusout", function (e) {
      if (e.relatedTarget && !menu.contains(e.relatedTarget)) fechar(false);
    });
    window.addEventListener("pageshow", function (e) {
      if (e.persisted) fechar(false);
    });
  });

  // ----------------------------------------- Contador de caracteres (ex.: carona)
  document.querySelectorAll("textarea[data-contador][maxlength]").forEach(function (campo) {
    var limite = Number(campo.getAttribute("maxlength"));
    var contador = document.createElement("small");
    contador.className = "campo__contador";
    campo.insertAdjacentElement("afterend", contador);
    function atualizar() { contador.textContent = campo.value.length + "/" + limite; }
    campo.addEventListener("input", atualizar);
    atualizar();
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

  // Evita envio duplo (ex.: dois cliques em "Confirmar presença").
  document.querySelectorAll('form[method="post"]').forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (e.defaultPrevented) return;
      form.querySelectorAll('button[type="submit"]').forEach(function (b) { b.disabled = true; });
    });
  });

  // ------------------------------------------------ Pré-visualização de imagem
  document.querySelectorAll("input[data-previa-imagem]").forEach(function (campo) {
    var previa = document.querySelector('[data-previa-de="' + campo.id + '"]');
    var vazio = document.querySelector('[data-vazio-de="' + campo.id + '"]');
    var remover = document.getElementById(campo.id + "-clear");
    campo.addEventListener("change", function () {
      var arquivo = campo.files && campo.files[0];
      if (!arquivo) return;
      if (previa.src.indexOf("blob:") === 0) URL.revokeObjectURL(previa.src);
      previa.src = URL.createObjectURL(arquivo);
      previa.hidden = false;
      if (vazio) vazio.hidden = true;
      if (remover) remover.checked = false; // enviar uma nova imagem já substitui a atual
    });
  });

  // ------------------------------------- Pré-visualização de várias imagens
  document.querySelectorAll("input[data-previa-varias]").forEach(function (campo) {
    var lista = document.querySelector('[data-previa-varias-de="' + campo.id + '"]');
    campo.addEventListener("change", function () {
      lista.querySelectorAll("img").forEach(function (img) { URL.revokeObjectURL(img.src); });
      lista.innerHTML = "";
      Array.prototype.forEach.call(campo.files, function (arquivo) {
        var item = document.createElement("li");
        var img = document.createElement("img");
        img.alt = arquivo.name;
        img.src = URL.createObjectURL(arquivo);
        var rotulo = document.createElement("span");
        rotulo.className = "fotos-evento__nova";
        rotulo.textContent = "Nova";
        item.appendChild(img);
        item.appendChild(rotulo);
        lista.appendChild(item);
      });
      lista.hidden = !campo.files.length;
    });
  });

  // ---------------------------------------- Cargo: lista com "Outro cargo…"
  document.querySelectorAll("select[data-cargo]").forEach(function (lista) {
    var form = lista.form;
    var outro = form.querySelector("[data-cargo-outro]");
    function alternar(focar) {
      var digitar = lista.value === lista.dataset.cargo;
      outro.hidden = !digitar;
      outro.required = digitar;
      if (digitar && focar) outro.focus();
    }
    lista.addEventListener("change", function () {
      alternar(true);
      // Na lista de membros, escolher um cargo já salva; "Outro" espera o texto digitado.
      if (form.hasAttribute("data-salvar-ao-escolher") && lista.value !== lista.dataset.cargo) {
        form.requestSubmit();
      }
    });
    alternar();
  });

  // ------------------------------------------------------ Copiar (ex.: Pix)
  document.querySelectorAll("[data-copiar]").forEach(function (botao) {
    var origem = document.getElementById(botao.dataset.copiar);
    var texto = botao.querySelector("span:last-child");
    var original = texto.textContent;
    botao.addEventListener("click", function () {
      function pronto() {
        texto.textContent = botao.dataset.copiado || "Copiado!";
        setTimeout(function () { texto.textContent = original; }, 2500);
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(origem.value).then(pronto);
      } else {
        // Fora de HTTPS (ex.: acesso pelo IP da rede) a API de área de transferência não existe.
        origem.select();
        document.execCommand("copy");
        pronto();
      }
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
