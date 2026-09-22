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

    This class currently provides read-only package information.
    Package installation, removal and update operations will be
    added in later steps.
    """

    name = PACKAGE_MANAGER_APT

    def get_installed_packages(self):
        """
        Return installed packages as:

            {
                "package": "version"
            }
        """

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
        """
        Return packages for which an update is available.
        """

        env = os.environ.copy()
        env["LC_ALL"] = "C"

        result = subprocess.run(
            ["apt", "list", "--upgradable"],
            capture_output=True,
            text=True,
            env=env
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
        """
        Return the installed state of one package.
        """

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
        """
        Build the APT command for installing a package.

        This method does not execute the command.
        Execution remains the responsibility of the agent/job layer.
        """

        return [
            "apt-get",
            "install",
            "-y",
            package
        ]

    def remove_package(self, package):
        """
        Build the APT command for removing a package.

        This method does not execute the command.
        Execution remains the responsibility of the agent/job layer.
        """

        return [
            "apt-get",
            "remove",
            "-y",
            package
        ]

    def update_package(self, package):
        """
        Build the APT command for updating an installed package.

        This method does not execute the command.
        Execution remains the responsibility of the agent/job layer.
        """

        return [
            "apt-get",
            "install",
            "--only-upgrade",
            "-y",
            package
        ]

    def update_system(self):
        """
        Build the APT command for updating the complete system.

        This method does not execute the command.
        Execution remains the responsibility of the agent/job layer.
        """

        return [
            "apt-get",
            "upgrade",
            "-y"
        ]

    def get_candidate_version(self, package):
        """
        Return the currently available APT candidate version.
        """

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
