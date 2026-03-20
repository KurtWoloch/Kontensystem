@echo off
cd /d C:\Users\kurt_\.openclaw\workspace\kontensystem\tools
set PYTHONIOENCODING=utf-8
python autodetect_audit.py %* > autodetect_result.txt 2>&1
echo Ergebnis gespeichert in: %cd%\autodetect_result.txt
pause
