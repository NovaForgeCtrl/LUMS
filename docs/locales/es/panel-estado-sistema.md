# Panel de estado del sistema de LUMS

## Propósito y alcance

El panel autenticado en `/health` ofrece al operador una vista rápida de
determinados estados de LUMS y de la flota:

- estado de la base de datos según lo determina la aplicación;
- número total de clientes y recuentos de clientes en línea, desconocidos y sin
  conexión;
- telemetría reciente de CPU, memoria y red para un cliente habilitado cuando
  la telemetría está instalada y hay muestras;
- telemetría reciente de CPU, memoria y red para los clientes habilitados
  cuando la telemetría está instalada y hay muestras;
- historial de alertas e interrupciones de telemetría detectadas;
- si se puede inspeccionar el directorio de copias de seguridad configurado,
  el archivo de copia más reciente que reconoce la aplicación y la última copia
  creada correctamente que consta en el registro de auditoría.
- filas opcionales del estado de servicios systemd de Wazuh y Suricata cuando
  están configuradas.

Los datos detallados de host y red por cliente, las temperaturas, los estados
de servicios y contenedores, y los resúmenes de eventos de seguridad están en
la página independiente `/monitoring`. La unidad de telemetría tiene acceso de
solo lectura al journal del sistema para resumir eventos; no envía mensajes
sin procesar de los registros, nombres de usuario ni direcciones de origen.
Los detalles de contenedores no están disponibles salvo que la cuenta del
servicio de telemetría pueda inspeccionar el entorno de ejecución sin
privilegios adicionales. Estas páginas no demuestran que el host, el daemon de
Docker, el proxy inverso, la red ni todos los clientes administrados estén en
buen estado. Que aparezca una copia de seguridad no demuestra que pueda
restaurarse; realiza periódicamente una prueba de restauración controlada.

## Control de acceso

La página `/health` requiere que el usuario haya iniciado sesión y tenga el
permiso `clients.view`. El acceso está sujeto a las comprobaciones normales de
autenticación y autorización de la aplicación. No hagas público el panel
eludiendo el inicio de sesión o los controles del proxy inverso.

El endpoint independiente `GET /api/health` es una respuesta ligera de
disponibilidad. Una respuesta correcta significa que la ruta puede responder;
no es una evaluación completa de la base de datos, las copias de seguridad ni
el estado de los clientes.

## Interpretación del estado del cliente

El panel clasifica los clientes según el tiempo transcurrido desde la última
marca de tiempo comunicada:

| Estado | Antigüedad de la marca de tiempo |
| --- | --- |
| En línea | 120 segundos o menos |
| Desconocido | Más de 120 segundos y hasta 600 segundos, marca de tiempo ausente/no válida o una marca de tiempo futura |
| Sin conexión | Más de 600 segundos |

Estos umbrales describen la actualidad de los informes, no si un equipo está
encendido ni si todos sus servicios funcionan. Los retrasos de red, los equipos
suspendidos, un agente detenido o fallos de comunicación pueden afectar al
resultado. Considera `unknown` como información insuficiente, no como prueba
de un fallo.

## Telemetría de CPU y memoria

La telemetría es opcional y está separada del Agent de informes y del Watcher
de ejecución. El servicio de telemetría envía una muestra aproximadamente cada
cinco segundos cuando está habilitado su temporizador systemd y el cliente puede
conectarse al servidor.

El panel ofrece intervalos de historial de 1 hora, 24 horas y 7 días, y
actualiza la telemetría de la flota cada cinco segundos. Los datos detallados
del host de `/monitoring` corresponden a la instantánea comunicada más
recientemente; el ancho de banda por interfaz se calcula a partir de
instantáneas consecutivas. Las consultas del historial se limitan a 1–168 horas
y pueden reducirse a un máximo de 1.000 puntos. Las muestras de más de siete
días se eliminan al procesar nuevos envíos de telemetría; si se detienen todos
los envíos, no des por sentado que la limpieza de retención se ejecuta de forma
independiente.

Cada consulta del journal de la página de supervisión se limita a 500 registros
coincidentes; un recuento mostrado como `500+` puede ser superior. El historial
de inicios y cierres de sesión se limita a 20 eventos y el historial de
arranques a 10 entradas. El panel de estado tiene un diseño fijo y utiliza los
umbrales existentes por usuario para CPU/RAM/disco (90 % de forma
predeterminada). Los cruces de umbral y las interrupciones de telemetría se
calculan a partir del historial de muestras conservado; los cambios de estado
de servicios y los nuevos fallos SSH comunicados se registran como eventos con
marca de tiempo durante un máximo de siete días. Las exportaciones CSV/JSON
incluyen todas las muestras del intervalo seleccionado; los gráficos
interactivos se limitan a 1.000 puntos.

Las filas de Wazuh y Suricata son opcionales e informan únicamente de estados
de servicios systemd. Requieren que la unidad correspondiente esté incluida en
`LUMS_MONITORED_SERVICES`; no se conectan a las API de Wazuh o Suricata ni
importan sus alertas. La marca de tiempo de la copia de seguridad procede del
registro de auditoría y no constituye una verificación de restauración
independiente.

La telemetría requiere autenticación del cliente. Las conexiones remotas del
agente requieren HTTPS; HTTP sin cifrar solo se acepta para direcciones de
loopback. Configura un archivo CA si el servidor utiliza una autoridad de
certificación privada. Consulta [Telemetría](telemetria.md) y
[Instalación y actualizaciones](Instalación%20y%20actualizaciones.md) para
obtener detalles de configuración. [Documentación original en inglés](../../../LUMS_Health_Dashboard.md).

## Estado del almacenamiento de copias de seguridad

La sección de copias de seguridad refleja lo que la aplicación puede
inspeccionar en el directorio configurado y el archivo más reciente que
reconoce. No verifica por sí sola el contenido de cada copia, confirma que haya
una réplica fuera del host ni demuestra que se pueda restaurar la base de datos.

Una rutina operativa recomendable:

1. Confirma que la fecha de la copia mostrada sea suficientemente reciente
   para tu objetivo de recuperación.
2. Revisa el trabajo de copia de seguridad y los registros de la aplicación
   para detectar errores.
3. Comprueba que la copia se haya transferido a un destino protegido adecuado.
4. Prueba periódicamente la restauración en una ubicación separada y controlada.

No elimines ni sobrescribas la base de datos activa o los archivos de copia de
seguridad como atajo para solucionar problemas.

## Comprobaciones recomendadas cuando un estado parece incorrecto

1. Comprueba el contenedor de LUMS y los registros recientes.
2. Si no se puede acceder a la página o a la API, comprueba la configuración del
   proxy inverso y TLS.
3. Para un cliente marcado como desconocido/sin conexión, inspecciona los
   temporizadores del Agent de informes y del Watcher, así como las entradas
   recientes del journal.
4. Si falta telemetría, inspecciona `lums-telemetry.timer`,
   `lums-telemetry.service` y la configuración del cliente/servidor.
5. Ante advertencias de copias de seguridad, comprueba la ruta configurada, los
   permisos del sistema de archivos, el espacio disponible y los registros
   recientes de las copias.
6. Anota el estado observado y las marcas de tiempo antes de realizar cambios.

Consulta [Solución de problemas](Solución%20de%20problemas.md) para ver comandos
de diagnóstico y [Administración y copias de seguridad](Administración%20y%20copias%20de%20seguridad.md)
para consultar los procedimientos de mantenimiento rutinario y copias.
