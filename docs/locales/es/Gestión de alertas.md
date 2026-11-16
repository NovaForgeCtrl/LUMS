# Gestión de alertas de LUMS: implementación actual

Esta nota describe el código de gestión de alertas que existe actualmente en LUMS. Es una referencia del código, no una hoja de ruta de funciones ni una promesa de que todos los controles visibles estén operativos. La implementación se centra en `server/alerts.py` y `server/alerts_routes.py`.

## Funciones implementadas

LUMS conserva en SQLite las reglas de alerta, los registros de alertas y el historial de estado de las alertas. El blueprint de Flask crea un `AlertManager` por solicitud y utiliza la fábrica de conexiones a la base de datos de la aplicación. En cada solicitud, el gestor carga de la base de datos las reglas y las alertas no resueltas.

La API actual permite:

- enumerar, crear, actualizar y eliminar reglas de alerta;
- activar manualmente una alerta para una regla existente y habilitada;
- consultar alertas activas e historial de alertas paginado;
- reconocer, resolver y escalar manualmente una alerta activa.

Los valores de gravedad de las alertas son `critical`, `warning` e `info`. Los estados almacenados son `triggered`, `acknowledged`, `resolved` y `escalated`. Los cambios de reconocimiento, resolución y escalado se escriben en `alert_history`. Las alertas resueltas se eliminan de la colección de alertas activas del gestor, pero permanecen en la base de datos.

## Límites importantes

El modelo de reglas almacena una condición, un umbral, la gravedad, una ruta de escalado y las opciones de agrupación y deduplicación. El servidor actual **no** evalúa las condiciones frente a la telemetría u otras mediciones. Las reglas no se activan automáticamente: una persona autenticada debe llamar a `POST /alerts/trigger`.

Al activar manualmente una alerta, el gestor puede invocar proveedores indicados en su ruta de escalado. Sin embargo, la aplicación web crea los gestores con un mapa de proveedores vacío y los endpoints de integración no permiten configurarlos; por tanto, el disparo desde la aplicación web no proporciona entrega de notificaciones. Los valores de agrupación y deduplicación se almacenan, pero no se aplican.

`AlertManager` define clases de proveedores para correo electrónico, Slack, PagerDuty y webhooks genéricos, pero la aplicación no las configura. La API de integraciones informa deliberadamente que las integraciones no están disponibles y devuelve `501 Not Implemented` para las solicitudes de configuración, prueba y eliminación. No debe esperarse la entrega de notificaciones. `POST /alerts/clear-all` también devuelve `501` para impedir que se elimine el historial de alertas a través de ese endpoint.

La página `/alerts/` es una vista general básica renderizada en el servidor. Los controles de pestañas de reglas, historial e integraciones y los botones de acciones de alertas no constituyen una interfaz interactiva completa de gestión. Utiliza el comportamiento documentado de la API como fuente de verdad; no des por hecho que un botón visible ejecuta una acción. La implementación actual no ofrece actualizaciones en tiempo real mediante push ni WebSocket.

## Rutas y control de acceso

Todas las rutas requieren una sesión web autenticada.

| Método | Ruta | Permiso | Comportamiento actual |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Renderiza la vista general básica de alertas |
| `GET` | `/alerts/rules` | `alerts.view` | Enumera las reglas almacenadas |
| `POST` | `/alerts/rules` | `alerts.manage` | Crea una regla validada |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Actualiza una regla almacenada |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Elimina una regla si las restricciones de la base de datos lo permiten |
| `GET` | `/alerts/current` | `alerts.view` | Devuelve las alertas activas |
| `GET` | `/alerts/history` | `alerts.view` | Devuelve el historial de alertas |
| `POST` | `/alerts/trigger` | `alerts.manage` | Crea manualmente una alerta para una regla habilitada |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Registra un reconocimiento |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Resuelve una alerta activa |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Incrementa manualmente el contador de escalado |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Deshabilitado; devuelve `501` |
| `GET` | `/alerts/integrations` | `alerts.view` | Devuelve una lista vacía y `available: false` |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Deshabilitados; devuelven `501` |

Las rutas que modifican datos requieren protección CSRF además del permiso correspondiente. Las comprobaciones de permisos se aplican en el servidor. `alerts.manage` depende de `alerts.view`; las concesiones de roles se mantienen mediante la migración de seguridad y la configuración de permisos.

## Tablas persistentes

`AlertManager` inicializa estas tablas al crearse:

- `alert_rules`: definiciones de reglas y sus valores configurados;
- `alerts`: registros de alertas y su estado actual en el ciclo de vida;
- `alert_history`: historial de reconocimientos, resoluciones y escalados;
- `notification_integrations`: esquema reservado para la configuración de integraciones;
- `alert_notifications_log`: esquema reservado para el registro de entregas.

Las dos últimas tablas no significan que las integraciones estén disponibles. Los endpoints HTTP de integración seguirán deshabilitados hasta que se implementen una configuración persistente segura y la entrega de notificaciones.

## Verificación

Las rutas de alertas, la aplicación de permisos, la validación de cargas útiles, la persistencia y el comportamiento del ciclo de vida están cubiertos por `tests/test_alerts.py`. Vuelve a ejecutar las pruebas pertinentes para la revisión que se vaya a implementar. Que la suite de pruebas pase no convierte en disponibles las rutas de integración deshabilitadas ni las reglas que no se evalúan.

## Código relacionado

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
