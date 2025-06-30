#!/usr/bin/env python3
import subprocess


def main():

    cmd_find_py_files = ["find", ".", "-path", "*.py"]
    cmd_find_files_with_shebang = ["grep", "-rwl", ".", "-e", "#!/usr/bin/env python3"]

    files_with_py_extension = subprocess.run(cmd_find_py_files, stdout=subprocess.PIPE)
    files_with_shebang = subprocess.run(
        cmd_find_files_with_shebang, stdout=subprocess.PIPE
    )
    python_files_without_extension = subprocess.run(
        ["grep", "-v", "\\.py$"], input=files_with_shebang.stdout, stdout=subprocess.PIPE
    )

    all_python_files = files_with_py_extension.stdout.decode(
        "utf-8"
    ) + python_files_without_extension.stdout.decode("utf-8")

    print(all_python_files)


if __name__ == "__main__":
    exit(main() or 0)
