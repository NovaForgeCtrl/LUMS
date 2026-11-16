# Topología de infraestructura de LUMS

## Propósito

La página autenticada `/infrastructure` reúne los clientes LUMS registrados y
la infraestructura mantenida manualmente en una vista de dependencias. Es un
inventario y un mapa de relaciones, no un sistema automático de descubrimiento
de red o administración de la configuración.

## Fuentes de datos y responsabilidades

- Los clientes LUMS registrados se leen del registro de clientes existente y
  aparecen automáticamente, incluidos el nombre de host, la dirección IP, el
  sistema operativo y el estado habilitado/de comunicación que hayan
  comunicado. Los clientes deshabilitados siguen visibles para que las
  relaciones existentes se entiendan. Estas entradas son de solo lectura en la
  página de topología; administra los clientes mediante el flujo habitual de
  gestión de clientes.
- Los servidores, las máquinas virtuales, los contenedores, los dispositivos
  de red, los servicios y el almacenamiento se pueden introducir manualmente
  con un nombre de host, una dirección IP, un rol, una ubicación y notas.
- Las relaciones se mantienen manualmente. Los tipos admitidos son `depends
  on`, `hosts`, `connects to` y `runs on`.
- La página no analiza subredes, consulta API de la nube ni deduce dependencias
  a partir de la configuración de servicios o contenedores. Mantén actualizado
  el inventario y las relaciones introducidos manualmente.

## Control de acceso y auditoría

Los usuarios con `clients.view` pueden ver la topología. La creación,
modificación y eliminación de entradas o relaciones manuales está restringida
a los administradores con el permiso `infrastructure.manage`. Para los cambios,
la aplicación exige una sesión autenticada normal, protección CSRF y registro
de auditoría.

`infrastructure.manage` depende de `users.manage` y `clients.view`, y se
concede a los administradores mediante la migración de base de datos
`016-infrastructure-topology`. Al eliminar un nodo administrado manualmente
también se eliminan sus registros de relaciones. Al eliminar un cliente, se
eliminan las relaciones que hacen referencia a él.

## Lectura del mapa

El mapa organiza los nodos por categoría y dibuja una arista direccional para
cada relación registrada. Una **dependencia compartida** es un nodo al que
apuntan al menos otros dos nodos mediante `depends on`. Es una señal útil para
revisar un posible punto central de fallo, no un análisis completo de
disponibilidad o impacto. El mapa no tiene en cuenta la redundancia, la
conmutación por error, la capacidad, la segmentación de red ni las dependencias
que no se hayan registrado.

Usa las tablas de inventario y relaciones para consultar los nombres de host,
las direcciones IP, los roles, las ubicaciones y los detalles exactos de las
relaciones. La topología utiliza el tema de LUMS seleccionado actualmente y
funciona con la barra lateral plegable compartida. [Documentación original en inglés](../../../LUMS_Infrastructure_Topology.md).
