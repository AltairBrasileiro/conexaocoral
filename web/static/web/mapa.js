/* Módulo 1 — Mapa interativo (Leaflet + OpenStreetMap) com busca instantânea. */
(function () {
  "use strict";

  var consulados = JSON.parse(document.getElementById("consulados-dados").textContent);
  var CENTRO_INICIAL = [-8.05, -34.9]; // Recife

  var mapa = L.map("mapa", { zoomControl: false, minZoom: 3 }).setView(CENTRO_INICIAL, 5);
  L.control.zoom({ position: "bottomright" }).addTo(mapa);
  // A política de uso dos tiles do OpenStreetMap exige o cabeçalho Referer; sem ele,
  // cada tile vem como a imagem "Access blocked". O Django envia "Referrer-Policy:
  // same-origin" (SECURE_REFERRER_POLICY), que omite o Referer em requisições a outros
  // domínios, então os tiles enviam só a origem do site (nunca o caminho da página).
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    referrerPolicy: "strict-origin-when-cross-origin",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">colaboradores do OpenStreetMap</a>',
  }).addTo(mapa);

  var busca = document.getElementById("busca-consulados");
  var resumo = document.getElementById("resumo-busca");
  var folha = document.getElementById("folha-consulado");
  var visiveis = consulados.slice();
  var selecionadoId = null;

  function esc(texto) {
    return String(texto).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  // "Consulado Coral Olinda" -> "Olinda"; "Consulado CoralJampa" -> "CoralJampa".
  function nomeCurto(nome) { return nome.replace(/^Consulado (Coral )?/, ""); }
  // Busca sem diferenciar acentos nem maiúsculas.
  function normalizar(texto) { return (texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function membros(total) { return total + (total === 1 ? " membro" : " membros"); }

  function icone(c) {
    var classes = "pino" + (c.logo ? " pino--logo" : "") + (c.id === selecionadoId ? " pino--selecionado" : "");
    var miolo = '<span class="pino__padrao"><span class="icon">sports_bar</span></span>';
    if (c.logo) miolo += '<img src="' + esc(c.logo) + '" alt="">';
    return L.divIcon({
      className: "marcador-coral",
      html: '<div class="marcador"><div class="' + classes + '">' + miolo + "</div>" +
            '<div class="etiqueta">' + esc(nomeCurto(c.nome)) + "</div></div>",
      iconSize: [150, 140],
      iconAnchor: [75, 70],
    });
  }

  // Logo quebrado: remove a imagem e deixa o pino padrão aparecer.
  document.getElementById("mapa").addEventListener("error", function (e) {
    if (e.target.matches && e.target.matches(".pino img")) {
      e.target.closest(".pino").classList.remove("pino--logo");
      e.target.remove();
    }
  }, true);

  var marcadores = {};
  consulados.forEach(function (c) {
    var m = L.marker([c.lat, c.lng], { icon: icone(c), title: c.nome, riseOnHover: true });
    m.on("click", function () { abrirResumo(c); });
    marcadores[c.id] = m;
  });

  function atualizarResumo() {
    var n = visiveis.length;
    resumo.textContent = n === 0 ? "Nenhum consulado encontrado" : n + " consulado" + (n === 1 ? "" : "s") + " no mapa";
  }

  function filtrar() {
    var termo = normalizar(busca.value.trim());
    visiveis = consulados.filter(function (c) {
      return !termo || [c.nome, c.endereco, c.descricao].some(function (t) { return normalizar(t).indexOf(termo) !== -1; });
    });
    consulados.forEach(function (c) {
      var m = marcadores[c.id];
      if (visiveis.indexOf(c) !== -1) m.addTo(mapa); else m.remove();
    });
    atualizarResumo();
  }

  // Ajusta o zoom para mostrar todos os consulados encontrados.
  function enquadrar() {
    if (!visiveis.length) return;
    if (visiveis.length === 1) {
      mapa.setView([visiveis[0].lat, visiveis[0].lng], 14);
      return;
    }
    var limites = L.latLngBounds(visiveis.map(function (c) { return [c.lat, c.lng]; }));
    mapa.fitBounds(limites, { paddingTopLeft: [60, 140], paddingBottomRight: [60, 80], maxZoom: 14 });
  }

  function selecionar(id) {
    var anterior = selecionadoId;
    selecionadoId = id;
    [anterior, id].forEach(function (i) {
      var c = consulados.find(function (x) { return x.id === i; });
      if (c) marcadores[c.id].setIcon(icone(c));
    });
  }

  function abrirResumo(c) {
    selecionar(c.id);
    mapa.setView([c.lat, c.lng], Math.max(mapa.getZoom(), 11));

    var foto = document.getElementById("folha-foto");
    foto.innerHTML = '<span class="icon">storefront</span>';
    if (c.foto) {
      var img = new Image();
      img.alt = "";
      img.onerror = function () { img.remove(); };
      img.src = c.foto;
      foto.appendChild(img);
    }
    document.getElementById("folha-nome").textContent = c.nome;
    document.getElementById("folha-endereco").textContent = c.endereco;
    document.getElementById("folha-descricao").textContent = c.descricao;
    document.getElementById("folha-pills").innerHTML =
      '<span class="pill"><span class="icon">groups</span>' + membros(c.membros) + "</span>" +
      (c.eh_membro ? '<span class="pill pill--vermelho"><span class="icon">check</span>Você é membro</span>' : "");

    var whatsapp = document.getElementById("folha-whatsapp");
    if (c.whatsapp) {
      whatsapp.href = c.whatsapp;
      whatsapp.removeAttribute("aria-disabled");
    } else {
      whatsapp.removeAttribute("href");
      whatsapp.setAttribute("aria-disabled", "true");
    }
    document.getElementById("folha-detalhes").href = c.url;
    folha.hidden = false;
  }

  function fecharResumo() {
    folha.hidden = true;
    selecionar(null);
  }

  var espera;
  busca.addEventListener("input", function () {
    clearTimeout(espera);
    espera = setTimeout(function () { filtrar(); enquadrar(); }, 250);
  });
  busca.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { clearTimeout(espera); filtrar(); enquadrar(); }
  });
  document.getElementById("enquadrar").addEventListener("click", enquadrar);
  document.getElementById("fechar-folha").addEventListener("click", fecharResumo);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !folha.hidden) fecharResumo(); });
  mapa.on("click", function () { if (!folha.hidden) fecharResumo(); });

  filtrar();
  enquadrar();
})();
