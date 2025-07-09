#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import subprocess


def main():

    cmd_find_sh_files = ["find", ".", "-path", "*.sh"]
    cmd_find_files_with_shebang = ["grep", "-rwl", ".", "-e", "#!/bin/bash"]

    shell_scripts_with_sh_extension = subprocess.run(cmd_find_sh_files, stdout=subprocess.PIPE)
    shell_scripts_with_shebang = subprocess.run(
        cmd_find_files_with_shebang, stdout=subprocess.PIPE
    )
    shell_scripts_without_extension = subprocess.run(
        ["grep", "-Ev", "(\\.sh$)|(\\.py$)|(\\.log$)|(Dockerfile)"],
        input=shell_scripts_with_shebang.stdout,
        stdout=subprocess.PIPE,
    )

    all_shell_scripts = shell_scripts_with_sh_extension.stdout.decode(
        "utf-8"
    ) + shell_scripts_without_extension.stdout.decode("utf-8")

    print(all_shell_scripts)


if __name__ == "__main__":
    exit(main() or 0)