@echo off
chcp 65001 >nul
echo ============================================
echo AIDBTools Windows 打包脚本
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] 清理旧构建...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo 完成。
echo.

echo [2/3] 执行 PyInstaller 打包...
echo.
pyinstaller AIDBTools.spec --clean --noconfirm
echo.

echo [3/3] 检查结果...
if exist "dist\AIDBTools\AIDBTools.exe" (
    echo.
    echo ============================================
    echo 打包成功！
    echo exe 路径: dist\AIDBTools\AIDBTools.exe
    echo ============================================
) else (
    echo.
    echo 打包可能有问题，请检查上方输出。
)
echo.
pause
