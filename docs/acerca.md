---
tipo: herramienta
nav_titulo: Acerca de
orden: 6
title: Acerca de
icon: material/information-outline
---

# Acerca de

Este sitio reúne los **reportes de las prácticas de Mecatrónica** de Alan Santiago, organizados por materia, con sus procedimientos, evidencias y conclusiones.

![IBERO Puebla](recursos/imgs/ibero.jpeg){ .acerca-img }

## Cómo está construido

- **[MkDocs](https://www.mkdocs.org/)** y **[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)** generan el sitio a partir de archivos Markdown.
- **GitHub Actions** publica el sitio en **GitHub Pages** cada vez que se hace `push` a la rama `main`.
- Un *hook* de MkDocs (`hooks/catalogo.py`) lee los metadatos de cada práctica y genera automáticamente la navegación, las estadísticas, las tarjetas de materias, las prácticas recientes y la galería.

## Cómo agregar una práctica

1. Copia `docs/_plantillas/practica.md` dentro de la carpeta de la materia, por ejemplo
   `docs/Primer_Parial/Introduccion_Mecatronica/practica-06-mi-practica.md`.
2. Guarda las fotografías en `docs/Primer_Parial/pruebas/` (o en otra carpeta) y enlázalas desde el reporte.
3. Llena el bloque de metadatos (`numero`, `title` y, si quieres, `fecha` y `portada`).
4. Ejecuta `mkdocs serve` para revisarla y después haz `commit` y `push`.

El contador de prácticas, el porcentaje de avance, las tarjetas de materias, el índice y las prácticas recientes se actualizan solos.

## Repositorio

[:fontawesome-brands-github: AlanSantiago77/Alan](https://github.com/AlanSantiago77/Alan){ .md-button .md-button--primary }
