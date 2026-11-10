@echo off
chcp 936 >nul
rem ============================================================
rem  JlAgent 打包脚本
rem  使用 UnifyPy + Inno Setup 6 生成 Windows 安装包
rem
rem  用法：双击本文件，或在命令行运行 build_package.bat
rem  产物：dist\JlAgent.exe 与 installer\JlAgent-1.0.0-x86_64.exe
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
rem 打包脚本自身与 build.json 在 packaging/ 目录下，但
rem UnifyPy 必须在项目根目录运行，所以先记住脚本位置再回到上一级。
set "SCRIPT_DIR=%CD%"
cd ..

rem ---------- 可配置项（按需修改） ----------
set "UNIFYPY=D:\Python313\Scripts\unifypy.exe"
set "PYTHON=python"
set "ISCC=D:\无用软件\Inno Setup 6\ISCC.exe"
set "APP_VERSION=1.0.0"
set "CONFIG_FILE=%SCRIPT_DIR%\build.json"
set "BUILD_OPTS=--clean --verbose"
rem ------------------------------------------

echo [1/4] 检查依赖（textual / openai / trafilatura / pyinstaller）
"%PYTHON%" -c "import textual,openai,trafilatura,PyInstaller" 2>nul
if errorlevel 1 (
    echo      未安装或版本不全，正在安装 requirements.txt + pyinstaller ...
    "%PYTHON%" -m pip install -r requirements.txt pyinstaller
    if errorlevel 1 ( echo [错误] 依赖安装失败 & goto :fail )
    echo      依赖安装完成
) else (
    echo      依赖已就绪
)

echo [2/4] 检查 Inno Setup
if not exist "%ISCC%" (
    echo [错误] 找不到 Inno Setup：%ISCC%
    echo        请修改本脚本顶部的 ISCC 变量，指向 ISCC.exe
    goto :fail
)
echo      使用 %ISCC%

echo [3/4] 清理旧 spec（确保用最新 build.json 重新生成）
if exist "JlAgent.spec" del /q "JlAgent.spec"
if exist ".unifypy\cache" rmdir /q /s ".unifypy\cache"

echo [4/4] 调用 UnifyPy 打包（exe + Inno Setup 安装包）
"%UNIFYPY%" . --config "%CONFIG_FILE%" --app-version "%APP_VERSION%" ^
    --inno-setup-path "%ISCC%" %BUILD_OPTS%
if errorlevel 1 ( echo [错误] UnifyPy 打包失败 & goto :fail )

echo.
echo 打包完成。产物：
dir /b "dist"
dir /b "installer"
goto :eof

:fail
echo.
echo 打包未完成，请检查上方错误信息。
exit /b 1
