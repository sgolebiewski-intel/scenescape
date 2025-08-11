#!/usr/bin/env python3
"""
Generate grouped NOTICE file and SPDX SBOM for:
- Python packages (pip)
- Node.js packages (npm)
- Ubuntu/Debian system packages

Requirements:
    pip install pip-licenses
    npm install -g license-checker
    (Ubuntu/Debian package tools: dpkg, apt-cache)
"""

import subprocess
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys
import os

OUTPUT_NOTICE = Path("THIRD_PARTY_NOTICE.txt")
OUTPUT_SPDX = Path("SBOM.spdx")


# --------------------------
# Python dependencies
# --------------------------
def get_python_dependencies():
    deps = []
    try:
        result = subprocess.run(
            ["pip-licenses", "--format=json", "--with-license-file", "--with-url"],
            capture_output=True, check=True, text=True
        )
        for dep in json.loads(result.stdout):
            deps.append({
                "ecosystem": "Python",
                "name": dep["Name"],
                "version": dep["Version"],
                "license": dep["License"] or "NOASSERTION",
                "url": dep.get("URL", "NOASSERTION"),
                "license_file": dep.get("LicenseFile", None)
            })
    except FileNotFoundError:
        print("⚠ Skipping Python scan (pip-licenses not installed).")
    except subprocess.CalledProcessError:
        print("⚠ Error running pip-licenses.")
    return deps


# --------------------------
# Node.js dependencies
# --------------------------
def get_npm_dependencies():
    deps = []
    try:
        result = subprocess.run(
            ["license-checker", "--json"],
            capture_output=True, check=True, text=True
        )
        data = json.loads(result.stdout)
        for pkg, info in data.items():
            name, _, version = pkg.partition("@")
            deps.append({
                "ecosystem": "npm",
                "name": name,
                "version": info.get("version", version),
                "license": info.get("licenses", "NOASSERTION"),
                "url": info.get("repository", "NOASSERTION"),
                "license_file": info.get("licenseFile", None)
            })
    except FileNotFoundError:
        print("⚠ Skipping npm scan (license-checker not installed).")
    except subprocess.CalledProcessError:
        print("⚠ Error running license-checker.")
    return deps


# --------------------------
# Ubuntu/Debian packages
# --------------------------
def get_ubuntu_dependencies():
    deps = []
    try:
        dpkg_result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package} ${Version}\n"],
            capture_output=True, check=True, text=True
        )
        for line in dpkg_result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            pkg, version = line.split(maxsplit=1)
            # Try to get license info from apt-cache
            lic = "NOASSERTION"
            homepage = "NOASSERTION"
            try:
                showpkg = subprocess.run(
                    ["apt-cache", "show", pkg],
                    capture_output=True, check=True, text=True
                ).stdout
                for l in showpkg.splitlines():
                    if l.lower().startswith("homepage:"):
                        homepage = l.split(":", 1)[1].strip()
                    if "license" in l.lower():
                        lic = l.split(":", 1)[1].strip()
            except subprocess.CalledProcessError:
                pass
            deps.append({
                "ecosystem": "Ubuntu",
                "name": pkg,
                "version": version,
                "license": lic,
                "url": homepage,
                "license_file": None
            })
    except FileNotFoundError:
        print("⚠ Skipping Ubuntu scan (dpkg-query not available).")
    except subprocess.CalledProcessError:
        print("⚠ Error running dpkg-query.")
    return deps


# --------------------------
# NOTICE generation
# --------------------------
def generate_notice(dependencies):
    grouped = defaultdict(list)
    license_texts = {}

    for dep in dependencies:
        lic = dep["license"]
        grouped[lic].append(dep)
        if lic not in license_texts and dep.get("license_file") and dep["license_file"] and os.path.exists(dep["license_file"]):
            try:
                license_texts[lic] = Path(dep["license_file"]).read_text(encoding="utf-8", errors="replace")
            except Exception:
                license_texts[lic] = f"(License text for {lic} not available)"

    lines = []
    lines.append("="*79)
    lines.append("Third-Party Software and Licenses")
    lines.append("="*79)
    lines.append(f"Generated on: {datetime.utcnow().isoformat()} UTC\n")
    lines.append("This software package includes third-party components grouped by license.\n")

    for lic, deps in sorted(grouped.items()):
        lines.append("-" * 79)
        lines.append(f"License: {lic}")
        lines.append("Components:")
        for dep in sorted(deps, key=lambda d: (d["ecosystem"], d["name"].lower())):
            lines.append(f"  - [{dep['ecosystem']}] {dep['name']} {dep['version']} ({dep['url']})")
        lines.append("\nLicense text:")
        lines.append("-" * 79)
        lines.append(license_texts.get(lic, f"(No license text available for {lic})"))
        lines.append("")

    OUTPUT_NOTICE.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ NOTICE file written to {OUTPUT_NOTICE}")


# --------------------------
# SPDX generation
# --------------------------
def generate_spdx(dependencies):
    lines = []
    lines.append("SPDXVersion: SPDX-2.3")
    lines.append("DataLicense: CC0-1.0")
    lines.append(f"Created: {datetime.utcnow().isoformat()}Z")
    lines.append("Creator: Tool: multi-ecosystem-license-scanner")
    lines.append("")

    for dep in sorted(dependencies, key=lambda d: (d["ecosystem"], d["name"].lower())):
        lic_id = dep["license"] if dep["license"] else "NOASSERTION"
        lines.append(f"PackageName: {dep['name']}")
        lines.append(f"PackageVersion: {dep['version']}")
        lines.append(f"PackageSupplier: Organization: {dep['ecosystem']}")
        lines.append(f"PackageLicenseDeclared: {lic_id}")
        lines.append(f"PackageDownloadLocation: {dep.get('url', 'NOASSERTION')}")
        lines.append("")

    OUTPUT_SPDX.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ SPDX SBOM written to {OUTPUT_SPDX}")


# --------------------------
# Main
# --------------------------
if __name__ == "__main__":
    deps = []
    deps.extend(get_python_dependencies())
    deps.extend(get_npm_dependencies())
    deps.extend(get_ubuntu_dependencies())

    if not deps:
        print("No dependencies found.")
        sys.exit(0)

    generate_notice(deps)
    generate_spdx(deps)
