# LUMS

**Gestión de actualizaciones de Linux sin el ruido.**

## Primeros pasos

LUMS gestiona centralmente las actualizaciones de Linux. Un servidor muestra clientes, software instalado y actualizaciones disponibles. Un agente en cada sistema Linux gestionado realiza las acciones de paquetes aprobadas utilizando el gestor de paquetes de ese sistema. LUMS no reemplaza APT en Debian/Ubuntu ni pacman en Arch Linux.

**¿Solo utiliza una instalación existente de LUMS?** Abra la dirección proporcionada por su administrador e inicie sesión con su propia cuenta. Si falta una función, es posible que su cuenta no tenga permiso para usarla. Pida ayuda a su administrador; no comparta cuentas ni use un token de cliente como contraseña web.

**¿Instala u opera LUMS?** Comience con la [guía de instalación](<Instalación y actualizaciones.md>), luego lea la [guía de administración](<Administración y copias de seguridad.md>). Si algo sale mal, use la [guía de solución de problemas](<Solución de problemas.md>). También hay guías traducidas; su cobertura puede diferir de los originales técnicos en inglés. El [índice de documentación](../../README.md) muestra las versiones disponibles.

Una ejecución de prueba o una imagen Docker construida con éxito **no** es una instalación de producción. Un despliegue de producción también necesita HTTPS, un secreto de aplicación protegido, datos persistentes, copias de seguridad verificadas y un contenedor endurecido. No copie comandos de producción hasta haber verificado sus marcadores de posición y rutas de almacenamiento contra su propia instalación.

### Idiomas de la interfaz web

La interfaz web ofrece alemán, inglés (EE. UU. y Reino Unido), francés, español, chino simplificado, japonés, polaco, sueco, noruego bokmål y finlandés. Elija un idioma en la esquina superior derecha de la página de inicio de sesión. Si no elige uno, LUMS intenta usar el idioma del navegador; después de iniciar sesión, tiene prioridad un idioma guardado en su cuenta. Algunos textos técnicos o dinámicos pueden permanecer en su idioma original cuando no haya traducción disponible. Las guías en Markdown son independientes de la interfaz web y no se traducen automáticamente.

---

LUMS es un servidor de gestión de actualizaciones de Linux diseñado para proporcionar una gestión de software y actualizaciones controlada, auditable y segura para clientes Linux.

En lugar de depender de la actividad de actualización no controlada del lado del cliente, LUMS proporciona una capa de gestión central para el inventario de software, la detección de actualizaciones, las operaciones de paquetes, los trabajos de actualización, la supervisión de ejecución y el reporte de resultados.

LUMS está diseñado para entornos donde las actualizaciones deben ser **visibles, controladas, rastreables y recuperables**.

---

## ¿Qué es LUMS?

LUMS (**Linux Update Management Server**) consta de un servidor central y clientes Linux ligeros.

El servidor proporciona la interfaz de gestión, la API, la autenticación, la autorización, la gestión de trabajos, el registro de auditoría y el estado persistente.

El agente del lado del cliente realiza operaciones locales del gestor de paquetes y reporta los resultados al servidor.

La arquitectura básica es:

```text
                    ┌──────────────────────┐
                    │      Web Browser      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     LUMS Server      │
                    │                      │
                    │ Web UI / API         │
                    │ Authentication       │
                    │ RBAC                 │
                    │ Job Management       │
                    │ Audit Logging        │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         HTTPS / API
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────────┐             ┌─────────────────┐
      │   Linux Client  │             │   Linux Client  │
      │                 │             │                 │
      │ LUMS Agent      │             │ LUMS Agent      │
      │ Package Manager │             │ Package Manager │
      │ Watcher         │             │ Watcher         │
      └─────────────────┘             └─────────────────┘
```

---

## ¿Por qué LUMS?

Los sistemas Linux ya proporcionan excelentes herramientas de gestión de paquetes.

LUMS no intenta reemplazarlas.

En cambio, LUMS proporciona una capa de gestión alrededor de esas herramientas para que los administradores puedan responder centralmente preguntas como:

* ¿Qué clientes existen?
* ¿Qué software está instalado?
* ¿Qué actualizaciones están disponibles?
* ¿Qué paquetes deberían instalarse o eliminarse?
* ¿Qué trabajos de actualización están en ejecución?
* ¿Qué ocurrió durante una actualización?
* ¿Reportó el cliente el resultado con éxito?
* ¿Se requirió un reinicio?
* ¿Puede un trabajo interrumpido recuperarse de forma segura?
* ¿Quién inició una acción administrativa?

El objetivo no es ocultar el gestor de paquetes de Linux subyacente.

El objetivo es hacer que su operación sea **gestionable y auditable**.

---

## Funciones principales

### Gestión de clientes

LUMS mantiene clientes Linux registrados y su estado de autenticación.

Cada cliente recibe un token de autenticación individual.

Los tokens de cliente no se almacenan como credenciales en texto plano. El servidor almacena un resumen SHA-256 y valida la autenticación entrante del cliente contra ese resumen.

Los administradores pueden:

* registrar clientes
* deshabilitar clientes
* rotar tokens de cliente
* inspeccionar el estado de los clientes
* supervisar el reporte de los clientes

---

### Inventario de software

Los clientes reportan su software instalado al servidor LUMS.

El servidor almacena el inventario y lo expone a través de la interfaz de gestión.

La vista de software instalado está intencionalmente separada de la búsqueda de gestión de paquetes.

Esto permite a los administradores y usuarios de solo lectura inspeccionar el software instalado sin exponer automáticamente operaciones de gestión de paquetes.

---

### Inventario de actualizaciones

Los clientes determinan periódicamente si hay actualizaciones de paquetes disponibles.

El servidor almacena la información de actualizaciones reportada y la pone a disposición de los usuarios autorizados.

La información de actualizaciones puede usarse como base para trabajos de actualización controlados.

---

### Gestión de paquetes

LUMS proporciona operaciones de gestión de paquetes a través del agente del cliente.

Las operaciones de paquetes admitidas incluyen:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

La capa de gestión de paquetes abstrae el gestor de paquetes subyacente.

Las familias de gestores de paquetes admitidas actualmente son:

* **Debian / Ubuntu:** APT / dpkg
* **Arch Linux:** pacman

La búsqueda de paquetes también está disponible a través de LUMS.

Las solicitudes de búsqueda se envían al cliente de destino, se ejecutan con el gestor de paquetes local y se devuelven al servidor para su visualización.

---

### Trabajos de actualización

Las operaciones de actualización se representan como trabajos persistentes.

Un trabajo puede contener una o más operaciones de paquetes y mantiene un estado de ejecución en el servidor.

El ciclo de vida general es:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► SUCCESS
   │
   └──────────────► FAILED
```

Los resultados a nivel de paquete se rastrean de forma independiente para que los trabajos interrumpidos puedan recuperarse sin repetir innecesariamente operaciones que ya se completaron con éxito.

---

### Ejecución controlada

LUMS no ejecuta comandos de shell arbitrarios proporcionados por la interfaz web.

El servidor crea trabajos estructurados utilizando acciones y nombres de paquetes validados.

El agente del cliente asigna esas acciones a la operación apropiada del gestor de paquetes local.

Esto crea una frontera deliberada entre:

```text
Web UI
   ↓
API
   ↓
Validated Job
   ↓
Agent
   ↓
Package Manager
```

---

### Ejecución consciente de la inactividad

LUMS puede diferir la ejecución de actualizaciones mientras un cliente se considera activo.

El umbral de inactividad actual es de **300 segundos**.

Donde sea compatible, el agente utiliza la información de sesión/inactividad del sistema local a través de `loginctl`.

Si la detección de inactividad no está disponible, LUMS no finge que el cliente está inactivo.

Esta distinción es importante porque **un estado de inactividad desconocido no es lo mismo que un estado de inactividad confirmado**.

---

### Recuperación de trabajos

Los trabajos de actualización están diseñados para sobrevivir a interrupciones.

El servidor mantiene el estado persistente del trabajo y de los elementos de paquetes.

Durante la recuperación, los elementos de paquetes ya exitosos no se ejecutan innecesariamente de nuevo.

Esto proporciona un modelo de ejecución similar a un punto de control para operaciones con múltiples paquetes.

El objetivo es:

> **Recuperar el trabajo, no reiniciar ciegamente todo el trabajo.**

---

### Detección de reinicio

Algunas operaciones de paquetes pueden requerir un reinicio del sistema.

Por lo tanto, LUMS trata la detección de reinicio como parte del manejo del resultado de actualización en lugar de asumir que una salida exitosa del gestor de paquetes siempre significa que el sistema está completamente operativo.

El cliente reporta el requisito de reinicio detectado al servidor.

---

### Autenticación de clientes

La comunicación del cliente se autentica utilizando tokens por cliente.

Los tokens son:

* asignados individualmente
* rotables
* almacenados en el servidor solo como resúmenes SHA-256
* validados antes de aceptar reportes de clientes

La rotación de tokens permite a un administrador invalidar una credencial de cliente emitida previamente sin recrear el cliente.

---

### Panel de estado

El panel de estado autenticado en `/health` resume el estado de la base de datos, el estado de los informes de clientes, la visibilidad del almacenamiento de copias de seguridad y la telemetr?a de CPU y memoria cuando est? configurada. Es una vista operativa r?pida, no sustituye la comprobaci?n de los registros del contenedor, del proxy inverso, del host y de las copias de seguridad, ni la realizaci?n de una prueba de restauraci?n. Consulte [panel-estado-sistema.md](panel-estado-sistema.md).

---

### Alertas

LUMS incluye una API de gesti?n de alertas y un panel b?sico para los registros de alertas almacenados. Los administradores pueden crear y gestionar reglas, activar una alerta manualmente y reconocer, resolver o escalar manualmente una alerta activa. Las condiciones y los umbrales de las reglas se almacenan como configuraci?n; el servidor actual no los eval?a autom?ticamente frente a la telemetr?a. Las integraciones de notificaci?n (correo electr?nico, Slack, PagerDuty y webhooks gen?ricos) no est?n disponibles mediante la API, y la eliminaci?n masiva est? deshabilitada para preservar el historial de alertas. Consulte [Gesti?n de alertas](Gesti%C3%B3n%20de%20alertas.md) para conocer los l?mites implementados.

---

### Auditabilidad

Las acciones administrativas y relevantes para la seguridad se registran a través del sistema de registro de auditoría de LUMS.

La pista de auditoría está destinada a responder:

```text
¿Quién?
¿Qué?
¿Cuándo?
¿Contra qué objeto?
¿Con qué resultado?
```

Esto incluye operaciones sensibles a la seguridad como acciones relacionadas con la autenticación, gestión de clientes, gestión de usuarios y creación de trabajos de actualización.

---

## Principio de diseño

LUMS sigue un principio simple:

> **Hacer que la gestión de actualizaciones de Linux sea visible, controlada, recuperable y auditable — sin ocultar las herramientas de Linux subyacentes.**

## Arquitectura

LUMS separa la gestión, la ejecución y la persistencia en componentes claramente definidos.

El servidor es responsable de la orquestación y las políticas.

El cliente es responsable de la interacción con el sistema local.

El gestor de paquetes sigue siendo responsable de instalar, eliminar o actualizar software realmente.

Esta separación es intencional.

```text
Browser
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│                LUMS Server                │
│                                          │
│  Web UI                                  │
│  Authentication / Sessions               │
│  RBAC                                    │
│  API                                     │
│  Client Management                       │
│  Package Search                          │
│  Update Job Management                   │
│  Audit Logging                            │
│  SQLite Persistence                       │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Client API
                    ▼
┌──────────────────────────────────────────┐
│               LUMS Agent                  │
│                                          │
│  Authentication                          │
│  Inventory Reporting                     │
│  Update Detection                        │
│  Package Search                          │
│  Job Execution                           │
│  Result Reporting                        │
│  Reboot Detection                        │
│  Idle Detection                          │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Package Manager    │
          │                    │
          │ APT / dpkg         │
          │ pacman             │
          └────────────────────┘
```

---

## Componentes del servidor

El servidor LUMS proporciona la capa de gestión central.

### Aplicación web

La aplicación web proporciona la interfaz administrativa para:

* gestión de clientes
* inventario de software
* información de actualizaciones
* trabajos de actualización
* gestión de paquetes
* historial de actualizaciones
* gestión de usuarios
* mantenimiento del sistema

La interfaz respeta el rol RBAC del usuario actual.

Por lo tanto, la visibilidad del frontend se adapta a los permisos del usuario, pero la autorización siempre se aplica también en el servidor.

---

### API

La API conecta la interfaz web y los clientes Linux con la lógica de aplicación del servidor.

Maneja operaciones como:

* registro y gestión de clientes
* reportes de clientes
* búsquedas de paquetes
* resultados de búsqueda de paquetes
* trabajos de actualización
* resultados de trabajos
* gestión de usuarios
* eventos de auditoría

Los puntos de conexión de la API validan su entrada antes de realizar operaciones que modifican el estado.

---

### Autenticación y sesiones

Los usuarios administrativos se autentican a través de la aplicación web LUMS.

Las sesiones son controladas por el servidor y admiten revocación explícita de sesiones.

La seguridad de autenticación incluye:

* hash de contraseñas usando Argon2
* gestión de sesiones
* revocación de sesiones
* limitación de la tasa de inicio de sesión
* protección CSRF
* autorización basada en roles

La autenticación de clientes es independiente de la autenticación administrativa.

---

### RBAC

LUMS combina plantillas de roles con permisos por usuario. Las plantillas Administrator, Operator y Viewer proporcionan conjuntos iniciales de permisos que pueden personalizarse para cada cuenta.

La autorización se aplica en el servidor utilizando los permisos almacenados de la cuenta.

El frontend además oculta funcionalidades que los permisos del usuario no permiten.

Esto significa que ocultar un botón nunca se trata como una frontera de seguridad.

---

### Persistencia SQLite

LUMS utiliza SQLite para el estado persistente de la aplicación.

La base de datos almacena información como:

* usuarios
* sesiones
* clientes
* estado de autenticación de clientes
* inventario de software
* actualizaciones disponibles
* trabajos de actualización
* resultados de trabajos a nivel de paquete
* solicitudes y resultados de búsqueda de paquetes
* información de auditoría

La aplicación habilita explícitamente la aplicación de claves foráneas SQLite para las conexiones a la base de datos.

La línea base actual de SQLite en producción es:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS usa el modo WAL de SQLite en la configuración de producción actual.

---

## Arquitectura del contenedor

El servidor LUMS se despliega como un contenedor Docker endurecido.

El contenedor de la aplicación se trata intencionalmente como desechable.

El estado persistente de la aplicación se almacena en el volumen Docker dedicado:

```text
lums-data
```

El contenedor de producción utiliza un sistema de archivos raíz de solo lectura.

Las ubicaciones escribibles están deliberadamente limitadas a las rutas de almacenamiento persistente y de tiempo de ejecución requeridas.

La línea base de seguridad de producción incluye:

```text
sistema de archivos raíz de solo lectura
todas las capacidades de Linux eliminadas
no-new-privileges
/tmp restringido
/run restringido
montaje de secreto de solo lectura
volumen de datos persistente dedicado
usuario de aplicación no root
```

La aplicación se expone internamente a través de:

```text
127.0.0.1:5050
```

El acceso HTTPS externo se proporciona a través del proxy inverso.

---

## Componentes persistentes y desechables

LUMS separa el estado persistente de los componentes de tiempo de ejecución reemplazables.

```text
Persistente
├── Base de datos SQLite
├── estado de clientes
├── estado de usuarios
├── estado de trabajos
└── estado de auditoría

Desechable
├── Contenedor Docker
├── proceso de aplicación
└── estado de tiempo de ejecución generado
```

Por lo tanto, reemplazar el contenedor de la aplicación no elimina inherentemente la base de datos de LUMS.

Esta separación es importante para actualizaciones y recuperación.

---

## Arquitectura del cliente

El cliente Linux consta de varios componentes que cooperan.

### LUMS Agent

El agente es responsable de la interacción con el servidor LUMS y el sistema Linux local.

Versión actual del agente:

```text
1.7.0
```

El agente maneja:

* autenticación
* recopilación de inventario
* detección de actualizaciones
* búsqueda de paquetes
* operaciones de paquetes
* ejecución de trabajos de actualización
* reporte de resultados
* detección de reinicio
* manejo del estado de inactividad

---

### Capa del gestor de paquetes

La capa del gestor de paquetes proporciona una abstracción controlada alrededor del gestor de paquetes nativo de Linux.

El agente no requiere que LUMS reemplace el gestor de paquetes.

En cambio:

```text
LUMS Action
     │
     ▼
Package Manager Abstraction
     │
     ├── Debian / Ubuntu → APT / dpkg
     │
     └── Arch Linux      → pacman
```

Esto mantiene el manejo de paquetes específico de la distribución dentro del cliente.

---

### Execution Watcher

El watcher supervisa la ejecución de trabajos de actualización en el cliente.

Versión actual del watcher:

```text
1.2.1
```

El watcher trabaja junto con el agente y el estado de los trabajos del servidor.

Su propósito es garantizar que los trabajos que se espera que se ejecuten no permanezcan indefinidamente sin procesar.

---

## Ruta de reporte

El reporte normal del cliente sigue esta dirección:

```text
Linux Client
    │
    │ inventory / update information
    ▼
LUMS API
    │
    ▼
SQLite
    │
    ▼
Web UI
```

Por ejemplo, una verificación de actualizaciones realizada por el cliente produce información que se reporta al servidor y se almacena como el estado de actualización actual del cliente.

El navegador no consulta directamente el gestor de paquetes del cliente.

---

## Ruta de búsqueda de paquetes

La búsqueda de paquetes sigue un flujo de solicitud/respuesta diferente:

```text
Browser
   │
   │ search request
   ▼
LUMS Server
   │
   │ package-search request
   ▼
Linux Client
   │
   │ APT / pacman search
   ▼
Linux Client
   │
   │ search result
   ▼
LUMS Server
   │
   ▼
Browser
```

Por lo tanto, el servidor no necesita mantener un índice completo de repositorios remotos de paquetes para cada cliente.

La búsqueda se realiza utilizando el entorno de gestión de paquetes del propio cliente.

---

## Ruta de ejecución de actualizaciones

Un trabajo de actualización sigue la arquitectura general:

```text
Browser
   │
   │ create job
   ▼
LUMS API
   │
   │ validate request
   ▼
SQLite
   │
   │ persistent job
   ▼
Linux Client
   │
   │ execute action
   ▼
APT / dpkg / pacman
   │
   │ result
   ▼
Linux Client
   │
   │ validated result
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Browser
```

Esto crea la cadena de ejecución central de LUMS:

> **Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI**

---

## Reclamo atómico de trabajos

Los trabajos de actualización son objetos persistentes del servidor.

Antes de la ejecución, el agente debe obtener un trabajo que sea elegible para ejecución.

El reclamo de trabajos se realiza de forma atómica para que el mismo trabajo pendiente no sea reclamado sin intención por múltiples rutas de ejecución.

Esto es especialmente importante cuando hay temporizadores, reintentos, recuperación o múltiples procesos del lado del cliente involucrados.

---

## Ejecución de trabajos

El servidor crea trabajos estructurados.

El agente del cliente interpreta las acciones de trabajo admitidas y ejecuta la operación local correspondiente.

Las acciones de paquetes admitidas son:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Los nombres de paquetes se validan antes de crear un trabajo de paquete.

El agente no trata los nombres de paquetes como fragmentos de shell arbitrarios.

---

## Abstracción del gestor de paquetes

Las operaciones de paquetes se implementan deliberadamente detrás de una abstracción del gestor de paquetes.

Esto mantiene el modelo de trabajo de LUMS de nivel superior independiente de los comandos específicos de la distribución.

Por ejemplo:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

El mismo principio se aplica a la eliminación y a las actualizaciones de paquetes.

---

## Debian / Ubuntu

En sistemas de la familia Debian, LUMS utiliza las herramientas nativas APT/dpkg.

Las responsabilidades típicas incluyen:

* búsqueda de paquetes
* consulta de metadatos de paquetes
* instalación de paquetes
* eliminación de paquetes
* actualizaciones de paquetes
* actualizaciones del sistema
* detección de actualizaciones

El agente de LUMS no reemplaza APT.

Proporciona orquestación controlada alrededor de él.

---

## Arch Linux

En sistemas Arch Linux, LUMS utiliza el gestor de paquetes nativo pacman.

Las responsabilidades típicas incluyen:

* búsqueda de paquetes
* consulta de metadatos de paquetes
* instalación de paquetes
* eliminación de paquetes
* actualizaciones de paquetes
* actualizaciones del sistema
* detección de actualizaciones

El comportamiento específico de la distribución permanece dentro de la capa del gestor de paquetes.

---

## Búsqueda de paquetes

La búsqueda de paquetes está separada del inventario de software instalado.

Esta distinción es importante:

```text
Installed Software
        │
        └── What is already installed?

Package Management Search
        │
        └── What package can the client currently find?
```

Los resultados de búsqueda pueden contener información de paquetes como:

* nombre del paquete
* versión
* descripción
* información del repositorio cuando esté disponible

Los resultados de búsqueda se devuelven al servidor LUMS y se muestran en la interfaz de gestión de paquetes.

---

## Permisos de gestión de paquetes

La gestión de paquetes es una operación privilegiada.

El modelo de permisos actual es:

```text
Administrator → allowed
Operator      → allowed
Viewer        → not allowed
```

Un Viewer aún puede inspeccionar el software instalado.

La interfaz de gestión de paquetes está oculta para los Viewers, y los puntos de conexión de mutación correspondientes del servidor aplican la autorización de forma independiente.

---

## Manejo de resultados de actualización

LUMS trata el resultado de una operación de actualización como estado estructurado en lugar de simplemente mostrar la salida de comando en bruto.

La información relevante puede incluir:

* éxito o fallo
* resultado a nivel de paquete
* estado de ejecución
* información de error
* requisito de reinicio
* marcas de tiempo de finalización

Esto permite al servidor mantener un historial de actualizaciones significativo.

---

## Detección de reinicio

Después de las operaciones de paquetes, el cliente verifica si la operación indica que se requiere un reinicio.

El resultado se reporta al servidor como parte del resultado del trabajo.

Por lo tanto, un requisito de reinicio permanece asociado con la operación de actualización en lugar de perderse en una sesión de terminal del lado del cliente.

---

## Frontera de autenticación del cliente

La API del cliente utiliza un mecanismo de autenticación separado de las sesiones web administrativas.

```text
Administrative User
        │
        ▼
 Web Authentication
        │
        ▼
    LUMS Server

Linux Client
        │
        ▼
 Client Token
        │
        ▼
    LUMS Server
```

Esta separación evita que las sesiones administrativas del navegador y las credenciales del cliente se conviertan en mecanismos de autenticación intercambiables.

---

## Pista de auditoría

Las acciones relevantes para la seguridad y administrativas son registradas por el sistema de auditoría del servidor.

La pista de auditoría complementa el registro normal de la aplicación.

El registro responde preguntas sobre el comportamiento de la aplicación.

El registro de auditoría además registra acciones administrativas importantes y su contexto.

Esta distinción es útil al investigar cambios en clientes, usuarios, estado de autenticación o trabajos de actualización.

---

## Principio operativo

LUMS separa deliberadamente:

```text
Management
     │
     ▼
Policy / Authorization
     │
     ▼
Job
     │
     ▼
Client Execution
     │
     ▼
Native Package Manager
```

Cada capa tiene una responsabilidad definida.

El servidor gestiona.

El agente ejecuta.

El gestor de paquetes realiza el cambio real del sistema.

El resultado viaja de vuelta a través de la misma cadena controlada.

## Control de acceso basado en roles

LUMS utiliza tres roles administrativos:

```text
Administrator
Operator
Viewer
```

La autorización se aplica en el servidor.

El frontend además adapta la interfaz visible a los permisos del usuario, pero la visibilidad del frontend nunca se considera una frontera de seguridad.

### Administrator

Los administradores tienen acceso a:

* ver clientes
* ver software instalado
* ver actualizaciones disponibles
* crear y ejecutar trabajos de actualización
* ver el historial de actualizaciones
* usar la gestión de paquetes
* realizar mantenimiento del sistema
* crear y deshabilitar clientes
* rotar tokens de cliente
* crear y gestionar usuarios
* gestionar roles y acceso de usuarios

### Operator

Los operadores tienen acceso a:

* ver clientes
* ver software instalado
* ver actualizaciones disponibles
* crear y ejecutar trabajos de actualización
* ver el historial de actualizaciones
* usar la gestión de paquetes
* realizar mantenimiento del sistema

Los operadores no tienen acceso a:

* gestión de usuarios
* administración de roles
* creación o deshabilitación de clientes
* rotación de tokens de cliente

### Viewer

Los Viewers tienen acceso de solo lectura a:

* clientes
* software instalado

Las siguientes funcionalidades no están disponibles para los Viewers:

* gestión de actualizaciones disponibles
* trabajos de actualización
* historial de actualizaciones
* gestión de paquetes
* mantenimiento del sistema
* otras operaciones administrativas que modifican el estado

El servidor aplica estas restricciones de forma independiente.

---

## Gestión de usuarios

LUMS proporciona gestión de usuarios a las cuentas con el permiso `users.manage`.

Los usuarios con este permiso pueden crear cuentas usando una plantilla de rol y luego asignar permisos individualmente o aplicar explícitamente esa plantilla. Las cuentas nuevas comienzan sin permisos; el editor de permisos se abre después de la creación. Los gestores de usuarios también pueden guardar notas administrativas privadas que no son visibles para el propietario de la cuenta.

Los administradores con `backups.manage` pueden crear copias de seguridad de base de datos `.db` o `.db.gz` validadas en un directorio configurado en el servidor y elegir una subcarpeta segura dentro de esa ubicación montada. Consulte [`administration.md`](<Administración y copias de seguridad.md>) y la guía de restauración en Markdown integrada en la aplicación para la configuración de almacenamiento de Docker y la recuperación.

Las contraseñas de usuario se almacenan usando hash de contraseña Argon2 en lugar de texto plano o cifrado reversible.

Las operaciones de gestión de usuarios están protegidas por:

* autenticación
* autorización basada en permisos
* protección CSRF
* validación de entrada
* comprobaciones de usuarios duplicados
* registro de auditoría

La interfaz de gestión de usuarios no se expone sin `users.manage`.

---

## Seguridad de sesiones

La autenticación administrativa utiliza manejo de sesiones del lado del servidor.

La seguridad de sesiones incluye:

* estado de sesión autenticado
* revocación de sesiones
* protección CSRF para solicitudes que modifican el estado
* limitación de la tasa de inicio de sesión
* aplicación de cuentas deshabilitadas
* comprobaciones de roles

Revocar una sesión invalida el estado autenticado correspondiente en lugar de simplemente ocultar la interfaz de usuario.

---

## Limitación de la tasa de inicio de sesión

Los intentos de inicio de sesión fallidos repetidos están sujetos a limitación progresiva de la tasa.

Los umbrales actuales son:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

El estado relevante se persiste en SQLite.

La autenticación exitosa borra el estado de fallo aplicable.

Esto evita que un simple reinicio de la aplicación se utilice para eludir la protección de inicio de sesión.

---

## Seguridad de tokens de cliente

Cada cliente registrado tiene su propio token de autenticación.

El servidor almacena el token como un resumen SHA-256.

El token original no es necesario para la validación normal del servidor.

La rotación de tokens permite a los administradores invalidar una credencial existente y emitir una de reemplazo.

Esto crea un ciclo de vida claro:

```text
Create
  │
  ▼
Use
  │
  ▼
Rotate
  │
  ▼
Old token invalid
```

---

## Seguridad de la API

LUMS valida la entrada de la API antes de realizar operaciones que modifican el estado.

Los controles de seguridad incluyen:

* autenticación
* autorización por permisos de usuario
* protección CSRF cuando corresponda
* validación de entrada
* validación de nombres de paquetes
* acciones de trabajo estructuradas
* consultas de base de datos parametrizadas
* manejo controlado de errores

La aplicación no utiliza nombres de paquetes proporcionados por el usuario como comandos de shell sin restricciones.

---

## Protección contra inyección SQL

Las operaciones de base de datos utilizan sentencias SQL parametrizadas.

Los valores controlados por el usuario no se concatenan directamente en las consultas SQL.

Esto se aplica a áreas como:

* autenticación
* gestión de clientes
* gestión de usuarios
* búsquedas de paquetes
* trabajos de actualización
* datos de auditoría
* reporte de resultados

El objetivo es mantener los valores de datos separados de las instrucciones SQL.

---

## Línea base de seguridad de SQLite

La configuración actual de SQLite en producción es:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

La aplicación de claves foráneas está habilitada explícitamente por la aplicación para las conexiones a la base de datos.

La configuración actual utiliza el modo WAL.

La base de datos se almacena en el volumen Docker persistente en lugar de dentro del sistema de archivos desechable del contenedor de la aplicación.

---

## Recuperación de trabajos y puntos de control

LUMS trata los trabajos de actualización como máquinas de estado persistentes.

Un trabajo con múltiples paquetes puede contener varias operaciones individuales de paquetes.

Cada elemento de paquete puede alcanzar su propio estado de resultado.

Si la ejecución se interrumpe, la recuperación puede distinguir entre:

```text
already successful
        │
        └── do not unnecessarily repeat

not completed
        │
        └── eligible for recovery
```

Esto reduce el riesgo de repetir ciegamente operaciones de paquetes completadas después de una interrupción.

---

## Ejecución controlada de actualizaciones

LUMS limita deliberadamente las acciones que se pueden solicitar a través de la API de trabajos de actualización.

Las acciones admitidas son:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

El servidor valida la acción y la información relevante del paquete antes de crear el trabajo.

Luego, el agente asigna la acción estructurada a la operación apropiada del gestor de paquetes.

Esto evita convertir el sistema de actualizaciones en un mecanismo genérico de ejecución de comandos remotos.

---

## Operaciones de paquetes

Las operaciones de paquetes se ejecutan a través del gestor de paquetes nativo del cliente.

### Instalación

Un nombre de paquete validado se pasa a la abstracción del gestor de paquetes para la instalación.

### Eliminación

Un nombre de paquete validado se pasa a la abstracción del gestor de paquetes para la eliminación.

### Actualización de paquete

Un paquete específico se puede actualizar cuando el cliente lo reporta como una actualización disponible.

### Actualización del sistema

La operación de actualización del sistema delega el proceso de actualización al gestor de paquetes nativo.

Todas las operaciones devuelven resultados estructurados al servidor LUMS.

---

## Seguridad del gestor de paquetes

LUMS trata el gestor de paquetes como un componente local privilegiado.

Por lo tanto, el agente no intenta emular el comportamiento del gestor de paquetes por sí mismo.

En cambio,:

1. valida la operación solicitada
2. selecciona la implementación apropiada del gestor de paquetes
3. ejecuta la operación controlada
4. captura el resultado
5. reporta el resultado al servidor

El comportamiento específico de la distribución permanece aislado dentro de la capa del gestor de paquetes.

---

## Manejo de reinicios

Algunas operaciones de paquetes pueden requerir un reinicio.

LUMS registra los requisitos de reinicio como parte de los resultados de los trabajos de actualización.

Esto permite a los administradores distinguir entre:

```text
Update completed
```

y:

```text
Update completed
Reboot required
```

Por lo tanto, el requisito de reinicio forma parte del estado operativo en lugar de tratarse como una notificación no relacionada.

---

## Registro de auditoría

LUMS mantiene una pista de auditoría de la aplicación para acciones administrativas y relevantes para la seguridad importantes.

Los ejemplos incluyen:

* eventos relacionados con la autenticación
* gestión de clientes
* operaciones de tokens
* gestión de usuarios
* creación de trabajos de actualización
* cambios de estado sensibles a la seguridad

El registro de auditoría es independiente del registro de diagnóstico ordinario.

Los registros de diagnóstico ayudan a solucionar problemas de la aplicación.

Los registros de auditoría proporcionan un historial administrativo de las acciones relevantes.

---

## Endurecimiento de seguridad

El despliegue actual incluye múltiples capas de endurecimiento.

### Endurecimiento del contenedor

El contenedor de producción utiliza:

* ejecución de aplicación no root
* sistema de archivos raíz de solo lectura
* capacidades de Linux eliminadas
* `no-new-privileges`
* sistemas de archivos temporales restringidos
* montaje de secreto de solo lectura
* volumen de datos persistente dedicado

### Endurecimiento de red

El contenedor de la aplicación está vinculado al loopback en el host:

```text
127.0.0.1:5050
```

Por lo tanto, el puerto de la aplicación no está expuesto directamente como servicio LAN.

El acceso externo se maneja a través del proxy inverso HTTPS.

El firewall no expone el puerto interno de la aplicación.

### Seguridad del transporte

El acceso administrativo se proporciona a través de HTTPS.

El proxy inverso maneja la terminación TLS externa.

Las solicitudes HTTP se redirigen a HTTPS.

### Secretos y configuración

Las credenciales sensibles de tiempo de ejecución se mantienen fuera del árbol de código fuente de la aplicación.

El secreto de producción se monta en el contenedor como un archivo de secreto de solo lectura.

Las reglas del repositorio y del contexto de construcción de Docker evitan que artefactos comunes de copias de seguridad, secretos, bases de datos y certificados entren sin intención en el contexto de construcción de la imagen.

### Seguridad de dependencias y construcción

Las dependencias de Python de producción están fijadas.

La imagen base de Python de producción está fijada por digest.

El contexto de construcción de Docker está restringido a través de `.dockerignore`.

Estos controles mejoran la reproducibilidad de la construcción y reducen la inclusión accidental de archivos sensibles.

---

## Estado de la auditoría de seguridad

La revisión de seguridad de LUMS ha cubierto las siguientes áreas:

* aplicación de claves foráneas SQLite
* configuración de tiempo de ejecución de SQLite
* manejo de tiempos de espera y procesos de actualización
* limitación de la tasa de inicio de sesión
* validación de entrada de la API
* revocación de sesiones
* rotación de tokens de cliente
* manejo de IP sin conexión
* recuperación de trabajos y puntos de control
* robustez de APT
* detección de reinicio en Arch
* validación de resultados unitarios y de API
* pruebas de simulación
* integración continua
* registro de aplicación y auditoría
* versionado y manejo de versiones
* RBAC
* seguridad de sesiones y CSRF
* seguridad de credenciales
* seguridad de dependencias y construcción
* endurecimiento de Docker/contenedor
* secretos y protección del contexto de construcción
* seguridad de HTTP/transporte
* permisos de sistema de archivos/tiempo de ejecución
* exposición de red
* higiene de artefactos del repositorio

La revisión de la documentación forma parte del mantenimiento continuo; esta guía no registra una fase del proyecto ligada a una rama ni un estado de lanzamiento en tiempo real.

---

## Pruebas y CI

LUMS incluye pruebas automatizadas que cubren el comportamiento principal de la aplicación y los controles de seguridad.

Ejecute la suite de pruebas completa desde la raíz del repositorio:

```bash
./.venv-test/bin/pytest -q
```

El número de pruebas cambia con el tiempo. El resultado requerido es que la suite completa termine con éxito sin fallos. La suite de pruebas incluye cobertura para áreas como:

* autenticación
* RBAC
* gestión de clientes
* gestión de usuarios
* búsqueda de paquetes
* trabajos de actualización
* validación de resultados de trabajos
* comportamiento de seguridad
* comportamiento de la API

La integración continua ejecuta la suite de pruebas automatizadas antes de que los cambios se consideren listos.

Se requiere una ejecución de pruebas exitosa, pero las pruebas son solo una parte del proceso de versión.

El proceso de versión también requiere:

```text
Implementation
    ↓
Security Review
    ↓
Documentation Review
    ↓
Full Test Suite
    ↓
CI
    ↓
Version
    ↓
Git Tag
    ↓
GitHub Release
```

---

## Estado de desarrollo

LUMS está actualmente en desarrollo activo.

La arquitectura central de gestión, el modelo de ejecución del cliente, la gestión de paquetes, el RBAC, el endurecimiento de seguridad y los mecanismos de recuperación están implementados.

El proyecto no se considera intencionalmente una versión terminada solo porque la aplicación sea funcional.

La preparación para la versión también requiere que la documentación circundante y los procedimientos operativos describan el mismo sistema actual.

Por eso la consistencia de la documentación se trata como parte del proceso de ingeniería y no como una idea de último momento.

## Sistemas compatibles

LUMS está diseñado para gestionar sistemas Linux utilizando gestores de paquetes nativos compatibles.

### Debian / Ubuntu

Pila de gestión de paquetes compatible:

```text
APT
dpkg
```

El cliente utiliza las herramientas nativas de gestión de paquetes de Debian para:

* inventario de paquetes
* detección de actualizaciones
* búsqueda de paquetes
* instalación de paquetes
* eliminación de paquetes
* actualizaciones de paquetes
* actualizaciones del sistema

### Arch Linux

Pila de gestión de paquetes compatible:

```text
pacman
```

El cliente utiliza las herramientas nativas de gestión de paquetes de Arch para:

* inventario de paquetes
* detección de actualizaciones
* búsqueda de paquetes
* instalación de paquetes
* eliminación de paquetes
* actualizaciones de paquetes
* actualizaciones del sistema

---

## Requisitos del cliente

Un cliente Linux gestionado requiere:

* una distribución Linux compatible
* el agente LUMS
* conectividad de red con el servidor LUMS
* un token de cliente registrado
* un gestor de paquetes nativo funcional
* systemd para los componentes de ejecución basados en temporizador/servicio

El cliente no requiere que el servidor LUMS acceda directamente a su base de datos de paquetes.

El cliente realiza operaciones locales de paquetes y reporta los resultados al servidor.

---

## Pila tecnológica

### Servidor

* Python
* Flask
* Gunicorn
* SQLite
* HTML
* CSS
* JavaScript
* Nginx
* Docker

### Autenticación y seguridad

* hash de contraseñas Argon2
* sesiones del lado del servidor
* protección CSRF
* plantillas de roles con permisos por usuario
* resúmenes SHA-256 de tokens de cliente
* HTTPS
* registro de auditoría

### Cliente

* Python
* systemd
* APT / dpkg
* pacman
* `loginctl` donde la información de estado de inactividad esté disponible

---

## Estructura del proyecto

El repositorio está organizado en componentes separados de servidor, cliente, frontend y pruebas.

Una estructura simplificada es:

```text id="1rq7v7"
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   └── ...
│
├── tests/
│   ├── test_rbac.py
│   ├── test_package_search.py
│   ├── test_job_result.py
│   └── ...
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
└── documentation
```

La disposición exacta del repositorio puede evolucionar a medida que LUMS se desarrolle.

La separación arquitectónica entre servidor, agente, abstracción del gestor de paquetes, frontend y pruebas es intencional.

---

## Aplicación del servidor

La aplicación Flask proporciona la API central de LUMS y la interfaz web.

Sus responsabilidades incluyen:

* autenticación
* autorización
* manejo de sesiones
* gestión de clientes
* gestión de usuarios
* inventario de software
* inventario de actualizaciones
* búsqueda de paquetes
* trabajos de actualización
* manejo de resultados de trabajos
* registro de auditoría
* persistencia de base de datos

La aplicación es servida por Gunicorn dentro del contenedor.

Nginx proporciona el punto de entrada HTTPS externo.

---

## Agente

El agente LUMS se instala directamente en los clientes Linux gestionados.

Versión actual del agente:

```text id="w8p4wz"
1.7.0
```

El agente es responsable de la parte del lado del cliente de la cadena de ejecución de LUMS.

Sus responsabilidades incluyen:

* reportar el estado del cliente
* recopilar el software instalado
* detectar actualizaciones disponibles
* buscar paquetes
* ejecutar operaciones de paquetes
* reportar resultados de trabajos
* detectar requisitos de reinicio
* manejar información de estado de inactividad
* participar en la recuperación de trabajos

El agente no proporciona un shell remoto sin restricciones.

---

## Capa del gestor de paquetes

La implementación del gestor de paquetes aísla el comportamiento específico de la distribución del resto del agente.

Conceptualmente:

```text id="zq8xq3"
Agent
  │
  ▼
Package Manager Interface
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

Esto permite que el sistema de trabajos de actualización de nivel superior trabaje con operaciones estructuradas sin necesidad de conocer cada comando específico de la distribución.

---

## Watcher

El watcher de ejecución de LUMS supervisa los trabajos que se espera que se ejecuten en el cliente.

Versión actual del watcher:

```text id="7k6w3s"
1.2.1
```

El watcher opera junto con el agente y el estado de los trabajos del servidor.

Esta arquitectura permite a LUMS detectar situaciones de ejecución donde un trabajo permanece pendiente o requiere atención de otro modo.

---

## Integración con systemd

El cliente utiliza systemd para la ejecución programada y controlada.

Los componentes relevantes incluyen unidades de servicio y temporizador para:

* reporte del cliente
* detección de actualizaciones
* ejecución/supervisión de trabajos

Esto proporciona una ejecución predecible sin requerir un proceso en primer plano que se ejecute continuamente para cada operación periódica.

El agente del cliente también se puede ejecutar manualmente durante la instalación y la solución de problemas.

---

## Ejecución consciente de la inactividad

La ejecución consciente de la inactividad está diseñada para reducir la interferencia con los usuarios activos.

El umbral de inactividad actual es:

```text id="g8v0lq"
300 seconds
```

El cliente determina el estado de inactividad utilizando la información de sesión local disponible.

Donde sea compatible, se utiliza `loginctl`.

El agente distingue entre:

```text id="6v3m4k"
confirmed idle
active
idle state unavailable
```

Un estado de inactividad no disponible no se interpreta silenciosamente como inactivo.

Esto hace que la decisión de ejecución sea explícita y diagnosticable.

---

## Ciclo de vida de los trabajos de actualización

El ciclo de vida completo de un trabajo de actualización se puede representar como:

```text id="h4d9kv"
Create
  │
  ▼
Validate
  │
  ▼
Persist
  │
  ▼
Claim
  │
  ▼
Execute
  │
  ├──────────────► SUCCESS
  │
  ├──────────────► FAILED
  │
  └──────────────► RECOVERY
                         │
                         ▼
                      Execute
```

Un trabajo se persiste antes de la ejecución.

Esto significa que el servidor conserva el conocimiento de la operación prevista incluso si el cliente o la aplicación se interrumpen.

---

## Tipos de trabajos

LUMS admite actualmente acciones de actualización estructuradas que incluyen:

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Estas acciones están limitadas intencionalmente.

LUMS es un sistema de gestión de actualizaciones, no un framework de comandos remotos de propósito general.

---

## Estado del trabajo a nivel de paquete

Los trabajos que contienen múltiples paquetes pueden rastrear el progreso a nivel de paquete.

Por ejemplo:

```text id="v9w1sh"
Job #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

Por lo tanto, la recuperación puede operar sobre las porciones incompletas del trabajo en lugar de repetir ciegamente las operaciones de paquetes exitosas.

---

## Recuperación de trabajos

La recuperación está diseñada en torno a puntos de control persistentes.

El servidor mantiene el estado del trabajo.

El cliente reporta resultados a nivel de paquete.

Si la ejecución se interrumpe, el servidor puede determinar qué trabajo ya se ha completado y qué trabajo sigue siendo elegible para recuperación.

El principio de recuperación previsto es:

> **Continuar desde el estado conocido en lugar de asumir que no ocurrió nada.**

---

## Validación de resultados

Los resultados de los trabajos del cliente se validan antes de aceptarse en el estado persistente del servidor.

Esto protege el estado del trabajo de envíos de resultados malformados o incompletos.

La validación se aplica a campos relevantes como:

* identidad del trabajo
* estado de ejecución
* datos de resultado de paquetes
* información de error
* información de reinicio

Por lo tanto, la capa de procesamiento de resultados actúa como otra frontera entre un cliente autenticado y el estado persistente del servidor.

---

## Gestión de usuarios

La gestión de usuarios requiere el permiso `users.manage`.

Los usuarios autorizados pueden crear usuarios a partir de una plantilla de rol y personalizar los permisos individuales asignados a cada cuenta.

Los roles actuales son:

```text id="2xqv79"
Administrator
Operator
Viewer
```

Las acciones de gestión de usuarios están autenticadas, verificadas por permisos, validadas, protegidas contra CSRF cuando corresponda y registradas en la pista de auditoría.

---

## Gestión de clientes

Los administradores pueden gestionar clientes registrados.

Las funciones de gestión de clientes incluyen:

* registro
* deshabilitación
* rotación de tokens
* inspección del estado del cliente

La autenticación de clientes es independiente para cada cliente registrado.

Deshabilitar un cliente le impide continuar la comunicación autenticada normal con el servidor.

---

## Historial de actualizaciones

LUMS mantiene el estado persistente de los trabajos de actualización para que las operaciones completadas y fallidas sigan siendo visibles después de la ejecución.

Los usuarios autorizados pueden inspeccionar el historial de operaciones de actualización según su rol.

El historial está destinado a proporcionar contexto operativo en lugar de simplemente mostrar el último inventario de paquetes.

---

## Auditabilidad

LUMS mantiene dos formas relacionadas pero distintas de información operativa:

### Registros de aplicación

Se utilizan principalmente para:

* diagnóstico
* errores
* comportamiento de tiempo de ejecución
* solución de problemas

### Registros de auditoría

Se utilizan principalmente para:

* acciones administrativas
* eventos relevantes para la seguridad
* cambios en el estado importante
* responsabilidad

Mantener estos conceptos separados facilita la solución de problemas y la revisión administrativa.

---

## Estrategia de pruebas

La suite de pruebas de LUMS cubre múltiples capas de la aplicación.

### Autenticación

Las pruebas cubren el comportamiento de autenticación, el manejo de sesiones y los controles de seguridad.

### RBAC

Las pruebas verifican que:

* los administradores pueden realizar acciones administrativas
* los operadores reciben sus funciones de gestión permitidas
* los viewers permanecen en solo lectura

### Gestión de paquetes

Las pruebas cubren el comportamiento de búsqueda de paquetes y el manejo de la API relacionado con la gestión de paquetes.

### Trabajos de actualización

Las pruebas cubren:

* creación de trabajos
* validación
* transiciones de estado
* manejo de resultados
* comportamiento de recuperación

### Seguridad

Las pruebas cubren el comportamiento de la aplicación sensible a la seguridad y los casos de regresión.

### Suite completa

Ejecute la suite de pruebas completa desde la raíz del repositorio:

```bash
./.venv-test/bin/pytest -q
```

El número de pruebas cambia a medida que el proyecto evoluciona; confíe en el resultado del comando, no en un número fijo impreso en este documento.

---

## Integración continua

El proyecto utiliza integración continua para ejecutar comprobaciones automatizadas sobre los cambios.

La tubería de CI ayuda a detectar regresiones antes de que los cambios se consideren listos para la versión.

Por lo tanto, el flujo de desarrollo es:

```text id="v3n9k8"
Change
  ↓
Test
  ↓
Security Review
  ↓
Documentation Review
  ↓
CI
  ↓
Release Preparation
```

Una ejecución de CI exitosa no reemplaza la revisión manual de seguridad o documentación.

---

## Documentación

LUMS mantiene documentación separada para diferentes preocupaciones operativas.

### `README.md`

Descripción general del proyecto, arquitectura, características, línea base de seguridad, estado de desarrollo y dirección del proyecto.

### `install.md`

Procedimientos de instalación, despliegue, configuración del cliente, validación, actualización y eliminación.

### `administration.md`

Administración de rutina, mantenimiento, copias de seguridad, actualizaciones, procedimientos operativos y administración de emergencia.

### `security.md`

Arquitectura de seguridad, controles de seguridad, hallazgos de auditoría, endurecimiento e información de seguridad para la preparación de la versión.

### `telemetry.md`

Telemetr?a opcional de CPU, memoria, disco, red, host y operaciones; configuraci?n del agente, retenci?n de datos, seguridad y soluci?n de problemas.

### `LUMS_Health_Dashboard.md`

Qu? informa el panel de estado autenticado, c?mo se clasifica el estado de los clientes, los l?mites de telemetr?a, la interpretaci?n del almacenamiento de copias de seguridad y las comprobaciones operativas.

### `LUMS_Infrastructure_Topology.md`

C?mo LUMS importa los clientes registrados, gestiona la infraestructura y sus dependencias, protege las ediciones de topolog?a e identifica posibles puntos comunes de fallo.

### `server/static/backup-restore.md`

Recuperaci?n cuidadosa de una copia de seguridad SQLite verificada mediante Docker, incluidas las comprobaciones de integridad y una copia alternativa de la base de datos activa.

### `docs/update-tools-package.md`

Contenido del artefacto descargable de herramientas de actualizaci?n, c?mo lo publica CI y las comprobaciones necesarias antes de utilizarlo en producci?n.

### `troubleshooting.md`

Procedimientos de diagnóstico para problemas de servidor, cliente, trabajos, gestión de paquetes, autenticación, base de datos, contenedor y red.

### `LUMS_Optional_Theme_System.md`

Arquitectura y guía de mantenimiento para los temas opcionales del frontend de LUMS.

La documentación está intencionalmente separada por responsabilidad para que las instrucciones operativas no se mezclen con el diseño de seguridad o la personalización visual.

---

## Principio de documentación

La documentación se trata como parte del sistema.

Una funcionalidad no se considera completamente terminada cuando el código funciona pero la documentación todavía describe una arquitectura más antigua.

La relación prevista es:

```text id="0m1m5u"
Implementation
      │
      ├── Tests
      ├── Security Review
      └── Documentation
               │
               ▼
          Release Ready
```

Esto es especialmente importante para los procedimientos de despliegue y administración sensibles a la seguridad.

## Estado actual

LUMS es una plataforma de gestión de actualizaciones de Linux en desarrollo activo.

La implementación actual incluye:

* gestión centralizada de clientes
* inventario de software
* detección de actualizaciones
* búsqueda de paquetes
* instalación y eliminación de paquetes
* actualizaciones específicas de paquetes
* actualizaciones del sistema
* trabajos de actualización persistentes
* estado de trabajo a nivel de paquete
* recuperación de trabajos
* detección de reinicio
* ejecución consciente de la inactividad
* autenticación por token de cliente
* rotación de tokens
* autenticación administrativa
* control de acceso basado en roles
* gestión de usuarios
* registro de auditoría
* endurecimiento del contenedor
* transporte HTTPS
* pruebas automatizadas
* integración continua
* telemetría opcional de CPU, memoria, disco, red, host y eventos
* topología de infraestructura basada en clientes registrados e inventario mantenido manualmente
* registros persistentes de alertas y endpoints para gestionar reglas, con las limitaciones descritas en `docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`

Esta lista es un inventario general, no una afirmación de que todas las funciones estén completas o de que el proyecto esté listo para publicarse. Los componentes opcionales pueden requerir instalación y configuración por separado, y algunas funciones tienen limitaciones documentadas. Consulta la revisión del código fuente y sus pruebas para conocer el comportamiento de una versión concreta.

---

## Estado de seguridad

Las principales áreas de revisión de seguridad se han implementado y revisado.

La línea base de seguridad actual incluye:

```text
Authentication
    ├── Argon2 password hashing
    ├── session handling
    ├── session revocation
    └── login rate limiting

Authorization
    ├── Administrator
    ├── Operator
    └── Viewer

Client Security
    ├── per-client tokens
    ├── SHA-256 token digests
    └── token rotation

API Security
    ├── input validation
    ├── CSRF protection
    ├── RBAC enforcement
    └── parameterized SQL

Runtime Security
    ├── non-root container
    ├── read-only root filesystem
    ├── dropped capabilities
    ├── no-new-privileges
    ├── restricted temporary filesystems
    └── protected secret mount

Network Security
    ├── HTTPS
    ├── reverse proxy
    ├── loopback application binding
    └── firewall restrictions
```

La seguridad se trata como una responsabilidad de ingeniería continua en lugar de una lista de verificación puntual.

---

## Proceso de publicación

```text id="f3c4y9"
Implementation
      ↓
Security Review
      ↓
Documentation Review
      ↓
Full Test Suite
      ↓
CI
      ↓
Version Assignment
      ↓
Git Tag
      ↓
GitHub Release
```

La disponibilidad de versiones y etiquetas puede cambiar sin que se actualice esta documentación; consulta la página Releases del repositorio y sus etiquetas para conocer el estado actual. Una versión solo debe publicarse cuando se hayan completado la implementación, la revisión de seguridad, la documentación y las pruebas de regresión correspondientes a esa revisión.

---

## Hoja de ruta

Esta guía no registra una fase del proyecto ligada a una rama o a un plazo. El trabajo futuro, una vez seleccionado y verificado, puede incluir:

* distribuciones Linux adicionales
* backends de gestores de paquetes adicionales
* mejoras adicionales de la interfaz
* capacidades de reporte adicionales
* automatización operativa ampliada
* controles de seguridad adicionales
* mayor cobertura de pruebas

Las funcionalidades futuras deben preservar las fronteras arquitectónicas existentes.

---

## Lo que LUMS no es

LUMS no está diseñado intencionalmente como:

* un shell remoto de propósito general
* un reemplazo de APT, dpkg o pacman
* una plataforma completa de gestión de configuración
* una suite de gestión de puntos finales para todos los sistemas operativos
* un servicio exclusivo en la nube
* un framework de ejecución de comandos no controlado

LUMS se centra en un problema más limitado:

> **Gestión controlada de software y actualizaciones de Linux con estado persistente y auditabilidad.**

---

## Filosofía de desarrollo

LUMS sigue un ciclo de desarrollo simple:

```text id="8a0mve"
Build
  ↓
Test
  ↓
Secure
  ↓
Document
```

Una funcionalidad no se considera completa simplemente porque funciona en el entorno del desarrollador.

También debe ser:

* probada
* revisada en seguridad
* documentada
* reproducible
* comprensible
* recuperable cuando corresponda

---

## Filosofía de cambios

Los cambios deben hacerse deliberadamente.

Un cambio típico debe responder:

1. ¿Qué problema resuelve?
2. ¿Qué componente debe poseer el cambio?
3. ¿Afecta el cambio a la seguridad?
4. ¿Afecta al estado persistente?
5. ¿Afecta a los clientes?
6. ¿Requiere cambios en la documentación?
7. ¿Qué pruebas demuestran que la funcionalidad existente sigue funcionando?

Esto reduce el riesgo de corregir una parte del sistema mientras se rompe silenciosamente otra.

---

## Flujo de desarrollo

El flujo de desarrollo preferido es:

```text id="r8u6o1"
Understand
   ↓
Implement
   ↓
Test
   ↓
Inspect
   ↓
Harden
   ↓
Document
   ↓
Regression Test
```

Los cambios sensibles a la seguridad reciben verificación adicional antes de considerarse completos.

---

## Repositorio

El repositorio del proyecto está alojado en GitHub:

**NovaForgeCtrl/LUMS**

El repositorio contiene el código fuente de la aplicación, los componentes del cliente, las pruebas, la configuración del contenedor y la documentación del proyecto.

---

## Conjunto de documentación

El conjunto de documentación actual consiste en:

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Cada documento tiene un propósito definido.

El README proporciona la descripción general del proyecto.

La guía de instalación explica el despliegue.

La guía de administración explica la operación continua.

La guía de seguridad documenta la arquitectura de seguridad y el estado de la auditoría.

La guía de solución de problemas proporciona procedimientos de diagnóstico.

El documento de temas opcionales cubre la arquitectura de temas del frontend.

---

## Licencia

LUMS se publica bajo la Licencia MIT.

La licencia tiene como objetivo mantener el proyecto abierto y accesible mientras permite su uso, modificación y redistribución bajo los términos de la licencia.

Consulte el archivo de licencia del repositorio para obtener el texto legal completo.

---

## Comunidad y contribuciones

LUMS es un proyecto de código abierto y las contribuciones son bienvenidas.

Las contribuciones útiles pueden incluir:

* informes de errores
* informes de seguridad
* mejoras de documentación
* pruebas
* soporte de gestores de paquetes
* mejoras del frontend
* mejoras del backend
* mejoras de despliegue

Las contribuciones deben preservar los principios arquitectónicos y de seguridad del proyecto.

---

## Informes de seguridad

Los problemas de seguridad no deben tratarse como solicitudes de funcionalidades ordinarias.

Al reportar un problema de seguridad, proporcione suficiente información para reproducir y comprender el problema sin exponer innecesariamente información sensible.

Los cambios relacionados con la seguridad deben revisarse cuidadosamente antes de fusionarse.

---

## Identidad del proyecto

LUMS se construye alrededor de una idea simple:

> **Gestión de actualizaciones de Linux sin el ruido.**

El proyecto no intenta ocultar la complejidad fingiendo que la gestión de paquetes de Linux es simple.

En cambio, hace visible el estado relevante:

```text id="q2j5r0"
What is installed?
        ↓
What can be updated?
        ↓
What should change?
        ↓
Who requested it?
        ↓
What actually happened?
        ↓
What state remains?
```

Esa información es la base de la gestión controlada de actualizaciones.

---

## Arquitectura final

En su nivel más alto, LUMS puede entenderse como cinco capas:

```text id="7b4p6n"
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Human interaction and visibility        │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│    Authentication, authorization, validation  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                  Persistence                   │
│       Jobs, clients, users, results, audit   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agent                      │
│      Local execution and system reporting     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Native Linux Tools               │
│              APT / dpkg / pacman             │
└───────────────────────────────────────────────┘
```

Cada capa tiene una responsabilidad específica.

La UI proporciona interacción.

La API aplica la política.

SQLite proporciona estado persistente.

El agente realiza la ejecución controlada del lado del cliente.

El gestor de paquetes nativo realiza el cambio real del sistema.

---

## Principio final

LUMS se construye alrededor de un principio central:

> **Observar el sistema. Controlar el cambio. Registrar el resultado.**

Ese principio se aplica a la arquitectura del software, la ejecución de actualizaciones, el modelo de seguridad, los mecanismos de recuperación y la documentación.

**Gestión de actualizaciones de Linux sin el ruido.**
