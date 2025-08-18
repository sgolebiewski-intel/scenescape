import csv
from collections import defaultdict

input_file = "SceneScape-1.4.0-deps.csv"
output_file = "third-party-programs-new.txt"

components = []
licenses = set()
license_to_components = defaultdict(list)

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

# Write to output file with 2 blank lines before and 1 after each section
with open(output_file, "w", encoding="utf-8") as f:
    for idx, lic in enumerate(licenses_sorted, 1):
        f.write("\n\n")  # 2 blank lines before
        f.write("-------------------------------------------------------------\n")
        f.write(f"{idx}. Software released under the license {lic}:\n")
        for comp in license_to_components[lic]:
            f.write(f"    {comp}\n")
        f.write("\n")  # 1 blank line after

print(f"Generated {output_file}")
