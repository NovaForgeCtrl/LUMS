import os
from html.parser import HTMLParser

import pytest

os.environ.setdefault("LUMS_SECRET_KEY", "pytest-only-test-secret")

from flask import render_template
from server.app import app


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nav_stack = []
        self.nav_errors = []
        self.nav_classes = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag == "nav":
            classes = attributes.get("class", "")
            self.nav_classes.append(classes)
            self.nav_stack.append(classes)

        elif tag == "a":
            self.links.append({
                "href": attributes.get("href", ""),
                "classes": attributes.get("class", ""),
                "nav_ancestors": tuple(self.nav_stack),
            })

    def handle_endtag(self, tag):
        if tag == "nav":
            if not self.nav_stack:
                self.nav_errors.append(
                    "Closing nav without matching opening nav"
                )
            else:
                self.nav_stack.pop()


def render_sidebar(path, permissions):
    with app.test_request_context(
        path,
        base_url="https://localhost",
    ):
        html = render_template(
            "_sidebar.html",
            user_permissions=set(permissions),
            user_role="viewer",
            csrf_token="test-csrf-token",
            languages={
                "de-DE": "Deutsch",
                "en-US": "English",
            },
            language="de-DE",
            tr=lambda message: message,
        )

    parser = NavigationParser()
    parser.feed(html)
    parser.close()

    return html, parser


@pytest.mark.parametrize(
    (
        "permissions",
        "path",
        "expect_soc",
        "expect_alerts",
        "expect_soc_subnav",
        "expect_alerts_subnav",
    ),
    [
        (set(), "/", False, False, False, False),
        (
            {"clients.view"},
            "/soc/",
            True, False, True, False,
        ),
        (
            {"alerts.view"},
            "/alerts",
            False, True, False, True,
        ),
        (
            {"clients.view", "alerts.view"},
            "/soc/",
            True, True, True, False,
        ),
        (
            {"clients.view", "alerts.view"},
            "/alerts",
            True, True, True, True,
        ),
    ],
)
def test_sidebar_navigation_permission_combinations(
    permissions,
    path,
    expect_soc,
    expect_alerts,
    expect_soc_subnav,
    expect_alerts_subnav,
):
    html, parser = render_sidebar(path, permissions)

    assert parser.nav_errors == []
    assert parser.nav_stack == []

    assert parser.nav_classes.count("lums-sidebar-nav") == 1
    assert (
        "lums-sidebar-soc-subnav" in parser.nav_classes
    ) is expect_soc_subnav
    assert (
        "lums-sidebar-alerts-subnav" in parser.nav_classes
    ) is expect_alerts_subnav

    hrefs = [link["href"] for link in parser.links]

    assert any(href == "/soc/" for href in hrefs) is expect_soc
    assert any(href.startswith("/alerts") for href in hrefs) is expect_alerts

    if "alerts.view" not in permissions:
        assert "data-alert-tab=" not in html

    if "clients.view" not in permissions:
        assert "/soc/network-monitoring" not in html
        assert "/soc/events" not in html
        assert "/soc/network-analyzer" not in html

    analyzer_links = [
        link for link in parser.links
        if link["href"] == "/soc/network-analyzer"
    ]

    if "clients.view" in permissions:
        assert len(analyzer_links) == 1
        assert "lums-sidebar-nav" in analyzer_links[0]["nav_ancestors"]
        assert "lums-sidebar-soc-subnav" not in analyzer_links[0]["nav_ancestors"]
