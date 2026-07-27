import pyautogui
import time
import os

print("🎯 [실시간 좌표 추적기]를 시작합니다.")
print("화면에서 밴픽 창이나 챔피언 초상화가 있는 곳에 마우스를 올려보세요.")
print("종료하려면 까만 창(터미널)을 클릭하고 Ctrl + C 를 누르세요.\n")
print(" X좌표 | Y좌표")
print("-" * 15)

try:
    while True:
        # 현재 마우스의 X, Y 좌표 가져오기
        x, y = pyautogui.position()
        
        # \r을 써서 줄바꿈 없이 한 줄에서 숫자가 실시간으로 바뀌게 합니다.
        print(f"  {str(x).rjust(4)} | {str(y).rjust(4)}", end="\r")
        time.sleep(0.1) # 0.1초마다 갱신
        
except KeyboardInterrupt:
    print("\n👋 좌표 추적기를 종료합니다.")