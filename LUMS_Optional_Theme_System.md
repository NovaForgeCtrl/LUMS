# LUMS — Optional Theme System

> **One LUMS · Many Interfaces · Same Backend**

LUMS provides an optional client-side theme system that allows the user interface to change its visual appearance without changing the underlying LUMS functionality.

Themes are a presentation layer only. They do not replace, modify, or bypass the LUMS backend, authentication, authorization, update execution, package management, client management, job handling, or security controls.

The theme system exists to make LUMS adaptable to different visual preferences while keeping the application itself consistent.

---

## 1. Overview

The optional theme system allows the LUMS web interface to provide multiple visual environments while using the same application backend.

A theme may change:

* colors
* typography
* backgrounds
* decorative elements
* visual emphasis
* navigation appearance
* animations
* optional visual effects
* page-specific presentation

A theme must not change:

* user permissions
* available API endpoints
* authentication behavior
* authorization decisions
* CSRF protection
* client authentication
* update execution
* package-management permissions
* job state handling
* audit logging
* database behavior
* security boundaries

The principle is simple:

> **Themes change how LUMS looks, not what LUMS is allowed to do.**

---

## 2. Design Principles

The theme system follows several principles.

### 2.1 Optional

Themes are an optional frontend feature.

LUMS remains fully functional without any additional theme being selected.

The standard LUMS appearance acts as the default presentation.

---

### 2.2 Client-Side

Theme selection belongs to the frontend.

Changing a theme must not require changes to the server-side application state.

A user's selected theme is therefore a presentation preference rather than an account permission or backend configuration.

---

### 2.3 Backend Independence

All themes use the same LUMS backend.

The following remain independent of the selected theme:

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

The backend remains the authoritative source for all security- and operation-sensitive decisions.

---

### 2.4 No Security by Theme

A theme must never be used as a security mechanism.

For example, hiding an action in the interface does not grant or revoke permission.

If an operation is not permitted for a user, the server must reject it regardless of which theme is active.

This ensures that frontend presentation cannot become an authorization boundary.

---

### 2.5 Graceful Fallback

The theme system should always provide a valid fallback.

If:

* no theme has been selected,
* a stored theme is no longer available,
* a theme identifier is invalid,
* a theme asset cannot be loaded,

LUMS should fall back to the standard presentation instead of leaving the interface unusable.

---

## 3. Conceptual Architecture

The theme system can be viewed as a separate presentation layer around the existing LUMS application.

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

The important boundary is between **presentation** and **application logic**.

Themes belong above that boundary.

---

## 4. Theme Lifecycle

Conceptually, selecting a theme follows this sequence:

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

The selection itself does not create a new LUMS environment.

There is still only one LUMS application, one backend, and one security model.

---

## 5. Theme Identifiers

Themes should use stable internal identifiers rather than relying on their display names.

For example:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

The identifier is an implementation detail.

The visible theme name may be changed independently without requiring the backend or application architecture to change.

When a theme identifier is removed or renamed, the theme system should provide a fallback for users who still have the previous identifier stored locally.

---

## 6. Separation of Responsibilities

The theme system has a deliberately narrow responsibility.

### Theme layer

Responsible for:

* visual presentation
* theme selection
* theme-specific styling
* optional visual effects
* theme-specific frontend decorations
* accessibility-related presentation behavior

### Common frontend

Responsible for:

* displaying application data
* calling LUMS APIs
* rendering jobs and software information
* handling user interaction
* enforcing presentation-level visibility

### Backend

Responsible for:

* authentication
* authorization
* RBAC
* CSRF protection
* client authentication
* job creation
* job execution
* package management
* database operations
* audit logging
* security decisions

This separation is fundamental to the design.

---

## 7. Security Boundary

The theme system is **not trusted code for authorization purposes**.

Even if a theme modifies or hides an interface element, the backend remains responsible for validating the requested operation.

Conceptually:

```text
Frontend visibility
        ≠
Backend permission
```

For example:

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

The same principle applies to administrative functions, update jobs, client management, and every other privileged operation.

---

## 8. Operational Principle

The theme system should remain invisible to the operational architecture of LUMS.

A theme change must not require:

* rebuilding the database
* changing client configuration
* changing client tokens
* restarting update agents
* changing update jobs
* modifying RBAC
* changing network configuration
* changing package-management behavior

The theme is a presentation preference, not an operational configuration.

---

## 9. Documentation Scope

This document describes the optional LUMS theme system itself.

General LUMS topics are documented separately:

* Installation and deployment → `installation.md`
* Administration and maintenance → `administration.md`
* Troubleshooting → `troubleshooting.md`
* Security architecture and audits → `security.md`
* General project overview → `README.md`

Keeping these responsibilities separate prevents the theme documentation from becoming a second installation or administration manual.

---

## 10. Core Principle

The optional theme system can therefore be summarized as:

> **One LUMS. One backend. One security model. Many possible**

# LUMS — Optional Theme System

## Part 2 — Theme Structure and Selection

## 11. Theme Structure

The optional theme system separates theme selection from the actual visual presentation.

A theme consists conceptually of three layers:

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

The identifier determines which theme has been selected.

The selection mechanism determines which theme should currently be active.

The presentation layer applies the corresponding visual configuration to the LUMS interface.

This separation makes it possible to add or remove themes without changing the fundamental LUMS application architecture.

---

## 12. Theme Selection

Theme selection is handled by the frontend.

The selected theme is treated as a local presentation preference rather than a server-side account property.

Conceptually:

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

The backend does not need to know which visual theme is currently selected.

This also means that changing the theme does not affect other users.

Two users can access the same LUMS instance while using completely different visual themes.

---

## 13. Local Theme Preference

The selected theme may be persisted locally by the browser.

The purpose of local persistence is convenience:

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

A stored theme selection should therefore be treated as untrusted client-side state.

It must never be interpreted by the server as:

* a role
* a permission
* an authentication state
* a security setting
* an administrative preference

The browser may select the appearance, but it does not control authorization.

---

## 14. Theme Initialization

When the LUMS interface is loaded, the frontend determines which theme should be active.

The conceptual sequence is:

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

If no preference exists, the standard LUMS presentation should be used.

If a stored identifier is no longer supported, the same fallback behavior should apply.

This prevents an outdated local preference from breaking the interface.

---

## 15. Default Theme

The standard LUMS theme is the baseline presentation.

It provides the reference appearance against which optional themes are defined.

The standard theme should therefore remain:

* functional
* readable
* accessible
* visually complete
* independent of optional decorative assets

Optional themes must not become prerequisites for normal LUMS operation.

---

## 16. Theme Application

The frontend can represent the active theme through a shared application state or a root-level theme attribute.

Conceptually:

```html
<html data-theme="theme-id">
```

The exact implementation may differ as the frontend evolves.

The important architectural requirement is that the active theme can be identified consistently by the frontend styling system.

This allows theme-specific styling to remain separated from common application structure.

---

## 17. Theme-Specific Styling

Theme styling should primarily be implemented through CSS rather than duplicating application markup.

Conceptually:

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

This allows the same application components to remain available across themes.

For example, a client table remains a client table regardless of the active theme.

Only its presentation changes.

---

## 18. Shared Application Components

Themes should not create independent versions of LUMS pages.

The following principle should be maintained:

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

Rather than:

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

Duplicating pages would make maintenance significantly harder and could cause behavioral differences between themes.

A theme should therefore decorate the common interface instead of replacing the application itself.

---

## 19. Theme Assets

Themes may use additional frontend assets where appropriate.

Possible assets include:

* background images
* decorative graphics
* icons
* animations
* visual overlays
* theme-specific illustrations

Assets remain part of the frontend presentation layer.

They must not contain:

* credentials
* client tokens
* secret keys
* database files
* authentication material
* private operational data

Theme assets should be treated as public frontend resources.

---

## 20. Optional Visual Effects

Some themes may provide additional visual effects.

Examples include:

* animated backgrounds
* decorative network effects
* ambient motion
* themed interface elements
* dynamic visual decorations

Such effects must remain optional.

They must never be required for the functional operation of LUMS.

---

## 21. Reduced Motion

Visual effects should respect users who prefer reduced motion.

Where animated or continuously changing elements are used, the theme system should provide an appropriate reduced-motion behavior.

Conceptually:

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

Accessibility takes priority over decorative animation.

A theme should remain usable even when visual effects are disabled.

---

## 22. Theme Independence

Changing the theme must not trigger operational side effects.

For example:

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

The theme system is therefore intentionally isolated from the operational lifecycle of LUMS.

---

## 23. Theme Failure Handling

A theme should fail safely.

If a theme-specific asset or presentation component cannot be loaded, the common LUMS interface should remain usable.

The preferred recovery path is:

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

A visual problem must not become an application availability problem.

---

## 24. Adding a New Theme

A new theme should follow the existing separation between application behavior and presentation.

Conceptually:

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

A new theme is complete only when the existing LUMS functionality remains unchanged.

---

## 25. Removing a Theme

Removing a theme should also be handled gracefully.

If an existing user has a removed theme stored locally, the frontend should detect that the identifier is no longer available and fall back to the standard theme.

The removal of a visual theme must therefore not make a user's LUMS interface unusable.

---

## 26. Theme Naming

Theme names should clearly distinguish between:

* internal identifier
* display name
* visual concept

For example:

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

This separation allows the visible wording to evolve without unnecessarily changing the internal implementation.

---

## 27. Current Theme Concept

The optional LUMS theme system is designed around multiple visual identities while maintaining a common application.

The current documented theme concepts include:

| Identifier    | Concept          |
| ------------- | ---------------- |
| `standard`    | Standard LUMS    |
| `LUMSStadium` | LUMS Stadium     |
| `golf`        | Golf Club        |
| `nerd`        | Nerd Mode        |
| `geek`        | Geek Lab         |
| `admin`       | Enterprise Admin |

These themes represent different visual directions rather than different LUMS editions.

All remain part of the same application.

---

## 28. One Backend, Many Interfaces

The final relationship can be summarized as:

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

The theme layer ends at the presentation boundary.

Everything below that boundary remains common to all themes.

# LUMS — Optional Theme System

## Part 3 — Theme Concepts

## 29. Standard LUMS

The Standard LUMS theme is the reference presentation for the application.

Its purpose is to provide a clean and functional interface without requiring a specific visual concept.

The standard theme should prioritize:

* readability
* clear information hierarchy
* predictable navigation
* accessibility
* low visual distraction
* consistent component presentation

It is the fallback presentation for the theme system.

The Standard LUMS theme should therefore remain usable even if all optional visual themes are unavailable.

---

## 30. LUMS Stadium

**LUMS Stadium** is a more expressive visual interpretation of the LUMS interface.

The concept combines system administration with a stadium-inspired visual identity.

Possible design elements include:

* scoreboard-inspired information panels
* stronger visual status indicators
* event-oriented presentation
* themed backgrounds
* visual emphasis for operational states
* decorative stadium elements

The theme remains functionally identical to Standard LUMS.

A successful update is still a successful update.

A failed job is still a failed job.

Only the presentation changes.

---

## 31. Golf Club

The **Golf Club** theme provides a deliberately contrasting visual identity.

Instead of a traditional server or infrastructure aesthetic, the interface uses a calmer recreational concept.

The visual direction may emphasize:

* clean surfaces
* restrained decoration
* golf-inspired elements
* course-like visual metaphors
* calm status presentation
* light thematic accents

The concept demonstrates that LUMS does not need to visually resemble a traditional administration console to remain functional.

The backend and application behavior remain unchanged.

---

## 32. Nerd Mode

**Nerd Mode** is aimed at a more technical and playful presentation.

The concept can emphasize the technical nature of LUMS through elements such as:

* terminal-inspired styling
* technical terminology
* system-oriented visual elements
* developer-style presentation
* diagnostic aesthetics
* deliberately technical decoration

The theme must still maintain clear information hierarchy.

A playful interface should not make operational information harder to understand.

---

## 33. Geek Lab

**Geek Lab** represents a more experimental technical environment.

The visual concept can combine:

* laboratory aesthetics
* technical experimentation
* infrastructure visualization
* system diagrams
* scientific or engineering-inspired elements
* experimental visual effects

The theme is intended to make the interface feel like an infrastructure laboratory while preserving the same LUMS functionality underneath.

The visual experimentation must remain isolated from the operational application.

---

## 34. Enterprise Admin

The **Enterprise Admin** theme represents a more conservative administrative interface.

Its visual direction can emphasize:

* structured information
* compact layouts
* administrative dashboards
* clear status indicators
* operational density
* reduced decorative elements

This theme is particularly suitable for users who prefer a conventional administration-console appearance.

It does not introduce additional administrative privileges.

The name describes the visual concept, not an authorization level.

---

## 35. Theme Comparison

The themes can be viewed as different visual interpretations of the same application:

| Theme            | Visual Direction            | Primary Character   |
| ---------------- | --------------------------- | ------------------- |
| Standard LUMS    | Clean / functional          | Reference interface |
| LUMS Stadium     | Stadium / event             | Expressive          |
| Golf Club        | Recreational / calm         | Relaxed             |
| Nerd Mode        | Technical / playful         | Developer-oriented  |
| Geek Lab         | Experimental / technical    | Laboratory          |
| Enterprise Admin | Structured / administrative | Conservative        |

This table describes presentation concepts only.

It does **not** describe differences in:

* permissions
* features
* API access
* client access
* job execution
* package management
* security

---

## 36. Same Interface, Different Presentation

A central design goal is that the same application component should remain recognizable across themes.

For example:

```text id="5dhlf7"
Client List
   │
   ├── Standard presentation
   ├── Stadium presentation
   ├── Golf presentation
   ├── Nerd presentation
   ├── Geek presentation
   └── Enterprise presentation
```

The underlying client data remains identical.

Only its presentation changes.

The same applies to:

* software inventories
* available updates
* update jobs
* job history
* user information
* system status
* package-management interfaces

---

## 37. Operational Statuses

Themes may visually emphasize different operational states.

For example:

```text id="5wyy17"
PENDING
RUNNING
SUCCESS
FAILED
```

A theme may use different visual representations for these states, but the semantic meaning must remain consistent.

The theme must not redefine application states.

For example:

```text id="j4i9qd"
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

The visual representation is only a rendering of the backend state.

---

## 38. Error Presentation

Themes may also change how errors are presented visually.

However, error information must remain understandable.

A theme should not:

* hide important error information
* replace technical information with decorative text
* make warnings indistinguishable from normal states
* suppress operational failures

Visual styling can improve presentation, but it must not remove diagnostic information required to understand a problem.

---

## 39. Status Consistency

The same status should have a consistent semantic meaning across every theme.

For example:

| State   | Meaning                   |
| ------- | ------------------------- |
| Pending | Waiting for execution     |
| Running | Currently being processed |
| Success | Completed successfully    |
| Failed  | Execution failed          |

A theme may represent these states using different colors, icons, typography, or layout.

The underlying meaning must remain unchanged.

---

## 40. Theme-Specific Decoration

Decorative elements should remain secondary to operational information.

Examples include:

* backgrounds
* patterns
* illustrations
* ambient effects
* themed icons
* visual ornaments

The following priority should be maintained:

```text id="3m08d7"
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

Decoration must never take priority over information required to operate LUMS.

---

## 41. Visual Density

Different themes may use different visual densities.

For example:

* Enterprise Admin may prioritize information density.
* Standard LUMS may prioritize balanced readability.
* Golf Club may use more whitespace.
* Nerd Mode may use compact technical elements.
* Stadium may emphasize large status areas.
* Geek Lab may provide more visual context.

These differences remain presentation choices.

They do not change the amount or authority of the underlying data.

---

## 42. Accessibility Across Themes

Every theme must preserve basic usability.

This includes:

* readable text
* sufficient visual distinction
* usable controls
* understandable status indicators
* keyboard accessibility
* usable focus states
* compatibility with reduced-motion preferences

Color should not be the only mechanism used to communicate an important state.

For example, a failed job should not be identifiable only because it is displayed in a particular color.

---

## 43. Theme-Specific Animations

Themes may contain animations where they improve the visual concept.

Examples include:

* subtle transitions
* animated backgrounds
* network effects
* status transitions
* ambient decoration

Animations should remain secondary to the application.

They should not:

* prevent interaction
* obscure controls
* continuously distract from operational data
* interfere with accessibility
* affect backend operations

---

## 44. The Living Network

Some LUMS themes may use a dynamic network-inspired visual layer.

The concept represents LUMS as a living infrastructure environment:

```text id="7w1v8b"
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

Such a visualization is decorative unless explicitly connected to actual application data.

A visual network should therefore never be interpreted as authoritative network topology unless the application explicitly provides that information.

This distinction is important:

> **A visual representation is not automatically operational telemetry.**

---

## 45. Decorative Data vs. Real Data

Theme-specific visual effects must clearly remain separate from real LUMS data.

For example:

```text id="z6i5j0"
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

This prevents users from confusing an aesthetic visualization with actual system information.

---

## 46. Theme Identity

Each theme should have a recognizable identity without becoming a separate product.

The goal is:

```text id="qv1fbe"
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

This keeps the theme system playful and flexible while preserving the technical integrity of the application.

---

## 47. Theme Design Rule

The most important design rule for all themes is:

> **A theme may be expressive, unusual, technical, playful, or conservative — but it must always remain LUMS.**

The application must remain recognizable as the same system regardless of the selected visual presentation.

# LUMS — Optional Theme System

## Part 4 — Frontend Implementation and Accessibility

## 48. Frontend Theme Layer

The optional theme system belongs entirely to the LUMS frontend.

Its responsibility is limited to presentation and user preference handling.

Conceptually:

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

The theme layer does not replace the common frontend logic.

Instead, it provides an additional presentation layer around it.

---

## 49. Theme Initialization

Theme initialization should happen as part of the normal frontend startup process.

The conceptual sequence is:

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

Initialization should be lightweight and must not depend on backend availability.

A user should be able to load the visual presentation even if an API request later fails.

---

## 50. Theme State

The active theme is frontend state.

It should therefore be treated differently from application state.

### Theme state

Examples:

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### Application state

Examples:

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

Theme state must never overwrite or impersonate application state.

---

## 51. Root Theme Attribute

A root-level attribute is a suitable conceptual representation of the active theme.

For example:

```html
<html data-theme="standard">
```

or:

```html
<html data-theme="nerd">
```

CSS can then use the active theme as a selector.

The exact implementation may evolve, but the architectural goal remains the same:

> **One application structure, multiple presentation definitions.**

---

## 52. CSS Organization

Theme-specific styling should remain distinguishable from common LUMS styling.

Conceptually:

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

Common styles should define the functional structure.

Theme styles should define the visual identity.

This reduces duplication and makes future theme maintenance easier.

---

## 53. CSS Variables

Theme systems can use CSS custom properties to separate semantic values from their visual representation.

For example:

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

A theme can then provide its own values:

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

The important principle is that components consume semantic variables instead of hard-coding theme-specific values wherever practical.

---

## 54. Shared Components

The theme system should style shared components rather than duplicate them.

Typical components include:

* navigation
* buttons
* forms
* tables
* status indicators
* cards
* dialogs
* package-management elements
* update-job elements
* client information
* system information

The same component should remain functionally identical regardless of the active theme.

---

## 55. Theme Assets

Optional themes may use dedicated assets.

Possible asset categories include:

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Theme assets should remain frontend resources.

They must not contain sensitive application information.

In particular, theme assets must never contain:

* passwords
* secret keys
* client tokens
* database contents
* private certificates
* authentication material

---

## 56. Asset Loading

Theme assets should be loaded only when they are required.

A theme should not unnecessarily increase the cost of every LUMS page simply because the theme exists.

Where practical:

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

rather than:

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

This becomes increasingly important as additional themes and visual effects are added.

---

## 57. Theme Performance

Visual customization must not significantly degrade the usability of LUMS.

Particular attention should be paid to:

* large background images
* continuously animated elements
* canvas effects
* repeated DOM updates
* expensive visual filters
* unnecessary network requests

Operational pages such as client lists, software inventories, and update-job views should remain responsive.

---

## 58. Decorative JavaScript

A theme may use JavaScript for visual effects.

Examples include:

* animated backgrounds
* network visualizations
* dynamic decorations
* theme-specific interactions

Such JavaScript should remain isolated from operational application logic.

A decorative script should never be responsible for:

* authorization
* job creation
* package installation
* package removal
* update execution
* client authentication
* audit logging

The distinction should remain clear:

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Network Visualization

If a theme uses a network-style visualization, it should be treated as a presentation component.

For example:

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

Unless explicitly connected to authoritative LUMS data, the visualization should not imply that it represents the actual network state.

This prevents decorative graphics from being mistaken for monitoring or telemetry.

---

## 60. Reduced Motion

Themes that use animation should support reduced-motion preferences.

The preferred behavior is conceptually:

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

Essential functionality must remain unchanged.

Reduced motion should affect presentation only.

---

## 61. Focus and Keyboard Navigation

Theme styling must preserve keyboard usability.

Important interactive elements should retain visible focus states.

Themes should not remove focus outlines without providing an equally clear alternative.

For example:

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

This applies to:

* navigation
* buttons
* links
* form fields
* selectors
* dialogs
* package-management controls

---

## 62. Color Independence

Important information must not rely solely on color.

For example:

```text
FAILED
```

should remain understandable through text, iconography, structure, or another accessible indication even if the theme's colors are unavailable.

This is particularly important because themes may use very different color palettes.

---

## 63. Contrast

Every theme should maintain sufficient contrast between:

* text and backgrounds
* controls and backgrounds
* status indicators and surrounding elements
* focused elements and their surroundings

A visually interesting palette is not a substitute for readable information.

When theme colors conflict with accessibility requirements, readability takes priority.

---

## 64. Theme Selection UI

The theme selector itself is part of the common LUMS interface.

It should remain understandable regardless of the currently active theme.

Conceptually:

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

Selecting another theme should update the presentation without changing the current LUMS session or operational state.

---

## 65. Session Independence

Changing the theme must not log the user out.

It must not:

* invalidate the session
* change the role
* rotate client tokens
* modify server-side authentication state

The theme preference is separate from authentication.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. RBAC Independence

Themes must remain independent of RBAC.

For example:

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

The selected theme does not alter these permissions.

A Viewer using Enterprise Admin does not become an administrator.

An Administrator using Nerd Mode does not lose administrative privileges.

The backend remains authoritative in every case.

---

## 67. Error Isolation

A failure in optional visual functionality should not break core LUMS operation.

For example, if a decorative animation fails:

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

Where possible, visual features should fail independently from application functionality.

This is especially important for optional effects such as animated backgrounds or network visualizations.

---

## 68. Browser Compatibility

The theme system should use browser features supported by the browsers targeted by the LUMS deployment environment.

When a visual feature is unavailable, the interface should degrade gracefully rather than becoming unusable.

The standard presentation should remain the baseline fallback.

---

## 69. Implementation Principle

The implementation can be summarized as:

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

The following must remain outside the theme layer:

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

This separation keeps the theme system powerful enough to be expressive while preventing it from becoming coupled to core LUMS behavior.

# LUMS — Optional Theme System

## Part 5 — Security, Testing and Development

## 70. Security Boundary

The theme system is part of the frontend and therefore operates within an untrusted client environment.

The browser controls the presentation layer.

The browser does **not** control LUMS authorization.

The security boundary remains:

```text id="h8e2ks"
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

All security-sensitive decisions must therefore remain server-side.

---

## 71. Theme Selection Is Not Authorization

A selected theme must never be interpreted as an authorization signal.

For example:

```text id="8u3r8v"
data-theme="admin"
```

does not mean that the current user is an administrator.

The word `admin` in a theme identifier is purely descriptive.

The user's actual role must always come from the authenticated application session and server-side authorization logic.

---

## 72. Frontend Visibility Is Not Security

A theme or frontend script may hide an interface element.

This is useful for presentation.

It is not sufficient for access control.

For example:

```text id="7m8c6w"
Hidden button
      ≠
Unauthorized operation prevented
```

The corresponding API endpoint must independently validate the user's permissions.

This applies to all privileged LUMS functionality.

---

## 73. Theme Assets Are Public

Frontend assets should be considered publicly accessible to anyone who can access the LUMS web interface.

Consequently, theme files must never contain secrets.

Never place the following into theme assets:

```text id="1zjz7n"
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

If information must remain confidential, it does not belong in a theme asset.

---

## 74. No Backend Secrets in Themes

Theme JavaScript must not contain server credentials or privileged API material.

A theme should communicate with the existing frontend application layer where necessary.

It must not introduce an alternative authentication mechanism.

The following principle applies:

> **Themes consume presentation data; they do not create security credentials.**

---

## 75. Cross-Site Request Forgery

Theme functionality must not bypass existing CSRF protection.

If a theme provides an interface element that triggers an operation requiring a protected request, the request must follow the same security requirements as the common LUMS interface.

The theme does not receive an exemption because it is visual code.

---

## 76. API Usage

A theme should avoid directly implementing its own operational API logic.

Where application data is required, the theme should use the established LUMS frontend/application mechanisms.

This prevents multiple independent implementations of:

* authentication
* API requests
* error handling
* authorization assumptions
* job handling

The common application logic remains the authoritative frontend integration layer.

---

## 77. Theme Isolation

A theme should be removable without removing core LUMS functionality.

Conceptually:

```text id="3m1o8q"
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

This makes optional themes genuinely optional.

---

## 78. Security Testing

Security testing should focus on proving that theme changes do not alter the LUMS security model.

Relevant checks include:

* Viewer remains a Viewer
* Operator remains an Operator
* Administrator remains an Administrator
* protected API endpoints remain protected
* CSRF protection remains active
* client authentication remains unchanged
* update-job permissions remain unchanged
* package-management permissions remain unchanged
* audit logging remains unchanged

The theme itself should never be used as evidence that an operation is secure.

---

## 79. Functional Theme Testing

Each theme should be tested against the common application.

At minimum:

```text id="9w6h1m"
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

The exact available functions depend on the authenticated user's role.

The purpose of the test is to ensure that theme rendering does not break normal application functionality.

---

## 80. RBAC Theme Testing

Theme testing should include all relevant roles.

A basic matrix is:

| Role          | Theme Testing |
| ------------- | ------------- |
| Administrator | Required      |
| Operator      | Required      |
| Viewer        | Required      |

For each role, verify that changing the theme does not change the permitted functionality.

For example:

```text id="3n5p2m"
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

The visual theme must not alter the result.

---

## 81. Theme Switching Tests

Theme switching should be tested repeatedly.

Example sequence:

```text id="gk2j7m"
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

The application should remain usable throughout the sequence.

Particular attention should be paid to:

* layout changes
* tables
* navigation
* dialogs
* forms
* status indicators
* long text
* responsive behavior

---

## 82. Persistence Testing

If the theme preference is persisted locally, test:

1. Select a theme.
2. Reload the page.
3. Confirm the theme remains selected.
4. Close the browser.
5. Open LUMS again.
6. Confirm the preference is still handled correctly.
7. Remove or invalidate the stored theme.
8. Confirm fallback to the standard theme.

The stored value should never be trusted as application security state.

---

## 83. Invalid Theme Testing

An invalid theme identifier should not break the interface.

For example:

```text id="4j5cqn"
unknown-theme
```

should result in a safe fallback rather than an unusable page.

The desired behavior is:

```text id="5x9h2f"
Invalid theme
     │
     ▼
Standard theme
     │
     ▼
LUMS remains usable
```

---

## 84. Asset Failure Testing

Optional assets should also be tested for failure.

Examples:

* missing image
* unavailable animation
* invalid asset path
* unsupported visual feature
* JavaScript error in optional decoration

The common application should remain usable whenever possible.

---

## 85. Reduced-Motion Testing

For themes containing animation, test both normal and reduced-motion environments.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Important application controls must remain fully functional in both cases.

---

## 86. Responsive Testing

Themes should be tested at different viewport sizes.

At minimum:

* desktop
* tablet-sized viewport
* narrow/mobile-sized viewport

The visual identity should not come at the expense of usable controls or readable application data.

Particular attention should be given to:

* navigation
* tables
* action buttons
* package-management controls
* job status information
* dialogs
* theme selectors

---

## 87. Performance Testing

Visual effects should be evaluated for their impact on browser performance.

Relevant observations include:

* page load time
* rendering responsiveness
* CPU usage
* memory usage
* animation smoothness
* repeated DOM updates
* network requests

Themes should remain presentation enhancements rather than becoming a performance bottleneck.

---

## 88. Development Workflow

A new theme should be developed independently from backend changes whenever possible.

Recommended workflow:

```text id="1i8qz6"
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

Backend changes should only be introduced when there is a genuine application requirement.

A visual theme should normally not require backend modifications.

---

## 89. Development Rules

When developing a theme:

1. Reuse existing LUMS components.
2. Avoid duplicating pages.
3. Keep theme-specific styling isolated.
4. Keep decorative JavaScript separate from operational logic.
5. Do not introduce authentication logic.
6. Do not introduce authorization logic.
7. Do not expose secrets.
8. Preserve accessibility.
9. Preserve reduced-motion behavior.
10. Test all relevant roles.
11. Test the standard fallback.
12. Document new assets and behavior.

---

## 90. Change Verification

Before considering a theme change complete, verify both presentation and functionality.

A useful validation sequence is:

```text id="i1v9yb"
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

A theme is not complete merely because it looks correct.

It must also leave LUMS behavior unchanged.

---

## 91. Regression Principle

Theme development should follow the same general project principle as other LUMS changes:

> **Change → Test → Verify → Document**

A visual change can still cause functional regressions.

Examples include:

* hidden buttons
* unreadable text
* broken layout
* inaccessible controls
* JavaScript conflicts
* missing assets
* incorrect selectors
* mobile layout failures

Testing is therefore part of theme development rather than an optional final step.

---

## 92. Troubleshooting: Theme Does Not Load

If the selected theme does not appear:

1. Reload the page.
2. Check whether the standard theme loads.
3. Check the browser console.
4. Check whether the selected theme identifier is valid.
5. Check whether required theme assets are available.
6. Check for JavaScript errors.
7. Clear the local theme preference if necessary.
8. Reload and verify the standard fallback.

Do not modify backend security configuration to solve a frontend theme problem.

---

## 93. Troubleshooting: Theme Breaks Layout

If a theme causes layout problems:

1. Switch to the Standard LUMS theme.
2. Confirm that the common interface works.
3. Identify the affected component.
4. Inspect theme-specific CSS.
5. Check responsive behavior.
6. Check browser console errors.
7. Correct the theme-specific styling.
8. Retest other themes.

The standard theme provides an important diagnostic comparison.

---

## 94. Troubleshooting: Theme Causes JavaScript Errors

If theme-specific JavaScript causes errors:

1. Switch to the standard theme.
2. Confirm normal LUMS functionality.
3. Identify the failing theme script.
4. Determine whether the error is decorative or application-related.
5. Remove the theme-specific failure.
6. Verify that common LUMS JavaScript remains unaffected.
7. Retest theme switching.

Operational JavaScript should not be modified merely to compensate for a decorative theme error.

---

## 95. Troubleshooting: Theme Preference Is Invalid

If an old or invalid theme remains stored locally:

```text id="b9n8wq"
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

The preferred solution is safe fallback rather than manual backend intervention.

---

## 96. Theme Documentation

Every new theme should document:

* internal identifier
* display name
* visual concept
* required assets
* optional visual effects
* accessibility considerations
* reduced-motion behavior
* known limitations

Implementation-specific documentation should describe the actual current code rather than assumptions about how the theme might work.

---

## 97. Current Theme Set

The documented theme concepts are currently:

```text id="r0w4u5"
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

The theme set is extensible.

Additional themes may be added without changing the underlying LUMS architecture, provided that the separation between presentation and application behavior remains intact.

---

## 98. Development Principle

The optional theme system should remain a controlled frontend extension.

Its purpose is to make LUMS more expressive and adaptable without making the application more complicated operationally.

The preferred architecture is therefore:

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

The common application remains the foundation.

Themes remain optional extensions.

# LUMS — Optional Theme System

## Part 6 — Maintenance, Extension and Final Status

## 99. Theme Maintenance

Theme maintenance should remain separate from core LUMS maintenance wherever possible.

A visual theme update should normally involve only frontend resources.

Typical changes include:

* CSS adjustments
* visual assets
* theme-specific JavaScript
* accessibility improvements
* responsive-layout corrections
* animation adjustments
* theme naming or presentation changes

A theme update should not require changes to:

* client configuration
* client tokens
* database schema
* update jobs
* package-management logic
* authentication
* RBAC
* server-side security controls

If a theme change unexpectedly requires such modifications, the dependency should be reviewed before proceeding.

---

## 100. Theme Updates

Theme updates should follow the normal LUMS development process:

```text id="2p7z9r"
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

For larger changes:

```text id="p7l5me"
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

A theme should not be considered complete solely because the visual result looks correct.

---

## 101. Adding a New Theme

A new theme can be introduced without changing the LUMS backend.

Recommended process:

### Step 1 — Define the concept

Describe:

* visual identity
* target style
* typography
* colors
* decorative elements
* optional animations

### Step 2 — Define the identifier

Choose a stable internal identifier.

### Step 3 — Implement presentation

Add the required styling and assets.

### Step 4 — Integrate selection

Make the theme available through the common theme selector.

### Step 5 — Test

Verify:

* normal pages
* interactive controls
* responsive layouts
* accessibility
* reduced motion
* all relevant RBAC roles
* fallback behavior

### Step 6 — Document

Record the theme and its relevant implementation details.

---

## 102. Removing a Theme

Removing a theme should be treated as a compatibility change for users who may still have the theme selected locally.

The frontend should therefore handle an obsolete identifier safely.

Preferred behavior:

```text id="x4e7p1"
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

Removing a theme should never require a database migration merely to remove a browser-side preference.

---

## 103. Renaming a Theme

A display name can normally change independently from the internal identifier.

For example:

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

If the internal identifier itself changes, a migration or compatibility mapping may be required for existing local preferences.

The preferred approach is to keep identifiers stable whenever practical.

---

## 104. Theme Compatibility

Themes should remain compatible with common LUMS UI changes.

When a new shared component is introduced, existing themes should be checked for:

* missing styling
* broken spacing
* unreadable text
* incorrect colors
* missing responsive behavior
* incorrect focus states
* inaccessible controls

A new backend feature does not automatically require a new theme feature.

The common application remains the source of truth.

---

## 105. New LUMS Features

When LUMS gains a new feature, theme support should normally be evaluated after the common feature is functional.

Recommended sequence:

```text id="z4b7jx"
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

This prevents visual customization from becoming a dependency of core feature development.

---

## 106. Theme API Stability

The theme system should avoid creating a separate API layer unless there is a genuine requirement.

Themes should preferably consume the same frontend application state and API mechanisms already used by LUMS.

This reduces:

* duplicated request logic
* duplicated error handling
* inconsistent authorization assumptions
* additional maintenance
* unnecessary attack surface

The theme system is therefore intentionally lightweight.

---

## 107. Theme Security Review

When adding or significantly changing a theme, review the following:

```text id="3eq4w6"
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

This review should be performed even when the change appears to be purely visual.

Frontend code is still executable code.

---

## 108. Theme Accessibility Review

For every theme, verify:

```text id="1y9xw6"
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

Accessibility should be treated as part of theme quality rather than an optional enhancement.

---

## 109. Theme Regression Checklist

Before accepting a theme change:

```text id="8j6x4e"
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

The exact feature set visible during the test depends on the user's role.

---

## 110. Operational Independence

The optional theme system is intentionally independent of the LUMS operational lifecycle.

Changing a theme must not require:

```text id="b2i1k4"
Agent restart
Watcher restart
Database restart
Client re-registration
Token rotation
Job cancellation
Package-manager changes
Network changes
```

This allows the presentation layer to evolve independently from the infrastructure layer.

---

## 111. Deployment Independence

Theme resources are part of the LUMS application frontend.

General deployment procedures remain documented in the main installation and administration documentation.

This document intentionally does not duplicate:

* Docker deployment procedures
* container hardening commands
* Nginx configuration
* database backup procedures
* server recovery procedures
* client installation procedures

Those topics belong to the appropriate operational documentation.

This separation prevents theme documentation from becoming outdated when deployment architecture changes.

---

## 112. Source and Runtime Separation

The theme system should be understood as part of the application source.

There is a distinction between:

```text id="b6q7jv"
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

A theme change in source code does not automatically mean that an already running deployment has received that change.

The normal LUMS build and deployment process remains responsible for delivering updated frontend resources.

---

## 113. Versioning

Themes do not need to introduce a separate LUMS backend version.

A theme may evolve as part of the frontend/application version.

If a theme change introduces compatibility concerns, those concerns should be documented explicitly.

For example:

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

The second category requires additional regression testing.

---

## 114. Release Readiness

Before a LUMS release containing theme changes, verify:

```text id="v2h3f7"
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

Theme changes must not be allowed to hide regressions in the core application.

---

## 115. Current Theme Set

The current documented theme concepts are:

| Identifier    | Display Name     | Concept                     |
| ------------- | ---------------- | --------------------------- |
| `standard`    | Standard LUMS    | Reference interface         |
| `LUMSStadium` | LUMS Stadium     | Stadium / event             |
| `golf`        | Golf Club        | Calm / recreational         |
| `nerd`        | Nerd Mode        | Technical / playful         |
| `geek`        | Geek Lab         | Experimental / technical    |
| `admin`       | Enterprise Admin | Structured / administrative |

These themes share the same LUMS application and backend.

They are visual variants, not separate products or permission levels.

---

## 116. Current Status

The optional theme system is an extension of the LUMS frontend architecture.

Its intended properties are:

```text id="2xq1w8"
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

Implementation-specific details should always be kept synchronized with the current frontend source.

---

## 117. Future Extensions

The theme system can be extended in several directions without changing the underlying architecture.

Possible future additions include:

* additional themes
* improved theme previews
* more granular visual preferences
* additional accessibility settings
* improved responsive behavior
* theme-specific dashboard layouts
* additional optional visualizations

Such extensions should continue to respect the same separation between presentation and application behavior.

---

## 118. Final Architecture

The complete concept can be summarized as:

```text id="x8j7z2"
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

The visual layer remains optional.

The application layer remains authoritative.

The security layer remains independent.

---

## 119. Final Principle

The optional theme system exists to make LUMS more personal, expressive, and adaptable without compromising the technical architecture.

The fundamental rule remains:

> **One LUMS · Many Interfaces · Same Backend**

A theme may change the atmosphere of LUMS.

It must never change what LUMS actually is allowed to do.
