#!/bin/bash
# mm.sh shot NAME | tap X Y | cmd "..."
MM=D:/WF/MuMuPlayer/nx_main/MuMuManager.exe
PHY=4619826888814064386; LOG=2
case "$1" in
  shot) "$MM" sh -v 1 -c "screencap -d $PHY -p /sdcard/Pictures/c_$2.png; echo" >/dev/null; echo "~/Documents/MuMu共享文件夹/Pictures/c_$2.png";;
  tap) "$MM" sh -v 1 -c "input -d $LOG tap $2 $3; echo" >/dev/null;;
  swipe) "$MM" sh -v 1 -c "input -d $LOG swipe $2 $3 $4 $5 ${6:-300}; echo" >/dev/null;;
  cmd) "$MM" sh -v 1 -c "$2; echo";;
esac
