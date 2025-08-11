#!/usr/bin/env python3
import json
import sys
import os
from collections import defaultdict

def load_spdx(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def extract_packages(spdx_data):
    packages = []
    spdx_data = spdx_data["predicate"]
    for doc in (spdx_data if isinstance(spdx_data, list) else [spdx_data]):
        for pkg in doc.get("packages", []):
            name = pkg.get("name")
            version = pkg.get("versionInfo", "")
            license_id = pkg.get("licenseDeclared") or pkg.get("licenseConcluded") or "NOASSERTION"
            license_text = None

            # SPDX may have extracted license texts in "hasExtractedLicensingInfo"
            # but not always; map by licenseId for lookup
            license_lookup = {}
            for lic in doc.get("hasExtractedLicensingInfo", []):
                license_lookup[lic.get("licenseId")] = lic.get("extractedText")

            if license_id in license_lookup:
                license_text = license_lookup[license_id]

            packages.append({
                "name": name,
                "version": version,
                "license": license_id,
                "license_text": license_text
            })
    return packages

def consolidate(spdx_files):
    license_groups = defaultdict(lambda: {"deps": [], "license_text": None})

    for file_path in spdx_files:
        data = load_spdx(file_path)
        pkgs = extract_packages(data)
        for pkg in pkgs:
            lic = pkg["license"]
            license_groups[lic]["deps"].append(f"{pkg['name']} {pkg['version']}".strip())
            if not license_groups[lic]["license_text"] and pkg["license_text"]:
                license_groups[lic]["license_text"] = pkg["license_text"]

    return license_groups

def write_notice(license_groups, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("THIRD-PARTY NOTICE FILE\n")
        f.write("=======================\n\n")
        f.write("This file lists third-party software included in this distribution,\n")
        f.write("grouped by license. License texts are included once per license.\n\n")

        for lic in sorted(license_groups.keys()):
            group = license_groups[lic]
            f.write(f"--- {lic} ---\n")
            for dep in sorted(set(group["deps"])):
                f.write(f"  - {dep}\n")
            f.write("\n")
            if group["license_text"]:
                f.write(group["license_text"].strip() + "\n\n")
            else:
                f.write("[License text not available]\n\n")

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <output_notice.txt> <spdx_file1.json> [<spdx_file2.json> ...]")
        sys.exit(1)

    output_file = sys.argv[1]
    spdx_files = sys.argv[2:]

    license_groups = consolidate(spdx_files)
    write_notice(license_groups, output_file)
    print(f"NOTICE file generated: {output_file}")

if __name__ == "__main__":
    main()
