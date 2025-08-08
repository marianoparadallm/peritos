# Frontend for Scraping Backend

This is a lightweight web interface for triggering and viewing data from the scraping backend.

## Development

Open `index.html` in a browser. The frontend expects the backend API to provide:

- `POST /scrape` — inicia el scraping.
- `GET /data` — devuelve los datos scrapeados en formato JSON.

### Configuración de `API_BASE`

El URL del backend se determina en tiempo de ejecución siguiendo este orden:

1. Valor almacenado en `localStorage` bajo la clave `API_BASE`.
2. Variable global `window.API_BASE` (definida en `config.js` o inyectada directamente en `index.html`).
3. Valor por defecto `""` (relativo), útil cuando frontend y backend comparten origen.

Ejemplo en la consola del navegador para apuntar a un backend local:

```js
localStorage.setItem('API_BASE', 'http://localhost:8000');
```

También puedes editar `config.js` y establecer:

```js
window.API_BASE = 'http://localhost:8000';
```

## Deployment

Los archivos son estáticos y pueden alojarse fácilmente en **GitHub Pages** o **Supabase**:

### GitHub Pages

1. Copia la carpeta `frontend` a tu repositorio público.
2. En la configuración del repositorio, habilita GitHub Pages seleccionando la rama y el directorio `/frontend`.
3. Ajusta `config.js` para apuntar a tu backend (por ejemplo, `window.API_BASE = 'https://tu-backend.example.com';`).
4. Accede al sitio desde `https://<usuario>.github.io/<repositorio>/`.

### Supabase

1. Crea un bucket de almacenamiento público.
2. Sube los archivos de `frontend` al bucket.
3. Edita `config.js` con la URL de tu backend.
4. Sirve el contenido directamente desde Supabase o mediante una función edge.
