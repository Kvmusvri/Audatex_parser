@echo off
echo Redis Manager для Audotex Parser
echo.

if "%1"=="start" (
    echo Запуск Redis...
    cd /d C:\redis
    start /B redis-server.exe redis.windows.conf
    echo Redis запущен в фоновом режиме
    goto :end
)

if "%1"=="stop" (
    echo Остановка Redis...
    taskkill /f /im redis-server.exe 2>nul
    echo Redis остановлен
    goto :end
)

if "%1"=="status" (
    echo Проверка статуса Redis...
    cd /d C:\redis
    redis-cli.exe ping
    goto :end
)

if "%1"=="install" (
    echo Установка Redis как службы...
    cd /d C:\redis
    redis-server.exe --service-install redis.windows-service.conf
    echo Redis установлен как служба
    goto :end
)

if "%1"=="uninstall" (
    echo Удаление службы Redis...
    sc delete Redis 2>nul
    echo Служба Redis удалена
    goto :end
)

echo Использование: redis_manager.bat [команда]
echo.
echo Команды:
echo   start     - Запустить Redis в фоновом режиме
echo   stop      - Остановить Redis
echo   status    - Проверить статус Redis
echo   install   - Установить Redis как службу Windows
echo   uninstall - Удалить службу Redis
echo.

:end
pause 