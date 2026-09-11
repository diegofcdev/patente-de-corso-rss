# Patente de corso — RSS histórico completo

Este proyecto genera un único RSS con todo el archivo de la etiqueta:

https://www.zendalibros.com/tag/patente-de-corso/

Primero intenta usar la API REST pública de WordPress, que permite descargar hasta
100 artículos por petición. Si Zenda bloquease esa API, utiliza automáticamente
como alternativa el RSS paginado (`?paged=2`, `?paged=3`, etc.).

El resultado se publica como `docs/feed.xml`.

## 1. Crear el repositorio

En GitHub crea un repositorio público, por ejemplo:

`patente-de-corso-rss`

## 2. Subir estos archivos

Sube el contenido de esta carpeta conservando las rutas:

- `build_feed.py`
- `requirements.txt`
- `.github/workflows/update-feed.yml`
- `docs/index.html`
- `docs/.nojekyll`

## 3. Ejecutar por primera vez

En GitHub:

**Actions → Actualizar RSS completo → Run workflow**

Abre el log. Al terminar verás el método utilizado y el número total de artículos
recuperados. Además aparecerá:

`docs/feed.xml`

## 4. Activar GitHub Pages

En el repositorio:

**Settings → Pages → Build and deployment → Deploy from a branch**

Selecciona:

- Branch: `main`
- Folder: `/docs`

Guarda.

## 5. URL del RSS

Con usuario `TUUSUARIO` y repositorio `patente-de-corso-rss`:

`https://TUUSUARIO.github.io/patente-de-corso-rss/feed.xml`

Añade esa dirección directamente a tu lector RSS.

## NetNewsWire en iPhone/iPad

1. Pulsa **Add Feed**.
2. Pega la URL anterior.
3. Para la primera prueba, puedes guardarlo en **On My iPhone/iPad**.
4. El feed se podrá ordenar por fecha y los artículos mantendrán enlaces estables a Zenda.

## Actualización automática

La GitHub Action reconstruye el feed una vez al día. Los GUID de los artículos son
estables, por lo que las entradas antiguas no deberían reaparecer como nuevas.

También puedes ejecutar la Action manualmente en cualquier momento.

## Qué contiene el feed

Incluye título, enlace, fecha y el resumen que WordPress publica. El artículo
completo sigue alojado en Zenda; al abrirlo, el lector te lleva a la publicación
original.
