#!/usr/bin/env python3

import os
import shutil
import subprocess


PACKAGE_MANAGER_APT = "apt"
PACKAGE_MANAGER_PACMAN = "pacman"


def detect_package_manager():
    """
    Detect the package manager available on the client.

    Returns:
        "apt"     when APT is available
        "pacman"  when pacman is available
        None      when no supported package manager is found
    """

    if shutil.which("apt"):
        return PACKAGE_MANAGER_APT

    if shutil.which("pacman"):
        return PACKAGE_MANAGER_PACMAN

    return None


class AptPackageManager:
    """
    APT package manager implementation.
    """

    name = PACKAGE_MANAGER_APT

    def get_installed_packages(self):
        result = subprocess.run(
            [
                "dpkg-query",
                "-W",
                "-f=${binary:Package} ${Version}\n"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        packages = {}

        for line in result.stdout.splitlines():

            parts = line.split(" ", 1)

            if len(parts) == 2:

                package, version = parts

                packages[package] = version

        return packages

    def get_updates(self):
        env = os.environ.copy()
        env["LC_ALL"] = "C"

        result = subprocess.run(
            ["apt", "list", "--upgradable"],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )

        updates = []

        for line in result.stdout.splitlines():

            if "/" not in line:
                continue

            if "upgradable" not in line:
                continue

            parts = line.split()

            if len(parts) < 2:
                continue

            package_info = parts[0]
            available_version = parts[1]

            package = package_info.split("/")[0]

            installed_version = None

            if "upgradable from:" in line:

                installed_version = line.split(
                    "upgradable from:",
                    1
                )[1].strip().rstrip("]")

            updates.append({
                "package": package,
                "installed_version": installed_version,
                "available_version": available_version
            })

        return updates

    def get_package_state(self, package):
        result = subprocess.run(
            [
                "dpkg-query",
                "-W",
                "-f=${Status}|${Version}",
                package
            ],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()

        if result.returncode != 0:

            return {
                "installed": False,
                "status": None,
                "version": None,
                "raw": output
            }

        parts = output.split("|", 2)

        if len(parts) != 2:

            return {
                "installed": False,
                "status": output,
                "version": None,
                "raw": output
            }

        package_status = parts[0]
        version = parts[1]

        installed = (
            package_status == "install ok installed"
        )

        return {
            "installed": installed,
            "status": package_status,
            "version": version,
            "raw": output
        }

    def install_package(self, package):
        return [
            "apt-get",
            "install",
            "-y",
            package
        ]

    def remove_package(self, package):
        return [
            "apt-get",
            "remove",
            "-y",
            package
        ]

    def update_package(self, package):
        return [
            "apt-get",
            "install",
            "--only-upgrade",
            "-y",
            package
        ]

    def update_system(self):
        return [
            "apt-get",
            "upgrade",
            "-y"
        ]

    def search_packages(self, query, max_results=50):
        env = os.environ.copy()
        env["LC_ALL"] = "C"

        result = subprocess.run(
            [
                "apt-cache",
                "search",
                query,
            ],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )

        query_lower = query.strip().lower()

        packages = []

        for line in result.stdout.splitlines():

            if " - " not in line:
                continue

            package, description = line.split(
                " - ",
                1
            )

            package = package.strip()
            description = description.strip()

            if not package:
                continue

            package_lower = package.lower()

            if package_lower == query_lower:
                priority = 0
            elif package_lower.startswith(query_lower):
                priority = 1
            elif query_lower in package_lower:
                priority = 2
            else:
                priority = 3

            packages.append({
                "package": package,
                "version": None,
                "description": description,
                "_priority": priority,
            })

        packages.sort(
            key=lambda item: (
                item["_priority"],
                item["package"].lower(),
            )
        )

        packages = packages[:max_results]

        package_names = [
            package["package"]
            for package in packages
        ]

        if package_names:

            version_result = subprocess.run(
                [
                    "apt-cache",
                    "show",
                    *package_names,
                ],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )

            versions = {}

            current_package = None

            for line in version_result.stdout.splitlines():

                if line.startswith("Package: "):
                    current_package = line[
                        len("Package: "):
                    ].strip()

                elif (
                    current_package
                    and line.startswith("Version: ")
                    and current_package not in versions
                ):
                    versions[current_package] = line[
                        len("Version: "):
                    ].strip()

            for package in packages:
                package["version"] = versions.get(
                    package["package"]
                )

        for package in packages:
            package.pop("_priority", None)

        return packages

    def get_candidate_version(self, package):
        env = os.environ.copy()
        env["LC_ALL"] = "C"

        result = subprocess.run(
            [
                "apt-cache",
                "policy",
                package
            ],
            capture_output=True,
            text=True,
            env=env
        )

        for line in result.stdout.splitlines():

            line = line.strip()

            if line.startswith("Candidate:"):

                return line.split(
                    ":",
                    1
                )[1].strip()

        return None


class PacmanPackageManager:
    """
    pacman package manager implementation for Arch Linux.
    """

    name = PACKAGE_MANAGER_PACMAN

    def get_installed_packages(self):
        result = subprocess.run(
            [
                "pacman",
                "-Q"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        packages = {}

        for line in result.stdout.splitlines():

            parts = line.split(None, 1)

            if len(parts) == 2:

                package, version = parts

                packages[package] = version

        return packages

    def get_updates(self):
        result = subprocess.run(
            [
                "pacman",
                "-Qu"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        updates = []

        for line in result.stdout.splitlines():

            parts = line.split()

            if len(parts) < 2:
                continue

            package = parts[0]
            available_version = parts[1]

            updates.append({
                "package": package,
                "installed_version": None,
                "available_version": available_version
            })

        return updates

    def get_package_state(self, package):
        result = subprocess.run(
            [
                "pacman",
                "-Q",
                package
            ],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()

        if result.returncode != 0:

            return {
                "installed": False,
                "status": None,
                "version": None,
                "raw": output
            }

        parts = output.split(None, 1)

        if len(parts) != 2:

            return {
                "installed": False,
                "status": output,
                "version": None,
                "raw": output
            }

        return {
            "installed": True,
            "status": "installed",
            "version": parts[1],
            "raw": output
        }

    def install_package(self, package):
        return [
            "pacman",
            "-S",
            "--noconfirm",
            package
        ]

    def remove_package(self, package):
        return [
            "pacman",
            "-R",
            "--noconfirm",
            package
        ]

    def update_package(self, package):
        return [
            "pacman",
            "-S",
            "--noconfirm",
            package
        ]

    def update_system(self):
        return [
            "pacman",
            "-Syu",
            "--noconfirm"
        ]

    def search_packages(self, query, max_results=50):
        result = subprocess.run(
            [
                "pacman",
                "-Ss",
                query,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        packages = []
        lines = result.stdout.splitlines()
        query_lower = query.strip().lower()

        index = 0

        while index < len(lines):

            header = lines[index]

            if (
                not header.startswith(" ")
                and "/" in header
            ):

                parts = header.split()

                if len(parts) >= 2:

                    repository_package = parts[0]
                    version = parts[1]

                    repository, package = (
                        repository_package.split(
                            "/",
                            1
                        )
                    )

                    description = ""

                    if index + 1 < len(lines):

                        next_line = lines[index + 1]

                        if next_line.startswith("    "):
                            description = next_line.strip()
                            index += 1

                    package_lower = package.lower()

                    if package_lower == query_lower:
                        priority = 0
                    elif package_lower.startswith(query_lower):
                        priority = 1
                    elif query_lower in package_lower:
                        priority = 2
                    else:
                        priority = 3

                    packages.append({
                        "package": package,
                        "version": version,
                        "description": description,
                        "repository": repository,
                        "_priority": priority,
                    })

            index += 1

        packages.sort(
            key=lambda item: (
                item["_priority"],
                item["package"].lower(),
            )
        )

        packages = packages[:max_results]

        for package in packages:
            package.pop("_priority", None)

        return packages

    def get_candidate_version(self, package):
        result = subprocess.run(
            [
                "pacman",
                "-Si",
                package
            ],
            capture_output=True,
            text=True
        )

        for line in result.stdout.splitlines():

            line = line.strip()

            if line.startswith("Version"):

                parts = line.split(":", 1)

                if len(parts) == 2:

                    return parts[1].strip()

        return None
