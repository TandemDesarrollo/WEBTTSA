# Correo del formulario en la fuente de producción

La fuente de partida es [TandemDesarrollo/WEBTTSA](https://github.com/TandemDesarrollo/WEBTTSA), commit `8ead9dfc515214b1f0abb5e855a4f941473a9c3c`. El servicio `web` conserva su Dockerfile Nginx, el puerto interno 8080, el diseño y las rutas estáticas. La API nueva se construye con `mail-api/Dockerfile` y escucha en el puerto 8000 de la red Compose, sin publicar un puerto en el host. Debe tener salida de red hacia el servidor SMTP; no convertir la red Compose en una red `internal` sin salida.

## Configuración posterior del correo

El código puede publicarse y quedar preparado con SMTP pendiente, sin obtener ahora datos del proveedor ni credenciales. Cuando falta configuración SMTP obligatoria, el formulario recibe HTTP 503 con `ok: false` y un mensaje público útil, conserva los datos y no muestra una confirmación de envío. El proveedor y el remitente autorizado se definirán al habilitar el correo, sin bloquear la publicación del código. La configuración SMTP remota está enmascarada o no fue verificada: los campos vacíos del ejemplo local no acreditan que falten variables en Dokploy. Una API key de Dokploy no sirve para autenticar SMTP.

- `SMTP_HOST`: necesario para enviar correo; hostname o IP del servidor indicado por el proveedor, sin protocolo, ruta ni puerto adjunto.
- `MAIL_FROM`: necesario para enviar correo; un único email que el proveedor autorice como remitente, sin nombre visible. No se toma desde el formulario ni se deduce del destinatario.
- `SMTP_SECURITY`: `starttls` de forma predeterminada o `ssl` para TLS directo. Siempre verifica el certificado y no permite transporte sin cifrar.
- `SMTP_PORT`: opcional; vacío o ausente elige 587 con `starttls` y 465 con `ssl`. Si el proveedor indica otro puerto, especificarlo; se admite de 1 a 65535.
- `SMTP_TIMEOUT`: segundos por operación de socket; predeterminado 15, rango permitido de 1 a 60. No limita toda la transacción ni la resolución DNS del servidor SMTP.
- `SMTP_USERNAME` y `SMTP_PASSWORD`: ambos para autenticación SMTP con usuario y contraseña, si el proveedor permite ese mecanismo. Ambos vacíos solo corresponden a un relay autorizado que no requiera login. No se implementa OAuth; si el proveedor lo exige, detener la habilitación del envío y definir la integración necesaria. Las credenciales se cargan directamente en el panel autorizado, no por chat ni en Git.
- `CONTACT_TO`: un único destinatario. Se conserva `info@tandemtech.com.ar`, ya publicado en el sitio, salvo cambio confirmado por su responsable. Compose utiliza ese valor predeterminado si la variable está vacía o ausente. El email del visitante solo se usa en `Reply-To`.

## Cómo llegan las variables al contenedor

El apartado `environment` de `mail-api` en `docker-compose.yml` enumera las ocho variables de correo. Compose interpola sus valores y los inyecta explícitamente al contenedor API; no se pasan al frontend ni a Nginx. El `.env` de interpolación, por sí solo, no inyectaría variables en un contenedor. El backend tampoco carga archivos `.env`.

`PORT` en el ejemplo controla únicamente el puerto publicado del servicio web. La API recibe `PORT=8000` en su propio servicio. Las imágenes copian únicamente los archivos necesarios y `.dockerignore` excluye los archivos `.env` privados. La API se ejecuta con UID/GID 10001, filesystem de solo lectura y `/tmp` temporal.

## Operación HTTP

Nginx publica únicamente `POST /api/contact` hacia la API. El contrato es JSON con `ok` booleano y `message` string en éxito y error; el backend conserva también `error` en los errores. HTTP 200 significa que SMTP aceptó el mensaje, no que ya llegó a la bandeja de entrada. La comprobación interna `/healthz` solo acredita que la API responde: no verifica proveedor, credenciales ni entrega, y nunca abre una conexión SMTP.

El servidor exige `nombre`, `empresa` y `email`; acepta `telefono`, `industria` y `mensaje` opcionales. Los límites respectivos son 120, 160, 254, 60, 80 y 5000 caracteres. `industria`, si se informa, debe coincidir con una opción del formulario. El campo auxiliar `website`, si aparece, debe estar vacío. Se rechazan controles, salvo saltos de línea y tabulaciones en el mensaje. El cuerpo completo se limita a 32 KiB tanto en Nginx como en Flask.

Los errores de validación retornan 400, los cuerpos demasiado grandes 413, el contenido que no sea JSON 415, la configuración SMTP incompleta o inválida 503 y los fallos SMTP 502. Los errores de método o ruta de la API también contienen JSON. Los mensajes públicos y los registros previstos no incluyen credenciales, direcciones del visitante, contenido de consultas ni respuestas del proveedor.

El proxy resuelve `mail-api` mediante el DNS de Docker y renueva la resolución para tolerar recreaciones del contenedor. Usa 5 segundos de conexión, 15 de escritura y 300 de espera de lectura. Son límites de inactividad del proxy, no un plazo total de entrega. La API puede realizar varias operaciones SMTP; por eso el timeout SMTP no equivale al timeout del proxy. Si Nginx no puede conectar o agota su espera, devuelve 502 o 504 con JSON y un mensaje de envío no confirmado. Un 413 generado por Nginx también devuelve JSON. Los errores JSON del backend se conservan.

No se reintentan POST automáticamente. Una desconexión o un timeout pueden ocurrir después de que el servidor haya aceptado el mensaje; un error no demuestra que no se envió. No reintentar sin verificar esa incertidumbre. Un fallo al cerrar la conexión después de una aceptación confirmada no convierte el envío en error.

## Pasos para el responsable del despliegue

1. Confirmar que se sigue trabajando sobre `Pagina Tandem`, servidor `SRV_185`, entorno `production`, repositorio `TandemDesarrollo/WEBTTSA`, rama `main`, Compose `./docker-compose.yml` y servicio público `web:8080`. La identidad proviene de la comprobación remota del coordinador; este cambio no realiza operaciones remotas.
2. Revisar el cambio completo, incluidas la adaptación del formulario, las pruebas y el tratamiento de la caché de `script.js` por el responsable del frontend. El push a `main` tiene autodeploy activo según la comprobación del coordinador; forma parte de la publicación del código y no se ejecuta desde esta corrección documental.
3. Publicar el Compose completo con SMTP pendiente de configuración es un resultado válido. El dominio sigue apuntando a `web` y al puerto interno 8080, y `mail-api` queda interno. No hace falta obtener proveedor, remitente ni credenciales para publicar esta versión preparada. No copiar valores de `.env.example` sobre una configuración real ni borrar variables existentes sin evidencia.
4. Comprobar rutas estáticas, estados de ambos servicios y `/healthz` interno. Para verificar la ruta pública sin enviar correo, un `POST /api/contact` con JSON `{}` debe responder 400 antes de cualquier conexión SMTP. La respuesta 503 y la conservación de datos ante configuración ausente se verifican con mocks; no enviar una consulta válida a producción si su configuración SMTP efectiva es desconocida.
5. Cuando se retome la habilitación del envío, definir proveedor y remitente autorizado, puerto/TLS, autenticación y destinatario, y cargar o conservar los valores necesarios en **Environment** del servicio Compose. Verificar su inyección en `mail-api` sin mostrar secretos. El healthcheck HTTP no acredita configuración SMTP ni entrega. Si ya existen variables reales, su presencia no demuestra que el proveedor permita enviar ni que el correo llegue.
6. La entrega real queda fuera del cierre de esta corrección. Con SMTP pendiente, la interfaz debe mantener la respuesta honesta de error y los datos del visitante, sin falsa confirmación. No se exige una prueba de email real para considerar terminado el código preparado.

Esta implementación no hace commits, push, cambios en Dokploy, despliegues ni envíos reales. Las verificaciones del backend deben sustituir `smtplib.SMTP` y `smtplib.SMTP_SSL` por mocks y bloquear conexiones de red accidentales.

## Comprobación de contenedores pendiente

La validación local confirmó sintaxis Python, configuración Compose y comportamiento del backend con SMTP simulado. No se pudo ejecutar `nginx -t` ni construir o iniciar los contenedores porque el socket local de Docker deniega acceso. La validación runtime de contenedores sigue pendiente; esta limitación documentada no impide cerrar el código como preparado con SMTP pendiente. No se intentó escalar permisos ni usar un servidor remoto como sustituto.

Cuando haya Docker disponible en un entorno local o de CI, estas comprobaciones adicionales pueden ejecutarse con variables sintéticas y sin credenciales reales:

```sh
docker compose config --quiet
docker compose build web mail-api
docker compose run --rm --no-deps web nginx -t
```

Estos comandos validan la configuración y las imágenes; no acreditan la entrega de correo. La comprobación runtime pendiente incluye los JSON de error generados por Nginx y las rutas estáticas con el Compose completo, manteniendo SMTP simulado o bloqueado. Publicar el código preparado no requiere activar SMTP ni ejecutar pruebas reales de envío.
