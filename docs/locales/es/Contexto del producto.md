# Producto

## Plataforma

Web.

## Usuarios

Administradores de sistemas Linux y equipos de TI responsables de gestionar de forma centralizada y mantener actualizados varios sistemas Linux. El producto también debe ser adecuado para un administrador individual, un equipo de TI pequeño y entornos de servicios gestionados apropiados.

## Propósito del producto

LUMS ofrece una vista centralizada de los clientes gestionados, el software instalado, las actualizaciones disponibles y la ejecución de trabajos de actualización. Ayuda a los administradores a iniciar el trabajo de forma deliberada y verificar el resultado, en vez de aplicar actualizaciones a ciegas en todos los sistemas.

## Contexto operativo

En las operaciones cotidianas, los administradores utilizan LUMS para inspeccionar el estado de la flota, la telemetría, el software y las actualizaciones; iniciar trabajos de actualización dirigidos; revisar el historial de ejecución; y mantener el acceso de usuarios, los registros de auditoría y las copias de seguridad de la base de datos. La topología de infraestructura puede combinar clientes LUMS registrados con sistemas y relaciones mantenidos manualmente.

## Capacidades y restricciones

- Los controles de acceso basados en roles y permisos, el registro de auditoría, las copias de seguridad de la base de datos, la visibilidad de paquetes y los trabajos de actualización de clientes son capacidades operativas centrales.
- Las operaciones de actualización del sistema deben ser controladas, auditables y comunicar los fallos con veracidad; no se debe indicar que una actualización tuvo éxito si sus comprobaciones no se superaron.
- Los clientes registrados y los datos que informan son la fuente disponible para importar automáticamente el inventario de infraestructura. La infraestructura y las relaciones adicionales requieren una entrada manual explícita, salvo que se confirme una integración futura.
- La edición del inventario de infraestructura está restringida a los administradores.
- No se debe insinuar el descubrimiento automático de máquinas virtuales, contenedores, dispositivos de red o dependencias arbitrarios.

## Compromisos de marca

- Conservar el nombre LUMS y el logotipo existente.
- El usuario denomina explícitamente al tema de estadio «LUMS-Stadion» y solicitó que su imagen de fondo de estadio existente se use en el panel de estado del sistema y en la monitorización en vivo.

## Evidencia disponible

- La interfaz y los recursos de temas existentes son `server/static/style.css`, `server/static/images/LUMS_Logo.jpg` y `server/static/images/lumsstadium.jpg`.
- Las implementaciones existentes de clientes registrados, telemetría, trabajos de actualización, RBAC, auditoría y copias de seguridad se encuentran en el paquete `server/`.
- No se han proporcionado afirmaciones de clientes verificadas, métricas comparativas del producto ni una integración de descubrimiento automático de infraestructura.

## Principios del producto

- Mantener a los administradores al mando de los cambios en los sistemas.
- Hacer verificables el estado operativo y los resultados de las actualizaciones.
- Aplicar las reglas de acceso en el servidor, no únicamente en la interfaz.
- Distinguir los datos informados por clientes del inventario mantenido manualmente.
