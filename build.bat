@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ====================================
echo  AIDBTools Windows 打包
echo ====================================

:: ── 选择 Python 3.11 解释器（优先环境变量 AIDBTOOLS_PYTHON） ──
set "PYTHON_EXE="

if defined AIDBTOOLS_PYTHON (
    if exist "%AIDBTOOLS_PYTHON%" (
        set "PYTHON_EXE=%AIDBTOOLS_PYTHON%"
    ) else (
        echo [错误] AIDBTOOLS_PYTHON 指向的文件不存在。
        echo %AIDBTOOLS_PYTHON%
        pause
        endlocal
        exit /b 1
    )
)

if not defined PYTHON_EXE if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\aidbtools311\Scripts\python.exe" set "PYTHON_EXE=%USERPROFILE%\.workbuddy\binaries\python\envs\aidbtools311\Scripts\python.exe"
if not defined PYTHON_EXE if exist "D:\Python311\python.exe" set "PYTHON_EXE=D:\Python311\python.exe"
if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"

if not defined PYTHON_EXE (
    echo [错误] 未检测到 Python 3.11。
    echo 请先安装 Python 3.11。
    echo 或设置环境变量 AIDBTOOLS_PYTHON 指向 Python 3.11 解释器。
    pause
    endlocal
    exit /b 1
)

echo 使用 Python：%PYTHON_EXE%

:: ── 每次打包前自动递增补丁版本号 ──────────────────
set "VER="
set "VERSION_OUTPUT=%TEMP%\aidbtools_build_version_%RANDOM%%RANDOM%.txt"
"%PYTHON_EXE%" -c "from version import bump_patch_version; print(bump_patch_version())" > "%VERSION_OUTPUT%"
if errorlevel 1 (
    if exist "%VERSION_OUTPUT%" del /q "%VERSION_OUTPUT%" >nul 2>&1
    echo [错误] 生成版本号失败。
    pause
    endlocal
    exit /b 1
)
set /p VER=<"%VERSION_OUTPUT%"
if exist "%VERSION_OUTPUT%" del /q "%VERSION_OUTPUT%" >nul 2>&1
if not defined VER (
    echo [错误] 生成版本号失败。
    pause
    endlocal
    exit /b 1
)

echo 本次构建版本：%VER%

:: ── 设置输出目录 ──────────────────────────────────
set DIST_DIR=release\windows\v%VER%
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

:: ── 写入平台标识到 version.py ──────────────────────
"%PYTHON_EXE%" -c "from version import set_build_platform; set_build_platform('windows'); print('  [OK] BUILD_PLATFORM = windows')"

:: ── 运行 PyInstaller（默认按 Python 3.11 打包；保留高版本 JPype 扫描兜底） ──
"%PYTHON_EXE%" build_pyinstaller.py --clean AIDBTools.spec

if errorlevel 1 (
    echo [错误] 打包失败！
    goto restore
)

:: ── 复制产物到分版本目录 ──────────────────────────
copy /Y "dist\AIDBTools.exe" "%DIST_DIR%\AIDBTools_v%VER%_windows.exe"
echo [OK] 产物已复制到：%DIST_DIR%\AIDBTools_v%VER%_windows.exe

:restore
:: ── 恢复 BUILD_PLATFORM 为 source ─────────────────
"%PYTHON_EXE%" -c "from version import set_build_platform; set_build_platform('source'); print('  [OK] BUILD_PLATFORM 已恢复为 source')"

echo.
echo 打包完成！输出目录：%DIST_DIR%
pause
endlocal
