import csv
from collections import defaultdict
import requests

input_file = "SceneScape-1.4.0-deps.csv"
output_file = "third-party-programs-new.txt"

components = []
licenses = set()
license_to_components = defaultdict(list)
failed_licenses = []

def get_license_url(license_name):
    # SPDX and other known mappings
    spdx_base = "https://spdx.org/licenses/"
    custom_map = {
        "AFL-2.1 License": spdx_base + "AFL-2.1.txt",
        "Apache-2.0": spdx_base + "Apache-2.0.txt",
        "Apache-2.1": "https://opensource.org/license/apache-2-1/",
        "Artistic License": spdx_base + "Artistic-2.0.txt",
        "Artistic License 1.0": spdx_base + "Artistic-1.0.txt",
        "Bitstream Vera License": "https://www.gnome.org/fonts/#Final_Bitstream_Vera_Fonts",
        "BSD License": spdx_base + "BSD-3-Clause.txt",
        "BSD-2-Clause": spdx_base + "BSD-2-Clause.txt",
        "BSD-3-Clause": spdx_base + "BSD-3-Clause.txt",
        "collection of licenses": "",
        "Eclipse Public License 2.0 OR\nEclipse Distribution License 1.0": "https://www.eclipse.org/legal/epl-2.0/",
        "EPL-1.0": spdx_base + "EPL-1.0.txt",
        "EPL-2.0": spdx_base + "EPL-2.0.txt",
        "FTL": spdx_base + "FTL.txt",
        "GPL-1.0": spdx_base + "GPL-1.0-only.txt",
        "GPL-2.0": spdx_base + "GPL-2.0-only.txt",
        "GPL-3.0": spdx_base + "GPL-3.0-only.txt",
        "HPND": spdx_base + "HPND.txt",
        "ICU License": "https://opensource.org/license/icu/",
        "Intel End User License": "",
        "Intel End User License Agreement for Developer Tools": "",
        "Intel Simplified Software License": "",
        "ISC": spdx_base + "ISC.txt",
        "ISC License": spdx_base + "ISC.txt",
        "JBIG License": spdx_base + "JBIG.txt",
        "LGPL": spdx_base + "LGPL-2.1-only.txt",
        "LGPL-2.0": spdx_base + "LGPL-2.0-only.txt",
        "LGPL-2.1": spdx_base + "LGPL-2.1-only.txt",
        "LGPL-3.0": spdx_base + "LGPL-3.0-only.txt",
        "libpng License": spdx_base + "Libpng.txt",
        "MIT": spdx_base + "MIT.txt",
        "MPL-1.1": spdx_base + "MPL-1.1.txt",
        "MPL-2.0": spdx_base + "MPL-2.0.txt",
        "OpenLDAP Public License": spdx_base + "OLDAP-2.8.txt",
        "PIL": "https://spdx.org/licenses/HPND.txt",  # PIL uses HPND
        "PostgreSQL": spdx_base + "PostgreSQL.txt",
        "PSF": spdx_base + "Python-2.0.txt",
        "Public Domain": "",
        "Qhull License": "https://github.com/qhull/qhull/blob/master/COPYING.txt",
        "SIL Open Font License": spdx_base + "OFL-1.1.txt",
        "The Regents of The University of Michigan": "",
        "Unlicense": spdx_base + "Unlicense.txt",
        "X11": spdx_base + "X11.txt",
        "Xkcense": "",
    }
    return custom_map.get(license_name, "")

def download_license_text(license_name):
    url = get_license_url(license_name)
    if not url:
        failed_licenses.append(license_name)
        return f"[No license text available for {license_name}]"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text
        else:
            failed_licenses.append(license_name)
            return f"[Failed to download license text for {license_name} from {url}]"
    except Exception as e:
        failed_licenses.append(license_name)
        return f"[Error downloading license text for {license_name}: {e}]"

with open(input_file, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        component = row["Component"].strip()
        license_ = row["License"].strip()
        components.append((component, license_))
        if license_:
            # Split on "and", "or", "OR", "," etc. to handle multi-license fields
            for lic in [l.strip() for l in license_.replace(" and ", ",").replace(" or ", ",").replace(" OR ", ",").split(",")]:
                if lic:
                    licenses.add(lic)
                    license_to_components[lic].append(component)

# Sort licenses and components
licenses_sorted = sorted(licenses, key=lambda x: x.lower())
for lic in licenses_sorted:
    license_to_components[lic] = sorted(set(license_to_components[lic]), key=lambda x: x.lower())

# Write to output file with 2 blank lines before and 1 after each section, and include license text
with open(output_file, "w", encoding="utf-8") as f:
    for idx, lic in enumerate(licenses_sorted, 1):
        f.write("\n\n")  # 2 blank lines before
        f.write("-------------------------------------------------------------\n")
        f.write(f"{idx}. Software released under the license {lic}:\n")
        for comp in license_to_components[lic]:
            f.write(f"    {comp}\n")
        f.write("\n")  # 1 blank line after
        # Add license text
        license_text = download_license_text(lic)
        f.write(license_text.strip() + "\n")

# Output list of all licenses without duplicates to stdout
print("Unique licenses used:")
for lic in licenses_sorted:
    print(f" - {lic}")

if failed_licenses:
    print("\nFailed to download license text for the following licenses:")
    for lic in sorted(set(failed_licenses)):
        print(f" - {lic}")

print(f"\nGenerated {output_file}")
