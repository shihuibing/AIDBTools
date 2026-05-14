@echo off
chcp 65001 >nul
setlocal

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

"%PYTHON_EXE%" main.py
pause
endlocal
