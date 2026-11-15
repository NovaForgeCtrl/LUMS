# LUMS Documentation Comprehensive Update Plan

## Project Context
- **Database**: SQLite (NOT PostgreSQL - correcting user misunderstanding)
- **New Features**: 
  - Fleet Overview & Dashboard Charts
  - Telemetry System (CPU/Memory/Network)
  - Theme System (6 themes: standard, LUMSStadium, golf, nerd, geek, admin)
  - Agent Components (agent.py, watcher.py, telemetry.py)

## Files to Update (71 total)

### Root Level (8 files)
1. README.md - Project overview
2. install.md - Installation guide with telemetry & theme setup
3. administration.md - Admin tasks including backups
4. security.md - Security model
5. troubleshooting.md - Comprehensive troubleshooting
6. telemetry.md - Telemetry system documentation
7. LUMS_Health_Dashboard.md - Fleet overview & charts
8. LUMS_Optional_Theme_System.md - Theme system details

### Locales (63 files across 11 languages)
- **de/** - Deutsch (7 files)
- **en-GB/** - English GB (6 files)
- **en-US/** - English US (1 file: quick-start.md)
- **es/** - Español (6 files)
- **fi/** - Suomi (6 files)
- **fr/** - Français (6 files)
- **ja/** - 日本語 (6 files)
- **nb-NO/** - Norsk Bokmål (6 files)
- **pl/** - Polski (6 files)
- **sv/** - Svenska (6 files)
- **zh-CN/** - 简体中文 (6 files)

### Additional
- server/static/backup-restore.md (1 file)

## Code Reference Details

### Database Schema (SQLite)
- **clients**: hostname, ip, os, kernel, architecture, agent_version, last_seen, idle, idle_seconds
- **available_updates**: client_id, package, installed_version, available_version
- **installed_packages**: client_id, package, version
- **update_jobs**: id, client_id, status, created_at, started_at, finished_at, reboot_required
- **update_job_packages**: job_id, package, installed_version, target_version, status

### Configuration Keys (from server/app.py)
- `LUMS_DB_PATH`: Database path (default: /var/lib/lums/lums.db)
- `LUMS_SECRET_KEY_FILE`: Secret key file (default: /run/secrets/lums_secret)
- `LUMS_SECRET_KEY`: Environment variable fallback
- `LUMS_BACKUP_DIR`: Backup directory (default: /var/backups/lums)
- `PACKAGE_SEARCH_QUERY_MAX_LENGTH`: 128
- `PACKAGE_SEARCH_MAX_RESULTS`: 50
- `ADMIN_NOTE_MAX_LENGTH`: 2000

### Security (from server/security.py)
- **Roles**: administrator, operator, viewer
- **Permissions**: 10 permissions with dependencies
- **Password Hasher**: Argon2
- **CSRF**: Enabled
- **Client Authentication**: Token-based

### Telemetry Details (from telemetry.md & telemetry.js)
- Metrics: CPU%, Memory%, Memory bytes, Network RX/TX bytes
- Update interval: ~5 seconds
- Data retention: 7 days
- History range: 1-168 hours
- Views: Line, Area, Donut charts
- Fleet status: Online (≤120s), Unknown (120-600s), Offline (>600s)

### Theme System (from theme.js)
- Themes: standard, LUMSStadium, golf, nerd, geek, admin
- Storage: localStorage "lums-theme"
- Visual-only: No security changes
- Special effects: Matrix effect for "nerd" theme

### Agent Components (from agent/ directory)
- `agent.py`: Main agent implementation
- `telemetry.py`: Telemetry collection
- `watcher.py`: Execution watcher
- `package_manager.py`: Package management
- Services: lums-agent.service, lums-telemetry.service, lums-agent-watcher.service
- Timers: lums-agent.timer, lums-telemetry.timer, lums-agent-watcher.timer

## Key Changes to Document

### For All Files:
1. Update command examples to match current code
2. Add telemetry setup sections
3. Add theme system information
4. Correct any PostgreSQL references (should be SQLite)
5. Add Fleet Overview dashboard documentation
6. Add troubleshooting for new features

### Specific Sections:

#### README.md
- Add telemetry feature overview
- Add theme system description
- Update architecture diagram if needed
- Mention Fleet Overview dashboard

#### install.md
- Add telemetry.py installation
- Add theme system configuration
- Correct any DB setup instructions (SQLite, not PostgreSQL)
- Add systemd timer setup for telemetry

#### administration.md
- Add telemetry management
- Add theme management
- Add backup procedures

#### security.md
- Document telemetry security
- Document theme security (visual-only, no auth bypass)

#### troubleshooting.md
- Telemetry collection issues
- Theme rendering problems
- Chart display issues
- Fleet overview blank

#### telemetry.md (EXISTING - review for updates)
- Verify all code references
- Check metric descriptions
- Verify API endpoints
- Check retention policies

#### LUMS_Health_Dashboard.md (EXISTING - review for updates)
- Document fleet overview filters
- Document chart views
- Document refresh rates
- Document status thresholds

#### LUMS_Optional_Theme_System.md (EXISTING - review for updates)
- Document all 6 themes
- Document selection mechanism
- Document special effects

#### server/static/backup-restore.md
- Verify backup procedures
- Add backup retention info
- Add restore verification steps

## Language-Specific Notes

All locales must have:
- Identical technical content (code paths, config keys, etc.)
- Proper translations of UI/business terminology
- Consistent glossary (backup → Backup, etc.)
- Localized examples where appropriate

## Glossary for Translations

| English | German | Spanish | French | Japanese | Norwegian | Polish | Swedish | Finnish | Chinese |
|---------|--------|---------|--------|----------|-----------|--------|---------|---------|---------|
| Client | Client | Cliente | Client | クライアント | Klient | Klient | Klient | Asiakas | 客户端 |
| Agent | Agent | Agente | Agent | エージェント | Agent | Agent | Agent | Agentti | 代理 |
| Update | Update | Actualización | Mise à jour | 更新 | Oppdatering | Aktualizacja | Uppdatering | Päivitys | 更新 |
| Package | Paket | Paquete | Paquet | パッケージ | Pakke | Pakiet | Paket | Paketti | 软件包 |
| Telemetry | Telemetrie | Telemetría | Télémétrie | テレメトリ | Telemetri | Telemetria | Telemetri | Telemetria | 遥测 |
| Fleet | Flotte | Flota | Flotte | フロート | Flåte | Flota | Flotta | Laivasto | 船队 |

## Output Structure

For each file update, document:
1. File path
2. Changes made (detailed list)
3. Code references used
4. Complete new content (if created)

## Implementation Approach

1. Start with root-level English files (8 files)
2. Create translations for root-level files
3. Update locale-specific documentation
4. Verify all cross-references
5. Validate all code examples
