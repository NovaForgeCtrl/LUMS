# Solución de problemas de LUMS

Esta guía proporciona procedimientos de solución de problemas para el servidor LUMS, los agentes de Linux, el watcher de ejecución, los trabajos de actualización, la autenticación, la gestión de paquetes, la base de datos y el despliegue con Docker.

El proceso de solución de problemas siempre debe comenzar con **observación antes de modificación**.

El objetivo es identificar el primer componente donde el comportamiento esperado se detiene, sin cambiar innecesariamente la configuración, el estado de la base de datos, las credenciales ni los controles de seguridad.

---

## Primeros pasos: Solucionar problemas de forma segura

Si es nuevo en Linux, un error no significa automáticamente que se hayan perdido datos. No cambie varias cosas a la vez. Comience con las comprobaciones a continuación y anote **cuándo** ocurre el problema y **qué acción** ocurrió inmediatamente antes.

### Primeras comprobaciones en el servidor LUMS

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`docker ps -a` también muestra los contenedores detenidos. `docker logs` lee los mensajes recientes de la aplicación. `systemctl status` muestra si Nginx está en ejecución; `nginx -t` comprueba su configuración sin cambiarla. Si `nginx -t` falla, **no** recargue Nginx hasta que se haya corregido la causa.

### Primeras comprobaciones en un cliente gestionado

```bash
sudo systemctl status lums-agent.service --no-pager
sudo journalctl -u lums-agent.service -n 100 --no-pager
sudo systemctl status lums-agent-watcher.service --no-pager
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

El agente y el watcher son servicios separados: un reporte exitoso del agente no prueba que el watcher pueda ejecutar trabajos de actualización. Para un servicio `oneshot`, `inactive` puede ser normal después de una ejecución exitosa; compruebe también el resultado y los mensajes de registro.

### Antes de compartir la salida de un comando

Compruebe los registros y la configuración en busca de contraseñas, tokens de cliente, claves de sesión o API, claves privadas e información personal. Nunca comparta el contenido de archivos secretos ni los valores completos de las variables de entorno. Si necesita ayuda, comparta solo los mensajes de error relevantes después de eliminar la información sensible.

**No comience por** eliminar la base de datos o el volumen Docker, ejecutar el contenedor como privilegiado, deshabilitar opciones de seguridad, eliminar archivos de bloqueo del gestor de paquetes ni rotar tokens. Estas acciones pueden dañar datos, borrar evidencia o empeorar el problema. Si una comprobación falla, guarde su salida y continúe con la sección relevante a continuación.

---

# 1. Filosofía de solución de problemas

LUMS consta de varios componentes independientes.

Un reporte de cliente exitoso no significa automáticamente que la ejecución de actualizaciones esté funcionando.

La ruta operativa principal es:

```text
Linux Client
    │
    ├── LUMS Agent
    │
    └── Execution Watcher
            │
            ▼
          HTTPS
            │
            ▼
        Nginx
            │
            ▼
        LUMS API
            │
            ▼
         SQLite
```

La ejecución de actualizaciones añade la capa de gestión de paquetes:

```text
Browser
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Update Job
   │
   ▼
Execution Watcher
   │
   ▼
LUMS Agent
   │
   ▼
APT / pacman
   │
   ▼
Result
   │
   ▼
LUMS API
   │
   ▼
SQLite
```

Al solucionar problemas, identifique el **primer componente que falla**.

Por ejemplo:

```text
Agent report fails
    ↓
Check agent service
    ↓
Check network
    ↓
Check TLS
    ↓
Check client token
    ↓
Check LUMS API
```

No haga inmediatamente lo siguiente:

* modificar la base de datos
* eliminar el volumen Docker
* reinstalar el agente
* rotar credenciales
* eliminar archivos de bloqueo del gestor de paquetes
* deshabilitar controles de seguridad
* hacer que el contenedor sea privilegiado

Estas acciones pueden destruir información de diagnóstico útil o crear problemas adicionales.

---

# 2. Línea base de diagnóstico

Antes de investigar un problema específico, establezca el estado actual de los componentes principales.

El despliegue de producción de LUMS utiliza:

```text
Application port: 127.0.0.1:5050
External access: HTTPS through Nginx
Database: /var/lib/lums/lums.db
Docker volume: lums-data
Agent: 1.7.0
Watcher: 1.2.1
```

El contenedor de producción está endurecido con:

```text
Read-only root filesystem
No Linux capabilities
no-new-privileges
Non-root application user
Protected secret mount
Dedicated persistent data volume
```

El puerto de la aplicación está vinculado intencionalmente solo al host local.

La ruta de red esperada es:

```text
Client / Browser
       │
       ▼
     HTTPS
       │
       ▼
    Nginx :443
       │
       ▼
127.0.0.1:5050
       │
       ▼
 Docker container
       │
       ▼
    LUMS :5000
```

---

# 3. Primeras comprobaciones de diagnóstico

## 3.1 Comprobar el contenedor LUMS

En el servidor LUMS:

```bash
sudo docker ps
```

El contenedor `lums` debería estar en ejecución.

Para una visión general completa de los contenedores:

```bash
sudo docker ps -a \
    --filter name=lums
```

No elimine contenedores detenidos antes de investigarlos.

Los contenedores de respaldo anteriores pueden contener información útil al investigar un problema de despliegue.

---

## 3.2 Comprobar los registros recientes de la aplicación

Inspeccione los registros más recientes de LUMS:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Para salida en vivo:

```bash
sudo docker logs \
    -f \
    lums
```

Al investigar una solicitud o trabajo específico, comience la inspección de registros antes de reproducir el problema cuando sea posible.

Esto facilita la correlación de la acción del cliente con el evento del lado del servidor correspondiente.

---

## 3.3 Comprobar Nginx

Compruebe el proxy inverso:

```bash
sudo systemctl status nginx \
    --no-pager
```

Valide la configuración:

```bash
sudo nginx -t
```

Una prueba de configuración exitosa debería informar:

```text
syntax is ok
test is successful
```

Si Nginx no está en ejecución, el acceso HTTPS a LUMS normalmente fallará incluso cuando el contenedor Docker en sí esté sano.

---

## 3.4 Comprobar el agente

En un cliente Linux gestionado:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspeccione la salida reciente del agente:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Para un servicio `Type=oneshot`, un estado inactivo después de una ejecución exitosa puede ser normal.

La información importante es el resultado de la ejecución.

Una ejecución exitosa debería terminar con:

```text
status=0/SUCCESS
```

---

## 3.5 Comprobar el execution watcher

El watcher es un componente separado del agente de reporte.

Compruébelo de forma independiente:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspeccione la salida reciente:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Por lo tanto, un reporte exitoso del agente **no** prueba que el watcher de ejecución esté funcionando correctamente.

---

## 3.6 Comprobar los temporizadores de LUMS

Compruebe todos los temporizadores relevantes:

```bash
sudo systemctl list-timers \
    --all | grep lums
```

Los temporizadores esperados incluyen los mecanismos de programación del agente y del watcher.

Si un temporizador falta o está inactivo, inspeccione la unidad correspondiente antes de cambiar nada.

---

# 4. El contenedor LUMS no está en ejecución

Si el contenedor `lums` no está en ejecución, no lo recree inmediatamente.

Primero inspeccione su estado:

```bash
sudo docker ps -a \
    --filter name=lums
```

Luego inspeccione el contenedor:

```bash
sudo docker inspect lums
```

Compruebe los registros recientes:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Compruebe el estado de salida:

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

El resultado puede ayudar a distinguir entre:

```text
Normal shutdown
Application failure
Configuration failure
Container runtime failure
Health/startup problem
```

Si el contenedor salió de forma inesperada, preserve los registros y el estado del contenedor antes de reemplazarlo.

---

# 5. El contenedor arranca pero LUMS no es accesible

La aplicación LUMS no está diseñada para ser accedida directamente a través del puerto de aplicación Docker desde la red.

La aplicación de producción está vinculada a:

```text
127.0.0.1:5050
```

Verifique la vinculación del puerto:

```bash
sudo docker port lums
```

Compruebe también los listeners del host:

```bash
sudo ss -lntp | grep -E ':443|:5050'
```

La arquitectura esperada es:

```text
HTTPS :443
    │
    ▼
  Nginx
    │
    ▼
127.0.0.1:5050
    │
    ▼
Docker
    │
    ▼
LUMS :5000
```

Si el contenedor está en ejecución pero HTTPS falla, investigue las capas individualmente:

1. Contenedor Docker
2. Puerto local de la aplicación
3. Configuración de Nginx
4. TLS
5. Ruta del firewall/red

No exponga el puerto `5050` públicamente como atajo de solución de problemas.

---

# 6. Nginx devuelve un error

Compruebe el servicio:

```bash
sudo systemctl status nginx \
    --no-pager
```

Valide la configuración:

```bash
sudo nginx -t
```

Inspeccione los mensajes recientes de Nginx:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Luego verifique que el contenedor LUMS esté realmente en ejecución:

```bash
sudo docker ps
```

Un error del proxy inverso no significa automáticamente que la aplicación LUMS en sí esté rota.

Las ubicaciones posibles de fallo incluyen:

```text
Browser
   ↓
TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
LUMS
```

Pruebe las capas por separado en lugar de cambiar varios componentes a la vez.

---

# 7. Problemas HTTPS / TLS

Primero pruebe el endpoint HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

Si la verificación del certificado falla, determine si el problema es:

```text
Certificate
Certificate chain
Hostname
Trust store
Nginx configuration
Client CA configuration
```

Valide Nginx:

```bash
sudo nginx -t
```

Si el certificado o la configuración TLS se cambiaron intencionalmente, recargue Nginx:

```bash
sudo systemctl reload nginx
```

Luego pruebe de nuevo:

```bash
curl -I https://LUMS-SERVER/
```

Los clientes que utilizan una autoridad de certificación privada deben confiar en el certificado de CA apropiado.

No deshabilite la verificación del certificado TLS como solución alternativa permanente.

Una prueba de conectividad exitosa que omite la validación del certificado no prueba que la configuración TLS de producción sea correcta.

---

# 8. El servicio del agente falla

Compruebe el servicio:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Lea el journal reciente:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inicie el servicio de nuevo solo después de inspeccionar el resultado anterior:

```bash
sudo systemctl start \
    lums-agent.service
```

Luego compruebe:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

y:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Busque:

```text
Configuration errors
Missing environment values
TLS errors
Authentication failures
API errors
Python exceptions
Package-manager errors
```

No reinstale el agente simplemente porque una única ejecución falló.

---

# 9. El agente informa que falta `LUMS_TOKEN`

El agente normalmente recibe su configuración de producción a través del entorno de su servicio systemd.

Si el agente se inicia manualmente desde un shell, el `EnvironmentFile` de systemd no se carga automáticamente en ese shell.

Por lo tanto:

```bash
sudo /opt/lums-agent/agent.py --version
```

puede comportarse de forma diferente a:

```bash
sudo systemctl start \
    lums-agent.service
```

cuando el token se proporciona exclusivamente a través de la configuración de systemd.

Al investigar problemas de autenticación, pruebe primero el servicio real:

```bash
sudo systemctl start \
    lums-agent.service
```

Luego inspeccione:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

No copie tokens de producción en comandos de shell innecesariamente.

Nunca imprima un token de producción en un registro de diagnóstico.

---

# 10. El agente no puede alcanzar el servidor

Comience con la conectividad de red:

```bash
ping LUMS-SERVER
```

Luego pruebe HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

Si HTTPS funciona pero el agente sigue fallando, investigue:

```text
Client configuration
Client token
TLS trust
API response
Client identity
Agent version
```

Inspeccione el agente:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Al mismo tiempo, inspeccione el servidor:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Esto ayuda a determinar si la solicitud llega a LUMS en absoluto.

Si el cliente ve un fallo de conexión y el servidor no muestra ninguna solicitud correspondiente, investigue la ruta de red o TLS antes de cambiar la configuración de la aplicación.

---

# 11. Continuar con la solución de problemas

Si las capas básicas del servidor, Docker, Nginx, TLS y agente están funcionando, continúe con:

```text
Client Authentication
Token Rotation
Update Detection
Execution Watcher
Idle Detection
Pending Jobs
```

La siguiente sección continúa con la autenticación de clientes y los problemas relacionados con tokens.

# 12. Autenticación de clientes

LUMS utiliza autenticación específica del cliente para la comunicación del agente.

Cuando se registra un cliente, el cliente recibe credenciales que se utilizan para la comunicación autenticada con el servidor LUMS.

Los fallos de autenticación deben investigarse sin exponer el token del cliente.

---

## 12.1 El cliente no es aceptado por LUMS

Si un agente informa un fallo de autenticación, primero inspeccione el registro del agente:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Luego inspeccione los registros del contenedor LUMS:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Busque:

```text
401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure
```

Una respuesta `401` generalmente indica un problema de autenticación.

Una respuesta `403` puede indicar que la autenticación tuvo éxito pero la operación solicitada no está permitida.

No rote el token inmediatamente.

Primero determine si el problema es:

```text
Wrong token
Wrong client ID
Disabled client
Incorrect server URL
TLS problem
Malformed request
Server-side authentication failure
```

---

## 12.2 El cliente existe pero la autenticación falla

Verifique que el cliente todavía existe en la interfaz de administración de LUMS.

No modifique el registro del cliente solo porque una solicitud del agente falló.

Si el cliente existe, compare la identidad del cliente configurada con la identidad utilizada por el agente.

El token de producción en sí nunca debe imprimirse en la salida de diagnóstico.

Utilice metadatos de configuración y el estado del servicio para solucionar problemas en lugar de exponer credenciales.

---

# 13. Rotación del token de cliente

La rotación del token de cliente invalida el token anterior y lo reemplaza con una nueva credencial.

Si un token se rotó intencionalmente, el agente afectado debe recibir el nuevo token antes de que pueda autenticarse de nuevo.

La secuencia esperada es:

```text
Administrator
    │
    ▼
Rotate client token
    │
    ▼
Old token becomes invalid
    │
    ▼
New token assigned to client
    │
    ▼
Agent configuration updated
    │
    ▼
Agent reports again
```

Si el agente continúa usando el token antiguo, la autenticación fallará.

---

## 13.1 Después de la rotación del token

Compruebe el servicio del agente:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Luego ejecute el agente a través de systemd:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspeccione el resultado:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Si la autenticación sigue fallando, inspeccione los registros del servidor:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

No rote el token repetidamente.

La rotación repetida puede dificultar la determinación de qué credencial está actualmente desplegada en el cliente.

---

# 14. El cliente está deshabilitado

Un cliente deshabilitado no debe tratarse como un cliente gestionado activo.

Si un agente perteneciente a un cliente deshabilitado intenta comunicarse, inspeccione el resultado de autenticación del lado del servidor.

Compruebe:

```text
Client identity
Client enabled state
Authentication result
Agent configuration
```

No vuelva a habilitar el cliente solo para hacer desaparecer un error.

Primero determine por qué se deshabilitó el cliente.

---

# 15. Detección de actualizaciones

La detección de actualizaciones consta de varios pasos independientes.

El agente debe:

1. ejecutar la consulta del gestor de paquetes
2. analizar el resultado
3. enviar el resultado a LUMS
4. LUMS debe validar el resultado
5. LUMS debe persistir el resultado
6. la UI debe mostrar el estado actual

Un fallo en cualquier paso puede hacer que la información de actualización parezca incorrecta.

El flujo básico es:

```text
APT / pacman
     │
     ▼
Agent
     │
     ▼
HTTPS
     │
     ▼
LUMS API
     │
     ▼
SQLite
     │
     ▼
Web UI
```

---

## 15.1 No se muestran actualizaciones

Primero determine si el cliente realmente reportó con éxito.

Compruebe:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Luego inspeccione el servidor:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Si el agente se completó correctamente pero no se muestran actualizaciones, investigue el estado de la API y de la base de datos antes de cambiar el gestor de paquetes.

---

## 15.2 Detección de actualizaciones en Debian / Ubuntu

El gestor de paquetes Debian utiliza APT.

Al investigar problemas relacionados con APT, primero verifique que APT en sí está funcionando:

```bash
sudo apt update
```

No ejecute automáticamente actualizaciones de paquetes durante la solución de problemas.

El propósito de esta prueba es determinar si los metadatos del repositorio pueden actualizarse con éxito.

Si APT informa errores de repositorio, DNS, TLS, firma o bloqueo, resuelva el problema subyacente de APT antes de investigar LUMS.

---

## 15.3 Detección de actualizaciones en Arch Linux

Arch Linux utiliza `pacman`.

Compruebe los metadatos del repositorio:

```bash
sudo pacman -Sy
```

Use esto solo cuando la actualización de los metadatos del repositorio sea realmente necesaria para el diagnóstico.

No combine una actualización del sistema innecesaria con una prueba de diagnóstico.

Para errores relacionados con paquetes, inspeccione la salida exacta de `pacman` antes de cambiar la configuración.

---

# 16. Las actualizaciones disponibles difieren entre LUMS y el cliente

La información de actualización puede cambiar entre dos observaciones.

Por ejemplo:

```text
Client reports updates
        ↓
Repository metadata changes
        ↓
Package is upgraded manually
        ↓
LUMS displays older information
```

Por lo tanto, siempre tenga en cuenta la marca de tiempo del último reporte exitoso del cliente.

Una diferencia no indica automáticamente un problema de base de datos.

Compruebe:

```text
Last Agent execution
Last successful report
Package-manager state
Repository metadata
Displayed update state
```

---

# 17. Gestión de paquetes

La gestión de paquetes de LUMS está separada del filtro de paquetes instalados que se muestra en la página del cliente.

El flujo de trabajo de gestión de paquetes es:

```text
User
 │
 ▼
Package Search
 │
 ▼
LUMS API
 │
 ▼
Agent
 │
 ▼
APT / pacman
 │
 ▼
Search Result
 │
 ▼
LUMS API
 │
 ▼
Web UI
```

Instalar, eliminar o actualizar un paquete utiliza el mecanismo normal de trabajos de LUMS.

La ruta de ejecución esperada es:

```text
Package Action
     │
     ▼
Update Job
     │
     ▼
Execution Watcher
     │
     ▼
Agent
     │
     ▼
APT / pacman
```

---

## 17.1 La búsqueda de paquetes no devuelve resultados

Primero verifique que el agente está operativo:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Luego inspeccione el journal del agente:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Para clientes basados en Debian, verifique los metadatos de APT.

Para clientes basados en Arch, verifique los metadatos del repositorio de pacman.

No suponga que un resultado de búsqueda vacío significa que la base de datos de LUMS está vacía.

La búsqueda se realiza a través del gestor de paquetes del cliente.

---

## 17.2 La búsqueda de paquetes funciona pero la instalación falla

Una búsqueda exitosa solo prueba que el gestor de paquetes pudo localizar el paquete.

No prueba que la instalación vaya a tener éxito.

Las causas posibles incluyen:

```text
Dependency conflicts
Repository changes
Package no longer available
Insufficient privileges
Package-manager lock
Disk-space problems
Network problems
Package-manager errors
```

Inspeccione el trabajo de actualización correspondiente.

El journal del agente debería contener el resultado del gestor de paquetes.

---

# 18. Trabajos de instalación de paquetes

La instalación de paquetes utiliza la infraestructura normal de trabajos de actualización.

La acción relevante es:

```text
INSTALL_PACKAGE
```

Al solucionar problemas de una instalación:

1. Compruebe el estado del trabajo en LUMS.
2. Compruebe la ejecución del agente.
3. Compruebe la salida del gestor de paquetes.
4. Compruebe el resultado final reportado a LUMS.

No modifique manualmente el estado del trabajo en SQLite.

El ciclo de vida esperado es:

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

Una instalación de paquete fallida debe seguir siendo rastreable a través de los mecanismos normales de trabajo y auditoría.

---

# 19. Trabajos de eliminación de paquetes

La eliminación de paquetes sigue el mismo ciclo de vida de trabajo.

La acción es:

```text
REMOVE_PACKAGE
```

Cuando una eliminación falla, inspeccione:

```text
Update job
Agent journal
Package-manager output
Final job result
```

No elimine manualmente registros de la base de datos para ocultar una operación de paquete fallida.

Un trabajo fallido es información de diagnóstico útil.

---

# 20. Trabajos de actualización de paquetes

Una actualización específica de un paquete utiliza:

```text
UPDATE_PACKAGE
```

El paquete debe ser conocido por LUMS como que tiene una actualización disponible antes de que se cree el trabajo.

Si la UI no ofrece la actualización de paquete esperada:

1. actualice la información de actualización
2. verifique el estado del gestor de paquetes
3. verifique el resultado de actualizaciones disponibles
4. inspeccione los registros del servidor si el estado es inconsistente

No inserte manualmente registros de actualización en SQLite.

---

# 21. Trabajos de actualización del sistema

Una actualización completa del sistema utiliza:

```text
UPDATE_SYSTEM
```

Esto es diferente de:

```text
UPDATE_PACKAGE
```

La actualización del sistema puede afectar a varios paquetes y puede requerir un reinicio dependiendo del sistema operativo y del estado resultante de los paquetes.

Al solucionar problemas de una actualización del sistema, determine si el fallo ocurrió durante:

```text
Update preparation
Package-manager execution
Result collection
Reboot detection
Post-reboot reporting
```

---

# 22. Bloqueos del gestor de paquetes

Los gestores de paquetes pueden rechazar una operación cuando ya hay otro proceso de gestión de paquetes en ejecución.

Los ejemplos típicos incluyen:

```text
APT is already running
dpkg is locked
pacman is locked
```

Primero identifique el proceso que mantiene el bloqueo.

No elimine archivos de bloqueo a ciegas.

Un archivo de bloqueo puede indicar que otro proceso de gestión de paquetes está legítimamente activo.

Eliminarlo mientras una operación de paquete está en ejecución puede dañar el estado de gestión de paquetes.

La secuencia correcta de solución de problemas es:

```text
Lock error
   ↓
Identify active process
   ↓
Determine whether it is legitimate
   ↓
Wait or resolve the process safely
   ↓
Retry operation
```

---

# 23. Fallo del gestor de paquetes vs. fallo de LUMS

Siempre distinga entre un fallo del gestor de paquetes y un fallo de LUMS.

Por ejemplo:

```text
APT fails
    ↓
Agent reports APT failure
    ↓
LUMS stores FAILED result
```

En este caso, LUMS puede estar funcionando correctamente aunque el trabajo haya fallado.

Por el contrario:

```text
APT succeeds
    ↓
Agent cannot report result
    ↓
LUMS never receives SUCCESS
```

Aquí la operación de paquete puede haber tenido éxito mientras que la ruta de reporte de LUMS falló.

Por lo tanto, el resultado del gestor de paquetes y el resultado del trabajo de LUMS deben investigarse por separado.

---

# 24. Separación de diagnóstico útil

Cuando un trabajo de paquete falla, clasifique primero el fallo:

```text
A. Package-manager failure
B. Agent execution failure
C. Agent reporting failure
D. Server/API failure
E. Database persistence failure
F. UI display problem
```

Esta clasificación evita que se modifiquen componentes no relacionados.

Un error del gestor de paquetes no debería resultar automáticamente en una reconstrucción de Docker.

Un problema de visualización de la UI no debería resultar automáticamente en la eliminación de la base de datos.

Un fallo de autenticación no debería resultar automáticamente en la reinstalación del agente.

---

# 25. Siguiente área de solución de problemas

Si la autenticación de clientes, la detección de actualizaciones y la gestión de paquetes están funcionando, la siguiente área de diagnóstico es el ciclo de vida de ejecución en sí:

```text
Update Job
    ↓
Watcher
    ↓
Agent
    ↓
Execution
    ↓
Result
    ↓
Checkpoint / Recovery
    ↓
Final Job State
```

La siguiente sección cubre **Execution Watcher, detección de inactividad, estado del trabajo, recuperación y manejo de reinicios**.

# 26. Ejecución de trabajos de actualización

Los trabajos de actualización de LUMS se ejecutan de forma asíncrona a través del agente y el execution watcher.

La ruta de ejecución normal es:

```text
User
 │
 ▼
LUMS API
 │
 ▼
SQLite
 │
 ▼
Pending Job
 │
 ▼
Execution Watcher
 │
 ▼
Agent
 │
 ▼
Package Manager
 │
 ▼
Result
 │
 ▼
LUMS API
 │
 ▼
SQLite
```

Un trabajo que es visible en la UI no está necesariamente ya en ejecución.

Siempre determine primero el estado actual del trabajo.

---

## 26.1 El trabajo está atascado en `PENDING`

Si un trabajo permanece en `PENDING`, compruebe el execution watcher antes de investigar el agente.

Compruebe el watcher:

```bash id="wq5h3v"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspeccione la salida reciente del watcher:

```bash id="8y0v7e"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Luego compruebe el agente:

```bash id="j8x4qm"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Un trabajo pendiente normalmente indica que la etapa de ejecución aún no ha comenzado.

Las causas posibles incluyen:

```text
Watcher is not running
Watcher timer is not running
Client is offline
Client is not idle
Client has not reported recently
Job is not eligible for execution yet
```

No cambie manualmente el estado del trabajo en SQLite.

---

# 27. El trabajo está atascado en `RUNNING`

Un trabajo `RUNNING` indica que la ejecución ha comenzado.

Primero determine si el agente está realmente ejecutando el trabajo.

Compruebe:

```bash id="s2z5ek"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Luego inspeccione el watcher:

```bash id="x4f6cb"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Un trabajo en ejecución puede tardar algún tiempo dependiendo de:

```text
Package count
Repository speed
Network latency
Package-manager operations
System load
Reboot requirements
```

No termine una operación de paquete activa solo porque la UI aún no se ha actualizado.

Primero determine si el proceso subyacente sigue activo.

---

# 28. El trabajo está `FAILED`

Un trabajo fallido no indica necesariamente un fallo del servidor LUMS.

Determine qué capa produjo el fallo.

Inspeccione:

```text id="5t9b83"
Job state
Agent execution result
Package-manager result
Server logs
Agent logs
```

Las categorías principales son:

```text
Package-manager failure
Agent execution failure
Agent reporting failure
Server/API failure
Authentication failure
Recovery failure
```

El error original debe preservarse siempre que sea posible.

No reemplace un trabajo fallido con un registro exitoso creado manualmente.

---

# 29. El trabajo está `SUCCESS` pero el paquete no cambió

Un trabajo LUMS exitoso significa que la operación solicitada se completó según el resultado del agente.

Si el estado esperado del paquete no coincide con el resultado del trabajo, verifique el cliente directamente.

Para sistemas basados en Debian:

```bash id="gqdbm7"
dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME
```

Para Arch Linux:

```bash id="2x9f7v"
pacman -Q \
    PACKAGE_NAME
```

Reemplace `PACKAGE_NAME` con el paquete que se está investigando.

Luego compare el estado local del paquete con el resultado de LUMS.

Las explicaciones posibles incluyen:

```text
Package was changed after the job
Package name refers to a virtual/provided package
Package-manager output was interpreted differently than expected
The job result was generated before another local change
```

No modifique la base de datos de LUMS hasta que se haya identificado la discrepancia.

---

# 30. Execution Watcher

El execution watcher es responsable de descubrir trabajos que son elegibles para ejecución.

El watcher debe tratarse como un componente independiente.

Compruebe su servicio:

```bash id="w5m0c8"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Compruebe su temporizador:

```bash id="3v1x7r"
sudo systemctl list-timers \
    --all | grep lums
```

Inspeccione su journal:

```bash id="d5m0xk"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Si el agente funciona pero los trabajos nunca comienzan, el watcher debería ser uno de los primeros componentes a investigar.

---

# 31. El watcher se ejecuta pero no ejecuta trabajos

Una ejecución del watcher no significa automáticamente que se vaya a iniciar un trabajo.

El trabajo debe satisfacer las condiciones de ejecución.

Compruebe:

```text id="m7p2zq"
Client exists
Client is enabled
Client is reachable
Client has recent status
Client is eligible
Job is pending
Job is not already completed
Execution conditions are satisfied
```

Si el cliente no es elegible, el watcher puede dejar correctamente el trabajo pendiente.

Esto no es necesariamente un error.

---

# 32. Detección de inactividad

LUMS puede utilizar la información de inactividad del cliente al decidir si se debe ejecutar un trabajo.

El propósito es evitar iniciar operaciones de mantenimiento mientras el cliente se está utilizando activamente.

Por lo tanto, la decisión de inactividad debe tratarse como una condición de programación, no como un fallo de ejecución.

Un cliente puede reportar con éxito mientras sigue siendo considerado no inactivo.

La secuencia de solución de problemas es:

```text
Agent reports
     ↓
Idle information available?
     ↓
Idle state acceptable?
     ↓
Job eligible?
     ↓
Watcher executes
```

---

## 32.1 El cliente reporta pero no se considera inactivo

Compruebe el journal del agente:

```bash id="5r2q1k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Busque la información de inactividad reportada.

Luego inspeccione el watcher:

```bash id="2a6v8m"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

La distinción importante es:

```text
Agent communication successful
```

frente a:

```text
Client eligible for maintenance execution
```

Estos son estados separados.

---

# 33. La detección de inactividad no está disponible

Algunos sistemas pueden no proporcionar toda la información del estado de inactividad.

Un mecanismo de inactividad no disponible no debe interpretarse automáticamente como un agente roto.

Primero determine la capacidad reportada.

Los conceptos relevantes son:

```text
Idle supported
Idle source
Idle state
Idle duration
```

Si la plataforma no puede proporcionar la información de inactividad esperada, investigue la implementación específica de la plataforma del agente en lugar de modificar la base de datos del servidor.

---

# 34. Recuperación de trabajos de actualización

LUMS utiliza puntos de control y recuperación para evitar que los trabajos de actualización interrumpidos se traten como completados.

Un trabajo puede interrumpirse debido a:

```text
Agent restart
Client reboot
Network interruption
Package-manager interruption
Server restart
Watcher restart
System failure
```

La recuperación debe distinguir entre el trabajo que ya se completó y el trabajo que aún debe ejecutarse.

El principio es:

```text
El trabajo completado permanece completado.
El trabajo incompleto sigue siendo recuperable.
```

---

# 35. Trabajo interrumpido

Si un trabajo fue interrumpido, primero inspeccione su estado.

Luego inspeccione el agente:

```bash id="3u8d4k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspeccione el watcher:

```bash id="w4x1b9"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

No marque manualmente el trabajo como exitoso.

El mecanismo de recuperación debe determinar qué elementos de paquetes ya se completaron.

---

# 36. La recuperación repite una operación de paquete

Cuando se activa la recuperación, los elementos de paquetes ya exitosos no deben ejecutarse de nuevo innecesariamente.

El modelo de recuperación se basa en el estado a nivel de elemento.

Conceptualmente:

```text
Job
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → FAILED
 └── Package D → PENDING
```

La recuperación debe preservar los elementos exitosos y continuar con el trabajo restante.

Si este comportamiento parece incorrecto, inspeccione el historial del trabajo y de los elementos de paquetes antes de cambiar la base de datos.

---

# 37. El cliente se reinicia durante una actualización

Un reinicio puede interrumpir el proceso del agente.

La ruta de recuperación esperada es:

```text
Update starts
    ↓
Package operation
    ↓
Client reboot
    ↓
Agent starts again
    ↓
State is reported
    ↓
LUMS evaluates recovery
```

Por lo tanto, un reinicio no significa automáticamente que el trabajo haya fallado permanentemente.

Inspeccione el servicio del agente después de que el cliente regrese:

```bash id="jjh3u8"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Luego inspeccione las ejecuciones recientes:

```bash id="h7y5gk"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

---

# 38. Detección de reinicio

La detección de reinicio se utiliza para determinar si se produjo un reinicio del sistema como parte de una operación de actualización.

Esto es particularmente relevante cuando una actualización cambia paquetes que requieren un reinicio.

Para Arch Linux, la detección de reinicio no debe confundirse con el estado de salida del gestor de paquetes.

Una operación de paquete puede tener éxito mientras el sistema todavía requiere un reinicio.

Al solucionar problemas del manejo de reinicios, compare:

```text
Package operation result
Reboot requirement
Actual reboot state
Post-reboot Agent report
Final LUMS job state
```

---

# 39. El resultado del trabajo no se reportó

Si la operación de paquete parece haberse completado pero LUMS no muestra el resultado final, investigue la ruta de reporte.

Compruebe el agente:

```bash id="t0r8kf"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Luego compruebe el servidor:

```bash id="h5n1xv"
sudo docker logs \
    --tail 200 \
    lums
```

Si el agente informa un error mientras la operación de paquete en sí tuvo éxito, clasifique el problema como un fallo de reporte en lugar de un fallo de gestión de paquetes.

---

# 40. Reinicio del servidor durante la ejecución de un trabajo

Un reinicio del servidor no debe tratarse automáticamente como prueba de que una operación de actualización falló.

El estado del trabajo debe evaluarse después de que el servidor vuelva a estar disponible.

Compruebe:

```text id="j4t7yw"
Container state
Database availability
Job state
Client state
Agent report
Watcher state
```

El mecanismo de recuperación es responsable de determinar si el trabajo interrumpido puede continuar de forma segura.

No reescriba manualmente los estados de los trabajos después de un reinicio del servidor.

---

# 41. La base de datos está disponible pero el estado del trabajo parece incorrecto

Si SQLite es accesible pero el estado del trabajo parece inconsistente, inspeccione los registros de aplicación y de auditoría antes de modificar la base de datos.

La información útil incluye:

```text
Job ID
Client ID
Job action
Job creation time
Current state
Package-item states
Agent result
Recovery events
Audit events
```

La base de datos es un almacén de datos de la aplicación, no una interfaz de reparación manual.

Las modificaciones directas pueden omitir la validación, la autorización, la auditoría y la lógica de recuperación.

---

# 42. Cambios manuales del estado del trabajo

Los cambios SQL manuales del estado de los trabajos de actualización no deben usarse como solución de problemas normal.

Evite operaciones como:

```sql id="8hbyqv"
UPDATE update_jobs ...
```

o:

```sql id="n1h7yr"
DELETE FROM update_jobs ...
```

a menos que un procedimiento controlado de recuperación de base de datos los requiera explícitamente.

Si una reparación a nivel de base de datos es realmente necesaria, preserve una copia de seguridad y documente el cambio exacto antes de aplicarlo.

Los problemas operativos normales deben resolverse a través de los mecanismos de la aplicación y del agente.

---

# 43. Matriz de diagnóstico de watcher y agente

Use la siguiente matriz para identificar la capa más probable:

| Síntoma                                            | Primer componente a inspeccionar |
| -------------------------------------------------- | -------------------------------- |
| El cliente no puede autenticarse                   | Agente + LUMS API                |
| El cliente reporta con éxito pero el trabajo sigue pendiente | Execution Watcher      |
| El trabajo pasa a running pero no termina          | Agente + gestor de paquetes      |
| La operación de paquete falla                      | Gestor de paquetes               |
| La operación de paquete tiene éxito pero falta el resultado | Reporte del agente    |
| El cliente se reinició durante la actualización    | Agente + recuperación            |
| El trabajo sigue inconsistente después del reinicio | Recuperación + estado de la base de datos |
| El trabajo nunca se descubre                       | Watcher + temporizador           |
| El cliente no es elegible                          | Estado de inactividad / cliente  |
| La UI muestra un estado obsoleto                   | API + último reporte del cliente |

Esta matriz es un punto de partida, no un sustituto de inspeccionar los registros reales y el estado del trabajo.

---

# 44. Siguiente área de solución de problemas

Después de verificar la ejecución de trabajos, las siguientes áreas son:

```text
SQLite and database state
RBAC and user management
Authentication sessions
Application and audit logging
Container security
Tests and CI
```

Estas áreas deben investigarse por separado de la ejecución de paquetes.

# 45. Solución de problemas de SQLite y base de datos

LUMS utiliza SQLite como su base de datos de aplicación.

La base de datos de producción está almacenada dentro del volumen Docker persistente:

```text id="9c6w3e"
/var/lib/lums/lums.db
```

La base de datos es gestionada por la aplicación y normalmente no debe modificarse manualmente.

Al investigar problemas relacionados con la base de datos, primero determine si el problema es:

```text id="4k4z1m"
Database availability
Database locking
Application configuration
Data consistency
Migration state
Application logic
```

---

# 46. La base de datos no está disponible

Si LUMS informa un error de base de datos, primero compruebe si el contenedor está en ejecución:

```bash id="0l5q6h"
sudo docker ps
```

Luego inspeccione los registros de la aplicación:

```bash id="6j5p8m"
sudo docker logs \
    --tail 200 \
    lums
```

No elimine inmediatamente el volumen Docker.

El volumen persistente contiene los datos de producción de la aplicación.

Eliminarlo puede quitar permanentemente:

```text id="4bq9rj"
Users
Clients
Client configuration
Update jobs
Audit data
Application state
```

---

# 47. Bloqueo de la base de datos SQLite

Los problemas de bloqueo de SQLite deben investigarse a través de los registros de la aplicación.

Inspeccione:

```bash id="l8f6vk"
sudo docker logs \
    --tail 200 \
    lums
```

La aplicación de producción utiliza:

```text id="2d3m8x"
journal_mode = wal
busy_timeout = 5000
synchronous = 2
```

La aplicación también habilita la aplicación de claves foráneas de SQLite en sus conexiones a la base de datos.

Un bloqueo de base de datos no significa automáticamente que la base de datos esté corrupta.

Las causas posibles incluyen:

```text id="9w4qcz"
Concurrent writes
Long-running transaction
Application process still using the database
Unexpected process termination
Filesystem problem
```

No elimine archivos de journal de SQLite manualmente.

---

# 48. Claves foráneas de SQLite

LUMS habilita explícitamente la aplicación de claves foráneas de SQLite a nivel de aplicación.

Esto significa que las relaciones entre registros de la base de datos son validadas por SQLite cuando se establece la conexión de la aplicación.

Si ocurre un error relacionado con claves foráneas, inspeccione primero los registros de la aplicación.

No deshabilite la aplicación de claves foráneas para hacer que una operación tenga éxito.

Un fallo de clave foránea puede indicar un problema de lógica de la aplicación o de integridad de datos.

---

# 49. Integridad de la base de datos SQLite

Si se sospecha corrupción de la base de datos, primero deje de hacer cambios innecesarios.

Preserve el estado actual e inspeccione los registros de la aplicación.

Se puede realizar una comprobación de integridad controlada contra una copia de la base de datos.

No realice operaciones de reparación destructivas directamente contra la base de datos de producción a menos que un procedimiento de recuperación documentado lo requiera.

El principio general es:

```text id="t4d1km"
Preserve
   ↓
Inspect
   ↓
Verify
   ↓
Recover
   ↓
Validate
```

Nunca comience con:

```text id="z1f6rw"
Delete database
Recreate database
Recreate Docker volume
```

---

# 50. Migraciones de la base de datos

LUMS utiliza migraciones de aplicación para introducir cambios de esquema en la base de datos.

Cuando ocurre un problema de migración, inspeccione los registros del contenedor:

```bash id="x4h9vf"
sudo docker logs \
    --tail 200 \
    lums
```

Busque:

```text id="m2x7kc"
Migration failure
SQL error
Duplicate column
Missing table
Constraint error
Migration already applied
```

No edite manualmente los registros de migración a menos que el sistema de migración requiera específicamente un procedimiento de recuperación controlado.

Una migración que ya se ha aplicado normalmente no debe ejecutarse manualmente de nuevo.

---

# 51. Volumen de base de datos

La base de datos de LUMS está almacenada en el volumen Docker persistente:

```text id="p6m3jw"
lums-data
```

Inspeccione el volumen:

```bash id="v4c7yq"
sudo docker volume inspect \
    lums-data
```

El volumen debe permanecer persistente a través de la recreación normal del contenedor.

El contenedor de la aplicación en sí es desechable.

Los datos de la aplicación no lo son.

Por lo tanto:

```text id="z9f4ws"
Container
    ≠
Persistent database
```

Recrear el contenedor no debe confundirse con recrear el volumen de datos.

---

# 52. Espacio en disco de la base de datos

SQLite requiere espacio de sistema de archivos disponible para el funcionamiento normal.

Compruebe el sistema de archivos del host:

```bash id="j6k1pt"
df -h
```

También compruebe la disponibilidad de inodos:

```bash id="q2c5ra"
df -i
```

El poco espacio en disco puede producir errores de base de datos que inicialmente parecen problemas de la aplicación.

Si la base de datos se vuelve repentinamente de solo lectura o las escrituras comienzan a fallar, verifique la capacidad del sistema de archivos antes de modificar la configuración de SQLite.

---

# 53. Solución de problemas de RBAC

LUMS utiliza control de acceso basado en roles.

Los roles actuales son:

```text id="k8w5j2"
Administrator
Operator
Viewer
```

Los permisos son intencionalmente diferentes.

---

## 53.1 Administrator

Los administradores pueden:

```text id="n4x7pa"
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

Las operaciones exclusivas de administrador incluyen la gestión de usuarios y la administración de roles.

---

## 53.2 Operator

Los operadores pueden:

```text id="b7c2mz"
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Los operadores no pueden:

```text id="q8v3kd"
Manage users
Manage roles
Create or disable clients
Rotate client tokens
```

---

## 53.3 Viewer

Los viewers tienen acceso deliberadamente restringido.

Un viewer puede:

```text id="y5m2rx"
View clients
View installed software
```

La siguiente funcionalidad está oculta en la interfaz del viewer y bloqueada en el servidor:

```text id="e8c4nw"
Available Updates
Update Jobs
Update History
Package Management
System Maintenance
```

Este es un control de seguridad intencional.

Si un viewer puede acceder a una de estas funciones, trate el problema como un problema de RBAC en lugar de simplemente un problema de UI.

---

# 54. El viewer ve demasiado

Si un viewer ve funcionalidad que no debería estar disponible, compruebe ambas capas:

```text id="x5j3mq"
Browser UI
    +
Server-side authorization
```

Ocultar un elemento en JavaScript o HTML no es seguridad suficiente.

La API también debe rechazar las operaciones no autorizadas.

Al investigar:

1. Determine el rol del usuario autenticado.
2. Identifique el endpoint afectado.
3. Compruebe la respuesta del servidor.
4. Inspeccione los registros de la aplicación si es necesario.
5. Verifique la prueba RBAC relevante.

No resuelva un problema de autorización solo ocultando el elemento de la UI.

---

# 55. El viewer no puede ver los datos esperados

Un viewer todavía debería poder acceder a la información explícitamente permitida por el modelo RBAC actual.

Si falta información de cliente permitida:

```text id="3h6q8f"
Verify login
   ↓
Verify role
   ↓
Verify client visibility
   ↓
Inspect API response
   ↓
Inspect browser console if necessary
```

No conceda permisos adicionales solo porque una página parece actualmente incompleta.

Primero determine si la información faltante está intencionalmente restringida.

---

# 56. El operator no puede realizar una operación

Si un operator recibe `403 Forbidden`, primero determine si la acción solicitada es exclusiva de administrador.

El acceso de operator no incluye:

```text id="n5y7cu"
User management
Role administration
Client creation/deactivation
Client token rotation
```

Si la operación debería estar permitida para los operators, inspeccione el decorador de autorización del endpoint y las pruebas RBAC correspondientes.

No promueva temporalmente al usuario a administrator como atajo de diagnóstico.

---

# 57. El administrator no puede realizar una operación

Un administrator debería tener acceso a todas las operaciones administrativas actualmente compatibles.

Si un administrator recibe un error de autorización:

```text id="q7d2nv"
Verify authenticated session
        ↓
Verify current role
        ↓
Verify endpoint authorization
        ↓
Inspect CSRF requirements
        ↓
Inspect application logs
```

Para las operaciones que modifican el estado, una sesión válida sola puede no ser suficiente.

La protección CSRF también debe satisfacerse cuando sea necesario.

---

# 58. Gestión de usuarios

La gestión de usuarios está restringida a los administradores.

El flujo de trabajo de gestión de usuarios es:

```text id="x4j6pw"
Administrator
    │
    ▼
User Management
    │
    ├── Create user
    ├── Assign role
    └── Enable / disable user
```

Cuando un usuario no puede crearse, compruebe:

```text id="b3q9fz"
Current role
Username validation
Role validation
Duplicate username
Password validation
CSRF protection
Application logs
```

No cree usuarios directamente en SQLite.

La inserción directa en la base de datos omite el hash de contraseñas, la validación, la autorización y el registro de auditoría.

---

# 59. La creación de usuario falla

Si la creación de usuario falla, inspeccione la respuesta del navegador y los registros del servidor.

La API debería validar:

```text id="7x3m5n"
Username
Role
Password requirements
Duplicate account
Authenticated administrator
CSRF token
```

Si la solicitud es rechazada, determine qué regla de validación se activó.

No debilite la validación solo para hacer que una solicitud de creación de cuenta tenga éxito.

---

# 60. Problemas de contraseña

LUMS almacena las contraseñas de usuario usando un mecanismo de hash de contraseñas en lugar de contraseñas en texto plano.

Si un usuario no puede iniciar sesión:

```text id="9w3r5b"
Verify username
   ↓
Verify account enabled state
   ↓
Verify password
   ↓
Check login rate limiting
   ↓
Inspect authentication logs
```

Nunca almacene ni registre contraseñas en texto plano.

No copie contraseñas en comandos de diagnóstico o archivos de registro.

---

# 61. Cuenta de usuario deshabilitada

Una cuenta deshabilitada no debe tratarse como una cuenta de inicio de sesión activa.

Si un usuario deshabilitado todavía puede autenticarse, investigue:

```text id="z6t2hx"
Current account state
Authentication lookup
Session state
Session revocation
Browser session
Server-side authorization
```

No elimine simplemente la cuenta.

Preservar la cuenta puede ser importante para el historial de auditoría.

---

# 62. Problemas de sesión

LUMS utiliza gestión de sesiones del lado del servidor.

Cuando un usuario parece tener acceso obsoleto o inesperado, primero cierre la sesión y establezca una nueva.

Si el problema persiste, investigue:

```text id="q1y7vm"
Account state
Role
Session state
Session revocation
Cookie configuration
CSRF protection
```

No deshabilite los controles de seguridad de sesión para eludir un problema de inicio de sesión.

---

# 63. Revocación de sesión

La revocación de sesión es relevante cuando:

```text id="4n8z7p"
A password changes
A user is disabled
A role changes
A session must be invalidated
A security event requires forced logout
```

Si un usuario parece conservar el acceso después de un cambio de cuenta, determine si la sesión existente se invalidó correctamente.

Pruebe con una nueva sesión del navegador solo después de confirmar el estado de la cuenta.

No suponga que eliminar las cookies del navegador por sí solo demuestra que la revocación de sesión del lado del servidor funciona.

---

# 64. Limitación de la tasa de inicio de sesión

LUMS aplica limitación de la tasa de inicio de sesión a los intentos de autenticación fallidos repetidos.

El comportamiento actual utiliza intervalos de bloqueo crecientes:

```text id="p7k4xz"
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

El estado de fallo se persiste en SQLite.

Si los intentos de inicio de sesión están bloqueados inesperadamente, inspeccione el estado de autenticación antes de cambiar la base de datos.

Una respuesta de limitación de tasa no es automáticamente un fallo de autenticación.

Puede indicar que la cuenta ha alcanzado el umbral configurado de intentos fallidos.

---

# 65. El inicio de sesión funciona pero la API devuelve `403`

Un inicio de sesión exitoso prueba la autenticación, no la autorización.

Una respuesta `403 Forbidden` puede indicar:

```text id="m9c2vx"
Insufficient role
Missing CSRF protection
Disallowed operation
Disabled functionality
```

Identifique el endpoint exacto antes de cambiar nada.

La pregunta correcta de solución de problemas es:

```text id="0q4g1k"
"Is this user authenticated?"
```

seguida de:

```text id="x8v5md"
"Is this authenticated user authorized for this operation?"
```

Estas son comprobaciones de seguridad separadas.

---

# 66. Errores CSRF

Las solicitudes de navegador que modifican el estado están protegidas contra la falsificación de solicitudes entre sitios.

Si una solicitud que modifica el estado falla inesperadamente:

```text id="6z4qpn"
Verify authenticated session
        ↓
Verify CSRF token
        ↓
Verify request method
        ↓
Verify endpoint
        ↓
Inspect server response
```

No deshabilite la protección CSRF como solución alternativa de solución de problemas.

Una comprobación CSRF fallida es un control de seguridad funcionando según lo previsto.

---

# 67. La UI del navegador y la API no coinciden

Si la UI muestra que una acción está disponible pero la API la rechaza:

```text id="v8n3ty"
Browser UI
   ↓
Displayed role/state
   ↓
API request
   ↓
Server-side authorization
```

El resultado del lado del servidor es autoritativo.

La UI puede contener estado obsoleto después de:

```text id="4g7m2x"
Role changes
Session changes
Client changes
Page remains open for a long time
```

Recargue la página y establezca una nueva sesión antes de suponer que la autorización del lado del servidor es incorrecta.

---

# 68. Matriz de diagnóstico RBAC

| Síntoma                          | Primer componente a inspeccionar        |
| -------------------------------- | --------------------------------------- |
| El viewer ve la UI de gestión    | Manejo del rol de la página del cliente |
| La solicitud API del viewer tiene éxito | RBAC del lado del servidor       |
| El operator recibe `403`         | Modelo de permisos del endpoint         |
| El administrator recibe `403`    | Sesión / CSRF / autorización del endpoint |
| El usuario no puede ser creado   | Rol de admin + validación               |
| Un usuario deshabilitado puede iniciar sesión | Estado de la cuenta + manejo de sesión |
| Inicio de sesión bloqueado temporalmente | Limitación de la tasa           |
| Solicitud que modifica el estado rechazada | CSRF / sesión                  |
| La UI y la API no coinciden      | Estado del navegador + autorización del servidor |

El resultado de la autorización del lado del servidor siempre es más importante que si un elemento de la interfaz es visible.

---

# 69. Siguiente área de solución de problemas

Las siguientes áreas de diagnóstico son:

```text id="8r5w2q"
Application and audit logging
Container security
Filesystem permissions
Docker runtime configuration
Tests and CI
Diagnostic snapshots
Final recovery checklist
```

Estas áreas deben investigarse sin debilitar la línea base de seguridad.

# 70. Registro de aplicación

LUMS utiliza el registro de aplicación para proporcionar información de diagnóstico sin exponer credenciales sensibles.

Al investigar un problema de la aplicación, comience con los registros más recientes:

```bash id="f6m2qa"
sudo docker logs \
    --tail 200 \
    lums
```

Para supervisión continua:

```bash id="x3v8kp"
sudo docker logs \
    -f \
    lums
```

Cuando sea posible, reproduzca el problema mientras supervisa los registros.

Esto facilita la correlación de:

```text id="p8k4zw"
User action
    ↓
HTTP request
    ↓
Application event
    ↓
Database operation
    ↓
Agent interaction
```

---

# 71. Los registros de aplicación contienen un error

Primero identifique el componente que produjo el mensaje.

Las fuentes típicas incluyen:

```text id="w4c8rn"
Flask application
Gunicorn
Database layer
Authentication
Authorization
Package management
Job execution
Client reporting
```

No suponga que el último mensaje del registro es la causa raíz.

Busque el primer error relevante en la secuencia de eventos.

Cuando sea posible, correlacione:

```text id="n6q2vy"
Timestamp
Client
Request
Job ID
Error
Result
```

---

# 72. Registro de auditoría

LUMS registra acciones de la aplicación relevantes para la seguridad en el registro de auditoría.

El registro de auditoría es útil al investigar:

```text id="j8r4px"
User changes
Authentication events
Administrative actions
Client management
Token operations
Update-job creation
Security-relevant state changes
```

Un evento de auditoría debe tratarse como evidencia de un evento de la aplicación, no como un sustituto de los registros del sistema.

Use los registros de aplicación para detalles técnicos de ejecución y los registros de auditoría para acciones de la aplicación relevantes para la seguridad.

---

# 73. Falta un evento de auditoría

Si falta un evento de auditoría esperado:

1. Identifique la acción exacta.
2. Identifique el endpoint de la API.
3. Verifique que la acción realmente llegó al servidor.
4. Inspeccione los registros de la aplicación.
5. Determine si la acción fue rechazada antes de que se debiera haber creado el evento de auditoría.

No inserte manualmente registros de auditoría simplemente para hacer que una pista de auditoría parezca completa.

Un registro de auditoría debe corresponder a un evento real de la aplicación.

---

# 74. El registro de auditoría y el registro de aplicación difieren

Los dos sistemas de registro tienen propósitos diferentes.

Por ejemplo:

```text id="7q2m5k"
Application log
→ technical execution information

Audit log
→ security-relevant application event
```

Por lo tanto, un error del gestor de paquetes puede aparecer en el registro de la aplicación o del agente sin representar un evento de auditoría administrativa separado.

Por el contrario, una acción de gestión de usuarios debería producir un evento de aplicación auditable incluso si la operación en sí es técnicamente simple.

---

# 75. Información sensible en los registros

Nunca coloque intencionalmente lo siguiente en la salida de diagnóstico:

```text id="3m7v9x"
Client tokens
Application secret keys
Passwords
Session secrets
Private keys
TLS private material
```

Si un comando de diagnóstico expusiera uno de estos valores, utilice en su lugar una comprobación redactada o solo de metadatos.

Al compartir registros para la solución de problemas, revíselos en busca de secretos antes de copiarlos en tickets, documentación, issues de GitHub o chat.

---

# 76. Seguridad del contenedor Docker

El contenedor LUMS de producción está intencionalmente endurecido.

Las propiedades de seguridad esperadas incluyen:

```text id="z4w6pt"
Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges enabled
No privileged mode
Dedicated writable data volume
Read-only secret mount
Restricted temporary filesystems
```

Si una de estas propiedades cambia inesperadamente, trátela como una desviación de la configuración.

No debilite el contenedor para resolver un problema de la aplicación a menos que el impacto en la seguridad se haya evaluado explícitamente.

---

# 77. Verificar la seguridad en tiempo de ejecución del contenedor

Inspeccione el contenedor:

```bash id="b8x5jq"
sudo docker inspect lums
```

Para una comprobación centrada en el tiempo de ejecución:

```bash id="r3n7cw"
sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums
```

Los valores esperados incluyen:

```text id="k5m2zr"
ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]
```

El formato exacto puede variar entre versiones de Docker.

Lo que importa son las propiedades de seguridad en sí.

---

# 78. El contenedor se ejecuta como root

La aplicación LUMS debería ejecutarse como su usuario de aplicación sin privilegios dedicado.

Si el contenedor se ejecuta inesperadamente como root, primero inspeccione la imagen y la configuración de tiempo de ejecución:

```bash id="p6x4nz"
sudo docker inspect \
    --format='{{.Config.User}}' \
    lums
```

Luego inspeccione el Dockerfile.

No resuelva problemas de permisos de la aplicación cambiando el contenedor de producción a root.

Si un directorio requiere acceso de escritura, identifique la ruta exacta y determine si debe ser datos persistentes de la aplicación o datos temporales.

---

# 79. Sistema de archivos raíz de solo lectura

El contenedor de producción utiliza un sistema de archivos raíz de solo lectura.

Esto protege la imagen de la aplicación de modificaciones innecesarias en tiempo de ejecución.

Si la aplicación informa:

```text id="y5k8mc"
Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data
```

primero determine **dónde** la aplicación está intentando escribir.

Las ubicaciones escribibles esperadas están deliberadamente limitadas.

Los datos persistentes de la aplicación pertenecen a:

```text id="q9m3xr"
/var/lib/lums
```

Los datos temporales de tiempo de ejecución pueden usar los sistemas de archivos temporales configurados.

No deshabilite `--read-only` solo porque una ruta de la aplicación sea inesperadamente escribible.

---

# 80. `/tmp` no es escribible

Si la aplicación requiere almacenamiento temporal, verifique el sistema de archivos temporal:

```bash id="a7w4vn"
sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums
```

El contenedor de producción proporciona un `/tmp` restringido.

El sistema de archivos temporal está destinado únicamente a datos transitorios.

Los datos persistentes no deben almacenarse allí.

---

# 81. Problemas con el montaje del secreto

El secreto de la aplicación LUMS se proporciona a través de un montaje de archivo protegido.

El secreto no debe integrarse directamente en la imagen.

Si LUMS informa que falta un secreto, primero inspeccione la configuración de tiempo de ejecución:

```bash id="j4p7zx"
sudo docker inspect \
    lums
```

Compruebe que el montaje del secreto existe y es de solo lectura.

No imprima el contenido del secreto.

Un diagnóstico útil es verificar que el archivo existe y tiene los permisos esperados sin mostrar su contenido.

---

# 82. Falta el archivo del secreto

Si el archivo del secreto no existe en el host y no se ha configurado el valor alternativo `LUMS_SECRET_KEY`, la aplicaci?n falla inmediatamente al iniciarse con `RuntimeError: LUMS secret is not configured. Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY.` (`server/app.py`). Se trata de un fallo de inicio, no simplemente de un s?ntoma de autenticaci?n. Consulte la secci?n 114 para conocer los detalles de la alternativa entre archivo y variable.
---

# 83. El volumen persistente no es escribible

Si LUMS no puede escribir datos de la aplicación, inspeccione el volumen:

```bash id="y6c2mt"
sudo docker volume inspect \
    lums-data
```

Luego inspeccione los montajes del contenedor:

```bash id="e5w8rq"
sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums
```

La base de datos de la aplicación debe residir en el volumen persistente escribible.

No haga que todo el sistema de archivos del contenedor sea escribible como solución alternativa.

La solución correcta es identificar la ruta específica que requiere persistencia.

---

# 84. El contenedor Docker arranca pero la aplicación falla

Si el contenedor arranca y se cierra inmediatamente:

```bash id="t7x3mp"
sudo docker ps -a \
    --filter name=lums
```

Luego inspeccione:

```bash id="n4q6vz"
sudo docker logs \
    --tail 200 \
    lums
```

Las causas comunes incluyen:

```text id="w3j8kc"
Application startup error
Missing secret
Database initialization error
Migration failure
Invalid environment configuration
Permission problem
Dependency problem
```

No reconstruya la imagen inmediatamente.

Determine si el problema está en la imagen, la configuración de tiempo de ejecución, los datos persistentes o la configuración externa.

---

# 85. Imagen Docker vs. configuración del contenedor

Una imagen funcional todavía puede fallar debido a una configuración de tiempo de ejecución incorrecta.

Siempre distinga:

```text id="s7q2mj"
Docker image
    +
Container runtime configuration
    +
Persistent volume
    +
Secret/configuration
```

Por ejemplo:

```text id="m5v9rz"
Image is valid
      +
Wrong volume
      =
Application failure
```

o:

```text id="r6c3pk"
Image is valid
      +
Missing secret
      =
Application startup failure
```

No reconstruya una imagen por lo demás válida para corregir un problema de configuración de tiempo de ejecución.

---

# 86. Problemas de construcción de Docker

Si no se puede construir una nueva imagen, primero inspeccione el Dockerfile.

Compruebe la imagen base y las definiciones de dependencias.

El Dockerfile de producción utiliza un digest de imagen base Python fijado.

Esto proporciona reproducibilidad y evita que la construcción se desplace silenciosamente a una revisión de imagen base no relacionada.

Si una construcción cambia repentinamente de comportamiento, compare:

```text id="e3y7pn"
Dockerfile
Base-image digest
Requirements
Application source
Build context
```

---

# 87. Problemas con `.dockerignore`

El contexto de construcción de Docker no debe contener archivos locales innecesarios ni material sensible.

El repositorio utiliza `.dockerignore` para excluir archivos como:

```text id="k2x8vw"
Local backups
Temporary files
Editor artifacts
Backup copies
Other unnecessary runtime material
```

Si una construcción contiene inesperadamente un archivo que no debería estar presente, inspeccione:

```bash id="q5m8cz"
cat .dockerignore
```

No resuelva problemas del contexto de construcción copiando archivos sensibles en la imagen.

---

# 88. Problemas de permisos del sistema de archivos

Si LUMS informa errores de permisos, primero identifique la ruta exacta.

Información útil:

```bash id="p4r7yn"
sudo docker inspect \
    lums
```

y:

```bash id="n8v2km"
sudo docker logs \
    --tail 200 \
    lums
```

La distinción importante es:

```text id="x6c9pw"
Application data
Temporary data
Application source
Secret material
Host configuration
```

Cada uno tiene permisos esperados diferentes.

No cambie recursivamente la propiedad o los permisos en todo el sistema de archivos como atajo de solución de problemas.

---

# 89. Desviación de la configuración de producción

La desviación de la configuración ocurre cuando el entorno en ejecución ya no coincide con la línea base de seguridad prevista.

Los ejemplos incluyen:

```text id="r5j8tx"
Container runs as root
Port 5050 exposed externally
Read-only filesystem disabled
Capabilities restored
Privileged mode enabled
Secret mounted read-write
Unexpected container running
```

Si se detecta una desviación:

1. Registre el estado actual.
2. Determine cuándo cambió.
3. Identifique la configuración responsable.
4. Corrija la configuración deliberadamente.
5. Vuelva a ejecutar la verificación de seguridad relevante.

No haga varios cambios no relacionados a la vez.

---

# 90. Exposición de red inesperada

El puerto de la aplicación debe permanecer local:

```text id="n7w4cp"
127.0.0.1:5050
```

Compruebe los listeners:

```bash id="y2m6vk"
sudo ss -lntp
```

Si `5050` está expuesto en una dirección que no sea loopback, investigue inmediatamente el mapeo de puertos de Docker.

No exponga el puerto de la aplicación solo porque Nginx parece difícil de diagnosticar.

La arquitectura prevista es:

```text id="h3x8qm"
Network
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS
```

---

# 91. Contenedores Docker inesperados

Liste todos los contenedores:

```bash id="c6w9rz"
sudo docker ps -a
```

Los contenedores inesperados deben identificarse antes de eliminarlos.

Compruebe:

```text id="m8x2kf"
Container name
Image
Creation time
Ports
Volumes
Restart policy
```

No elimine un contenedor desconocido sin determinar si forma parte del despliegue de LUMS o de un entorno de respaldo requerido.

---

# 92. El volumen Docker no debe eliminarse durante la solución de problemas normal

La siguiente operación es destructiva:

```bash id="q7v3mc"
sudo docker volume rm lums-data
```

No debe usarse como paso general de solución de problemas.

Eliminar el volumen puede quitar la base de datos de la aplicación y el estado persistente asociado.

Si se requiere intencionalmente una instalación limpia, trátela como una operación separada de migración o recuperación y verifique primero las copias de seguridad.

---

# 93. Línea base de seguridad después de cambios en tiempo de ejecución

Después de cambiar la configuración de Docker de producción, verifique de nuevo la línea base de seguridad.

Como mínimo verifique:

```text id="z5n8xp"
Container runs as intended user
Root filesystem is read-only
Capabilities are dropped
Privileged mode is disabled
no-new-privileges is enabled
Secret mount is read-only
Database volume is writable
Application port is loopback-only
```

Una configuración que hace funcionar la aplicación pero debilita estas propiedades no debe considerarse una corrección exitosa.

---

# 94. Siguiente área de solución de problemas

Los temas restantes de solución de problemas son:

```text id="v4m7yx"
Tests and CI
Diagnostic snapshots
Common failure combinations
Recovery principles
Final troubleshooting checklist
```

Las secciones finales proporcionan un procedimiento compacto para recopilar suficiente información para diagnosticar un problema sin cambiar innecesariamente el entorno de producción.

# 95. Pruebas y CI

Las pruebas automatizadas son una parte importante de la solución de problemas de LUMS.

Antes de investigar un problema de producción como un defecto de la aplicación, verifique si el comportamiento relevante ya está cubierto por la suite de pruebas.

La suite de pruebas completa actual debe pasar antes de que una versión se considere lista.

Ejecute la suite de pruebas completa desde el repositorio:

```bash id="m4x8kp"
./.venv-test/bin/pytest -q
```

Una ejecución exitosa debería informar que todas las pruebas pasaron.

El número de pruebas cambia a medida que se añaden pruebas adicionales. La condición importante es que la suite de pruebas completa tenga éxito en lugar de depender de un número fijo de pruebas.

---

# 96. Un fallo de prueba no significa automáticamente que la producción esté rota

Una prueba fallida puede ser causada por:

```text id="q8r5wy"
Application regression
Test regression
Dependency change
Environment problem
Missing test dependency
Incorrect test configuration
```

Primero inspeccione la salida completa del fallo.

No modifique la configuración de producción simplemente porque una prueba local falla.

La secuencia correcta es:

```text id="n4m7tx"
Test failure
    ↓
Read complete error
    ↓
Identify affected component
    ↓
Reproduce locally
    ↓
Determine root cause
    ↓
Apply controlled fix
    ↓
Run relevant tests
    ↓
Run full test suite
```

---

# 97. Fallos de pruebas RBAC

Al investigar problemas de autorización, ejecute primero las pruebas RBAC:

```bash id="k6w2pv"
./.venv-test/bin/pytest -q tests/test_rbac.py
```

Las pruebas cubren el comportamiento específico del rol y las fronteras de autorización.

Si el problema concierne a la página del cliente, use el subconjunto relevante cuando corresponda:

```bash id="z5n8rc"
./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page
```

No debilite la autorización para hacer que una prueba pase.

Una prueba de autorización fallida puede indicar una regresión de seguridad.

---

# 98. Fallos de pruebas de búsqueda de paquetes

La funcionalidad de gestión de paquetes tiene cobertura de pruebas dedicada.

Al investigar el comportamiento de búsqueda de paquetes:

```bash id="b7x3mf"
./.venv-test/bin/pytest -q \
    tests/test_package_search.py
```

Si el fallo implica la ejecución de paquetes o los resultados de trabajos, inspeccione también las pruebas relevantes de resultados de trabajos.

La suite de pruebas debe usarse para distinguir:

```text id="y9r4nk"
Application logic problem
Package-search problem
Agent problem
Integration problem
```

---

# 99. Pruebas de validación de resultados de trabajos

El manejo de resultados de trabajos es sensible a la seguridad porque el servidor no debe confiar ciegamente en la entrada arbitraria del cliente.

Ejecute las pruebas relevantes al investigar la validación de resultados:

```bash id="w6q2vz"
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Un fallo aquí debe tratarse como un problema de corrección de la aplicación y de seguridad.

No omita la validación de resultados para hacer que un reporte de cliente tenga éxito.

---

# 100. Fallos de CI

LUMS utiliza integración continua para verificar el proyecto antes de que se acepten cambios.

Si CI falla:

1. Identifique el trabajo fallido.
2. Lea el error completo.
3. Determine si el fallo está relacionado con el código, las dependencias, las pruebas o el entorno.
4. Reproduzca localmente cuando sea posible.
5. Corrija la causa raíz.
6. Ejecute las pruebas relevantes.
7. Ejecute la suite de pruebas completa.

No ignore los fallos de CI simplemente porque el entorno de producción parece actualmente funcional.

---

# 101. Instantánea de diagnóstico

Cuando pida ayuda con un problema de LUMS, recopile una instantánea de diagnóstico mínima.

El objetivo es proporcionar suficiente información para identificar el componente que falla sin exponer secretos.

Una instantánea útil incluye:

```bash id="x8p4qn"
sudo docker ps
```

```bash id="c5m7vz"
sudo docker logs --tail 100 lums
```

```bash id="f2w9yk"
sudo systemctl status nginx --no-pager
```

```bash id="n6r3tx"
sudo systemctl status lums-agent.service --no-pager
```

```bash id="q7v4mc"
sudo systemctl status lums-agent-watcher.service --no-pager
```

```bash id="z3k8wp"
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

```bash id="h5m2rx"
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

```bash id="p9x6kc"
sudo ss -lntp
```

Utilice solo los comandos relevantes para el problema.

No vuelque el entorno completo en una solicitud de soporte.

---

# 102. La instantánea de diagnóstico no debe contener secretos

Antes de compartir la salida de diagnóstico, compruebe:

```text id="r4m8yn"
Passwords
Client tokens
Application secret keys
Session secrets
Private keys
TLS private material
Credentials
```

Redacte los valores sensibles antes de compartir.

No suponga que un registro es seguro simplemente porque proviene de un servicio del sistema.

---

# 103. Matriz de combinaciones de fallos

Algunos síntomas se vuelven más fáciles de diagnosticar cuando se consideran varios componentes juntos.

| Síntoma                                       | Área más probable a inspeccionar primero |
| --------------------------------------------- | ---------------------------------------- |
| El navegador no puede conectar                | Nginx / TLS / red                        |
| Nginx funciona pero la aplicación falla       | Docker / LUMS                            |
| LUMS funciona pero el cliente no puede reportar | Agente / TLS / token                   |
| El cliente reporta pero el trabajo sigue pendiente | Watcher / elegibilidad              |
| El trabajo se ejecuta pero el paquete falla   | APT / pacman                             |
| El paquete tiene éxito pero falta el resultado | Reporte del agente                      |
| El resultado llega al servidor pero la UI está obsoleta | API / base de datos / estado del navegador |
| El viewer puede modificar datos               | RBAC del lado del servidor               |
| El usuario no puede iniciar sesión            | Cuenta / contraseña / limitación de tasa |
| El inicio de sesión funciona pero la acción es rechazada | RBAC / CSRF                    |
| Las escrituras de base de datos fallan        | SQLite / disco / permisos                |
| El contenedor pierde datos después de la recreación | Configuración del volumen persistente |
| La aplicación escribe en el sistema de archivos raíz | Configuración del sistema de archivos del contenedor |
| El puerto 5050 es accesible externamente      | Configuración de Docker / firewall       |

Esta tabla identifica el primer lugar a investigar, no necesariamente la causa raíz final.

---

# 104. Errores comunes de solución de problemas

Evite los siguientes atajos:

## No elimine la base de datos

```text id="h7k2px"
Deleting lums.db
Deleting lums-data
```

puede destruir el estado persistente de la aplicación.

---

## No deshabilite los controles de seguridad

No deshabilite permanentemente:

```text id="j5r9cw"
RBAC
CSRF protection
TLS validation
Container hardening
Read-only filesystem
no-new-privileges
Capability restrictions
```

Una solución alternativa que elimina un control de seguridad no es una corrección completada.

---

## No ejecute el contenedor como privilegiado

Evite:

```text id="b3x7mz"
--privileged
```

como solución de solución de problemas.

Si la aplicación requiere acceso adicional, determine exactamente qué acceso se requiere.

---

## No exponga el puerto 5050

No cambie:

```text id="v8n4qr"
127.0.0.1:5050
```

a:

```text id="p2m6wy"
0.0.0.0:5050
```

simplemente para eludir Nginx.

La aplicación está intencionalmente protegida detrás del proxy inverso.

---

## No modifique los estados de los trabajos manualmente

Evite cambiar directamente:

```text id="r7c5xn"
update_jobs
update_job_packages
```

para ocultar un problema operativo.

Use los mecanismos de la aplicación, el agente, el watcher y la recuperación.

---

## No elimine los bloqueos del gestor de paquetes a ciegas

Un bloqueo puede indicar un proceso del gestor de paquetes activo.

Identifique primero el proceso.

---

## No rote las credenciales repetidamente

La rotación repetida de tokens o secretos puede crear problemas de autenticación adicionales.

Primero determine qué credencial está configurada actualmente y qué credencial espera el servidor.

---

# 105. Principios de recuperación

Los siguientes principios se aplican a toda la solución de problemas de LUMS:

### Preservar primero

Mantenga:

```text id="q3m8vx"
Logs
Job state
Database
Container state
Configuration
Error messages
```

hasta que se comprenda el problema.

### Cambie una cosa a la vez

Cuando se hacen varios cambios simultáneamente, la causa original se vuelve más difícil de identificar.

### Verifique después de cada cambio

Después de un cambio controlado:

```text id="z6w2kp"
Re-test
Check logs
Verify state
Confirm security properties
```

### Prefiera cambios reversibles

Siempre que sea posible, use cambios que puedan revertirse sin destruir el estado de la aplicación.

### Mantenga los controles de seguridad activos

Un resultado exitoso de solución de problemas no debe introducir una regresión de seguridad innecesaria.

---

# 106. Secuencia de solución de problemas de producción

Para un problema general de producción de LUMS, use este orden:

```text id="f4n8rx"
1. Identify the symptom
        ↓
2. Identify the affected component
        ↓
3. Inspect current state
        ↓
4. Inspect relevant logs
        ↓
5. Reproduce safely
        ↓
6. Determine the first failing layer
        ↓
7. Apply the smallest required change
        ↓
8. Re-test
        ↓
9. Verify security controls
        ↓
10. Document the result
```

Este orden evita que se cambien innecesariamente componentes no relacionados.

---

# 107. Ruta de diagnóstico del sistema completo

Cuando se desconoce el componente afectado, siga la ruta completa:

```text id="u7x3mp"
Browser
  │
  ▼
Nginx / HTTPS
  │
  ▼
Docker
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Update Job
  │
  ▼
Watcher
  │
  ▼
Agent
  │
  ▼
APT / pacman
  │
  ▼
Client state
  │
  ▼
Agent result
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Web UI
```

En cada etapa, pregunte:

```text id="k5r2qy"
Did the request reach this component?

Did this component process it?

Did it produce the expected result?

Did the next component receive that result?
```

El primer `NO` normalmente identifica el área que requiere investigación.

---

# 108. Solución de problemas de versión

Antes de preparar una versión, verifique:

```text id="m8x4vp"
Full test suite passes
CI passes
Security audit is complete
Documentation is current
Production configuration matches the documented baseline
No unexpected debug configuration remains
No secrets are included in the repository
Docker hardening remains active
RBAC behavior is correct
Package management works
Update-job execution works
Recovery behavior is verified
```

No se debe crear una versión simplemente porque la aplicación arranca correctamente.

---

# 109. Lista de comprobación de solución de problemas

Use esta lista de comprobación antes de declarar resuelto un problema de producción:

```text id="y6q3kn"
[ ] Root cause identified
[ ] Relevant logs inspected
[ ] No unnecessary data was deleted
[ ] No credentials were exposed
[ ] No security control was disabled
[ ] Relevant functionality tested
[ ] Full test suite considered where appropriate
[ ] Docker security baseline verified
[ ] Network exposure verified
[ ] Agent state verified
[ ] Watcher state verified
[ ] Job state verified
[ ] Recovery state verified
[ ] Database state verified where relevant
[ ] Documentation updated if behavior changed
```

---

# 110. Cuándo dejar de solucionar problemas

Deje de hacer cambios cuando:

```text id="v9m4xr"
The root cause is identified
    AND
The corrective action is understood
    AND
The system is stable
    AND
Security controls remain intact
```

Si no se comprende la causa raíz, preserve el estado actual en lugar de cambiar repetidamente el entorno.

Un fallo preservado limpiamente es más fácil de diagnosticar que un sistema parcialmente modificado.

---

# 111. Principio de recuperación final

La regla más importante de solución de problemas de LUMS es:

> **Observar primero. Cambiar segundo. Verificar tercero.**

LUMS contiene varias capas independientes de seguridad y ejecución.

Un problema en una capa no debería resultar automáticamente en cambios en otra.

Por lo tanto, el enfoque preferido de solución de problemas es:

```text id="c8w5zn"
Observe
   ↓
Classify
   ↓
Isolate
   ↓
Correct
   ↓
Verify
   ↓
Document
```

Esto mantiene la solución de problemas controlada, reproducible y compatible con la línea base de seguridad de LUMS.

---

# 112. Mantenimiento de la documentación

Este documento debe actualizarse cada vez que cambie un comportamiento operativo documentado.

Los cambios de documentación deben permanecer consistentes con:

```text id="q7m3vx"
Security documentation
Deployment documentation
Agent behavior
Watcher behavior
RBAC model
Package-management behavior
Docker runtime configuration
Test baseline
```

Las instrucciones de solución de problemas obsoletas pueden ser peligrosas cuando recomiendan comandos obsoletos o soluciones alternativas que debilitan la seguridad.

Cuando cambia un comportamiento de producción, actualice la documentación relevante antes de considerar completa la solución de problemas.

---

# 113. L?nea base actual

La l?nea base actual de LUMS documentada por esta gu?a de soluci?n de problemas incluye:

```text id="m4x8qp"
Agent version: 1.7.0
Watcher version: 1.2.1

Application port:
127.0.0.1:5050

Database:
SQLite

SQLite journal mode:
WAL (enabled by server/init_db.py; verify on your database with
sqlite3 <db> "pragma journal_mode;")

SQLite busy timeout:
5000 ms

SQLite synchronous:
2

SQLite foreign keys:
Enabled by the application

Container:
Non-root
Read-only root filesystem
Capabilities dropped
no-new-privileges enabled
Privileged mode disabled

RBAC:
Administrator
Operator
Viewer

Viewer:
Clients + Installed Software only

Full test suite:
Run on Linux (the CI reference is Ubuntu with Python 3.13). Some tests
assume Linux features such as os.geteuid() or an installed apt/pacman and
can fail on Windows; check the CI result for the revision you deploy.
```

No considere esta l?nea base como prueba de que una instalaci?n concreta est? en buen estado; verifique cada valor en el sistema de destino.

Las propiedades de seguridad y arquitectura son la l?nea base importante.

---

# 114. Errores de configuraci?n al iniciar

**S?ntoma:** El contenedor se cierra inmediatamente, o el servidor utiliza una base de datos o un directorio de copias de seguridad distintos de los que sugieren los vol?menes de Docker.

**Hechos del c?digo (`server/app.py`):**

- Sin un secreto, la aplicaci?n genera `RuntimeError: LUMS secret is not configured. Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY.`
- Si no existe el archivo indicado por `LUMS_SECRET_KEY_FILE`, el c?digo recurre a `LUMS_SECRET_KEY`. Solo se gestiona as? la ausencia del archivo; un archivo ilegible (por permisos) puede generar un error del sistema de archivos.
- `LUMS_DB_PATH` y `LUMS_BACKUP_DIR` reemplazan los valores predeterminados `/var/lib/lums/lums.db` y `/var/backups/lums`. Una sobrescritura obsoleta dirige silenciosamente LUMS a una ubicaci?n distinta de la del volumen montado.

**Verificaci?n (solo lectura):**

```text
docker compose logs lums | grep "LUMS secret"
docker inspect lums --format '{{range .Config.Env}}{{println .}}{{end}}'
ls -l <secret file>   # permissions only; never print the contents
```

**Soluci?n:** Corrija la ruta del secreto o sus permisos, o elimine las sobrescrituras obsoletas de `LUMS_DB_PATH` / `LUMS_BACKUP_DIR`. No genere un secreto de reemplazo a la ligera (consulte la secci?n 82).

---

# 115. El agente no puede iniciarse por comprobaciones durante la importaci?n

**S?ntoma:** `lums-agent` falla antes de leer su token, por ejemplo con `RuntimeError: No supported package manager found. Supported package managers: apt, pacman`, o con un error SSL relacionado con el archivo de CA.

**Causa:** `agent/agent.py` detecta el gestor de paquetes y crea el contexto TLS al importar el m?dulo. Los hosts sin `apt` o `pacman` (o con un `LUMS_CA_FILE` inexistente o ilegible) fallan al iniciarse. Lo mismo sucede en entornos de prueba como Windows.

**Verificaci?n:**

```text
systemctl status lums-agent --no-pager
journalctl -u lums-agent -n 50 --no-pager
```

**Soluci?n:** Utilice una distribuci?n compatible, confirme que el gestor de paquetes est? en el `PATH` del servicio y que `LUMS_CA_FILE` existe y puede leerlo el usuario del servicio.

---

# 116. El agente utiliza una direcci?n de servidor incorrecta (puerto 5000 frente a 5050)

**S?ntoma:** El agente informa de que se rechaz? la conexi?n aunque el servidor est? en buen estado.

**Causa:** El valor predeterminado integrado del agente es `LUMS_BASE=http://127.0.0.1:5000`, mientras que el contenedor documentado publica `127.0.0.1:5050`. Los ejemplos con el puerto `5050` de esta gu?a describen el puerto publicado por el servidor, no el valor predeterminado del agente.

**Verificaci?n:**

```text
systemctl show lums-agent --property=Environment
ss -lntp | grep -E ':5000|:5050'
```

**Soluci?n:** Defina `LUMS_BASE` expl?citamente con el endpoint real accesible desde el cliente (normalmente la URL HTTPS de la implementaci?n). No exponga p?blicamente el puerto `5050` como soluci?n alternativa.

---

# 117. El watcher se cierra con el estado 1

**S?ntoma:** `lums-watcher` termina con error y registra uno de estos mensajes: `CLIENT LOOKUP FAILED`, `RUNNING JOB LOOKUP FAILED`, `JOB LOOKUP FAILED`, `IDLE CHECK FAILED`, `JOB CLAIM FAILED`, `UPDATE EXECUTION FAILED`.

**Causa:** El watcher es una unidad de ejecuci?n ?nica. Captura todos los errores, los registra, termina con estado 1 y no vuelve a intentarlo en el proceso; la siguiente ejecuci?n del temporizador comienza desde cero. Solo reanuda trabajos cuyo estado sea exactamente `running`. De lo contrario, busca trabajos pendientes, y `NO UPDATE JOB // SYSTEM CLEAN` es un resultado normal.

**Verificaci?n:**

```text
journalctl -u lums-watcher -n 100 --no-pager
systemctl status lums-watcher lums-watcher.timer
```

**Soluci?n:** Resuelva el fallo indicado (accesibilidad de la API, token, comprobaci?n de inactividad o bloqueo del gestor de paquetes) y deje que vuelva a ejecutarse el temporizador. Inspeccione el estado mediante la interfaz o la API; nunca modifique manualmente los estados en SQLite.

---

# 118. El actualizador del host sigue registrando fallos de heartbeat

**S?ntoma:** `lums-host-updater` sigue ejecut?ndose, pero registra repetidamente `Heartbeat failed (ValueError)` o `Heartbeat failed (HTTPError)`.

**Causa:** El actualizador del host captura intencionadamente los errores dentro de su bucle y vuelve a intentarlo. Causas habituales (`host_updater/agent.py`):

- `Host-updater token is missing or too short` ? el archivo del token no existe o tiene menos de 32 caracteres.
- `Only a loopback LUMS endpoint is permitted` ? la URL debe usar `http` o `https`, el host debe ser exactamente `127.0.0.1`, debe especificarse un puerto y no se permiten credenciales, consulta ni fragmento (por ejemplo, `http://127.0.0.1:5050`).
- HTTP `401` con `host_updater_authentication_required` ? el token bearer no es v?lido.
- HTTP `503` con `host_updater_not_configured` ? el servidor no tiene configurado un token del actualizador del host.
- El servicio se detiene con `Unexpected update-execution state; stopping` (estado 1) si la respuesta no indica expl?citamente `update_execution_enabled: false`. Compruebe que coincidan las versiones del servidor y del actualizador.

**Verificaci?n (no imprima el token):**

```text
journalctl -u lums-host-updater -n 100 --no-pager
systemctl show lums-host-updater --property=Environment
stat /etc/lums-host-updater/token
```

**Soluci?n:** Corrija el propietario y el modo del archivo del token, ajuste la URL de loopback y reinicie el servicio una sola vez.

---

# 119. Las solicitudes de integraci?n de alertas devuelven 501

**S?ntoma:** Configurar, probar o eliminar una integraci?n de correo electr?nico, Slack, PagerDuty o webhook devuelve `501` con `Notification integrations are disabled pending secure persistent configuration`.

**Causa:** Es intencionado (`server/alerts_routes.py`). Las integraciones no est?n disponibles, `POST /alerts/clear-all` tambi?n devuelve `501` y las reglas no se eval?an autom?ticamente. No vuelva a intentarlo ni introduzca secretos de proveedores.

**Relacionado:** Estas rutas requieren `alerts.manage` y protecci?n CSRF. Si falta el token CSRF o es incorrecto, se devuelve `403` con `csrf_validation_failed` antes de cualquier `501`. No desactive CSRF. Consulte `docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`.

---

# 120. Fallos de inicio de sesi?n: CSRF, limitaci?n de frecuencia y bloqueos

**S?ntoma:** Se rechaza una contrase?a v?lida tras varios intentos fallidos, o aparece la entrada de auditor?a `login.rate_limit`.

**Causa:** Los intentos se limitan por nombre de usuario y origen, y el estado se almacena en SQLite (`login_rate_limits`, con `locked_until`), por lo que persiste tras reiniciar. La ruta `/login` est? exenta de la comprobaci?n CSRF: la falta de un token CSRF no causa el fallo de inicio de sesi?n; compruebe las credenciales, las cookies y la limitaci?n de frecuencia.

**Verificaci?n (solo lectura):**

```text
sqlite3 /var/lib/lums/lums.db "select rate_limit_key, locked_until from login_rate_limits;"
```

**Soluci?n:** Espere a que expire el bloqueo y corrija el origen de los fallos. No elimine filas manualmente ni realice repetidos intentos de inicio de sesi?n para probarlo.

---

# 121. SQLite est? ocupado o las migraciones afectan a otra base de datos

**S?ntoma:** Las escrituras fallan por contenci?n, o una migraci?n parece completarse correctamente pero al servidor le siguen faltando tablas o funciones.

**Causa:** Las conexiones de la aplicaci?n usan `PRAGMA busy_timeout = 5000`, por lo que una escritura espera como m?ximo cinco segundos. La base de datos funciona en modo WAL (`server/init_db.py`), por lo que los archivos `-wal` y `-shm` son normales. Los scripts de migraci?n leen `LUMS_DB_PATH` por separado y pueden modificar un archivo distinto del que utiliza el servidor.

**Verificaci?n:**

```text
sqlite3 /var/lib/lums/lums.db "pragma busy_timeout; pragma journal_mode;"
docker inspect lums --format '{{range .Config.Env}}{{println .}}{{end}}'
```

**Soluci?n:** Encuentre y detenga el proceso en competencia, conserve los archivos WAL y SHM y haga coincidir el entorno de migraci?n con el del servidor. Nunca elimine los archivos `-wal` o `-shm`.

---

# 122. La restauraci?n se niega a ejecutarse (hay archivos WAL/SHM)

**S?ntoma:** La restauraci?n se detiene con `Restore verweigert: SQLite-WAL/SHM-Datei vorhanden.` (el mensaje est? en alem?n en el c?digo).

**Causa:** `server/database_backup.py` falla de forma segura cuando existen archivos auxiliares de la base de datos de destino, para evitar mezclar datos antiguos y nuevos.

**Verificaci?n:** `find /var/lib/lums -maxdepth 1 -type f -name 'lums.db*'`

**Soluci?n:** Detenga o deje inactiva la aplicaci?n y utilice el procedimiento de restauraci?n documentado. Nunca elimine manualmente los archivos auxiliares.

---

# 123. Errores de instant?neas y verificaci?n de versiones

**S?ntoma y causa (`scripts/volume_snapshot.py`, `scripts/release_verification.py`):**

| Mensaje | Significado |
| --- | --- |
| `Could not create or publish the snapshot.` | El destino ya existe o no se puede escribir; las instant?neas nunca sobrescriben. |
| `Source tree changed during snapshot creation.` | Los archivos cambiaron durante la copia; detenga las escrituras y vuelva a intentarlo. |
| `Invalid snapshot filename.` / `Invalid restore target.` | Se rechaz? una ruta o nombre de archivo no seguro. |
| `Duplicate restore target: ...` | El archivo contiene entradas duplicadas; utilice un archivo creado con la herramienta compatible. |
| Fallo de verificaci?n de versi?n en los datos de suma de comprobaci?n | Los metadatos de suma de comprobaci?n est?n limitados a 4096 bytes; obtenga el archivo oficial en lugar de omitir la verificaci?n. |

Las restauraciones sin privilegios de root no aplican propietarios arbitrarios del archivo archivado. Ejecute la restauraci?n documentada con la cuenta de servicio prevista en lugar de convertir el contenedor en root. Enumere el contenido con `tar -tf` sin extraerlo.

---

# 124. Fin de la gu?a de soluci?n de problemas

La soluci?n de problemas de LUMS debe seguir siendo basada en evidencia y consciente de la seguridad.

En caso de duda:

```text id="r9x4kw"
Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.
```

No intercambie seguridad o integridad de datos por una soluci?n alternativa r?pida.

---

**Fin de la gu?a de soluci?n de problemas de LUMS**
