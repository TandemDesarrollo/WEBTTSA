# WEBTTSA

Sitio web estático de Tandem Technology, servido con Nginx en Docker.

## Requisitos

- Docker y Docker Compose

## Ejecutar en local

```bash
cp .env.example .env   # opcional; PORT=8080 por defecto
docker compose up -d --build
```

Abrí [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

```bash
docker compose down
```

## Variables de entorno

| Variable | Descripción              | Default |
|----------|--------------------------|---------|
| `PORT`   | Puerto publicado en host | `8080`  |

No hay base de datos ni secretos obligatorios.

## Despliegue en Dokploy

1. Crear un servicio **Docker Compose** (o Application con build **Dockerfile**).
2. Conectar este repositorio.
3. Compose file: `docker-compose.yml`.
4. Dominio → servicio `web`, **puerto del contenedor: `8080`**.
5. Configurar DNS del dominio hacia el servidor Dokploy.
6. Habilitar SSL en Dokploy.

No se requieren volúmenes ni servicios adicionales.

## Estructura

```
├── index.html
├── styles.css
├── script.js
├── assets/
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── .env.example
└── .dockerignore
```
