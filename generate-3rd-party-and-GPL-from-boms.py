#!/usr/bin/env python3
import json
import sys
import re
from collections import defaultdict
from pathlib import Path

def load_spdx_files(paths):
    docs = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            docs.append(json.load(f))
    return docs

def normalize_license(lic):
    return lic.strip() if lic else "NOASSERTION"

def extract_license_text(lic):
    # Placeholder: in real case fetch from SPDX or local cache if needed
    return f"[License text for {lic} would go here]\n"

def is_gpl_license_expression(lic_expr):
    """
    Detect if the license expression includes any GPL variant.
    Match tokens like 'GPL-1.0', 'GPL-2.0-only', 'GPL-3.0-or-later'
    even inside complex expressions (AND/OR).
    """
    return bool(re.search(r"\bGPL-\d+(\.\d+)?", lic_expr))

def consolidate_notice(spdx_docs, output_path):
    # license_expression -> { 'packages': [(name, version)], 'text': license_text }
    license_groups = defaultdict(lambda: {"packages": [], "text": None})
    gpl_packages = []

    for doc in spdx_docs:
        doc = doc["predicate"]
        packages = doc.get("packages", [])
        for pkg in packages:
            name = pkg.get("name", "UNKNOWN")
            version = pkg.get("versionInfo", "")
            lic_expr = normalize_license(pkg.get("licenseDeclared"))
            license_groups[lic_expr]["packages"].append((name, version))

            if is_gpl_license_expression(lic_expr):
                gpl_packages.append((name, version, lic_expr))

    # Fetch license texts only once per license expression
    for lic_expr in license_groups:
        license_groups[lic_expr]["text"] = extract_license_text(lic_expr)

    # Write NOTICE file
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("NOTICE\n")
        out.write("======\n\n")

        for lic_expr, data in sorted(license_groups.items()):
            out.write(f"License: {lic_expr}\n")
            out.write("-" * (9 + len(lic_expr)) + "\n")
            for name, version in sorted(set(data["packages"])):
                out.write(f"- {name} {version}\n")
            out.write("\n")
            out.write(data["text"])
            out.write("\n\n")

        # GPL section
        out.write("PACKAGES SUBJECT TO GPL LICENSES (with licenses expression)\n")
        out.write("--------------------------------\n")
        for name, version, lic_expr in sorted(set(gpl_packages)):
            out.write(f"- {name} {version}  ({lic_expr})\n")

        # GPL section
        out.write("\n\nPACKAGES SUBJECT TO GPL LICENSES (w/o licenses expression)\n")
        out.write("--------------------------------\n")
        for name, version, lic_expr in sorted(set(gpl_packages)):
            out.write(f"{name} {version}\n")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <output_notice.txt> <spdx_file1.json> [<spdx_file2.json> ...]")
        sys.exit(1)

    output_file = sys.argv[1]
    spdx_files = sys.argv[2:]

    docs = load_spdx_files(spdx_files)
    consolidate_notice(docs, output_file)
