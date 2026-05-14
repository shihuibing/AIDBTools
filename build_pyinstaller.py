import os
import sys

import PyInstaller.__main__
import PyInstaller.building.build_main as build_main


def apply_windows_jpype_workaround():
    """Windows 下为高版本 Python 打包提供 JPype 依赖扫描兜底。"""
    if os.name != "nt" or sys.version_info < (3, 13):
        return False


    original = build_main.find_binary_dependencies

    def patched(binaries, import_packages, symlink_suppression_patterns):
        filtered_packages = [pkg for pkg in import_packages if pkg != "jpype"]
        return original(binaries, filtered_packages, symlink_suppression_patterns)

    build_main.find_binary_dependencies = patched
    return True


def main():
    args = sys.argv[1:] or ["--clean", "AIDBTools.spec"]
    if apply_windows_jpype_workaround():
        print("[INFO] 已启用 Windows 高版本 Python 的 JPype 打包兜底逻辑")

    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
