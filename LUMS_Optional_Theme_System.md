
# LUMS — Optional Theme System

> **One LUMS · Many Interfaces · Same Backend**

> **Linux Update Management without the noise.**

---

## Overview

LUMS provides an optional client-side theme system for its web interface.

Themes change only the visual presentation of LUMS:

- Backend
- API
- Database
- Authentication
- Agent communication
- Update jobs
- Audit logging

remain unchanged.

The original LUMS design remains the standard interface.

## Available Themes

| Theme | Identifier | Character |
|---|---|---|
| 🖥️ Standard LUMS | `standard` | Original interface |
| 🏈 LUMS Stadium | `LUMSStadium` | Stadium / Game-Day |
| ⛳ Golf Club | `golf` | Golf / Club |
| 🤓 Nerd Mode | `nerd` | Terminal / CRT |
| 🧠 Geek Lab | `geek` | Lab / Cyber / Blueprint |
| 🗄️ Enterprise Admin | `admin` | Enterprise control center |

The theme selector is available **only on the login page**.

The selected theme is stored in the browser using `localStorage` and automatically applied to subsequent LUMS pages.

---

# 1. Design Principles

The theme system follows these principles:

- Standard LUMS remains the default design.
- Themes are optional visual extensions.
- Theme selection is available only on the login page.
- The dashboard does not contain a theme selector.
- Theme selection is stored client-side.
- The backend and database are not modified.
- No additional database structure is required.
- Themes use HTML, CSS and JavaScript.
- Frontend assets are version-controlled with the project.
- Theme changes must not alter security-relevant functionality.

```text
ONE LUMS
   │
   ├── Standard
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

# 2. Current Architecture

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

| Component | Value |
|---|---|
| Repository | `/opt/lums-public` |
| Docker image | `lums:latest` |
| Docker container | `lums` |
| Docker volume | `lums-data` |
| Internal Flask port | `5000` |
| Host binding | `127.0.0.1:5050` |
| External HTTPS | Nginx on port `443` |
| Environment file | `/etc/lums/docker/lums.env` |

The container is published using:

```text
127.0.0.1:5050 → 5000/tcp
```

Port `5000` is not directly exposed to the network.

---

# 3. Theme Architecture

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
Theme CSS
    │
    ├── Standard
    ├── LUMS Stadium
    ├── Golf Club
    ├── Nerd Mode
    ├── Geek Lab
    └── Enterprise Admin
```

## Browser Storage

The storage key is:

```javascript
const STORAGE_KEY = "lums-theme";
```

Example:

```javascript
localStorage.getItem("lums-theme");
```

Possible result:

```text
"golf"
```

## Supported Values

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

---

# 4. Standard Fallback

If no theme has been stored or an unknown value is detected, LUMS falls back to:

```text
standard
```

This prevents invalid browser state from creating an undefined theme.

The fallback should be implemented in `theme.js`.

Example:

```javascript
const theme = THEMES.includes(savedTheme)
    ? savedTheme
    : "standard";
```

The `standard` theme must remain the default when:

- No theme has been selected.
- `localStorage` is empty.
- An invalid theme value is stored.
- The browser blocks access to local storage.
- Theme initialization fails.

---

# 5. Login Theme Selector

The selector exists only on the login page.

## Source

```text
/opt/lums-public/server/templates/login.html
```

The login template must be included in the Docker image during deployment.

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

The central theme script is loaded through Flask:

```html
<script src="{{ url_for('static', filename='theme.js') }}"></script>
```

The selector must not be added to the dashboard.

---

# 6. Dashboard Theme Element

The dashboard does not contain a theme selector.

It may contain a dynamic title element:

```html
<div class="theme-day-title" aria-hidden="true"></div>
```

The element is used for theme-specific presentation.

For the following themes, it remains empty:

- Standard
- Nerd
- Geek Lab
- Enterprise Admin

Theme-specific titles:

| Theme | Title |
|---|---|
| `LUMSStadium` | `GAMEDAY` |
| `golf` | `CLUB DAY` |

The title is generated through CSS and does not affect backend functionality.

---

# 7. Theme JavaScript

## Source

```text
/opt/lums-public/server/static/theme.js
```

The file is included in the Docker image during the build process.

The JavaScript is responsible for:

- Reading the saved theme.
- Validating the theme value.
- Applying the fallback.
- Updating `data-theme`.
- Saving user selections.
- Synchronizing the login selector.

The theme system must not:

- Send theme data to the backend.
- Modify the SQLite database.
- Modify authentication.
- Modify API requests.
- Modify client tokens.
- Modify update jobs.

---

# 8. Theme CSS

## Source

```text
/opt/lums-public/server/static/style.css
```

Theme-specific rules should be scoped through the HTML root element.

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

The Standard theme should not require additional overrides.

Theme-specific CSS must not change:

- API URLs.
- Form actions.
- Authentication behavior.
- JavaScript security checks.
- Client-side authorization logic.
- Update-management functionality.

---

# 9. LUMS Stadium

The Stadium theme provides a Game-Day visual presentation.

## Background

```text
server/static/images/lumsstadium.jpg
```

The asset is included in the Docker image and served through Flask.

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
    animation: lums-football-flight 7s linear infinite;
}
```

The animation is visual only.

## Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
    html[data-theme="LUMSStadium"] .topbar::after {
        animation: none !important;
        opacity: 0 !important;
    }
}
```

---

# 10. Golf Club

The Golf theme provides a relaxed club-style presentation.

## Background

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

```css
html[data-theme="golf"] .topbar::after {
    content: "⚪";
    animation: lums-golf-ball-flight 6s linear infinite;
}
```

The animation must respect:

```text
prefers-reduced-motion
```

---

# 11. Nerd Mode

Nerd Mode is the dedicated Nerdseite of LUMS.

Typical visual elements:

- Monospace fonts.
- Terminal-inspired styling.
- CRT scanlines.
- Green accents.
- Dark interface.
- Technical presentation.
- Subtle glow effects.
- Console-inspired design.

The Nerd theme remains purely visual.

The following remain unchanged:

- Authentication.
- Dashboard functionality.
- Client management.
- API communication.
- Update jobs.
- Agent reporting.
- Database operations.
- Audit logging.

> **The Nerdseite changes the interface — not the infrastructure.**

---

# 12. Geek Lab

Geek Lab uses a technical laboratory and blueprint-inspired visual style.

Typical elements:

- Dark background.
- Blue and purple accents.
- Grid effects.
- Blueprint styling.
- Technical glow effects.
- Laboratory and engineering presentation.

Only the visual presentation is changed.

---

# 13. Enterprise Admin

Enterprise Admin uses a classic light administration interface.

Design goals:

- Neutral appearance.
- Light background.
- Subtle colors.
- High readability.
- Enterprise control-center character.

The theme does not change administrative functionality or permissions.

---

# 14. Theme-Day Titles

Theme titles are generated through CSS.

```css
html[data-theme="LUMSStadium"] .theme-day-title::after {
    content: "GAMEDAY";
}

html[data-theme="golf"] .theme-day-title::after {
    content: "CLUB DAY";
}
```

Example positioning:

```css
html[data-theme="LUMSStadium"] .theme-day-title,
html[data-theme="golf"] .theme-day-title {
    position: absolute;
    left: 50%;
    top: 18px;
    transform: translateX(-50%);
}
```

The title element must exist in the currently deployed dashboard template.

---

# 15. Frontend Assets

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
server/static/images/example.svg
```

The Docker build must include the required static files.

The runtime application serves these assets from its internal Flask static directory.

## Attribution

If an image or graphic was created using an external service or AI system, its origin should be documented where appropriate.

Current theme attribution:

> **Pictures by leonardo.ai**

Only assets that are legally usable and appropriate for the project should be committed.

---

# 16. Git Asset Management

Check the repository:

```bash
cd /opt/lums-public

git status
```

Check theme assets:

```bash
git status --short server/static/images/
```

Add a new asset:

```bash
git add server/static/images/example.svg
```

Review the staged changes:

```bash
git diff --cached --check
```

Commit:

```bash
git commit -m "Add theme visual asset"
```

Push:

```bash
git push origin main
```

Use the configured LUMS Git identity:

```text
Name:  NovaForgeCtrl
Email: 232026481+NovaForgeCtrl@users.noreply.github.com
```

Never commit:

- Passwords.
- API tokens.
- Private keys.
- Environment files.
- Database files.
- Session secrets.
- Personal data.

---

# 17. Current Docker Deployment

The current LUMS application runs in Docker.

The source directory is:

```text
/opt/lums-public
```

The Docker image is:

```text
lums:latest
```

The runtime application is not updated by copying files into `/opt/lums-api`.

Frontend changes must be included in a newly built Docker image.

## Deployment Sequence

```text
Git repository
      ↓
Review changes
      ↓
Syntax and whitespace checks
      ↓
SQLite-aware backup
      ↓
Build Docker image
      ↓
Recreate container
      ↓
Test local application
      ↓
Test HTTPS through Nginx
      ↓
Browser refresh
```

---

# 18. Safe Frontend Deployment

Check the repository:

```bash
cd /opt/lums-public

git status
```

Review changes:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

Build the image:

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

Before recreating the container, create a database backup.

> **Important:** Building a Docker image does not automatically update the running container.

---

# 19. SQLite-Aware Backup Before Deployment

Create the backup directory:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

Create a backup using the Docker volume:

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

The backup should be verified before major changes.

---

# 20. Recreate the Docker Container

Confirm that the persistent volume exists:

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

Recreate the container using the existing volume:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Check the container:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Check logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Test the local application:

```bash
curl -i \
    http://127.0.0.1:5050/
```

A redirect to `/login` can be an expected result.

> **Never remove the `lums-data` volume during a normal frontend deployment.**

---

# 21. Nginx and HTTPS Verification

Test the Nginx configuration:

```bash
sudo nginx -t
```

Reload Nginx only after a successful test:

```bash
sudo systemctl reload nginx
```

Test HTTPS locally:

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

# 22. Browser Cache

After frontend deployment:

```text
Ctrl + F5
```

If the old design remains visible:

1. Confirm the Docker image was rebuilt.
2. Confirm the container was recreated.
3. Check Docker logs.
4. Test the local application.
5. Reload the browser.
6. Inspect the loaded CSS and JavaScript.

Do not immediately delete the database or reinstall LUMS.

---

# 23. Browser Verification

Open the browser developer console.

## Stored Theme

```javascript
localStorage.getItem("lums-theme");
```

## Currently Applied Theme

```javascript
document.documentElement.dataset.theme;
```

## Theme Element

```javascript
document.querySelector(".theme-day-title")?.outerHTML;
```

Expected result:

```html
<div class="theme-day-title" aria-hidden="true"></div>
```

If the result is:

```text
undefined
```

the currently loaded page does not contain the element.

## Current Dashboard HTML

```javascript
document.querySelector("header.topbar")?.innerHTML;
```

This helps identify whether an old dashboard template is being served.

---

# 24. Common Problems

## Theme Is Not Saved

Check:

```javascript
localStorage.getItem("lums-theme");
```

If the result is `null`, no theme has been stored.

Check whether the browser allows local storage.

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

## Golf Shows GAMEDAY

Check the stored theme:

```javascript
localStorage.getItem("lums-theme");
```

Check the applied theme:

```javascript
document.documentElement.dataset.theme;
```

Check the dashboard element:

```javascript
document.querySelector(".theme-day-title")?.outerHTML;
```

Then inspect the deployed CSS inside the Docker container:

```bash
sudo docker exec \
    lums \
    grep -n -A12 -B4 \
    'theme-day-title' \
    /app/static/style.css
```

If the application uses another internal static path, inspect the container configuration first.

---

## Old GAMEDAY Element Is Visible

Inspect the actual topbar:

```javascript
document.querySelector("header.topbar")?.innerHTML;
```

If this appears:

```html
<div class="gameday-title">
    GAMEDAY
</div>
```

an older dashboard template may still be loaded.

Corrective sequence:

```text
1. Check the Git source template.
2. Rebuild the Docker image.
3. Recreate the container.
4. Test the application.
5. Reload with Ctrl + F5.
```

---

## Source Is Correct but Browser Is Outdated

Check the source template:

```bash
grep -n -A2 -B2 \
    'theme-day-title\|gameday-title' \
    /opt/lums-public/server/templates/index.html
```

Rebuild the image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Recreate the container using the existing volume.

Then refresh the browser.

---

## CSS Is Present but the Theme Does Not Change

Check the applied theme:

```javascript
document.documentElement.dataset.theme;
```

Check whether the CSS file is loaded in the browser.

Check the Docker image contents:

```bash
sudo docker exec \
    lums \
    ls -l /app/static/
```

Inspect the relevant CSS rules inside the container.

Possible causes:

- Wrong `data-theme` value.
- CSS selector mismatch.
- Old Docker image.
- Old running container.
- Browser cache.
- Missing static asset.
- Incorrect template deployment.

---

# 25. Security

The theme system is client-side and does not modify security-relevant functionality.

The following remain unchanged:

- Flask authentication.
- Session management.
- CSRF protection.
- API authentication.
- Agent tokens.
- SQLite database.
- Password hashing.
- Audit logging.
- API endpoints.
- Update jobs.
- Client reporting.

The stored theme value is not a security-sensitive setting.

Users can change their local theme value through browser developer tools.

However, all theme assets must still be reviewed for:

- External tracking.
- Untrusted scripts.
- Embedded active content.
- Unexpected remote requests.
- Copyright and licensing issues.

Theme CSS and JavaScript must not disable or bypass security controls.

---

# 26. Backup and Rollback

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

A theme rollback should not require:

- Database deletion.
- Database migration.
- Token replacement.
- TLS replacement.
- Authentication changes.

> **The database volume must be preserved during frontend rollback.**

---

# 27. Source and Runtime Separation

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

| Component | Location |
|---|---|
| Git source | `/opt/lums-public` |
| Docker image | `lums:latest` |
| Running container | `lums` |
| Persistent database | Docker volume `lums-data` |
| Secret configuration | `/etc/lums/docker/lums.env` |
| Nginx TLS key | `/etc/nginx/ssl/lums/lums.key` |

The repository contains source code and frontend assets.

Runtime state and secrets remain outside the Git repository.

---

# 28. Files

| File | Function |
|---|---|
| `server/templates/login.html` | Login and theme selector |
| `server/templates/index.html` | Dashboard and theme title |
| `server/static/theme.js` | Theme selection and storage |
| `server/static/style.css` | Theme design and animations |
| `server/static/images/lumsstadium.jpg` | Stadium background |
| `server/static/images/golf.jpg` | Golf background |
| `server/static/images/*.svg` | Theme and frontend graphics |

All required frontend files must be included in the Docker image.

The exact internal container paths should be verified using:

```bash
sudo docker inspect lums
```

and:

```bash
sudo docker exec \
    lums \
    find / -path '*static*' \
    -maxdepth 5 \
    2>/dev/null
```

---

# 29. Current Status

Implemented theme functionality:

- [x] Login theme selector.
- [x] Six themes.
- [x] `localStorage` persistence.
- [x] Automatic theme activation.
- [x] No dashboard theme selector.
- [x] Standard LUMS remains intact.
- [x] Stadium background.
- [x] Golf background.
- [x] `GAMEDAY`.
- [x] `CLUB DAY`.
- [x] Football animation.
- [x] Golf ball animation.
- [x] Reduced-motion support.
- [x] Theme-specific CSS.
- [x] Nerd Mode / Nerdseite.
- [x] Geek Lab.
- [x] Enterprise Admin.
- [x] SVG asset support.
- [x] Git-controlled frontend assets.
- [x] Asset attribution documentation.
- [x] Docker-based deployment process.

The theme selector requires:

- No additional database structure.
- No backend API.
- No separate service.
- No separate application instance.

---

# 30. Frontend Troubleshooting Order

When a theme problem occurs, inspect the layers in this order:

```text
1. localStorage
       ↓
2. data-theme
       ↓
3. Loaded HTML
       ↓
4. Docker image
       ↓
5. Running container
       ↓
6. CSS
       ↓
7. JavaScript
       ↓
8. Static assets
       ↓
9. Nginx
       ↓
10. Browser cache
```

Identify the affected layer before making changes.

Do not immediately:

- Delete the Docker volume.
- Reinstall LUMS.
- Disable TLS verification.
- Expose port `5000`.
- Expose port `5050`.
- Modify the database.
- Replace production configuration blindly.

---

# 31. Final Principle

```text
ONE LUMS
MANY INTERFACES
SAME BACKEND
SAME API
SAME DATABASE
SAME SECURITY
```

The theme system changes the visual experience without creating a separate LUMS installation.

> **One LUMS. Many Interfaces. Same Backend.**

> **LUMS — Linux Update Management without the noise.**
