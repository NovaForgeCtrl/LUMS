
# Guía de instalación de LUMS

## Servidor de gestión de actualizaciones de Linux

**Proyecto:** LUMS
**Eslogan:** Gestión de actualizaciones de Linux sin el ruido.
**Repositorio:** `NovaForgeCtrl/LUMS`

---

## Primeros pasos: Comprender la instalación antes de comenzar

Esta guía cubre una instalación completa del servidor, incluidos procedimientos avanzados de mantenimiento y verificación. **No** es un único script para ejecutar sin revisión: el nombre del servidor, el certificado TLS, el archivo secreto, el destino de copia de seguridad, la red y la base de datos varían entre instalaciones.

### ¿Qué se instala?

* **Servidor LUMS:** la interfaz web y la API, ejecutándose en un contenedor Docker.
* **Nginx:** acepta conexiones HTTPS externas y las reenvía localmente al contenedor.
* **Volumen de datos:** contiene la base de datos SQLite. Este volumen debe sobrevivir a las actualizaciones y nunca debe eliminarse durante un reemplazo normal de contenedor.
* **Archivo secreto:** protege las sesiones de la aplicación, entre otras cosas. Nunca lo coloque en el repositorio Git, en una imagen Docker o en un mensaje de chat.
* **LUMS Agent y Watcher:** se instalan por separado en clientes Linux gestionados. Un servidor que funcione por sí solo no actualiza ningún cliente.

| Término | Significado |
| --- | --- |
| Terminal / shell | Una ventana de texto donde se introducen comandos de Linux. |
| `sudo` | Ejecuta el comando que sigue con derechos de administrador. Linux puede pedir su contraseña. |
| Host | El equipo Linux que ejecuta Docker y el servidor LUMS. |
| Contenedor | Un proceso aislado que ejecuta la aplicación web LUMS. |
| Imagen | Una plantilla preparada que Docker usa para iniciar un contenedor. |
| Volumen | Almacenamiento persistente de Docker que permanece cuando se reemplaza un contenedor. |
| Marcador de posición | Texto como `LUMS-SERVER` que debe reemplazarse con su valor real. |

### Ejecutar solo las pruebas (esto no instala un servidor)

Estos pasos son adecuados para Debian 13 para obtener el código fuente y ejecutar las pruebas localmente. **No** crean un servidor de producción accesible a través de la red y no instalan un agente en otro equipo. `sudo` solo es necesario para instalar paquetes de Debian.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q
```

`apt update` actualiza las listas de paquetes; no actualiza todo el software instalado. El entorno virtual de Python `.venv-test` mantiene las dependencias de prueba separadas del resto del sistema. Una ejecución de prueba exitosa termina con el código `0`; el número de pruebas puede cambiar a medida que el proyecto crece. Si la creación del entorno falla, compruebe que `python3-venv` esté instalado. Si una prueba falla, guarde el error completo y lea la [guía de solución de problemas](<Solución de problemas.md>); no elimine datos de producción.

Para una instalación real, continúe con las secciones numeradas y lea primero las instrucciones de seguridad y copia de seguridad. Si LUMS ya está en ejecución, use el procedimiento de actualización en [`administration.md`](<Administración y copias de seguridad.md>), no el procedimiento de primera instalación.

---

# 1. Descripción general

LUMS es una plataforma centralizada de gestión de actualizaciones de Linux para la distribución controlada de actualizaciones, el reporte de clientes, la gestión de paquetes, la ejecución de trabajos de actualización, la validación de resultados y la administración auditable.

La arquitectura actual separa el servidor de gestión de los clientes Linux gestionados.

El servidor proporciona:

* Administración basada en web
* Gestión de clientes
* Autenticación de clientes
* Inventario de paquetes
* Reporte de actualizaciones disponibles
* Búsqueda de paquetes
* Instalación y eliminación de paquetes
* Gestión de trabajos de actualización
* Validación de resultados de trabajos
* Historial de actualizaciones
* Control de acceso basado en roles
* Registro de auditoría
* Estado persistente basado en SQLite

Los clientes Linux proporcionan:

* Información del sistema
* Inventario de paquetes instalados
* Detección de actualizaciones disponibles
* Operaciones de paquetes
* Ejecución de trabajos de actualización
* Detección de estado inactivo
* Puntos de control y recuperación de trabajos
* Detección de reinicio
* Reporte de resultados

La implementación actual admite:

```text
Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman
```

---

# 2. Arquitectura

La arquitectura de producción es:

```text
                         LUMS Server
                              │
                              │ HTTPS :443
                              ▼
                       ┌──────────────┐
                       │    Nginx     │
                       │  TLS / Proxy │
                       └──────┬───────┘
                              │
                              │ HTTP
                              ▼
                       127.0.0.1:5050
                              │
                              ▼
                    ┌───────────────────┐
                    │   Docker: lums    │
                    │                   │
                    │   Gunicorn        │
                    │   Flask :5000     │
                    │   SQLite          │
                    └─────────┬─────────┘
                              │
                              ▼
                         lums-data
                              │
                              ▼
                   /var/lib/lums/lums.db


        Linux Client
              │
              │ HTTPS + Bearer Token
              ▼
         LUMS API
              │
              ├── Report
              ├── Package Search
              ├── Job Retrieval
              └── Job Result
```

La aplicación LUMS **no está diseñada para exponerse directamente a la red**.

El contenedor de la aplicación está vinculado a:

```text
127.0.0.1:5050 → container:5000
```

Nginx es el punto de entrada HTTPS externo.

El puerto `5000` no se publica directamente.

El puerto `5050` debe permanecer solo en localhost.

---

# 3. Componentes de la aplicación

Una instalación completa de LUMS consta de varios componentes.

## 3.1 Servidor LUMS

El servidor contiene:

```text
Flask
Gunicorn
SQLite
Web UI
REST API
Authentication
RBAC
Audit logging
Job management
Package management
```

La aplicación se ejecuta dentro del contenedor Docker:

```text
lums
```

La base de datos persistente se almacena fuera del sistema de archivos de aplicación escribible del contenedor:

```text
lums-data:/var/lib/lums/lums.db
```

---

## 3.2 Nginx

Nginx proporciona:

```text
HTTPS termination
TLS certificate handling
HTTP → HTTPS redirect
Reverse proxy
External network entry point
```

La ruta de solicitud prevista es:

```text
Browser
   │
   │ HTTPS
   ▼
Nginx
   │
   │ localhost HTTP
   ▼
127.0.0.1:5050
   │
   ▼
LUMS
```

La aplicación Flask/Gunicorn no debe exponerse directamente a la LAN.

---

## 3.3 Agente Linux

El agente LUMS se ejecuta en cada cliente Linux gestionado.

La versión actual del agente es:

```text
1.7.0
```

El agente es responsable de:

```text
System information
Installed packages
Available updates
Client reporting
Job retrieval
Job claiming
Package operations
Result reporting
Reboot detection
```

El agente se comunica con el servidor LUMS mediante HTTPS y un token Bearer específico del cliente.

---

## 3.4 Execution Watcher

El watcher de ejecución es responsable de la ejecución controlada de trabajos de actualización.

La versión actual del watcher es:

```text
1.2.1
```

El watcher maneja:

```text
Pending-job detection
Idle-state checks
Atomic job claiming
Update execution
Checkpoint handling
Interrupted-job recovery
Result processing
```

El watcher está intencionalmente separado del reporte ordinario de clientes.

---

# 4. Modelo de seguridad

La instalación debe preservar la línea base de seguridad de LUMS.

El servidor de producción utiliza:

```text
HTTPS
Bearer-token client authentication
Role-based web authorization
CSRF protection
Audit logging
Read-only container root filesystem
Dropped Linux capabilities
no-new-privileges
Non-root application user
Localhost-only application port
Persistent Docker volume
Read-only secret mount
```

El contenedor Docker se ejecuta como el usuario no privilegiado:

```text
lums
```

con UID:

```text
10001
```

El contenedor no debe ejecutarse en modo privilegiado.

El sistema de archivos raíz debe permanecer de solo lectura.

La aplicación no debe requerir acceso de escritura a su directorio de aplicación.

Los datos persistentes de la aplicación se almacenan a través del volumen Docker dedicado.

---

# 5. Modelo RBAC actual

LUMS proporciona actualmente tres roles web:

```text
administrator
operator
viewer
```

## Administrator

Los administradores pueden realizar operaciones administrativas, incluidas:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
Create and disable clients
Rotate client tokens
Manage users
Manage roles
```

---

## Operator

Los operadores pueden realizar gestión operativa:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Los operadores no tienen acceso a:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

---

## Viewer

Los viewers tienen acceso intencionalmente restringido.

Un viewer puede acceder a:

```text
Clients
Installed software
```

Las siguientes áreas de gestión están ocultas de la interfaz del viewer y protegidas en el servidor:

```text
Available updates
Update Jobs
Update History
Package Management
System Maintenance
```

Por lo tanto, ocultar la interfaz de usuario no es la frontera de seguridad.

La autorización del lado del servidor sigue siendo obligatoria.

---

# 6. Requisitos de instalación

## 6.1 Servidor LUMS

El despliegue actual requiere un host Linux con:

```text
Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage
```

El servidor debe tener suficiente almacenamiento para:

```text
Docker images
SQLite database
Application data
Logs
Backups
```

La aplicación LUMS en sí se ejecuta dentro de Docker.

---

## 6.2 Clientes Linux

Los clientes Linux gestionados requieren:

```text
Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate
```

Familias de gestión de paquetes compatibles:

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

El cliente debe poder alcanzar el punto de conexión HTTPS de LUMS.

---

# 7. Estructura de directorios recomendada

La ubicación recomendada del repositorio del lado del servidor es:

```text
/opt/lums-public/
```

El repositorio contiene el código fuente de la aplicación, el código fuente del agente y las pruebas.

Una instalación típica utiliza:

```text
/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt
```

La configuración del lado del host se mantiene fuera del repositorio:

```text
/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key
```

Los datos persistentes de la aplicación se almacenan en:

```text
lums-data:/var/lib/lums
```

La base de datos SQLite es:

```text
/var/lib/lums/lums.db
```

La base de datos nunca debe almacenarse dentro del árbol de trabajo de Git.

Los secretos y el material TLS privado también deben permanecer fuera del repositorio.

---

# 8. Preparación del repositorio

Clone el repositorio en el directorio de instalación previsto:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Entre en el repositorio:

```bash
cd /opt/lums-public
```

Compruebe el árbol de trabajo:

```bash
git status
```

Inspeccione la revisión actual:

```bash
git log -1 --oneline --decorate
```

Para despliegues controlados, debe registrarse el commit exacto utilizado para la instalación.

No construya imágenes de producción desde un árbol de trabajo desconocido o no verificado.

---

# 9. Verificación de seguridad del repositorio

Antes de construir la imagen de producción, verifique que no se hayan colocado archivos sensibles en el repositorio.

Revise el árbol de trabajo:

```bash
git status --short
```

Revise los archivos ignorados cuando corresponda:

```bash
git status --ignored --short
```

El repositorio no debe contener:

```text
Production database files
Private TLS keys
Application secrets
Client tokens
Credential dumps
Backup databases
Runtime logs
Temporary backup files
```

El proyecto utiliza reglas de ignorancia del repositorio para evitar que los artefactos de copia de seguridad comunes se rastreen accidentalmente.

Antes de confirmar cambios, inspeccione cuidadosamente la lista de archivos preparados.

---

# 10. Preparar los directorios de configuración del host

Cree los directorios requeridos del lado del host:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

El directorio de secretos contiene el secreto de la aplicación.

El directorio TLS contiene el certificado TLS y la clave privada.

Proteger estos directorios reduce el riesgo de divulgación accidental.

Verifique:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls
```

---

# 11. Crear el secreto de la aplicación

El secreto de la aplicación LUMS se almacena en el host en lugar de incrustarse directamente en la imagen Docker.

La ruta del secreto de producción es:

```text
/etc/lums/secrets/lums_secret
```

Genere un secreto aleatorio:

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Proteja el archivo resultante:

```bash
sudo chmod 600 \
    /etc/lums/secrets/lums_secret
```

Verifique los permisos sin mostrar el secreto:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

Esperado:

```text
600
```

El secreto nunca debe ser:

```text
Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation
```

El contenedor recibe el secreto a través de un montaje bind de solo lectura.

---

# 12. Preparar el material TLS

LUMS utiliza HTTPS para el acceso externo.

Las ubicaciones recomendadas del lado del host son:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Instale el certificado y la clave privada apropiados antes de configurar Nginx.

Proteja la clave privada:

```bash
sudo chmod 600 \
    /etc/lums/tls/lums.key
```

El certificado puede ser legible por el servicio Nginx:

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

Verifique:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

La clave privada nunca debe confirmarse en Git ni incluirse en la imagen Docker.

---

# 13. Principio de instalación

La instalación debe realizarse en etapas controladas:

```text
Repository
    ↓
Host configuration
    ↓
Application secret
    ↓
TLS material
    ↓
Docker image
    ↓
Persistent volume
    ↓
Hardened container
    ↓
Nginx / HTTPS
    ↓
Administrator
    ↓
Server validation
    ↓
Linux clients
```

No conecte clientes de producción antes de que el servidor haya superado sus propias comprobaciones de validación.

Las siguientes secciones continúan con la construcción de la imagen Docker y el despliegue de producción endurecido.

# 14. Construir la imagen Docker de LUMS

Antes de construir la imagen de producción, asegúrese de que el repositorio esté en el estado previsto.

Entre en el repositorio:

```bash
cd /opt/lums-public
```

Ejecute la suite de pruebas antes de crear una imagen de producción:

```bash
./.venv-test/bin/pytest -q
```

Se espera que el número de pruebas crezca a medida que evoluciona el proyecto.

El requisito importante es que la suite de pruebas relevante se complete con éxito antes del despliegue.

Construya la imagen Docker:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Verifique que la imagen existe:

```bash
sudo docker image ls lums
```

Inspeccione la imagen:

```bash
sudo docker image inspect lums:latest
```

La imagen de producción se basa en una imagen base Python 3.13 slim fijada.

El Dockerfile también utiliza dependencias de producción fijadas cuando es necesario.

---

# 15. Revisar la construcción de Docker

Antes de desplegar la imagen, revise la salida de la construcción en busca de errores o advertencias inesperados.

Compruebe la imagen resultante:

```bash
sudo docker inspect \
    lums:latest
```

Verifique el usuario de la aplicación configurado:

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

La aplicación está diseñada para ejecutarse como:

```text
lums
```

La aplicación no debe requerir privilegios de root durante la ejecución normal.

Revise el Dockerfile al cambiar el proceso de construcción:

```bash
sed -n '1,240p' Dockerfile
```

No agregue secretos, certificados ni bases de datos de producción al contexto de construcción de Docker.

El repositorio contiene un archivo `.dockerignore` para reducir el riesgo de incluir accidentalmente artefactos de tiempo de ejecución en la imagen.

---

# 16. Crear el volumen Docker persistente

Cree el volumen de datos persistente de LUMS:

```bash
sudo docker volume create lums-data
```

Verifique:

```bash
sudo docker volume inspect lums-data
```

El volumen almacena datos persistentes de la aplicación:

```text
lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db
```

El sistema de archivos del contenedor en sí no debe tratarse como almacenamiento persistente de la aplicación.

Por lo tanto, la base de datos sobrevive al reemplazo del contenedor siempre que se preserve el volumen `lums-data`.

> [!IMPORTANT]
> Nunca elimine `lums-data` durante una actualización normal de la aplicación.

Eliminar el volumen elimina la base de datos SQLite almacenada en su interior.

---

# 17. Verificar el volumen persistente

Antes de iniciar LUMS, confirme que el volumen existe:

```bash
sudo docker volume inspect \
    lums-data
```

El volumen también se puede verificar a través de Docker:

```bash
sudo docker volume ls | grep lums-data
```

Un volumen recién creado normalmente aún no contendrá una base de datos.

La base de datos es inicializada por la aplicación LUMS durante el despliegue.

---

# 18. Configuración del contenedor de producción

El contenedor de producción utiliza varios controles de seguridad simultáneamente.

La línea base de tiempo de ejecución esperada es:

```text
Non-root user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
No privileged mode
Localhost-only application binding
Read-only application-secret mount
Persistent writable data volume
Dedicated /tmp tmpfs
```

El puerto de la aplicación se publica solo en localhost:

```text
127.0.0.1:5050 → container:5000
```

El punto de conexión HTTPS externo es proporcionado por Nginx.

---

# 19. Iniciar el contenedor LUMS endurecido

Antes de iniciar un nuevo contenedor de producción, asegúrese de que no haya otro contenedor llamado `lums` ya en ejecución:

```bash
sudo docker ps \
    --filter name=lums
```

Si se está reemplazando un despliegue existente, preserve el contenedor existente hasta que la nueva imagen haya sido validada.

Inicie el contenedor endurecido:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:latest
```

El secreto de la aplicación se monta como de solo lectura.

La base de datos SQLite se almacena en el volumen persistente.

El sistema de archivos raíz es de solo lectura.

Todas las capacidades de Linux se eliminan.

La opción de seguridad `no-new-privileges` evita que los procesos dentro del contenedor obtengan privilegios adicionales.

---

# 20. Verificar el estado del contenedor

Compruebe el contenedor en ejecución:

```bash
sudo docker ps \
    --filter name=lums
```

Estado esperado:

```text
Up ...
```

Verifique el estado del contenedor directamente:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Esperado:

```text
running
```

Inspeccione los registros recientes:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Los errores de inicio de la aplicación deben resolverse antes de continuar con la instalación.

---

# 21. Verificar la seguridad del contenedor

Inspeccione la configuración de seguridad efectiva en tiempo de ejecución:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

La línea base esperada es:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

El formato exacto de la salida de Docker puede variar.

Lo que importa es la configuración efectiva.

---

# 22. Verificar el puerto de la aplicación

Compruebe el puerto Docker publicado:

```bash
sudo docker port lums
```

Esperado:

```text
5000/tcp -> 127.0.0.1:5050
```

Lo siguiente **no** es aceptable para la aplicación de producción:

```text
0.0.0.0:5050
```

o:

```text
0.0.0.0:5000
```

La aplicación es accesible intencionalmente solo a través de la ruta local del proxy inverso.

Compruebe los sockets en escucha:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Solo debe estar presente la vinculación de la aplicación a localhost.

---

# 23. Verificar el montaje del secreto

Confirme que el secreto está montado:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

El secreto de la aplicación debería aparecer similar a:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

La salida exacta puede contener información de montaje adicional.

La propiedad importante es:

```text
RW=false
```

Nunca imprima el contenido del secreto.

Una prueba directa de legibilidad es suficiente:

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Esperado:

```text
secret mount: OK
```

---

# 24. Verificar el montaje del volumen persistente

Inspeccione los montajes del contenedor:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'
```

El volumen de datos de LUMS debe montarse en:

```text
/var/lib/lums
```

y debe ser escribible:

```text
RW=true
```

La relación esperada es:

```text
lums-data
    ↓
/var/lib/lums
```

El sistema de archivos raíz permanece de solo lectura mientras el volumen de datos dedicado proporciona el acceso de escritura persistente requerido.

---

# 25. Verificar el sistema de archivos raíz de solo lectura

El sistema de archivos raíz de la aplicación debe ser de solo lectura.

El tiempo de ejecución del contenedor debería informar:

```text
ReadonlyRootfs=true
```

Se puede realizar una prueba de escritura controlada dentro del contenedor.

Por ejemplo:

```bash
sudo docker exec lums \
    sh -c 'touch /app/.write-test'
```

El comando debería fallar porque `/app` es parte del sistema de archivos de solo lectura del contenedor.

No deshabilite el sistema de archivos raíz de solo lectura solo porque un componente de la aplicación intenta escribir fuera de sus ubicaciones escribibles designadas.

Si la aplicación requiere datos persistentes, use el volumen o el sistema de archivos de tiempo de ejecución apropiado en su lugar.

---

# 26. Verificar el sistema de archivos temporal escribible

El contenedor proporciona un tmpfs `/tmp` dedicado.

Verifique:

```bash
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'
```

Esperado:

```text
tmpfs: OK
```

El sistema de archivos temporal está configurado con:

```text
noexec
nosuid
```

y un límite de tamaño.

Esto proporciona almacenamiento temporal escribible sin hacer escribible el sistema de archivos raíz del contenedor.

---

# 27. Verificar el directorio de datos de la aplicación

La aplicación LUMS requiere acceso de escritura a su directorio de datos persistente.

Prueba:

```bash
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'
```

Esperado:

```text
data volume: OK
```

Esto confirma que el volumen escribible dedicado está disponible mientras el resto del contenedor permanece de solo lectura.

---

# 28. Verificar el usuario de la aplicación

Confirme el usuario efectivo en tiempo de ejecución:

```bash
sudo docker exec lums \
    id
```

El proceso debería ejecutarse como el usuario LUMS no privilegiado.

La identidad esperada incluye:

```text
uid=10001(lums)
```

La información exacta del grupo puede variar según la configuración de la imagen.

El contenedor no debe ejecutarse como:

```text
root
```

durante el funcionamiento normal.

---

# 29. Inicialización de la base de datos

Después de que el contenedor se inicie, compruebe si la base de datos existe:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Si la aplicación se ha inicializado correctamente, la base de datos debería estar presente.

La base de datos se encuentra en:

```text
/var/lib/lums/lums.db
```

dentro del contenedor y persiste físicamente a través de:

```text
lums-data
```

La base de datos no debe copiarse en:

```text
/opt/lums-public
```

ni confirmarse en Git.

---

# 30. Verificar la configuración de tiempo de ejecución de SQLite

La línea base de producción actual de LUMS utiliza:

```text
journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON
```

La aplicación habilita explícitamente la aplicación de claves foráneas para las conexiones a la base de datos.

La base de datos utiliza el modo WAL para el funcionamiento normal de producción.

La configuración de tiempo de ejecución se puede inspeccionar desde la base de datos de la aplicación.

Por ejemplo:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for pragma in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    print(f"{pragma}={db.execute(f'PRAGMA {pragma}').fetchone()[0]}")

db.close()
PY
```

Los valores esperados son equivalentes a:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

La aplicación habilita las claves foráneas explícitamente.

---

# 31. Verificar la integridad de la base de datos

Ejecute una comprobación de integridad de SQLite:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY
```

Esperado:

```text
ok
```

No continúe con el despliegue si la comprobación de integridad informa corrupción de la base de datos.

---

# 32. Verificar las migraciones de la base de datos

LUMS utiliza migraciones de aplicación para los cambios de esquema de la base de datos.

Inspeccione los archivos relacionados con las migraciones:

```bash
ls -lh \
    server/*migration*.py
```

La aplicación realiza las migraciones requeridas durante el inicio/despliegue según la implementación actual.

Después del inicio, inspeccione los registros de la aplicación:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Los errores de migración deben investigarse antes de crear usuarios o conectar clientes.

No modifique manualmente el esquema SQLite de producción a menos que la documentación del proyecto lo requiera explícitamente.

---

# 33. Validación local de la aplicación

Antes de configurar Nginx, confirme que la aplicación responde localmente.

La aplicación Docker está vinculada a:

```text
127.0.0.1:5050
```

Se puede probar una solicitud local con:

```bash
curl -I \
    http://127.0.0.1:5050/
```

La respuesta HTTP exacta depende de la ruta actual de la aplicación y del estado de autenticación.

El requisito importante es que la solicitud llegue a la aplicación LUMS en ejecución.

Si la conexión falla, inspeccione:

```bash
sudo docker ps \
    --filter name=lums
```

y:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

No exponga el puerto `5050` externamente como solución alternativa de solución de problemas.

---

# 34. Punto de control inicial del servidor

En esta etapa, el servidor debe cumplir:

```text
[ ] Repository cloned
[ ] Working tree reviewed
[ ] Production tests completed
[ ] Docker image built
[ ] Persistent lums-data volume exists
[ ] Hardened container running
[ ] Container runs as lums
[ ] Root filesystem is read-only
[ ] All capabilities are dropped
[ ] no-new-privileges is enabled
[ ] Privileged mode is disabled
[ ] Secret is mounted read-only
[ ] Persistent data volume is mounted
[ ] Port 5050 is localhost-only
[ ] SQLite database exists
[ ] SQLite integrity check succeeds
[ ] Foreign keys are enabled
[ ] Local application endpoint responds
```

No conecte todavía clientes de producción.

La siguiente etapa configura Nginx, HTTPS y el punto de conexión externo de LUMS.

# 35. Configurar Nginx

Nginx proporciona el punto de entrada HTTPS externo para LUMS.

La aplicación en sí permanece vinculada a:

```text
127.0.0.1:5050
```

La ruta de solicitud prevista es:

```text
Client
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
LUMS container :5000
```

Cree la configuración del sitio de Nginx:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name LUMS-SERVER;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name LUMS-SERVER;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    location / {
        proxy_pass http://127.0.0.1:5050;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Reemplace:

```text
LUMS-SERVER
```

con el nombre de host o la dirección utilizados por la instalación.

No use el marcador de posición literal en una configuración de producción.

---

# 36. Habilitar la configuración de Nginx de LUMS

Cree el enlace del sitio habilitado:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Si no se requiere el sitio predeterminado de Nginx, elimínelo:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/default
```

No elimine otras configuraciones de Nginx pertenecientes a aplicaciones no relacionadas.

---

# 37. Validar la configuración de Nginx

Pruebe siempre la configuración antes de recargar Nginx:

```bash
sudo nginx -t
```

Esperado:

```text
syntax is ok
test is successful
```

Solo después de una prueba de configuración exitosa se debe recargar Nginx:

```bash
sudo systemctl reload nginx
```

Verifique el servicio:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Nginx debe estar en ejecución antes de continuar con la validación de HTTPS.

---

# 38. Verificar los archivos de certificado TLS

Confirme que los archivos de certificado configurados existen:

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Verifique los permisos:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

La clave privada normalmente debe ser:

```text
600
```

El certificado normalmente puede ser:

```text
644
```

Nunca imprima el contenido de la clave privada.

---

# 39. Verificar el punto de conexión HTTPS

Pruebe HTTPS localmente:

```bash
curl -I \
    https://LUMS-SERVER/
```

Reemplace `LUMS-SERVER` con el nombre de host cubierto por el certificado TLS del servidor. No use `-k` para la verificación rutinaria; omite la validación del certificado.

Cuando el sistema confía en el certificado, use la verificación del certificado:

```bash
curl -I \
    https://LUMS-SERVER/
```

Una respuesta exitosa confirma que la solicitud llega al punto de conexión HTTPS de Nginx.

El estado HTTP exacto depende de la ruta solicitada y del estado de autenticación.

El requisito importante es que la conexión TLS se realice con éxito y la solicitud llegue a LUMS.

---

# 40. Verificar la redirección HTTP a HTTPS

El listener HTTP debe redirigir a los clientes a HTTPS.

Prueba:

```bash
curl -I \
    http://LUMS-SERVER/
```

Comportamiento esperado:

```text
HTTP/1.1 301 ...
Location: https://...
```

La aplicación LUMS no debe operarse a través de una conexión HTTP sin cifrar.

No configure permanentemente los clientes con la verificación de certificados deshabilitada solo porque el certificado inicial no es de confianza.

Corrija la configuración de confianza en su lugar.

---

# 41. Verificar la ruta de red externa

Inspeccione los sockets en escucha:

```bash
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

La arquitectura prevista es:

```text
80
 │
 └── HTTP redirect
        │
        ▼
443
 │
 └── Nginx
        │
        ▼
127.0.0.1:5050
        │
        ▼
Docker :5000
```

El puerto `5050` no debe exponerse a la LAN.

El puerto `5000` no debe exponerse directamente.

El puerto de la aplicación Docker es un punto de conexión interno del proxy inverso.

---

# 42. Verificar las cabeceras de seguridad

Inspeccione las cabeceras de respuesta HTTPS:

```bash
curl -I \
    https://LUMS-SERVER/
```

Revise las cabeceras devueltas en lugar de suponer que la configuración de seguridad está activa.

Las cabeceras de seguridad relevantes pueden incluir:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

Las cabeceras exactas dependen de la aplicación LUMS actual y de la configuración de Nginx.

Si falta una cabecera requerida, inspeccione la configuración efectiva de Nginx:

```bash
sudo nginx -T
```

y la configuración de la aplicación:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

No agregue cabeceras de seguridad a ciegas sin comprobar qué capa ya es responsable de ellas.

---

# 43. Verificar el manejo del host

El despliegue de producción no debe exponer la aplicación a través de un sitio Nginx predeterminado no intencionado.

Revise la configuración activa:

```bash
sudo nginx -T
```

Compruebe los sitios habilitados:

```bash
ls -la \
    /etc/nginx/sites-enabled/
```

El host virtual LUMS previsto debe estar presente.

El sitio predeterminado no debe servir inesperadamente la aplicación LUMS.

Cuando utilice una dirección IP como punto de conexión de LUMS, asegúrese de que el `server_name` configurado y el certificado coincidan con el modelo de despliegue real.

---

# 44. Verificar nuevamente la exposición de Docker

Después de configurar Nginx, confirme que la aplicación permanece solo en localhost:

```bash
sudo docker port lums
```

Esperado:

```text
5000/tcp -> 127.0.0.1:5050
```

El proxy inverso no requiere cambiar la vinculación de Docker.

No la cambie a:

```text
0.0.0.0:5050
```

solo porque Nginx está escuchando en la red.

Nginx y Docker tienen fronteras de exposición deliberadamente separadas.

---

# 45. Crear el administrador inicial

El administrador inicial debe crearse utilizando el mecanismo de inicialización de administrador del repositorio actual.

Antes de ejecutar un comando de inicialización, inspeccione la implementación disponible del repositorio:

```bash
cd /opt/lums-public
```

Revise los archivos de inicialización relacionados con la seguridad:

```bash
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
```

Luego inspeccione la implementación actual de migración/inicialización antes de ejecutarla.

Por ejemplo:

```bash
sed -n '1,260p' \
    server/security_migration.py
```

Utilice el procedimiento de inicialización proporcionado por la revisión exacta del repositorio que se está desplegando.

> [!IMPORTANT]
> No copie una contraseña de administrador en el historial del shell ni en la documentación.

El administrador inicial debe recibir:

```text
role = administrator
```

La cuenta de administrador es necesaria para el primer inicio de sesión web y la posterior administración de clientes.

---

# 46. Verificar la cuenta de administrador

Después de la inicialización del administrador, verifique la cuenta sin exponer material de autenticación.

Se puede realizar una inspección de la base de datos desde el contenedor:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

rows = db.execute(
    """
    SELECT id, username, enabled, role
    FROM users
    ORDER BY id
    """
).fetchall()

for row in rows:
    print(row)

db.close()
PY
```

Las propiedades esperadas del administrador incluyen:

```text
enabled = 1
role = administrator
```

No imprima:

```text
password hashes
session data
client tokens
application secrets
```

---

# 47. Contraseña del administrador

Use una contraseña de administrador única.

La contraseña no debe reutilizarse de:

```text
other servers
Linux accounts
GitHub accounts
email accounts
network devices
other LUMS installations
```

La aplicación LUMS almacena las contraseñas utilizando el mecanismo de hash de contraseñas configurado.

No intente reemplazar manualmente el hash de la contraseña de la aplicación en SQLite.

Si se debe cambiar la contraseña del administrador, use el mecanismo de aplicación compatible.

---

# 48. Primer inicio de sesión web

Abra el punto de conexión HTTPS de LUMS:

```text
https://LUMS-SERVER/
```

Inicie sesión con la cuenta de administrador.

Después de la autenticación, el administrador debe tener acceso a la interfaz administrativa.

La interfaz de administrador debe proporcionar acceso a las áreas permitidas por la implementación RBAC actual.

Como mínimo, el administrador debe poder acceder a:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

---

# 49. Verificar el RBAC del administrador

Después del inicio de sesión, verifique que las funciones administrativas están disponibles.

El administrador debe poder acceder a la gestión de usuarios.

El administrador también debe poder realizar las operaciones de gestión de clientes permitidas por la implementación actual.

La autorización del lado del servidor sigue siendo la frontera de seguridad.

La interfaz del navegador no es de confianza solo porque un elemento sea visible u oculto.

---

# 50. Crear un operador

Después de que la cuenta de administrador haya sido verificada, cree una cuenta de operador a través de la interfaz de gestión de usuarios de LUMS.

El rol de operador está destinado a la gestión operativa de actualizaciones.

Un operador puede acceder a:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Un operador no debe poder realizar funciones exclusivas del administrador como:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Verifique los permisos utilizando la interfaz de la aplicación y, cuando corresponda, el comportamiento de autorización de la API.

---

# 51. Crear un viewer

Se puede crear una cuenta de viewer cuando se requiere acceso de solo lectura.

El rol de viewer está intencionalmente restringido.

Un viewer puede acceder a:

```text
Clients
Installed software
```

Las siguientes áreas no deben estar disponibles para un viewer:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Estas restricciones se aplican en el servidor.

La interfaz puede además ocultar funciones no disponibles.

---

# 52. Verificar el aislamiento del viewer

Inicie sesión con una cuenta de viewer y verifique la interfaz visible.

El viewer no debe recibir controles de gestión.

El viewer no debe poder eludir la interfaz de usuario e invocar directamente puntos de conexión protegidos.

Se debe devolver un fallo de autorización para las operaciones protegidas.

El principio esperado es:

```text
UI restriction
     +
server-side authorization
     =
RBAC boundary
```

Nunca dependa de JavaScript o elementos HTML ocultos como único mecanismo de autorización.

---

# 53. Verificar la protección de sesión y CSRF

Después del primer inicio de sesión exitoso, verifique que la aplicación utiliza sus protecciones de sesión y CSRF configuradas.

La instalación no debe deshabilitar la protección CSRF para que funcionen las solicitudes de API o las acciones del navegador.

Si una solicitud legítima falla con un error CSRF, inspeccione el flujo de la aplicación en lugar de deshabilitar la protección.

El comportamiento relacionado con las sesiones está documentado en:

```text
docs/security.md
```

---

# 54. Verificar la limitación de la tasa de inicio de sesión

La protección actual de inicio de sesión utiliza un seguimiento persistente de fallos.

La progresión configurada es:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

La autenticación exitosa borra el estado de fallo aplicable.

No active repetidamente la autenticación fallida contra una instalación de producción simplemente para probar el mecanismo.

Utilice la suite de pruebas existente para la validación automatizada repetida.

---

# 55. Punto de control de validación del servidor

En esta etapa, verifique:

```text
[ ] Nginx is running
[ ] Nginx configuration passes nginx -t
[ ] TLS certificate is installed
[ ] TLS private key is protected
[ ] HTTPS works
[ ] HTTP redirects to HTTPS
[ ] Docker remains localhost-only
[ ] Port 5000 is not externally exposed
[ ] Security headers are present as configured
[ ] Default Nginx site is not unintentionally serving LUMS
[ ] Administrator account exists
[ ] Administrator can log in
[ ] Administrator RBAC works
[ ] Operator role can be created
[ ] Viewer role can be created
[ ] Viewer restrictions are enforced server-side
[ ] CSRF protection remains enabled
[ ] Session protection remains enabled
```

Solo después de que el servidor supere estas comprobaciones se deben instalar los clientes Linux.

La siguiente sección cubre el agente Linux, la configuración del cliente, la confianza TLS y la integración con systemd.

# 56. Instalación del cliente Linux

Los clientes LUMS son sistemas Linux gestionados por el servidor LUMS.

Una instalación de cliente consta de:

```text
Linux system
    ↓
LUMS Agent
    ↓
Client configuration
    ↓
Client token
    ↓
TLS trust
    ↓
systemd service
    ↓
Reporting timer
```

La ejecución de actualizaciones es manejada por separado por el watcher de ejecución.

La versión actual del agente es:

```text
1.7.0
```

La versión actual del watcher es:

```text
1.2.1
```

---

# 57. Clientes Linux compatibles

Las implementaciones actuales de gestión de paquetes admiten:

```text
Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman
```

Verifique el sistema operativo antes de instalar el cliente:

```bash
cat /etc/os-release
```

Verifique la arquitectura:

```bash
uname -m
```

Verifique systemd:

```bash
systemctl --version
```

El cliente requiere una instalación funcional de systemd.

---

# 58. Requisitos de red del cliente

El cliente debe poder alcanzar el punto de conexión HTTPS de LUMS.

Pruebe la conectividad de red básica:

```bash
ping LUMS-SERVER
```

No se requiere un ping exitoso cuando ICMP está bloqueado.

El requisito importante es la conectividad HTTPS.

Pruebe el punto de conexión de LUMS:

```bash
curl -I \
    https://LUMS-SERVER/
```

Si el servidor utiliza una CA privada, el cliente debe confiar en esa CA antes de continuar.

No deshabilite la verificación TLS como solución alternativa permanente.

---

# 59. Obtener el agente LUMS

El código fuente del agente está incluido en el repositorio LUMS.

En el cliente, obtenga el repositorio o transfiera de otra manera los archivos del agente requeridos a través del método de despliegue aprobado.

Los archivos relevantes son:

```text
agent/agent.py
agent/watcher.py
agent/package_manager.py
```

El directorio de instalación recomendado es:

```text
/opt/lums-agent
```

Créelo:

```bash
sudo install -d -m 755 \
    /opt/lums-agent
```

---

# 60. Instalar los archivos del agente

Desde el repositorio LUMS:

```bash
cd /opt/lums-public
```

Instale el agente:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Instale el watcher:

```bash
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

Instale la abstracción del gestor de paquetes:

```bash
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Verifique:

```bash
ls -lh \
    /opt/lums-agent/
```

El directorio debe contener los componentes del agente instalados.

---

# 61. Verificar las versiones del agente

Verifique la versión del agente instalada:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

La versión actual es:

```text
1.7.0
```

Verifique el watcher:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

La versión actual es:

```text
1.2.1
```

Si las versiones instaladas no coinciden con la revisión de despliegue prevista, deténgase y verifique que se esté utilizando la revisión correcta del repositorio.

---

# 62. Instalar los archivos de servicio de systemd

El agente y el watcher utilizan servicios systemd separados.

Instale el servicio del agente:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Instale el servicio del watcher:

```bash
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Instale el temporizador de reporte:

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Instale el temporizador del watcher:

```bash
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Recargue systemd:

```bash
sudo systemctl daemon-reload
```

---

# 63. Verificar las unidades de systemd

Inspeccione el servicio del agente:

```bash
systemctl cat \
    lums-agent.service
```

Inspeccione el servicio del watcher:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Inspeccione el temporizador del agente:

```bash
systemctl cat \
    lums-agent.timer
```

Inspeccione el temporizador del watcher:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Las unidades deben hacer referencia a los archivos instalados en:

```text
/opt/lums-agent/
```

No habilite los temporizadores hasta que se hayan completado la configuración del cliente y la autenticación.

---

# 64. Crear la configuración del cliente

La configuración del cliente se almacena fuera del repositorio Git.

Use:

```text
/etc/default/lums-agent
```

Cree el archivo:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

La configuración contiene el punto de conexión del servidor LUMS y el token del cliente.

Estructura de ejemplo:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Reemplace:

```text
LUMS-SERVER
```

con el punto de conexión real del servidor LUMS.

Reemplace:

```text
<CLIENT-TOKEN>
```

con el token asignado a este cliente.

Proteja la configuración:

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Verifique sin mostrar su contenido:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Esperado:

```text
600
```

---

# 65. Tokens de cliente

Cada cliente LUMS tiene su propio token de autenticación.

El token se utiliza como:

```text
Authorization: Bearer <CLIENT-TOKEN>
```

El servidor no necesita el valor original del token después del aprovisionamiento.

El servidor almacena una representación criptográfica del token para la validación.

Esto significa que las credenciales del cliente deben tratarse como contraseñas.

Nunca coloque un token real en:

```text
Git
documentation
screenshots
issue reports
shell history
public configuration
```

---

# 66. Aprovisionar el token del cliente

Cree o aprovisione el cliente desde la interfaz de administrador de LUMS según el flujo de trabajo actual de gestión de clientes.

El token de cliente resultante debe transferirse al cliente previsto a través de un canal seguro.

Almácelo solo en:

```text
/etc/default/lums-agent
```

en el cliente.

No reutilice un token de cliente en varias máquinas.

La relación prevista es:

```text
Client A
    ↓
Token A

Client B
    ↓
Token B

Client C
    ↓
Token C
```

Por lo tanto, un token comprometido solo debe identificar a su cliente asociado.

---

# 67. Rotación del token del cliente

Los tokens de cliente pueden ser rotados por un administrador.

El flujo de rotación es:

```text
Current token
     ↓
Administrator rotates token
     ↓
Old token invalidated
     ↓
New token issued
     ↓
Client configuration updated
```

Después de actualizar la configuración del cliente, ejecute el agente manualmente para verificar que la autenticación se realiza correctamente.

Un token rotado no debe seguir siendo aceptado indefinidamente.

---

# 68. Confianza TLS

El agente LUMS se comunica con el servidor a través de HTTPS.

La verificación de certificados debe permanecer habilitada.

Para un certificado de confianza pública, el almacén de confianza normal del sistema operativo es suficiente.

Para una CA de laboratorio privada, instale el certificado de la CA en el cliente.

No resuelva los problemas de certificados deshabilitando la verificación.

La solución correcta es hacer que el cliente confíe en la autoridad de certificación prevista.

---

# 69. Confianza TLS en Debian / Ubuntu

En sistemas de la familia Debian, se puede instalar una CA privada en el almacén de confianza del sistema.

Copie el certificado de la CA:

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Actualice el almacén de confianza:

```bash
sudo update-ca-certificates
```

Verifique que el certificado es aceptado:

```bash
curl -I \
    https://LUMS-SERVER/
```

Si el comando se ejecuta correctamente sin `-k`, la configuración de confianza del sistema está funcionando.

---

# 70. Confianza TLS en Arch Linux

En Arch Linux, instale la CA privada utilizando el mecanismo de almacén de confianza configurado del sistema.

Después de instalar la CA, actualice la base de datos de confianza según la configuración activa del almacén de confianza.

Verifique:

```bash
curl -I \
    https://LUMS-SERVER/
```

La conexión debería realizarse correctamente sin:

```text
-k
```

No configure permanentemente el agente para ignorar la verificación de certificados.

---

# 71. Verificar el gestor de paquetes

El agente detecta la familia de gestión de paquetes compatible.

Para Debian/Ubuntu:

```bash
command -v apt
```

y:

```bash
command -v dpkg-query
```

Verifique los paquetes instalados:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head
```

Verifique las actualizaciones disponibles:

```bash
apt list --upgradable
```

Para Arch Linux:

```bash
command -v pacman
```

Verifique los paquetes instalados:

```bash
pacman -Q | head
```

Verifique las actualizaciones disponibles:

```bash
pacman -Qu
```

La abstracción del gestor de paquetes utiliza automáticamente la implementación apropiada.

---

# 72. Verificar los permisos del agente

Inspeccione el directorio de instalación:

```bash
ls -ld \
    /opt/lums-agent
```

Inspeccione los archivos instalados:

```bash
ls -lh \
    /opt/lums-agent/
```

El agente no necesita acceso de escritura a su propio directorio de origen.

La configuración del cliente permanece protegida por separado:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Esperado:

```text
600
```

El agente requiere privilegios de sistema suficientes para inspeccionar el estado de los paquetes y realizar operaciones de paquetes.

Los privilegios exactos de tiempo de ejecución están definidos por el servicio systemd instalado.

---

# 73. Verificar la configuración del agente

Antes de iniciar el servicio, verifique que el archivo de configuración existe:

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"
```

No imprima el contenido del archivo de configuración.

Verifique que las variables requeridas existen sin exponer el token:

```bash
sudo sh -c '
set -a
. /etc/default/lums-agent
set +a

test -n "$LUMS_BASE" &&
echo "LUMS_BASE: configured"

test -n "$LUMS_TOKEN" &&
echo "LUMS_TOKEN: configured"
'
```

El valor del token en sí no debe imprimirse.

---

# 74. Probar el agente manualmente

Antes de habilitar el temporizador, ejecute el agente una vez manualmente:

```bash
sudo systemctl start \
    lums-agent.service
```

Compruebe el resultado:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

El agente es un servicio de tipo one-shot.

Después de completarse correctamente, puede mostrar:

```text
Active: inactive (dead)
```

Esto es normal.

El resultado importante es:

```text
status=0/SUCCESS
```

Inspeccione el journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 75. Verificar el primer reporte del cliente

Una ejecución exitosa del agente debería reportar el cliente al servidor LUMS.

La ruta completa es:

```text
Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
Bearer authentication
   ↓
Client lookup
   ↓
Report accepted
```

Inspeccione los registros del servidor cuando sea necesario:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

El cliente debería aparecer en la interfaz web de LUMS después de un reporte exitoso.

Que el servicio local se ejecute con éxito no es suficiente por sí solo.

El servidor debe aceptar el reporte.

---

# 76. Verificar el cliente en la interfaz web

Inicie sesión como administrador u operador.

Abra la vista general de clientes.

El nuevo cliente debería reportar información como:

```text
Hostname
IP address
Operating system
Architecture
Agent version
Last report
Installed packages
Available updates
```

La información reportada pertenece a ese cliente.

Un cliente no debe poder acceder a los recursos de otro cliente.

---

# 77. Habilitar el temporizador de reporte

Solo después de que la ejecución manual del agente tenga éxito se debe habilitar el temporizador de reporte:

```bash
sudo systemctl enable --now \
    lums-agent.timer
```

Compruebe:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Inspeccione la programación:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

El temporizador inicia periódicamente:

```text
lums-agent.service
```

El servicio en sí sigue siendo una unidad one-shot.

Por lo tanto, es normal que el servicio vuelva a:

```text
inactive (dead)
```

entre las ejecuciones del temporizador.

---

# 78. Verificar el reporte programado

Después de habilitar el temporizador, inspeccione la próxima ejecución programada:

```bash
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent
```

Después de que el temporizador se haya ejecutado, inspeccione:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verifique el reporte de cliente correspondiente en LUMS.

Un ciclo de reporte saludable es:

```text
Timer
  ↓
Agent service
  ↓
System inventory
  ↓
Package inventory
  ↓
Update detection
  ↓
HTTPS report
  ↓
LUMS database
```

---

# 79. Punto de control de instalación del cliente

Antes de instalar el watcher de ejecución, verifique:

```text
[ ] Supported Linux distribution
[ ] Python 3 available
[ ] systemd available
[ ] Package manager available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher files installed
[ ] Client configuration exists
[ ] Client token protected
[ ] TLS certificate trusted
[ ] Agent service succeeds
[ ] Client report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Scheduled reporting verified
```

No proceda a las pruebas de trabajos de actualización hasta que funcione la ruta de reporte.

La siguiente sección instala y valida el watcher de ejecución.

# 80. Instalar el watcher de ejecución

El watcher de ejecución de LUMS es responsable de detectar y ejecutar trabajos de actualización pendientes en el cliente.

La arquitectura separa el reporte de la ejecución:

```text
Reporting
    │
    ▼
lums-agent.service
    │
    └── system inventory / update detection

Execution
    │
    ▼
lums-agent-watcher.service
    │
    └── pending update jobs
```

Esta separación permite que el reporte regular del cliente continúe independientemente de la ejecución de actualizaciones.

---

# 81. Verificar la instalación del watcher

Verifique que el watcher está presente:

```bash
ls -lh \
    /opt/lums-agent/watcher.py
```

Verifique la versión instalada:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

La versión actual del watcher es:

```text
1.2.1
```

---

# 82. Verificar el servicio del watcher

Inspeccione la unidad systemd:

```bash
systemctl cat \
    lums-agent-watcher.service
```

El servicio debe hacer referencia a:

```text
/opt/lums-agent/watcher.py
```

Verifique que la unidad es conocida por systemd:

```bash
systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

El servicio puede estar inactivo cuando no se ha activado ninguna ejecución.

Esto no es en sí mismo un error.

---

# 83. Verificar el temporizador del watcher

Antes de habilitar el temporizador del watcher, verifique que:

- `/etc/default/lums-agent` existe y contiene la configuración correcta del cliente.
- El punto de conexión del servidor LUMS y el token del cliente están configurados correctamente.
- Una ejecución manual del agente tuvo éxito y el servidor aceptó el reporte del cliente.
- Ambos archivos de unidad del watcher fueron instalados desde el repositorio.

No habilite el temporizador mientras la autenticación o el reporte estén fallando.

Inspeccione el temporizador:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Habilite el temporizador solo después de verificar todos los requisitos previos anteriores:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Verifique:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspeccione la próxima ejecución programada:

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

---

# 84. Comprender la ejecución consciente de la inactividad

El watcher puede usar la información de inactividad del cliente antes de ejecutar trabajos de actualización.

El flujo previsto es:

```text
Pending job
    │
    ▼
Watcher
    │
    ▼
Idle detection
    │
    ├── idle state available
    │       │
    │       ▼
    │   idle threshold
    │       │
    │       ▼
    │   execute when allowed
    │
    └── idle state unavailable
            │
            ▼
        use configured
        fallback behavior
```

La detección de inactividad nunca debe interpretarse como autenticación o autorización.

Es solo un mecanismo de programación de ejecución.

---

# 85. Verificar la detección de inactividad

Ejecute la ruta de detección de inactividad manualmente a través de la implementación instalada del agente/watcher.

Inspeccione el journal del servicio resultante:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Si la plataforma no proporciona la información de inactividad requerida, el cliente puede reportar la detección de inactividad como no disponible.

Esto no es automáticamente un fallo.

La distinción importante es:

```text
idle_supported = available
```

frente a:

```text
idle_supported = unavailable
```

No se debe suponer que el cliente está inactivo solo porque no se devolvió información de inactividad.

---

# 86. Crear un trabajo de actualización de prueba controlado

No comience las pruebas de instalación con una actualización grande del sistema.

Use un paquete pequeño y conocido para la primera prueba.

El paquete debe:

```text
exist in the configured repository
be safe to install
be removable again
not be required by the operating system
```

Paquete de prueba de ejemplo:

```text
sl
```

Antes de crear el trabajo, verifique si ya está instalado:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Para Arch Linux, use un paquete que esté disponible en los repositorios configurados y sea adecuado para una prueba reversible.

No use `sl` a ciegas en todas las distribuciones.

---

# 87. Verificar la búsqueda de paquetes

Use la interfaz de gestión de paquetes de LUMS para buscar el paquete seleccionado.

El flujo de búsqueda es:

```text
Browser
   ↓
LUMS API
   ↓
Package Search Request
   ↓
Client
   ↓
APT / pacman
   ↓
Package Search Result
   ↓
LUMS API
   ↓
Browser
```

Verifique que el resultado contiene la información esperada:

```text
Package
Version
Description
Status
Action
```

Para Arch Linux, también puede devolverse información del repositorio.

---

# 88. Permisos de gestión de paquetes

La gestión de paquetes está restringida por RBAC.

Administrator:

```text
Allowed
```

Operator:

```text
Allowed
```

Viewer:

```text
Not allowed
```

Un viewer no debe poder ejecutar la instalación o eliminación de paquetes llamando directamente a la API.

Ocultar la función en la interfaz del navegador es solo una restricción de usabilidad adicional.

La autorización del lado del servidor es la frontera de seguridad real.

---

# 89. Probar la instalación de paquetes

Cree un trabajo de instalación a través de la interfaz de LUMS.

La operación lógica es:

```text
INSTALL_PACKAGE
```

El trabajo se almacena en la base de datos de LUMS antes de que el agente lo ejecute.

El flujo esperado es:

```text
Create job
   ↓
PENDING
   ↓
Watcher detects job
   ↓
RUNNING
   ↓
Package manager
   ↓
SUCCESS
```

Supervise el trabajo en la interfaz de LUMS.

No modifique manualmente la base de datos para forzar un estado de trabajo.

---

# 90. Verificar el resultado de la instalación

Después de que el trabajo informe éxito, verifique el paquete localmente.

En Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl
```

Verifique que el gestor de paquetes está de acuerdo:

```bash
apt-cache policy \
    sl
```

El paquete debe estar realmente instalado.

Un estado `SUCCESS` de LUMS debe corresponder a una operación exitosa del lado del cliente.

---

# 91. Verificar el resultado del trabajo

Inspeccione el historial de trabajos de LUMS.

Verifique:

```text
Action
Package
Client
Start time
Completion time
Result
```

El resultado devuelto por el cliente debe ser validado por el servidor.

Los datos de resultado inválidos o incompletos no deben convertirse silenciosamente en un trabajo exitoso.

Esta validación es parte del modelo de seguridad y fiabilidad de LUMS.

---

# 92. Probar la eliminación de paquetes

Después de verificar la instalación, cree un trabajo de eliminación:

```text
REMOVE_PACKAGE
```

Supervise:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

Después de completarse:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

El paquete ya no debería estar instalado.

Si el paquete no estaba instalado antes de la prueba, no trate la ausencia como prueba de una operación de eliminación exitosa.

---

# 93. Probar la actualización de paquetes

Las actualizaciones de paquetes utilizan:

```text
UPDATE_PACKAGE
```

El servidor valida que el paquete solicitado es una actualización disponible antes de crear el trabajo correspondiente.

El flujo general es:

```text
Client reports available updates
       ↓
User selects package
       ↓
Server validates package
       ↓
Update job created
       ↓
Watcher executes
       ↓
Result reported
```

No construya manualmente solicitudes de actualización que eludan la ruta de validación normal.

---

# 94. Probar la actualización del sistema

Una actualización completa del sistema utiliza:

```text
UPDATE_SYSTEM
```

Esta operación afecta al estado del gestor de paquetes del cliente de forma más amplia que una operación de un solo paquete.

Para la primera prueba de actualización del sistema:

```text
Use a test client
Use a current backup
Monitor the console
Monitor the LUMS job
Do not interrupt the package manager
```

No use el servidor de producción en sí como primer objetivo de prueba de actualización del sistema.

---

# 95. Bloqueos del gestor de paquetes

APT y pacman pueden usar bloqueos del gestor de paquetes.

Cuando una operación falla porque otro proceso de gestión de paquetes está activo, inspeccione los procesos en ejecución antes de tomar medidas.

Debian/Ubuntu:

```bash
ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'
```

Arch Linux:

```bash
ps aux | grep -E \
    '[p]acman|[p]ar'
```

No elimine los archivos de bloqueo del gestor de paquetes mientras el gestor de paquetes esté realmente en ejecución.

Un bloqueo normalmente protege contra operaciones concurrentes de paquetes.

---

# 96. Distinguir fallos de LUMS de fallos del gestor de paquetes

Cuando un trabajo falla, determine qué capa falló.

```text
LUMS API
   │
   ├── Job creation failure
   │
   ▼
LUMS database
   │
   ├── State / persistence problem
   │
   ▼
Watcher
   │
   ├── Execution problem
   │
   ▼
Package manager
   │
   ├── APT / pacman failure
   │
   ▼
Operating system
```

Inspeccione el journal del cliente:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspeccione el contenedor LUMS:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

No reintente inmediatamente un trabajo fallido sin determinar por qué falló.

---

# 97. Verificar los puntos de control de trabajos

LUMS rastrea el estado de trabajos y de elementos de paquetes.

Para los trabajos basados en paquetes, los elementos de paquetes individuales pueden tener puntos de control.

El comportamiento previsto es:

```text
Package A → SUCCESS
Package B → SUCCESS
Package C → RUNNING
             │
             ▼
          interruption
             │
             ▼
          recovery
             │
             ▼
Package A → not repeated
Package B → not repeated
Package C → resumed / handled
```

Esto evita que las operaciones de paquetes completadas se repitan innecesariamente después de una interrupción.

---

# 98. Probar la recuperación controlada de trabajos

Use un trabajo de prueba no crítico.

Inicie el trabajo y observe su estado:

```text
PENDING
```

luego:

```text
RUNNING
```

No interrumpa deliberadamente una actualización de producción.

Para las pruebas de recuperación, use un cliente de prueba dedicado y una operación de paquete controlada.

Después de una interrupción o fallo simulado, reinicie el watcher:

```bash
sudo systemctl restart \
    lums-agent-watcher.timer
```

Luego inspeccione:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Verifique que los elementos de paquetes que ya tuvieron éxito no se ejecuten innecesariamente de nuevo.

---

# 99. Verificar la detección de reinicio

Algunas operaciones de paquetes pueden requerir un reinicio.

El agente/watcher reporta los requisitos de reinicio a LUMS.

El flujo general es:

```text
Package operation
      ↓
Reboot requirement detected
      ↓
Result reported
      ↓
LUMS records reboot state
```

Después de una operación de prueba que requiera legítimamente un reinicio, verifique el resultado del trabajo correspondiente en la interfaz de LUMS.

No reinicie un cliente de producción solo para probar el mecanismo a menos que el sistema esté destinado a esa prueba.

---

# 100. Verificar el reporte después del reinicio

Cuando se reinicia un cliente de prueba, verifique que:

```text
systemd
   ↓
LUMS Agent timer
   ↓
Agent report
   ↓
LUMS server
```

continúa funcionando.

Compruebe:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

y:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Luego inspeccione el último reporte en la interfaz de LUMS.

---

# 101. Verificar la detección de actualizaciones

Ejecute el agente manualmente:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspeccione:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

El cliente debería reportar:

```text
Installed packages
Available updates
Agent status
```

El servidor debería actualizar el estado actual del cliente.

No confunda:

```text
available updates
```

con:

```text
installed packages
```

Representan conjuntos de datos diferentes.

---

# 102. Verificar el software instalado

Abra la sección de software instalado del cliente en LUMS.

La lista de paquetes debe corresponder al gestor de paquetes del lado del cliente.

Para Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'
```

Para Arch:

```bash
pacman -Q
```

El inventario de LUMS es informativo hasta que se crea explícitamente un trabajo.

El filtro de paquetes instalados no modifica el cliente por sí mismo.

---

# 103. Verificar la búsqueda de paquetes por separado

La búsqueda de gestión de paquetes es independiente del filtro de paquetes instalados.

La distinción es:

```text
Installed Package Filter
    ↓
Searches the package inventory already reported by the client

Package Management Search
    ↓
Requests package information from the client's package manager
```

No trate las dos funciones de búsqueda como intercambiables.

Un paquete puede estar disponible a través de APT o pacman sin estar instalado.

---

# 104. Verificar el aislamiento de paquetes para viewers

Inicie sesión como viewer.

Verifique que la interfaz de gestión de paquetes no está disponible.

Luego verifique la restricción del lado del servidor intentando una solicitud de gestión de paquetes no autorizada a través de un método de prueba aprobado.

La solicitud debe ser rechazada.

El acceso del viewer debe permanecer de solo lectura.

---

# 105. Verificar la gestión de paquetes del operador

Inicie sesión como operador.

Verifique el acceso a:

```text
Package Search
Package Installation
Package Removal
Package Updates
Update Jobs
Update History
```

El operador no debe obtener acceso a funciones de gestión de usuarios exclusivas del administrador.

---

# 106. Verificar la gestión de paquetes del administrador

Inicie sesión como administrador.

Verifique las mismas capacidades de gestión de paquetes que el operador.

Además, verifique el acceso a:

```text
User Management
Client Management
Client Token Rotation
```

Los permisos de administrador deben seguir aplicándose en el servidor.

---

# 107. Primera prueba de paquete de extremo a extremo

La primera prueba completa de gestión de paquetes debe seguir esta secuencia:

```text
1. Client reports successfully
2. Package search succeeds
3. Package result is displayed
4. Administrator/Operator creates INSTALL_PACKAGE job
5. Job becomes PENDING
6. Watcher detects the job
7. Job becomes RUNNING
8. Package manager executes
9. Client reports result
10. Server validates result
11. Job becomes SUCCESS
12. Installed package is verified locally
13. Package is visible in LUMS inventory
```

Solo después de que esta secuencia tenga éxito se deben comenzar pruebas de actualización más amplias.

---

# 108. Punto de control de ejecución del cliente

Verifique:

```text
[ ] Watcher installed
[ ] Watcher version verified
[ ] Watcher timer enabled
[ ] Idle detection works or reports unavailable correctly
[ ] Package search works
[ ] Package installation works
[ ] Package removal works
[ ] Package update works
[ ] System update path is available
[ ] Job states transition correctly
[ ] Job results are validated
[ ] Package checkpointing works
[ ] Reboot detection works
[ ] Reporting continues after reboot
[ ] Viewer cannot mutate package state
[ ] Operator can manage packages
[ ] Administrator can manage packages
```

En este punto, la ruta principal de ejecución del cliente LUMS está instalada y validada.

La siguiente sección cubre la validación completa de extremo a extremo, la verificación RBAC, la copia de seguridad/restauración, el mantenimiento, las actualizaciones y las comprobaciones finales de instalación.

# 109. Validación completa de extremo a extremo

Después de que el servidor y al menos un cliente Linux hayan sido configurados, realice una validación completa de extremo a extremo.

La ruta completa de LUMS es:

```text
Browser
   │
   ▼
Nginx / HTTPS
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Client Agent
   │
   ▼
Package Manager
   │
   ▼
Update Result
   │
   ▼
SQLite
   │
   ▼
Web Interface
```

No considere la instalación completa solo porque se abra la interfaz web.

Todas las capas principales deben verificarse.

---

# 110. Comprobación de estado del servidor

Verifique el contenedor LUMS:

```bash
sudo docker ps \
    --filter name=lums
```

Verifique el estado del contenedor:

```bash
sudo docker inspect \
    lums \
    --format '{{.State.Status}}'
```

Esperado:

```text
running
```

Inspeccione los registros recientes:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Los registros no deben contener un fallo de inicio o de migración activo.

---

# 111. Comprobación de seguridad del contenedor

Verifique la configuración de seguridad en tiempo de ejecución:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Línea base esperada:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Verifique la vinculación de red:

```bash
sudo docker port \
    lums
```

Esperado:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 112. Comprobación del almacenamiento persistente

Verifique el volumen de LUMS:

```bash
sudo docker volume inspect \
    lums-data
```

Verifique que existe la base de datos de la aplicación:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

La base de datos debe residir en almacenamiento persistente.

No almacene la base de datos de producción solo dentro del sistema de archivos del contenedor.

---

# 113. Comprobación de estado de SQLite

Inspeccione la configuración de tiempo de ejecución actual de SQLite:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for name in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    value = db.execute(
        f"PRAGMA {name}"
    ).fetchone()[0]
    print(f"{name}={value}")

db.close()
PY
```

La línea base actual es:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

La aplicación habilita explícitamente la aplicación de claves foráneas.

---

# 114. Comprobación de integridad de SQLite

Ejecute:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

result = db.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print(result)

db.close()
PY
```

Esperado:

```text
ok
```

No continúe con un nuevo despliegue de producción si la comprobación de integridad informa corrupción.

---

# 115. Verificar las migraciones de la base de datos

Inspeccione el estado de las migraciones:

```bash
sudo docker logs \
    --tail 200 \
    lums | grep -i migration
```

La aplicación debe completar sus migraciones configuradas antes del funcionamiento normal.

No modifique manualmente la tabla de estado de migraciones a menos que el procedimiento de migración actual de LUMS lo requiera explícitamente.

---

# 116. Ejecutar la suite de pruebas automatizadas

En el entorno de desarrollo/prueba de LUMS:

```bash
cd /opt/lums-public
```

Ejecute:

```bash
./.venv-test/bin/pytest -q
```

El número de pruebas cambia a medida que el proyecto evoluciona; confíe en el resultado del comando, no en un número fijo en este documento.

El requisito importante es:

```text
all tests pass
```

No ignore las pruebas que fallan porque la interfaz web de producción parece funcional.

---

# 117. Verificar el RBAC

El modelo de roles actual es:

| Función                    | Administrator | Operator | Viewer |
| -------------------------- | ------------: | -------: | -----: |
| Ver clientes               |            Sí |       Sí |     Sí |
| Software instalado         |            Sí |       Sí |     Sí |
| Actualizaciones disponibles |           Sí |       Sí |     No |
| Crear/ejecutar trabajos    |            Sí |       Sí |     No |
| Historial de actualizaciones |          Sí |       Sí |     No |
| Gestión de paquetes        |            Sí |       Sí |     No |
| Mantenimiento del sistema  |            Sí |       Sí |     No |
| Crear/deshabilitar clientes |           Sí |       No |     No |
| Rotar tokens de cliente    |            Sí |       No |     No |
| Gestión de usuarios        |            Sí |       No |     No |
| Gestión de roles           |            Sí |       No |     No |

La interfaz debe reflejar estos permisos.

Más importante aún, la API debe aplicarlos de forma independiente.

---

# 118. Verificar el acceso del administrador

Inicie sesión como administrator.

Verifique el acceso a:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

Verifique las funciones de gestión de clientes:

```text
Create client
Disable client
Rotate client token
```

El administrador debe poder realizar estas operaciones.

---

# 119. Verificar el acceso del operador

Inicie sesión como operator.

Verifique el acceso a:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Verifique que la funcionalidad exclusiva del administrador no está disponible:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

No confíe solo en elementos de interfaz ocultos.

Las operaciones de API protegidas deben rechazar solicitudes no autorizadas.

---

# 120. Verificar el acceso del viewer

Inicie sesión como viewer.

El viewer debe poder acceder a:

```text
Clients
Installed software
```

Lo siguiente no debe estar disponible:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

El viewer no debe poder modificar el estado del cliente.

---

# 121. Verificar la autenticación del cliente

Confirme que cada cliente utiliza su propio token Bearer.

El modelo esperado es:

```text
Client A → Token A
Client B → Token B
Client C → Token C
```

No comparta tokens entre clientes.

Verifique que un token rotado o revocado ya no se acepta.

Nunca coloque tokens reales en la salida de pruebas o en la documentación.

---

# 122. Verificar la detección de actualizaciones

En un cliente de prueba:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspeccione:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Luego verifique el cliente en la interfaz de LUMS.

La información reportada debe incluir el inventario actual de paquetes y la información de actualizaciones cuando sea compatible.

---

# 123. Verificar la creación de trabajos de actualización

Cree un trabajo de actualización controlado a través de la interfaz de LUMS.

El trabajo inicialmente debería aparecer como:

```text
PENDING
```

Luego el watcher procesa el trabajo:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

o:

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
```

según el resultado real de la operación.

No cambie manualmente el estado de la base de datos.

---

# 124. Verificar la ejecución del trabajo

Inspeccione el watcher del cliente:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspeccione el servidor LUMS:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Compare el estado del trabajo del lado del servidor con el resultado de ejecución del lado del cliente.

Ambos deben coincidir.

---

# 125. Verificar la validación del resultado del paquete

Un trabajo no debe volverse exitoso solo porque el cliente envió una respuesta sintácticamente válida.

El servidor valida el resultado devuelto.

Verifique esto a través de las pruebas automatizadas de validación de resultados:

```bash
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Un resultado exitoso debe contener la estructura esperada y un contexto de trabajo válido.

Los resultados malformados o inconsistentes deben ser rechazados.

---

# 126. Verificar la recuperación de trabajos

Use un cliente de prueba dedicado para las pruebas de recuperación.

El modelo de recuperación es:

```text
Job
 │
 ├── package item A → SUCCESS
 ├── package item B → SUCCESS
 └── package item C → interrupted
                       │
                       ▼
                    recovery
                       │
                       ▼
                  resume safely
```

Después de la recuperación, los elementos de paquetes que ya tuvieron éxito no deben repetirse innecesariamente.

Inspeccione:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Luego verifique el estado final del trabajo en LUMS.

---

# 127. Verificar la detección de reinicio

Para una actualización de prueba controlada que requiera un reinicio, verifique que el cliente reporta el requisito de reinicio.

Después del reinicio:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

y:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

El cliente debe reanudar el reporte normal después del arranque.

---

# 128. Verificar el registro de auditoría

Realice una acción administrativa controlada y luego inspeccione el registro de auditoría de LUMS.

Las operaciones relevantes incluyen:

```text
Login
User creation
Client creation
Client-token rotation
Job creation
Package management
```

Las entradas de auditoría deben proporcionar suficiente información para reconstruir la acción administrativa sin exponer secretos.

No registre:

```text
Passwords
Client tokens
Application secrets
Private keys
Session secrets
```

---

# 129. Verificar la redacción de registros

Inspeccione los registros recientes:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Inspeccione los registros del cliente:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

y:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Las credenciales de autenticación y los secretos no deben aparecer en la salida de diagnóstico normal.

Si un comando de diagnóstico expusiera un secreto, no pegue su salida en un issue, commit o documentación.

---

# 130. Verificar la exposición de red

Inspeccione los puertos en escucha:

```bash
sudo ss -lntp
```

El puerto de la aplicación LUMS debe permanecer:

```text
127.0.0.1:5050
```

Nginx proporciona el servicio externo:

```text
:80
:443
```

La aplicación no debe exponerse directamente a través de:

```text
0.0.0.0:5050
```

o:

```text
0.0.0.0:5000
```

---

# 131. Verificar la configuración del firewall

Si hay un firewall de host habilitado, inspecciónelo:

```bash
sudo ufw status verbose
```

El despliegue solo debe exponer los servicios requeridos por el host.

No cree una regla de firewall para el puerto `5050` solo porque Docker usa ese puerto internamente.

La arquitectura prevista es:

```text
LAN
 │
 ▼
443
 │
 ▼
Nginx
 │
 ▼
127.0.0.1:5050
 │
 ▼
LUMS
```

---

# 132. Estrategia de copia de seguridad

La base de datos SQLite de LUMS es estado persistente de la aplicación.

Como mínimo, las copias de seguridad deben proteger:

```text
LUMS database
TLS material
LUMS application secret
Deployment configuration
```

Las copias de seguridad deben almacenarse fuera del contenedor LUMS activo.

No almacene copias de seguridad dentro de:

```text
/app
```

ni dependa del sistema de archivos del contenedor.

El volumen Docker:

```text
lums-data
```

contiene datos persistentes de la aplicación, pero un volumen Docker no es en sí mismo una copia de seguridad.

---

# 133. Copia de seguridad de la base de datos

Antes de hacer una copia de seguridad de la base de datos, identifique el archivo de la base de datos:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Una copia de seguridad de la base de datos debe realizarse utilizando un mecanismo de copia de seguridad de SQLite consistente.

No copie a ciegas una base de datos SQLite en vivo mientras se está modificando si el procedimiento de copia de seguridad no puede garantizar la consistencia.

Después de crear una copia de seguridad, verifique que el archivo de copia de seguridad existe y está protegido.

---

# 134. Copia de seguridad de la configuración

Proteja el siguiente material de despliegue:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

No publique estos archivos.

Los siguientes archivos son particularmente sensibles:

```text
/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key
```

Proteja los permisos de las copias de seguridad en consecuencia.

---

# 135. Planificación de la restauración

Se debe probar una restauración en un sistema que no sea de producción antes de que sea necesaria para la recuperación ante desastres.

La secuencia de restauración es conceptualmente:

```text
Backup
  ↓
Verify backup integrity
  ↓
Prepare clean LUMS host
  ↓
Restore secret/configuration
  ↓
Restore database
  ↓
Restore TLS material
  ↓
Start LUMS
  ↓
Run integrity checks
  ↓
Validate users/clients/jobs
```

No sobrescriba una base de datos de producción sin antes preservar el estado existente.

---

# 136. Verificar una restauración de base de datos

Después de restaurar una base de datos, ejecute:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

print(
    db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

db.close()
PY
```

Esperado:

```text
ok
```

Luego verifique:

```text
users
clients
update jobs
package data
audit data
```

No suponga que una comprobación de integridad de SQLite exitosa demuestra que el estado completo de la aplicación es correcto.

---

# 137. Principios de mantenimiento

El mantenimiento de rutina debe seguir:

```text
Observe
   ↓
Back up
   ↓
Change
   ↓
Verify
```

No realice mantenimiento no relacionado durante un trabajo de actualización activo.

Antes del mantenimiento:

```bash
sudo docker ps \
    --filter name=lums
```

Compruebe los trabajos activos en la interfaz de LUMS.

Si hay una actualización en ejecución, déjela terminar a menos que la operación de mantenimiento requiera específicamente una interrupción.

---

# 138. Mantenimiento del contenedor

Inspeccione la imagen en ejecución:

```bash
sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'
```

Inspeccione el contenedor:

```bash
sudo docker ps \
    --filter name=lums
```

Inspeccione los registros recientes:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

No elimine el volumen persistente durante el mantenimiento ordinario del contenedor.

El volumen contiene el estado de la aplicación.

---

# 139. Mantenimiento de la imagen

Antes de reemplazar la imagen de producción:

```bash
cd /opt/lums-public
```

Ejecute las pruebas automatizadas:

```bash
./.venv-test/bin/pytest -q
```

Construya la nueva imagen:

```bash
sudo docker build \
    -t lums:new \
    .
```

No reemplace el contenedor en ejecución hasta que la imagen haya superado la validación requerida.

Mantenga disponible el contenedor actualmente funcional hasta que se haya verificado el reemplazo.

---

# 140. Reemplazo controlado del contenedor

Al reemplazar el contenedor de producción:

```text
Current container
       │
       ▼
Backup / checkpoint
       │
       ▼
Build new image
       │
       ▼
Validate image
       │
       ▼
Stop old container
       │
       ▼
Start new container
       │
       ▼
Validate runtime
       │
       ▼
Validate HTTPS
       │
       ▼
Validate application
```

El volumen persistente debe permanecer:

```text
lums-data
```

El montaje del secreto debe permanecer de solo lectura.

El puerto de la aplicación debe permanecer solo en localhost.

---

# 141. Verificar la seguridad en tiempo de ejecución después del reemplazo

Después de cada reemplazo de contenedor, repita:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Verifique:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

También verifique:

```bash
sudo docker port \
    lums
```

Esperado:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 142. Verificar los datos persistentes después del reemplazo

Después de iniciar el contenedor de reemplazo:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Luego:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Esperado:

```text
ok
```

Finalmente, verifique que los usuarios y clientes existentes siguen presentes a través de la interfaz de LUMS.

---

# 143. Punto de control de finalización del mantenimiento

Después del mantenimiento, verifique:

```text
[ ] Container running
[ ] Runtime hardening intact
[ ] Persistent volume mounted
[ ] Database accessible
[ ] SQLite integrity check passes
[ ] Nginx running
[ ] HTTPS working
[ ] Login working
[ ] Existing users present
[ ] Existing clients present
[ ] Agent reporting working
[ ] Watcher working
[ ] Update jobs working
[ ] Audit logging working
```

Solo después de estas comprobaciones se completa la operación de mantenimiento.

---

# 144. Estado de la instalación en este punto

Un entorno LUMS correctamente instalado ahora consta de:

```text
                    ┌──────────────────────┐
                    │       Browser        │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │        Nginx         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    LUMS Container    │
                    │                      │
                    │ Flask / Gunicorn     │
                    │ RBAC                 │
                    │ CSRF                 │
                    │ Audit Logging        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       SQLite         │
                    │     lums-data        │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌──────────────┐              ┌──────────────┐
        │ LUMS Agent   │              │ LUMS Watcher │
        │ 1.7.0        │              │ 1.2.1        │
        └──────┬───────┘              └──────┬───────┘
               │                             │
               ▼                             ▼
        Inventory / Report             Update Jobs
               │                             │
               └──────────────┬──────────────┘
                              ▼
                       APT / pacman
```

Esta es la arquitectura operativa prevista.

La siguiente sección cubre actualizaciones, desinstalación y la lista de comprobación final de instalación.

# 145. Procedimiento de actualización

Las actualizaciones de LUMS deben realizarse en pasos controlados.

La secuencia recomendada es:

```text
Review
   ↓
Backup
   ↓
Test
   ↓
Build
   ↓
Deploy
   ↓
Validate
```

No actualice la instalación de producción solo porque exista una nueva revisión de Git.

Revise primero los cambios:

```bash
cd /opt/lums-public

git status
git log --oneline -10
```

Revise los cambios relevantes de la aplicación, el agente y las migraciones antes del despliegue.

---

# 146. Crear una copia de seguridad previa a la actualización

Antes de reemplazar el contenedor de producción, cree una copia de seguridad actual del estado persistente de LUMS.

Verifique el volumen activo:

```bash
sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'
```

Confirme que:

```text
lums-data
```

sigue montado en:

```text
/var/lib/lums
```

También proteja la configuración externa:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/
```

No proceda con una actualización si no se puede verificar la copia de seguridad requerida.

---

# 147. Detener cambios innecesarios durante una actualización

Antes de actualizar, inspeccione los trabajos activos en la interfaz de LUMS.

Evite reemplazar la aplicación mientras un trabajo de actualización crítico se está ejecutando activamente.

Si es necesario, espere hasta que el trabajo alcance un estado final:

```text
SUCCESS
```

o:

```text
FAILED
```

No cambie manualmente un trabajo de `RUNNING` a `SUCCESS` o `FAILED` solo para hacer posible una actualización.

---

# 148. Actualizar el repositorio

Diríjase al repositorio:

```bash
cd /opt/lums-public
```

Inspeccione el estado actual:

```bash
git status
```

Actualice el repositorio utilizando el flujo de trabajo normal del proyecto.

Después de actualizar:

```bash
git log --oneline -5
```

Verifique que la revisión prevista está extraída.

No despliegue un repositorio que contenga modificaciones locales no intencionadas.

Si hay cambios locales presentes:

```bash
git status
```

Revíselos antes de continuar.

---

# 149. Ejecutar la suite de pruebas antes de construir

Ejecute:

```bash
./.venv-test/bin/pytest -q
```

Todas las pruebas deben pasar.

Un número de pruebas modificado no es automáticamente un problema. El requisito es que la suite completa se complete con éxito.

---

# 150. Construir la imagen actualizada

Construya una nueva imagen sin reemplazar inmediatamente el contenedor en ejecución:

```bash
sudo docker build \
    -t lums:new \
    .
```

Verifique la imagen:

```bash
sudo docker image inspect \
    lums:new
```

La construcción debe completarse con éxito.

No use una imagen fallida o parcialmente construida para el despliegue de producción.

---

# 151. Verificar la imagen actualizada

Revise los metadatos de la imagen:

```bash
sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'
```

La imagen debe preservar el modelo esperado de aplicación no root.

El tiempo de ejecución de producción debe seguir proporcionando:

```text
read-only root filesystem
dropped Linux capabilities
no-new-privileges
read-only secret mount
persistent application volume
localhost-only application port
```

---

# 152. Reemplazar el contenedor de producción

Cuando la nueva imagen haya superado la validación, reemplace el contenedor en ejecución utilizando la configuración endurecida establecida.

Detenga el contenedor existente:

```bash
sudo docker stop \
    lums
```

Elimine solo el contenedor:

```bash
sudo docker rm \
    lums
```

**No** elimine:

```text
lums-data
```

Inicie el reemplazo con el tiempo de ejecución endurecido:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:new
```

---

# 153. Verificar el contenedor de reemplazo

Compruebe:

```bash
sudo docker ps \
    --filter name=lums
```

Luego:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Verifique el tiempo de ejecución:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Esperado:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

---

# 154. Verificar la disponibilidad de la aplicación

Compruebe el punto de conexión local de la aplicación:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Luego pruebe la ruta HTTPS pública:

```bash
curl -I \
    https://LUMS-SERVER/
```

Verifique el inicio de sesión a través del navegador.

No considere la actualización completa hasta que también se haya probado la ruta HTTPS externa.

---

# 155. Verificar el estado persistente después de la actualización

Compruebe la base de datos:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Ejecute:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Esperado:

```text
ok
```

Verifique a través de la interfaz web que:

```text
users
clients
jobs
audit history
package information
```

siguen disponibles.

---

# 156. Verificar la comunicación del cliente después de la actualización

Ejecute el agente en un cliente de prueba:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspeccione:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verifique que el servidor acepta el reporte.

Luego verifique el cliente en la interfaz de LUMS.

---

# 157. Verificar la ejecución de actualizaciones después de la actualización

Cree un trabajo de prueba controlado.

Verifique:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

o un estado esperado:

```text
FAILED
```

cuando la operación falla realmente.

Inspeccione el watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Esto confirma que la actualización no rompió la ruta de ejecución.

---

# 158. Verificar la línea base de seguridad después de la actualización

Cada actualización de producción debe preservar la línea base de seguridad.

Verifique:

```text
[ ] HTTPS
[ ] Bearer client authentication
[ ] RBAC
[ ] CSRF protection
[ ] Audit logging
[ ] Non-root container
[ ] Read-only root filesystem
[ ] Capabilities dropped
[ ] no-new-privileges
[ ] Protected secret mount
[ ] Persistent data volume
[ ] Localhost-only Docker port
[ ] Firewall policy
```

Una actualización funcional que debilite estas propiedades no se considera completa.

---

# 159. Procedimiento de reversión

Si el nuevo contenedor falla la validación, no destruya inmediatamente la información de despliegue anterior.

Primero inspeccione:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Si la imagen anterior todavía está disponible:

```bash
sudo docker images
```

restaure la imagen previamente validada utilizando la misma configuración de contenedor endurecido.

El volumen persistente permanece:

```text
lums-data
```

No restaure una copia de seguridad de la base de datos solo porque se reemplazó el contenedor de la aplicación.

Solo restaure la base de datos cuando la base de datos en sí deba recuperarse.

---

# 160. Preparación de la desinstalación

Antes de desinstalar LUMS, decida si se deben conservar los datos persistentes de la aplicación.

Los siguientes son recursos separados:

```text
Container
Image
Persistent volume
Configuration
TLS material
Nginx configuration
Client installations
```

Eliminar el contenedor no elimina el volumen Docker.

Esta distinción es intencional.

---

# 161. Eliminar el contenedor LUMS

Detenga el contenedor:

```bash
sudo docker stop \
    lums
```

Elimínelo:

```bash
sudo docker rm \
    lums
```

Verifique:

```bash
sudo docker ps -a \
    --filter name=lums
```

El volumen persistente sigue presente a menos que se elimine explícitamente.

---

# 162. Eliminar la imagen Docker de LUMS

Liste las imágenes:

```bash
sudo docker images \
    'lums*'
```

Elimine solo las imágenes que ya no sean necesarias:

```bash
sudo docker rmi \
    lums:new
```

Repita para otras imágenes LUMS locales obsoletas según corresponda.

No elimine la imagen actualmente requerida para una reversión antes de que la instalación haya sido completamente desmantelada.

---

# 163. Eliminar el volumen persistente

Realice este paso solo cuando la base de datos de LUMS ya no sea necesaria.

Verifique:

```bash
sudo docker volume inspect \
    lums-data
```

Cree una copia de seguridad final si es necesario.

Luego elimine:

```bash
sudo docker volume rm \
    lums-data
```

Esto elimina permanentemente los datos persistentes de la aplicación almacenados en ese volumen.

No ejecute este comando durante actualizaciones normales.

---

# 164. Eliminar la configuración del servidor LUMS

Cuando el servidor se desmantela permanentemente, elimine la configuración específica de LUMS:

```text
/etc/lums/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Elimine el sitio de Nginx:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/lums
```

Elimine la configuración:

```bash
sudo rm -f \
    /etc/nginx/sites-available/lums
```

Luego valide Nginx:

```bash
sudo nginx -t
```

Recargue:

```bash
sudo systemctl reload nginx
```

Solo elimine `/etc/lums/` después de verificar que ninguna otra aplicación depende de él.

---

# 165. Eliminar las instalaciones de clientes

Los clientes LUMS deben desmantelarse por separado.

Deshabilite el temporizador del agente:

```bash
sudo systemctl disable --now \
    lums-agent.timer
```

Deshabilite el temporizador del watcher:

```bash
sudo systemctl disable --now \
    lums-agent-watcher.timer
```

Detenga cualquier servicio restante:

```bash
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service
```

Elimine las unidades systemd instaladas:

```bash
sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Recargue systemd:

```bash
sudo systemctl daemon-reload
```

Elimine la instalación del agente:

```bash
sudo rm -rf \
    /opt/lums-agent
```

Elimine la configuración del cliente:

```bash
sudo rm -f \
    /etc/default/lums-agent
```

Realice estos pasos solo cuando el cliente se esté eliminando genuinamente de la gestión de LUMS.

---

# 166. Lista de comprobación final de instalación del servidor

Una instalación completa de LUMS debe cumplir todo lo siguiente:

```text
SERVER
[ ] Debian/Linux host prepared
[ ] Docker installed
[ ] Nginx installed
[ ] Repository deployed
[ ] Application secret generated
[ ] TLS material installed
[ ] LUMS image built
[ ] Persistent volume created
[ ] Hardened container deployed
[ ] Container runs as non-root
[ ] Root filesystem is read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Secret mounted read-only
[ ] Persistent data volume mounted
[ ] Application bound to 127.0.0.1:5050
[ ] Nginx HTTPS configured
[ ] HTTP redirects to HTTPS
[ ] TLS verified
[ ] Database initialized
[ ] SQLite integrity check passes
[ ] Migrations complete
```

---

# 167. Lista de comprobación final de instalación del cliente

```text
CLIENT
[ ] Supported Linux distribution
[ ] systemd available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher installed
[ ] Watcher version verified
[ ] Client configuration protected
[ ] Unique client token configured
[ ] TLS trust configured
[ ] Agent manual run succeeds
[ ] Initial report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Watcher timer enabled
[ ] Idle detection verified
[ ] Package inventory verified
[ ] Update detection verified
```

---

# 168. Lista de comprobación funcional final

```text
FUNCTIONALITY
[ ] Administrator login works
[ ] Operator login works
[ ] Viewer login works
[ ] Administrator RBAC verified
[ ] Operator RBAC verified
[ ] Viewer RBAC verified
[ ] Client authentication verified
[ ] Token rotation verified
[ ] Package search verified
[ ] Package installation verified
[ ] Package removal verified
[ ] Package update verified
[ ] System update path verified
[ ] Update jobs verified
[ ] Job result validation verified
[ ] Job recovery verified
[ ] Reboot detection verified
[ ] Audit logging verified
[ ] Logs contain no secrets
[ ] End-to-end reporting verified
[ ] End-to-end update execution verified
```

---

# 169. Lista de comprobación de seguridad final

```text
SECURITY
[ ] HTTPS enforced
[ ] Client Bearer authentication enabled
[ ] RBAC enforced server-side
[ ] CSRF protection enabled
[ ] Session protection enabled
[ ] Login rate limiting enabled
[ ] Password hashing enabled
[ ] Client token hashing enabled
[ ] Client token rotation available
[ ] Audit logging enabled
[ ] Secrets outside Git
[ ] Secrets outside Docker image
[ ] TLS private key protected
[ ] Docker root filesystem read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Container runs as non-root
[ ] Persistent data isolated in volume
[ ] Application port localhost-only
[ ] Firewall reviewed
[ ] Default Nginx site removed or controlled
[ ] Backup procedure defined
[ ] Restore procedure tested
```

---

# 170. Lista de comprobación de pruebas final

Ejecute la suite de pruebas automatizadas completa:

```bash
cd /opt/lums-public

./.venv-test/bin/pytest -q
```

La instalación solo debe considerarse completa cuando la suite de pruebas completa pase.

Luego verifique manualmente el tiempo de ejecución de producción:

```bash
sudo docker ps \
    --filter name=lums
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

```bash
curl -I \
    https://LUMS-SERVER/
```

```bash
sudo ss -lntp
```

---

# 171. Comprobación final de la documentación

Antes de declarar la instalación completa, verifique que la documentación coincide con el despliegue real.

Como mínimo, revise:

```text
install.md
security.md
troubleshooting.md
administration.md
docs/README.md
```

Las guías en inglés de la raíz son la referencia técnica. Es posible que las traducciones de `docs/locales/` todavía no incluyan todos los detalles técnicos.

La documentación no debe contener:

```text
old container commands
obsolete image names
obsolete RBAC rules
obsolete test counts
obsolete service paths
obsolete authentication mechanisms
real secrets
real client tokens
private keys
```

Si el despliegue cambia, actualice la documentación junto con la implementación.

---

# 172. Preparación para la versión

Una instalación exitosa no significa automáticamente que LUMS tenga una versión oficial.

El estado actual del proyecto separa deliberadamente:

```text
Working implementation
Security audit
Documentation review
Release preparation
Versioning
Git tag
GitHub Release
```

Una versión oficial de LUMS solo debe crearse después de que la implementación completa, la revisión de seguridad, la revisión de documentación y la validación final hayan sido completadas.

Hasta entonces, trate el repositorio como un proyecto en desarrollo activo.

---

# 173. Línea base operativa

La línea base documentada actual es:

```text
LUMS Server
    Docker
    Nginx
    HTTPS
    SQLite
    RBAC
    CSRF
    Audit Logging
    Hardened Container

LUMS Agent
    Version 1.7.0

LUMS Watcher
    Version 1.2.1

Database
    journal_mode=wal
    busy_timeout=5000
    synchronous=2
    foreign_keys=ON (application connections)

Container
    non-root
    read-only root filesystem
    CapDrop=ALL
    no-new-privileges
    localhost-only application port

Roles
    Administrator
    Operator
    Viewer
```

Esta línea base debe tratarse como el estado de referencia para la solución de problemas y el mantenimiento futuro.

---

# 174. Instalación completa

La instalación está completa cuando:

```text
Server
  │
  ├── HTTPS works
  ├── Authentication works
  ├── RBAC works
  ├── Database is healthy
  ├── Container is hardened
  └── Persistent storage is verified
       │
       ▼
Client
  │
  ├── Agent reports
  ├── Watcher executes
  ├── Package manager works
  ├── Jobs complete
  ├── Results are validated
  └── Recovery works
       │
       ▼
Operations
  │
  ├── Backup exists
  ├── Restore is understood
  ├── Troubleshooting documentation is available
  └── Security baseline is maintained
```

El principio operativo fundamental de LUMS es:

```text
Observe first.
Change second.
Verify third.
Document last.
```

Para los cambios de producción, extienda esto a:

```text
Backup
   ↓
Change
   ↓
Verify
   ↓
Document
```

Una instalación de LUMS siempre debe permanecer reproducible, auditable y recuperable.
