# LUMS — Guía de administración

> **Gestión de actualizaciones de Linux sin el ruido.**

Esta guía describe la administración y operación diarias de LUMS después de que el servidor y los clientes hayan sido instalados.

Se centra en las tareas administrativas realizadas a través de la interfaz web de LUMS y en las tareas operativas controladas en el servidor LUMS y los clientes gestionados.

Los procedimientos de instalación están documentados por separado en `install.md`.

Los procedimientos de solución de problemas están documentados por separado en `troubleshooting.md`.

La arquitectura de seguridad y la información de auditoría están documentadas por separado en `security.md`.

---

## Primeros pasos: Administración diaria

Esta guía está dirigida a la persona responsable de una instalación existente de LUMS. Las secciones técnicas detalladas se mantienen en inglés. Comience con estos términos:

* **Cuenta de usuario:** determina lo que una persona puede hacer en la interfaz web de LUMS. No comparta cuentas; dé a cada persona su propia cuenta.
* **Cliente:** un ordenador Linux gestionado. Su token de cliente es un secreto y no es lo mismo que una contraseña de cuenta web.
* **Trabajo de actualización:** una operación solicitada que el agente recupera y ejecuta usando APT o pacman en el ordenador de destino. Verifique el destino y los paquetes antes de iniciarlo.
* **Copia de seguridad:** una copia separada y verificada de la base de datos. Una copia en el mismo volumen Docker no protege contra la pérdida de ese volumen.
* **Actualización:** reemplaza la versión del contenedor, no la base de datos. Una actualización normal no debe eliminar ni recrear `lums-data`.

### Lista de comprobación segura antes de hacer un cambio

1. Compruebe si hay trabajos de actualización en ejecución y si se necesita una ventana de mantenimiento.
2. Confirme que existe una copia de seguridad reciente y utilizable de la base de datos.
3. Registre la imagen en ejecución, la configuración del contenedor y las rutas de datos.
4. Construya y pruebe la nueva imagen antes de detener el contenedor activo.
5. Reemplace el contenedor con los mismos montajes de datos, secretos y copias de seguridad y las mismas opciones de seguridad.
6. Compruebe el estado del contenedor, los registros, el inicio de sesión HTTPS y los datos después del arranque.
7. Mantenga el contenedor antiguo como opción de reversión hasta que se haya verificado la nueva versión.

**No ejecute** `docker volume rm lums-data`, `docker system prune --volumes` u otros comandos de eliminación como parte de una actualización normal. Pueden eliminar datos de forma permanente. Si no está seguro de qué contenedor o ruta está activo, deténgase e inspeccione primero la configuración actual; no copie un comando de ejemplo sin comprobarlo.

---

## 1. Descripción general de la administración

LUMS proporciona administración centralizada del inventario de software de Linux, actualizaciones disponibles, operaciones de paquetes, trabajos de actualización, clientes gestionados, usuarios e historial operativo.

La interfaz administrativa proporciona tres plantillas de roles:

* **Administrator**
* **Operator**
* **Viewer**

Cuando se crea una cuenta, el rol seleccionado rellena un conjunto recomendado de permisos. Los administradores pueden ajustar esos permisos por usuario; los permisos guardados, en lugar de la etiqueta del rol, determinan el acceso.

LUMS también separa las operaciones administrativas del lado del servidor de la ejecución de paquetes del lado del cliente.

El flujo operativo normal es:

```text
Administrator / Operator
        │
        ▼
   LUMS Web UI
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
   Managed Client
        │
        ▼
 APT / pacman / system
        │
        ▼
      Result
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
    Web Interface
```

El servidor LUMS no ejecuta directamente comandos de gestión de paquetes en los clientes gestionados.

Las operaciones de paquetes son ejecutadas por el agente LUMS instalado en el sistema gestionado.

---

## 2. Responsabilidades administrativas

La administración de LUMS se puede dividir en varias áreas.

### Administración de usuarios

Los administradores gestionan:

* usuarios de LUMS
* roles de usuario
* estado de la cuenta
* acceso administrativo

La gestión de usuarios requiere el permiso `users.manage`.

La plantilla Administrator incluye este permiso por defecto.

Los Operators y Viewers no lo reciben por defecto.

---

### Administración de clientes

Los administradores gestionan:

* clientes registrados
* estado de los clientes
* autenticación de clientes
* tokens de cliente
* rotación de tokens
* habilitación y deshabilitación de clientes

La administración de clientes requiere el permiso `clients.manage` porque la autenticación de clientes determina qué sistemas pueden reportar a LUMS.

---

### Administración de actualizaciones

Las plantillas Administrator y Operator conceden permisos para:

* ver actualizaciones disponibles
* crear trabajos de actualización
* ejecutar operaciones de paquetes
* revisar el historial de actualizaciones
* gestionar paquetes individuales
* realizar actualizaciones del sistema

La plantilla Viewer es de solo lectura y no puede realizar operaciones de actualización.

---

### Administración de paquetes

LUMS admite operaciones de gestión de paquetes a través del gestor de paquetes nativo del cliente.

Los backends de gestión de paquetes admitidos actualmente incluyen:

* **APT/dpkg** para sistemas basados en Debian
* **pacman** para Arch Linux

LUMS no reemplaza el gestor de paquetes del sistema operativo.

En cambio, LUMS proporciona una interfaz centralizada para solicitar y rastrear operaciones de paquetes.

---

### Administración operativa

Los administradores y operadores pueden necesitar supervisar:

* trabajos de actualización en ejecución
* trabajos fallidos
* trabajos completados
* reporte de clientes
* requisitos de reinicio
* errores del gestor de paquetes
* actividad de auditoría

Los procedimientos detallados de solución de problemas para estas condiciones están documentados en `troubleshooting.md`.

---

## 3. Roles administrativos

LUMS proporciona actualmente tres roles.

| Rol           | Propósito                                          |
| ------------- | -------------------------------------------------- |
| Administrator | Control administrativo completo                    |
| Operator      | Gestión operativa diaria                           |
| Viewer        | Visibilidad de solo lectura de clientes y software |

Cada rol es una plantilla de permisos. Los permisos guardados individualmente de la cuenta se aplican en el servidor.

Por lo tanto, ocultar un elemento de la interfaz no se considera un control de seguridad por sí mismo.

Las operaciones de API no autorizadas también deben ser rechazadas por el servidor.

---

## 4. Administrator

La plantilla Administrator proporciona por defecto el conjunto completo de permisos de la aplicación LUMS.

Los administradores pueden:

* ver clientes gestionados
* ver software instalado
* ver actualizaciones disponibles
* crear y ejecutar trabajos de actualización
* revisar el historial de actualizaciones
* realizar operaciones de gestión de paquetes
* realizar mantenimiento del sistema
* crear clientes
* deshabilitar clientes
* rotar tokens de cliente
* crear y gestionar usuarios de LUMS
* asignar plantillas de roles y permisos individuales

Los permisos completos de la plantilla Administrator solo deben concederse a usuarios que los necesiten.

Las cuentas administrativas no deben usarse para la supervisión rutinaria de solo lectura cuando una cuenta Operator o Viewer sea suficiente.

---

## 5. Operator

La plantilla Operator está destinada a la administración diaria de actualizaciones y del sistema.

Los operadores pueden:

* ver clientes gestionados
* ver software instalado
* ver actualizaciones disponibles
* crear y ejecutar trabajos de actualización
* revisar el historial de actualizaciones
* realizar operaciones de gestión de paquetes
* realizar mantenimiento del sistema

La plantilla Operator no concede:

* crear o gestionar usuarios de LUMS
* asignar roles de usuario
* crear o deshabilitar clientes
* rotar tokens de cliente

Esta separación por defecto permite operaciones de actualización de rutina sin conceder privilegios de gestión de cuentas y clientes. Las concesiones individuales pueden ser modificadas por un usuario con `users.manage`.

---

## 6. Viewer

La plantilla Viewer proporciona visibilidad de solo lectura.

Los viewers pueden:

* ver clientes gestionados
* ver software instalado

La plantilla Viewer no concede las siguientes funciones administrativas:

* gestión de actualizaciones disponibles
* creación de trabajos de actualización
* ejecución de trabajos de actualización
* historial de actualizaciones
* gestión de paquetes
* mantenimiento del sistema
* gestión de usuarios
* gestión de clientes
* rotación de tokens

Las operaciones de API mutativas correspondientes también están protegidas en el servidor.

El acceso de viewer está destinado por lo tanto a usuarios que necesitan visibilidad sin control operativo.

---

## 7. Directrices de selección de roles

Use el rol más pequeño que proporcione la funcionalidad requerida.

### Administrator

Úselo cuando el usuario deba gestionar:

* usuarios
* roles
* clientes
* autenticación de clientes
* tokens
* actualizaciones
* paquetes
* operaciones del sistema

### Operator

Úselo cuando el usuario necesite realizar trabajo operativo rutinario como:

* comprobar actualizaciones
* instalar paquetes
* eliminar paquetes
* actualizar paquetes
* ejecutar trabajos de actualización
* revisar el historial de trabajos

### Viewer

Úselo cuando el usuario solo necesite visibilidad sobre:

* clientes
* software instalado

---

## 8. Principio de seguridad administrativa

La administración de LUMS sigue el principio de mínimo privilegio.

El acceso administrativo debe limitarse a la funcionalidad requerida para la tarea del usuario.

En particular:

* no use cuentas de Administrator para la visualización rutinaria
* no comparta cuentas entre administradores
* no comparta tokens de cliente
* no coloque credenciales en la documentación
* no exponga tokens de cliente en capturas de pantalla o registros
* no eluda la interfaz web de LUMS modificando directamente la base de datos a menos que un procedimiento de recuperación documentado lo requiera explícitamente

Cuando una operación administrativa falla, investigue la causa antes de cambiar el estado persistente.

Use el principio:

> **Observar primero. Cambiar segundo. Verificar tercero.**

---

## 9. Flujo de trabajo administrativo

Un flujo de trabajo administrativo normal debe seguir esta secuencia:

```text
1. Authenticate
      │
      ▼
2. Verify role
      │
      ▼
3. Select client / operation
      │
      ▼
4. Review current state
      │
      ▼
5. Perform required operation
      │
      ▼
6. Monitor job
      │
      ▼
7. Verify result
      │
      ▼
8. Review history / audit information
```

Las acciones administrativas siempre deben verificarse después de la ejecución.

Una solicitud de API exitosa no prueba por sí misma que la operación solicitada de paquete o sistema se haya completado con éxito.

El estado final reportado por el cliente gestionado es el resultado operativo relevante.

---

## 10. Separación de la documentación

El conjunto de documentación de LUMS está dividido intencionalmente en guías operativas separadas.

| Documento            | Propósito                                        |
| -------------------- | ------------------------------------------------ |
| `install.md`         | Instalación y despliegue inicial                 |
| `administration.md`  | Administración diaria                            |
| `security.md`        | Arquitectura de seguridad y resultados de auditoría |
| `troubleshooting.md` | Diagnóstico y recuperación                       |

Por lo tanto, esta guía debe evitar duplicar los procedimientos detallados de instalación y solución de problemas.

En cambio, describe lo que los administradores pueden gestionar, qué significa cada operación y cómo se realizan los flujos de trabajo administrativos normales.

## 11. Gestión de usuarios

La gestión de usuarios está disponible para usuarios con el permiso `users.manage`.

Los administradores pueden crear y gestionar cuentas de aplicación de LUMS a través de la interfaz dedicada de gestión de usuarios.

Las cuentas de usuario están separadas de la autenticación de clientes gestionados.

Un usuario de LUMS se autentica en la aplicación web con una cuenta de aplicación.

Un cliente gestionado se autentica en la API de LUMS con un token de cliente.

Estos mecanismos de autenticación no deben confundirse.

```text
LUMS User
    │
    │ username + password
    ▼
Web Interface
    │
    ▼
LUMS Application

Managed Client
    │
    │ client token
    ▼
LUMS API
```

---

## 12. Creación de usuarios

Los usuarios con `users.manage` pueden crear nuevos usuarios de LUMS.

Al crear un usuario, el administrador especifica:

* nombre de usuario
* contraseña
* una etiqueta de rol, con una plantilla de rol disponible para la asignación posterior de permisos

Las plantillas de roles disponibles son:

* `administrator`
* `operator`
* `viewer`

El servidor valida los valores proporcionados antes de crear la cuenta.

Las cuentas nuevas comienzan sin permisos. Después de la creación, los administradores pueden asignar casillas individuales o aplicar una de las plantillas de roles. Aplicar una plantilla preselecciona sus permisos predeterminados, que luego pueden personalizarse. Los permisos disponibles son:

| Permiso           | Acceso concedido                                    |
| ----------------- | --------------------------------------------------- |
| `clients.view`    | Ver la lista de clientes y la información del sistema |
| `software.view`   | Ver el software instalado                           |
| `updates.view`    | Ver actualizaciones, trabajos e historial de actualizaciones |
| `packages.search` | Buscar en los repositorios de paquetes              |
| `jobs.manage`     | Crear operaciones de paquetes y trabajos de actualización |
| `clients.manage`  | Registrar/eliminar clientes y rotar tokens de cliente |
| `users.manage`    | Crear usuarios y gestionar roles, permisos y notas internas |
| `backups.manage`  | Crear e inspeccionar copias de seguridad de la base de datos |

Los permisos relacionados con clientes requieren `clients.view`; `jobs.manage` también requiere `updates.view`. LUMS impide eliminar la última cuenta activa con `users.manage`, por lo que los administradores no pueden bloquearse accidentalmente.

Las contraseñas no se almacenan en texto plano.

LUMS utiliza hash de contraseñas basado en Argon2 para las credenciales de aplicación.

Después de la creación, verifique que:

* el nombre de usuario aparece en la lista de usuarios
* la plantilla de rol y los permisos individuales son correctos
* la cuenta está habilitada
* el usuario puede autenticarse correctamente

No transmita contraseñas a través de documentación, tickets, capturas de pantalla u otros canales inseguros.

---

## Interfaz de copia de seguridad de la base de datos

Los usuarios con el permiso `backups.manage` pueden crear copias de seguridad de SQLite desde **Copias de seguridad de la base de datos**. Las cuentas de administrador reciben este permiso a través de la migración `005-backup-permission`; las cuentas nuevas lo reciben aplicando la plantilla Administrator o se les puede conceder explícitamente.

La interfaz admite archivos `.db` nativos y `.db.gz` comprimidos. Utiliza la API de copia de seguridad en línea de SQLite, valida la base de datos completada y almacena los archivos con permisos exclusivos del propietario. La UI lista los diez archivos más recientes. Las copias de seguridad no son cifradas, eliminadas automáticamente, programadas, descargadas ni restauradas por LUMS; los administradores con `backups.manage` pueden eliminar copias de seguridad individuales de la lista después de confirmación. Proteja el destino en consecuencia.

El directorio de destino base está fijado por la configuración del lado del servidor `LUMS_BACKUP_DIR`. La interfaz permite elegir un subdirectorio relativo bajo esta base y lo crea cuando es necesario; se rechazan rutas absolutas, recorridos de directorio padre y subdirectorios con enlaces simbólicos. Las rutas del host deben ser montadas en Docker por el administrador del servidor. Para un despliegue de Docker, cree un directorio de host separado escribible por el UID/GID `10001` del contenedor:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/lums
```

Agregue estas opciones a la configuración del contenedor LUMS:

```bash
-v /var/backups/lums:/var/backups/lums \
-e LUMS_BACKUP_DIR=/var/backups/lums \
```

Use un disco separado o almacenamiento remoto para la resiliencia contra fallos del host. Por ejemplo, monte primero un NAS en el host Debian, luego use esa ruta montada como el lado izquierdo del montaje bind de Docker. La UI de copias de seguridad muestra el directorio base del lado del contenedor; la ruta relativa seleccionada está debajo de él. El destino de la copia de seguridad debe estar disponible y ser escribible dentro del contenedor; de lo contrario, la interfaz informa que el almacenamiento de copias de seguridad no está disponible.

Para los pasos de restauración, consulte [`server/static/backup-restore.md`](../../../server/static/backup-restore.md).

---

## 13. Roles de usuario

Seleccione una plantilla de rol según el privilegio mínimo requerido, luego revise los permisos individuales de cada cuenta.

| Plantilla de rol | Gestión de usuarios | Gestión de clientes | Actualizaciones | Gestión de paquetes | Acceso de solo lectura |
| ---------------- | ------------------: | ------------------: | --------------: | ------------------: | ---------------------: |
| Administrator    |                 Sí  |                 Sí  |             Sí  |                 Sí  |                    Sí  |
| Operator         |                 No  |                 No  |             Sí  |                 Sí  |                    Sí  |
| Viewer           |                 No  |                 No  |             No  |                 No  |                    Sí  |

Estos son valores predeterminados, no límites fijos. Los administradores pueden personalizar el conjunto de permisos de cada usuario. La aplicación de roles ocurre en el servidor a través de los permisos resultantes por usuario.

La interfaz web refleja el rol asignado, pero el servidor sigue siendo la frontera de seguridad autoritativa.

---

## 14. Deshabilitar cuentas de usuario

Cuando una cuenta ya no deba poder acceder a LUMS, deshabilite la cuenta en lugar de compartir o reutilizar las credenciales.

Los ejemplos incluyen:

* un administrador que abandona el proyecto
* un operador que ya no requiere acceso
* eliminación temporal del acceso administrativo
* respuesta de seguridad a una cuenta comprometida

Después de deshabilitar una cuenta, verifique que la autenticación es rechazada.

Las sesiones autenticadas existentes también deben considerarse durante las investigaciones de seguridad de cuentas.

No modifique manualmente la tabla `users` a menos que un procedimiento de recuperación documentado requiera explícitamente una intervención a nivel de base de datos.

---

## 15. Administración de contraseñas

Las contraseñas son credenciales de aplicación y deben tratarse como información sensible.

Los administradores deben asegurarse de que:

* las contraseñas no se comparten
* las contraseñas no se almacenan en Git
* las contraseñas no se colocan en la documentación
* las contraseñas no se incluyen en capturas de pantalla
* las contraseñas no se escriben innecesariamente en el historial del shell
* los usuarios reciben sus credenciales a través de un canal seguro apropiado

LUMS almacena hashes de contraseñas en lugar de contraseñas en texto plano.

Si se sospecha que una contraseña ha sido comprometida, reemplácela a través del procedimiento de gestión de cuentas apropiado en lugar de intentar recuperar la contraseña original.

---

## 16. Sesiones

LUMS utiliza sesiones de aplicación autenticadas para el acceso web.

La gestión de sesiones es parte de la frontera de seguridad de la aplicación.

Los administradores deben tratar una sesión autenticada inesperada como un evento de seguridad si la cuenta asociada ya no debería tener acceso.

Las situaciones relevantes incluyen:

* cuenta deshabilitada que sigue apareciendo activa
* acceso administrativo inesperado
* sospecha de compromiso de credenciales
* sesión de navegador inesperada
* investigación de seguridad

Para la solución de problemas detallada de sesiones y autenticación, consulte `troubleshooting.md`.

---

## 17. Limitación de la tasa de inicio de sesión

LUMS aplica limitación de la tasa a los intentos de inicio de sesión fallidos repetidos.

La progresión actual es:

| Intentos fallidos | Bloqueo    |
| ----------------: | ---------: |
|                 5 |  30 segundos |
|                 6 |  60 segundos |
|                 7 | 120 segundos |
|                8+ | 300 segundos |

El estado de limitación de la tasa se persiste en SQLite.

Un inicio de sesión exitoso borra el estado de intentos fallidos aplicable.

Los fallos de autenticación repetidos deben investigarse en lugar de eludir el limitador de tasa.

Las causas posibles incluyen:

* credenciales incorrectas
* credenciales guardadas obsoletas
* un cliente automatizado que usa credenciales incorrectas
* intentos de inicio de sesión manuales repetidos
* un posible ataque de credenciales

---

## 18. Gestión de clientes

Los clientes gestionados son sistemas Linux que ejecutan el agente LUMS.

Un cliente proporciona a LUMS información como:

* identidad del cliente
* software instalado
* actualizaciones disponibles
* resultados de gestión de paquetes
* resultados de trabajos de actualización
* estado de reinicio
* estado operativo

El servidor LUMS almacena el estado del cliente y lo expone a través de la interfaz web.

El cliente realiza las operaciones reales de gestión de paquetes localmente.

---

## 19. Autenticación de clientes

Cada cliente gestionado se autentica en LUMS usando un token de cliente.

El token actúa como credencial para el cliente gestionado.

Trate los tokens de cliente con el mismo cuidado que las contraseñas.

Nunca:

* confirme tokens en Git
* coloque tokens en documentación pública
* incluya tokens en capturas de pantalla
* pegue tokens en rastreadores de issues
* exponga tokens en la salida de diagnóstico
* comparta el token de un cliente con otro cliente

Un token solo debe instalarse en el cliente para el que fue emitido.

---

## 20. Registro de clientes

Un nuevo cliente primero debe registrarse en LUMS.

El proceso de registro establece la identidad del cliente del lado del servidor y la credencial de autenticación.

Después del registro:

1. instale el agente LUMS
2. configure el token del cliente
3. configure el punto de conexión del servidor LUMS
4. establezca la confianza TLS
5. realice una ejecución inicial del agente
6. verifique que el cliente reporta correctamente
7. confirme que el cliente aparece en la interfaz de LUMS

Un cliente no debe considerarse operativo solo porque el servicio del agente arranca correctamente.

El servidor debe recibir y aceptar un reporte de cliente válido.

---

## 21. Estado del cliente

La vista de clientes debe usarse para distinguir entre diferentes estados operativos.

Los ejemplos incluyen:

* cliente registrado pero sin reportar
* cliente reportando normalmente
* cliente reportando información obsoleta
* cliente deshabilitado
* fallo de autenticación del cliente
* fallo del gestor de paquetes del lado del cliente

Cuando un cliente deja de reportar, primero determine si el problema es:

1. conectividad de red
2. confianza TLS
3. autenticación del cliente
4. ejecución del agente
5. disponibilidad del servidor
6. procesamiento del lado del servidor

Evite cambiar las credenciales del cliente antes de establecer qué capa está fallando realmente.

---

## 22. Rotación de tokens de cliente

Los tokens de cliente pueden rotarse cuando sea necesario.

Las razones típicas incluyen:

* exposición sospechosa del token
* política de rotación de credenciales
* mantenimiento administrativo
* reemplazo de una configuración de cliente
* respuesta a un incidente de seguridad

La rotación de tokens cambia la credencial aceptada para el cliente.

Después de la rotación:

1. obtenga el nuevo token de cliente
2. actualice la configuración del cliente
3. ejecute el agente
4. verifique la autenticación exitosa
5. verifique el reporte de cliente resultante
6. confirme que el reporte normal se reanuda

No elimine la configuración antigua del cliente hasta que se haya verificado el nuevo camino de autenticación.

---

## 23. Deshabilitar un cliente

Un cliente puede deshabilitarse cuando ya no deba participar en las operaciones de LUMS.

Los ejemplos incluyen:

* desmantelamiento del sistema
* mantenimiento temporal
* reemplazo del cliente
* sospecha de compromiso de credenciales

Antes de deshabilitar un cliente, compruebe si hay trabajos de actualización activos asociados con él.

Después de deshabilitar:

* verifique que el cliente ya no se trata como operativo
* revise el historial relevante de trabajos de actualización
* preserve la información de auditoría necesaria para la investigación

No elimine los datos persistentes del cliente simplemente porque un cliente está temporalmente fuera de línea.

---

## 24. Lista de comprobación de administración de clientes

Al agregar o cambiar un cliente, verifique la cadena completa:

```text
[ ] Client exists in LUMS
[ ] Client is enabled
[ ] Client token is valid
[ ] TLS trust is valid
[ ] LUMS Agent is installed
[ ] Agent configuration is valid
[ ] Initial report succeeds
[ ] Client appears in the Web UI
[ ] Installed software is reported
[ ] Available updates are reported
[ ] Update jobs can be tracked
[ ] Results are returned correctly
```

Un cliente es operativo solo cuando la cadena completa de reporte y autenticación funciona.

---

## 25. Principio administrativo

La administración de usuarios y la administración de clientes deben permanecer separadas.

Una cuenta de aplicación de LUMS determina **lo que una persona puede hacer**.

Un token de cliente determina **qué sistema gestionado puede comunicarse con LUMS**.

```text
Application User
      │
      └── Role / Permissions

Managed Client
      │
      └── Client Token / Identity
```

No use un mecanismo como sustituto del otro.

## 26. Inventario de software

LUMS mantiene la información de software reportada por los clientes gestionados.

El inventario de software permite a administradores y operadores determinar qué paquetes están instalados en un cliente.

El inventario es recopilado por el agente LUMS y reportado al servidor.

El servidor luego hace que la información reportada esté disponible a través de la interfaz del cliente.

El inventario debe tratarse como una instantánea del estado reportado por el cliente.

No reemplaza al gestor de paquetes nativo.

---

## 27. Software instalado

La sección **Software instalado** muestra los paquetes reportados por el cliente seleccionado.

Los administradores y operadores pueden usar el filtro de paquetes local para reducir el inventario mostrado.

El filtro de software instalado es una función de interfaz local.

Está separado de la búsqueda de gestión de paquetes.

Esta distinción es importante:

```text
Installed Software
    │
    └── Filter already reported package inventory

Package Management
    │
    └── Search the client's package repositories
```

Por lo tanto, un paquete instalado puede no aparecer en la búsqueda de gestión de paquetes si ya no está disponible en un repositorio configurado.

---

## 28. Actualizaciones disponibles

LUMS también recopila información sobre paquetes para los cuales hay actualizaciones disponibles.

La información de actualizaciones disponibles se genera en el cliente gestionado usando su sistema de gestión de paquetes nativo.

La información reportada puede usarse para identificar paquetes que requieren atención.

Antes de crear un trabajo de actualización, revise:

* identidad del cliente
* nombre del paquete
* versión actualmente instalada
* versión disponible
* estado del paquete
* si el cliente es actualmente accesible

No suponga que cada actualización disponible debe instalarse inmediatamente.

Los requisitos operativos, las ventanas de mantenimiento, las dependencias de la aplicación y el estado del cliente deben considerarse antes de la ejecución.

---

## 29. Gestión de paquetes

LUMS proporciona operaciones centralizadas de gestión de paquetes para clientes Linux compatibles.

Las acciones actuales de gestión de paquetes incluyen:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

La operación se solicita a través de LUMS pero es ejecutada localmente por el agente LUMS.

El agente delega la operación real del paquete al gestor de paquetes nativo.

```text
LUMS Web UI
      │
      ▼
LUMS API
      │
      ▼
Update Job
      │
      ▼
LUMS Agent
      │
      ├── APT / dpkg
      │
      └── pacman
```

Por lo tanto, LUMS permanece independiente de la base de datos de paquetes y de la implementación de gestión de paquetes del sistema operativo.

---

## 30. Búsqueda de paquetes

La interfaz **Gestión de paquetes** proporciona una búsqueda de paquetes separada del filtro de software instalado.

La búsqueda solicita información de paquetes al cliente gestionado.

En sistemas basados en Debian, el agente utiliza las herramientas de gestión de paquetes APT.

En Arch Linux, el agente utiliza `pacman`.

Los resultados de búsqueda pueden contener:

* nombre del paquete
* versión del paquete
* descripción del paquete
* información del repositorio cuando esté disponible

La búsqueda de paquetes no instala nada.

Por lo tanto, una búsqueda es una operación de solo lectura.

---

## 31. Instalar un paquete

Los administradores y operadores pueden crear trabajos de instalación de paquetes.

El flujo de trabajo normal es:

1. seleccionar el cliente gestionado
2. abrir **Gestión de paquetes**
3. buscar el paquete requerido
4. revisar el resultado
5. seleccionar la acción de instalación
6. crear el trabajo
7. supervisar la ejecución
8. verificar el resultado
9. actualizar o volver a comprobar el software instalado

El paquete es instalado por el agente usando el gestor de paquetes nativo.

La creación exitosa del trabajo no significa que la instalación ya se haya completado.

Debe comprobarse el resultado final del trabajo.

---

## 32. Eliminar un paquete

La eliminación de paquetes sigue el mismo flujo de trabajo de trabajo controlado.

Antes de eliminar un paquete, verifique:

* el cliente correcto
* el paquete correcto
* la operación prevista
* si otro software depende del paquete

Después de la ejecución, verifique el estado resultante del trabajo y el estado de software reportado por el cliente.

LUMS no elude el manejo de dependencias del gestor de paquetes.

El gestor de paquetes nativo sigue siendo responsable de resolver la operación.

---

## 33. Actualizar un paquete

Un paquete específico puede actualizarse cuando hay una actualización disponible.

El flujo de trabajo es:

```text
Available Update
      │
      ▼
Review Package
      │
      ▼
Create UPDATE_PACKAGE Job
      │
      ▼
Agent Execution
      │
      ▼
Result Validation
```

LUMS valida la información del paquete antes de crear el trabajo de actualización correspondiente.

Si el paquete ya no aparece como actualizable, la solicitud de trabajo no debe tratarse como una operación de actualización válida.

Esto evita que la información de actualización obsoleta se ejecute a ciegas.

---

## 34. Actualizar el sistema

`UPDATE_SYSTEM` realiza una actualización del sistema más amplia utilizando el mecanismo nativo de gestión de paquetes del cliente.

Esta operación afecta a más de un paquete y, por lo tanto, debe tratarse como una operación de mantenimiento.

Antes de iniciar una actualización del sistema, verifique:

* disponibilidad del cliente
* ventana de mantenimiento
* trabajos en ejecución actualmente
* estado del gestor de paquetes
* espacio en disco disponible donde sea relevante
* si puede requerirse un reinicio

Después de la actualización, verifique:

* resultado del trabajo
* reporte del cliente
* software instalado
* actualizaciones disponibles
* estado de reinicio

---

## 35. Trabajos de actualización

Todas las operaciones mutativas de paquetes y actualizaciones se representan como trabajos de actualización de LUMS.

Esto proporciona un modelo común de ejecución y seguimiento.

Ciclo de vida típico de un trabajo:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS
```

Un trabajo también puede requerir manejo adicional cuando el cliente se vuelve no disponible o la ejecución se interrumpe.

El historial de trabajos debe usarse como el registro operativo autoritativo en lugar de depender únicamente de la vista actual del cliente.

---

## 36. Creación de trabajos

Antes de crear un trabajo de actualización, verifique cuidadosamente la operación prevista.

Compruebe:

* cliente
* acción
* paquete
* versión de destino cuando corresponda
* estado actual del paquete
* requisitos de mantenimiento

Las acciones admitidas incluyen:

| Acción            | Propósito                       |
| ----------------- | ------------------------------- |
| `INSTALL_PACKAGE` | Instalar un paquete             |
| `REMOVE_PACKAGE`  | Eliminar un paquete             |
| `UPDATE_PACKAGE`  | Actualizar un paquete específico |
| `UPDATE_SYSTEM`   | Realizar una actualización de todo el sistema |

La creación de trabajos de actualización está restringida a los roles **Administrator** y **Operator**.

Los viewers no pueden crear trabajos de actualización.

---

## 37. Ejecución de trabajos

Después de la creación, el trabajo es procesado por el agente LUMS.

El agente recibe el trabajo y ejecuta la operación solicitada localmente.

El servidor rastrea el estado resultante.

El agente no trata una solicitud HTTP exitosa como prueba de que la operación del paquete tuvo éxito.

En cambio, el resultado real del gestor de paquetes se devuelve a LUMS.

Esta distinción es importante:

```text
API request accepted
        ≠
Package operation successful
```

Por lo tanto, el resultado final de la ejecución siempre debe comprobarse.

---

## 38. Resultados de trabajos

Un trabajo completado debe contener un resultado explícito.

Los resultados relevantes incluyen:

* ejecución exitosa
* ejecución fallida
* error del gestor de paquetes
* ejecución interrumpida
* estado relacionado con la recuperación
* estado relacionado con el reinicio cuando corresponda

Los administradores y operadores deben inspeccionar el resultado cuando un trabajo falla en lugar de repetir inmediatamente la misma operación.

La ejecución repetida sin comprender el fallo original puede dificultar el diagnóstico.

---

## 39. Historial de trabajos

El historial de actualizaciones proporciona un registro operativo de la actividad de actualización anterior.

Úselo para responder preguntas como:

* ¿Ya se actualizó este paquete?
* ¿Qué cliente ejecutó la operación?
* ¿Cuándo se creó el trabajo?
* ¿Cuándo comenzó la ejecución?
* ¿Cuándo terminó la ejecución?
* ¿Tuvo éxito la operación?
* ¿El gestor de paquetes informó un error?

La información histórica de trabajos es especialmente importante al investigar fallos repetidos u operaciones de mantenimiento interrumpidas.

---

## 40. Trabajos fallidos

Cuando un trabajo falla:

1. registre el cliente y el ID del trabajo
2. inspeccione el resultado del trabajo
3. determine si el fallo ocurrió en el servidor o en el cliente
4. inspeccione los registros relevantes del agente
5. inspeccione el estado del gestor de paquetes nativo
6. corrija el problema subyacente
7. reintente solo después de comprender la causa

Las causas comunes incluyen:

* repositorios no disponibles
* bloqueos del gestor de paquetes
* problemas de red
* solicitudes de paquetes inválidas
* conflictos de dependencias
* espacio en disco insuficiente
* operaciones de paquetes interrumpidas
* problemas de autenticación o comunicación del cliente

Los procedimientos de diagnóstico detallados están documentados en `troubleshooting.md`.

---

## 41. Bloqueos del gestor de paquetes

APT y pacman pueden impedir operaciones concurrentes de paquetes.

Si una operación de gestión de paquetes falla porque el gestor de paquetes ya está en uso:

* identifique el proceso de gestión de paquetes activo
* determine qué operación está en ejecución
* espere a que termine la operación legítima cuando corresponda
* reintente la operación de LUMS después

**No** elimine a ciegas los archivos de bloqueo del gestor de paquetes mientras el gestor de paquetes está en ejecución.

Eliminar un archivo de bloqueo no resuelve la operación concurrente subyacente y puede dañar el estado de gestión de paquetes.

---

## 42. Ejecución consciente de la inactividad

LUMS puede usar la información de inactividad del cliente al determinar si un trabajo de actualización debe ejecutarse.

Este mecanismo está destinado a evitar interrumpir el uso interactivo activo de un sistema gestionado.

La detección de inactividad la realiza el agente en el cliente.

Si la información de inactividad no está disponible, el agente debe reportar esa condición en lugar de inventar un estado inactivo.

Los administradores deben distinguir entre:

* el cliente está inactivo
* el cliente está activo
* la detección de inactividad no está disponible
* el cliente no es accesible

Estos estados tienen significados operativos diferentes.

---

## 43. Supervisión de la ejecución de actualizaciones

Durante el mantenimiento, supervise:

* estado del trabajo
* conectividad del cliente
* actividad del agente
* resultado del gestor de paquetes
* requisito de reinicio

No suponga que un trabajo que permanece en `RUNNING` indefinidamente significa que el gestor de paquetes sigue trabajando.

Si la ejecución parece atascada, investigue el estado del cliente y del agente antes de crear otro trabajo.

---

## 44. Requisitos de reinicio

Algunas actualizaciones de paquetes y del sistema pueden requerir un reinicio.

LUMS rastrea el estado relacionado con el reinicio reportado por el cliente gestionado.

Después de una actualización del sistema:

1. inspeccione el estado de reinicio reportado
2. determine si se requiere un reinicio
3. realice el reinicio durante una ventana de mantenimiento apropiada
4. permita que el agente reporte nuevamente
5. verifique que el cliente vuelve al funcionamiento normal

Un requisito de reinicio no debe interpretarse automáticamente como un fallo de actualización.

---

## 45. Lista de comprobación operativa de actualizaciones

Para el mantenimiento rutinario de paquetes:

```text
[ ] Correct client selected
[ ] Client is reachable
[ ] Current software state reviewed
[ ] Available updates reviewed
[ ] Correct package/action selected
[ ] Maintenance requirements checked
[ ] Update job created
[ ] Job execution monitored
[ ] Job result verified
[ ] Installed software verified
[ ] Available updates rechecked
[ ] Reboot state checked
[ ] Job history reviewed if required
```

La operación se completa solo después de que se haya verificado el estado resultante del cliente.

---

## 46. Principio de gestión de paquetes

LUMS proporciona orquestación centralizada y visibilidad.

El sistema operativo gestionado sigue siendo responsable de la gestión real de paquetes.

Por lo tanto:

> **LUMS solicita y rastrea la operación. El gestor de paquetes nativo la ejecuta.**

Esta separación permite a LUMS gestionar diferentes sistemas Linux preservando la semántica de gestión de paquetes de cada sistema operativo.

## 47. Recuperación de trabajos

LUMS está diseñado para manejar trabajos de actualización interrumpidos sin repetir a ciegas operaciones que ya se han completado con éxito.

La ejecución de actualizaciones utiliza información de puntos de control para rastrear el progreso.

Esto es particularmente importante cuando:

* el agente se interrumpe
* el cliente se reinicia
* el servidor se reinicia
* la comunicación de red no está disponible temporalmente
* una operación de paquete se completa antes de que se reporte el resultado

El mecanismo de recuperación utiliza el estado registrado del trabajo para determinar qué trabajo aún debe realizarse.

---

## 48. Puntos de control a nivel de paquete

Los trabajos que contienen múltiples operaciones de paquetes se procesan individualmente.

Una operación de paquete exitosa se registra antes de que el agente proceda a la siguiente operación.

Conceptualmente:

```text
Job
 │
 ├── Package A → SUCCESS
 │
 ├── Package B → SUCCESS
 │
 ├── Package C → interrupted
 │
 └── Package D → PENDING
```

Después de la recuperación, las operaciones de paquetes ya completadas no deben ejecutarse nuevamente de forma innecesaria.

El trabajo restante puede continuar desde el estado registrado.

Esto reduce el riesgo de repetir operaciones de paquetes después de una interrupción.

---

## 49. Trabajos interrumpidos

Cuando un trabajo de actualización se interrumpe, no cree inmediatamente un trabajo de reemplazo.

Primero determine:

1. qué trabajo fue interrumpido
2. qué operación de paquete estaba activa
3. qué operaciones de paquetes ya tuvieron éxito
4. si el gestor de paquetes completó la operación
5. si el agente recuperó el trabajo automáticamente
6. si el cliente requiere un reinicio

El historial de trabajos existente y los registros del agente deben inspeccionarse antes de la intervención manual.

---

## 50. Recuperación del agente

El agente es responsable de continuar el trabajo recuperable después de una interrupción.

La recuperación debe preservar los resultados exitosos de paquetes siempre que sea posible.

Si una operación de paquete ya está registrada como exitosa, la recuperación no debe ejecutar a ciegas esa misma operación nuevamente.

Si la recuperación no puede determinar de forma segura el estado de una operación, la condición debe tratarse como un problema operativo e investigarse.

No modifique manualmente los estados de los trabajos en la base de datos simplemente para hacer que un trabajo parezca completo.

---

## 51. Reinicio del servidor durante un trabajo

Un reinicio del servidor LUMS no significa necesariamente que la operación de paquete del lado del cliente se haya interrumpido.

El servidor y el cliente tienen estados de ejecución separados.

Después de un reinicio del servidor:

1. verifique que el contenedor LUMS está en ejecución
2. verifique la disponibilidad de la base de datos
3. verifique que el cliente puede comunicarse con LUMS
4. inspeccione los trabajos de actualización afectados
5. compruebe los reportes del agente
6. verifique el estado final del paquete

El resultado de ejecución del lado del cliente sigue siendo la fuente importante de verdad para la operación de paquete.

---

## 52. Reinicio del cliente durante un trabajo

Un reinicio del cliente puede interrumpir la ejecución del agente o producirse porque la actualización en sí requiere un reinicio.

Estas situaciones deben distinguirse.

### Reinicio esperado

La actualización se completó y el sistema requiere un reinicio.

### Interrupción inesperada

El sistema se reinició antes de que se completara la operación o antes de que pudiera reportarse el resultado.

Después de que el cliente regrese:

1. permita que el agente arranque normalmente
2. verifique la comunicación con LUMS
3. inspeccione el trabajo afectado
4. verifique el estado del paquete
5. compruebe el estado de reinicio
6. permita que la recuperación continúe cuando corresponda

---

## 53. Detección de reinicio

LUMS puede rastrear los requisitos de reinicio reportados por el cliente gestionado.

La detección de reinicio no es lo mismo que detectar si la máquina es actualmente accesible.

Estos son estados separados:

```text
Client reachable
        │
        ├── reboot not required
        │
        └── reboot required

Client unreachable
        │
        └── current state cannot be confirmed
```

Por lo tanto, los administradores deben evitar tratar un cliente inaccesible como prueba de que se requiere un reinicio.

---

## 54. Verificación después del reinicio

Después de un reinicio requerido:

1. espere a que el sistema operativo esté disponible
2. verifique el servicio o temporizador del agente
3. verifique la autenticación del cliente
4. verifique el reporte del cliente
5. inspeccione el trabajo de actualización afectado
6. verifique las versiones de paquetes instaladas
7. verifique las actualizaciones disponibles
8. compruebe si se requiere otro reinicio

Un reinicio debe considerarse operativamente completo solo después de que el cliente haya reportado correctamente de nuevo.

---

## 55. Supervisión de trabajos de actualización

Los administradores y operadores deben supervisar los trabajos durante el mantenimiento planificado.

Los estados importantes incluyen:

| Estado    | Significado                                      |
| --------- | ------------------------------------------------ |
| `PENDING` | El trabajo existe pero la ejecución no ha comenzado |
| `RUNNING` | La ejecución del trabajo está en curso           |
| `SUCCESS` | La ejecución se completó con éxito               |
| `FAILED`  | La ejecución se completó con un error            |

El estado de un trabajo siempre debe interpretarse junto con su información de resultado.

Por ejemplo, un trabajo `FAILED` debe investigarse usando su resultado registrado en lugar de simplemente reintentarse.

---

## 56. Execution Watcher

El agente LUMS incluye un watcher de ejecución dedicado.

El watcher es responsable de supervisar la ejecución de trabajos de actualización en el cliente.

Su propósito es soportar un manejo fiable de la ejecución independientemente del flujo de trabajo de reporte.

La versión actual del watcher es:

**Watcher 1.2.1**

La versión del agente es:

**Agent 1.7.0**

Estas versiones deben verificarse después de las actualizaciones de clientes.

---

## 57. Supervisión del watcher

Los administradores pueden inspeccionar el watcher a través de systemd en el cliente gestionado.

Las comprobaciones útiles incluyen:

```bash
systemctl status lums-agent-watcher.service --no-pager
```

y:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

El temporizador puede inspeccionarse con:

```bash
systemctl status lums-agent-watcher.timer --no-pager
```

El estado exacto activo/inactivo de un servicio oneshot debe interpretarse junto con su temporizador y journal.

Un estado `inactive (dead)` no es automáticamente un error para un servicio oneshot.

---

## 58. Temporizadores de reporte y ejecución

LUMS separa el reporte regular del cliente de la supervisión de la ejecución.

El temporizador de reporte es responsable de la ejecución programada del agente.

El temporizador del watcher es responsable de la ejecución programada del watcher.

Inspeccione ambos al diagnosticar problemas de programación del lado del cliente:

```bash
systemctl list-timers --all | grep lums-agent
```

Las unidades esperadas incluyen:

```text
lums-agent.timer
lums-agent-watcher.timer
```

Si un temporizador no está en ejecución, inspeccione:

```bash
systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager
```

Luego inspeccione las entradas de journal correspondientes.

---

## 59. Registro de auditoría

LUMS registra acciones importantes de la aplicación administrativas y relevantes para la seguridad en el registro de auditoría.

La información de auditoría puede ayudar a establecer:

* qué operación ocurrió
* qué usuario la inició
* qué cliente fue afectado
* cuándo ocurrió la operación
* si la operación fue aceptada
* qué acción administrativa se realizó

La información de auditoría debe tratarse como evidencia operativa.

No debe eliminarse ni modificarse de forma casual.

---

## 60. Eventos de auditoría administrativos

La actividad administrativa relevante incluye operaciones como:

* creación de usuarios
* asignación de roles
* gestión de clientes
* rotación de tokens
* creación de trabajos de actualización
* operaciones de gestión de paquetes
* eventos de seguridad relacionados con la autenticación

Los datos exactos del evento dependen de la operación.

Los administradores deben usar la información de auditoría junto con el historial de trabajos al investigar actividad inesperada.

---

## 61. Manejo de registros de auditoría

Los registros de auditoría deben manejarse con cuidado.

No:

* modifique entradas históricas de auditoría para ocultar una operación
* exponga credenciales sensibles en registros exportados
* publique registros que contengan tokens de cliente
* publique contraseñas o material de autenticación
* copie salidas de registros sensibles en rastreadores de issues públicos

Si se deben compartir registros para la solución de problemas, redacte primero las credenciales y otra información sensible.

---

## 62. Registros de aplicación

Los registros de aplicación describen el funcionamiento interno del servidor LUMS.

Las fuentes útiles incluyen:

```bash
sudo docker logs --tail 100 lums
```

Para supervisión en vivo:

```bash
sudo docker logs -f lums
```

Al investigar un problema, reduzca la ventana de tiempo cuando sea posible.

No vuelque automáticamente el registro completo de producción cuando una sección relevante más pequeña sea suficiente.

---

## 63. Registros del agente

La actividad del agente del lado del cliente puede inspeccionarse a través de systemd:

```bash
journalctl -u lums-agent.service --no-pager -n 100
```

Para la actividad del watcher:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Para una ventana de tiempo específica, se puede usar el filtrado del journal de systemd.

Ejemplo:

```bash
journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Los registros deben correlacionarse con el ID del trabajo afectado siempre que sea posible.

---

## 64. Correlación de registros

Al investigar un problema de actualización, correlacione la información en todo el sistema:

```text id="jv3j7c"
Web UI
  │
  ├── Job ID
  │
  ▼
LUMS API / Application Log
  │
  ▼
Update Job
  │
  ▼
Agent
  │
  ▼
Native Package Manager
```

Esto evita el error común de suponer que un problema observado en una capa se originó en esa misma capa.

---

## 65. Lista de comprobación de supervisión administrativa

Durante el funcionamiento normal, verifique periódicamente:

```text
[ ] LUMS container is running
[ ] HTTPS endpoint is available
[ ] Database is accessible
[ ] Clients are reporting
[ ] No unexpected failed jobs
[ ] No unexplained authentication failures
[ ] Agent timers are active
[ ] Watcher timers are active
[ ] Package-manager operations complete normally
[ ] Audit activity is available
[ ] Logs contain no unexplained recurring errors
```

La frecuencia de estas comprobaciones debe coincidir con la importancia operativa del despliegue de LUMS.

---

## 66. Principio de recuperación

Cuando ocurre un problema de actualización, el enfoque administrativo más seguro es:

```text
Observe
   │
   ▼
Identify affected job/client
   │
   ▼
Inspect state and logs
   │
   ▼
Determine actual failure point
   │
   ▼
Correct underlying problem
   │
   ▼
Allow recovery or retry
   │
   ▼
Verify final state
   │
   ▼
Document significant incidents
```

Evite acciones de recuperación destructivas a menos que se comprenda el estado real del fallo.

En particular, no elimine manualmente trabajos, registros de base de datos, bloqueos del gestor de paquetes o datos persistentes de clientes solo para restaurar una interfaz de aspecto limpio.

> **Preservar la evidencia primero. Reparar el estado segundo. Verificar el resultado tercero.**

## 67. Administración de la base de datos

LUMS utiliza SQLite como su base de datos de aplicación.

La base de datos de producción se almacena dentro del volumen Docker persistente:

```text
/var/lib/lums/lums.db
```

La base de datos es persistente a través del reemplazo del contenedor siempre que se preserve el volumen Docker.

La base de datos contiene estado de la aplicación como:

* usuarios
* clientes gestionados
* trabajos de actualización
* información de paquetes
* información de auditoría
* estado relacionado con la autenticación
* estado de migración

Los administradores deben tratar la base de datos como datos críticos de la aplicación.

---

## 68. Configuración de tiempo de ejecución de SQLite

La línea base de SQLite de producción actual es:

| Configuración  | Valor                          |
| -------------- | ------------------------------ |
| `journal_mode` | `wal`                          |
| `busy_timeout` | `5000`                         |
| `synchronous`  | `2`                            |
| `foreign_keys` | habilitado por la aplicación   |

La aplicación habilita explícitamente la aplicación de claves foráneas de SQLite para las conexiones a la base de datos.

Los administradores no deben cambiar esta configuración de forma casual.

Los cambios en la configuración de tiempo de ejecución de la base de datos deben probarse antes de introducirse en producción.

---

## 69. Integridad de la base de datos

La integridad de la base de datos debe comprobarse cuando hay indicios de corrupción de la base de datos o comportamiento inesperado de la aplicación.

Una comprobación típica de integridad de SQLite es:

```bash id="f0g8sl"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Una base de datos sana debería devolver:

```text
ok
```

Si la comprobación de integridad informa errores, no continúe modificando el estado de la aplicación a ciegas.

Preserve la base de datos afectada e investigue la causa.

---

## 70. Migraciones de la base de datos

LUMS utiliza migraciones de aplicación para introducir cambios en la base de datos.

Las migraciones deben permitirse ejecutar a través del mecanismo normal de arranque y migración de la aplicación.

Los administradores no deben modificar manualmente el estado de migración simplemente para eludir un error.

Después de una actualización de la aplicación, verifique:

1. el contenedor arranca correctamente
2. las migraciones se completan
3. la aplicación es accesible
4. los usuarios existentes siguen disponibles
5. los clientes existentes siguen disponibles
6. el historial de trabajos existente sigue disponible

---

## 71. Volumen Docker persistente

El volumen Docker que contiene los datos de la aplicación LUMS es un recurso persistente crítico.

El volumen de producción es:

```text
lums-data
```

Inspecciónelo con:

```bash id="f3z2kd"
sudo docker volume inspect lums-data
```

El volumen debe permanecer adjunto al reemplazar el contenedor LUMS.

Eliminar el contenedor **no** elimina el volumen automáticamente.

Eliminar el volumen, sin embargo, elimina permanentemente los datos persistentes de la aplicación a menos que exista una copia de seguridad separada.

---

## 72. Administración del contenedor

La aplicación LUMS se ejecuta dentro de un contenedor Docker endurecido.

La línea base de seguridad de producción incluye:

* usuario de aplicación no root
* sistema de archivos raíz de solo lectura
* capacidades de Linux eliminadas
* `no-new-privileges`
* sistemas de archivos temporales restringidos
* montaje de secreto de solo lectura
* volumen de datos persistente dedicado
* puerto de aplicación solo en localhost

El contenedor no debe iniciarse con configuraciones de seguridad más débiles solo porque la solución de problemas se vuelve más conveniente.

---

## 73. Estado del contenedor

Compruebe el estado actual del contenedor con:

```bash id="4n6p2v"
sudo docker ps --filter name=lums
```

Inspeccione la configuración completa de tiempo de ejecución con:

```bash id="k1q4z8"
sudo docker inspect lums
```

Las propiedades importantes incluyen:

* estado de ejecución
* política de reinicio
* usuario
* sistema de archivos raíz de solo lectura
* capacidades
* opciones de seguridad
* vinculaciones de puertos
* montajes de volúmenes

---

## 74. Verificación de seguridad del contenedor

El tiempo de ejecución endurecido debe seguir proporcionando las propiedades esperadas.

Por ejemplo:

```bash id="0u7x3n"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

La línea base esperada es equivalente a:

```text
lums true false
```

Las capacidades deben permanecer eliminadas:

```bash id="k5n8ae"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Esperado:

```text
["ALL"]
```

Las opciones de seguridad deben incluir:

```text
no-new-privileges:true
```

---

## 75. Puerto de la aplicación

La aplicación LUMS escucha en el host a través de la interfaz de loopback.

El mapeo esperado es:

```text
127.0.0.1:5050 → container:5000
```

Verifíquelo con:

```bash id="b6v2w0"
sudo docker port lums
```

El puerto de la aplicación no debe exponerse directamente a la LAN.

El acceso externo se proporciona a través de Nginx sobre HTTPS.

---

## 76. Nginx y HTTPS

Nginx proporciona el punto de entrada HTTPS externo para LUMS.

La ruta de solicitud normal es:

```text
Client Browser
      │
      ▼
HTTPS :443
      │
      ▼
Nginx
      │
      ▼
127.0.0.1:5050
      │
      ▼
LUMS Container
```

El puerto de la aplicación Docker debe permanecer vinculado a localhost.

Por lo tanto, los administradores deben evitar exponer el puerto `5050` directamente a través del firewall o la configuración de Docker.

---

## 77. Verificación HTTPS

Después de cambios en Nginx, siempre valide la configuración antes de recargar:

```bash id="7f1h9m"
sudo nginx -t
```

Si la configuración es válida:

```bash id="4g5s2w"
sudo systemctl reload nginx
```

Luego verifique HTTPS:

```bash id="2w8v6c"
curl -I https://LUMS-SERVER/
```

Reemplace `LUMS-SERVER` con el nombre de host cubierto por el certificado TLS del servidor. No use `-k` para la verificación rutinaria; omite la validación del certificado.

Una respuesta HTTPS exitosa confirma que Nginx puede alcanzar la aplicación LUMS.

La validación del certificado también debe probarse usando el nombre de host o la dirección que los administradores normalmente usan.

No deshabilite permanentemente la verificación de certificados con `-k`.

---

## 78. Redirección HTTP

El punto de conexión HTTP debe redirigir a los clientes a HTTPS.

Verifique:

```bash id="w5q0rx"
curl -I http://127.0.0.1/
```

El comportamiento esperado es una redirección HTTP al punto de conexión HTTPS.

El acceso administrativo debe usar HTTPS.

---

## 79. Mantenimiento de certificados TLS

Los certificados TLS y las claves privadas son externos a la imagen Docker.

Las ubicaciones típicas son:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Las claves privadas deben permanecer protegidas.

Antes de reemplazar un certificado:

1. verifique el nuevo certificado
2. verifique la clave privada correspondiente
3. verifique los permisos de archivo
4. valide la configuración de Nginx
5. recargue Nginx
6. verifique HTTPS
7. verifique el inicio de sesión de la aplicación

Nunca coloque claves TLS privadas en el repositorio Git o en la imagen Docker.

---

## 80. Gestión de secretos

El secreto de la aplicación se almacena fuera de la imagen del contenedor.

El secreto de producción se monta de solo lectura en el contenedor:

```text
/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret
```

La aplicación recibe el secreto a través de:

```text
LUMS_SECRET_KEY_FILE
```

Los administradores nunca deben:

* confirmar el secreto
* imprimir el secreto
* incluir el secreto en la documentación
* exponerlo en capturas de pantalla
* colocarlo en una capa de imagen

Si se sospecha que el secreto ha sido expuesto, trátelo como comprometido y siga el procedimiento apropiado de rotación de secretos.

---

## 81. Estrategia de copia de seguridad

Los datos de LUMS deben respaldarse antes de cambios administrativos significativos.

Como mínimo, considere proteger:

* datos de la aplicación SQLite
* configuración de la aplicación
* material TLS
* secretos de la aplicación
* información de configuración del cliente
* documentación operativa relevante

Las copias de seguridad deben almacenarse separadas del contenedor de producción y de su volumen Docker persistente.

Una copia de seguridad que existe solo dentro del mismo host o volumen Docker no proporciona protección adecuada contra la pérdida de ese host o volumen.

---

## 82. Copia de seguridad de la base de datos

La base de datos SQLite debe respaldarse usando un método consciente de SQLite en lugar de simplemente copiar un archivo de base de datos activamente modificado sin considerar su estado.

Antes de realizar una copia de seguridad:

1. identifique la base de datos de producción
2. asegúrese de que el destino de la copia de seguridad está disponible
3. cree la copia de seguridad usando un método seguro para SQLite apropiado
4. verifique que la copia de seguridad existe
5. registre cuándo fue creada

No suponga que una copia de archivo exitosa significa automáticamente que existe una copia de seguridad de base de datos válida y recuperable.

---

## 83. Verificación de copias de seguridad

Una copia de seguridad no se considera fiable hasta que haya sido probada.

Verifique periódicamente que una copia de seguridad puede ser:

* leída
* abierta como datos SQLite
* comprobada en cuanto a integridad
* restaurada en un entorno de prueba aislado

Por ejemplo, una copia de prueba extraída puede verificarse con:

```bash id="p3v7cx"
sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"
```

Resultado esperado:

```text
ok
```

Una copia de seguridad de producción nunca debe probarse sobrescribiendo la base de datos de producción activa.

---

## 84. Principio de restauración

La restauración es una operación administrativa controlada.

Antes de restaurar:

1. identifique la copia de seguridad correcta
2. verifique su integridad
3. determine el punto de recuperación requerido
4. detenga o aísle la actividad de la aplicación según corresponda
5. preserve el estado actual de producción
6. restaure la copia de seguridad
7. verifique la integridad de la base de datos
8. inicie la aplicación
9. verifique las migraciones
10. verifique usuarios y clientes
11. verifique el historial de trabajos
12. verifique el reporte normal del cliente

No sobrescriba la única copia de la base de datos de producción durante la recuperación.

---

## 85. Verificación de la restauración

Después de una restauración, verifique como mínimo:

```text id="q6r2yh"
[ ] Container starts
[ ] Database opens
[ ] SQLite integrity check passes
[ ] Users are present
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is present
[ ] Audit information is available
[ ] HTTPS works
[ ] Clients can report
[ ] New operations can be created
```

Una restauración se completa solo después de que la aplicación y sus clientes gestionados hayan sido verificados.

---

## 86. Principio de copia de seguridad del servidor

La regla administrativa más importante para los datos persistentes de LUMS es:

> **Nunca realice una operación destructiva de base de datos o volumen sin una ruta de recuperación verificada.**

En particular, no elimine `lums-data` simplemente porque el contenedor se esté reconstruyendo o reemplazando.

El reemplazo del contenedor y la eliminación de datos persistentes son operaciones separadas.

---

## 87. Lista de comprobación administrativa del servidor

Antes de realizar un cambio significativo del lado del servidor:

```text id="7h3m0p"
[ ] Current container state recorded
[ ] Current image recorded
[ ] Database backup available
[ ] Backup integrity verified
[ ] Active jobs reviewed
[ ] Client reporting state reviewed
[ ] Configuration changes documented
[ ] TLS material available
[ ] Secret handling verified
[ ] Rollback path known
```

Solo después de que se hayan considerado estas condiciones debe procederse con un cambio significativo de producción.

---

## 88. Principio de administración del servidor

LUMS separa el estado de la aplicación del contenedor de aplicación desechable.

```text
Disposable
└── LUMS Container

Persistent
├── SQLite Database
└── lums-data Volume

External
├── TLS Material
└── Application Secret
```

Esta separación permite que el contenedor de la aplicación sea reemplazado sin destruir intencionalmente datos persistentes de la aplicación.

> **Reemplace la aplicación cuando sea necesario. Preserve los datos a menos que la eliminación de datos sea intencional explícitamente.**

## 89. Mantenimiento de rutina

El mantenimiento de rutina mantiene la instalación de LUMS fiable y reduce el riesgo de problemas operativos inesperados.

Las actividades de mantenimiento típicas incluyen:

* revisar trabajos de actualización fallidos
* comprobar el reporte de clientes
* revisar registros de la aplicación
* revisar la actividad de auditoría
* verificar copias de seguridad
* comprobar el espacio en disco disponible
* revisar el estado del contenedor Docker
* comprobar la validez del certificado TLS
* revisar actualizaciones de seguridad
* verificar la versión e imagen actuales de LUMS

El mantenimiento debe realizarse durante una ventana de mantenimiento apropiada cuando los cambios puedan afectar a los clientes de producción.

---

## 90. Mantenimiento antes de cambios

Antes de realizar mantenimiento que pueda afectar al servidor LUMS:

1. revise los trabajos de actualización activos
2. verifique que los clientes no están en mantenimiento inesperado
3. cree o verifique una copia de seguridad actual
4. registre el estado actual del contenedor y de la imagen
5. documente el cambio planificado
6. asegúrese de que existe una ruta de reversión

No comience el mantenimiento deteniendo o eliminando inmediatamente componentes de producción.

Primero establezca el estado actual.

---

## 91. Mantenimiento de la imagen Docker

Las imágenes de la aplicación LUMS deben reconstruirse desde el árbol de código fuente revisado.

Antes de construir una nueva imagen:

```bash id="x0m7r4"
cd /opt/lums-public
```

Ejecute la suite de pruebas automatizadas:

```bash id="4gk1dp"
./.venv-test/bin/pytest -q
```

Continúe solo cuando se comprenda el resultado de las pruebas.

Construya la nueva imagen usando una etiqueta temporal distinta:

```bash id="m8q3vz"
sudo docker build -t lums:new .
```

Una etiqueta temporal permite que la imagen actualmente en ejecución siga siendo identificable durante el proceso de reemplazo.

---

## 92. Verificación de la imagen

Después de construir una nueva imagen, verifique que la imagen existe:

```bash id="h6s2we"
sudo docker image inspect lums:new
```

Revise la configuración de la imagen antes del despliegue.

Cuando corresponda, verifique:

* digest de la imagen
* imagen base
* archivos de la aplicación
* dependencias instaladas
* tamaño de la imagen
* puertos expuestos
* usuario configurado

La imagen debe desplegarse solo después de que se hayan revisado los resultados de construcción y pruebas.

---

## 93. Reemplazo controlado del contenedor

El reemplazo del contenedor debe realizarse deliberadamente.

Antes de reemplazar el contenedor de producción:

```text id="m3z8qk"
[ ] Tests passed
[ ] New image exists
[ ] Database backup available
[ ] Active jobs reviewed
[ ] Current image recorded
[ ] Persistent volume confirmed
[ ] Secret available
[ ] TLS configuration available
[ ] Rollback image identified
```

Antes de ejecutar el ejemplo, compárelo con el contenedor realmente en ejecución. Los valores a continuación son un ejemplo, no un comando seguro para cada instalación. En particular, las rutas de origen del montaje bind de Docker en el lado izquierdo de `:` deben coincidir con su host, y el contenedor antiguo puede tener un nombre diferente.

Muestre la imagen, los montajes, los puertos publicados, la política de reinicio y las configuraciones de endurecimiento sin imprimir los valores de las variables de entorno:

```bash
sudo docker inspect lums --format 'Image={{.Config.Image}}
Mounts={{json .Mounts}}
Ports={{json .HostConfig.PortBindings}}
Restart={{json .HostConfig.RestartPolicy}}
Readonly={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
Tmpfs={{json .HostConfig.Tmpfs}}'
```

Guarde la salida en un lugar privado y úsela para comprobar que el nuevo contenedor mantiene el mismo volumen de base de datos, archivo secreto, directorio de copias de seguridad, vinculación de puerto solo local y opciones de seguridad. No pegue contenidos de secretos o valores de entorno en notas o mensajes.

Detenga el contenedor existente solo después de que se hayan considerado estas condiciones.

El contenedor de producción debe conservar la configuración de tiempo de ejecución endurecida.

Ejemplo:

```bash id="n8q2kf"
sudo docker stop lums
sudo docker rename lums lums-before-upgrade
```

Luego inicie la nueva imagen con la configuración endurecida establecida:

```bash id="c7w4md"
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
    -v /var/backups/lums:/var/backups/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -e LUMS_BACKUP_DIR=/var/backups/lums \
    lums:new
```

No elimine `lums-before-upgrade` hasta que se haya validado el nuevo despliegue.

---

## 94. Validación posterior a la actualización

Inmediatamente después de reemplazar el contenedor, verifique:

```bash id="b4m7tz"
sudo docker ps --filter name=lums
```

Luego inspeccione los registros:

```bash id="v5n2ra"
sudo docker logs --tail 100 lums
```

Verifique HTTPS:

```bash id="w9x1kf"
curl -I https://LUMS-SERVER/
```

Reemplace `LUMS-SERVER` con el nombre de host cubierto por el certificado TLS del servidor. No use `-k` para la verificación rutinaria; omite la validación del certificado.

Luego verifique la aplicación a través de la interfaz administrativa normal.

Compruebe que los usuarios, clientes e historial recientes existentes siguen presentes. Revise los registros en busca de errores de arranque o migración. Un contenedor en ejecución por sí solo no demuestra que la aplicación o su base de datos estén sanas.

### Revertir si el nuevo contenedor no funciona

Mantenga el contenedor antiguo hasta que la nueva versión haya superado la validación. Si el nuevo contenedor es inutilizable y ha confirmado que el contenedor antiguo se llama `lums-before-upgrade`, detenga y elimine **solo el nuevo contenedor**, luego renombre y reinicie el antiguo:

```bash
sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade lums
sudo docker start lums
```

`docker rm lums` sin `-v` elimina el contenedor, no el volumen `lums-data`. Nunca agregue `-v` a este comando de reversión. Si el nombre del contenedor difiere, o no está seguro de cuál contenedor es el antiguo y cuál el nuevo, no ejecute estos comandos; inspeccione el estado actual o pida ayuda a un administrador. Después de la reversión, inspeccione los registros y verifique que la interfaz web y los datos están disponibles.

---

## 95. Datos persistentes después de la actualización

El reemplazo del contenedor no debe eliminar el volumen Docker persistente.

Verifique:

```bash id="j4p8sx"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Confirme que:

```text id="m7z3kc"
/var/lib/lums
```

está respaldado por el volumen persistente esperado.

Luego verifique:

* los usuarios siguen existiendo
* los roles siguen siendo correctos
* los clientes siguen registrados
* el historial de trabajos sigue disponible
* la información de auditoría sigue disponible
* las migraciones se completaron con éxito

---

## 96. Línea base de seguridad después de la actualización

Después de desplegar una nueva imagen, verifique nuevamente el tiempo de ejecución endurecido.

Compruebe:

```bash id="q6c3xv"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Línea base esperada:

```text id="s0r8jm"
lums true false
```

También verifique:

```text id="g4m2vx"
CapDrop = ALL
SecurityOpt = no-new-privileges:true
```

y que:

```text id="c3p9rw"
127.0.0.1:5050 → container:5000
```

sigue siendo la exposición de la aplicación.

Una actualización exitosa de la aplicación no debe debilitar silenciosamente la línea base de seguridad.

---

## 97. Comunicación del cliente después de la actualización

Después de una actualización del servidor, verifique que los clientes gestionados aún pueden comunicarse.

Verifique primero al menos un cliente representativo.

Verifique:

```text id="x8h5qk"
[ ] Client authentication succeeds
[ ] Client report is accepted
[ ] Installed software is available
[ ] Available updates are available
[ ] Update jobs can be created
[ ] Agent results are accepted
```

Si se despliegan múltiples plataformas de clientes, verifique sistemas representativos de cada plataforma compatible.

---

## 98. Ejecución de actualizaciones después de la actualización

No realice inmediatamente una actualización de producción grande después de reemplazar el servidor LUMS.

Primero realice una prueba funcional controlada.

Una prueba adecuada debe verificar la ruta completa:

```text id="y7k2fd"
Web UI
  ↓
API
  ↓
Update Job
  ↓
Agent
  ↓
Package Manager
  ↓
Result
  ↓
Database
  ↓
Web UI
```

Solo después de que la prueba controlada tenga éxito deben reanudarse las operaciones de mantenimiento normales.

---

## 99. Reversión

La reversión debe ser posible cuando una nueva imagen causa un problema de producción inesperado.

Preserve:

* imagen de trabajo anterior
* datos persistentes
* copia de seguridad de la base de datos
* configuración anterior
* material TLS anterior
* registros relevantes

Si el nuevo contenedor no es utilizable:

1. detenga el nuevo contenedor
2. presérvelo para investigación cuando sea práctico
3. detenga más cambios administrativos
4. restaure la imagen previamente conocida como buena
5. reutilice el volumen persistente existente
6. inicie el tiempo de ejecución endurecido
7. verifique la aplicación
8. verifique los clientes
9. verifique el estado de los trabajos
10. investigue la imagen fallida por separado

No elimine el volumen persistente como parte de una reversión normal.

---

## 100. Validación de la reversión

Después de la reversión, verifique:

```text id="z1j8md"
[ ] LUMS starts
[ ] HTTPS works
[ ] Users can authenticate
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is available
[ ] Audit information is available
[ ] Package inventory is available
[ ] Update jobs can be tracked
[ ] Security baseline is intact
```

Una reversión se completa solo después de que se hayan verificado la aplicación y la ruta de comunicación del cliente.

---

## 101. Administración de emergencia

La administración de emergencia debe preservar la evidencia y el estado persistente siempre que sea posible.

Los ejemplos incluyen:

* fallos repetidos de la aplicación
* errores de integridad de la base de datos
* fallos de autenticación de clientes generalizados
* comportamiento inesperado de trabajos de paquetes
* sospecha de exposición de credenciales
* actualizaciones rotas
* fallos TLS que afectan a todos los usuarios

La secuencia preferida es:

```text id="f8k3wz"
Preserve
   ↓
Observe
   ↓
Isolate
   ↓
Recover
   ↓
Verify
   ↓
Document
```

Evite eliminar registros, bases de datos, contenedores o registros de clientes solo porque parecen ser parte del problema.

---

## 102. Principio de cambio administrativo

Cada cambio significativo de producción debe tener tres estados claramente definidos:

### Antes

El estado actual de producción es conocido y recuperable.

### Durante

El cambio se realiza usando el procedimiento documentado.

### Después

El estado resultante se verifica contra la línea base esperada.

Esto hace que el trabajo administrativo sea reproducible y reduce la deriva accidental de configuración.

---

## 103. Desinstalación controlada

La desinstalación es una operación administrativa destructiva.

Solo debe realizarse cuando el despliegue de LUMS se esté eliminando intencionalmente.

Antes de eliminar LUMS:

```text id="u5r2nc"
[ ] All managed clients identified
[ ] Active update jobs reviewed
[ ] Required job history exported or preserved
[ ] Required audit information preserved
[ ] Database backup created
[ ] Backup verified
[ ] TLS material preserved if required
[ ] Application secret preserved if required
[ ] Documentation preserved
[ ] Reinstallation requirements documented
```

No elimine datos persistentes antes de confirmar que ya no se requieren.

---

## 104. Eliminar el contenedor

Para eliminar el contenedor de la aplicación después de que el despliegue haya sido desmantelado:

```bash id="n2x7kc"
sudo docker stop lums
sudo docker rm lums
```

El volumen Docker **no** se elimina intencionalmente por estos comandos.

Esto permite que los datos de la aplicación permanezcan disponibles para inspección o recuperación posteriores.

---

## 105. Eliminar datos persistentes

Eliminar el volumen Docker de LUMS es una operación destructiva separada.

Realice esto solo después de confirmar que la base de datos y todo el estado almacenado de la aplicación ya no son necesarios.

Ejemplo:

```bash id="r8w3mz"
sudo docker volume rm lums-data
```

Esto elimina permanentemente los datos persistentes de la aplicación almacenados en ese volumen.

No ejecute este comando durante una actualización o reversión normal.

---

## 106. Eliminar componentes del cliente

Cuando un cliente gestionado se elimina permanentemente de LUMS, desinstale o deshabilite sus componentes de agente según el procedimiento del sistema operativo del cliente.

El cliente ya no debe reportar al servidor LUMS después del desmantelamiento.

Preserve la información relevante de trabajos y auditoría antes de eliminar el cliente si se requieren registros históricos.

---

## 107. Lista de comprobación administrativa final

### Administración de usuarios

```text id="p5z8cv"
[ ] Users have appropriate roles
[ ] Administrator access is limited
[ ] Disabled accounts are reviewed
[ ] Credentials are protected
```

### Administración de clientes

```text id="q2m7xd"
[ ] Clients are correctly registered
[ ] Client tokens are protected
[ ] Disabled clients are reviewed
[ ] Token rotation is performed when required
[ ] Client reporting is healthy
```

### Administración de actualizaciones

```text id="h6v9kt"
[ ] Available updates are reviewed
[ ] Update jobs are monitored
[ ] Failed jobs are investigated
[ ] Package operations are verified
[ ] Reboot requirements are checked
[ ] Job history is retained
```

### Administración del servidor

```text id="r3c8wn"
[ ] Container is running
[ ] Persistent volume is attached
[ ] SQLite integrity is healthy
[ ] HTTPS is working
[ ] TLS material is valid
[ ] Application secret is protected
[ ] Backups are available
```

### Seguridad

```text id="v7m4qx"
[ ] RBAC remains enforced
[ ] Viewer restrictions remain intact
[ ] Client authentication works
[ ] Container remains hardened
[ ] Application port remains localhost-only
[ ] No credentials are exposed
[ ] Logs contain no unexplained sensitive information
```

---

## 108. Línea base operativa

Una instalación sana de LUMS debe satisfacer la siguiente línea base:

```text id="d4k9sy"
Application
    ├── HTTPS available
    ├── Authentication available
    └── RBAC enforced

Server
    ├── Hardened container
    ├── Persistent database
    └── Valid migrations

Clients
    ├── Authenticated
    ├── Reporting
    ├── Software inventory available
    └── Update information available

Operations
    ├── Update jobs executable
    ├── Results recorded
    ├── Recovery supported
    └── Reboot state reported

Security
    ├── Secrets protected
    ├── Tokens protected
    ├── Audit information retained
    └── Network exposure restricted

Recovery
    ├── Backups available
    ├── Restore path known
    └── Rollback path known
```

---

## 109. Administración completa

La administración de LUMS debe priorizar siempre cambios controlados, observables y reversibles.

El ciclo de vida administrativo es:

```text id="w6f1pa"
Plan
  ↓
Observe
  ↓
Change
  ↓
Verify
  ↓
Document
  ↓
Maintain
```

Los principios operativos más importantes son:

> **Use el menor privilegio necesario.**

> **Preserve los datos persistentes.**

> **No cambie el estado sin comprender el estado actual.**

> **Verifique el resultado de cada operación significativa.**

> **Mantenga una ruta de recuperación probada.**

Para los procedimientos de instalación, consulte `install.md`.

Para la arquitectura de seguridad y los resultados de auditoría, consulte `security.md`.

Para los procedimientos de diagnóstico y recuperación, consulte `troubleshooting.md`.

---

## 110. Principio administrativo final

LUMS está destinado a hacer que la gestión de actualizaciones de Linux sea predecible y observable.

Por lo tanto, el trabajo administrativo no debe basarse en suposiciones o repeticiones ciegas.

Cuando algo cambia:

**Observar primero. Cambiar segundo. Verificar tercero.**

Cuando algo se rompe:

**Preservar la evidencia. Identificar la capa del fallo. Recuperar deliberadamente.**

Cuando algo funciona:

**Registrar el resultado y mantener la línea base conocida como buena.**
