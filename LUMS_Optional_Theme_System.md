# LUMS -- Optional Theme System

## Overview

LUMS provides an optional theme system for its web interface.

Themes change only the visual presentation of LUMS.

**Backend, API, database, authentication, and update logic remain
unchanged.**

The standard system remains the original LUMS design.

Available themes:

-   🖥️ **Standard LUMS**
-   🏈 **LUMS Stadium**
-   ⛳ **Golf Club**
-   🤓 **Nerd Mode**
-   🧠 **Geek Lab**
-   🗄️ **Enterprise Admin**

The theme selector is available **only on the login page**.

After selecting a theme, the choice is stored in the browser and
automatically applied to the other LUMS pages.

------------------------------------------------------------------------

## Goals

The theme system was introduced to make LUMS visually adaptable to
different users and usage scenarios.

The following principles apply:

-   The original LUMS design remains intact.
-   Themes are optional visual extensions.
-   There is no theme selector on the dashboard.
-   Theme selection happens only on the login page.
-   The selected theme is stored client-side.
-   The selected theme is automatically applied to subsequent LUMS
    pages.
-   The backend and database are not modified.
-   No additional database structure is required.
-   Themes use only HTML, CSS, and JavaScript.

------------------------------------------------------------------------

## Architecture

The theme system consists of three main components:

``` text
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

The stored value uses the following browser storage key:

``` text
lums-theme
```

Example:

``` javascript
localStorage.getItem("lums-theme")
```

may return:

``` text
"golf"
```

------------------------------------------------------------------------

## Theme Values

The following internal values are used:

  -----------------------------------------------------------------------
  Theme                   Value                   Purpose
  ----------------------- ----------------------- -----------------------
  🖥️ Standard LUMS        `standard`              Original design

  🏈 LUMS Stadium         `nfl`                   Stadium / Game-Day
                                                  presentation

  ⛳ Golf Club            `golf`                  Golf / Club
                                                  presentation

  🤓 Nerd Mode            `nerd`                  Terminal / CRT
                                                  presentation

  🧠 Geek Lab             `geek`                  Lab / Cyber / Blueprint
                                                  presentation

  🗄️ Enterprise Admin     `admin`                 Enterprise
                                                  control-center
                                                  presentation
  -----------------------------------------------------------------------

The internal value `nfl` is used only as a technical identifier.

The user-facing name is **LUMS Stadium**.

------------------------------------------------------------------------

## Login Theme Selector

The selector is located only in:

``` text
/opt/lums-api/templates/login.html
```

Source file:

``` text
/opt/lums-public/server/templates/login.html
```

The selector contains:

``` html
<div class="login-theme-selector">
    <label for="login-theme-select">Theme</label>

    <select id="login-theme-select">
        <option value="standard">🖥️ Standard LUMS</option>
        <option value="nfl">🏈 LUMS Stadium</option>
        <option value="golf">⛳ Golf Club</option>
        <option value="nerd">🤓 Nerd Mode</option>
        <option value="geek">🧠 Geek Lab</option>
        <option value="admin">🗄️ Enterprise Admin</option>
    </select>
</div>
```

The login page loads the central theme script:

``` html
<script src="{{ url_for('static', filename='theme.js') }}"></script>
```

------------------------------------------------------------------------

## Theme JavaScript

The central theme logic is located in:

``` text
/opt/lums-public/server/static/theme.js
```

and deployed to:

``` text
/opt/lums-api/static/theme.js
```

The browser storage key is defined as:

``` javascript
const STORAGE_KEY = "lums-theme";
```

The supported themes are:

``` javascript
const THEMES = [
    "standard",
    "nfl",
    "golf",
    "nerd",
    "geek",
    "admin"
];
```

The selected theme is applied to the HTML root element:

``` javascript
document.documentElement.dataset.theme = theme;
```

This produces, for example:

``` html
<html data-theme="golf">
```

or:

``` html
<html data-theme="nfl">
```

CSS can then target individual themes.

------------------------------------------------------------------------

## Standard Fallback

If no theme has been saved or an unknown value is found, LUMS
automatically falls back to:

``` text
standard
```

Example:

``` javascript
applyTheme(
    THEMES.includes(savedTheme)
        ? savedTheme
        : "standard"
);
```

This prevents an invalid or corrupted browser state from creating an
undefined theme.

------------------------------------------------------------------------

## Theme Persistence

The selected theme is stored in the browser.

Example:

``` javascript
localStorage.setItem("lums-theme", "golf");
```

When the LUMS interface is opened again, the stored value is
automatically loaded.

The user therefore does not have to select the theme again on every
page.

------------------------------------------------------------------------

## Behavior After Login

The flow is:

``` text
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

The theme selector itself is not displayed on the dashboard.

------------------------------------------------------------------------

## Dashboard

The dashboard does not contain a theme selector.

The topbar contains only a dynamic theme title element:

``` html
<div class="theme-day-title" aria-hidden="true"></div>
```

This element is populated through CSS depending on the selected theme.

For Standard, Nerd, Geek, and Enterprise Admin, the element remains
empty.

------------------------------------------------------------------------

## LUMS Stadium

The Stadium theme uses a dedicated background image:

``` text
/static/images/lumsstadium.jpg
```

Source file:

``` text
/opt/lums-public/server/static/images/lumsstadium.jpg
```

Deployed file:

``` text
/opt/lums-api/static/images/lumsstadium.jpg
```

The image is used as the LUMS dashboard background.

Example:

``` css
html[data-theme="nfl"] body {
    background:
        #07120b
        url("/static/images/lumsstadium.jpg")
        center top / cover
        fixed
        no-repeat;
}
```

### Game-Day Title

The Stadium theme displays:

``` text
GAMEDAY
```

The title is activated only when:

``` text
data-theme="nfl"
```

### Football Animation

The Stadium theme can animate a football across the topbar.

The animation uses the CSS pseudo-element:

``` css
.topbar::after
```

Example:

``` css
html[data-theme="nfl"] .topbar::after {
    content: "🏈";
    animation: lums-football-flight 7s linear infinite;
}
```

The football moves from left to right while changing its position and
rotation.

### Reduced Motion

For users who have enabled reduced motion, the animation is disabled:

``` css
@media (prefers-reduced-motion: reduce) {
    html[data-theme="nfl"] .topbar::after {
        animation: none !important;
        opacity: 0 !important;
    }
}
```

------------------------------------------------------------------------

## Golf Club

The Golf theme uses:

``` text
/static/images/golf.jpg
```

Source file:

``` text
/opt/lums-public/server/static/images/golf.jpg
```

Deployed file:

``` text
/opt/lums-api/static/images/golf.jpg
```

The background is loaded through CSS:

``` css
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

### Club-Day Title

The Golf theme displays:

``` text
CLUB DAY
```

The title is activated only when:

``` text
data-theme="golf"
```

### Golf Ball Animation

The Golf theme can animate a golf ball across the topbar.

Technically:

``` css
html[data-theme="golf"] .topbar::after {
    content: "⚪";
    animation: lums-golf-ball-flight 6s linear infinite;
}
```

The ball moves from left to right while changing height and rotation
during its flight.

The animation also respects:

``` text
prefers-reduced-motion
```

------------------------------------------------------------------------

## Nerd Mode

Nerd Mode uses a terminal/CRT-inspired visual design.

Typical visual elements:

-   Monospace font
-   Terminal styling
-   CRT scanlines
-   Green accents
-   Technical presentation
-   Reduced classic UI styling

The theme is purely visual.

The actual LUMS functionality remains unchanged.

------------------------------------------------------------------------

## Geek Lab

Geek Lab uses a technical laboratory / blueprint visual style.

Typical elements:

-   Dark background
-   Blue / purple accents
-   Grid / blueprint effects
-   Technical glow effects
-   Laboratory / engineering character

Only CSS presentation is changed.

------------------------------------------------------------------------

## Enterprise Admin

Enterprise Admin uses a classic light administration interface.

Goals:

-   Neutral appearance
-   Light background
-   Subtle colors
-   Control-center character
-   High readability

The theme does not change any administrative functionality.

------------------------------------------------------------------------

## Standard LUMS

The Standard theme is especially important.

It has **no additional theme overrides**.

When:

``` text
data-theme="standard"
```

is active, the original LUMS interface remains unchanged.

This allows new themes to be added without replacing the original
design.

------------------------------------------------------------------------

## CSS Structure

Theme rules are located in:

``` text
/opt/lums-public/server/static/style.css
```

and deployed to:

``` text
/opt/lums-api/static/style.css
```

Theme CSS rules use the HTML attribute:

``` css
html[data-theme="THEME"]
```

Example:

``` css
html[data-theme="golf"] body {
    /* Golf Theme */
}
```

This keeps the rules scoped to the selected theme.

------------------------------------------------------------------------

## Theme-Day Titles

Dynamic theme titles are generated through CSS.

Golf example:

``` css
html[data-theme="golf"] .theme-day-title::after {
    content: "CLUB DAY";
}
```

Stadium example:

``` css
html[data-theme="nfl"] .theme-day-title::after {
    content: "GAMEDAY";
}
```

Positioning is handled within the topbar:

``` css
html[data-theme="nfl"] .theme-day-title,
html[data-theme="golf"] .theme-day-title {
    position: absolute;
    left: 50%;
    top: 18px;
    transform: translateX(-50%);
}
```

This keeps the title horizontally centered and approximately aligned
with the LUMS header.

------------------------------------------------------------------------

## Deployment

The project uses two relevant directories.

### Source Directory

``` text
/opt/lums-public
```

This contains the version-controlled frontend files.

### Runtime Directory

``` text
/opt/lums-api
```

Flask uses the files deployed here.

### Deploy CSS

After changes to:

``` text
/opt/lums-public/server/static/style.css
```

copy the file to:

``` text
/opt/lums-api/static/style.css
```

Example:

``` bash
sudo cp /opt/lums-public/server/static/style.css /opt/lums-api/static/style.css
```

### Deploy JavaScript

After changes to:

``` text
/opt/lums-public/server/static/theme.js
```

copy the file to:

``` text
/opt/lums-api/static/theme.js
```

Example:

``` bash
sudo cp /opt/lums-public/server/static/theme.js /opt/lums-api/static/theme.js
```

### Deploy Templates

After changes to:

``` text
/opt/lums-public/server/templates/index.html
```

or:

``` text
/opt/lums-public/server/templates/login.html
```

copy the corresponding template to:

``` text
/opt/lums-api/templates/
```

Example:

``` bash
sudo cp /opt/lums-public/server/templates/index.html /opt/lums-api/templates/index.html
```

------------------------------------------------------------------------

## Images and GitHub

The theme images are part of the frontend and are therefore
version-controlled in Git.

Source files:

``` text
server/static/images/lumsstadium.jpg
server/static/images/golf.jpg
```

The images are committed and pushed to GitHub together with the theme
files.

Example:

``` bash
cd /opt/lums-public
git status
git add server/static/images/lumsstadium.jpg
git add server/static/images/golf.jpg
git add server/static/style.css
git add server/static/theme.js
git add server/templates/index.html
git add server/templates/login.html
git commit -m "Add optional LUMS themes"
git push
```

The repository therefore contains:

-   Theme logic
-   Theme CSS
-   Login selector
-   Dashboard theme support
-   Stadium background
-   Golf background

The images are therefore part of the LUMS frontend project and are not
only stored locally on the server.

------------------------------------------------------------------------

## Restart Flask

After template changes, restart the LUMS service:

``` bash
sudo systemctl restart lums.service
```

The service uses:

``` text
ExecStart=/usr/bin/python3 /opt/lums-api/app.py
```

and:

``` text
WorkingDirectory=/opt/lums-api
```

This ensures that Flask uses the current template version.

------------------------------------------------------------------------

## Browser Cache

After frontend changes, reload the page using:

``` text
Ctrl + F5
```

This forces the browser to reload the frontend resources.

------------------------------------------------------------------------

## Verify Theme

The currently stored theme can be checked in the browser console:

``` javascript
localStorage.getItem("lums-theme")
```

Example:

``` text
"golf"
```

The currently applied HTML theme can be checked with:

``` javascript
document.documentElement.dataset.theme
```

Example:

``` text
"golf"
```

------------------------------------------------------------------------

## Check Rendered Theme Element

The dynamic title element can be checked with:

``` javascript
document.querySelector(".theme-day-title")?.outerHTML
```

Expected result:

``` html
<div class="theme-day-title" aria-hidden="true"></div>
```

If the result is:

``` text
undefined
```

the currently loaded page does not contain the new dynamic theme
element.

------------------------------------------------------------------------

## Detect Old GAMEDAY

If the browser still displays:

``` text
GAMEDAY
```

inspect the actual topbar content:

``` javascript
document.querySelector("header.topbar")?.innerHTML
```

If the following appears:

``` html
<div class="gameday-title">
    GAMEDAY
</div>
```

an older dashboard template is still being served.

In that case:

-   Check the deployed template
-   Restart the LUMS service
-   Reload the browser using Ctrl + F5

------------------------------------------------------------------------

## Common Problems

### Golf Theme Displays GAMEDAY

Check:

``` javascript
localStorage.getItem("lums-theme")
```

Expected:

``` text
"golf"
```

Then:

``` javascript
document.documentElement.dataset.theme
```

Expected:

``` text
"golf"
```

Then:

``` javascript
document.querySelector(".theme-day-title")?.outerHTML
```

If this returns `undefined`, the currently loaded page has not yet
received the new template.

### Source Template Is Correct but Browser Still Shows the Old Version

Check:

``` bash
grep -n -A2 -B2 'theme-day-title\|gameday-title' /opt/lums-api/templates/index.html
```

The runtime template must contain:

``` html
<div class="theme-day-title" aria-hidden="true"></div>
```

Then:

``` bash
sudo systemctl restart lums.service
```

and afterwards:

``` text
Ctrl + F5
```

in the browser.

### CSS Appears Correct but the Display Does Not Change

Check:

``` bash
grep -n -A12 -B4 'theme-day-title' /opt/lums-api/static/style.css
```

At minimum, the following rules should exist:

``` css
html[data-theme="nfl"] .theme-day-title::after {
    content: "GAMEDAY";
}

html[data-theme="golf"] .theme-day-title::after {
    content: "CLUB DAY";
}
```

### Theme Is Not Saved

Check:

``` javascript
localStorage.getItem("lums-theme")
```

If `null` is returned, no theme has been stored yet.

### Unknown Theme Value

Example:

``` javascript
localStorage.setItem("lums-theme", "invalid")
```

During the next initialization, LUMS automatically falls back to:

``` text
standard
```

------------------------------------------------------------------------

## Security

The theme system does not modify any security-relevant functionality.

The following remain unchanged:

-   Flask authentication
-   Session management
-   CSRF protection
-   API authentication
-   Agent tokens
-   SQLite database
-   Password hashing
-   Audit logging
-   API endpoints
-   Update jobs
-   Client reporting

The theme system operates entirely on the client side.

The stored theme value is therefore **not a security-sensitive
setting**.

A user can change the local theme value at any time using the browser
developer tools.

------------------------------------------------------------------------

## Files

  File                                     Function
  ---------------------------------------- ----------------------------------
  `server/templates/login.html`            Login + theme selector
  `server/templates/index.html`            Dashboard + theme title element
  `server/static/theme.js`                 Theme selection and localStorage
  `server/static/style.css`                Theme design and animations
  `server/static/images/lumsstadium.jpg`   Stadium background
  `server/static/images/golf.jpg`          Golf background

### Deployment

  File                Runtime Path
  ------------------- -----------------------------------------------
  `login.html`        `/opt/lums-api/templates/login.html`
  `index.html`        `/opt/lums-api/templates/index.html`
  `theme.js`          `/opt/lums-api/static/theme.js`
  `style.css`         `/opt/lums-api/static/style.css`
  `lumsstadium.jpg`   `/opt/lums-api/static/images/lumsstadium.jpg`
  `golf.jpg`          `/opt/lums-api/static/images/golf.jpg`

------------------------------------------------------------------------

## Backup / Rollback

Before major frontend changes, create a backup of the current state.

Example:

``` bash
cp server/static/style.css /tmp/lums-style-backup.css
cp server/templates/index.html /tmp/lums-index-backup.html
cp server/templates/login.html /tmp/lums-login-backup.html
cp server/static/theme.js /tmp/lums-theme-backup.js
```

A rollback affects only the frontend.

The backend, database, and service configuration do not need to be
changed for a theme rollback.

------------------------------------------------------------------------

## Design Principle

The LUMS theme system follows the principle:

``` text
One LUMS
Many Interfaces
Same Backend
```

The themes are different visual interfaces for the same LUMS system.

The technical functionality remains identical.

LUMS can therefore be presented as:

-   Classic and neutral
-   Sport-inspired
-   Relaxed
-   Nerd-oriented
-   Technical
-   Enterprise-oriented

------------------------------------------------------------------------

## Current Status

The theme infrastructure is implemented.

Available:

-   Theme selector on the login page
-   Six themes
-   localStorage persistence
-   Automatic theme activation
-   No theme selector on the dashboard
-   Standard LUMS remains intact
-   Stadium background
-   Golf background
-   GAMEDAY
-   CLUB DAY
-   Football animation
-   Golf ball animation
-   Reduced-motion support
-   Theme-specific CSS overlays
-   Separate source and runtime directories
-   Browser-side theme management
-   Theme images included in the Git repository

The theme selector requires no additional database structure and no
backend API.

------------------------------------------------------------------------

## Troubleshooting Principle

When dealing with frontend display problems, do not immediately replace
files or reinstall LUMS.

Check the layers in order:

``` text
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
6. Flask process
       ↓
7. Browser cache
```

**Identify the affected layer first, then correct that layer.**

> **Don't reinstall everything immediately. Find the layer where the
> problem occurs.**

This principle also applies to the LUMS theme system.
