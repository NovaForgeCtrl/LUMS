# LUMS — Sistema de temas opcional

> **Un LUMS · muchas interfaces · el mismo backend**

LUMS ofrece un sistema opcional de temas del lado del cliente que permite cambiar el aspecto visual de la interfaz sin cambiar la funcionalidad subyacente de LUMS.

Los temas son únicamente una capa de presentación. No sustituyen, modifican ni eluden el backend de LUMS, la autenticación, la autorización, la ejecución de actualizaciones, la gestión de paquetes, la gestión de clientes, el manejo de trabajos ni los controles de seguridad.

El sistema de temas permite adaptar LUMS a distintas preferencias visuales y, al mismo tiempo, mantener coherente la aplicación.

## Estado de implementación y fuente de verdad

La implementación actual del navegador está en `server/static/theme.js`. Admite
`standard`, `LUMSStadium`, `golf`, `nerd`, `geek` y `admin`; guarda la selección
en el `localStorage` del navegador bajo `lums-theme`; y vuelve a `standard`
cuando el identificador guardado falta o no es válido. El tema `nerd` inicia el
efecto Matrix y `geek` inicia el efecto de red. La selección de tema es una
preferencia del navegador, no una configuración de cuenta ni un estado de
autorización del servidor.

Esta referencia también contiene requisitos de diseño y ejemplos conceptuales.
Las afirmaciones que usan términos como «debería», «debe» o «futuro» describen
orientación arquitectónica, no demuestran que una función visual o un
comportamiento de accesibilidad concreto esté implementado. Verifica el
comportamiento actual en el código fuente antes de considerar un concepto como
una capacidad disponible.

---

## 1. Descripción general

El sistema de temas opcional permite que la interfaz web de LUMS ofrezca varios entornos visuales mientras usa el mismo backend de aplicación.

Un tema puede cambiar:

* los colores
* la tipografía
* los fondos
* los elementos decorativos
* el énfasis visual
* el aspecto de la navegación
* las animaciones
* los efectos visuales opcionales
* la presentación específica de una página

Un tema no debe cambiar:

* los permisos de usuario
* los endpoints de API disponibles
* el comportamiento de autenticación
* las decisiones de autorización
* la protección CSRF
* la autenticación de clientes
* la ejecución de actualizaciones
* los permisos de gestión de paquetes
* el manejo del estado de los trabajos
* el registro de auditoría
* el comportamiento de la base de datos
* los límites de seguridad

El principio es sencillo:

> **Los temas cambian el aspecto de LUMS, no lo que LUMS tiene permitido hacer.**

---

## 2. Principios de diseño

El sistema de temas sigue varios principios.

### 2.1 Opcional

Los temas son una función opcional del frontend.

LUMS sigue siendo plenamente funcional sin seleccionar ningún tema adicional.

La apariencia estándar de LUMS actúa como presentación predeterminada.

### 2.2 Del lado del cliente

La selección de temas pertenece al frontend.

Cambiar de tema no debe requerir cambios en el estado de la aplicación del lado del servidor.

Por tanto, el tema seleccionado por un usuario es una preferencia de presentación, no un permiso de cuenta ni una configuración del backend.

### 2.3 Independencia del backend

Todos los temas usan el mismo backend de LUMS.

Lo siguiente permanece independiente del tema seleccionado:

```text
Authentication
Authorization
RBAC
Client Management
Software Inventory
Update Detection
Package Management
Update Jobs
Job Recovery
Audit Logging
Database Operations
```

El backend sigue siendo la fuente de autoridad para todas las decisiones sensibles a la seguridad y a la operación.

### 2.4 La apariencia no es seguridad

Nunca se debe usar un tema como mecanismo de seguridad.

Por ejemplo, ocultar una acción en la interfaz no concede ni revoca permisos.

Si una operación no está permitida para un usuario, el servidor debe rechazarla independientemente del tema activo.

Así se garantiza que la presentación del frontend no se convierta en un límite de autorización.

### 2.5 Alternativa controlada

El sistema de temas debería ofrecer siempre una alternativa válida.

Si no se ha seleccionado un tema, el tema almacenado ya no está disponible, su identificador no es válido o no se puede cargar un recurso del tema, LUMS debería volver a la presentación estándar en vez de dejar inutilizable la interfaz.

---

## 3. Arquitectura conceptual

El sistema de temas puede considerarse una capa de presentación separada que rodea la aplicación LUMS existente.

```text
┌──────────────────────────────────────┐
│              LUMS UI                 │
│                                      │
│  ┌────────────────────────────────┐  │
│  │        Theme Presentation      │  │
│  │                                │  │
│  │ Standard / Stadium / Golf /    │  │
│  │ Nerd / Geek / Admin / ...      │  │
│  └────────────────────────────────┘  │
│                  │                   │
│                  ▼                   │
│        Common Frontend Logic        │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             LUMS API                 │
│                                      │
│ Authentication / RBAC / Jobs /       │
│ Clients / Packages / Updates / Logs  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          LUMS Backend                │
│                                      │
│ Flask / SQLite / Job Processing /   │
│ Client Communication                 │
└──────────────────────────────────────┘
```

El límite importante separa **la presentación** de **la lógica de la aplicación**.

Los temas pertenecen a la capa situada por encima de ese límite.

---

## 4. Ciclo de vida del tema

Conceptualmente, la selección de un tema sigue esta secuencia:

```text
User selects theme
        │
        ▼
Frontend stores selection
        │
        ▼
Theme initialization
        │
        ▼
Theme applied to UI
        │
        ▼
LUMS continues using
the same backend and permissions
```

La selección no crea por sí misma un nuevo entorno LUMS.

Sigue habiendo una sola aplicación LUMS, un backend y un modelo de seguridad.

---

## 5. Identificadores de tema

Los temas deberían usar identificadores internos estables en lugar de depender de los nombres que se muestran al usuario.

Por ejemplo:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

El identificador es un detalle de implementación.

El nombre visible del tema puede cambiarse por separado sin que sea necesario modificar el backend ni la arquitectura de la aplicación.

Cuando se elimine o cambie el nombre de un identificador, el sistema debería ofrecer una alternativa a los usuarios que aún tengan guardado localmente el identificador anterior.

---

## 6. Separación de responsabilidades

El sistema de temas tiene una responsabilidad deliberadamente limitada.

### Capa de temas

Responsable de:

* la presentación visual
* la selección de temas
* los estilos específicos de cada tema
* los efectos visuales opcionales
* las decoraciones específicas del frontend
* el comportamiento de presentación relacionado con la accesibilidad

### Frontend común

Responsable de:

* mostrar los datos de la aplicación
* llamar a las API de LUMS
* representar trabajos e información de software
* gestionar las interacciones del usuario
* aplicar la visibilidad de elementos en la presentación

### Backend

Responsable de:

* la autenticación
* la autorización
* RBAC
* la protección CSRF
* la autenticación de clientes
* la creación de trabajos
* la ejecución de trabajos
* la gestión de paquetes
* las operaciones con la base de datos
* el registro de auditoría
* las decisiones de seguridad

Esta separación es fundamental para el diseño.

---

## 7. Límite de seguridad

El sistema de temas **no es código de confianza para fines de autorización**.

Aunque un tema modifique u oculte un elemento de la interfaz, el backend sigue siendo responsable de validar la operación solicitada.

Conceptualmente:

```text
Frontend visibility
        ≠
Backend permission
```

Por ejemplo:

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

El mismo principio se aplica a las funciones administrativas, los trabajos de actualización, la gestión de clientes y cualquier otra operación privilegiada.

---

## 8. Principio operativo

El sistema de temas debería ser invisible para la arquitectura operativa de LUMS.

Cambiar de tema no debe requerir:

* reconstruir la base de datos
* cambiar la configuración de los clientes
* cambiar los tokens de cliente
* reiniciar los agentes de actualización
* cambiar los trabajos de actualización
* modificar RBAC
* cambiar la configuración de red
* cambiar el comportamiento de gestión de paquetes

El tema es una preferencia de presentación, no una configuración operativa.

---

## 9. Alcance de la documentación

Este documento describe el sistema opcional de temas de LUMS.

Los temas generales de LUMS se documentan por separado:

* Instalación y despliegue → `install.md`
* Administración y mantenimiento → `administration.md`
* Solución de problemas → `troubleshooting.md`
* Arquitectura de seguridad y auditorías → `security.md`
* Descripción general del proyecto → `README.md`

Separar estas responsabilidades evita que la documentación de temas se convierta en otro manual de instalación o administración.

---

## 10. Principio fundamental

El sistema opcional de temas puede resumirse así:

> **Un LUMS. Un backend. Un modelo de seguridad. Muchas interfaces posibles.**

# LUMS — Sistema de temas opcional

## Parte 2 — Estructura y selección de temas

## 11. Estructura del tema

El sistema opcional separa la selección del tema de su presentación visual.

Conceptualmente, un tema consta de tres capas:

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

El identificador determina qué tema se ha seleccionado.

El mecanismo de selección determina cuál debe estar activo en ese momento.

La capa de presentación aplica la configuración visual correspondiente a la interfaz de LUMS.

Esta separación permite añadir o quitar temas sin cambiar la arquitectura fundamental de LUMS.

---

## 12. Selección de temas

La selección del tema se gestiona en el frontend.

El tema seleccionado se trata como una preferencia local de presentación, no como una propiedad de la cuenta en el servidor.

Conceptualmente:

```text
User
 │
 ▼
Theme Selector
 │
 ▼
Selected Theme Identifier
 │
 ▼
Frontend Theme Initialization
 │
 ▼
Active Theme
```

El backend no necesita saber qué tema visual está seleccionado.

Por tanto, cambiar de tema tampoco afecta a otros usuarios.

Dos usuarios pueden acceder a la misma instancia de LUMS y usar temas visuales completamente distintos.

---

## 13. Preferencia local del tema

El navegador puede guardar localmente el tema seleccionado.

El almacenamiento local aporta comodidad:

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

La selección guardada debe tratarse como estado del cliente no confiable.

El servidor nunca debe interpretarla como:

* un rol
* un permiso
* un estado de autenticación
* una configuración de seguridad
* una preferencia administrativa

El navegador puede seleccionar la apariencia, pero no controla la autorización.

---

## 14. Inicialización del tema

Al cargar la interfaz de LUMS, el frontend determina qué tema debe estar activo.

Secuencia conceptual:

```text
Page Load
   │
   ▼
Read Stored Theme
   │
   ▼
Is Theme Valid?
   │
   ├── Yes ──────► Apply Theme
   │
   └── No ───────► Use Standard Theme
```

Si no existe una preferencia, debería usarse la presentación estándar de LUMS.

Si el identificador guardado ya no es compatible, debería aplicarse la misma alternativa.

Así se evita que una preferencia local obsoleta rompa la interfaz.

---

## 15. Tema predeterminado

El tema estándar de LUMS es la presentación de referencia.

Proporciona el aspecto base con el que se definen los temas opcionales.

Por tanto, el tema estándar debería seguir siendo:

* funcional
* legible
* accesible
* visualmente completo
* independiente de recursos decorativos opcionales

Los temas opcionales no deben convertirse en requisitos para el funcionamiento normal de LUMS.

---

## 16. Aplicación del tema

El frontend puede representar el tema activo mediante un estado compartido de la aplicación o un atributo de tema en el elemento raíz.

Conceptualmente:

```html
<html data-theme="theme-id">
```

La implementación exacta puede cambiar a medida que evoluciona el frontend.

El requisito arquitectónico importante es que el sistema de estilos del frontend pueda identificar de forma coherente el tema activo.

Esto permite mantener separados los estilos específicos del tema y la estructura común de la aplicación.

---

## 17. Estilos específicos del tema

Los estilos de los temas deberían implementarse principalmente con CSS, en vez de duplicar el marcado de la aplicación.

Conceptualmente:

```text
Common HTML
     │
     ├── Standard styling
     ├── Stadium styling
     ├── Golf styling
     ├── Nerd styling
     ├── Geek styling
     └── Admin styling
```

Así los mismos componentes de aplicación siguen estando disponibles en todos los temas.

Por ejemplo, una tabla de clientes sigue siendo una tabla de clientes, independientemente del tema activo.

Solo cambia su presentación.

---

## 18. Componentes compartidos de la aplicación

Los temas no deberían crear versiones independientes de las páginas de LUMS.

Debe conservarse este principio:

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

En lugar de:

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

Duplicar páginas dificultaría mucho el mantenimiento y podría crear diferencias de comportamiento entre temas.

Por tanto, un tema debería decorar la interfaz común, no sustituir la aplicación.

---

## 19. Recursos de los temas

Cuando proceda, los temas pueden usar recursos adicionales del frontend.

Entre los recursos posibles se incluyen:

* imágenes de fondo
* gráficos decorativos
* iconos
* animaciones
* superposiciones visuales
* ilustraciones específicas del tema

Los recursos siguen perteneciendo a la capa de presentación del frontend.

No deben contener:

* credenciales
* tokens de cliente
* claves secretas
* archivos de base de datos
* material de autenticación
* datos operativos privados

Los recursos de temas deben considerarse recursos públicos del frontend.

---

## 20. Efectos visuales opcionales

Algunos temas pueden ofrecer efectos visuales adicionales, por ejemplo:

* fondos animados
* efectos de red decorativos
* movimiento ambiental
* elementos de interfaz temáticos
* adornos visuales dinámicos

Estos efectos deben seguir siendo opcionales.

Nunca deben ser necesarios para el funcionamiento de LUMS.

---

## 21. Movimiento reducido

Los efectos visuales deberían respetar a los usuarios que prefieren reducir el movimiento.

Cuando se usen elementos animados o en cambio continuo, el sistema debería ofrecer un comportamiento apropiado para movimiento reducido.

Conceptualmente:

```text
Normal motion
     │
     ├── animations enabled
     └── visual effects enabled

Reduced motion
     │
     ├── animations reduced or disabled
     └── essential interface remains functional
```

La accesibilidad tiene prioridad sobre la animación decorativa.

El tema debe seguir siendo utilizable aunque se desactiven los efectos visuales.

---

## 22. Independencia del tema

Cambiar el tema no debe desencadenar efectos secundarios operativos.

Por ejemplo:

```text
Theme change
     │
     ├── No client restart
     ├── No agent restart
     ├── No job cancellation
     ├── No database migration
     ├── No token rotation
     └── No permission change
```

Por diseño, el sistema de temas está aislado del ciclo de vida operativo de LUMS.

---

## 23. Gestión de errores del tema

Un tema debería fallar de forma segura.

Si no se puede cargar un recurso o componente de presentación específico, la interfaz común de LUMS debería seguir siendo utilizable.

La recuperación preferida es:

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

Un problema visual no debe convertirse en un problema de disponibilidad de la aplicación.

---

## 24. Añadir un tema

Un tema nuevo debería conservar la separación existente entre el comportamiento de la aplicación y la presentación.

Secuencia conceptual:

```text
1. Define theme identifier
2. Define visual design
3. Add theme styling
4. Add optional assets
5. Add theme to selection mechanism
6. Test normal pages
7. Test different RBAC roles
8. Test reduced-motion behavior
9. Test fallback behavior
10. Verify no backend behavior changed
```

Un tema nuevo solo está completo cuando la funcionalidad existente de LUMS permanece sin cambios.

---

## 25. Eliminar un tema

La eliminación de un tema también debería gestionarse de forma controlada.

Si un usuario conserva localmente un tema eliminado, el frontend debe detectar que el identificador ya no está disponible y volver al tema estándar.

Por tanto, la eliminación de un tema visual no debe dejar inutilizable la interfaz de LUMS del usuario.

---

## 26. Nombres de los temas

Los nombres deberían distinguir claramente entre:

* el identificador interno
* el nombre visible
* el concepto visual

Por ejemplo:

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

Esta separación permite cambiar el texto visible sin modificar innecesariamente la implementación interna.

---

## 27. Conceptos actuales de temas

El sistema opcional de temas de LUMS se ha diseñado para admitir varias identidades visuales en una aplicación común.

Los conceptos documentados actualmente incluyen:

| Identificador | Concepto |
| --- | --- |
| `standard` | Standard LUMS |
| `LUMSStadium` | LUMS Stadium |
| `golf` | Golf Club |
| `nerd` | Nerd Mode |
| `geek` | Geek Lab |
| `admin` | Enterprise Admin |

Estos temas representan distintas direcciones visuales, no distintas ediciones de LUMS.

Todos forman parte de la misma aplicación.

---

## 28. Un backend, muchas interfaces

La relación final puede resumirse así:

```text
                     ┌── Standard
                     ├── Stadium
                     ├── Golf
                     ├── Nerd
                     ├── Geek
                     └── Admin
                           │
                           ▼
                    Common LUMS UI
                           │
                           ▼
                       LUMS API
                           │
                           ▼
                     LUMS Backend
```

La capa de temas termina en el límite de presentación.

Todo lo que queda por debajo de ese límite es común a todos los temas.

# LUMS — Sistema de temas opcional

## Parte 3 — Conceptos de temas

## 29. Standard LUMS

El tema Standard LUMS es la presentación de referencia de la aplicación.

Su propósito es ofrecer una interfaz clara y funcional sin exigir un concepto visual específico.

El tema estándar debería priorizar:

* la legibilidad
* una jerarquía clara de la información
* una navegación predecible
* la accesibilidad
* pocas distracciones visuales
* una presentación coherente de los componentes

Es la presentación alternativa del sistema de temas.

Por tanto, debería seguir siendo utilizable aunque no esté disponible ningún tema visual opcional.

---

## 30. LUMS Stadium

**LUMS Stadium** es una interpretación visual más expresiva de la interfaz de LUMS.

El concepto combina la administración de sistemas con una identidad visual inspirada en un estadio.

Entre los posibles elementos de diseño se incluyen:

* paneles de información inspirados en marcadores
* indicadores de estado más destacados
* presentación orientada a eventos
* fondos temáticos
* énfasis visual en los estados operativos
* elementos decorativos de estadio

El tema mantiene la misma funcionalidad que Standard LUMS.

Una actualización correcta sigue siendo una actualización correcta.

Un trabajo fallido sigue siendo fallido.

Solo cambia la presentación.

---

## 31. Golf Club

El tema **Golf Club** ofrece una identidad visual deliberadamente distinta.

En vez de una estética tradicional de servidor o infraestructura, la interfaz adopta un concepto recreativo más tranquilo.

La dirección visual puede destacar:

* superficies limpias
* decoración discreta
* elementos inspirados en el golf
* metáforas visuales de un campo
* una presentación serena de los estados
* acentos temáticos ligeros

El concepto demuestra que LUMS no necesita parecer una consola de administración tradicional para seguir siendo funcional.

El backend y el comportamiento de la aplicación no cambian.

---

## 32. Nerd Mode

**Nerd Mode** está pensado para una presentación más técnica y lúdica.

El concepto puede destacar el carácter técnico de LUMS con elementos como:

* estilos inspirados en terminales
* terminología técnica
* elementos visuales orientados a sistemas
* presentación de estilo desarrollador
* estética de diagnóstico
* decoración deliberadamente técnica

El tema debe mantener una jerarquía clara de la información.

Una interfaz lúdica no debería dificultar la comprensión de la información operativa.

---

## 33. Geek Lab

**Geek Lab** representa un entorno técnico más experimental.

El concepto visual puede combinar:

* estética de laboratorio
* experimentación técnica
* visualización de infraestructura
* diagramas de sistemas
* elementos científicos o de ingeniería
* efectos visuales experimentales

El tema pretende que la interfaz parezca un laboratorio de infraestructura y, al mismo tiempo, mantener intacta la funcionalidad de LUMS.

La experimentación visual debe permanecer aislada de la aplicación operativa.

---

## 34. Enterprise Admin

El tema **Enterprise Admin** representa una interfaz administrativa más conservadora.

Su dirección visual puede priorizar:

* información estructurada
* diseños compactos
* paneles administrativos
* indicadores de estado claros
* densidad operativa
* menos elementos decorativos

Este tema es especialmente adecuado para usuarios que prefieren el aspecto convencional de una consola de administración.

No introduce privilegios administrativos adicionales.

El nombre describe el concepto visual, no un nivel de autorización.

---

## 35. Comparación de temas

Los temas se pueden considerar distintas interpretaciones visuales de la misma aplicación:

| Tema | Dirección visual | Carácter principal |
| --- | --- | --- |
| Standard LUMS | Claro / funcional | Interfaz de referencia |
| LUMS Stadium | Estadio / evento | Expresivo |
| Golf Club | Recreativo / tranquilo | Relajado |
| Nerd Mode | Técnico / lúdico | Orientado a desarrolladores |
| Geek Lab | Experimental / técnico | Laboratorio |
| Enterprise Admin | Estructurado / administrativo | Conservador |

Esta tabla describe únicamente conceptos de presentación.

**No** describe diferencias en:

* permisos
* funciones
* acceso a la API
* acceso a clientes
* ejecución de trabajos
* gestión de paquetes
* seguridad

---

## 36. La misma interfaz, distinta presentación

Un objetivo central de diseño es que el mismo componente de la aplicación siga siendo reconocible en todos los temas.

Por ejemplo:

```text
Client List
   │
   ├── Standard presentation
   ├── Stadium presentation
   ├── Golf presentation
   ├── Nerd presentation
   ├── Geek presentation
   └── Enterprise presentation
```

Los datos subyacentes del cliente no cambian.

Solo cambia su presentación.

Lo mismo se aplica a:

* inventarios de software
* actualizaciones disponibles
* trabajos de actualización
* historial de trabajos
* información de usuarios
* estado del sistema
* interfaces de gestión de paquetes

---

## 37. Estados operativos

Los temas pueden destacar visualmente distintos estados operativos.

Por ejemplo:

```text
PENDING
RUNNING
SUCCESS
FAILED
```

Un tema puede representar esos estados con estilos distintos, pero su significado semántico debe mantenerse coherente.

El tema no debe redefinir los estados de la aplicación.

Por ejemplo:

```text
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

La representación visual solo muestra el estado del backend.

---

## 38. Presentación de errores

Los temas también pueden cambiar el aspecto visual con que se presentan los errores.

Sin embargo, la información de error debe seguir siendo comprensible.

Un tema no debería:

* ocultar información importante de errores
* reemplazar información técnica por texto decorativo
* hacer que las advertencias sean indistinguibles de los estados normales
* suprimir fallos operativos

El estilo visual puede mejorar la presentación, pero no debe eliminar la información de diagnóstico necesaria para entender el problema.

---

## 39. Coherencia de los estados

Un mismo estado debe conservar un significado semántico coherente en todos los temas.

Por ejemplo:

| Estado | Significado |
| --- | --- |
| Pendiente | En espera de ejecución |
| En ejecución | Se está procesando |
| Correcto | Se completó correctamente |
| Fallido | Falló la ejecución |

Un tema puede representar estos estados con distintos colores, iconos, tipografía o diseño.

El significado subyacente no debe cambiar.

---

## 40. Elementos decorativos específicos

Los elementos decorativos deben seguir siendo secundarios frente a la información operativa.

Algunos ejemplos:

* fondos
* patrones
* ilustraciones
* efectos ambientales
* iconos temáticos
* adornos visuales

Debe conservarse esta prioridad:

```text
Operational Information
        │
        ▼
Application Usability
        │
        ▼
Accessibility
        │
        ▼
Visual Decoration
```

La decoración nunca debe tener prioridad sobre la información necesaria para operar LUMS.

---

## 41. Densidad visual

Los distintos temas pueden emplear distintas densidades visuales.

Por ejemplo:

* Enterprise Admin puede priorizar la densidad de información.
* Standard LUMS puede priorizar una legibilidad equilibrada.
* Golf Club puede usar más espacio en blanco.
* Nerd Mode puede usar elementos técnicos compactos.
* Stadium puede destacar áreas de estado grandes.
* Geek Lab puede ofrecer más contexto visual.

Estas diferencias son opciones de presentación.

No cambian la cantidad ni la autoridad de los datos subyacentes.

---

## 42. Accesibilidad en todos los temas

Todos los temas deben conservar una usabilidad básica. Esto incluye:

* texto legible
* distinción visual suficiente
* controles utilizables
* indicadores de estado comprensibles
* accesibilidad con teclado
* estados de foco utilizables y visibles
* compatibilidad con las preferencias de movimiento reducido

El color no debe ser el único medio para comunicar un estado importante.

Por ejemplo, un trabajo fallido no debería identificarse únicamente porque se muestra en un color determinado.

---

## 43. Animaciones específicas del tema

Los temas pueden incluir animaciones cuando mejoren el concepto visual.

Por ejemplo:

* transiciones sutiles
* fondos animados
* efectos de red
* transiciones de estado
* decoración ambiental

Las animaciones deben seguir siendo secundarias respecto a la aplicación.

No deberían:

* impedir la interacción
* ocultar controles
* distraer continuamente de los datos operativos
* interferir con la accesibilidad
* afectar a las operaciones del backend

---

## 44. La red viva

Algunos temas de LUMS pueden usar una capa visual dinámica inspirada en redes.

El concepto representa LUMS como un entorno de infraestructura vivo:

```text
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

Una visualización así es decorativa, salvo que se conecte explícitamente a datos reales de la aplicación.

Por tanto, una red visual nunca debe interpretarse como topología de red autoritativa, a menos que la aplicación proporcione explícitamente esa información.

La distinción es importante:

> **Una representación visual no es automáticamente telemetría operativa.**

---

## 45. Datos decorativos frente a datos reales

Los efectos visuales específicos de un tema deben mantenerse claramente separados de los datos reales de LUMS.

Por ejemplo:

```text
Decorative node
    ≠
Real client

Animated connection
    ≠
Real network connection

Visual status effect
    ≠
Backend job state
```

Así se evita que los usuarios confundan una visualización estética con información real del sistema.

---

## 46. Identidad del tema

Cada tema debería tener una identidad reconocible sin convertirse en un producto independiente.

El objetivo es:

```text
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

Así, el sistema puede ser lúdico y flexible sin perder la integridad técnica de la aplicación.

---

## 47. Regla de diseño de los temas

La regla de diseño más importante para todos los temas es:

> **Un tema puede ser expresivo, inusual, técnico, lúdico o conservador, pero siempre debe seguir siendo LUMS.**

La aplicación debe seguir siendo reconocible como el mismo sistema, independientemente de la presentación visual seleccionada.

# LUMS — Sistema de temas opcional

## Parte 4 — Implementación del frontend y accesibilidad

## 48. Capa de temas del frontend

El sistema opcional de temas pertenece por completo al frontend de LUMS.

Su responsabilidad se limita a la presentación y a gestionar las preferencias del usuario.

Conceptualmente:

```text
┌─────────────────────────────────┐
│          LUMS Frontend          │
│                                 │
│  Common Application Logic       │
│              │                  │
│              ▼                  │
│       Theme Presentation        │
│              │                  │
│              ▼                  │
│       Browser Rendering         │
└─────────────────────────────────┘
```

La capa de temas no sustituye la lógica común del frontend.

En cambio, añade una capa de presentación alrededor de ella.

---

## 49. Inicialización de temas

La inicialización del tema debería formar parte del proceso normal de inicio del frontend.

Secuencia conceptual:

```text
Frontend starts
      │
      ▼
Theme system initializes
      │
      ▼
Stored preference is evaluated
      │
      ▼
Theme availability is checked
      │
      ├── Valid → selected theme
      │
      └── Invalid → standard theme
      │
      ▼
LUMS interface rendered
```

La inicialización debería ser ligera y no depender de que el backend esté disponible.

El usuario debería poder cargar la presentación visual aunque falle posteriormente una solicitud a la API.

---

## 50. Estado del tema

El tema activo es estado del frontend.

Por ello, debe tratarse de forma distinta al estado de la aplicación.

### Estado del tema

Algunos ejemplos:

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### Estado de la aplicación

Algunos ejemplos:

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

El estado del tema nunca debe sobrescribir ni suplantar el estado de la aplicación.

---

## 51. Atributo de tema raíz

Un atributo en el elemento raíz es una representación conceptual adecuada del tema activo.

Por ejemplo:

```html
<html data-theme="standard">
```

o:

```html
<html data-theme="nerd">
```

CSS puede usar el tema activo como selector.

La implementación exacta puede evolucionar, pero el objetivo arquitectónico permanece:

> **Una estructura de aplicación, varias definiciones de presentación.**

---

## 52. Organización de CSS

Los estilos específicos de tema deberían distinguirse de los estilos comunes de LUMS.

Conceptualmente:

```text
Common styles
│
├── Layout
├── Forms
├── Tables
├── Navigation
├── Status elements
└── Shared components

Theme styles
│
├── Standard
├── Stadium
├── Golf
├── Nerd
├── Geek
└── Admin
```

Los estilos comunes definen el diseño, los formularios, las tablas, la navegación, los estados y los componentes compartidos. Los estilos de tema definen Standard, Stadium, Golf, Nerd, Geek y Admin.

Los estilos comunes deberían definir la estructura funcional.

Los estilos del tema deberían definir la identidad visual.

Esto reduce la duplicación y simplifica el mantenimiento futuro de los temas.

---

## 53. Variables CSS

Los sistemas de temas pueden utilizar propiedades personalizadas de CSS para separar los valores semánticos de su representación visual.

Por ejemplo:

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Un tema puede aportar sus propios valores:

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Siempre que sea práctico, los componentes deberían consumir variables semánticas en lugar de codificar valores específicos de un tema.

---

## 54. Componentes compartidos

El sistema de temas debería aplicar estilos a componentes compartidos en vez de duplicarlos.

Entre los componentes habituales están:

* la navegación
* los botones
* los formularios
* las tablas
* los indicadores de estado
* las tarjetas
* los cuadros de diálogo
* los elementos de gestión de paquetes
* los elementos de trabajos de actualización
* la información de clientes
* la información del sistema

El mismo componente debería conservar una funcionalidad idéntica en cualquier tema activo.

---

## 55. Recursos de los temas

Los temas opcionales pueden usar recursos específicos.

Algunas categorías posibles:

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Los recursos del tema deberían seguir siendo recursos del frontend.

No deben contener información sensible de la aplicación.

En particular, nunca deben incluir:

* contraseñas
* claves secretas
* tokens de cliente
* contenido de bases de datos
* certificados privados
* material de autenticación

---

## 56. Carga de recursos

Los recursos de un tema deberían cargarse solo cuando sean necesarios.

La mera existencia de un tema no debería aumentar innecesariamente el coste de todas las páginas de LUMS.

Cuando sea práctico:

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

en lugar de:

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

Esto cobra cada vez más importancia a medida que se añaden temas y efectos visuales.

---

## 57. Rendimiento de los temas

La personalización visual no debe perjudicar significativamente la usabilidad de LUMS.

Debe prestarse atención en particular a:

* imágenes de fondo grandes
* elementos con animación continua
* efectos de canvas
* actualizaciones repetidas del DOM
* filtros visuales costosos
* solicitudes de red innecesarias

Las páginas operativas —como listas de clientes, inventarios de software y vistas de trabajos de actualización— deberían seguir respondiendo con fluidez.

---

## 58. JavaScript decorativo

Un tema puede utilizar JavaScript para efectos visuales, como fondos animados, visualizaciones de red, decoraciones dinámicas o interacciones específicas del tema.

Este JavaScript debe permanecer aislado de la lógica operativa de la aplicación.

Un script decorativo nunca debe ser responsable de:

* la autorización
* la creación de trabajos
* la instalación o eliminación de paquetes
* la ejecución de actualizaciones
* la autenticación de clientes
* el registro de auditoría

La distinción debe permanecer clara:

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Visualización de red

Si un tema usa una visualización de estilo de red, debe tratarse como componente de presentación.

Por ejemplo:

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

A menos que se conecte explícitamente a datos autoritativos de LUMS, la visualización no debería sugerir que representa el estado real de la red.

Así se evita confundir los gráficos decorativos con monitorización o telemetría.

---

## 60. Movimiento reducido

Los temas con animaciones deberían admitir las preferencias de movimiento reducido.

El comportamiento preferido se puede expresar así:

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

La funcionalidad esencial debe permanecer igual.

El movimiento reducido solo debería afectar a la presentación.

---

## 61. Foco y navegación con teclado

Los estilos del tema deben conservar la usabilidad mediante teclado.

Los elementos interactivos importantes deberían mantener estados de foco visibles.

Los temas no deberían eliminar los contornos de foco sin ofrecer una alternativa igual de clara.

Por ejemplo:

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

Esto se aplica a:

* la navegación
* los botones
* los enlaces
* los campos de formulario
* los selectores
* los cuadros de diálogo
* los controles de gestión de paquetes

---

## 62. Independencia del color

La información importante no debe depender únicamente del color.

Por ejemplo:

```text
FAILED
```

`FAILED` debería seguir siendo comprensible mediante texto, iconos, estructura u otra indicación accesible, aunque los colores del tema no estén disponibles.

Esto es especialmente importante porque los temas pueden utilizar paletas muy distintas.

---

## 63. Contraste

Todos los temas deberían mantener un contraste suficiente entre:

* el texto y los fondos
* los controles y los fondos
* los indicadores de estado y los elementos circundantes
* los elementos enfocados y su entorno

Una paleta visualmente interesante no sustituye a una información legible.

Si los colores de un tema entran en conflicto con los requisitos de accesibilidad, debe priorizarse la legibilidad.

---

## 64. Interfaz de selección de temas

El selector de temas forma parte de la interfaz común de LUMS.

Debería seguir siendo comprensible con cualquier tema activo.

Conceptualmente:

```text
Theme selector
      │
      ├── Standard LUMS
      ├── LUMS Stadium
      ├── Golf Club
      ├── Nerd Mode
      ├── Geek Lab
      └── Enterprise Admin
```

Seleccionar otro tema debería cambiar la presentación sin cambiar la sesión actual de LUMS ni el estado operativo.

---

## 65. Independencia de la sesión

Cambiar de tema no debe cerrar la sesión del usuario.

Tampoco debe:

* invalidar la sesión
* cambiar el rol
* rotar los tokens de cliente
* modificar el estado de autenticación del servidor

La preferencia de tema está separada de la autenticación.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. Independencia de RBAC

Los temas deben mantenerse independientes de RBAC.

Por ejemplo:

```text
Administrator
     │
     └── sees functionality permitted to administrators

Operator
     │
     └── sees functionality permitted to operators

Viewer
     │
     └── sees functionality permitted to viewers
```

El tema seleccionado no altera estos permisos.

Un Viewer que utiliza Enterprise Admin no se convierte en administrador.

Un Administrator que utiliza Nerd Mode no pierde sus privilegios administrativos.

En todos los casos, el backend sigue siendo la autoridad.

---

## 67. Aislamiento de errores

Un fallo en una función visual opcional no debería romper las funciones básicas de LUMS.

Por ejemplo, si falla una animación decorativa:

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

Siempre que sea posible, las funciones visuales deberían fallar independientemente de la funcionalidad de la aplicación.

Esto es especialmente importante para efectos opcionales, como fondos animados o visualizaciones de red.

---

## 68. Compatibilidad con navegadores

El sistema de temas debería usar funciones del navegador compatibles con los navegadores previstos para el entorno de despliegue de LUMS.

Cuando una función visual no esté disponible, la interfaz debería degradarse de forma controlada en vez de volverse inutilizable.

La presentación estándar debería seguir siendo la alternativa base.

---

## 69. Principio de implementación

La implementación se puede resumir así:

```text
Common HTML
     +
Common LUMS JavaScript
     +
Theme selection
     +
Theme-specific CSS/assets
     =
Optional visual layer
```

Lo siguiente debe permanecer fuera de la capa de temas:

```text
Authentication
Authorization
Database
Jobs
Package management
Client authentication
Audit logging
Security decisions
```

Esta separación hace que los temas puedan ser expresivos sin acoplarlos al comportamiento central de LUMS.

# LUMS — Sistema de temas opcional

## Parte 5 — Seguridad, pruebas y desarrollo

## 70. Límite de seguridad

El sistema de temas forma parte del frontend y, por tanto, funciona en un entorno de cliente no confiable.

El navegador controla la capa de presentación.

El navegador **no** controla la autorización de LUMS.

El límite de seguridad sigue siendo:

```text
Browser
   │
   │ untrusted presentation
   ▼
LUMS API
   │
   │ authoritative validation
   ▼
LUMS Backend
```

Por tanto, todas las decisiones sensibles a la seguridad deben seguir tomándose en el servidor.

---

## 71. La selección del tema no es autorización

Nunca se debe interpretar el tema seleccionado como una señal de autorización.

Por ejemplo:

```text
data-theme="admin"
```

no significa que el usuario actual sea administrador.

La palabra `admin` en el identificador de un tema es puramente descriptiva.

El rol real del usuario debe proceder siempre de la sesión autenticada de la aplicación y de la lógica de autorización del servidor.

---

## 72. La visibilidad del frontend no es seguridad

Un tema o un script del frontend puede ocultar un elemento de interfaz.

Esto sirve para la presentación.

No basta para controlar el acceso.

```text
Hidden button
      ≠
Unauthorized operation prevented
```

El endpoint de API correspondiente debe validar por separado los permisos del usuario.

Esto se aplica a todas las funciones privilegiadas de LUMS.

---

## 73. Los recursos de temas son públicos

Los recursos del frontend deben considerarse públicamente accesibles para cualquiera que pueda acceder a la interfaz web de LUMS.

Por consiguiente, los archivos de temas nunca deben contener secretos.

No incluyas en los recursos:

```text
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

La información que deba permanecer confidencial no pertenece a un recurso de tema.

---

## 74. No incluir secretos del backend en temas

El JavaScript de un tema no debe contener credenciales del servidor ni material privilegiado de API.

Cuando sea necesario, un tema debería comunicarse con la capa existente de la aplicación frontend.

No debe introducir un mecanismo de autenticación alternativo.

> **Los temas consumen datos de presentación; no crean credenciales de seguridad.**

---

## 75. Falsificación de solicitudes entre sitios (CSRF)

La funcionalidad de un tema no debe eludir la protección CSRF existente.

Si el tema incluye un elemento de interfaz que inicia una operación que requiere una solicitud protegida, la solicitud debe cumplir los mismos requisitos de seguridad que la interfaz común de LUMS.

El hecho de que sea código visual no exime al tema.

---

## 76. Uso de la API

Un tema debería evitar implementar su propia lógica operativa de API.

Cuando necesite datos de aplicación, debería usar los mecanismos establecidos de la aplicación frontend de LUMS.

Así se evitan varias implementaciones independientes de:

* autenticación
* solicitudes de API
* manejo de errores
* supuestos de autorización
* gestión de trabajos

La lógica común de la aplicación sigue siendo la capa de integración frontend autoritativa.

---

## 77. Aislamiento de los temas

Se debería poder quitar un tema sin eliminar funciones esenciales de LUMS.

Conceptualmente:

```text
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

Así los temas son realmente opcionales.

---

## 78. Pruebas de seguridad

Las pruebas de seguridad deberían demostrar que cambiar de tema no altera el modelo de seguridad de LUMS.

Entre las comprobaciones pertinentes:

* Viewer sigue siendo Viewer
* Operator sigue siendo Operator
* Administrator sigue siendo Administrator
* los endpoints de API protegidos siguen protegidos
* la protección CSRF sigue activa
* la autenticación de clientes permanece igual
* los permisos de trabajos de actualización permanecen iguales
* los permisos de gestión de paquetes permanecen iguales
* el registro de auditoría permanece igual

El tema nunca debe usarse como prueba de que una operación es segura.

---

## 79. Pruebas funcionales de los temas

Cada tema debería probarse con la aplicación común.

Como mínimo:

```text
Login
Client list
Client details
Installed software
Available updates
Update jobs
Job history
Package management
User management
System maintenance
Logout
```

Las funciones disponibles dependen del rol del usuario autenticado.

La prueba verifica que la representación del tema no rompa el funcionamiento normal de la aplicación.

---

## 80. Pruebas de temas con RBAC

Las pruebas de temas deberían incluir todos los roles pertinentes.

| Rol | Pruebas del tema |
| --- | --- |
| Administrator | Obligatorio |
| Operator | Obligatorio |
| Viewer | Obligatorio |

Para cada rol, verifica que cambiar de tema no modifique las funciones permitidas.

Por ejemplo:

```text
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

El tema visual no debe cambiar el resultado.

---

## 81. Pruebas de cambio de tema

El cambio de tema debería probarse repetidamente. Por ejemplo:

```text
Standard
   ↓
Stadium
   ↓
Golf
   ↓
Nerd
   ↓
Geek
   ↓
Admin
   ↓
Standard
```

La aplicación debería seguir siendo utilizable durante toda la secuencia.

Presta atención en particular a:

* los cambios de diseño
* las tablas
* la navegación
* los cuadros de diálogo
* los formularios
* los indicadores de estado
* el texto largo
* el comportamiento adaptable

---

## 82. Pruebas de persistencia

Si la preferencia del tema se guarda localmente, prueba lo siguiente:

1. Selecciona un tema.
2. Vuelve a cargar la página.
3. Confirma que el tema sigue seleccionado.
4. Cierra el navegador.
5. Vuelve a abrir LUMS.
6. Confirma que la preferencia sigue gestionándose correctamente.
7. Elimina o invalida el tema guardado.
8. Confirma que se vuelve al tema estándar.

El valor guardado nunca debe tratarse como estado de seguridad de la aplicación.

---

## 83. Pruebas de temas no válidos

Un identificador de tema no válido no debería romper la interfaz.

Por ejemplo:

```text id="4j5cqn"
unknown-theme
```

Debería producir una alternativa segura, no una página inutilizable.

El comportamiento deseado es:

```text
Invalid theme
     │
     ▼
Standard theme
     │
     ▼
LUMS remains usable
```

---

## 84. Pruebas de fallos de recursos

También se deberían probar los fallos de recursos opcionales.

Algunos ejemplos:

* imagen ausente
* animación no disponible
* ruta de recurso no válida
* función visual no compatible
* error de JavaScript en una decoración opcional

Siempre que sea posible, la aplicación común debería seguir siendo utilizable.

---

## 85. Pruebas de movimiento reducido

En los temas con animaciones, prueba entornos con movimiento normal y reducido.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Los controles importantes de la aplicación deben seguir funcionando plenamente en ambos casos.

---

## 86. Pruebas de diseño adaptable

Los temas deberían probarse en distintos tamaños de ventana:

* escritorio
* ventana del tamaño de una tableta
* ventana estrecha o del tamaño de un móvil

La identidad visual no debe perjudicar el uso de los controles ni la legibilidad de los datos de aplicación.

Presta atención en particular a:

* la navegación
* las tablas
* los botones de acción
* los controles de gestión de paquetes
* la información de estado de los trabajos
* los cuadros de diálogo
* los selectores de tema

---

## 87. Pruebas de rendimiento

Se debería evaluar el impacto de los efectos visuales en el rendimiento del navegador.

Observa, entre otros aspectos:

* tiempo de carga de la página
* capacidad de respuesta del renderizado
* uso de CPU
* uso de memoria
* fluidez de las animaciones
* actualizaciones repetidas del DOM
* solicitudes de red

Los temas deberían mejorar la presentación sin convertirse en un cuello de botella de rendimiento.

---

## 88. Flujo de desarrollo

Siempre que sea posible, desarrolla los temas independientemente de los cambios del backend.

Flujo recomendado:

```text
Design
   ↓
Frontend implementation
   ↓
Theme selector integration
   ↓
Accessibility review
   ↓
Functional testing
   ↓
RBAC testing
   ↓
Fallback testing
   ↓
Performance review
   ↓
Documentation
```

Introduce cambios en el backend solo cuando exista una necesidad real de la aplicación.

Normalmente, un tema visual no debería requerir cambios en el backend.

---

## 89. Reglas de desarrollo

Al desarrollar un tema:

1. Reutiliza los componentes existentes de LUMS.
2. Evita duplicar páginas.
3. Aísla los estilos específicos del tema.
4. Separa el JavaScript decorativo de la lógica operativa.
5. No introduzcas lógica de autenticación.
6. No introduzcas lógica de autorización.
7. No expongas secretos.
8. Conserva la accesibilidad.
9. Conserva el comportamiento de movimiento reducido.
10. Prueba todos los roles pertinentes.
11. Prueba la alternativa estándar.
12. Documenta los recursos y comportamientos nuevos.

---

## 90. Verificación de cambios

Antes de dar por terminado un cambio de tema, verifica tanto la presentación como la funcionalidad.

Secuencia útil:

```text
Theme changed
      │
      ▼
Visual inspection
      │
      ▼
Page functionality
      │
      ▼
Role behavior
      │
      ▼
API behavior
      │
      ▼
Browser console
      │
      ▼
Regression tests
```

Un tema no está terminado únicamente porque se vea bien.

También debe dejar intacto el comportamiento de LUMS.

---

## 91. Principio de regresión

El desarrollo de temas debería seguir el mismo principio general que otros cambios de LUMS:

> **Cambiar → Probar → Verificar → Documentar**

Un cambio visual también puede causar regresiones funcionales, por ejemplo:

* botones ocultos
* texto ilegible
* diseño roto
* controles inaccesibles
* conflictos de JavaScript
* recursos ausentes
* selectores incorrectos
* fallos de diseño móvil

Por tanto, probar forma parte del desarrollo de temas; no es un paso final opcional.

---

## 92. Diagnóstico: el tema no se carga

Si no aparece el tema seleccionado:

1. Vuelve a cargar la página.
2. Comprueba si se carga el tema estándar.
3. Revisa la consola del navegador.
4. Comprueba si el identificador seleccionado es válido.
5. Comprueba si están disponibles los recursos necesarios.
6. Busca errores de JavaScript.
7. Si hace falta, borra la preferencia local del tema.
8. Vuelve a cargar la página y verifica la alternativa estándar.

No modifiques la configuración de seguridad del backend para resolver un problema visual del frontend.

---

## 93. Diagnóstico: el tema rompe el diseño

Si un tema causa problemas de diseño:

1. Cambia al tema Standard LUMS.
2. Confirma que la interfaz común funciona.
3. Identifica el componente afectado.
4. Inspecciona el CSS específico del tema.
5. Comprueba el comportamiento adaptable.
6. Revisa los errores de la consola.
7. Corrige los estilos específicos del tema.
8. Vuelve a probar los demás temas.

El tema estándar proporciona una comparación de diagnóstico importante.

---

## 94. Diagnóstico: el tema provoca errores de JavaScript

Si el JavaScript específico del tema provoca errores:

1. Cambia al tema estándar.
2. Confirma que las funciones normales de LUMS están disponibles.
3. Identifica el script del tema que falla.
4. Determina si el error es decorativo o afecta a la aplicación.
5. Corrige el fallo específico del tema.
6. Verifica que el JavaScript común de LUMS no esté afectado.
7. Vuelve a probar el cambio entre temas.

No modifiques el JavaScript operativo únicamente para compensar un error decorativo del tema.

---

## 95. Diagnóstico: la preferencia del tema no es válida

Si localmente sigue guardado un tema antiguo o no válido:

```text
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

La solución preferida es una alternativa segura, no una intervención manual en el backend.

---

## 96. Documentación de temas

Cada tema nuevo debería documentar:

* el identificador interno
* el nombre visible
* el concepto visual
* los recursos necesarios
* los efectos visuales opcionales
* las consideraciones de accesibilidad
* el comportamiento de movimiento reducido
* las limitaciones conocidas

La documentación específica de implementación debe describir el código actual, no suposiciones sobre cómo podría funcionar el tema.

---

## 97. Conjunto actual de temas

Los conceptos de temas documentados son:

```text
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

El conjunto de temas se puede ampliar.

Se pueden añadir temas sin cambiar la arquitectura subyacente de LUMS, siempre que se mantenga la separación entre la presentación y el comportamiento de la aplicación.

---

## 98. Principio de desarrollo

El sistema opcional de temas debería seguir siendo una extensión controlada del frontend.

Su propósito es hacer LUMS más expresivo y adaptable sin complicar las operaciones.

La arquitectura preferida es:

```text id="l2e8o9"
Common LUMS
     │
     ├── Common functionality
     ├── Common security
     ├── Common backend
     └── Common application state
              │
              ▼
       Optional Theme Layer
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
    Theme A Theme B Theme C
```

La aplicación común sigue siendo la base.

Los temas siguen siendo extensiones opcionales.

# LUMS — Sistema de temas opcional

## Parte 6 — Mantenimiento, ampliación y estado final

## 99. Mantenimiento de temas

Siempre que sea posible, el mantenimiento de temas debería mantenerse separado del mantenimiento central de LUMS.

Una actualización visual normalmente debería afectar solo a recursos del frontend.

Los cambios habituales incluyen:

* ajustes de CSS
* recursos visuales
* JavaScript específico del tema
* mejoras de accesibilidad
* correcciones del diseño adaptable
* ajustes de animaciones
* cambios en el nombre o la presentación del tema

Una actualización del tema no debería requerir cambios en:

* la configuración de clientes
* los tokens de cliente
* el esquema de base de datos
* los trabajos de actualización
* la lógica de gestión de paquetes
* la autenticación
* RBAC
* los controles de seguridad del servidor

Si un cambio de tema requiere inesperadamente alguna de estas modificaciones, revisa la dependencia antes de continuar.

---

## 100. Actualizaciones de temas

Las actualizaciones deberían seguir el proceso habitual de desarrollo de LUMS:

```text
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

Para cambios mayores:

```text
Design
   ↓
Implementation
   ↓
Functional testing
   ↓
Accessibility testing
   ↓
RBAC regression testing
   ↓
Performance review
   ↓
Documentation
```

Un tema no debe considerarse terminado solo porque el resultado visual parezca correcto.

---

## 101. Añadir un tema nuevo

Se puede incorporar un tema sin cambiar el backend de LUMS.

Proceso recomendado:

### Paso 1 — Definir el concepto

Describe:

* la identidad visual
* el estilo objetivo
* la tipografía
* los colores
* los elementos decorativos
* las animaciones opcionales

### Paso 2 — Definir el identificador

Elige un identificador interno estable.

### Paso 3 — Implementar la presentación

Añade los estilos y recursos necesarios.

### Paso 4 — Integrar la selección

Haz que el tema esté disponible en el selector común.

### Paso 5 — Probar

Verifica:

* las páginas normales
* los controles interactivos
* los diseños adaptables
* la accesibilidad
* el movimiento reducido
* todos los roles RBAC pertinentes
* el comportamiento alternativo

### Paso 6 — Documentar

Registra el tema y los detalles pertinentes de su implementación.

---

## 102. Eliminar un tema

Eliminar un tema es un cambio de compatibilidad para los usuarios que aún puedan tenerlo seleccionado localmente.

Por tanto, el frontend debe gestionar de forma segura un identificador obsoleto.

```text
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

Eliminar un tema nunca debería requerir una migración de base de datos únicamente para borrar una preferencia del navegador.

---

## 103. Cambiar el nombre de un tema

Normalmente, el nombre visible puede cambiar independientemente del identificador interno.

Por ejemplo:

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

Si cambia el propio identificador interno, quizá se necesite una migración o una correspondencia de compatibilidad para las preferencias locales existentes.

Siempre que sea práctico, es preferible mantener estables los identificadores.

---

## 104. Compatibilidad de temas

Los temas deberían seguir siendo compatibles con los cambios de la interfaz común de LUMS.

Cuando se añade un componente compartido, comprueba los temas existentes para detectar:

* estilos ausentes
* espaciado roto
* texto ilegible
* colores incorrectos
* falta de comportamiento adaptable
* estados de foco incorrectos
* controles inaccesibles

Una función nueva del backend no requiere automáticamente una función nueva en los temas.

La aplicación común sigue siendo la fuente de verdad.

---

## 105. Nuevas funciones de LUMS

Cuando LUMS incorpora una función, normalmente se debería evaluar la compatibilidad con los temas después de que funcione la función común.

Secuencia recomendada:

```text
New LUMS feature
       │
       ▼
Common implementation
       │
       ▼
Functional tests
       │
       ▼
Theme compatibility
       │
       ▼
Theme-specific refinement
```

Así se evita que la personalización visual dependa del desarrollo de las funciones centrales.

---

## 106. Estabilidad de la API de temas

El sistema debería evitar crear una capa de API separada salvo que exista una necesidad real.

Los temas deberían consumir preferentemente el estado de la aplicación frontend y los mecanismos de API que LUMS ya utiliza.

Esto reduce:

* la duplicación de la lógica de solicitudes
* la duplicación del manejo de errores
* los supuestos de autorización incoherentes
* el mantenimiento adicional
* la superficie de ataque innecesaria

Por diseño, el sistema de temas es ligero.

---

## 107. Revisión de seguridad de temas

Al añadir o cambiar significativamente un tema, revisa lo siguiente:

```text
[ ] No credentials in assets
[ ] No client tokens in assets
[ ] No private keys
[ ] No authentication bypass
[ ] No authorization logic
[ ] No CSRF bypass
[ ] No direct security decisions
[ ] No unintended API endpoints
[ ] No sensitive information in frontend assets
[ ] Decorative scripts remain isolated
```

Esta revisión debe hacerse incluso cuando el cambio parezca puramente visual.

El código del frontend sigue siendo código ejecutable.

---

## 108. Revisión de accesibilidad de temas

Para cada tema, verifica:

```text
[ ] Text remains readable
[ ] Contrast remains sufficient
[ ] Focus states are visible
[ ] Keyboard navigation works
[ ] Controls remain usable
[ ] Statuses are not color-only
[ ] Reduced motion is respected
[ ] Responsive layout remains usable
[ ] Decorative effects do not obscure information
```

La accesibilidad debe considerarse parte de la calidad del tema, no una mejora opcional.

---

## 109. Lista de regresión de temas

Antes de aceptar un cambio de tema, comprueba:

```text
[ ] Standard theme works
[ ] Changed theme works
[ ] Other themes still work
[ ] Theme switching works
[ ] Stored preference works
[ ] Invalid preference falls back safely
[ ] Login works
[ ] Logout works
[ ] Client views work
[ ] Software views work
[ ] Update views work
[ ] Package-management views work
[ ] User-management views work where authorized
[ ] Job information remains readable
[ ] Error messages remain understandable
[ ] RBAC remains unchanged
[ ] Backend behavior remains unchanged
```

Las funciones visibles concretas de la prueba dependen del rol del usuario.

---

## 110. Independencia operativa

El sistema opcional de temas es deliberadamente independiente del ciclo operativo de LUMS.

Cambiar un tema no debe requerir:

```text
Agent restart
Watcher restart
Database restart
Client re-registration
Token rotation
Job cancellation
Package-manager changes
Network changes
```

Esto permite que la capa de presentación evolucione independientemente de la infraestructura.

---

## 111. Independencia del despliegue

Los recursos de temas forman parte del frontend de la aplicación LUMS.

Los procedimientos generales de despliegue se documentan en las guías principales de instalación y administración.

Este documento no duplica intencionalmente:

* los procedimientos de despliegue de Docker
* los comandos de endurecimiento de contenedores
* la configuración de Nginx
* los procedimientos de copia de seguridad de la base de datos
* la recuperación del servidor
* la instalación de clientes

Esos temas pertenecen a la documentación operativa correspondiente.

Esta separación evita que la documentación de temas quede obsoleta cuando cambia la arquitectura de despliegue.

---

## 112. Separación entre código fuente y runtime

El sistema de temas debe entenderse como parte del código fuente de la aplicación.

Hay que distinguir entre:

```text
Source
   │
   ├── Theme definitions
   ├── CSS
   ├── JavaScript
   └── Assets

Runtime
   │
   ├── Built LUMS image
   └── Running LUMS application
```

Un cambio en el código fuente no significa automáticamente que una instalación ya en ejecución lo haya recibido.

El proceso normal de compilación y despliegue de LUMS es el responsable de entregar los recursos frontend actualizados.

---

## 113. Versionado

Los temas no necesitan introducir una versión separada del backend de LUMS.

Un tema puede evolucionar como parte de la versión del frontend o de la aplicación.

Si un cambio de tema crea problemas de compatibilidad, deben documentarse explícitamente.

Por ejemplo:

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

La segunda categoría requiere pruebas de regresión adicionales.

---

## 114. Preparación de una versión

Antes de una versión de LUMS que incluya cambios de temas, verifica:

```text
Theme rendering
Theme selection
Theme fallback
Accessibility
Reduced motion
Responsive layout
RBAC behavior
API behavior
Security boundaries
Regression tests
Documentation
```

No se debe permitir que los cambios de temas oculten regresiones de la aplicación central.

---

## 115. Conjunto actual de temas

Los conceptos de temas documentados actualmente son:

| Identificador | Nombre visible | Concepto |
| --- | --- | --- |
| `standard` | Standard LUMS | Interfaz de referencia |
| `LUMSStadium` | LUMS Stadium | Estadio / evento |
| `golf` | Golf Club | Sereno / recreativo |
| `nerd` | Nerd Mode | Técnico / lúdico |
| `geek` | Geek Lab | Experimental / técnico |
| `admin` | Enterprise Admin | Estructurado / administrativo |

Estos temas comparten la misma aplicación LUMS y el mismo backend.

Son variantes visuales, no productos independientes ni niveles de permiso.

---

## 116. Estado actual

El sistema opcional de temas es una extensión de la arquitectura frontend de LUMS.

Sus propiedades previstas son:

```text
[✓] Optional
[✓] Client-side presentation
[✓] Common backend
[✓] Common security model
[✓] Common RBAC model
[✓] Standard fallback
[✓] Theme-specific visual identity
[✓] Reduced-motion consideration
[✓] Accessibility consideration
[✓] No theme-based authorization
```

Los detalles específicos de implementación deben mantenerse siempre sincronizados con el código frontend actual.

---

## 117. Ampliaciones futuras

El sistema de temas puede ampliarse de varias maneras sin cambiar la arquitectura subyacente.

Entre las posibles adiciones futuras:

* más temas
* mejores vistas previas de temas
* preferencias visuales más detalladas
* más opciones de accesibilidad
* mejor comportamiento adaptable
* diseños de panel específicos de cada tema
* más visualizaciones opcionales

Estas ampliaciones deben respetar la misma separación entre presentación y comportamiento de la aplicación.

---

## 118. Arquitectura final

El concepto completo se puede resumir así:

```text
                    LUMS
                     │
          ┌──────────┴──────────┐
          │                     │
     Application             Theme Layer
          │                     │
          │             ┌───────┼────────┐
          │             │       │        │
          │          Standard Stadium  Golf
          │
          │             Nerd   Geek   Admin
          │
          └──────────────┬──────────────┘
                         │
                         ▼
                  Common Backend
                         │
             ┌───────────┼───────────┐
             │           │           │
          Security      Jobs       Clients
             │           │           │
             └───────────┼───────────┘
                         ▼
                      SQLite
```

La capa visual sigue siendo opcional.

La capa de aplicación sigue siendo la autoridad.

La capa de seguridad sigue siendo independiente.

---

## 119. Principio final

El sistema opcional de temas existe para hacer LUMS más personal, expresivo y adaptable sin comprometer la arquitectura técnica.

La regla fundamental permanece:

> **Un LUMS · muchas interfaces · el mismo backend**

Un tema puede cambiar la atmósfera de LUMS.

Nunca debe cambiar lo que LUMS tiene realmente permitido hacer.
