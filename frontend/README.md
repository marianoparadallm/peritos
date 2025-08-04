# Frontend for Scraping Backend

This is a lightweight web interface for triggering and viewing data from the scraping backend.

## Development

Open `index.html` in a browser. The frontend expects the backend API to be available at `http://localhost:8000`:

- `POST /scrape` — inicia el scraping.
- `GET /data` — devuelve los datos scrapeados en formato JSON.

Ajusta la constante `API_BASE` en `main.js` según la URL donde esté desplegado tu backend.

## Deployment

Los archivos son estáticos y pueden alojarse fácilmente en **GitHub Pages** o **Supabase**:

### GitHub Pages

1. Copia la carpeta `frontend` a tu repositorio público.
2. En la configuración del repositorio, habilita GitHub Pages seleccionando la rama y el directorio `/frontend`.
3. Accede al sitio desde `https://<usuario>.github.io/<repositorio>/`.

### Supabase

1. Crea un bucket de almacenamiento público.
2. Sube los archivos de `frontend` al bucket.
3. Sirve el contenido directamente desde Supabase o mediante una función edge.
