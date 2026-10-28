import sqlite3
import re
from pathlib import Path
from werkzeug.datastructures import LanguageAccept

from server.i18n import (
    LANGUAGES,
    browser_language,
    normalize_language,
    translate,
    translations_for,
)
from server.security_migration import migrate_user_language


def test_configured_languages_include_requested_locales():
    assert set(LANGUAGES) == {
        "de",
        "en-US",
        "en-GB",
        "fr",
        "es",
        "zh-CN",
        "ja",
        "pl",
        "sv",
        "nb",
        "fi",
    }


def test_normalize_language_accepts_browser_locale_variants():
    assert normalize_language("en") == "en-US"
    assert normalize_language("EN-gb") == "en-GB"
    assert normalize_language("zh-TW") == "zh-CN"
    assert normalize_language("no-NO") == "nb"
    assert normalize_language("ar") is None


def test_browser_language_matches_supported_language_or_english():
    assert browser_language(
        LanguageAccept([("fr-CA", 1), ("en-GB", 0.8)])
    ) == "fr"
    assert browser_language(LanguageAccept([("en-GB", 1)])) == "en-GB"
    assert browser_language(LanguageAccept([("ar", 1)])) == "de"


def test_translation_falls_back_to_source_text_for_unknown_keys():
    assert translate("Clients", "fr") == "Clients"
    assert translate("Unknown key", "ja") == "Unknown key"


def test_current_template_and_script_keys_are_translated():
    project_root = Path(__file__).resolve().parents[1]
    source_files = [
        *project_root.joinpath("server", "templates").glob("*.html"),
        *project_root.joinpath("server", "static").glob("*.js"),
    ]
    keys = set()
    for source_file in source_files:
        content = source_file.read_text(encoding="utf-8")
        keys.update(
            re.findall(r'tr\(["\']([^"\']+)["\']\)', content)
        )
        keys.update(
            re.findall(r'\bt\(["\']([^"\']+)["\']\)', content)
        )

    for language in LANGUAGES:
        if language in {"en-US", "en-GB"}:
            continue
        missing = keys - translations_for(language).keys()
        assert not missing, f"{language} is missing translations: {missing}"



def test_dynamic_topology_and_telemetry_messages_are_localized():
    project_root = Path(__file__).resolve().parents[1]
    infrastructure = (
        project_root / "server" / "static" / "infrastructure.js"
    ).read_text(encoding="utf-8")
    telemetry = (
        project_root / "server" / "static" / "telemetry.js"
    ).read_text(encoding="utf-8")

    infrastructure_block = re.search(
        r"const messages = \{(.*?)\n    \};",
        infrastructure,
        re.DOTALL,
    )
    telemetry_block = re.search(
        r"const dashboardMessages = \{(.*?)\n    \};",
        telemetry,
        re.DOTALL,
    )
    assert infrastructure_block, "Infrastructure messages block not found"
    assert telemetry_block, "Telemetry dashboardMessages block not found"

    dynamic_keys = set(
        re.findall(r':\s*"([^"]+)"', infrastructure_block.group(1))
    )
    dynamic_keys.update(
        re.findall(r':\s*"([^"]+)"', telemetry_block.group(1))
    )

    representative = {
        "Loading infrastructure data…",
        "Infrastructure data could not be loaded.",
        "No infrastructure items are registered yet.",
        "Delete this infrastructure item and its relationships?",
        "Request failed (HTTP {status}).",
        "No alerts or outages in this period.",
        "CPU threshold exceeded",
        "Disk returned below the threshold",
        "Telemetry interrupted",
        "Not monitored on this client",
    }

    for language in LANGUAGES:
        if language in {"en-US", "en-GB"}:
            continue
        entries = translations_for(language)
        missing = dynamic_keys - entries.keys()
        assert not missing, (
            f"{language} is missing dynamic JS translation keys: {missing}"
        )
        untranslated = {
            key: entries[key]
            for key in representative
            if entries[key] == key
        }
        assert not untranslated, (
            f"{language} still has untranslated dynamic messages: "
            f"{untranslated}"
        )


def test_user_language_migration_preserves_users_and_is_idempotent():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO users (id, username) VALUES (1, 'admin')"
    )

    migrate_user_language(connection)
    migrate_user_language(connection)

    assert connection.execute(
        "SELECT username, language FROM users WHERE id = 1"
    ).fetchone() == ("admin", "")
    assert sum(
        column[1] == "language"
        for column in connection.execute("PRAGMA table_info(users)")
    ) == 1
    connection.close()


def test_language_can_be_selected_on_login_page(monkeypatch):
    monkeypatch.setenv("LUMS_SECRET_KEY", "pytest-i18n-secret")
    from server import app as app_module

    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as client:
        response = client.get("/login", headers={"Accept-Language": "ja-JP"})
        assert response.status_code == 200
        assert b'<html lang="ja"' in response.data
        assert b'id="login-language-select"' in response.data
        assert b'class="login-language-selector"' in response.data

        with client.session_transaction() as session:
            csrf_token = session["csrf_token"]

        response = client.post(
            "/language",
            data={"csrf_token": csrf_token, "language": "fr"},
        )

        assert response.status_code == 302
        assert client.get("/login").data.startswith(
            b'<!DOCTYPE html>\n<html lang="fr"'
        )


def test_language_preference_is_saved_for_authenticated_user(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("LUMS_SECRET_KEY", "pytest-i18n-secret")
    from server import app as app_module

    db_path = tmp_path / "language.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, language TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO users (id, language) VALUES (4, '')"
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(app_module, "DB_PATH", str(db_path))

    with app_module.app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 4
            session["csrf_token"] = "valid-test-csrf"

        response = client.post(
            "/language",
            data={
                "csrf_token": "valid-test-csrf",
                "language": "en-GB",
            },
        )

    assert response.status_code == 302
    connection = sqlite3.connect(db_path)
    assert connection.execute(
        "SELECT language FROM users WHERE id = 4"
    ).fetchone() == ("en-GB",)
    connection.close()


def test_static_infrastructure_texts_are_localized():
    infrastructure_keys = {
        "Infrastructure topology",
        "See registered LUMS clients, infrastructure and their dependencies in one place.",
        "Infrastructure map",
        "LUMS clients are imported automatically. Other systems and links are maintained here.",
        "Topology summary",
        "Registered clients",
        "Infrastructure items",
        "Relationships",
        "Shared dependencies",
        "Registered clients and manually managed infrastructure connected by their relationships.",
        "Relationship",
        "Inventory",
        "Hostname, IP address, role and location for each system.",
        "Notes",
        "Hostname / IP address",
        "Role / location",
        "Source",
        "Relationships and dependencies",
        "Record what depends on, hosts, connects to or runs on another system.",
        "From",
        "To",
        "Depends on",
        "Hosts",
        "Connects to",
        "Runs on",
        "Virtual machine",
        "Network device",
        "Service",
        "Storage",
    }

    for language in LANGUAGES:
        if language in {"en-US", "en-GB"}:
            continue

        entries = translations_for(language)
        untranslated = {
            key: entries.get(key, key)
            for key in infrastructure_keys
            if entries.get(key, key) == key
        }

        assert not untranslated, (
            f"{language} has untranslated static infrastructure text: "
            f"{untranslated}"
        )
