# LUMS — Optional Theme System

> **One LUMS · Many Interfaces · Same Backend**

---

## Overview

LUMS provides an optional theme system for its web interface.

Themes change **only the visual presentation** of LUMS.

**Backend, API, database, authentication, and update logic remain unchanged.**

The original LUMS design remains the standard interface.

### Available Themes

| Theme                    | Identifier | Character                 |
| ------------------------ | ---------- | ------------------------- |
| 🖥️ **Standard LUMS**    | `standard` | Original LUMS interface   |
| 🏈 **LUMS Stadium**      | `LUMSStadium`      | Stadium / Game-Day        |
| ⛳ **Golf Club**          | `golf`     | Golf / Club               |
| 🤓 **Nerd Mode**         | `nerd`     | Terminal / CRT            |
| 🧠 **Geek Lab**          | `geek`     | Lab / Cyber / Blueprint   |
| 🗄️ **Enterprise Admin** | `admin`    | Enterprise control center |

The theme selector is available **only on the login page**.

After selecting a theme, the choice is stored in the browser and automatically applied to the other LUMS pages.

---

# Goals

The theme system makes LUMS visually adaptable without changing its technical behavior.

The following principles apply:

* The original LUMS design remains intact.
* Themes are optional visual extensions.
* There is **no theme selector on the dashboard**.
* Theme selection happens only on the login page.
* The selected theme is stored client-side.
* The selected theme is automatically applied to subsequent LUMS pages.
* The backend and database are not modified.
* No additional database structure is required.
* Themes use only HTML, CSS, and JavaScript.
* Visual assets such as images and SVG files are version-controlled together with the frontend.

---

# Architecture

```text
Login Page
    │
    ▼
Theme Selector
    │
    ▼
theme.js
    │
    ▼
localStorage
    │
    ▼
document.documentElement.dataset.theme
    │
    ▼
CSS Theme Rules
    │
    ├── Standard
    ├── LUMS Stadium
    ├── Golf Club
    ├── Nerd Mode
    ├── Geek Lab
    └── Enterprise Admin
```

### Browser Storage

The theme is stored using:

```text
lums-theme
```

Example:

```javascript
localStorage.getItem("lums-theme")
```

Possible result:

```text
"golf"
```

---

# Theme Values

| Theme                | Internal Value | Purpose                                |
| -------------------- | -------------- | -------------------------------------- |
| 🖥️ Standard LUMS    | `standard`     | Original design                        |
| 🏈 LUMS Stadium      | `LUMSStadium`          | Stadium / Game-Day presentation        |
| ⛳ Golf Club          | `golf`         | Golf / Club presentation               |
| 🤓 Nerd Mode         | `nerd`         | Terminal / CRT presentation            |
| 🧠 Geek Lab          | `geek`         | Lab / Cyber / Blueprint presentation   |
| 🗄️ Enterprise Admin | `admin`        | Enterprise control-center presentation |

> **Note:** The internal value `LUMSStadium` is only a technical identifier.
> The user-facing theme name is **LUMS Stadium**.

---

# Login Theme Selector

The selector exists only on the login page.

### Runtime

```text
/opt/lums-api/templates/login.html
```

### Source

```text
/opt/lums-public/server/templates/login.html
```

Example:

```html
<div class="login-theme-selector">
    <label for="login-theme-select">Theme</label>

    <select id="login-theme-select">
        <option value="standard">🖥️ Standard LUMS</option>
        <option value="LUMSStadium">🏈 LUMS Stadium</option>
        <option value="golf">⛳ Golf Club</option>
        <option value="nerd">🤓 Nerd Mode</option>
        <option value="geek">🧠 Geek Lab</option>
        <option value="admin">🗄️ Enterprise Admin</option>
    </select>
</div>
```

The login page loads the central theme script:

```html
<script src="{{ url_for('static', filename='theme.js') }}"></script>
```

---

# Theme JavaScript

### Source

```text
/opt/lums-public/server/static/theme.js
```

### Runtime

```text
/opt/lums-api/static/theme.js
```

The browser storage key is defined as:

```javascript
const STORAGE_KEY = "lums-theme";
```

Supported themes:

```javascript
const THEMES = [
    "standard",
    "LUMSStadium",
    "golf",
    "nerd",
    "geek",
    "admin"
];
```

The selected theme is applied to the HTML root element:

```javascript
document.documentElement.dataset.theme = theme;
```

Example:

```html
<html data-theme="golf">
```

or:

```html
<html data-theme="LUMSStadium">
```

CSS can then target individual themes.

---

# Standard Fallback

If no theme has been saved or an unknown value is found, LUMS automatically falls back to:

```text
standard
```

Example:

```javascript
applyTheme(
    THEMES.includes(savedTheme)
        ? savedTheme
        : "standard"
);
```

This prevents an invalid or corrupted browser state from creating an undefined theme.

---

# Theme Persistence

The selected theme is stored in the browser:

```javascript
localStorage.setItem("lums-theme", "golf");
```

When the LUMS interface is opened again, the stored value is automatically loaded.

The user therefore does not have to select the theme again on every page.

---

# Behavior After Login

```text
1. User opens LUMS
        │
        ▼
2. Login page is displayed
        │
        ▼
3. User selects a theme
        │
        ▼
4. theme.js stores "lums-theme"
        │
        ▼
5. User logs in
        │
        ▼
6. Dashboard is loaded
        │
        ▼
7. theme.js reads localStorage
        │
        ▼
8. data-theme is applied
        │
        ▼
9. CSS activates the selected theme
```

The theme selector itself is **not displayed on the dashboard**.

---

# Dashboard

The dashboard does not contain a theme selector.

The topbar contains only a dynamic theme title element:

```html
<div class="theme-day-title" aria-hidden="true"></div>
```

This element is populated through CSS depending on the selected theme.

For:

* Standard
* Nerd
* Geek
* Enterprise Admin

the element remains empty.

---

# 🏈 LUMS Stadium

The Stadium theme provides a dedicated Game-Day presentation.

## Background

```text
/static/images/lumsstadium.jpg
```

### Source

```text
/opt/lums-public/server/static/images/lumsstadium.jpg
```

### Runtime

```text
/opt/lums-api/static/images/lumsstadium.jpg
```

Example:

```css
html[data-theme="LUMSStadium"] body {
    background:
        #07120b
        url("/static/images/lumsstadium.jpg")
        center top / cover
        fixed
        no-repeat;
}
```

## Game-Day Title

The Stadium theme displays:

```text
GAMEDAY
```

only when:

```text
data-theme="LUMSStadium"
```

## Football Animation

The animation uses the topbar pseudo-element:

```css
.topbar::after
```

Example:

```css
html[data-theme="LUMSStadium"] .topbar::after {
    content: "🏈";
    animation: lums-football-flight 7s linear infinite;
}
```

The football moves across the topbar while changing its position and rotation.

## Reduced Motion

For users who have enabled reduced motion:

```css
@media (prefers-reduced-motion: reduce) {
    html[data-theme="LUMSStadium"] .topbar::after {
        animation: none !important;
        opacity: 0 !important;
    }
}
```

---

# ⛳ Golf Club

The Golf theme provides a relaxed club-style presentation.

## Background

```text
/static/images/golf.jpg
```

### Source

```text
/opt/lums-public/server/static/images/golf.jpg
```

### Runtime

```text
/opt/lums-api/static/images/golf.jpg
```

Example:

```css
html[data-theme="golf"] body {
    background:
        linear-gradient(
            rgba(18, 42, 24, 0.28),
            rgba(18, 42, 24, 0.55)
        ),
        url("/static/images/golf.jpg")
        center top / cover
        fixed
        no-repeat;
}
```

## Club-Day Title

The Golf theme displays:

```text
CLUB DAY
```

only when:

```text
data-theme="golf"
```

## Golf Ball Animation

```css
html[data-theme="golf"] .topbar::after {
    content: "⚪";
    animation: lums-golf-ball-flight 6s linear infinite;
}
```

The ball moves across the topbar while changing height and rotation during its flight.

The animation respects:

```text
prefers-reduced-motion
```

---

# 🤓 Nerd Mode

Nerd Mode is the dedicated **Nerdseite** of LUMS.

It provides a terminal/CRT-inspired visual presentation while keeping the complete LUMS functionality unchanged.

### Typical Visual Elements

* Monospace font
* Terminal styling
* CRT scanlines
* Green accents
* Technical presentation
* Dark interface
* Command-line / console character
* Subtle glow effects
* Reduced classic UI styling

### Nerd Principle

```text
TERMINAL
    │
    ├── SYSTEM
    ├── CLIENTS
    ├── UPDATES
    ├── JOBS
    └── STATUS
```

The Nerd theme is **purely visual**.

It does not create a separate LUMS system.

The following remain unchanged:

* Authentication
* Dashboard
* Client management
* API communication
* Update jobs
* Agent reporting
* Database operations
* Audit logging

> **The Nerdseite changes the interface — not the infrastructure.**

---

# 🧠 Geek Lab

Geek Lab uses a technical laboratory / blueprint visual style.

Typical elements:

* Dark background
* Blue / purple accents
* Grid / blueprint effects
* Technical glow effects
* Laboratory / engineering character

Only CSS presentation is changed.

---

# 🗄️ Enterprise Admin

Enterprise Admin uses a classic light administration interface.

Goals:

* Neutral appearance
* Light background
* Subtle colors
* Control-center character
* High readability

The theme does not change any administrative functionality.

---

# 🖥️ Standard LUMS

The Standard theme is especially important.

It has **no additional theme overrides**.

When:

```text
data-theme="standard"
```

is active, the original LUMS interface remains unchanged.

This allows new themes to be added without replacing the original design.

---

# CSS Structure

### Source

```text
/opt/lums-public/server/static/style.css
```

### Runtime

```text
/opt/lums-api/static/style.css
```

Theme CSS rules use:

```css
html[data-theme="THEME"]
```

Example:

```css
html[data-theme="golf"] body {
    /* Golf Theme */
}
```

This keeps the rules scoped to the selected theme.

---

# Theme-Day Titles

Dynamic theme titles are generated through CSS.

### Golf

```css
html[data-theme="golf"] .theme-day-title::after {
    content: "CLUB DAY";
}
```

### Stadium

```css
html[data-theme="LUMSStadium"] .theme-day-title::after {
    content: "GAMEDAY";
}
```

### Positioning

```css
html[data-theme="LUMSStadium"] .theme-day-title,
html[data-theme="golf"] .theme-day-title {
    position: absolute;
    left: 50%;
    top: 18px;
    transform: translateX(-50%);
}
```

This keeps the title horizontally centered and approximately aligned with the LUMS header.

---

# 🖼️ Images, SVG Assets & GitHub

Theme images, SVG files and other visual frontend assets are part of the LUMS frontend and are therefore version-controlled in Git.

## Raster Images

```text
server/static/images/lumsstadium.jpg
server/static/images/golf.jpg
```

Runtime:

```text
/opt/lums-api/static/images/
```

## SVG Assets

SVG files can be used for:

* Theme-specific graphics
* Logos
* Icons
* Decorative elements
* Interface illustrations
* Background graphics
* Other scalable frontend artwork

Example:

```text
server/static/images/example.svg
```

Runtime:

```text
/opt/lums-api/static/images/example.svg
```

SVG assets required by the frontend should remain part of the version-controlled LUMS project.

## Asset Principle

The repository should contain the complete frontend asset set required to reproduce the documented themes.

```text
HTML
CSS
JavaScript
SVG
JPG
PNG
WebP
```

The runtime server should receive the same required assets from the source repository.

## Git Tracking

Check visual assets:

```bash
cd /opt/lums-public
git status
```

Add a new asset:

```bash
git add server/static/images/example.svg
```

Commit and push:

```bash
git commit -m "Add theme visual asset"
git push
```

This keeps theme implementation and its required visual assets synchronized.

## Attribution

If an image, SVG or other visual asset was generated using an external service or AI system, its origin should be documented where appropriate.

Current LUMS theme attribution:

> **Pictures by leonardo.ai**

---

# Deployment

The project uses two relevant directories.

| Role       | Path               |
| ---------- | ------------------ |
| 📦 Source  | `/opt/lums-public` |
| 🚀 Runtime | `/opt/lums-api`    |

The source directory contains the version-controlled frontend.

The runtime directory contains the files used by Flask.

## Deploy CSS

```bash
sudo cp /opt/lums-public/server/static/style.css /opt/lums-api/static/style.css
```

## Deploy JavaScript

```bash
sudo cp /opt/lums-public/server/static/theme.js /opt/lums-api/static/theme.js
```

## Deploy Templates

```bash
sudo cp /opt/lums-public/server/templates/index.html /opt/lums-api/templates/index.html
sudo cp /opt/lums-public/server/templates/login.html /opt/lums-api/templates/login.html
```

## Deploy Visual Assets

Example:

```bash
sudo cp /opt/lums-public/server/static/images/example.svg /opt/lums-api/static/images/example.svg
```

Preserve the same directory structure between source and runtime.

---

# Restart Flask

After template changes:

```bash
sudo systemctl restart lums.service
```

Service configuration:

```text
ExecStart=/usr/bin/python3 /opt/lums-api/app.py
WorkingDirectory=/opt/lums-api
```

This ensures that Flask uses the current template version.

---

# Browser Cache

After frontend changes:

```text
Ctrl + F5
```

This forces the browser to reload the frontend resources.

---

# Verification

## Stored Theme

```javascript
localStorage.getItem("lums-theme")
```

Example:

```text
"golf"
```

## Currently Applied Theme

```javascript
document.documentElement.dataset.theme
```

Example:

```text
"golf"
```

## Rendered Theme Element

```javascript
document.querySelector(".theme-day-title")?.outerHTML
```

Expected:

```html
<div class="theme-day-title" aria-hidden="true"></div>
```

If the result is:

```text
undefined
```

the currently loaded page does not contain the dynamic theme element.

---

# Detecting an Old GAMEDAY Element

If the browser still displays:

```text
GAMEDAY
```

inspect the actual topbar:

```javascript
document.querySelector("header.topbar")?.innerHTML
```

If the following appears:

```html
<div class="gameday-title">
    GAMEDAY
</div>
```

an older dashboard template is still being served.

### Corrective Sequence

1. Check the deployed template.
2. Restart the LUMS service.
3. Reload the browser using `Ctrl + F5`.

---

# Common Problems

## Golf Theme Displays GAMEDAY

Check:

```javascript
localStorage.getItem("lums-theme")
```

Expected:

```text
"golf"
```

Then:

```javascript
document.documentElement.dataset.theme
```

Expected:

```text
"golf"
```

Then:

```javascript
document.querySelector(".theme-day-title")?.outerHTML
```

If this returns `undefined`, the currently loaded page has not yet received the new template.

---

## Source Template Is Correct but Browser Shows the Old Version

Check:

```bash
grep -n -A2 -B2 'theme-day-title\|gameday-title' /opt/lums-api/templates/index.html
```

The runtime template must contain:

```html
<div class="theme-day-title" aria-hidden="true"></div>
```

Then:

```bash
sudo systemctl restart lums.service
```

Afterwards:

```text
Ctrl + F5
```

---

## CSS Appears Correct but the Display Does Not Change

Check:

```bash
grep -n -A12 -B4 'theme-day-title' /opt/lums-api/static/style.css
```

At minimum:

```css
html[data-theme="LUMSStadium"] .theme-day-title::after {
    content: "GAMEDAY";
}

html[data-theme="golf"] .theme-day-title::after {
    content: "CLUB DAY";
}
```

---

## Theme Is Not Saved

Check:

```javascript
localStorage.getItem("lums-theme")
```

If `null` is returned, no theme has been stored yet.

---

## Unknown Theme Value

Example:

```javascript
localStorage.setItem("lums-theme", "invalid")
```

During the next initialization, LUMS automatically falls back to:

```text
standard
```

---

# Security

The theme system does **not** modify any security-relevant functionality.

The following remain unchanged:

* Flask authentication
* Session management
* CSRF protection
* API authentication
* Agent tokens
* SQLite database
* Password hashing
* Audit logging
* API endpoints
* Update jobs
* Client reporting

The theme system operates entirely on the client side.

The stored theme value is therefore **not a security-sensitive setting**.

A user can change the local theme value at any time using the browser developer tools.

---

# Files

| File                                   | Function                         |
| -------------------------------------- | -------------------------------- |
| `server/templates/login.html`          | Login + theme selector           |
| `server/templates/index.html`          | Dashboard + theme title element  |
| `server/static/theme.js`               | Theme selection and localStorage |
| `server/static/style.css`              | Theme design and animations      |
| `server/static/images/lumsstadium.jpg` | Stadium background               |
| `server/static/images/golf.jpg`        | Golf background                  |
| `server/static/images/*.svg`           | Theme and frontend SVG assets    |

## Deployment Paths

| File              | Runtime Path                                  |
| ----------------- | --------------------------------------------- |
| `login.html`      | `/opt/lums-api/templates/login.html`          |
| `index.html`      | `/opt/lums-api/templates/index.html`          |
| `theme.js`        | `/opt/lums-api/static/theme.js`               |
| `style.css`       | `/opt/lums-api/static/style.css`              |
| `lumsstadium.jpg` | `/opt/lums-api/static/images/lumsstadium.jpg` |
| `golf.jpg`        | `/opt/lums-api/static/images/golf.jpg`        |
| `*.svg`           | `/opt/lums-api/static/images/`                |

---

# Backup / Rollback

Before major frontend changes:

```bash
cp server/static/style.css /tmp/lums-style-backup.css
cp server/templates/index.html /tmp/lums-index-backup.html
cp server/templates/login.html /tmp/lums-login-backup.html
cp server/static/theme.js /tmp/lums-theme-backup.js
```

A rollback affects only the frontend.

The backend, database, and service configuration do not need to be changed for a theme rollback.

---

# Design Principle

```text
┌───────────────────────────────────────┐
│               LUMS                    │
├───────────────────────────────────────┤
│                                       │
│  Standard      Stadium      Golf      │
│  Nerd          Geek Lab     Admin     │
│                                       │
├───────────────────────────────────────┤
│          SAME BACKEND                 │
│          SAME API                     │
│          SAME DATABASE                │
│          SAME SECURITY                │
└───────────────────────────────────────┘
```

> **One LUMS. Many Interfaces. Same Backend.**

The themes are different visual interfaces for the same LUMS system.

The technical functionality remains identical.

LUMS can therefore be presented as:

* Classic and neutral
* Sport-inspired
* Relaxed
* Nerd-oriented
* Technical
* Enterprise-oriented

---

# Current Status

The theme infrastructure is implemented.

### Available

* ✅ Theme selector on the login page
* ✅ Six themes
* ✅ `localStorage` persistence
* ✅ Automatic theme activation
* ✅ No theme selector on the dashboard
* ✅ Standard LUMS remains intact
* ✅ Stadium background
* ✅ Golf background
* ✅ `GAMEDAY`
* ✅ `CLUB DAY`
* ✅ Football animation
* ✅ Golf ball animation
* ✅ Reduced-motion support
* ✅ Theme-specific CSS overlays
* ✅ Separate source and runtime directories
* ✅ Browser-side theme management
* ✅ Theme images included in the Git repository
* ✅ SVG frontend assets supported and version-controlled
* ✅ **Nerd Mode / Nerdseite**
* ✅ Asset attribution documented

The theme selector requires **no additional database structure** and **no backend API**.

---

# Troubleshooting Principle

When dealing with frontend display problems, do not immediately replace files or reinstall LUMS.

Check the layers in order:

```text
1. localStorage
       ↓
2. data-theme
       ↓
3. Loaded HTML
       ↓
4. Deployed CSS
       ↓
5. Deployed JavaScript
       ↓
6. Static visual assets
       ↓
7. Flask process
       ↓
8. Browser cache
```

**Identify the affected layer first, then correct that layer.**

> **Don't reinstall everything immediately. Find the layer where the problem occurs.**

This principle also applies to the LUMS theme system.
