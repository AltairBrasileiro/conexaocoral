/*
 * Localização do consulado na solicitação de cadastro. Três jeitos de marcar o ponto:
 *   1. "Localizar o endereço digitado": busca no Nominatim (geocodificador do OpenStreetMap);
 *   2. "Usar minha localização": GPS/localização do navegador;
 *   3. clique direto no mapa.
 * Depois, o pino pode ser arrastado para o ajuste fino. Ao marcar pelo mapa ou pelo
 * GPS, o campo de endereço é preenchido pela busca reversa do Nominatim.
 */
(function () {
  "use strict";

  var latitude = document.getElementById("id_latitude");
  var longitude = document.getElementById("id_longitude");
  var endereco = document.getElementById("id_endereco");
  var ajuda = document.getElementById("local-ajuda");
  var botaoBuscar = document.getElementById("local-buscar");
  var botaoGps = document.getElementById("local-gps");

  var mapa = L.map("mapa-local").setView([-8.05, -34.9], 6); // Recife
  CoralMapa.camadaBase(mapa);

  // Garante o tamanho certo do mapa se o layout mudar depois de criado (fontes, imagens).
  window.addEventListener("load", function () { mapa.invalidateSize(); });

  var pino = null;
  var esperaEndereco = null;
  var buscaEndereco = null;

  // "Avenida Epitácio Pessoa, 1000 - Tambaú, João Pessoa - PB".
  function formatarEndereco(r) {
    var a = r.address || {};
    var rua = [a.road || a.pedestrian || a.footway || a.square || "", a.house_number || ""]
      .filter(Boolean).join(", ");
    var bairro = a.suburb || a.neighbourhood || a.quarter || a.city_district || "";
    var cidade = a.city || a.town || a.village || a.municipality || "";
    var uf = (a["ISO3166-2-lvl4"] || "").replace(/^BR-/, "") || a.state || "";
    var local = [rua, bairro].filter(Boolean).join(" - ");
    var municipio = [cidade, uf].filter(Boolean).join(" - ");
    return [local, municipio].filter(Boolean).join(", ") || r.display_name || "";
  }

  // Política do Nominatim: no máximo 1 busca por segundo. Esperamos o pino parar
  // (ex.: fim do arraste) e cancelamos a busca anterior, se ainda estiver em andamento.
  function preencherEndereco(latlng) {
    clearTimeout(esperaEndereco);
    esperaEndereco = setTimeout(function () {
      if (buscaEndereco) buscaEndereco.abort();
      buscaEndereco = new AbortController();
      avisar("Buscando o endereço deste ponto…");
      var url = "https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=18&addressdetails=1" +
        "&accept-language=pt-BR&lat=" + latlng.lat.toFixed(6) + "&lon=" + latlng.lng.toFixed(6);
      fetch(url, {
        signal: buscaEndereco.signal,
        referrerPolicy: "strict-origin-when-cross-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (resposta) {
          if (!resposta.ok) throw new Error("HTTP " + resposta.status);
          return resposta.json();
        })
        .then(function (resultado) {
          var texto = resultado.error ? "" : formatarEndereco(resultado);
          if (!texto) {
            avisar("Local marcado, mas não achamos o endereço deste ponto. Digite-o no campo acima.", true);
            return;
          }
          endereco.value = texto;
          endereco.classList.add("campo--atualizado");
          setTimeout(function () { endereco.classList.remove("campo--atualizado"); }, 1500);
          avisar("Endereço preenchido pelo mapa. Confira o número e o bairro e corrija, se precisar.");
        })
        .catch(function (erro) {
          if (erro.name === "AbortError") return;
          avisar("Local marcado. Não conseguimos buscar o endereço agora: digite-o no campo acima.", true);
        });
    }, 700);
  }

  function avisar(texto, erro) {
    ajuda.textContent = texto;
    ajuda.classList.toggle("campo__msg", !!erro);
  }

  function marcar(latlng, zoom, atualizarEndereco) {
    // O banco guarda 6 casas decimais (~10 cm de precisão).
    latitude.value = latlng.lat.toFixed(6);
    longitude.value = latlng.lng.toFixed(6);
    if (!pino) {
      pino = L.marker(latlng, { draggable: true, title: "Local do consulado" }).addTo(mapa);
      pino.on("dragend", function () { marcar(pino.getLatLng(), null, true); });
    } else {
      pino.setLatLng(latlng);
    }
    if (zoom) mapa.setView(latlng, zoom);
    avisar("Local marcado. Arraste o pino para ajustar, se precisar.");
    if (atualizarEndereco) preencherEndereco(latlng);
  }

  function ocupado(botao, sim) {
    botao.disabled = sim;
    botao.setAttribute("aria-busy", sim ? "true" : "false");
  }

  // Política de uso do Nominatim: uma busca por clique (sem autocompletar) e com Referer.
  botaoBuscar.addEventListener("click", function () {
    var texto = endereco.value.trim();
    if (texto.length < 5) {
      avisar("Digite o endereço completo (rua, número, cidade) no campo acima e tente de novo.", true);
      endereco.focus();
      return;
    }
    ocupado(botaoBuscar, true);
    avisar("Procurando o endereço…");
    var url = "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=br" +
      "&accept-language=pt-BR&q=" + encodeURIComponent(texto);
    fetch(url, { referrerPolicy: "strict-origin-when-cross-origin", headers: { Accept: "application/json" } })
      .then(function (resposta) {
        if (!resposta.ok) throw new Error("HTTP " + resposta.status);
        return resposta.json();
      })
      .then(function (resultados) {
        if (!resultados.length) {
          avisar("Não encontramos esse endereço. Confira o texto ou clique no mapa para marcar o local.", true);
          return;
        }
        marcar(L.latLng(parseFloat(resultados[0].lat), parseFloat(resultados[0].lon)), 17);
        avisar("Endereço encontrado. Confira o pino e arraste para ajustar, se precisar.");
      })
      .catch(function () {
        avisar("A busca de endereço não respondeu agora. Clique no mapa para marcar o local.", true);
      })
      .finally(function () { ocupado(botaoBuscar, false); });
  });

  botaoGps.addEventListener("click", function () {
    if (!navigator.geolocation) {
      avisar("Seu navegador não informa a localização. Use a busca pelo endereço ou clique no mapa.", true);
      return;
    }
    ocupado(botaoGps, true);
    avisar("Obtendo sua localização…");
    navigator.geolocation.getCurrentPosition(
      function (posicao) {
        ocupado(botaoGps, false);
        marcar(L.latLng(posicao.coords.latitude, posicao.coords.longitude), 17, true);
      },
      function () {
        ocupado(botaoGps, false);
        avisar("Não foi possível obter sua localização (permissão negada?). Use a busca ou clique no mapa.", true);
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  });

  // Formulário reenviado com erro: mantém o ponto já escolhido.
  if (latitude.value && longitude.value) {
    marcar(L.latLng(parseFloat(latitude.value), parseFloat(longitude.value)), 16);
  }
  mapa.on("click", function (e) { marcar(e.latlng, null, true); });
})();
