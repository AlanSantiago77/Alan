"""
Catálogo automático de materias y prácticas
===========================================

Hook de MkDocs (no requiere instalar nada extra). Se ejecuta en cada
``mkdocs build`` / ``mkdocs serve`` / ``mkdocs gh-deploy`` y:

1. Recorre ``docs/`` y lee el *front matter* (bloque ``---`` al inicio) de
   cada archivo Markdown.
2. Detecta las **materias** (archivos con ``tipo: materia``, normalmente el
   ``index.md`` de la carpeta de cada materia) y las **prácticas**
   (archivos con ``tipo: practica``).
3. Construye la navegación lateral (Inicio, Materias, Herramientas) sin que
   tengas que editar ``mkdocs.yml``.
4. Calcula las estadísticas (prácticas registradas, avance, periodo),
   las prácticas recientes y la galería, y las deja disponibles para las
   plantillas en ``config.extra.catalogo``.
5. Convierte los videos insertados como imagen (``![texto](video.mp4)``) en
   reproductores de video y añade carga diferida a las imágenes.

Para agregar una práctica basta con crear su archivo ``.md`` con el front
matter mínimo (ver ``docs/_plantillas/practica.md``).
"""

from __future__ import annotations

import logging
import os
import posixpath
import re
from urllib.parse import quote, unquote

from mkdocs.utils.meta import get_data

log = logging.getLogger("mkdocs.hooks.catalogo")

IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif"}
VID_EXT = {".mp4", ".webm", ".mov", ".m4v"}

# Carpetas que nunca se consideran evidencias de prácticas
CARPETAS_IGNORADAS_GALERIA = {"recursos", "assets", "portadas", "_plantillas"}

PARCIAL_RE = re.compile(r"(primer|segundo|tercer|cuarto|quinto)[ _-]?parc?i?al", re.I)
PARCIAL_NUM = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5}
PARCIAL_NOMBRE = {
    1: "Primer Parcial",
    2: "Segundo Parcial",
    3: "Tercer Parcial",
    4: "Cuarto Parcial",
    5: "Quinto Parcial",
}

MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)>]+?)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
HTML_IMG_RE = re.compile(r"<img[^>]*?src=[\"']([^\"']+)[\"'][^>]*>", re.I)
FENCE_RE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)

# Estado compartido entre eventos de una misma compilación
_CAT: dict = {}
_POR_SRC: dict = {}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _excluido(config, rel: str) -> bool:
    partes = rel.split("/")
    if any(p.startswith((".", "_")) for p in partes):
        return True
    spec = config.get("exclude_docs")
    if spec is not None:
        try:
            if spec.match_file(rel):
                return True
        except Exception:  # pragma: no cover - versiones antiguas de mkdocs
            pass
    return False


def _resolver(dir_md: str, ruta: str) -> str | None:
    """Convierte una ruta relativa de un .md en ruta relativa a docs/."""
    ruta = unquote(ruta.strip())
    if re.match(r"^[a-z]+://", ruta) or ruta.startswith(("#", "data:", "mailto:")):
        return None
    ruta = ruta.split("#")[0].split("?")[0]
    if ruta.startswith("/"):
        return posixpath.normpath(ruta.lstrip("/"))
    return posixpath.normpath(posixpath.join(dir_md, ruta))


def _parcial(rel: str, meta: dict) -> int | None:
    valor = meta.get("parcial")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor)
    for parte in rel.split("/"):
        m = PARCIAL_RE.search(parte)
        if m:
            return PARCIAL_NUM[m.group(1).lower()]
    return None


def _resumen(cuerpo: str, largo: int = 150) -> str:
    texto = FENCE_RE.sub("", cuerpo)
    for bloque in re.split(r"\n\s*\n", texto):
        b = bloque.strip()
        if not b or b.startswith(("#", "!", "<", "|", "-", "*", "/", ">", "?", "1.", "---")):
            continue
        b = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", b)
        b = re.sub(r"[*_`]", "", b)
        b = " ".join(b.split())
        if len(b) > largo:
            b = b[:largo].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
        return b
    return ""


def _medios(cuerpo: str, dir_md: str, docs_dir: str):
    """Devuelve (imagenes, videos) referenciados en el Markdown."""
    texto = FENCE_RE.sub("", cuerpo)
    encontrados = []
    for m in MD_IMG_RE.finditer(texto):
        encontrados.append((m.group(1).strip(), m.group(2)))
    for m in HTML_IMG_RE.finditer(texto):
        alt = re.search(r"alt=[\"']([^\"']*)[\"']", m.group(0))
        encontrados.append(((alt.group(1) if alt else ""), m.group(1)))

    imagenes, videos, vistos = [], [], set()
    for alt, ruta in encontrados:
        rel = _resolver(dir_md, ruta)
        if not rel or rel in vistos:
            continue
        vistos.add(rel)
        existe = os.path.isfile(os.path.join(docs_dir, rel))
        ext = posixpath.splitext(rel)[1].lower()
        item = {"ruta": rel, "url": quote(rel), "alt": alt, "existe": existe}
        if ext in VID_EXT:
            poster = _poster(rel, docs_dir)
            item["poster"] = quote(poster) if poster else None
            videos.append(item)
        elif ext in IMG_EXT:
            imagenes.append(item)
    return imagenes, videos


def _poster(video_rel: str, docs_dir: str) -> str | None:
    carpeta, nombre = posixpath.split(video_rel)
    base = posixpath.splitext(nombre)[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        cand = posixpath.join(carpeta, "portadas", base + ext)
        if os.path.isfile(os.path.join(docs_dir, cand)):
            return cand
    return None


def _a_lista(valor) -> list:
    if valor is None:
        return []
    if isinstance(valor, (list, tuple)):
        return [str(v) for v in valor if v is not None]
    return [s.strip() for s in str(valor).split(",") if s.strip()]


# ---------------------------------------------------------------------------
# Eventos de MkDocs
# ---------------------------------------------------------------------------

def on_config(config, **kwargs):
    docs_dir = config["docs_dir"]
    extra = config["extra"]

    materias: dict[str, dict] = {}
    practicas: list[dict] = []
    herramientas: list[dict] = []
    paginas: dict[str, dict] = {}
    referenciados: set[str] = set()

    for raiz, dirs, archivos in os.walk(docs_dir):
        dirs.sort()
        for nombre in sorted(archivos):
            if not nombre.lower().endswith(".md"):
                continue
            abs_path = os.path.join(raiz, nombre)
            rel = os.path.relpath(abs_path, docs_dir).replace(os.sep, "/")
            if _excluido(config, rel):
                continue
            try:
                with open(abs_path, encoding="utf-8-sig") as fh:
                    cuerpo, meta = get_data(fh.read())
            except Exception as exc:  # pragma: no cover
                log.warning("No se pudo leer %s: %s", rel, exc)
                continue
            meta = meta or {}
            dir_md = posixpath.dirname(rel)
            tipo = str(meta.get("tipo", "")).lower()
            titulo = meta.get("title")
            if not titulo:
                h1 = re.search(r"^#\s+(.+)$", cuerpo, re.M)
                titulo = h1.group(1).strip() if h1 else posixpath.splitext(nombre)[0]
            paginas[rel] = {"src": rel, "titulo": titulo, "meta": meta}

            if tipo == "materia":
                slug = str(meta.get("slug") or posixpath.basename(dir_md) or "general").lower()
                portada = meta.get("portada")
                portada_rel = _resolver(dir_md, portada) if portada else None
                materias[slug] = {
                    "slug": slug,
                    "src": rel,
                    "dir": dir_md,
                    "nombre": titulo,
                    "corto": meta.get("nombre_corto") or titulo,
                    "descripcion": meta.get("descripcion", ""),
                    "icono": meta.get("icono", "material/book-open-variant"),
                    "color": meta.get("color", "azul"),
                    "orden": meta.get("orden", 99),
                    "portada": quote(portada_rel) if portada_rel else None,
                    "practicas": [],
                    "url": None,
                }
            elif tipo == "practica":
                imagenes, videos = _medios(cuerpo, dir_md, docs_dir)
                for m in imagenes + videos:
                    referenciados.add(m["ruta"])
                portada = meta.get("portada")
                portada_rel = _resolver(dir_md, portada) if portada else None
                if not portada_rel:
                    ok = [i for i in imagenes if i["existe"]]
                    if ok:
                        portada_rel = ok[0]["ruta"]
                    else:
                        for v in videos:
                            p = _poster(v["ruta"], docs_dir)
                            if p:
                                portada_rel = p
                                break
                numero = meta.get("numero", meta.get("practica"))
                try:
                    numero = int(numero)
                except (TypeError, ValueError):
                    numero = None
                fecha = meta.get("fecha")
                practicas.append({
                    "src": rel,
                    "dir": dir_md,
                    "titulo": titulo,
                    "numero": numero,
                    "numero_txt": f"{numero:02d}" if numero is not None else "—",
                    "materia_slug": str(meta.get("materia", "")).lower() or None,
                    "fecha": str(fecha) if fecha else None,
                    "parcial": _parcial(rel, meta),
                    "resumen": meta.get("resumen") or _resumen(cuerpo),
                    "portada": quote(portada_rel) if portada_rel else None,
                    "imagenes": imagenes,
                    "videos": videos,
                    "materiales": _a_lista(meta.get("materiales")),
                    "etiquetas": _a_lista(meta.get("etiquetas")),
                    "url": None,
                })
            elif tipo == "herramienta":
                herramientas.append({
                    "src": rel,
                    "titulo": meta.get("nav_titulo") or titulo,
                    "orden": meta.get("orden", 99),
                })

    # Asociar prácticas con su materia (explícita o por carpeta más cercana)
    por_dir = {m["dir"]: m for m in materias.values()}
    sin_materia = {
        "slug": "otras", "src": None, "dir": None, "nombre": "Otras prácticas",
        "corto": "Otras", "descripcion": "Prácticas sin materia asignada.",
        "icono": "material/folder-outline", "color": "violeta", "orden": 999,
        "portada": None, "practicas": [], "url": None,
    }
    for p in practicas:
        materia = materias.get(p["materia_slug"]) if p["materia_slug"] else None
        d = p["dir"]
        while materia is None:
            if d in por_dir:
                materia = por_dir[d]
                break
            if not d:
                break
            d = posixpath.dirname(d)
        if materia is None:
            materia = materias.setdefault("otras", sin_materia)
        p["materia"] = materia["slug"]
        p["materia_nombre"] = materia["nombre"]
        p["materia_icono"] = materia["icono"]
        p["materia_color"] = materia["color"]
        materia["practicas"].append(p)

    orden_materias = sorted(materias.values(), key=lambda m: (m["orden"], m["nombre"]))
    for m in orden_materias:
        m["practicas"].sort(key=lambda p: (p["parcial"] or 0, p["numero"] if p["numero"] is not None else 999, p["titulo"]))
        m["total"] = len(m["practicas"])
        for i, p in enumerate(m["practicas"]):
            p["anterior"] = m["practicas"][i - 1]["src"] if i > 0 else None
            p["siguiente"] = m["practicas"][i + 1]["src"] if i + 1 < len(m["practicas"]) else None

    # Estadísticas
    registradas = len(practicas)
    try:
        previstas = int(extra.get("practicas_previstas", 30)) or 30
    except (TypeError, ValueError):
        previstas = 30
    avance = min(100, round(registradas / previstas * 100)) if previstas else 0
    parciales = [p["parcial"] for p in practicas if p["parcial"]]
    periodo = extra.get("periodo") or (PARCIAL_NOMBRE.get(max(parciales)) if parciales else "—")

    # Recientes: primero por fecha (si existe), después por parcial y número
    def clave_reciente(p):
        return (p["fecha"] or "", p["parcial"] or 0, p["numero"] or 0)

    try:
        num_recientes = int(extra.get("practicas_recientes", 4))
    except (TypeError, ValueError):
        num_recientes = 4
    recientes = sorted(practicas, key=clave_reciente, reverse=True)[:num_recientes]

    # Galería: evidencias por práctica + archivos multimedia no usados
    otras = []
    for raiz, dirs, archivos in os.walk(docs_dir):
        dirs.sort()
        rel_dir = os.path.relpath(raiz, docs_dir).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        if any(p in CARPETAS_IGNORADAS_GALERIA or p.startswith(".") for p in rel_dir.split("/") if p):
            continue
        for nombre in sorted(archivos):
            ext = posixpath.splitext(nombre)[1].lower()
            rel = posixpath.join(rel_dir, nombre) if rel_dir else nombre
            if ext not in IMG_EXT | VID_EXT or rel in referenciados:
                continue
            if not rel_dir:  # imágenes sueltas en la raíz (logos, etc.)
                continue
            item = {"ruta": rel, "url": quote(rel), "alt": "", "existe": True,
                    "es_video": ext in VID_EXT}
            if item["es_video"]:
                poster = _poster(rel, docs_dir)
                item["poster"] = quote(poster) if poster else None
            otras.append(item)

    total_fotos = sum(len([i for i in p["imagenes"] if i["existe"]]) for p in practicas)
    total_videos = sum(len([v for v in p["videos"] if v["existe"]]) for p in practicas)

    _CAT.clear()
    _CAT.update({
        "materias": orden_materias,
        "practicas": sorted(practicas, key=lambda p: ([m["slug"] for m in orden_materias].index(p["materia"]), p["parcial"] or 0, p["numero"] or 0)),
        "recientes": recientes,
        "otras_evidencias": otras,
        "herramientas": sorted(herramientas, key=lambda h: (h["orden"], h["titulo"])),
        "stats": {
            "registradas": registradas,
            "previstas": previstas,
            "avance": avance,
            "periodo": periodo,
            "materias": len(orden_materias),
            "fotos": total_fotos,
            "videos": total_videos,
        },
        "urls": {},
    })
    _POR_SRC.clear()
    _POR_SRC.update({p["src"]: p for p in practicas})
    extra["catalogo"] = _CAT

    # Navegación automática (se respeta un `nav:` escrito a mano si existe)
    if not config.get("nav") and extra.get("nav_automatica", True):
        nav = []
        if "index.md" in paginas:
            nav.append({"Inicio": "index.md"})
        seccion = []
        if "materias.md" in paginas:
            seccion.append("materias.md")
        for m in orden_materias:
            hijos = ([m["src"]] if m["src"] else []) + [p["src"] for p in m["practicas"]]
            seccion.append({m["nombre"]: hijos})
        if seccion:
            nav.append({"Materias": seccion})
        if herramientas:
            nav.append({"Herramientas": [{h["titulo"]: h["src"]} for h in _CAT["herramientas"]]})
        config["nav"] = nav

    log.info(
        "Catálogo: %d materias, %d prácticas (%d%% de %d), %d evidencias sin asignar",
        len(orden_materias), registradas, avance, previstas, len(otras),
    )
    return config


def on_files(files, config, **kwargs):
    urls = _CAT.setdefault("urls", {})
    for f in files.documentation_pages():
        urls[f.src_uri] = f.url
    for p in _CAT.get("practicas", []):
        p["url"] = urls.get(p["src"])
        p["anterior_url"] = urls.get(p["anterior"]) if p.get("anterior") else None
        p["siguiente_url"] = urls.get(p["siguiente"]) if p.get("siguiente") else None
        if p.get("anterior"):
            p["anterior_titulo"] = _POR_SRC[p["anterior"]]["titulo"]
            p["anterior_num"] = _POR_SRC[p["anterior"]]["numero_txt"]
        if p.get("siguiente"):
            p["siguiente_titulo"] = _POR_SRC[p["siguiente"]]["titulo"]
            p["siguiente_num"] = _POR_SRC[p["siguiente"]]["numero_txt"]
    for m in _CAT.get("materias", []):
        m["url"] = urls.get(m["src"]) if m["src"] else None
    return files


def on_page_markdown(markdown, page, config, files, **kwargs):
    meta = page.meta
    tipo = str(meta.get("tipo", "")).lower()
    if tipo == "practica":
        datos = _POR_SRC.get(page.file.src_uri)
        if datos:
            meta["practica_info"] = datos
            # Etiquetas para el buscador (materia + etiquetas propias)
            meta["tags"] = [datos["materia_nombre"], f"Práctica {datos['numero_txt']}"] + datos["etiquetas"] + datos["materiales"]
        meta.setdefault("icon", "material/file-document-outline")
    elif tipo == "materia":
        for m in _CAT.get("materias", []):
            if m["src"] == page.file.src_uri:
                meta["materia_info"] = m
                meta.setdefault("icon", m["icono"])
                meta["tags"] = [m["nombre"]]
    return markdown


VIDEO_IMG_RE = re.compile(
    r"(?:<p>\s*)?<img\b([^>]*?)\bsrc=\"([^\"]+\.(?:mp4|webm|mov|m4v))\"([^>]*)/?>(?:\s*</p>)?",
    re.I,
)


def on_page_content(html, page, config, files, **kwargs):
    base = page.url if page.url.endswith("/") or not page.url else posixpath.dirname(page.url) + "/"

    def a_video(m):
        attrs = m.group(1) + m.group(3)
        src = m.group(2)
        alt_m = re.search(r'alt="([^"]*)"', attrs)
        alt = alt_m.group(1) if alt_m else ""
        destino = posixpath.normpath(posixpath.join(base, unquote(src)))
        poster_rel = _poster(destino, config["docs_dir"])
        poster_attr = ""
        if poster_rel:
            carpeta, nombre = posixpath.split(src)
            poster_src = posixpath.join(carpeta, "portadas", posixpath.basename(poster_rel))
            poster_attr = f' poster="{poster_src}"'
        ext = posixpath.splitext(src)[1].lower().lstrip(".")
        tipo = "video/quicktime" if ext == "mov" else f"video/{'mp4' if ext == 'm4v' else ext}"
        cap = f"<figcaption>{alt}</figcaption>" if alt else ""
        return (
            f'<figure class="evidencia evidencia--video">'
            f'<video controls preload="metadata" playsinline{poster_attr} aria-label="{alt}">'
            f'<source src="{src}" type="{tipo}">Tu navegador no puede reproducir este video.</video>'
            f"{cap}</figure>"
        )

    html = VIDEO_IMG_RE.sub(a_video, html)
    html = re.sub(r"<img(?![^>]*\bloading=)", '<img loading="lazy" decoding="async"', html)
    return html
