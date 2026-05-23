@echo off
echo.
echo  Starting AI server - Gemma 4 E2B
start cmd /k "C:\llama\llama-server.exe -m C:\llama\models\gemma-4-E2B-it-Q4_K_M.gguf --port 8080 -c 6144"
pause
