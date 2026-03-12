@echo off
:: ============================================================
:: ENSMG Archives — Script d'initialisation du projet
:: À exécuter UNE SEULE FOIS après avoir récupéré le projet.
:: ============================================================

echo.
echo  ============================================
echo   ENSMG — Initialisation du système d'archives
echo  ============================================
echo.

:: Activation du venv
call venv\Scripts\activate

echo [1/4] Création des migrations...
python manage.py makemigrations users archives
if errorlevel 1 (
    echo ERREUR lors de la création des migrations.
    pause
    exit /b 1
)

echo.
echo [2/4] Application des migrations...
python manage.py migrate
if errorlevel 1 (
    echo ERREUR lors de l'application des migrations.
    pause
    exit /b 1
)

echo.
echo [3/4] Collecte des fichiers statiques...
python manage.py collectstatic --noinput

echo.
echo [4/4] Création du superutilisateur (admin)...
python manage.py createsuperuser

echo.
echo  ============================================
echo   Initialisation terminée avec succès !
echo.
echo   Lancez le serveur avec :
echo     venv\Scripts\activate
echo     python manage.py runserver
echo.
echo   Accédez à l'interface admin sur :
echo     http://127.0.0.1:8000/admin/
echo  ============================================
echo.
pause
