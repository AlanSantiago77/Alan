/* =====================================================================
   Interacciones del sitio: tema, aparición al desplazarse, contadores,
   barra de lectura, filtro de prácticas y visor de imágenes.
   Sin dependencias externas. Compatible con Material for MkDocs.
   ===================================================================== */
(function () {
  "use strict";

  var reducido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Interruptor de tema ---------- */
  function iniciarTema() {
    document.querySelectorAll("[data-tema-switch]").forEach(function (btn) {
      if (btn.dataset.listo) return;
      btn.dataset.listo = "1";
      btn.addEventListener("click", function () {
        var visible = document.querySelector('form[data-md-component="palette"] label:not([hidden])');
        if (visible) visible.click();
      });
    });
  }

  /* ---------- Aparición al desplazarse ---------- */
  function iniciarReveal() {
    var items = Array.prototype.slice.call(document.querySelectorAll(".reveal:not(.is-visible)"));
    if (!items.length) return;
    if (reducido || !("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    // Retraso escalonado dentro de cada rejilla
    items.forEach(function (el) {
      var padre = el.parentElement;
      if (!padre) return;
      var hermanos = Array.prototype.filter.call(padre.children, function (h) { return h.classList.contains("reveal"); });
      var i = hermanos.indexOf(el);
      el.style.setProperty("--retraso", Math.min(i, 8) * 70 + "ms");
    });
    var obs = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-visible");
          obs.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.08 });
    items.forEach(function (el) { obs.observe(el); });
  }

  /* ---------- Contadores animados ---------- */
  function iniciarContadores() {
    var nums = document.querySelectorAll("[data-contar]");
    if (!nums.length || reducido) return;
    nums.forEach(function (el) {
      var fin = parseInt(el.getAttribute("data-contar"), 10);
      if (!isFinite(fin) || fin <= 0) return;
      var inicio = null, dur = 1100;
      el.textContent = "0";
      function paso(t) {
        if (inicio === null) inicio = t;
        var p = Math.min(1, (t - inicio) / dur);
        var e = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(fin * e);
        if (p < 1) requestAnimationFrame(paso);
      }
      requestAnimationFrame(paso);
    });
    // Anillo de avance: animar desde vacío
    document.querySelectorAll(".stat__anillo-valor").forEach(function (c) {
      var final = c.getAttribute("stroke-dashoffset");
      var total = c.getAttribute("stroke-dasharray");
      c.style.strokeDashoffset = total;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { c.style.strokeDashoffset = final; });
      });
    });
  }

  /* ---------- Barra de progreso de lectura ---------- */
  function iniciarBarraLectura() {
    var barra = document.querySelector("[data-barra-lectura]");
    var contenido = document.querySelector(".md-content__inner");
    if (!barra || !contenido || document.querySelector(".hero")) return;
    var span = barra.firstElementChild;
    var pendiente = false;
    function actualizar() {
      pendiente = false;
      var rect = contenido.getBoundingClientRect();
      var total = contenido.offsetHeight - window.innerHeight + 120;
      if (total <= 0) { barra.classList.remove("is-visible"); return; }
      var p = Math.min(1, Math.max(0, -rect.top / total));
      span.style.setProperty("--progreso", p.toFixed(4));
      barra.classList.toggle("is-visible", p > 0.005);
    }
    function pedir() { if (!pendiente) { pendiente = true; requestAnimationFrame(actualizar); } }
    window.addEventListener("scroll", pedir, { passive: true });
    window.addEventListener("resize", pedir);
    actualizar();
  }

  /* ---------- Filtro del índice de prácticas ---------- */
  function iniciarFiltro() {
    var zona = document.querySelector("[data-filtro-practicas]");
    if (!zona) return;
    var input = zona.querySelector("[data-filtro-texto]");
    var chips = zona.querySelectorAll("[data-filtro-materia]");
    var tarjetas = zona.querySelectorAll("[data-filtro-lista] .tarjeta-practica");
    var vacio = zona.querySelector("[data-filtro-vacio]");
    var materia = "";
    function normal(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
    function aplicar() {
      var q = normal(input.value).trim().split(/\s+/).filter(Boolean);
      var visibles = 0;
      tarjetas.forEach(function (t) {
        var texto = normal(t.getAttribute("data-filtro"));
        var ok = (!materia || t.getAttribute("data-materia") === materia) &&
                 q.every(function (w) { return texto.indexOf(w) !== -1; });
        t.classList.toggle("is-oculta", !ok);
        if (ok) { visibles++; t.classList.add("is-visible"); }
      });
      if (vacio) vacio.hidden = visibles !== 0;
    }
    input.addEventListener("input", aplicar);
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        chips.forEach(function (o) { o.classList.remove("is-activo"); o.setAttribute("aria-pressed", "false"); });
        c.classList.add("is-activo");
        c.setAttribute("aria-pressed", "true");
        materia = c.getAttribute("data-filtro-materia");
        aplicar();
      });
    });
  }

  /* ---------- Visor de imágenes ---------- */
  var ICONOS = {
    cerrar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
    prev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.41 16.59 10.83 12l4.58-4.59L14 6l-6 6 6 6z"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.59 16.59 13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>',
    abrir: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3m-2 16H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2z"/></svg>'
  };
  var visor = null, lista = [], actual = 0, ultimoFoco = null;

  function crearVisor() {
    if (visor) return visor;
    visor = document.createElement("div");
    visor.className = "visor";
    visor.setAttribute("role", "dialog");
    visor.setAttribute("aria-modal", "true");
    visor.setAttribute("aria-label", "Visor de imágenes");
    visor.innerHTML =
      '<div class="visor__barra"><span class="visor__contador" aria-live="polite"></span>' +
      '<span><a class="visor__btn visor__abrir" target="_blank" rel="noopener" title="Abrir imagen original" aria-label="Abrir imagen original">' + ICONOS.abrir + '</a> ' +
      '<button class="visor__btn visor__cerrar" type="button" title="Cerrar (Esc)" aria-label="Cerrar">' + ICONOS.cerrar + "</button></span></div>" +
      '<div class="visor__escena">' +
      '<button class="visor__btn visor__nav visor__nav--prev" type="button" aria-label="Imagen anterior">' + ICONOS.prev + "</button>" +
      '<img class="visor__img" alt="">' +
      '<button class="visor__btn visor__nav visor__nav--next" type="button" aria-label="Imagen siguiente">' + ICONOS.next + "</button>" +
      "</div>" +
      '<div class="visor__pie"></div>';
    document.body.appendChild(visor);

    visor.querySelector(".visor__cerrar").addEventListener("click", cerrar);
    visor.querySelector(".visor__nav--prev").addEventListener("click", function () { mover(-1); });
    visor.querySelector(".visor__nav--next").addEventListener("click", function () { mover(1); });
    visor.querySelector(".visor__escena").addEventListener("click", function (e) {
      if (e.target === e.currentTarget) cerrar();
    });
    document.addEventListener("keydown", function (e) {
      if (!visor.classList.contains("is-abierto")) return;
      if (e.key === "Escape") cerrar();
      else if (e.key === "ArrowLeft") mover(-1);
      else if (e.key === "ArrowRight") mover(1);
      else if (e.key === "Tab") {
        var focos = visor.querySelectorAll("button:not([hidden]), a[href]");
        var a = focos[0], z = focos[focos.length - 1];
        if (e.shiftKey && document.activeElement === a) { z.focus(); e.preventDefault(); }
        else if (!e.shiftKey && document.activeElement === z) { a.focus(); e.preventDefault(); }
      }
    });
    // Gestos táctiles
    var x0 = null;
    var escena = visor.querySelector(".visor__escena");
    escena.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    escena.addEventListener("touchend", function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 50) mover(dx < 0 ? 1 : -1);
      x0 = null;
    });
    return visor;
  }

  function leyenda(img) {
    var fig = img.closest("figure");
    var cap = fig && fig.querySelector("figcaption");
    var texto = cap ? cap.textContent.trim() : "";
    return texto || img.getAttribute("alt") || "";
  }

  function mostrar(i) {
    actual = (i + lista.length) % lista.length;
    var origen = lista[actual];
    var img = visor.querySelector(".visor__img");
    img.classList.remove("is-lista");
    var src = origen.currentSrc || origen.src;
    var nueva = new Image();
    nueva.onload = nueva.onerror = function () {
      img.src = src;
      img.alt = origen.getAttribute("alt") || "";
      requestAnimationFrame(function () { img.classList.add("is-lista"); });
    };
    nueva.src = src;
    visor.querySelector(".visor__abrir").href = src;
    visor.querySelector(".visor__pie").textContent = leyenda(origen);
    visor.querySelector(".visor__contador").textContent = lista.length > 1 ? (actual + 1) + " / " + lista.length : "";
    var multi = lista.length > 1;
    visor.querySelector(".visor__nav--prev").hidden = !multi;
    visor.querySelector(".visor__nav--next").hidden = !multi;
  }

  function mover(d) { if (lista.length > 1) mostrar(actual + d); }

  function abrir(grupo, i) {
    crearVisor();
    lista = grupo;
    ultimoFoco = document.activeElement;
    document.documentElement.classList.add("visor-activo");
    visor.classList.add("is-abierto");
    mostrar(i);
    visor.querySelector(".visor__cerrar").focus();
  }

  function cerrar() {
    if (!visor) return;
    visor.classList.remove("is-abierto");
    document.documentElement.classList.remove("visor-activo");
    if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  }

  function iniciarVisor() {
    var art = document.querySelector(".md-content__inner");
    if (!art) return;
    var imgs = Array.prototype.filter.call(art.querySelectorAll("img"), function (img) {
      return !img.closest("a") && !img.classList.contains("no-zoom") &&
             !img.closest(".tarjeta-materia, .tarjeta-practica, .materia-banner, .twemoji, .emojione, .grid.cards");
    });
    imgs.forEach(function (img, i) {
      if (img.dataset.visor) return;
      img.dataset.visor = "1";
      img.setAttribute("tabindex", "0");
      img.setAttribute("role", "button");
      img.setAttribute("aria-label", "Ampliar imagen" + (img.alt ? ": " + img.alt : ""));
      img.addEventListener("click", function () { abrir(imgs, i); });
      img.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(imgs, i); }
      });
    });
  }

  /* ---------- Arranque ---------- */
  function iniciar() {
    iniciarTema();
    iniciarReveal();
    iniciarContadores();
    iniciarBarraLectura();
    iniciarFiltro();
    iniciarVisor();
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(iniciar);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
