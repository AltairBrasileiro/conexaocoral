/*
 * Mapa de fundo com os nomes em português do Brasil.
 *
 * Os tiles comuns do OpenStreetMap (imagens prontas) mostram cada lugar no idioma
 * local ("Bolivia", "Paraguay / Paraguái"). Para traduzir, usamos os tiles
 * vetoriais do OpenFreeMap, feitos com os mesmos dados do OpenStreetMap, e
 * trocamos o texto dos rótulos por "name:pt" (com o nome original como reserva).
 * O desenho é do MapLibre, integrado ao Leaflet pelo plugin maplibre-gl-leaflet,
 * então marcadores e cliques continuam sendo do Leaflet.
 *
 * Sem WebGL (navegador antigo ou aceleração desligada), volta aos tiles do OSM.
 */
window.CoralMapa = (function () {
  "use strict";

  var ESTILO = "https://tiles.openfreemap.org/styles/liberty";
  var ATRIBUICAO_VETORIAL =
    '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> ' +
    '&copy; <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> ' +
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">colaboradores do OpenStreetMap</a>';
  var ATRIBUICAO_OSM =
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">colaboradores do OpenStreetMap</a>';
  var NOME_EM_PORTUGUES = ["coalesce", ["get", "name:pt"], ["get", "name"]];

  function temWebGL() {
    try {
      var canvas = document.createElement("canvas");
      return !!(window.WebGLRenderingContext && (canvas.getContext("webgl2") || canvas.getContext("webgl")));
    } catch (e) {
      return false;
    }
  }

  // Troca o texto de todo rótulo que exibe um nome (ruas, cidades, países, rios...).
  // Rótulos de número de casa e de placa de rodovia não usam "name" e ficam como estão.
  function traduzir(estilo) {
    estilo.layers.forEach(function (camada) {
      var texto = camada.layout && camada.layout["text-field"];
      if (texto && JSON.stringify(texto).indexOf('"name') !== -1) {
        camada.layout["text-field"] = NOME_EM_PORTUGUES;
      }
    });
    return estilo;
  }

  function json(resposta) {
    if (!resposta.ok) throw new Error("HTTP " + resposta.status);
    return resposta.json();
  }

  // O crédito exibido no rodapé vem do TileJSON de cada fonte ("Data from OpenStreetMap").
  // Lemos o TileJSON aqui e embutimos os tiles na fonte, já com o crédito em português.
  function creditoEmPortugues(estilo) {
    var fontes = Object.keys(estilo.sources).filter(function (nome) { return estilo.sources[nome].url; });
    return Promise.all(fontes.map(function (nome) {
      var fonte = estilo.sources[nome];
      return fetch(fonte.url).then(json).then(function (tilejson) {
        delete fonte.url;
        fonte.tiles = tilejson.tiles;
        ["minzoom", "maxzoom", "bounds", "scheme"].forEach(function (campo) {
          if (tilejson[campo] !== undefined) fonte[campo] = tilejson[campo];
        });
        fonte.attribution = ATRIBUICAO_VETORIAL;
      });
    })).then(function () {
      // As demais fontes (ex.: relevo) não repetem o crédito.
      Object.keys(estilo.sources).forEach(function (nome) {
        if (fontes.indexOf(nome) === -1) delete estilo.sources[nome].attribution;
      });
      return estilo;
    });
  }

  function tilesOSM(mapa) {
    // A política de uso do OSM exige o Referer; o Django envia "Referrer-Policy:
    // same-origin", que o omite em outros domínios. Os tiles mandam só a origem do site.
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      referrerPolicy: "strict-origin-when-cross-origin",
      attribution: ATRIBUICAO_OSM,
    }).addTo(mapa);
  }

  function camadaBase(mapa) {
    if (!temWebGL() || !L.maplibreGL || !window.maplibregl) {
      tilesOSM(mapa);
      return;
    }
    fetch(ESTILO)
      .then(json)
      .then(function (estilo) { return creditoEmPortugues(traduzir(estilo)); })
      .then(function (estilo) {
        L.maplibreGL({ style: estilo, attribution: ATRIBUICAO_VETORIAL }).addTo(mapa);
      })
      .catch(function () { tilesOSM(mapa); });
  }

  return { camadaBase: camadaBase };
})();
