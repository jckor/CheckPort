@echo off
cd /d C:\Users\jchor\Code
if not exist data mkdir data
if not exist logs mkdir logs

C:\Users\jchor\AppData\Local\Programs\Python\Python313\python.exe run_daily.py >> logs\checkport.log 2>&1
