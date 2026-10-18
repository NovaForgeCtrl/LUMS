
# Documentación de seguridad de LUMS

**LUMS — Servidor de gestión de actualizaciones de Linux**

Este documento describe la arquitectura de seguridad actual, los controles de seguridad implementados, los resultados de la auditoría de seguridad, las limitaciones operativas y las decisiones de diseño relacionadas con la seguridad de LUMS.

El documento refleja el **estado actualmente implementado del sistema**. Las mejoras planificadas o futuras se identifican explícitamente como tales.

---

# Principios de seguridad

LUMS sigue un enfoque de defensa en profundidad para la gestión de actualizaciones de Linux.

El modelo de seguridad separa la autenticación administrativa, la autenticación de clientes, la autorización, la ejecución controlada de actualizaciones y el registro de auditoría.

Los objetivos principales de seguridad son:

* acceso administrativo autenticado
* autorización basada en roles
* comunicación autenticada con clientes
* ejecución controlada de actualizaciones
* protección contra la ejecución concurrente de trabajos
* trabajos de actualización recuperables
* secretos protegidos
* ejecución controlada del contenedor
* operaciones sensibles a la seguridad auditables
* manejo predecible de fallos
* pruebas de regresión de seguridad

LUMS está destinado principalmente a entornos de infraestructura controlada, laboratorio y redes internas.

No debe exponerse directamente a Internet público sin una revisión de seguridad adicional y controles de red apropiados.

---

# Arquitectura de seguridad

LUMS consta de los siguientes componentes relevantes para la seguridad:

* Interfaz de administración web
* API REST
* Base de datos SQLite
* Agente LUMS en clientes gestionados
* Backends de gestión de paquetes APT y pacman
* Mecanismos de trabajos de actualización y recuperación
* Proxy inverso HTTPS Nginx
* Contenedor Docker endurecido

El flujo básico de gestión es:

Navegador → HTTPS/Nginx → LUMS API → SQLite → Agente LUMS → Gestor de paquetes → Resultado → SQLite → UI Web

La autenticación y la autorización están deliberadamente separadas.

Una sesión autenticada válida no concede automáticamente acceso a todas las operaciones administrativas.

La autorización se aplica en el servidor. La interfaz web además oculta las funciones que no están disponibles para el rol actual, pero la visibilidad de la UI nunca se trata como una frontera de seguridad.

---

## Autenticación administrativa

Los usuarios administrativos se autentican a través de la interfaz web de LUMS.

Las contraseñas nunca se almacenan en texto plano. LUMS utiliza hashing de contraseñas basado en Argon2 para el almacenamiento de contraseñas.

Las sesiones administrativas utilizan:

* gestión de sesiones autenticadas en el servidor
* expiración de sesión
* regeneración de sesión
* protección CSRF para solicitudes de navegador que modifican el estado
* limitación de la tasa de inicio de sesión
* invalidación de sesión durante el cierre de sesión
* validación de roles en el servidor

La autenticación y la autorización siguen siendo controles de seguridad separados.

Un usuario autenticado con éxito debe poseer además el permiso requerido para las operaciones protegidas.

---

# Control de acceso basado en roles

LUMS admite actualmente tres roles de usuario web:

* `administrator`
* `operator`
* `viewer`

Las plantillas de roles se almacenan en `users.role`; los permisos individuales se almacenan en el servidor en `user_permissions`.

El servidor carga los permisos efectivos para cada cuenta autenticada. La información de permisos del lado del cliente solo controla la presentación y nunca reemplaza la autorización del servidor.

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
* ver el historial de trabajos de actualización
* usar la gestión de paquetes
* usar las funciones de mantenimiento del sistema
* gestionar usuarios
* gestionar roles de usuario
* acceder a funciones administrativas

## Operator

Los operadores pueden realizar tareas operativas de gestión de actualizaciones.

Pueden:

* ver clientes
* ver paquetes instalados y actualizaciones disponibles
* crear trabajos de actualización
* ejecutar operaciones de actualización compatibles
* ver el historial de trabajos de actualización
* usar la gestión de paquetes
* usar las funciones de mantenimiento del sistema

Los operadores no pueden:

* gestionar usuarios
* cambiar roles de usuario
* crear clientes
* deshabilitar clientes
* rotar tokens de cliente

## Viewer

Los viewers tienen acceso restringido de solo lectura.

Pueden:

* ver clientes
* ver software instalado

Las siguientes áreas de gestión están ocultas para las cuentas Viewer:

* Actualizaciones
* Trabajos de actualización
* Historial de actualizaciones
* Gestión de paquetes
* Mantenimiento del sistema

Las cuentas Viewer no pueden realizar operaciones de gestión de actualizaciones que modifiquen el estado.

El servidor aplica estas restricciones de forma independiente mediante la autenticación y las comprobaciones de permisos por usuario.

---

# Autenticación de clientes

Cada cliente LUMS gestionado utiliza un token Bearer individual.

El mecanismo de autenticación sigue el modelo:

`Authorization: Bearer <CLIENT_TOKEN>`

El servidor no almacena los tokens de cliente como valores en texto plano.

En su lugar, LUMS almacena un resumen hexadecimal SHA-256 del token de cliente.

El flujo de autenticación es:

Token de cliente → SHA-256 → Resumen del token → SQLite

La autenticación de cliente verifica el token autenticado contra el cliente registrado y además comprueba el estado relevante del cliente.

El modelo de seguridad no utiliza una dirección IP de origen como única prueba de la identidad del cliente.

Esto permite que LUMS opere en:

* redes de laboratorio privadas
* infraestructura aislada
* redes basadas en NAT
* entornos sin conexión
* redes donde las direcciones de los clientes pueden cambiar

Los tokens de cliente pueden ser rotados por administradores autorizados.

Una rotación de token genera un token de reemplazo, almacena solo su resumen, invalida el token anterior, registra la acción administrativa en el registro de auditoría y presenta el token de reemplazo una sola vez.

Los valores de token de cliente en texto plano no se escriben en los registros de auditoría.

---

# Auditoría de seguridad

La auditoría de seguridad se realiza de forma incremental.

Cada área de auditoría se revisa contra la implementación real, seguida de pruebas automatizadas, verificación aislada o verificación en producción cuando corresponda.

Áreas de auditoría actuales:

| Auditoría | Área                                    | Estado                    |
| --------- | --------------------------------------- | ------------------------- |
| #01       | Claves foráneas SQLite                  | SUPERADA                  |
| #02       | Configuración de ejecución SQLite       | SUPERADA                  |
| #03       | Manejo de timeouts de actualización     | SUPERADA                  |
| #04       | Limitación de la tasa de inicio de sesión | SUPERADA                |
| #05       | Validación de entrada de API            | SUPERADA                  |
| #06       | Revocación de sesión                    | SUPERADA                  |
| #07       | Rotación de token de cliente            | SUPERADA                  |
| #08       | Manejo de direcciones IP / Redes sin conexión | SUPERADA           |
| #09       | Recuperación de trabajos / Checkpointing | SUPERADA                 |
| #10       | Robustez de APT                         | SUPERADA                  |
| #11       | Detección de reinicio en Arch           | SUPERADA                  |
| #12       | Pruebas unitarias / Validación de resultados de API | SUPERADA    |
| #13       | Pruebas de simulación                   | SUPERADA                  |
| #14       | Integración continua                    | SUPERADA                  |
| #15       | Registro de aplicación / auditoría      | SUPERADA                  |
| #16       | Versionado / Lanzamientos               | REVISADA — ABIERTA POR DISEÑO |
| #17       | Control de acceso basado en roles       | SUPERADA                  |
| #18       | Revisión de documentación               | EN CURSO                  |

La auditoría #16 es intencionalmente diferente de los controles técnicos de seguridad anteriores.

LUMS actualmente no tiene una versión estable oficial, ni una etiqueta de lanzamiento, ni una GitHub Release. Esto es intencional porque el proyecto sigue en desarrollo activo.

La auditoría #18 permanece abierta hasta que el conjunto completo de documentación haya sido revisado y sincronizado con la implementación actual.

# Auditoría de seguridad #01

## Claves foráneas SQLite

La aplicación de claves foráneas SQLite está habilitada para las conexiones a la base de datos de la aplicación.

La aplicación habilita explícitamente:

`PRAGMA foreign_keys = ON`

Esto garantiza que se aplica la integridad referencial para las relaciones entre registros de base de datos relacionados.

La auditoría verificó:

* aplicación de claves foráneas en tiempo de ejecución
* integridad de claves foráneas
* comportamiento del ciclo de vida del cliente
* comportamiento de deshabilitación del cliente
* preservación de información histórica de trabajos
* preservación de información de auditoría

El estado del cliente se maneja de forma conservadora.

Cuando corresponde, los clientes se deshabilitan en lugar de eliminarse de una manera que destruiría información operativa histórica.

**Estado: SUPERADA**

---

# Auditoría de seguridad #02

## Configuración de ejecución SQLite

La base de datos SQLite de producción fue revisada para su configuración de tiempo de ejecución.

La configuración de producción verificada es:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

La aplicación habilita explícitamente:

`PRAGMA foreign_keys = ON`

La base de datos de producción actualmente utiliza el modo WAL.

La configuración de la base de datos se documentó según el estado real de producción verificado, en lugar de la configuración histórica de desarrollo.

El busy timeout configurado reduce los fallos inmediatos de la base de datos cuando otra transacción mantiene temporalmente la base de datos.

La configuración de claves foráneas a nivel de aplicación garantiza la integridad referencial para cada conexión a la base de datos.

La auditoría incluyó la verificación en producción de la configuración activa de SQLite.

**Estado: SUPERADA**

---

# Auditoría de seguridad #03

## Timeout de actualización y manejo de procesos

La ejecución de actualizaciones está protegida contra procesos del gestor de paquetes que bloquean indefinidamente.

El flujo de ejecución es:

Iniciar proceso
↓
Leer salida del proceso
↓
Monitorizar timeout
↓
¿Timeout alcanzado?
↓
Terminar proceso
↓
Período de gracia
↓
¿Proceso aún en ejecución?
↓
Matar proceso si es necesario
↓
Completar trabajo

La implementación utiliza manejo controlado de subprocesos para que los procesos silenciosos no puedan bloquear indefinidamente mientras esperan salida.

El manejo de timeouts se probó contra:

* procesos silenciosos
* finalización normal de procesos
* condiciones de timeout
* procesos resistentes a la terminación normal
* fallback de kill
* comportamiento de timeout a nivel de integración

El mecanismo de timeout evita que una operación de gestión de paquetes permanezca indefinidamente en un estado activo.

Los errores y las condiciones de timeout se devuelven como resultados de trabajo controlados y se registran en el estado del trabajo.

La versión actual documentada del Agente LUMS es:

`1.7.0`

**Estado: SUPERADA**

---

# Auditoría de seguridad #04

## Limitación de la tasa de inicio de sesión

Los intentos de inicio de sesión administrativo están limitados por tasa.

La política de escalado actual es:

* 5 intentos fallidos → 30 segundos
* 6 intentos fallidos → 60 segundos
* 7 intentos fallidos → 120 segundos
* 8 o más intentos fallidos → 300 segundos

El estado de limitación de tasa se persiste en SQLite.

Los fallos de inicio de sesión concurrentes utilizan bloqueo transaccional de base de datos con:

`BEGIN IMMEDIATE`

Esto evita que los fallos de autenticación concurrentes eludan el estado de limitación de tasa previsto mediante condiciones de carrera.

Una autenticación exitosa borra el estado de fallo aplicable.

La auditoría cubrió:

* comportamiento aislado de limitación de tasa
* fallos de autenticación concurrentes
* rollback de transacciones
* manejo de bloqueos de base de datos
* comportamiento de reinicio tras inicio de sesión exitoso
* eventos de auditoría de limitación de tasa
* comportamiento de inicio de sesión en producción

Por lo tanto, el limitador de tasa proporciona un control del lado del servidor contra intentos de autenticación repetidos en lugar de depender del comportamiento del lado del cliente.

**Estado: SUPERADA**

---

# Estado de la auditoría después de la parte 2

Las primeras cuatro áreas de auditoría de seguridad están completas:

| Auditoría | Área                                  | Estado |
| --------- | ------------------------------------- | ------ |
| #01       | Claves foráneas SQLite                | SUPERADA |
| #02       | Configuración de ejecución SQLite     | SUPERADA |
| #03       | Timeout de actualización / Manejo de procesos | SUPERADA |
| #04       | Limitación de la tasa de inicio de sesión | SUPERADA |

Las siguientes áreas de auditoría se documentan en las secciones posteriores:

* #05 Validación de entrada de API
* #06 Revocación de sesión
* #07 Rotación de token de cliente
* #08 Manejo de direcciones IP / Redes sin conexión
* #09 Recuperación de trabajos / Checkpointing
* #10 Robustez de APT
* #11 Detección de reinicio en Arch
* #12 Pruebas unitarias / Validación de resultados de API
* #13 Pruebas de simulación
* #14 Integración continua
* #15 Registro de aplicación / auditoría
* #16 Versionado / Lanzamientos
* #17 Control de acceso basado en roles

La auditoría #18 — Revisión de documentación — permanece abierta hasta que el conjunto completo de documentación haya sido revisado y sincronizado con la implementación actual.

# Auditoría de seguridad #05

## Validación de entrada de API

LUMS valida las entradas de API sensibles a la seguridad en el servidor.

Los valores proporcionados por el cliente no se consideran de confianza simplemente porque provengan de la interfaz web autenticada o de un cliente registrado.

La validación se aplica a los parámetros de API relevantes, incluidos:

* identificadores de clientes
* nombres de paquetes
* acciones de trabajos de actualización
* listas de paquetes
* parámetros de búsqueda
* parámetros de gestión de usuarios
* operaciones de token de cliente
* datos de resultados de trabajos

Los nombres de paquetes se validan antes de pasarlos a operaciones de gestión de paquetes.

La API de trabajos de actualización solo acepta acciones explícitamente compatibles.

Las acciones relacionadas con paquetes actualmente compatibles son:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Las acciones inesperadas se rechazan.

Las listas de paquetes se validan antes de la creación del trabajo.

Para `UPDATE_PACKAGE`, el paquete solicitado también debe estar presente en la información de actualizaciones disponibles del cliente.

Las consultas de base de datos utilizan SQL parametrizado en lugar de construir sentencias SQL a partir de entradas no confiables.

Esto evita que los valores controlados por el usuario se interpreten como sintaxis SQL.

La auditoría incluyó pruebas de entrada negativas y casos de prueba orientados a inyección SQL.

Los controles de validación también se verificaron a través de la suite de pruebas automatizadas.

**Estado: SUPERADA**

---

# Auditoría de seguridad #06

## Revocación de sesión

LUMS protege las sesiones administrativas autenticadas contra su uso continuado después del cierre de sesión.

El manejo de sesiones incluye:

* sesiones autenticadas en el servidor
* expiración de sesión
* regeneración de sesión
* invalidación en cierre de sesión
* comprobaciones de autenticación en el servidor
* validación de roles en el servidor

El cierre de sesión invalida la sesión autenticada activa.

Los endpoints de API protegidos requieren una sesión autenticada y no dependen del estado del lado del cliente para determinar si el usuario sigue autenticado.

Por lo tanto, el estado de la sesión es evaluado por el servidor para las operaciones protegidas.

Las solicitudes de navegador que modifican el estado requieren además protección CSRF.

La auditoría verificó que:

* el acceso autenticado funciona normalmente
* los endpoints protegidos rechazan solicitudes no autenticadas
* el cierre de sesión invalida la sesión activa
* una sesión previamente autenticada no puede seguir utilizando funcionalidad protegida después de la revocación
* la información de roles se evalúa en el servidor

**Estado: SUPERADA**

---

# Auditoría de seguridad #07

## Rotación de token de cliente

Cada cliente LUMS gestionado utiliza un token de autenticación individual.

Los tokens de cliente no se almacenan como valores en texto plano.

En su lugar, LUMS almacena el resumen hexadecimal SHA-256 del token de cliente.

El modelo de autenticación es:

`Authorization: Bearer <CLIENT_TOKEN>`

El servidor aplica hash al token proporcionado y compara el resumen resultante con el resumen del token de cliente registrado.

Los administradores autorizados pueden rotar el token de un cliente.

La rotación de token realiza las siguientes operaciones:

1. Generar un token de reemplazo.
2. Calcular su resumen SHA-256.
3. Reemplazar el resumen del token de cliente almacenado.
4. Invalidar el token anterior.
5. Registrar la acción administrativa en el registro de auditoría.
6. Presentar el token de reemplazo al administrador.

El token anterior no puede autenticarse después de la rotación.

Los valores de token en texto plano no se escriben en los registros de auditoría.

La auditoría verificó:

* autenticación exitosa con token
* almacenamiento del resumen del token
* rotación de token
* invalidación del token anterior
* autenticación con el token de reemplazo
* requisitos de autorización para la rotación de token
* registro de auditoría
* protección contra rotación no autorizada

La rotación de tokens de cliente está restringida a administradores.

Los operadores y viewers no pueden rotar tokens de cliente.

**Estado: SUPERADA**

---

# Auditoría de seguridad #08

## Manejo de direcciones IP y redes sin conexión

LUMS no utiliza la dirección IP de origen de un cliente como única prueba de la identidad del cliente.

La autenticación de cliente se basa en el token de cliente registrado.

Este diseño es intencional porque los clientes gestionados pueden operar en entornos donde su dirección de red cambia.

Los escenarios de despliegue compatibles incluyen:

* redes de laboratorio privadas
* redes basadas en NAT
* infraestructura aislada
* clientes con direccionamiento dinámico
* entornos sin conexión
* redes internas controladas

Por lo tanto, el servidor separa:

**Ubicación de red**

de:

**Identidad del cliente**

Un token de cliente válido identifica al cliente registrado.

La dirección de red del cliente aún puede registrarse con fines operativos y de auditoría, pero no se trata como una credencial de autenticación.

La implementación también evita suposiciones de que un cliente debe ser accesible desde una dirección fija.

Esto es particularmente importante para entornos de laboratorio e infraestructura donde la topología de red puede cambiar sin cambiar la identidad lógica del sistema gestionado.

La auditoría verificó la autenticación de cliente sin depender de una dirección IP de origen fija.

**Estado: SUPERADA**

---

# Estado de la auditoría después de la parte 3

Las siguientes áreas de auditoría de seguridad están completas:

| Auditoría | Área                                    | Estado   |
| --------- | --------------------------------------- | -------- |
| #01       | Claves foráneas SQLite                  | SUPERADA |
| #02       | Configuración de ejecución SQLite       | SUPERADA |
| #03       | Timeout de actualización / Manejo de procesos | SUPERADA |
| #04       | Limitación de la tasa de inicio de sesión | SUPERADA |
| #05       | Validación de entrada de API            | SUPERADA |
| #06       | Revocación de sesión                    | SUPERADA |
| #07       | Rotación de token de cliente            | SUPERADA |
| #08       | Manejo de direcciones IP / Redes sin conexión | SUPERADA |

La siguiente sección cubre:

* #09 Recuperación de trabajos / Checkpointing
* #10 Robustez de APT
* #11 Detección de reinicio en Arch
* #12 Pruebas unitarias / Validación de resultados de API

# Auditoría de seguridad #09

## Recuperación de trabajos y checkpointing

Los trabajos de actualización de LUMS están diseñados para recuperarse de forma segura de ejecuciones interrumpidas.

Los trabajos de actualización mantienen estado persistente en la base de datos SQLite.

Las operaciones individuales de paquetes se rastrean por separado del estado general del trabajo.

Esto permite al agente determinar qué operaciones de paquetes ya se han completado con éxito antes de reanudar un trabajo interrumpido.

Durante la recuperación, las operaciones de paquetes completadas con éxito no se ejecutan de nuevo.

Por lo tanto, la lógica de recuperación sigue el principio:

`Estado persistente del trabajo → Determinar trabajo completado → Omitir elementos completados → Continuar trabajo restante`

Esto reduce el riesgo de operaciones de paquetes repetidas innecesariamente después de:

* interrupción del agente
* terminación del proceso
* reinicio del sistema
* fallo temporal de comunicación
* reinicio del contenedor
* otras interrupciones de ejecución

La auditoría verificó el comportamiento de recuperación y checkpointing de trabajos interrumpidos.

La recuperación se probó con trabajos que contenían múltiples operaciones de paquetes y con elementos de paquetes previamente exitosos.

La auditoría confirmó que el trabajo completado se preserva y el trabajo restante puede continuar sin repetir innecesariamente operaciones exitosas.

**Estado: SUPERADA**

---

# Auditoría de seguridad #10

## Robustez de APT

Las operaciones de paquetes basadas en Debian se ejecutan a través de la capa de gestión de paquetes de LUMS.

Las operaciones de actualización relacionadas con APT se revisaron para la detección fiable del estado del gestor de paquetes y los resultados de actualización.

La implementación contempla casos en los que los comandos de gestión de paquetes pueden devolver éxito mientras requieren una interpretación adicional de su salida o del estado resultante del sistema.

La detección de actualizaciones de APT se endureció para evitar depender de una única condición simplista de salida de comando.

La auditoría incluyó pruebas de:

* operaciones normales de APT
* actualizaciones de paquetes disponibles
* instalación de paquetes
* eliminación de paquetes
* ejecución de trabajos de actualización
* manejo de resultados de APT
* comportamiento de detección de actualizaciones

El endurecimiento correspondiente se confirmó como:

`c76f331 security: harden apt update detection`

El objetivo es garantizar que LUMS no informe incorrectamente del estado de gestión de paquetes basándose únicamente en una salida de comando incompleta o ambigua.

**Estado: SUPERADA**

---

# Auditoría de seguridad #11

## Detección de reinicio en Arch Linux

Las operaciones de paquetes de Arch Linux pueden resultar en un estado del sistema donde se requiere o recomienda un reinicio.

Por lo tanto, LUMS evalúa el estado resultante del sistema después de las operaciones relevantes de gestión de paquetes.

El agente distingue la finalización normal de una operación de paquete de las situaciones en las que se requiere un reinicio.

El estado de reinicio se reporta al servidor LUMS como parte del resultado del trabajo.

Esto permite que la interfaz de gestión distinga entre:

* operación de paquete exitosa
* operación exitosa con requisito de reinicio
* operación fallida

La auditoría verificó la detección de reinicio en Arch Linux utilizando la ruta real de ejecución del gestor de paquetes.

La implementación se probó contra condiciones de reinicio requerido y condiciones de finalización normal.

**Estado: SUPERADA**

---

# Auditoría de seguridad #12

## Pruebas unitarias y validación de resultados de API

El comportamiento sensible a la seguridad está cubierto por pruebas automatizadas.

La suite de pruebas incluye cobertura para autenticación, autorización, validación de API, trabajos de actualización, gestión de paquetes, autenticación de clientes y manejo de resultados.

La ruta de resultados del agente al servidor fue revisada específicamente para garantizar que los resultados de los trabajos no puedan alterar arbitrariamente estado no relacionado del servidor.

El procesamiento de resultados valida la información enviada antes de aplicar cambios de estado al trabajo de actualización correspondiente.

La validación cubre los campos de resultado relevantes y las relaciones de trabajo esperadas.

Esto evita que un cliente autenticado seleccione libremente trabajos no relacionados o inyecte estado arbitrario en la base de datos de trabajos de actualización.

La suite de pruebas de seguridad también cubre casos negativos y no autorizados.

Ejecute la suite de pruebas automatizadas completa desde la raíz del repositorio con
`./.venv-test/bin/pytest -q`. El número de pruebas cambia con el tiempo; utilice el
resultado de la ejecución actual en lugar de un recuento fijo en este documento.

Los controles de seguridad relevantes se verificaron adicionalmente mediante ejecuciones de pruebas enfocadas durante la auditoría.

**Estado: SUPERADA**

---

# Estado de la auditoría después de la parte 4

Las siguientes áreas de auditoría de seguridad están completas:

| Auditoría | Área                                    | Estado   |
| --------- | --------------------------------------- | -------- |
| #01       | Claves foráneas SQLite                  | SUPERADA |
| #02       | Configuración de ejecución SQLite       | SUPERADA |
| #03       | Timeout de actualización / Manejo de procesos | SUPERADA |
| #04       | Limitación de la tasa de inicio de sesión | SUPERADA |
| #05       | Validación de entrada de API            | SUPERADA |
| #06       | Revocación de sesión                    | SUPERADA |
| #07       | Rotación de token de cliente            | SUPERADA |
| #08       | Manejo de direcciones IP / Redes sin conexión | SUPERADA |
| #09       | Recuperación de trabajos / Checkpointing | SUPERADA |
| #10       | Robustez de APT                         | SUPERADA |
| #11       | Detección de reinicio en Arch           | SUPERADA |
| #12       | Pruebas unitarias / Validación de resultados de API | SUPERADA |

La siguiente sección cubre:

* #13 Pruebas de simulación
* #14 Integración continua
* #15 Registro de aplicación / auditoría
* #16 Versionado / Lanzamientos

# Auditoría de seguridad #13

## Pruebas de simulación

LUMS proporciona un mecanismo de simulación para probar flujos de trabajo de gestión de actualizaciones sin realizar la operación correspondiente de gestión de paquetes en el sistema gestionado.

La simulación se implementa en la capa de ejecución del agente.

Cuando la simulación está habilitada, las operaciones de gestión de paquetes se representan y procesan sin aplicar el cambio de paquete solicitado al sistema operativo.

Esto permite probar el comportamiento de los trabajos de actualización sin modificar intencionalmente el sistema gestionado.

Las pruebas de simulación cubren rutas relevantes de gestión de actualizaciones, incluidos:

* instalación de paquetes
* eliminación de paquetes
* actualizaciones de paquetes
* actualizaciones del sistema
* ejecución de trabajos
* reporte de resultados
* finalización exitosa
* manejo de fallos

El mecanismo de simulación se utilizó durante la auditoría de seguridad para verificar la creación de trabajos, la ejecución del agente, el manejo de resultados y las transiciones de estado del lado del servidor independientemente de las modificaciones reales de paquetes.

El modo de simulación es un mecanismo de prueba y no reemplaza los controles de autorización de las operaciones normales de actualización.

**Estado: SUPERADA**

---

# Auditoría de seguridad #14

## Integración continua

LUMS utiliza pruebas automatizadas para detectar regresiones de seguridad y funcionales antes de que las modificaciones se consideren completas.

El proceso de CI ejecuta la suite de pruebas automatizadas contra el proyecto.

El entorno de pruebas verifica la aplicación y la funcionalidad sensible a la seguridad de forma independiente del contenedor de producción.

El proceso de CI incluye validación de:

* autenticación
* autorización
* RBAC
* comportamiento de API
* manejo de trabajos de actualización
* comportamiento de gestión de paquetes
* autenticación de clientes
* validación de resultados de trabajos
* manejo de errores sensibles a la seguridad

La auditoría de CI se revisó después de los cambios de endurecimiento de seguridad.

La suite de pruebas final verificada se completó con éxito.

El recuento de pruebas cambia a medida que el proyecto evoluciona. La CI proporciona una barrera de regresión automatizada para cambios de aplicación relevantes para la seguridad.

**Estado: SUPERADA**

---

# Auditoría de seguridad #15

## Registro de aplicación y auditoría

LUMS registra eventos administrativos y operativos sensibles a la seguridad a través del registro de auditoría a nivel de aplicación.

El registro de auditoría está diseñado para proporcionar un historial operativo sin almacenar credenciales sensibles.

Las acciones sensibles a la seguridad relevantes incluyen eventos como:

* eventos de seguridad relacionados con la autenticación
* acciones administrativas
* gestión de clientes
* operaciones de tokens de cliente
* creación de trabajos de actualización
* ejecución de trabajos de actualización
* fallos relevantes para la seguridad

El material de credenciales sensibles se excluye de los registros de auditoría.

En particular:

* las contraseñas no se registran
* los tokens de cliente en texto plano no se registran
* los valores secretos no se escriben intencionalmente en los registros de auditoría

Los registros de auditoría se asocian con el contexto administrativo u operativo relevante cuando corresponde.

La implementación del registro de auditoría se revisó para:

* cobertura de eventos sensibles a la seguridad
* exclusión de credenciales
* trazabilidad administrativa
* manejo de fallos
* persistencia de información de auditoría relevante

El sistema de registro está destinado a soportar tanto la solución de problemas operativos como la investigación de seguridad.

**Estado: SUPERADA**

---

# Auditoría de seguridad #16

## Versionado y lanzamientos

El versionado y la gestión de lanzamientos se revisaron como parte de la auditoría de seguridad.

LUMS está actualmente en desarrollo activo y aún no tiene un lanzamiento estable oficial.

Por lo tanto, el estado actual del repositorio tiene intencionalmente:

* sin versión de lanzamiento estable oficial
* sin etiqueta de lanzamiento
* sin GitHub Release

Las versiones actuales de los componentes incluyen:

* LUMS Agent: `1.7.0`
* LUMS Watcher: `1.2.1`

Actualmente no existe un número de versión formal único que represente la aplicación LUMS completa.

Esta es una decisión intencional del estado del proyecto, no una omisión accidental.

El proceso de lanzamiento planificado es:

1. Completar el trabajo de implementación.
2. Completar la revisión de seguridad.
3. Revisar y sincronizar la documentación.
4. Completar la suite de pruebas automatizadas completa.
5. Verificar la CI.
6. Definir la versión de lanzamiento.
7. Crear la etiqueta Git correspondiente.
8. Publicar la GitHub Release.
9. Preservar el lanzamiento como la línea base documentada.

No se crea un lanzamiento oficial solo porque la auditoría de seguridad alcance un número de auditoría particular.

La creación del lanzamiento tendrá lugar solo después de que el trabajo restante de implementación y documentación haya sido completado.

**Estado: REVISADA — ABIERTA POR DISEÑO**

---

# Estado de la auditoría después de la parte 5

Las siguientes áreas de auditoría de seguridad están completas:

| Auditoría | Área                                    | Estado                    |
| --------- | --------------------------------------- | ------------------------- |
| #01       | Claves foráneas SQLite                  | SUPERADA                  |
| #02       | Configuración de ejecución SQLite       | SUPERADA                  |
| #03       | Timeout de actualización / Manejo de procesos | SUPERADA              |
| #04       | Limitación de la tasa de inicio de sesión | SUPERADA                |
| #05       | Validación de entrada de API            | SUPERADA                  |
| #06       | Revocación de sesión                    | SUPERADA                  |
| #07       | Rotación de token de cliente            | SUPERADA                  |
| #08       | Manejo de direcciones IP / Redes sin conexión | SUPERADA           |
| #09       | Recuperación de trabajos / Checkpointing | SUPERADA                 |
| #10       | Robustez de APT                         | SUPERADA                  |
| #11       | Detección de reinicio en Arch           | SUPERADA                  |
| #12       | Pruebas unitarias / Validación de resultados de API | SUPERADA    |
| #13       | Pruebas de simulación                   | SUPERADA                  |
| #14       | Integración continua                    | SUPERADA                  |
| #15       | Registro de aplicación / auditoría      | SUPERADA                  |
| #16       | Versionado / Lanzamientos               | REVISADA — ABIERTA POR DISEÑO |

El área de auditoría técnica numerada restante es:

* #17 Control de acceso basado en roles

La revisión de documentación se rastrea por separado como:

* #18 Revisión de documentación — EN CURSO

# Auditoría de seguridad #17

## Control de acceso basado en roles

LUMS combina plantillas de roles con permisos asignados individualmente. Las plantillas compatibles son `administrator`, `operator` y `viewer`; elegir una plantilla selecciona sus permisos predeterminados, que un administrador puede personalizar para cada cuenta.

El rol sigue siendo metadatos de la cuenta. Las rutas protegidas autorizan contra el conjunto de permisos almacenado en el servidor de la cuenta, no contra la etiqueta del rol. La interfaz oculta las funciones no disponibles por usabilidad, mientras que el servidor sigue siendo la frontera de seguridad.

---

## Modelo de permisos RBAC

| Permiso           | Acceso concedido |
| ----------------- | ---------------- |
| `clients.view`    | Ver clientes e información del sistema |
| `software.view`   | Ver software instalado |
| `updates.view`    | Ver actualizaciones disponibles, trabajos e historial |
| `packages.search` | Buscar en repositorios de paquetes |
| `jobs.manage`     | Crear operaciones de paquetes y trabajos de actualización |
| `clients.manage`  | Registrar/eliminar clientes y rotar tokens de cliente |
| `users.manage`    | Crear usuarios y gestionar roles y permisos |

Las plantillas de roles predeterminadas son:

| Plantilla       | Permisos predeterminados |
| --------------- | ------------------------ |
| `administrator` | Todos los permisos |
| `operator`      | Visibilidad de clientes/software/actualizaciones, búsqueda de paquetes y gestión de trabajos |
| `viewer`        | Visibilidad de clientes y software instalado |

Los permisos relacionados con clientes requieren `clients.view`. `jobs.manage` también requiere `updates.view`. La UI carga los permisos de la cuenta autenticada y omite los controles que el usuario no puede usar; las comprobaciones del servidor aplican de forma independiente las mismas concesiones.

---

## Aplicación de la autorización

Las operaciones protegidas utilizan autenticación y comprobaciones de permisos del lado del servidor.

El modelo de autorización sigue el principio:

`Autenticar → Cargar permisos del usuario → Autorizar operación → Ejecutar`

La autenticación por sí sola no es suficiente para acceder a operaciones privilegiadas.

Las operaciones que modifican el estado requieren además protección CSRF cuando corresponda.

Los ejemplos de operaciones administrativas protegidas incluyen:

* creación de trabajos de actualización
* instalación de paquetes
* eliminación de paquetes
* actualizaciones de paquetes
* actualizaciones del sistema
* operaciones de gestión de paquetes
* creación de clientes
* deshabilitación de clientes
* rotación de tokens de cliente
* creación de usuarios
* funciones de gestión de usuarios

Los endpoints protegidos definen explícitamente el permiso requerido para la operación correspondiente.

Un permiso faltante es rechazado por el servidor incluso si el usuario construye manualmente la solicitud HTTP correspondiente.

Esto evita eludir el modelo RBAC llamando directamente a un endpoint de API que está oculto en la interfaz web.

---

## Restricciones de Viewer

La plantilla Viewer está intencionalmente restringida por su conjunto de permisos predeterminado.

Para las cuentas sin las concesiones correspondientes, la interfaz del cliente no expone:

* Actualizaciones
* Trabajos de actualización
* Historial de actualizaciones
* Gestión de paquetes
* Mantenimiento del sistema

El servidor además impide que las cuentas sin las concesiones correspondientes realicen operaciones protegidas.

La interfaz JavaScript no carga datos de gestión de actualizaciones sin `updates.view`.

Esto reduce la exposición innecesaria de información operativa mientras se mantiene la autorización del servidor como el control de seguridad real.

El software instalado sigue disponible para las cuentas Viewer como una función de información de solo lectura.

---

## Gestión administrativa de usuarios

La gestión de usuarios requiere el permiso `users.manage`.

Los usuarios con ese permiso pueden crear cuentas sin permisos y luego asignar concesiones individuales o aplicar una plantilla de rol en el editor de permisos. Las plantillas de roles tienen descripciones que explican sus concesiones predeterminadas.

Los gestores de usuarios autorizados pueden guardar una nota interna por cuenta. Las notas están limitadas a 2.000 caracteres, no se incluyen en los detalles del registro de auditoría y no son visibles para el propietario de la cuenta.

La creación de usuarios incluye:

* validación del nombre de usuario
* validación del rol
* validación de la contraseña
* hashing de contraseñas con Argon2
* detección de usuarios duplicados
* registro de auditoría
* protección CSRF
* autorización del servidor

Los endpoints de gestión de usuarios no son accesibles sin `users.manage`.

El servidor rechaza permisos desconocidos y combinaciones de dependencias no válidas. Al menos una cuenta activa debe conservar `users.manage`; los cambios que eliminarían al último gestor de usuarios son rechazados.

Las contraseñas nunca se almacenan en texto plano.

---

## Migración de base de datos RBAC

La información de la plantilla de rol permanece en el registro de la base de datos del usuario. Las concesiones individuales se almacenan en la tabla `user_permissions` con una clave foránea al usuario. La migración `003-user-permissions` crea esa tabla y siembra las cuentas existentes desde su plantilla de rol actual, preservando su acceso durante la transición. La migración `004-user-admin-notes` añade el campo privado `users.admin_note`; las cuentas existentes reciben una nota vacía. La migración `005-backup-permission` concede `backups.manage` a las cuentas Administrator existentes.

La creación de copias de seguridad de base de datos requiere `backups.manage`; la plantilla Administrator incluye este permiso por defecto. El servidor escribe las copias de seguridad en línea de SQLite solo en el `LUMS_BACKUP_DIR` configurado en el servidor; no acepta rutas del sistema de archivos desde el navegador. Los archivos de copia de seguridad se crean con permisos exclusivos del propietario y se verifica su integridad antes de la publicación.

---

## Pruebas de seguridad RBAC

El comportamiento RBAC está cubierto por pruebas automatizadas.

Las pruebas incluyen:

* autorización de Administrator
* autorización de Operator
* restricciones de Viewer
* acceso a API protegida
* operaciones no autorizadas
* restricciones de gestión de clientes
* restricciones de trabajos de actualización
* restricciones de gestión de usuarios
* visibilidad de la página del cliente
* comportamiento de interfaz específico de permisos

Las pruebas RBAC cubren los valores predeterminados de las plantillas de roles, permisos personalizados, dependencias de permisos y autorización del servidor. La verificación en producción debe incluir cuentas con permisos personalizados, así como las plantillas predeterminadas Administrator, Operator y Viewer.

---

## Resultado de seguridad RBAC

La implementación RBAC proporciona autorización en capas:

1. La autenticación establece la identidad del usuario.
2. El servidor carga los permisos del usuario.
3. Las rutas protegidas aplican el permiso requerido.
4. La protección CSRF se aplica a los cambios de estado relevantes del navegador.
5. La interfaz web oculta la funcionalidad no disponible.
6. Las pruebas automatizadas verifican las fronteras de autorización.

Por lo tanto, la interfaz no proporciona el mecanismo de autorización por sí misma.

El servidor sigue siendo la frontera de seguridad autoritativa.

**Estado: SUPERADA**

# Auditoría de seguridad #18

## Revisión de documentación

La documentación de seguridad se revisa contra el sistema LUMS actualmente implementado.

El propósito de esta revisión es garantizar que la documentación de seguridad describa la implementación real en lugar de un estado de desarrollo anterior.

La revisión cubre:

* autenticación
* autorización
* RBAC
* autenticación de clientes
* manejo de tokens
* manejo de sesiones
* protección CSRF
* limitación de tasa
* configuración de SQLite
* ejecución de actualizaciones
* recuperación de trabajos
* gestión de paquetes
* endurecimiento del contenedor
* exposición de red
* manejo de secretos
* seguridad de dependencias y construcción
* permisos del sistema de archivos
* registro de aplicación y auditoría
* versionado y manejo de lanzamientos
* pruebas de seguridad automatizadas

La documentación debe distinguir entre:

* controles implementados
* comportamiento de producción verificado
* mejoras planificadas
* decisiones del proyecto intencionalmente abiertas

Los detalles de implementación históricos no deben presentarse como configuración de producción actual.

En particular, la documentación refleja la configuración de producción actual de SQLite en lugar de la configuración WAL actual.

El tiempo de ejecución de producción actual se documenta como:

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* `PRAGMA foreign_keys = ON` a nivel de aplicación

El comportamiento actual de RBAC de Viewer también se documenta según la interfaz de producción implementada.

Los usuarios Viewer tienen acceso a:

* información de clientes
* software instalado

Los usuarios Viewer no tienen acceso a:

* Actualizaciones
* Trabajos de actualización
* Historial de actualizaciones
* Gestión de paquetes
* Mantenimiento del sistema

La revisión de documentación también elimina o reemplaza referencias obsoletas a recuentos de pruebas anteriores, estados de migración, configuraciones de despliegue y comportamiento exclusivo de desarrollo.

**Estado: EN CURSO**

---

# Endurecimiento de seguridad adicional

La auditoría de seguridad numerada cubre los controles principales de seguridad de la aplicación.

Se realizó un endurecimiento adicional después de la secuencia de auditoría original y forma parte de la línea base de seguridad actual.

Estos controles se documentan aquí porque representan propiedades de seguridad importantes del despliegue actual.

---

## Endurecimiento del contenedor

El contenedor LUMS de producción se ejecuta con una configuración de Docker endurecida.

El contenedor de producción utiliza:

* usuario de aplicación no root
* sistema de archivos raíz de solo lectura
* capacidades de Linux eliminadas
* `no-new-privileges`
* sistemas de archivos temporales restringidos
* montaje de secreto de solo lectura
* volumen dedicado persistente de datos de aplicación
* política de reinicio
* publicación en el host del puerto de aplicación solo en loopback

Por lo tanto, el sistema de archivos raíz de la aplicación no es escribible durante el funcionamiento normal.

Las ubicaciones escribibles están explícitamente limitadas a las ubicaciones requeridas por la aplicación.

El contenedor de producción se inspeccionó de forma independiente para verificar la configuración efectiva en tiempo de ejecución.

El tiempo de ejecución endurecido también se probó verificando que:

* las escrituras en el sistema de archivos de la aplicación fallan
* `/tmp` permanece disponible cuando es necesario
* `/var/lib/lums` permanece escribible
* el archivo del secreto permanece de solo lectura
* la aplicación permanece operativa

---

## Exposición de red

El puerto de la aplicación LUMS no está expuesto directamente a la LAN.

El puerto de la aplicación Docker está vinculado a la interfaz de loopback:

`127.0.0.1:5050`

El acceso externo se proporciona a través de Nginx.

El host de producción expone los servicios de red previstos a través del firewall y el proxy inverso.

Se verificó el despliegue para evitar el acceso remoto directo al puerto interno de la aplicación Docker.

El firewall utiliza un modelo de denegación por defecto para el tráfico entrante y enrutado.

Los servicios previstos accesibles desde el exterior son:

* SSH
* HTTP
* HTTPS

Las solicitudes HTTP son redirigidas a HTTPS por el servidor web.

El sitio predeterminado de Nginx se eliminó para que el contenido predeterminado no relacionado no quede expuesto.

---

## Seguridad del transporte

El acceso web administrativo se proporciona a través de HTTPS.

HTTP se redirige a HTTPS.

El endpoint TLS lo maneja Nginx en lugar de la aplicación Flask/Gunicorn directamente.

Esto mantiene la seguridad del transporte y el servicio de la aplicación separados.

Por lo tanto, el puerto interno de la aplicación Gunicorn no está destinado a ser un endpoint HTTP público.

El despliegue actual está destinado a infraestructura interna controlada.

Un despliegue futuro con exposición directa a Internet público requeriría una revisión de seguridad adicional.

---

## Secretos y configuración

Los secretos de producción no se almacenan en el árbol de código fuente de la aplicación.

La clave secreta de LUMS se proporciona a través de un archivo secreto protegido.

El contenedor de producción recibe el secreto a través de:

`/run/secrets/lums_secret`

El archivo del secreto está montado en modo de solo lectura.

La aplicación lee el secreto a través del mecanismo de archivo secreto configurado.

Se revisó el manejo del repositorio y del contexto de construcción de Docker para evitar la inclusión accidental de:

* archivos de base de datos
* archivos de copia de seguridad
* archivos secretos
* claves privadas
* certificados
* registros de tiempo de ejecución
* artefactos de copia de seguridad locales

El repositorio también ignora los patrones comunes de copia de seguridad temporal utilizados durante el desarrollo.

---

## Seguridad de dependencias y construcción

La imagen Docker de producción utiliza un digest de imagen base Python fijado.

Las dependencias de tiempo de ejecución de producción están fijadas explícitamente a versiones.

El conjunto actual de dependencias de producción incluye:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

El contexto de construcción de Docker está restringido mediante `.dockerignore`.

Se compararon construcciones de producción repetidas durante la auditoría.

Los metadatos relevantes de dependencias y paquetes permanecieron consistentes entre construcciones repetidas, aparte de las diferencias esperadas en el bytecode Python generado.

Esto proporciona una línea base reproducible para la imagen de producción mientras se mantiene limitado el contexto de construcción.

---

## Permisos del sistema de archivos y de tiempo de ejecución

La aplicación de producción se ejecuta como el usuario dedicado `lums` en lugar de root.

Los datos persistentes de la aplicación se almacenan en el volumen de datos LUMS dedicado.

El sistema de archivos raíz de la aplicación es de solo lectura.

El acceso de escritura en tiempo de ejecución está restringido a las ubicaciones explícitamente requeridas.

Se verificó que el tiempo de ejecución de producción rechaza escrituras no autorizadas en el sistema de archivos de la aplicación.

Esto reduce el impacto de modificaciones de archivos accidentales o maliciosas dentro del contenedor de la aplicación.

---

# Conclusión de la auditoría de seguridad

La implementación actual de LUMS ha sido sometida a una revisión de seguridad amplia que cubre:

* autenticación
* autorización
* RBAC
* seguridad de sesiones
* protección CSRF
* limitación de la tasa de inicio de sesión
* seguridad de tokens de cliente
* validación de API
* resistencia a inyección SQL
* integridad de SQLite
* ejecución de actualizaciones
* manejo de timeouts
* recuperación de trabajos
* robustez de gestión de paquetes
* validación de resultados
* simulación
* integración continua
* registro de auditoría
* endurecimiento del contenedor
* exposición de red
* seguridad del transporte
* manejo de secretos
* permisos del sistema de archivos
* seguridad de dependencias y construcción

Los resultados de la auditoría numerada son:

| Auditoría | Área                                    | Estado                    |
| --------- | --------------------------------------- | ------------------------- |
| #01       | Claves foráneas SQLite                  | SUPERADA                  |
| #02       | Configuración de ejecución SQLite       | SUPERADA                  |
| #03       | Timeout de actualización / Manejo de procesos | SUPERADA              |
| #04       | Limitación de la tasa de inicio de sesión | SUPERADA                |
| #05       | Validación de entrada de API            | SUPERADA                  |
| #06       | Revocación de sesión                    | SUPERADA                  |
| #07       | Rotación de token de cliente            | SUPERADA                  |
| #08       | Manejo de direcciones IP / Redes sin conexión | SUPERADA           |
| #09       | Recuperación de trabajos / Checkpointing | SUPERADA                 |
| #10       | Robustez de APT                         | SUPERADA                  |
| #11       | Detección de reinicio en Arch           | SUPERADA                  |
| #12       | Pruebas unitarias / Validación de resultados de API | SUPERADA    |
| #13       | Pruebas de simulación                   | SUPERADA                  |
| #14       | Integración continua                    | SUPERADA                  |
| #15       | Registro de aplicación / auditoría      | SUPERADA                  |
| #16       | Versionado / Lanzamientos               | REVISADA — ABIERTA POR DISEÑO |
| #17       | Control de acceso basado en roles       | SUPERADA                  |
| #18       | Revisión de documentación               | EN CURSO                  |

Los controles técnicos de seguridad revisados en las auditorías #01–#15 y #17 han superado la revisión.

La auditoría #16 permanece intencionalmente abierta porque LUMS aún no ha alcanzado su primer lanzamiento estable oficial.

La auditoría #18 permanece abierta hasta que la documentación completa del proyecto haya sido revisada y sincronizada con el estado final de implementación.

Ningún resultado de auditoría de seguridad debe interpretarse como una garantía de que LUMS está libre de vulnerabilidades.

La seguridad es un proceso continuo.

Los cambios en la aplicación, el agente, las dependencias, la configuración del contenedor, la exposición de red, el modelo de autenticación o la arquitectura de despliegue deben activar otra revisión de seguridad de los controles afectados.

---

# Línea base de seguridad

La línea base de seguridad actual se basa en la implementación verificada y el estado de despliegue en producción.

La línea base incluye:

* autenticación en el servidor
* RBAC en el servidor
* hashing de contraseñas con Argon2
* resúmenes SHA-256 de tokens de cliente
* protección CSRF
* limitación de la tasa de inicio de sesión
* SQL parametrizado
* entrada de API validada
* ejecución controlada del gestor de paquetes
* recuperación de trabajos de actualización
* registro de auditoría
* tiempo de ejecución Docker endurecido
* HTTPS a través de Nginx
* exposición del puerto de aplicación solo en loopback
* restricciones de firewall
* secretos de producción protegidos
* dependencias de producción fijadas
* permisos de sistema de archivos restringidos
* pruebas de seguridad automatizadas

Los cambios futuros deben preservar estas propiedades a menos que un cambio arquitectónico deliberado las reemplace con un control equivalente o más fuerte.

---

# Mantenimiento de seguridad

Los controles de seguridad deben revalidarse cuando se introducen cambios significativos.

Los ejemplos incluyen:

* cambios de autenticación
* nuevos roles de usuario
* nuevos endpoints de API
* cambios de gestión de paquetes
* cambios de ejecución del agente
* migraciones de base de datos
* actualizaciones de dependencias
* cambios en el Dockerfile
* cambios en el tiempo de ejecución del contenedor
* cambios en el proxy inverso
* cambios en el firewall
* cambios en la gestión de secretos
* preparación de lanzamiento

Las pruebas de seguridad deben realizarse antes de publicar un lanzamiento oficial.

La documentación de seguridad debe actualizarse siempre que cambie la línea base de seguridad verificada.

---

# Preparación para el lanzamiento

El primer lanzamiento oficial de LUMS se creará solo después de que:

1. el trabajo de implementación esté completo
2. la revisión de seguridad esté completa
3. la revisión de documentación esté completa
4. la suite de pruebas automatizadas completa pase
5. la CI pase
6. la versión final esté definida
7. la etiqueta Git esté creada
8. la GitHub Release esté publicada

Hasta entonces, LUMS sigue siendo un proyecto en desarrollo activo.

---

# Declaración final

LUMS está diseñado como una plataforma controlada de gestión de actualizaciones de Linux con la seguridad como una preocupación arquitectónica central.

El modelo de seguridad no depende de un único mecanismo de protección.

En su lugar, la autenticación, autorización, validación, ejecución controlada, persistencia, recuperación, registro, aislamiento del contenedor, restricciones de red y pruebas automatizadas trabajan juntas como controles en capas.

El proyecto favorece deliberadamente la aplicación explícita en el servidor sobre la seguridad por interfaz.

La línea base de seguridad actual se documenta según el estado verificado de implementación en lugar del comportamiento histórico de desarrollo.

---

**LUMS — Gestión de actualizaciones de Linux sin el ruido.**

`segfault // override`
