# Documentación de Seguridad de LUMS

**LUMS — Servidor de Gestión de Actualizaciones de Linux**

Este documento describe la arquitectura de seguridad actual, controles de seguridad implementados, resultados de auditoría de seguridad, limitaciones operacionales y decisiones de diseño relacionadas con la seguridad de LUMS.

El documento refleja el **estado actual del sistema implementado**. Las mejoras planificadas o futuras se identifican explícitamente como tales.

---

# Principios de Seguridad

LUMS sigue un enfoque de defensa en profundidad para la gestión de actualizaciones de Linux.

El modelo de seguridad separa la autenticación administrativa, la autenticación del cliente, la autorización, la ejecución de actualizaciones controlada y el registro de auditoría.

Los objetivos de seguridad primarios son:

* acceso administrativo autenticado
* autorización basada en roles
* comunicación de cliente autenticada
* ejecución de actualización controlada
* protección contra la ejecución de trabajos concurrentes
* trabajos de actualización recuperables
* secretos protegidos
* ejecución de contenedor controlada
* operaciones sensibles a la seguridad auditables
* manejo predecible de fallos
* pruebas de regresión de seguridad

LUMS está destinado principalmente a entornos de infraestructura controlada, laboratorio y red interna.

No debe exponerse directamente a Internet público sin una revisión de seguridad adicional y controles de red apropiados.

---

# Arquitectura de Seguridad

LUMS consta de los siguientes componentes relevantes para la seguridad:

* Interfaz de administración web
* API REST
* Base de datos SQLite
* Agente de LUMS en clientes gestionados
* Backends de gestión de paquetes APT y pacman
* Mecanismos de trabajo de actualización y recuperación
* Proxy inverso HTTPS de Nginx
* Contenedor Docker reforzado

El flujo de gestión básico es:

Browser → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Package Manager → Result → SQLite → Web UI

La autenticación y la autorización están deliberadamente separadas.

Una sesión autenticada válida no otorga automáticamente acceso a todas las operaciones administrativas.

La autorización se aplica en el lado del servidor. La interfaz web además oculta funciones que no están disponibles para la función actual, pero la visibilidad de la interfaz de usuario nunca se trata como un límite de seguridad.

---

## Autenticación Administrativa

Los usuarios administrativos se autentican a través de la interfaz web de LUMS.

Las contraseñas nunca se almacenan en texto plano. LUMS utiliza hash de contraseña basado en Argon2 para el almacenamiento de contraseñas.

Las sesiones administrativas utilizan:

* manejo de sesión autenticado del lado del servidor
* vencimiento de sesión
* regeneración de sesión
* protección CSRF para solicitudes de navegador que cambian el estado
* limitación de velocidad de inicio de sesión
* invalidación de sesión durante el cierre de sesión
* validación de rol del lado del servidor

La autenticación y la autorización siguen siendo controles de seguridad separados.

Un usuario autenticado correctamente debe poseer el permiso requerido
para operaciones protegidas.

---

# Control de Acceso Basado en Roles

LUMS actualmente admite tres funciones de usuario web:

* `administrador`
* `operador`
* `visor`

Las plantillas de funciones se almacenan en `users.role`; los permisos individuales se almacenan
en el lado del servidor en `user_permissions`.

El servidor carga los permisos efectivos para cada cuenta autenticada.
La información de permisos del lado del cliente controla solo la presentación y nunca
reemplaza la autorización del lado del servidor.

## Administrator

Los administradores tienen acceso administrativo y operativo completo.

Pueden:

* ver clientes
* crear clientes
* deshabilitar clientes
* rotar tokens de cliente
* ver paquetes instalados y actualizaciones disponibles
* crear trabajos de actualización
* ejecutar operaciones de actualización compatibles
* ver historial de trabajos de actualización
* usar gestión de paquetes
* usar funciones de mantenimiento del sistema
* gestionar usuarios
* gestionar funciones de usuario
* acceder a funciones administrativas

## Operator

Los operadores pueden realizar tareas de gestión de actualizaciones operativas.

Pueden:

* ver clientes
* ver paquetes instalados y actualizaciones disponibles
* crear trabajos de actualización
* ejecutar operaciones de actualización compatibles
* ver historial de trabajos de actualización
* usar gestión de paquetes
* usar funciones de mantenimiento del sistema

Los operadores no pueden:

* gestionar usuarios
* cambiar funciones de usuario
* crear clientes
* deshabilitar clientes
* rotar tokens de cliente

## Viewer

Los espectadores tienen acceso restringido de solo lectura.

Pueden:

* ver clientes
* ver el software instalado

Las siguientes áreas de gestión se ocultan de las cuentas de Viewer:

* Actualizaciones
* Trabajos de Actualización
* Historial de Actualizaciones
* Gestión de Paquetes
* Mantenimiento del Sistema

Las cuentas de Viewer no pueden realizar operaciones de gestión de actualizaciones que cambien el estado.

El servidor aplica independientemente estas restricciones mediante la autenticación
y comprobaciones de permiso por usuario.

---

# Autenticación del Cliente

Cada cliente LUMS gestionado usa un individual Bearer token.

El mecanismo de autenticación sigue el modelo:

`Authorization: Bearer <CLIENT_TOKEN>`

El servidor no almacena tokens de cliente como valores de texto plano.

En su lugar, LUMS almacena un resumen hexadecimal SHA-256 del token del cliente.

El flujo de autenticación es:

Client Token → SHA-256 → Token Digest → SQLite

Client authentication verifies the authenticated token against the registered client and additionally checks the relevant client state.

The security model does not use a source IP address as the sole proof of client identity.

This allows LUMS to operate in:

* private laboratory networks
* isolated infrastructure
* NAT-based networks
* offline environments
* networks where client addresses may change

Client tokens can be rotated by authorized administradors.

Una rotación de token genera un token de reemplazo, almacena solo su resumen, invalida el token anterior, registra la acción administrativa en el registro de auditoría y presenta el token de reemplazo una vez.

Los valores de token de cliente de texto plano no se escriben en registros de auditoría.

---

# Seguridad de Telemetría

Los datos de telemetría (CPU, memoria, métricas de red) están sujetos al mismo modelo de autenticación y autorización que otros componentes del lado del cliente.

## Envío de Telemetría

Las muestras de telemetría se envían a través de `POST /api/telemetry` y requieren:

* Autenticación del cliente usando el mismo token de cliente que el informe de actualización
* HTTPS para conexiones remotas (HTTP simple solo para `127.0.0.1`, `localhost`, `::1`)
* Verificación de certificado CA opcional para autoridades de certificado personalizadas

El punto final de telemetría valida:

* Autenticación del token del cliente contra el resumen SHA-256 almacenado
* Estructura de carga y tipos de campo
* Rangos numéricos (CPU y memoria 0-100%, bytes no negativos)
* Actualización de muestra (rechaza muestras con marcas de tiempo excesivamente antiguas o futuras)

Las cargas inválidas se rechazan con códigos de estado HTTP apropiados.

El token del cliente no se incluye en la carga JSON y no se registra en la salida del agente.

## Control de Acceso de Telemetría

Las consultas de historial de telemetría y descripción general de la flota requieren el `clients.view` permiso.

Los siguientes puntos finales requieren autenticación:

* `GET /api/telemetry/history/<client_id>?hours=1-168` - historial del cliente
* `GET /api/telemetry/overview` - resumen de la flota

Las solicitudes no autenticadas o no autorizadas se rechazan.

## Clasificación de Datos de Telemetría

La telemetría contiene solo métricas de recursos del sistema:

* porcentaje de utilización de CPU
* porcentaje de utilización de memoria y bytes
* Contadores de bytes de red (acumulativo, sin datos de carga útil)

La telemetría **no** contiene:

* Operaciones de gestión de paquetes
* Salida de comando o registros
* Actividad del usuario
* Contenidos del archivo
* Datos de paquete de red
* Valores de configuración privada

Esta clasificación de datos limita la telemetría a métricas de utilización de recursos apropiadas para el monitoreo operativo.

## Data Storage and Retention

Telemetry samples are stored in the `telemetry_samples` table with the following schema:

```sql
CREATE TABLE telemetry_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    cpu_percent REAL NOT NULL,
    memory_percent REAL NOT NULL,
    memory_total_bytes INTEGER NOT NULL,
    memory_available_bytes INTEGER NOT NULL,
    network_rx_bytes INTEGER,
    network_tx_bytes INTEGER,
    FOREIGN KEY (client_id) REFERENCES clients(id)
)
```

Los datos anteriores a 7 días se eliminan automáticamente durante el procesamiento de nuevos envíos de telemetría.

Los datos de telemetría están sujetos a las mismas consideraciones de copia de seguridad y encriptación que el resto de la base de datos de LUMS.

Las copias de seguridad no están encriptadas por LUMS; use encriptación a nivel de host o encriptación de copia de seguridad separada según sea necesario.

---

# Auditoría de Seguridad

La auditoría de seguridad se realiza incrementalmente.

Cada área de auditoría se revisa frente a la implementación real, seguida de pruebas automatizadas, verificación aislada o verificación de producción cuando sea aplicable.

Áreas de auditoría actuales:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | APROBADO                      |
| #02   | SQLite Runtime Configuration           | APROBADO                      |
| #03   | Update Timeout Handling                | APROBADO                      |
| #04   | Login Rate Limiting                    | APROBADO                      |
| #05   | API Input Validation                   | APROBADO                      |
| #06   | Session Revocation                     | APROBADO                      |
| #07   | Client Token Rotation                  | APROBADO                      |
| #08   | IP Address Handling / Offline Networks | APROBADO                      |
| #09   | Job Recovery / Checkpointing           | APROBADO                      |
| #10   | APT Robustness                         | APROBADO                      |
| #11   | Arch Reboot Detection                  | APROBADO                      |
| #12   | Unit Tests / API Result Validation     | APROBADO                      |
| #13   | Simulation Tests                       | APROBADO                      |
| #14   | Continuous Integration                 | APROBADO                      |
| #15   | Application / Audit Logging            | APROBADO                      |
| #16   | Versioning / Releases                  | REVISADO — ABIERTO POR DISEÑO |
| #17   | Control de Acceso Basado en Roles              | APROBADO                      |
| #18   | Documentation Review                   | EN PROGRESO               |

La Auditoría #16 es intencionalmente diferente de los controles de seguridad técnicos anteriores.

LUMS actualmente no tiene una versión estable oficial, sin etiqueta de versión y sin versión de GitHub. Esto es intencional porque el proyecto sigue en desarrollo activo.

La Auditoría #18 permanece abierta hasta que se haya revisado y sincronizado todo el conjunto de documentación con la implementación actual.

# Auditoría de Seguridad #01

## SQLite Foreign Keys

La aplicación de clave externa de SQLite está habilitada para las conexiones de base de datos de aplicaciones.

La aplicación habilita explícitamente:

`PRAGMA foreign_keys = ON`

Esto garantiza que se aplique la integridad referencial para las relaciones entre registros de base de datos relacionados.

La auditoría verificó:

* aplicación de clave externa en tiempo de ejecución
* integridad de clave externa
* comportamiento del ciclo de vida del cliente
* comportamiento de deshabilitación del cliente
* preservación de información histórica de trabajos
* preservación de información de auditoría

El estado del cliente se maneja de forma conservadora.

Cuando sea apropiado, los clientes se deshabilitan en lugar de eliminarse de una manera que destruiría información histórica de operaciones.

**Estado: APROBADO**

---

# Auditoría de Seguridad #02

## SQLite Runtime Configuration

La base de datos SQLite de producción se revisó para su configuración en tiempo de ejecución.

La configuración de producción verificada es:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

La aplicación habilita explícitamente:

`PRAGMA foreign_keys = ON`

La base de datos de producción actualmente utiliza el modo WAL.

La configuración de la base de datos se documentó basándose en el estado de producción verificado realmente en lugar de la configuración histórica de desarrollo.

El tiempo de espera ocupado configurado reduce los fallos inmediatos de la base de datos cuando otra transacción mantiene temporalmente la base de datos.

La configuración de clave externa a nivel de aplicación garantiza la integridad referencial para cada conexión de base de datos.

La auditoría incluyó la verificación de producción de la configuración activa de SQLite.

**Estado: APROBADO**

---

# Auditoría de Seguridad #03

## Update Timeout and Process Handling

## Actualización y Manejo de Procesos

La ejecución de actualización está protegida contra procesos de gestor de paquetes bloqueados indefinidamente.

El flujo de ejecución es:

Iniciar proceso
↓
Leer salida del proceso
↓
Monitorear tiempo de espera
↓
¿Se alcanzó el tiempo de espera?
↓
Terminar proceso
↓
Período de gracia
↓
¿Sigue ejecutándose el proceso?
↓
Matar proceso si es necesario
↓
Completar trabajo

La implementación utiliza manejo controlado de subprocesos para que los procesos silenciosos no puedan bloquearse indefinidamente mientras esperan una salida.

La gestión del tiempo de espera se probó contra:

* procesos silenciosos
* finalización normal del proceso
* condiciones de tiempo de espera
* procesos resistentes a la finalización normal
* recurso de eliminación
* comportamiento de tiempo de espera a nivel de integración

El mecanismo de tiempo de espera evita que una operación de gestión de paquetes permanezca indefinidamente en un estado activo.

Los errores y condiciones de tiempo de espera se devuelven como resultados de trabajos controlados y se registran en el estado del trabajo.

La versión actual documentada del Agente LUMS es:

`1.7.0`

**Estado: APROBADO**

---

# Auditoría de Seguridad #04

## Login Rate Limiting

## Limitación de Velocidad de Inicio de Sesión

Los intentos de inicio de sesión administrativo están limitados en velocidad.

La política de escalamiento actual es:

* 5 intentos fallidos → 30 segundos
* 6 intentos fallidos → 60 segundos
* 7 intentos fallidos → 120 segundos
* 8 o más intentos fallidos → 300 segundos

El estado del límite de velocidad se persiste en SQLite.

Los fallos de inicio de sesión concurrentes utilizan bloqueo de base de datos transaccional con:

`BEGIN IMMEDIATE`

Esto evita que fallos de autenticación concurrentes eviten el estado de límite de velocidad previsto a través de condiciones de carrera.

Una autenticación exitosa borra el estado de falla aplicable.

La auditoría cubrió:

* comportamiento aislado de límite de velocidad
* fallos de autenticación concurrentes
* reversión de transacción
* manejo de bloqueo de base de datos
* comportamiento de restablecimiento de inicio de sesión exitoso
* eventos de auditoría de límite de velocidad
* comportamiento de inicio de sesión de producción

El limitador de velocidad, por lo tanto, proporciona un control del lado del servidor contra intentos de autenticación repetidos en lugar de confiar en el comportamiento del lado del cliente.

**Estado: APROBADO**

---

# Audit Status After Part 2

Las primeras cuatro áreas de auditoría de seguridad están completas:

| Auditoría | Área                              | Estado |
| ----- | --------------------------------- | ------ |
| #01   | Claves Externas de SQLite               | APROBADO   |
| #02   | Configuración de Tiempo de Ejecución de SQLite      | APROBADO   |
| #03   | Tiempo de Espera de Actualización / Manejo de Procesos | APROBADO   |
| #04   | Limitación de Velocidad de Inicio de Sesión               | APROBADO   |

Las siguientes áreas de auditoría se documentan en las secciones posteriores:

* #05 Validación de Entrada de API
* #06 Revocación de Sesión
* #07 Rotación de Token de Cliente
* #08 Manejo de Dirección IP / Redes Sin Conexión
* #09 Recuperación de Trabajo / Punto de Control
* #10 Robustez de APT
* #11 Detección de Reinicio de Arch
* #12 Pruebas Unitarias / Validación de Resultado de API
* #13 Pruebas de Simulación
* #14 Integración Continua
* #15 Registro de Aplicación / Auditoría
* #16 Versionado / Versiones
* #17 Control de Acceso Basado en Roles

La Auditoría #18 — Revisión de Documentación — permanece abierta hasta que se haya revisado y sincronizado todo el conjunto de documentación con la implementación actual.

# Auditoría de Seguridad #05

## Validación de Entrada de API

LUMS valida la entrada de API sensible a la seguridad en el lado del servidor.

Los valores suministrados por el cliente no se confían simplemente porque se originen en la interfaz web autenticada o en un cliente registrado.

La validación se aplica a los parámetros de API relevantes, que incluyen:

* identificadores de cliente
* nombres de paquetes
* acciones de trabajo de actualización
* listas de paquetes
* parámetros de búsqueda
* parámetros de gestión de usuarios
* operaciones de token de cliente
* datos de resultado de trabajo

Los nombres de paquetes se validan antes de pasarlos a operaciones de gestión de paquetes.

La API de trabajo de actualización acepta solo acciones explícitamente compatibles.

Las acciones relacionadas con paquetes actualmente compatibles son:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Las acciones inesperadas se rechazan.

Las listas de paquetes se validan antes de la creación del trabajo.

Para `UPDATE_PACKAGE`, el paquete solicitado también debe estar presente en la información de actualizaciones disponibles del cliente.

Las consultas de base de datos utilizan SQL parametrizado en lugar de construir sentencias SQL a partir de entrada no confiable.

Esto evita que los valores controlados por el usuario se interpreten como sintaxis SQL.

La auditoría incluyó pruebas de entrada negativa y casos de prueba orientados a inyección SQL.

Los controles de validación también se verificaron a través de la suite de pruebas automatizadas.

**Estado: APROBADO**

---

# Auditoría de Seguridad #06

## Revocación de Sesión

LUMS protege las sesiones administrativas autenticadas contra su uso continuado después de cerrar la sesión.

La gestión de sesiones incluye:

* sesiones autenticadas del lado del servidor
* expiración de sesión
* regeneración de sesión
* invalidación de cierre de sesión
* comprobaciones de autenticación del lado del servidor
* validación de rol del lado del servidor

Cerrar la sesión invalida la sesión autenticada activa.

Los puntos finales de API protegidos requieren una sesión autenticada y no se basan en el estado del lado del cliente para determinar si el usuario permanece autenticado.

El estado de la sesión, por lo tanto, es evaluado por el servidor para operaciones protegidas.

Las solicitudes de navegador que cambian el estado además requieren protección CSRF.

La auditoría verificó que:

* el acceso autenticado funciona normalmente
* protected endpoints reject unauthenticated requests
* logout invalidates the active session
* a previously authenticated session cannot continue using protected functionality after revocation
* role information is evaluated server-side

**Status: APROBADO**

---

# Auditoría de Seguridad #07

## Client Token Rotation

Each managed LUMS client uses an individual authentication token.

Client tokens are not stored as plaintext values.

Instead, LUMS stores the SHA-256 hexadecimal digest of the client token.

The authentication model is:

`Authorization: Bearer <CLIENT_TOKEN>`

The server hashes the supplied token and compares the resulting digest with the registered client token digest.

Authorized administradors can rotate a client's token.

Token rotation performs the following operations:

1. Generate a replacement token.
2. Calculate its SHA-256 digest.
3. Replace the stored client-token digest.
4. Invalidate the previous token.
5. Record the administrative action in the audit log.
6. Present the replacement token to the administrador.

The previous token cannot authenticate after rotation.

Plaintext token values are not written to audit logs.

The audit verified:

* successful token authentication
* token digest storage
* token rotation
* invalidation of the previous token
* authentication with the replacement token
* authorization requirements for token rotation
* registro de auditoría
* protection against unauthorized rotation

Client token rotation is restricted to administradors.

Operators and visors cannot rotar tokens de cliente.

**Status: APROBADO**

---

# Auditoría de Seguridad #08

## Manejo de Dirección IP y Redes Sin Conexión

LUMS no utiliza la dirección IP de origen de un cliente como la única prueba de identidad del cliente.

La autenticación del cliente se basa en el token de cliente registrado.

Este diseño es intencional porque los clientes gestionados pueden operar en entornos donde su dirección de red cambia.

Los escenarios de implementación compatibles incluyen:

* redes privadas de laboratorio
* redes basadas en NAT
* infraestructura aislada
* clientes direccionados dinámicamente
* entornos sin conexión
* redes internas controladas

El servidor, por lo tanto, separa:

**Ubicación de red**

de:

**Identidad del cliente**

Un token de cliente válido identifica al cliente registrado.

La dirección de red del cliente aún puede registrarse con fines operativos y de auditoría, pero no se trata como una credencial de autenticación.

La implementación también evita suposiciones de que un cliente debe ser alcanzable desde una dirección fija.

Esto es particularmente importante para entornos de laboratorio e infraestructura donde la topología de red puede cambiar sin cambiar la identidad lógica del sistema gestionado.

La auditoría verificó la autenticación del cliente sin confiar en una dirección IP de origen fija.

**Estado: APROBADO**

---

# Audit Status After Part 3

Las siguientes áreas de auditoría de seguridad están completas:

| Auditoría | Área                                   | Estado |
| ----- | -------------------------------------- | ------ |
| #01   | Claves Externas de SQLite                    | APROBADO   |
| #02   | Configuración de Tiempo de Ejecución de SQLite           | APROBADO   |
| #03   | Tiempo de Espera de Actualización / Manejo de Procesos      | APROBADO   |
| #04   | Limitación de Velocidad de Inicio de Sesión                    | APROBADO   |
| #05   | Validación de Entrada de API                   | APROBADO   |
| #06   | Revocación de Sesión                     | APROBADO   |
| #07   | Rotación de Token de Cliente                  | APROBADO   |
| #08   | Manejo de Dirección IP / Redes Sin Conexión | APROBADO   |

La siguiente sección cubre:

* #09 Recuperación de Trabajo / Punto de Control
* #10 Robustez de APT
* #11 Detección de Reinicio de Arch
* #12 Pruebas Unitarias / Validación de Resultado de API

# Auditoría de Seguridad #09

## Recuperación de Trabajo y Punto de Control

Los trabajos de actualización de LUMS están diseñados para recuperarse de forma segura de la ejecución interrumpida.

Los trabajos de actualización mantienen estado persistente en la base de datos SQLite.

Las operaciones de paquetes individuales se rastrean por separado del estado general del trabajo.

Esto permite que el Agente determine qué operaciones de paquete ya se han completado correctamente antes de que se reanude un trabajo interrumpido.

Durante la recuperación, las operaciones de paquete completadas correctamente no se ejecutan nuevamente.

Por lo tanto, la lógica de recuperación sigue el principio:

`Estado de Trabajo Persistente → Determinar Trabajo Completado → Omitir Elementos Completados → Continuar Trabajo Restante`

Esto reduce el riesgo de operaciones de paquete innecesariamente repetidas después de:

* interrupción del agente
* terminación del proceso
* reinicio del sistema
* falha temporal de comunicación
* reinicio del contenedor
* otras interrupciones de ejecución

La auditoría verificó el comportamiento de recuperación de trabajo interrumpido y punto de control.

La recuperación se probó con trabajos que contenían múltiples operaciones de paquete y con elementos de paquete previamente exitosos.

La auditoría confirmó que el trabajo completado se conserva y el trabajo restante puede continuar sin repetir innecesariamente operaciones exitosas.

**Estado: APROBADO**

---

# Auditoría de Seguridad #10

## Robustez de APT

Las operaciones de paquetes basadas en Debian se ejecutan a través de la capa de gestión de paquetes de LUMS.

Las operaciones de actualización relacionadas con APT se revisaron para una detección confiable del estado del gestor de paquetes y los resultados de la actualización.

La implementación tiene en cuenta casos donde los comandos de gestión de paquetes pueden devolvere exitosamente mientras requieren interpretación adicional de su salida o estado del sistema resultante.

La detección de actualización de APT se endurecio para evitar confiar en una única condición de salida de comando simplista.

La auditoría incluyó pruebas de:

* operaciones normales de APT
* actualizaciones de paquetes disponibles
* instalación de paquetes
* eliminación de paquetes
* ejecución de trabajo de actualización
* manejo de resultado de APT
* comportamiento de detección de actualización

El endurecimiento correspondiente se comprometió como:

`c76f331 security: harden apt update detection`

El objetivo es garantizar que LUMS no informar incorrectamente el estado de gestión de paquetes basándose únicamente en una salida de comando incompleta o ambigua.

**Estado: APROBADO**

---

# Auditoría de Seguridad #11

## Detección de Reinicio de Arch Linux

Las operaciones de paquetes de Arch Linux pueden resultar en un estado del sistema en el que se requiere o se recomienda un reinicio.

Por lo tanto, LUMS evalúa el estado del sistema resultante después de las operaciones relevantes de gestión de paquetes.

El Agente distingue la finalización normal de la operación de paquete de situaciones en las que se requiere un reinicio.

El estado de reinicio se reporta nuevamente al servidor LUMS como parte del resultado del trabajo.

Esto permite que la interfaz de gestión distinga entre:

* operación de paquete exitosa
* operación exitosa con requisito de reinicio
* operación fallida

La auditoría verificó la detección de reinicio de Arch Linux utilizando la ruta de ejecución de gestión de paquetes real.

La implementación se probó contra condiciones de reinicio requeridas y condiciones de finalización normal.

**Estado: APROBADO**

---

# Auditoría de Seguridad #12

## Pruebas Unitarias y Validación de Resultado de API

El comportamiento sensible a la seguridad se cubre mediante pruebas automatizadas.

La suite de pruebas incluye cobertura para autenticación, autorización, validación de API, trabajos de actualización, gestión de paquetes, autenticación de cliente y manejo de resultados.

La ruta del resultado del Agente al servidor se revisó específicamente para garantizar que los resultados del trabajo no puedan alterar arbitrariamente el estado del lado del servidor no relacionado.

El procesamiento de resultados valida la información enviada antes de aplicar cambios de estado al trabajo de actualización correspondiente.

La validación cubre los campos de resultado relevantes y las relaciones laborales esperadas.

Esto evita que un cliente autenticado seleccione libremente trabajos no relacionados o inyecte estado arbitrario en la base de datos de trabajos de actualización.

La suite de pruebas de seguridad también cubre casos no autorizados y negativos.

Ejecute la suite de pruebas automatizadas completa desde la raíz del repositorio con
`./.venv-test/bin/pytest -q`. El número de pruebas cambia con el tiempo; use el
resultado de la ejecución actual en lugar de un recuento fijo en este documento.

Los controles de seguridad relevantes también se verificaron mediante ejecuciones de pruebas enfocadas durante la auditoría.

**Estado: APROBADO**

---

# Audit Status After Part 4

Las siguientes áreas de auditoría de seguridad están completas:

| Auditoría | Área                                   | Estado |
| ----- | -------------------------------------- | ------ |
| #01   | Claves Externas de SQLite                    | APROBADO   |
| #02   | Configuración de Tiempo de Ejecución de SQLite           | APROBADO   |
| #03   | Tiempo de Espera de Actualización / Manejo de Procesos      | APROBADO   |
| #04   | Limitación de Velocidad de Inicio de Sesión                    | APROBADO   |
| #05   | Validación de Entrada de API                   | APROBADO   |
| #06   | Revocación de Sesión                     | APROBADO   |
| #07   | Rotación de Token de Cliente                  | APROBADO   |
| #08   | Manejo de Dirección IP / Redes Sin Conexión | APROBADO   |
| #09   | Recuperación de Trabajo / Punto de Control           | APROBADO   |
| #10   | Robustez de APT                         | APROBADO   |
| #11   | Detección de Reinicio de Arch                  | APROBADO   |
| #12   | Pruebas Unitarias / Validación de Resultado de API     | APROBADO   |

La siguiente sección cubre:

* #13 Pruebas de Simulación
* #14 Integración Continua
* #15 Registro de Aplicación / Auditoría
* #16 Versionado / Versiones

# Auditoría de Seguridad #13

## Pruebas de Simulación

LUMS proporciona un mecanismo de simulación para probar flujos de trabajo de gestión de actualización sin realizar la operación correspondiente de gestión de paquetes en el sistema gestionado.

La simulación se implementa en la capa de ejecución del Agente.

Cuando la simulación está habilitada, las operaciones de gestión de paquetes se representan y procesan sin aplicar el cambio de paquete solicitado al sistema operativo.

Esto permite que el comportamiento del trabajo de actualización se pruebe sin modificar intencionalmente el sistema gestionado.

Las pruebas de simulación cubren rutas de gestión de actualización relevantes, incluyendo:

* instalación de paquetes
* eliminación de paquetes
* actualizaciones de paquetes
* actualizaciones del sistema
* ejecución de trabajos
* informe de resultados
* finalización exitosa
* manejo de fallos

El mecanismo de simulación se utilizó durante la auditoría de seguridad para verificar la creación de trabajos, la ejecución del Agente, el manejo de resultados y las transiciones de estado del lado del servidor independientemente de las modificaciones reales de paquetes.

El modo de simulación es un mecanismo de prueba y no reemplaza los controles de autorización de operaciones de actualización normales.

**Estado: APROBADO**

---

# Auditoría de Seguridad #14

## Integración Continua

LUMS utiliza pruebas automatizadas para detectar regresiones de seguridad y funcionales antes de que los cambios se consideren completos.

El proceso de CI ejecuta la suite de pruebas automatizadas contra el proyecto.

El entorno de prueba verifica la aplicación y la funcionalidad sensible a la seguridad independientemente del contenedor de producción.

El proceso de CI incluye validación de:

* autenticación
* autorización
* RBAC
* comportamiento de API
* manejo de trabajo de actualización
* comportamiento de gestión de paquetes
* autenticación de cliente
* validación de resultado de trabajo
* manejo de errores sensibles a la seguridad

La auditoría de CI se revisó después de los cambios de endurecimiento de seguridad.

La suite de pruebas final verificada se completó correctamente.

El recuento de pruebas cambia a medida que evoluciona el proyecto. CI proporciona una barrera de
regresión automatizada para cambios de aplicación relevantes para la seguridad.

**Estado: APROBADO**

---

# Auditoría de Seguridad #15

## Registro de Aplicación y Auditoría

LUMS registra eventos administrativos y operacionales sensibles a la seguridad a través del registro de auditoría a nivel de aplicación.

El registro de auditoría está diseñado para proporcionar un historial operativo sin almacenar credenciales sensibles.

Las acciones sensibles a la seguridad relevantes incluyen eventos tales como:

* eventos de seguridad relacionados con autenticación
* acciones administrativas
* gestión de clientes
* operaciones de token de cliente
* creación de trabajo de actualización
* ejecución de trabajo de actualización
* fallos relevantes para la seguridad

El material de credenciales sensibles se excluye de los registros de auditoría.

En particular:

* las contraseñas no se registran
* los tokens de cliente de texto plano no se registran
* los valores secretos no se escriben intencionalmente en los registros de auditoría

Los registros de auditoría se asocian con el contexto administrativo u operacional relevante cuando sea aplicable.

La implementación del registro de auditoría se revisó para:

* cobertura de eventos sensibles a la seguridad
* exclusión de credenciales
* trazabilidad administrativa
* manejo de fallos
* persistencia de información de auditoría relevante

El sistema de registro está diseñado para apoyar tanto la solución de problemas operacionales como la investigación de seguridad.

**Estado: APROBADO**

---

# Auditoría de Seguridad #16

## Versionado y Versiones

El versionado y la gestión de versiones se revisaron como parte de la auditoría de seguridad.

LUMS está actualmente en desarrollo activo y aún no tiene una versión estable oficial.

El estado actual del repositorio por lo tanto intencionalmente tiene:

* sin versión de versión estable oficial
* sin etiqueta de versión
* sin Versión de GitHub

Las versiones actuales de componentes incluyen:

* Agente LUMS: `1.7.0`
* Relojero LUMS: `1.2.1`

Actualmente no hay un único número de versión formal que represente la aplicación LUMS completa.

Esta es una decisión de estado de proyecto intencional en lugar de una omisión accidental.

El proceso de lanzamiento planeado es:

1. Completar el trabajo de implementación.
2. Completar la revisión de seguridad.
3. Revisar y sincronizar la documentación.
4. Completar la suite de pruebas automatizadas completa.
5. Verificar CI.
6. Definir la versión de lanzamiento.
7. Crear la etiqueta de Git correspondiente.
8. Publicar la Versión de GitHub.
9. Preservar la versión como la línea base documentada.

No se crea ninguna versión oficial simplemente porque la auditoría de seguridad alcanza un número de auditoría particular.

La creación de versiones se realizará únicamente después de que se haya completado el trabajo de implementación y documentación restante.

**Estado: REVISADO — ABIERTO POR DISEÑO**

---

# Audit Status After Part 5

The following security audit areas are complete:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | APROBADO                      |
| #02   | SQLite Runtime Configuration           | APROBADO                      |
| #03   | Update Timeout / Process Handling      | APROBADO                      |
| #04   | Login Rate Limiting                    | APROBADO                      |
| #05   | API Input Validation                   | APROBADO                      |
| #06   | Session Revocation                     | APROBADO                      |
| #07   | Client Token Rotation                  | APROBADO                      |
| #08   | IP Address Handling / Offline Networks | APROBADO                      |
| #09   | Job Recovery / Checkpointing           | APROBADO                      |
| #10   | APT Robustness                         | APROBADO                      |
| #11   | Detección de Reinicio de Arch                  | APROBADO                      |
| #12   | Pruebas Unitarias / Validación de Resultado de API     | APROBADO                      |
| #13   | Pruebas de Simulación                       | APROBADO                      |
| #14   | Integración Continua                 | APROBADO                      |
| #15   | Registro de Aplicación / Auditoría            | APROBADO                      |
| #16   | Versionado / Versiones                  | REVISADO — ABIERTO POR DISEÑO |

El área técnica de auditoría numerada restante es:

* #17 Control de Acceso Basado en Roles

La revisión de documentación se rastrea por separado como:

* #18 Revisión de Documentación — EN PROGRESO

# Auditoría de Seguridad #17

## Control de Acceso Basado en Roles

LUMS combina plantillas de rol con permisos asignados individualmente. Los
templates admitidos son `administrador`, `operador` y `visor`; elegir un
template selecciona sus permisos predeterminados, que un administrador puede personalizar
para cada cuenta.

El rol sigue siendo metadatos de la cuenta. Las rutas protegidas se autorizan contra el
conjunto de permiso almacenado en el servidor de la cuenta, no la etiqueta de rol. La interfaz oculta
funciones no disponibles para facilitar el uso, mientras que el servidor sigue siendo el límite de seguridad.

---

## Modelo de Permiso de RBAC

| Permiso        | Acceso otorgado |
| ----------------- | -------------- |
| `clients.view`    | Ver clientes e información del sistema |
| `software.view`   | Ver software instalado |
| `updates.view`    | Ver actualizaciones disponibles, trabajos e historial |
| `packages.search` | Buscar repositorios de paquetes |
| `jobs.manage`     | Crear operaciones de paquete y trabajos de actualización |
| `clients.manage`  | Registrar/eliminar clientes y rotar tokens de cliente |
| `users.manage`    | Crear usuarios y gestionar roles y permisos |

Las plantillas de rol predeterminadas son:

| Template        | Permisos predeterminados |
| --------------- | ------------------- |
| `administrador` | Todos los permisos |
| `operador`      | Visibilidad de cliente/software/actualización, búsqueda de paquetes y gestión de trabajos |
| `visor`        | Visibilidad de cliente y visibilidad de software instalado |

Los permisos relacionados con clientes requieren `clients.view`. `jobs.manage` también requiere
`updates.view`. La interfaz carga permisos para la cuenta autenticada y
omite controles que el usuario no puede usar; las comprobaciones del lado del servidor aplican de forma independiente
las mismas concesiones.

---

## Aplicación de Autorización

Las operaciones protegidas utilizan autenticación del lado del servidor y comprobaciones de permiso.

El modelo de autorización sigue el principio:

`Autenticar → Cargar Permisos del Usuario → Autorizar Operación → Ejecutar`

La autenticación por sí sola no es suficiente para acceder a operaciones privilegiadas.

Las operaciones que cambian el estado además requieren protección CSRF donde sea aplicable.

Los ejemplos de operaciones administrativas protegidas incluyen:

* creación de trabajo de actualización
* instalación de paquete
* eliminación de paquete
* actualizaciones de paquetes
* actualizaciones del sistema
* operaciones de gestión de paquetes
* creación de cliente
* deshabilitación de cliente
* rotación de token de cliente
* creación de usuario
* funciones de gestión de usuarios

Los puntos finales protegidos definen explícitamente el permiso requerido para el
operación correspondiente.

La falta de permiso es rechazada por el servidor incluso si el usuario construye manualmente
la solicitud HTTP correspondiente.

Esto evita eludir el modelo de RBAC llamando directamente a un punto final de API que está oculto en la interfaz web.

---

## Restricciones de Visor

La plantilla de Visor está intencionalmente restringida por su conjunto de permisos predeterminado.

Para cuentas sin las concesiones correspondientes, la interfaz del cliente no expone:

* Actualizaciones
* Trabajos de Actualización
* Historial de Actualizaciones
* Gestión de Paquetes
* Mantenimiento del Sistema

El servidor además evita que cuentas sin las concesiones correspondientes
realicen operaciones protegidas.

La interfaz de JavaScript no carga datos de gestión de actualización sin
`updates.view`.

Esto reduce la exposición innecesaria de información operacional mientras se mantiene la autorización del lado del servidor como el control de seguridad real.

El software instalado permanece disponible para cuentas de Visor como una función de información de solo lectura.

---

## Gestión de Usuario Administrativo

La gestión de usuarios requiere el permiso `users.manage`.

Los usuarios con ese permiso pueden crear cuentas sin permisos y luego
asignar concesiones individuales o aplicar una plantilla de rol en el editor de permisos.
Las plantillas de rol tienen descripciones que explican sus concesiones predeterminadas.

Los gestores de usuarios autorizados pueden guardar una nota interna por cuenta. Las notas se
limitan a 2.000 caracteres, no se incluyen en los detalles del registro de auditoría y
no son visibles para el propietario de la cuenta.

La creación de usuario incluye:

* validación de nombre de usuario
* validación de rol
* validación de contraseña
* hash de contraseña Argon2
* detección de usuario duplicado
* registro de auditoría
* protección CSRF
* autorización del lado del servidor

Los puntos finales de gestión de usuario no son accesibles sin `users.manage`.

El servidor rechaza permisos desconocidos y combinaciones de dependencia no válidas.
At least one active account must retain `users.manage`; changes that would
remove the last user manager are rejected.

Las contraseñas nunca se almacenan en texto plano.

---

## RBAC Database Migration

Role-template information remains in the user database record. Individual
grants are stored in the `user_permisos` table with a foreign key to the
user account. Migration `003-user-permisos` creates that table and seeds
existing accounts from their current role template, preserving their access
during the transition. Migration `004-user-admin-notes` adds the private
`users.admin_note` field; existing accounts receive an empty note. Migration
`005-backup-permiso` grants `backups.manage` to existing Administrator
accounts.

Database backup creation requires `backups.manage`; the Administrator
template includes this permiso by default. The server writes SQLite online
backups only to the server-configured `LUMS_BACKUP_DIR`; it does not accept
filesystem paths from the browser. Backup files are created with owner-only
permisos and are integrity-checked before publication.

---

## RBAC Security Testing

RBAC behavior is covered by automated tests.

The tests include:

* Administrator authorization
* Operator authorization
* Viewer restrictions
* protected API access
* unauthorized operations
* client-management restrictions
* update-job restrictions
* user-management restrictions
* client-page visibility
* permiso-specific interface behavior

RBAC tests cover role-template defaults, custom permisos, permiso
dependencies, and server-side authorization. Production verification should
include accounts with customized permisos as well as the default
Administrator, Operator, and Viewer templates.

---

## RBAC Security Result

The RBAC implementation provides layered authorization:

1. Authentication establishes the user identity.
2. The server loads the user's permisos.
3. Protected routes enforce the required permiso.
4. protección CSRF applies to relevant browser state changes.
5. The web interface hides unavailable functionality.
6. Automated tests verify authorization boundaries.

The interface therefore does not provide the authorization mechanism by itself.

The server remains the authoritative security boundary.

**Status: APROBADO**

# Auditoría de Seguridad #18

## Documentation Review

The security documentation is reviewed against the currently implemented LUMS system.

The purpose of this review is to ensure that security documentation describes the actual implementation rather than an earlier development state.

The review covers:

* authentication
* authorization
* RBAC
* client authentication
* token handling
* session handling
* protección CSRF
* rate limiting
* SQLite configuration
* update execution
* job recovery
* package management
* container hardening
* network exposure
* secrets handling
* dependency and build security
* filesystem permisos
* application and registro de auditoría
* versioning and release handling
* pruebas de seguridad automatizadas

Documentation must distinguish between:

* implemented controls
* verified production behavior
* planned improvements
* intentionally open project decisions

Historical implementation details must not be presented as current production configuration.

In particular, the documentation reflects the current SQLite production configuration rather than the current WAL configuration.

The current production runtime is documented as:

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* application-level `PRAGMA foreign_keys = ON`

The current Viewer-RBAC behavior is also documented according to the implemented production interface.

Viewer users have access to:

* client information
* installed software

Viewer users do not have access to:

* Actualizaciones
* Trabajos de Actualización
* Historial de Actualizaciones
* Gestión de Paquetes
* Mantenimiento del Sistema

The documentation review also removes or replaces outdated references to earlier test counts, migration states, deployment configurations, and development-only behavior.

**Status: EN PROGRESO**

---

# Additional Security Hardening

The numbered security audit covers the primary application security controls.

Additional hardening was performed after the original audit sequence and is part of the current security baseline.

These controls are documented here because they represent important security properties of the current deployment.

---

## Container Hardening

The production LUMS container runs with a hardened Docker configuration.

The production container uses:

* non-root application user
* read-only root filesystem
* dropped Linux capabilities
* `no-new-privileges`
* restricted temporary filesystems
* read-only secret mount
* dedicated persistent application-data volume
* restart policy
* loopback-only host publication of the application port

The application root filesystem is therefore not writable during normal operation.

Writable locations are explicitly limited to the locations required by the application.

The production container was independently inspected to verify the effective runtime configuration.

The hardened runtime was also tested by verifying that:

* application filesystem writes fail
* `/tmp` remains available where required
* `/var/lib/lums` remains writable
* the secret file remains read-only
* the application remains operational

---

## Network Exposure

The LUMS application port is not directly exposed to the LAN.

The Docker application port is bound to the loopback interface:

`127.0.0.1:5050`

External access is provided through Nginx.

The production host exposes the intended network services through the firewall and reverse proxy.

The deployment was verified to prevent direct remote access to the internal Docker application port.

The firewall uses a default-deny model for incoming and routed traffic.

The intended externally reachable services are:

* SSH
* HTTP
* HTTPS

HTTP requests are redirected to HTTPS by the web server.

The default Nginx site was removed so that unrelated default content is not exposed.

---

## Transport Security

Administrative web access is provided through HTTPS.

HTTP is redirected to HTTPS.

The TLS endpoint is handled by Nginx rather than the Flask/Gunicorn application directly.

This keeps transport security and application serving separated.

The internal Gunicorn application port is therefore not intended to be a public HTTP endpoint.

The current deployment is intended for controlled internal infrastructure.

A future deployment with direct public-Internet exposure would require an additional security review.

---

## Secrets and Configuration

Production secrets are not stored in the application source tree.

The LUMS secret key is supplied through a protected secret file.

The production container receives the secret through:

`/run/secrets/lums_secret`

The secret file is mounted read-only.

The application reads the secret through the configured secret-file mechanism.

Repository and Docker build-context handling was reviewed to prevent accidental inclusion of:

* database files
* backup files
* secret files
* private keys
* certificates
* runtime logs
* local backup artifacts

The repository also ignores common temporary backup patterns used during development.

---

## Dependency and Build Security

The production Docker image uses a pinned Python base-image digest.

The production runtime dependencies are explicitly version-pinned.

The current production dependency set includes:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

The Docker build context is restricted through `.dockerignore`.

Repeated production builds were compared during the audit.

The relevant dependency and package metadata remained consistent between repeated builds, apart from expected generated Python bytecode differences.

This provides a reproducible baseline for the production image while keeping the build context limited.

---

## Filesystem and Runtime Permissions

The production application runs as the dedicated `lums` user rather than root.

Persistent application data is stored in the dedicated LUMS data volume.

The application root filesystem is read-only.

Runtime write access is restricted to explicitly required locations.

The production runtime was verified to reject unauthorized writes to the application filesystem.

This reduces the impact of accidental or malicious file modification inside the application container.

---

# Auditoría de Seguridad Conclusion

The current LUMS implementation has undergone a broad security review covering:

* authentication
* authorization
* RBAC
* session security
* protección CSRF
* limitación de velocidad de inicio de sesión
* seguridad de token de cliente
* validación de API
* resistencia a la inyección SQL
* integridad de SQLite
* ejecución de actualización
* manejo de tiempo de espera
* recuperación de trabajo
* robustez de gestión de paquetes
* validación de resultado
* simulación
* integración continua
* registro de auditoría
* endurecimiento de contenedor
* exposición de red
* seguridad del transporte
* manejo de secretos
* permisos del sistema de archivos
* seguridad de dependencia y construcción

The numbered audit results are:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | APROBADO                      |
| #02   | SQLite Runtime Configuration           | APROBADO                      |
| #03   | Tiempo de Espera de Actualización / Manejo de Procesos      | APROBADO                      |
| #04   | Limitación de Velocidad de Inicio de Sesión                    | APROBADO                      |
| #05   | Validación de Entrada de API                   | APROBADO                      |
| #06   | Revocación de Sesión                     | APROBADO                      |
| #07   | Rotación de Token de Cliente                  | APROBADO                      |
| #08   | Manejo de Dirección IP / Redes Sin Conexión | APROBADO                      |
| #09   | Recuperación de Trabajo / Punto de Control           | APROBADO                      |
| #10   | Robustez de APT                         | APROBADO                      |
| #11   | Detección de Reinicio de Arch                  | APROBADO                      |
| #12   | Pruebas Unitarias / Validación de Resultado de API     | APROBADO                      |
| #13   | Pruebas de Simulación                       | APROBADO                      |
| #14   | Integración Continua                 | APROBADO                      |
| #15   | Registro de Aplicación / Auditoría            | APROBADO                      |
| #16   | Versionado / Versiones                  | REVISADO — ABIERTO POR DISEÑO |
| #17   | Control de Acceso Basado en Roles              | APROBADO                      |
| #18   | Revisión de Documentación                   | EN PROGRESO               |

Los controles de seguridad técnicos revisados en auditorías #01–#15 y #17 han pasado.

La Auditoría #16 permanece intencionalmente abierta porque LUMS aún no ha llegado a su primer lanzamiento estable oficial.

La Auditoría #18 permanece abierta hasta que se haya revisado toda la documentación del proyecto y se sincronice con el estado de implementación final.

Ningún resultado de auditoría de seguridad debe interpretarse como una garantía de que LUMS no tenga vulnerabilidades.

La seguridad es un proceso continuo.

Los cambios en la aplicación, Agente, dependencias, configuración del contenedor, exposición de red, modelo de autenticación o arquitectura de implementación deben desencadenar otra revisión de seguridad de los controles afectados.

---

# Línea Base de Seguridad

La línea base de seguridad actual se basa en el estado de implementación y despliegue de producción verificado.

La línea base incluye:

* autenticación del lado del servidor
* RBAC del lado del servidor
* hash de contraseña Argon2
* resúmenes de token de cliente SHA-256
* protección CSRF
* limitación de velocidad de inicio de sesión
* SQL parametrizado
* entrada de API validada
* ejecución controlada del gestor de paquetes
* recuperación de trabajos de actualización
* registro de auditoría
* tiempo de ejecución de Docker reforzado
* HTTPS a través de Nginx
* exposición de puerto de aplicación de solo bucle de retorno
* restricciones de cortafuegos
* secretos de producción protegidos
* dependencias de producción fijadas
* restricted filesystem permisos
* pruebas de seguridad automatizadas

Los cambios futuros deben preservar estas propiedades a menos que un cambio arquitectónico deliberado las reemplace con un control equivalente o más fuerte.

---

# Mantenimiento de Seguridad

Los controles de seguridad deben revalidarse cuando se introducen cambios significativos.

Los ejemplos incluyen:

* cambios de autenticación
* nuevas funciones de usuario
* nuevos puntos finales de API
* cambios de gestión de paquetes
* cambios de ejecución del agente
* migraciones de base de datos
* actualizaciones de dependencia
* cambios de Dockerfile
* cambios de tiempo de ejecución del contenedor
* cambios de proxy inverso
* cambios de cortafuegos
* cambios de gestión de secretos
* preparación del lanzamiento

Las pruebas de seguridad deben realizarse antes de publicar una versión oficial.

La documentación de seguridad debe actualizarse cada vez que cambie la línea base de seguridad verificada.

---

# Preparación del Lanzamiento

La primera versión oficial de LUMS se creará solo después de:

1. el trabajo de implementación está completo
2. la revisión de seguridad está completa
3. la revisión de documentación está completa
4. la suite de pruebas automatizadas completa pasa
5. CI pasa
6. se define la versión final
7. se crea la etiqueta Git
8. se publica la versión de GitHub

Hasta entonces, LUMS sigue siendo un proyecto en desarrollo activo.

---

# Declaración Final

LUMS está diseñado como una plataforma controlada de gestión de actualizaciones de Linux con seguridad como una preocupación arquitectónica central.

El modelo de seguridad no se basa en un único mecanismo protector.

En su lugar, la autenticación, la autorización, la validación, la ejecución controlada, la persistencia, la recuperación, el registro, el aislamiento de contenedores, las restricciones de red y las pruebas automatizadas funcionan juntas como controles en capas.

El proyecto deliberadamente favorece la aplicación explícita del lado del servidor sobre la seguridad por interfaz.

La línea base de seguridad actual se documenta de acuerdo con el estado de implementación verificado en lugar del comportamiento de desarrollo histórico.

---

**LUMS — Linux Update Management without the noise.**

`segfault // override`

