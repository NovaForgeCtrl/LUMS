# Telemetría de CPU, memoria y red de LUMS

## Descripción general

El agente opcional de telemetría de LUMS recopila el uso de CPU y memoria,
contadores de red y una instantánea limitada del host de un sistema Linux
administrado, y envía las mediciones al servidor LUMS.

El servidor almacena muestras de telemetría y ofrece una API de historial
autenticada que utiliza el panel de telemetría del cliente.

La telemetría es independiente del Agent y el Watcher de informes de LUMS
existentes. No sustituye a ninguno de ellos ni realiza actualizaciones de
paquetes.

## Componentes

| Componente | Responsabilidad |
| --- | --- |
| `agent/telemetry.py` | Recopila métricas de CPU, memoria, host, red, sensores, servicios y contenedores |
| `agent/lums-telemetry.service` | Ejecuta el agente de telemetría como un servicio systemd restringido |
| `agent/lums-telemetry.timer` | Programa recopilaciones de telemetría periódicas |
| `server/app.py` | Autentica los envíos, valida las métricas y almacena las muestras |
| `server/static/telemetry.js` | Muestra la vista general de la flota, gráficos de historial e indicadores circulares |

## Mediciones

Cada muestra incluye estos campos obligatorios:

- `cpu_percent`: uso de CPU de 0 a 100.
- `memory_percent`: uso de memoria de 0 a 100.
- `memory_total_bytes`: memoria total detectada, en bytes.
- `memory_available_bytes`: memoria disponible, en bytes.

La versión 1.1.0 del agente y las posteriores también envían dos contadores
acumulativos opcionales:

- `network_rx_bytes`: bytes recibidos desde el arranque, sumados en todas las
  interfaces que no sean loopback.
- `network_tx_bytes`: bytes enviados desde el arranque, sumados en todas las
  interfaces que no sean loopback.

Ambos contadores deben enviarse juntos como enteros no negativos. Los agentes
anteriores que los omiten siguen funcionando; en ese caso, el panel no muestra
datos de red para ese cliente. El servidor almacena los contadores sin procesar
y calcula los bytes por segundo a partir de muestras consecutivas cuando se
solicitan los datos. No se muestra ninguna tasa para la primera muestra,
después de un reinicio del contador (por ejemplo, tras un reinicio del sistema)
ni cuando el intervalo entre dos muestras supera los cinco minutos.

La versión 1.2.0 del agente y las posteriores también informan de una
instantánea limitada del sistema:

- carga media, tiempo de actividad, sistema operativo, kernel y uso del sistema
  de archivos raíz;
- estado del enlace, contadores de bytes, errores y descartes de cada interfaz
  de red;
- servidores DNS configurados y comprobaciones de mejor esfuerzo de la
  conectividad con la puerta de enlace, DNS e Internet;
- lecturas térmicas y del ventilador cuando las expone el kernel;
- estados y tiempos de ejecución de servicios systemd seleccionados y
  recuentos de reinicios, además de nombres y estados normalizados de
  contenedores Docker y Podman cuando las herramientas locales y los permisos
  permiten una inspección de solo lectura;
- porcentaje de uso del disco en cada muestra de telemetría para gráficos
  históricos y evaluación de eventos de umbral.

La versión 1.3.0 del agente y las posteriores también informan de resúmenes
limitados de eventos operativos: recuentos y marcas de tiempo de inicios de
sesión SSH fallidos, recuentos recientes de advertencias y errores del journal,
marcas de tiempo de inicio y cierre de sesión, y las primeras y últimas marcas
de tiempo del journal de los arranques recientes. No se envían mensajes sin
procesar del journal, nombres de usuario ni direcciones de origen. Cada consulta
del journal se limita a 500 registros coincidentes; el panel muestra `500+`
cuando el recuento llega a 500. El historial de arranques se limita a 10 y el
de inicios y cierres de sesión a 20 eventos.

El servidor calcula el rendimiento por interfaz a partir de muestras
consecutivas. Los detalles de servicios, contenedores, temperatura,
ventiladores y eventos se almacenan únicamente como la instantánea más
reciente; no se duplican en cada muestra histórica. Las métricas opcionales que
el sistema operativo no expone o no permite consultar aparecen como no
disponibles. El agente no inicia, detiene ni modifica servicios o contenedores.
El servicio del agente no recibe acceso al socket de Docker; los detalles de
los contenedores no estarán disponibles salvo que el entorno de ejecución ya
permita inspeccionarlos a la cuenta del servicio.

La unidad systemd de telemetría pertenece al grupo `systemd-journal` para
obtener acceso de solo lectura al journal. Esto concede acceso a los registros
del sistema, pero el agente solo envía los resúmenes limitados descritos
anteriormente. La lista de servicios permitidos predeterminada incluye las
unidades de LUMS, Docker y SSH. Sustitúyela con un valor separado por comas de
`LUMS_MONITORED_SERVICES` en el archivo de entorno del agente; solo se aceptan
nombres válidos de unidades `.service`.

La conectividad con la puerta de enlace se comprueba con un único ping cuando
está disponible; la conectividad DNS, con una consulta breve de `getent`; y la
conectividad a Internet, con un intento breve de conexión TCP a `1.1.1.1:443`.
Estas comprobaciones son solo indicadores y pueden reflejar la política del
cortafuegos en lugar de una interrupción.

El servidor asigna la marca de tiempo de la muestra y rechaza las cargas útiles
no válidas.

Después de actualizar el servidor, ejecuta una vez la migración de la base de
datos (`python3 server/security_migration.py`) para que existan las columnas de
red, la tabla del último estado del sistema y el historial de eventos.
Actualiza el agente en cada cliente para que empiece a informar de las nuevas
métricas. Para supervisar el propio servidor LUMS, regístralo como cliente e
instala y configura también el agente de telemetría en ese host.

## Seguridad y privacidad

El endpoint de telemetría requiere autenticación del cliente mediante el token
de cliente LUMS configurado.

El agente envía las solicitudes mediante HTTPS cuando se conecta a un servidor
remoto. Solo se permite HTTP sin cifrar para `localhost`, `127.0.0.1` y `::1`.
Las conexiones a servidores remotos requieren HTTPS. Se puede configurar un
archivo CA opcional para la verificación de certificados.

El agente no incluye el token de cliente en la carga JSON ni lo registra. El
servicio systemd utiliza un entorno de ejecución restringido y no necesita
privilegios de root para recopilar las métricas documentadas.

La telemetría contiene recursos del sistema y metadatos operativos, no
actualizaciones de paquetes ni resultados arbitrarios de comandos. Las
direcciones de interfaces, servidores DNS, nombres de servicios y nombres de
contenedores pueden ser datos de infraestructura sensibles; el acceso al panel
y a la API sigue protegido por el permiso `clients.view`.

## Conservación de datos

El servidor elimina las muestras de telemetría de más de siete días al procesar
nuevos envíos de telemetría.

El endpoint de historial autenticado acepta un intervalo de 1 a 168 horas. El
acceso requiere el permiso correspondiente para ver clientes. Los conjuntos de
resultados grandes pueden reducirse a un máximo de 1.000 muestras.

El panel `/health` ofrece intervalos de historial de 1 hora, 24 horas y 7 días,
y actualiza los datos mostrados cada cinco segundos. Muestra el historial de
uso de CPU, memoria y disco, así como el tráfico de red agregado y, para el
cliente seleccionado, detalles actuales del disco, carga, tiempo de actividad,
kernel, sistema operativo, interfaces, conectividad, sensores, servicios y
contenedores. También muestra una vista general de la flota que se puede
filtrar por estado, telemetría obsoleta o carga alta, buscar y ordenar, además
de detalles por cliente. La CPU y la memoria se pueden mostrar como gráfico de
líneas, gráfico de áreas o indicador circular del valor actual; la vista
elegida se recuerda en el navegador. El tráfico de red se muestra como tasas de
descarga y carga. La telemetría de más de dos minutos se marca como obsoleta.
La vista general de la flota utiliza el endpoint `/api/telemetry/overview`,
que requiere el permiso para ver clientes. Las solicitudes de historial se
limitan a 1–168 horas y pueden reducirse a un máximo de 1.000 muestras. El
temporizador systemd está configurado para ejecutar el agente de una sola
ejecución cada cinco segundos; la frecuencia real de las muestras depende de
la duración del servicio y de la disponibilidad de la red. El panel también
muestra fallos recientes de SSH, recuentos de advertencias y errores del
journal, y el historial de inicios/cierres de sesión y arranques. Las alertas
de umbral utilizan los límites configurables de CPU, RAM y disco del usuario
con sesión iniciada. Los recuentos del journal abarcan como máximo 500 registros
coincidentes por consulta. La última copia de seguridad creada correctamente
se obtiene del registro de auditoría del servidor; esto no constituye una
prueba de restauración.

Los cruces de umbral y las interrupciones de telemetría de más de dos minutos
aparecen en el historial de eventos. Las alertas de umbral se calculan a partir
de las muestras conservadas y de los umbrales del usuario con sesión iniciada;
los cambios de estado de servicios y las nuevas marcas de tiempo de fallos SSH
se registran durante la ingesta. Los eventos se conservan hasta siete días y el
endpoint de eventos devuelve como máximo 500 entradas.

Hay exportaciones CSV y JSON para el cliente y el intervalo seleccionados. Las
descargas del historial incluyen todas las muestras conservadas para ese
intervalo; los gráficos siguen reducidos a un máximo de 1.000 puntos. Las
exportaciones requieren `clients.view` y el navegador no las almacena en caché.

Wazuh y Suricata se pueden habilitar como filas de estado opcionales en el panel.
Estas filas solo muestran el estado del servicio systemd configurado; LUMS no se
conecta a sus API ni recopila sus alertas. Para informar de un servicio, incluye
su unidad instalada (por ejemplo, `wazuh-agent.service`,
`wazuh-manager.service` o `suricata.service`) en la lista permitida
`LUMS_MONITORED_SERVICES` del agente. LUMS no necesita ni almacena credenciales
de integración.

## Configuración

El agente de telemetría utiliza las variables de entorno `LUMS_BASE`,
`LUMS_TOKEN` y, opcionalmente, `LUMS_CA_FILE`. Las conexiones a servidores
remotos requieren HTTPS. Consulta [Instalación y actualizaciones](Instalación%20y%20actualizaciones.md)
para obtener instrucciones de instalación y configuración. [Documentación original en inglés](../../../telemetry.md).

## Instalación y funcionamiento

El servicio de telemetría es independiente del cliente LUMS normal. En Debian,
primero actualiza la copia del repositorio LUMS en el cliente y ejecuta
`sudo bash scripts/install-telemetry-agent.sh` desde su raíz. El instalador
comprueba que `/etc/default/lums-agent` defina `LUMS_BASE` y `LUMS_TOKEN`,
instala el collector actual y las unidades systemd, habilita el temporizador y
envía una muestra de prueba. Nunca muestra el token.

Comprueba el temporizador y el servicio con `systemctl status lums-telemetry.timer`
y `systemctl status lums-telemetry.service`. Revisa los registros recientes del
servicio con `journalctl -u lums-telemetry.service -n 30 --no-pager`. Que el
servicio de una sola ejecución esté inactivo entre ejecuciones programadas no
significa necesariamente que haya un error; comprueba también el temporizador y
los registros recientes.

La página `/monitoring` distingue entre la ausencia de muestras, telemetría
básica sin instantáneas detalladas y una instantánea obsoleta, y muestra estas
comprobaciones del lado del cliente. No pegues ni compartas el token al
investigar problemas.

## Solución de problemas

- **No aparecen muestras:** Comprueba la URL del servidor, el token del cliente
  y la autenticación.
- **Errores TLS:** Comprueba el certificado del servidor y el archivo CA
  configurado.
- **Fallos del servicio:** Inspecciona el journal del servicio.
- **Falta el historial:** Comprueba el permiso para ver clientes y el intervalo
  solicitado (1–168 horas).

Para conocer los umbrales de estado del panel y las limitaciones de su
indicador de almacenamiento de copias de seguridad, consulta el [Panel de
estado del sistema](panel-estado-sistema.md). Para obtener orientación
general, consulta [Instalación y actualizaciones](Instalación%20y%20actualizaciones.md)
y [Solución de problemas](Solución%20de%20problemas.md).
