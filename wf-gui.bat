@echo off
chcp 65001 >nul
REM ============================================================
REM  WF 网页修改器启动脚本
REM  第一次用:复制 profiles.example.json 为 profiles.json,按你的
REM  服务端目录改路径(store / cdndata);或用下面的环境变量指路。
REM ============================================================

REM ---- 按需改这几行(用绝对路径),或改用 profiles.json ----
REM set WF_TARGET_STORE=D:\你的路径\WorldFlipper\dummy\download\production\upload
REM set WF_CDNDATA=D:\你的服务端\assets\cdndata
REM set WF_CDN_DIR=D:\你的服务端\.cdn\cn
REM set WF_VOICE_DUMP=D:\你的语音dump目录
REM set WF_GUI_PORT=8765

python "%~dp0wf_gui.py"
pause
