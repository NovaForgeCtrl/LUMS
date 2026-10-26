# Paquete descargable de herramientas de actualización

Cuando el workflow `Tests` termina correctamente en `main`, el workflow
`Updater package` crea un artefacto `lums-update-tools-<commit>.tar.gz` y una
suma de comprobación SHA-256. Descárgalo desde la sección **Artifacts** de la
ejecución correcta de ese workflow; los artefactos de compilación se conservan
durante 90 días.

Cuando se publica una versión de GitHub, el workflow ejecuta la suite de
pruebas en la etiqueta publicada antes de adjuntar el archivo del actualizador
y un archivo de código fuente determinista. El archivo de código fuente incluye
su suma de comprobación SHA-256 y el identificador del commit probado; el
Update Center solo muestra las versiones cuando están disponibles los tres
recursos necesarios para verificar el código fuente.

El paquete de herramientas del actualizador es una descarga práctica, no un
paquete Debian. El contenedor web no instala directamente el archivo de código
fuente. No lo uses para actualizar producción hasta que un actualizador del
host instalado por separado haya superado las comprobaciones de despliegue y
haya verificado tanto la copia de seguridad de la base de datos como el
comportamiento de reversión para ese despliegue concreto.

[Documentación original en inglés](../../update-tools-package.md).
