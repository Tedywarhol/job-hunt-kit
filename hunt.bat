@echo off
chcp 65001 >nul
title Job-Hunt Kit — Assistant Candidature

REM Verification de l'installation de Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo [ERREUR] Python n'est pas installe ou n'est pas dans le PATH.
    echo Rendez-vous sur https://www.python.org/downloads/ pour l'installer.
    echo N'oubliez pas de cocher "Add Python to PATH" lors de l'installation.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

REM Lancement direct du menu interactif
python hunt.py %*
if %errorlevel% neq 0 (
    pause
)
