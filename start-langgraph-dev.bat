@echo off
echo Starting LangGraph Dev Server on port 8123...
echo.

:: Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

:: Run langgraph dev command
uv run langgraph dev --port 8123

:: Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Error occurred. Press any key to exit...
    pause >nul
)