# LUMS — Optional Theme System

> **One LUMS · Many Interfaces · Same Backend**

> **Linux Update Management without the noise.**

---

## Overview

LUMS provides an optional client-side theme system for its web interface.

Themes change only the visual presentation of LUMS.

The following components remain unchanged:

* Backend
* API
* Database
* Authentication
* Agent communication
* Update jobs
* Audit logging
* Client management
* Security mechanisms

The original LUMS design remains the `standard` interface.

The theme system does not create separate LUMS installations. All themes operate on the same application, the same backend and the same persistent database.

```text
ONE LUMS
   │
   ├── Standard LUMS
   ├── LUMS Stadium
   ├── Golf Club
   ├── Nerd Mode
   ├── Geek Lab
   └── Enterprise Admin
   │
   ▼
SAME BACKEND
SAME API
SAME DATABASE
SAME SECURITY
```

---

# 1. Available Themes

| Theme                | Identifier    | Character                         |
| -------------------- | ------------- | --------------------------------- |
| 🖥️ Standard LUMS    | `standard`    | Original LUMS interface           |
| 🏈 LUMS Stadium      | `LUMSStadium` | Stadium / Game-Day                |
| ⛳ Golf Club          | `golf`        | Golf / Club                       |
| 🤓 Nerd Mode         | `nerd`        | Terminal / CRT / Matrix           |
| 🧠 Geek Lab          | `geek`        | Cyber / Network / Laboratory      |
| 🗄️ Enterprise Admin | `admin`       | Dry Enterprise Operations Console |

The identifier `admin` is the internal technical value for the **Enterprise Admin** theme.

The user-facing theme name remains:

```text
Enterprise Admin
```

---

# 2. Design Principles

The theme system follows these principles:

* Standard LUMS remains the default design.
* Themes are optional visual extensions.
* Theme selection is stored client-side.
* Themes do not require additional database structures.
* Themes do not communicate theme information to the backend.
* Theme-specific CSS is scoped through `data-theme`.
* Theme-specific JavaScript is limited to presentation.
* Frontend assets are version-controlled with the project.
* Security-relevant functionality must not depend on the selected theme.
* Changing a theme must never modify LUMS data.
* Themes must not modify API authorization or authentication logic.

The architecture intentionally separates:

```text
Application functionality
        │
        ├── Backend
        ├── API
        ├── Database
        ├── Authentication
        ├── Agents
        └── Update Jobs

from

Presentation
        │
        ├── CSS
        ├── Theme JavaScript
        ├── Visual effects
        └── Theme assets
```

---

# 3. Current Architecture

The current LUMS installation uses Docker for the application and Nginx as the TLS reverse proxy.

```text
Browser
   │
   │ HTTPS :443
   ▼
Nginx
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   │ Docker port mapping
   ▼
LUMS Container
   │
   │ Flask :5000
   ▼
LUMS Application
   │
   ▼
Docker Volume
lums-data
```

## Current Application Values

| Component           | Value                       |
| ------------------- | --------------------------- |
| Repository          | `/opt/lums-public`          |
| Docker image        | `lums:latest`               |
| Docker container    | `lums`                      |
| Docker volume       | `lums-data`                 |
| Internal Flask port | `5000`                      |
| Host binding        | `127.0.0.1:5050`            |
| External HTTPS      | Nginx on port `443`         |
| Environment file    | `/etc/lums/docker/lums.env` |

The container is published using:

```text
127.0.0.1:5050 → 5000/tcp
```

Port `5000` is internal to the container.

Port `5050` is bound only to localhost.

Neither port should be directly exposed to the network.

---

# 4. Theme Architecture

The theme system is implemented entirely on the client side.

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
Theme-specific CSS / JavaScript
    │
    ├── Standard
    ├── LUMS Stadium
    ├── Golf Club
    ├── Nerd Mode
    ├── Geek Lab
    └── Enterprise Admin
```

The currently selected theme is represented on the root HTML element.

Example:

```html
<html data-theme="geek">
```

The CSS then scopes theme-specific rules:

```css
html[data-theme="geek"] ...
```

This prevents one theme from unintentionally changing another theme.

---

# 5. Browser Storage

The theme storage key is:

```javascript
const STORAGE_KEY = "lums-theme";
```

Example:

```javascript
localStorage.getItem("lums-theme");
```

Possible result:

```text
"geek"
```

The stored value is local to the browser.

The backend does not need to know which theme the user selected.

---

# 6. Supported Theme Values

The current `theme.js` contains:

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

The `admin` identifier represents:

```text
Enterprise Admin
```

The theme value is applied through:

```javascript
document.documentElement.dataset.theme = theme;
```

Example:

```html
<html data-theme="admin">
```

---

# 7. Standard Fallback

If no theme has been stored or an unknown value is detected, LUMS falls back to:

```text
standard
```

The fallback prevents invalid browser state from producing an undefined interface.

Example:

```javascript
applyTheme(
    THEMES.includes(savedTheme)
        ? savedTheme
        : "standard"
);
```

The `standard` theme therefore remains the default when:

* no theme has been selected,
* `localStorage` is empty,
* an invalid theme value is stored,
* or theme initialization falls back to the default.

---

# 8. Theme JavaScript

## Source

```text
/opt/lums-public/server/static/theme.js
```

The theme JavaScript is included in the Docker image during the build process.

It is responsible for:

* Reading the saved theme.
* Validating the theme.
* Applying the fallback.
* Updating `data-theme`.
* Saving the selected theme.
* Synchronizing available theme selectors.
* Starting and stopping theme-specific visual effects.

The theme system must not:

* modify the SQLite database,
* modify authentication,
* modify client tokens,
* modify API authorization,
* modify update jobs,
* modify agent communication,
* send theme data to the backend.

---

# 9. Theme Selection

The theme selector is available through the LUMS frontend theme selection mechanism.

The login selector uses:

```html
<select id="login-theme-select">
```

The theme JavaScript also supports:

```html
<select id="theme-select">
```

when such a selector is present on a page.

Both selectors are synchronized by `theme.js`.

The selected value is written to:

```text
localStorage
```

and then applied through:

```javascript
document.documentElement.dataset.theme
```

---

# 10. Theme-Day Titles

Some themes can provide additional presentation elements through CSS.

The relevant dashboard element is:

```html
<div class="theme-day-title" aria-hidden="true"></div>
```

Examples:

```css
html[data-theme="LUMSStadium"] .theme-day-title::after {
    content: "GAMEDAY";
}

html[data-theme="golf"] .theme-day-title::after {
    content: "CLUB DAY";
}
```

These elements are purely visual.

They do not affect:

* backend functionality,
* authentication,
* client management,
* update jobs,
* database operations,
* API requests.

Themes that do not require a theme-day title leave the element visually empty.

---

# 11. LUMS Stadium

The Stadium theme provides a Game-Day visual presentation.

Typical elements include:

* stadium background,
* sports-inspired colors,
* Game-Day title,
* football animation,
* reduced-motion handling.

## Background

Example asset:

```text
server/static/images/lumsstadium.jpg
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

```css
html[data-theme="LUMSStadium"] .theme-day-title::after {
    content: "GAMEDAY";
}
```

## Football Animation

```css
html[data-theme="LUMSStadium"] .topbar::after {
    content: "🏈";
}
```

The animation is presentation-only.

Reduced-motion settings must be respected.

---

# 12. Golf Club

The Golf theme provides a relaxed club-style presentation.

Typical elements include:

* golf background,
* club-style presentation,
* `CLUB DAY`,
* golf-ball animation,
* reduced-motion handling.

## Background

Example asset:

```text
server/static/images/golf.jpg
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

```css
html[data-theme="golf"] .theme-day-title::after {
    content: "CLUB DAY";
}
```

## Golf Animation

The golf-ball animation is purely visual and must respect:

```text
prefers-reduced-motion
```

---

# 13. Nerd Mode

Nerd Mode is the dedicated terminal/CRT-inspired interface.

Typical visual elements include:

* monospace fonts,
* terminal-inspired styling,
* dark interface,
* green accents,
* CRT effects,
* Matrix-style rain,
* technical presentation.

The Matrix layer is created by `theme.js` and styled through CSS.

The visual layer is only activated when:

```text
data-theme="nerd"
```

The Nerd theme does not modify LUMS functionality.

> **The Nerdseite changes the interface — not the infrastructure.**

---

# 14. Geek Lab

Geek Lab represents the technical laboratory / cyber-oriented interface.

Typical visual elements include:

* dark interface,
* technical blue/purple accents,
* blueprint-inspired presentation,
* grid effects,
* laboratory styling,
* technical visual effects.

The Geek theme also contains the **The Living Network** background animation.

---

# 15. The Living Network

**The Living Network** is the animated network background of the Geek theme.

It is implemented separately from the normal theme CSS.

## JavaScript Source

```text
/opt/lums-public/server/static/network.js
```

The script exposes:

```javascript
window.LumsNetwork = {
    start,
    stop,
    destroy
};
```

The animation consists of:

* slowly moving network nodes,
* connections between nearby nodes,
* animated blue network packets,
* a fixed fullscreen canvas,
* transparent background,
* application content above the network.

The network canvas is:

```html
<canvas id="lums-network-canvas"></canvas>
```

The CSS restricts it to the Geek theme:

```css
html[data-theme="geek"] #lums-network-canvas {
    display: block;
}

html:not([data-theme="geek"]) #lums-network-canvas {
    display: none;
}
```

The network animation is started by `theme.js` only when:

```javascript
theme === "geek"
```

For every other theme:

```javascript
window.LumsNetwork.stop();
```

Therefore:

```text
Geek
  │
  └── The Living Network → ACTIVE

Enterprise Admin
  │
  └── The Living Network → OFF

Standard
  │
  └── The Living Network → OFF

LUMS Stadium
  │
  └── The Living Network → OFF

Golf
  │
  └── The Living Network → OFF

Nerd
  │
  └── The Living Network → OFF
```

## Reduced Motion

The network canvas is disabled when the browser requests reduced motion:

```css
@media (prefers-reduced-motion: reduce) {
    #lums-network-canvas {
        display: none !important;
    }
}
```

The Geek network therefore remains a visual enhancement only.

---

# 16. Enterprise Admin

Enterprise Admin is intentionally designed as a **dry Enterprise Operations Console**.

The objective is not to create another modern SaaS dashboard.

The visual character is:

> **Infrastructure Management Console**

or:

> **Enterprise software that exists to manage infrastructure, not to impress marketing departments.**

😂

## Design Goals

Enterprise Admin uses:

* light gray background,
* white panels,
* dark blue/gray header,
* classic blue accent color,
* thin borders,
* compact spacing,
* small corner radius,
* dense information presentation,
* conventional tables,
* restrained status indicators,
* minimal shadows,
* no decorative gradients,
* no neon effects,
* no glow,
* no unnecessary animation.

The theme deliberately avoids:

* glassmorphism,
* oversized cards,
* marketing-style layouts,
* large decorative icons,
* neon effects,
* animated backgrounds,
* cyber effects,
* unnecessary visual motion.

---

# 17. Enterprise Admin Identifier

The internal identifier remains:

```text
admin
```

The user-facing name is:

```text
Enterprise Admin
```

This distinction is intentional.

The existing theme architecture therefore continues to use:

```html
<html data-theme="admin">
```

Enterprise-specific CSS is scoped using:

```css
html[data-theme="admin"] ...
```

---

# 18. Enterprise Admin CSS Architecture

Enterprise Admin is implemented as a dedicated CSS override layer at the end of:

```text
server/static/style.css
```

The section is clearly marked:

```css
/* =========================================================
   LUMS // ENTERPRISE ADMIN
   Operations Console
   ========================================================= */
```

This approach avoids rewriting the complete LUMS stylesheet.

Existing styles remain available as the base layer.

Enterprise-specific rules override only the visual presentation when:

```text
data-theme="admin"
```

is active.

---

# 19. Enterprise Admin Visual Language

## Background

```text
Light gray
```

## Panels

```text
White
1px border
Small radius
Minimal shadow
```

## Header

```text
Dark blue/gray
White text
Thin bottom border
```

## Accent

```text
Classic administrative blue
```

## Tables

Enterprise tables use:

* compact rows,
* clear borders,
* neutral header background,
* restrained hover states,
* small uppercase column headings where appropriate.

The goal is information density rather than visual decoration.

---

# 20. Enterprise Admin Status Display

Status indicators remain simple and readable.

Typical presentation:

```text
● Online
● Offline
● Unknown
```

The status presentation must not change the underlying status logic.

The theme only changes how the status is displayed.

---

# 21. Enterprise Admin Controls

Buttons and form controls use a conventional administrative design.

Typical characteristics:

* rectangular controls,
* small radius,
* blue primary buttons,
* thin borders,
* white input fields,
* compact controls,
* no glow,
* no animated hover effects.

The underlying actions remain unchanged.

A button that performs an update job remains the same update-job action regardless of the selected theme.

---

# 22. Enterprise Admin Client View

The client page follows the same administrative visual language.

Affected visual areas include:

* client header,
* client IP information,
* status,
* statistics,
* system information,
* update tables,
* update jobs,
* update history,
* software/package tables.

The Enterprise Admin theme does not modify the underlying client data.

---

# 23. Enterprise Admin Software View

The software/package section uses a compact administrative layout.

Visual characteristics include:

* thin table borders,
* compact rows,
* neutral tab styling,
* classic blue active state,
* white content areas,
* restrained controls.

The package information itself is unchanged.

---

# 24. Enterprise Admin and Other Themes

Enterprise Admin must remain isolated from the other themes.

The following themes must not inherit Enterprise-specific visual changes:

```text
standard
LUMSStadium
golf
nerd
geek
```

Enterprise CSS therefore uses scoped selectors such as:

```css
html[data-theme="admin"] .panel
```

rather than global rules such as:

```css
.panel
```

This is an important architectural rule.

> **Enterprise Admin changes Enterprise Admin only.**

---

# 25. Theme Isolation

Each visual effect must be restricted to its intended theme.

Examples:

```css
html[data-theme="nerd"] ...
```

```css
html[data-theme="geek"] ...
```

```css
html[data-theme="admin"] ...
```

The Living Network specifically uses:

```css
html[data-theme="geek"] #lums-network-canvas
```

and is hidden for all other themes.

This prevents visual effects from leaking between themes.

---

# 26. Frontend Assets

Theme assets are part of the version-controlled frontend.

Supported formats may include:

```text
HTML
CSS
JavaScript
SVG
JPG
PNG
WebP
```

## Source Directory

```text
/opt/lums-public/server/static/
```

Example assets:

```text
server/static/images/lumsstadium.jpg
server/static/images/golf.jpg
server/static/images/*.svg
server/static/network.js
```

The Docker build copies the server source into the application image.

Theme assets therefore become part of the resulting Docker image.

---

# 27. Asset Attribution

If external or AI-generated assets are used, their origin should be documented where appropriate.

Existing theme attribution:

> **Pictures by leonardo.ai**

Only assets that are legally usable and appropriate for the project should be committed.

Theme assets must not introduce:

* tracking,
* analytics,
* external scripts,
* unexpected network requests,
* malicious active content.

---

# 28. Git Asset Management

Check the repository:

```bash
cd /opt/lums-public

git status
```

Check frontend assets:

```bash
git status --short server/static/
```

Review changes:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

Commit only intended changes:

```bash
git add server/static/
git add server/templates/
git commit -m "Update LUMS theme system"
```

Push:

```bash
git push origin main
```

Use the configured LUMS Git identity:

```text
Name:  xxxxx
Email: xxxxx
```

Never commit:

* passwords,
* API tokens,
* private keys,
* environment files,
* database files,
* session secrets,
* personal data.

---

# 29. Current Docker Deployment

The LUMS application runs inside Docker.

The source repository is:

```text
/opt/lums-public
```

The Docker image is:

```text
lums:latest
```

The running container is:

```text
lums
```

The persistent database is stored in:

```text
lums-data
```

The runtime application is not updated simply by modifying files inside the running container.

Frontend changes must therefore be:

```text
Source
  ↓
Docker build
  ↓
New image
  ↓
Container recreation
```

---

# 30. Important Source/Runtime Separation

The current architecture separates:

```text
Git source
    ≠
Docker image
    ≠
Running container
    ≠
Persistent database volume
    ≠
Secret configuration
```

| Component                 | Location                    |
| ------------------------- | --------------------------- |
| Git source                | `/opt/lums-public`          |
| Docker image              | `lums:latest`               |
| Running container         | `lums`                      |
| Persistent database       | Docker volume `lums-data`   |
| Environment configuration | `/etc/lums/docker/lums.env` |
| Nginx TLS configuration   | `/etc/nginx/`               |

The repository contains source code and frontend assets.

Runtime state and secrets remain outside the Git repository.

---

# 31. Safe Frontend Deployment

Before deployment:

```bash
cd /opt/lums-public

git status
git diff
git diff --check
```

Build the new image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Inspect the image:

```bash
sudo docker image inspect \
    lums:latest
```

Building the image does not automatically update the running container.

The running container must be recreated.

---

# 32. SQLite-Aware Backup

Before recreating the production container, create a database backup.

Create the backup directory:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

Create a SQLite-aware backup:

```bash
sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/lums.db.backup")

with target:
    source.backup(target)

target.close()
source.close()

print("SQLite backup completed")
'
```

Protect the backup:

```bash
sudo chmod 600 \
    /var/backups/lums/lums.db.backup
```

The backup must not be committed to Git.

---

# 33. Recreate the Docker Container

Confirm the persistent volume:

```bash
sudo docker volume inspect \
    lums-data
```

Stop the existing container:

```bash
sudo docker stop \
    lums
```

Remove only the container:

```bash
sudo docker rm \
    lums
```

Recreate the container:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

The important persistent component is:

```text
-v lums-data:/var/lib/lums
```

The Docker volume must not be removed during a normal frontend deployment.

---

# 34. Container Verification

Check the container:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Check the logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Check the local application:

```bash
curl -i \
    http://127.0.0.1:5050/
```

A redirect to `/login` can be an expected result.

---

# 35. Nginx and HTTPS Verification

Test the Nginx configuration:

```bash
sudo nginx -t
```

Only after a successful configuration test:

```bash
sudo systemctl reload nginx
```

Test HTTPS:

```bash
curl -k -i \
    https://127.0.0.1/
```

Check listening ports:

```bash
sudo ss -lntp | grep -E ':443|:5050|:5000'
```

Expected architecture:

```text
443     Nginx HTTPS
5050    Docker localhost binding
5000    Flask inside Docker
```

The theme system must not require direct exposure of ports `5000` or `5050`.

---

# 36. Browser Cache

After frontend deployment:

```text
Ctrl + F5
```

If the old theme remains visible:

1. Confirm the Docker image was rebuilt.
2. Confirm the container was recreated.
3. Check Docker logs.
4. Test the local application.
5. Reload the browser.
6. Inspect the loaded CSS and JavaScript.

Do not immediately delete the database or reinstall LUMS.

---

# 37. Browser Verification

Open the browser developer console.

## Stored Theme

```javascript
localStorage.getItem("lums-theme");
```

## Currently Applied Theme

```javascript
document.documentElement.dataset.theme;
```

Example:

```text
admin
```

means:

```text
Enterprise Admin
```

## Theme Element

```javascript
document.querySelector(".theme-day-title")?.outerHTML;
```

## Current Dashboard

```javascript
document.querySelector("header.topbar")?.innerHTML;
```

These checks help distinguish between:

* browser state,
* loaded HTML,
* theme state,
* CSS state,
* deployed application state.

---

# 38. Enterprise Admin Verification

When Enterprise Admin is selected:

```javascript
document.documentElement.dataset.theme
```

should return:

```text
admin
```

The interface should show:

* light gray background,
* white panels,
* dark blue/gray header,
* classic blue controls,
* thin borders,
* compact tables,
* minimal shadows,
* small corner radii,
* no Geek network animation,
* no Matrix rain,
* no neon effects.

The Enterprise theme should feel like:

```text
Operations Console
```

rather than:

```text
Modern SaaS Dashboard
```

---

# 39. Geek Verification

When Geek is selected:

```javascript
document.documentElement.dataset.theme
```

should return:

```text
geek
```

The Living Network should be active.

The canvas should exist:

```javascript
document.getElementById("lums-network-canvas");
```

Enterprise-specific styling must not appear.

The Geek theme remains independent from Enterprise Admin.

---

# 40. Theme Isolation Test

Test all themes after major frontend changes:

```text
Standard
LUMS Stadium
Golf Club
Nerd Mode
Geek Lab
Enterprise Admin
```

The important rule is:

> Changing Enterprise Admin must not change the appearance or functionality of any other theme.

Likewise:

> Adding a Geek visual effect must not activate that effect in Enterprise Admin.

---

# 41. Common Problems

## Theme Is Not Saved

Check:

```javascript
localStorage.getItem("lums-theme");
```

If the result is:

```text
null
```

no theme has been stored.

---

## Unknown Theme Value

Example:

```javascript
localStorage.setItem("lums-theme", "invalid");
```

The next initialization should fall back to:

```text
standard
```

---

## Enterprise Admin Does Not Look Different

Check:

```javascript
document.documentElement.dataset.theme;
```

Expected:

```text
admin
```

Then check the deployed CSS inside the container:

```bash
sudo docker exec \
    lums \
    grep -n -A10 -B4 \
    'LUMS // ENTERPRISE ADMIN' \
    /app/server/static/style.css
```

If the path differs, inspect the container:

```bash
sudo docker exec \
    lums \
    find /app -maxdepth 4 \
    -type f \
    \( -name "style.css" -o -name "theme.js" \)
```

---

## Enterprise Shows Geek Network Animation

Check:

```javascript
document.documentElement.dataset.theme;
```

The network animation should only be active for:

```text
geek
```

Check that:

```html
html[data-theme="geek"]
```

is the only theme selector enabling the network canvas.

---

## Geek Does Not Show The Living Network

Check:

```javascript
document.getElementById("lums-network-canvas");
```

Check:

```javascript
window.LumsNetwork
```

The network script should be present in:

```text
server/static/network.js
```

Check the deployed container:

```bash
sudo docker exec \
    lums \
    ls -l /app/server/static/network.js
```

---

## Old Theme Still Appears

Use:

```text
Ctrl + F5
```

Then verify:

```javascript
localStorage.getItem("lums-theme");
```

and:

```javascript
document.documentElement.dataset.theme;
```

If the source is correct but the browser still displays an old interface:

```text
1. Check Git source.
2. Rebuild Docker image.
3. Recreate container.
4. Check container logs.
5. Test localhost.
6. Reload browser.
```

---

# 42. Security

The theme system is client-side and does not modify security-relevant functionality.

The following remain unchanged:

* Flask authentication.
* Session management.
* CSRF protection.
* API authentication.
* Agent tokens.
* SQLite database.
* Password hashing.
* Audit logging.
* API endpoints.
* Update jobs.
* Client reporting.

The stored theme value is not a security-sensitive setting.

A user can change their own local theme value through browser developer tools.

That does not grant additional permissions.

Theme assets must still be reviewed for:

* external tracking,
* analytics,
* untrusted scripts,
* embedded active content,
* unexpected network requests,
* copyright/licensing issues.

Theme JavaScript must not bypass or disable security controls.

---

# 43. Backup and Rollback

Before major frontend changes:

```bash
cd /opt/lums-public

git status
git diff
git diff --check
```

Create a SQLite-aware backup before rebuilding or recreating the production container.

A frontend rollback consists of:

```text
1. Restore the required Git version.
2. Review the changes.
3. Build the Docker image.
4. Recreate the container.
5. Test the application.
6. Refresh the browser.
```

A theme rollback must not require:

* database deletion,
* database migration,
* token replacement,
* TLS replacement,
* authentication changes.

> **The ****`lums-data`**** volume must be preserved during frontend rollback.**

---

# 44. Source and Runtime Separation

The current architecture uses:

```text
Git source
    ≠
Docker image
    ≠
Running container
    ≠
Persistent database volume
    ≠
Secret configuration
```

| Component            | Location                    |
| -------------------- | --------------------------- |
| Git source           | `/opt/lums-public`          |
| Docker image         | `lums:latest`               |
| Running container    | `lums`                      |
| Persistent database  | Docker volume `lums-data`   |
| Secret configuration | `/etc/lums/docker/lums.env` |
| Nginx configuration  | `/etc/nginx/`               |

This separation prevents frontend deployment from accidentally replacing persistent application data.

---

# 45. Files

| File                                   | Function                            |
| -------------------------------------- | ----------------------------------- |
| `server/templates/login.html`          | Login interface and theme selection |
| `server/templates/index.html`          | Main dashboard                      |
| `server/templates/client.html`         | Client detail interface             |
| `server/static/theme.js`               | Theme selection and theme state     |
| `server/static/style.css`              | Base and theme-specific styling     |
| `server/static/network.js`             | Geek / The Living Network animation |
| `server/static/images/lumsstadium.jpg` | Stadium background                  |
| `server/static/images/golf.jpg`        | Golf background                     |
| `server/static/images/*.svg`           | Theme/frontend graphics             |

All required frontend files must be included in the Docker image.

---

# 46. Current Status

Current theme functionality:

* [x] Theme selector.
* [x] Six themes.
* [x] `localStorage` persistence.
* [x] Automatic theme activation.
* [x] Standard fallback.
* [x] Standard LUMS.
* [x] LUMS Stadium.
* [x] Golf Club.
* [x] Nerd Mode.
* [x] Matrix visual layer.
* [x] Geek Lab.
* [x] The Living Network.
* [x] Reduced-motion handling.
* [x] Enterprise Admin.
* [x] Enterprise Operations Console styling.
* [x] Theme isolation.
* [x] Theme-specific CSS.
* [x] Theme-specific JavaScript.
* [x] Git-controlled frontend assets.
* [x] Docker-based deployment.
* [x] Persistent Docker volume.
* [x] SQLite-aware backup procedure.

---

# 47. Troubleshooting Order

When a theme problem occurs, inspect the layers in this order:

```text
1. localStorage
       ↓
2. data-theme
       ↓
3. Loaded HTML
       ↓
4. Git source
       ↓
5. Docker image
       ↓
6. Running container
       ↓
7. CSS
       ↓
8. JavaScript
       ↓
9. Static assets
       ↓
10. Nginx
       ↓
11. Browser cache
```

Identify the affected layer before making changes.

Do not immediately:

* delete the Docker volume,
* reinstall LUMS,
* expose port `5000`,
* expose port `5050`,
* modify the database,
* replace production configuration blindly.

---

# 48. Final Principle

```text
ONE LUMS
MANY INTERFACES
SAME BACKEND
SAME API
SAME DATABASE
SAME SECURITY
```

The theme system changes the visual experience without creating a separate LUMS installation.

**Geek can be alive.**

**Nerd can be chaotic.**

**Stadium can be Game-Day.**

**Golf can be Club Day.**

**Enterprise Admin can be deliberately boring.**

But underneath all of them:

```text
ONE LUMS
```

> **Linux Update Management without the noise.**
