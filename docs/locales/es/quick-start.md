# Inicio rápido de LUMS — Español

Esta guía breve está pensada para quienes empiezan con LUMS o Linux. Muchos
documentos relevantes para usuarios y administradores también están traducidos
a otros idiomas; consulta la [documentación organizada por idioma](../../README.md)
para ver toda la cobertura disponible. Los originales en inglés siguen siendo
la fuente de referencia y pueden ser más completos o estar más actualizados
que las traducciones.

## ¿Qué es LUMS?

LUMS administra equipos Linux de forma centralizada. El servidor muestra los
clientes, el software instalado y las actualizaciones disponibles. Un agente
en cada cliente ejecuta las acciones autorizadas con el gestor de paquetes del
sistema: APT en Debian/Ubuntu y pacman en Arch Linux. LUMS no instala todas
las actualizaciones automáticamente.

## Si solo utilizas LUMS

Abre la dirección web que te proporcionó la persona administradora e inicia
sesión con tu propia cuenta. Las acciones disponibles dependen de tus
permisos. No compartas tu cuenta ni un token de cliente. Elige un idioma en la
esquina superior derecha de la página de inicio de sesión; después, LUMS puede
guardar la preferencia en tu cuenta.

## Instalación y operación

Una prueba no equivale a un servidor de producción. Una instalación segura
necesita, entre otras cosas, HTTPS, un secreto de aplicación protegido,
almacenamiento persistente para la base de datos y copias de seguridad
verificadas. El servidor y los clientes Linux se configuran por separado.
Sigue con cuidado la [guía de instalación](../../../install.md). Sustituye los
valores de ejemplo, como `LUMS-SERVER`, y comprueba cada ruta antes de ejecutar
un comando. Si LUMS ya está funcionando, usa las instrucciones de actualización
de la [guía de administración](../../../administration.md), no el procedimiento
de primera instalación.

En una actualización normal, nunca borres el volumen de Docker `lums-data`:
contiene la base de datos. Conserva los montajes existentes del secreto y de
las copias de seguridad, así como las opciones de seguridad del contenedor.
Los comandos de ejemplo no sirven para todas las instalaciones; compáralos
primero con tu contenedor activo.

## Primeras comprobaciones si algo falla

En el servidor, estos comandos muestran el estado del contenedor, los registros
recientes de la aplicación y el estado de Nginx:

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` puede pedirte la contraseña de Linux. Estas comprobaciones no cambian
la configuración. No borres la base de datos ni el volumen de Docker, no
inicies el contenedor con privilegios y no desactives las protecciones como
primer intento. Antes de compartir registros, elimina contraseñas, tokens,
claves y datos personales.

## Documentación detallada

* [Descripción del proyecto](Descripción%20del%20proyecto.md)
* [Instalación y actualizaciones](Instalación%20y%20actualizaciones.md)
* [Administración y copias de seguridad](Administración%20y%20copias%20de%20seguridad.md)
* [Solución de problemas](Solución%20de%20problemas.md)
* [Modelo de seguridad](Modelo%20de%20seguridad.md)
