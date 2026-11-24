# WEBTTSA

Sitio web de Tandem Technology: una landing estática servida con Nginx y una API interna (`mail-api`) que envía por SMTP las consultas del formulario de contacto. Ambos corren con Docker Compose.

## Arquitectura

| Servicio   | Imagen / código                          | Puerto | Función |
|------------|------------------------------------------|--------|---------|
| `web`      | `Dockerfile` (Nginx 1.27) + `nginx.conf` | 8080 (publicado) | Sirve `index.html`, `styles.css`, `script.js` y `assets/`. Reenvía únicamente `POST /api/contact` a `mail-api`. |
| `mail-api` | `mail-api/Dockerfile` (Python 3.12, Flask + waitress) | 8000 (solo red interna) | Valida el formulario y lo envía por SMTP a `CONTACT_TO`. Expone `/healthz` para el healthcheck. |

Ambos contenedores corren sin root y con filesystem de solo lectura. `web` espera a que `mail-api` esté sano antes de arrancar.

## Requisitos

- Docker y Docker Compose
- Para los tests: Python 3.12 y Node.js

## Ejecutar en local

```bash
cp .env.example .env   # opcional; PORT=8080 por defecto
docker compose up -d --build
```

Abrí [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

```bash
docker compose down
```

Sin SMTP configurado el sitio funciona normalmente y el formulario responde `503` con un mensaje de error (no muestra una confirmación falsa).

## Variables de entorno

| Variable        | Descripción | Default |
|-----------------|-------------|---------|
| `PORT`          | Puerto publicado en el host para `web` | `8080` |
| `SMTP_HOST`     | Hostname o IP del servidor SMTP (sin protocolo ni puerto) | — (obligatorio para enviar) |
| `MAIL_FROM`     | Remitente autorizado por el proveedor (un único email) | — (obligatorio para enviar) |
| `SMTP_SECURITY` | `starttls` o `ssl`; no se permite transporte sin cifrar | `starttls` |
| `SMTP_PORT`     | Puerto SMTP; vacío usa 587 (`starttls`) o 465 (`ssl`) | vacío |
| `SMTP_TIMEOUT`  | Segundos por operación de red (1 a 60) | `15` |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Credenciales SMTP; van ambas o ninguna. No hay soporte OAuth | vacío |
| `CONTACT_TO`    | Buzón que recibe las consultas | `info@tandemtech.com.ar` |

Las variables SMTP se inyectan solo en `mail-api` a través de `docker-compose.yml`; ni Nginx ni el frontend las ven. No commitear `.env` ni credenciales.

## API de contacto

`POST /api/contact` con JSON. Campos: `nombre`, `empresa` y `email` obligatorios; `telefono`, `industria` y `mensaje` opcionales; `website` es un honeypot y debe venir vacío. El cuerpo se limita a 32 KiB.

Todas las respuestas son JSON con `ok` (booleano) y `message` (string):

| Código | Significado |
|--------|-------------|
| 200 | El servidor SMTP aceptó el mensaje |
| 400 | Datos inválidos |
| 413 | Cuerpo demasiado grande |
| 415 | El cuerpo no es JSON |
| 502 | Falló el envío SMTP (o Nginx no pudo conectar con la API) |
| 503 | Configuración SMTP incompleta o inválida |
| 504 | Nginx agotó la espera de la API |

Los POST no se reintentan: un error de red no garantiza que el correo no se haya enviado. Más detalle en [docs/despliegue-correo.md](docs/despliegue-correo.md).

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install -r mail-api/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Los tests simulan SMTP (no envían correos reales) y cubren la API, la coherencia entre el formulario HTML y el backend, el Compose y el handler del formulario en Node.

El workflow [`contact-smoke`](.github/workflows/contact-smoke.yml) corre en cada push a `main`: ejecuta los tests, construye ambas imágenes en una red aislada, valida `nginx -t` y comprueba el sitio servido y la respuesta `503` sin SMTP.

## Despliegue en Dokploy

1. Crear un servicio **Docker Compose** conectado a este repositorio, rama `main`, con el archivo `docker-compose.yml`. El push a `main` dispara el autodeploy.
2. Dominio → servicio `web`, **puerto del contenedor: `8080`**. `mail-api` queda interno y necesita salida de red hacia el servidor SMTP.
3. Configurar el DNS del dominio hacia el servidor Dokploy y habilitar SSL.
4. Cargar las variables SMTP en **Environment** del servicio Compose cuando se habilite el envío de correo.

No se requieren volúmenes ni base de datos.

## Caché de CSS y JS

`index.html` referencia `styles.css?v=…` y `script.js?v=…`, y Nginx los cachea 7 días. Al modificar alguno de esos archivos, cambiar su `?v=` para que los navegadores descarguen la versión nueva.

## Estructura

```
├── index.html              # Landing (una sola página)
├── styles.css              # Estilos, incluye tema claro/oscuro
├── script.js               # Animaciones, journey, tema y formulario
├── assets/                 # Logos, banderas, clientes, certificaciones, hero
├── Dockerfile              # Imagen Nginx del servicio web
├── nginx.conf              # Estáticos + proxy de /api/contact
├── docker-compose.yml      # Servicios web y mail-api
├── mail-api/
│   ├── app.py              # API Flask del formulario
│   ├── requirements.txt
│   └── Dockerfile
├── tests/                  # Tests de API, frontend y despliegue
├── docs/
│   └── despliegue-correo.md
├── .github/workflows/      # CI (contact-smoke)
├── .env.example
└── .dockerignore
```
