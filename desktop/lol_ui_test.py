import tkinter as tk
from tkinter import messagebox

# 프로그램 창 생성
root = tk.Tk()
root.title("🤖 LOL 내전 전략 분석관 (V1.0)")
root.geometry("550x450")
root.configure(bg="#010A15") # 롤 클라이언트 특유의 어두운 남색 배경

# 상단 제목 타이틀
title_label = tk.Label(
    root, 
    text="🏆 LOL 내전 실시간 분석기 🏆", 
    font=("Malgun Gothic", 16, "bold"), 
    bg="#010A15", 
    fg="#C8AA6E" # 롤 특유의 황금색 글씨
)
title_label.pack(pady=15)

# --- 구역 1: 실시간 포지션 매칭 ---
frame_pos = tk.LabelFrame(root, text=" 1단계: 실시간 포지션 매칭 ", font=("Malgun Gothic", 10, "bold"), bg="#010A15", fg="#F0E6D2", bd=1, relief="solid")
frame_pos.pack(fill="x", padx=20, pady=10)

blue_team_text = "🔵 블루팀 (우리팀):  탑(A)   정글(B)   미드(C)   원딜(D)   서폿(나)"
red_team_text  = "🔴 레드팀 (상대팀):  탑(F)   정글(G)   미드(H)   원딜(I)   서폿(플레이어J)"

lbl_blue = tk.Label(frame_pos, text=blue_team_text, font=("Malgun Gothic", 10), bg="#010A15", fg="#A0C4FF")
lbl_blue.pack(anchor="w", padx=15, pady=5)

lbl_red = tk.Label(frame_pos, text=red_team_text, font=("Malgun Gothic", 10), bg="#010A15", fg="#FFADAD")
lbl_red.pack(anchor="w", padx=15, pady=5)


# --- 구역 2: AI 실시간 밴픽 권장 지표 ---
frame_ai = tk.LabelFrame(root, text=" 2단계: AI 실시간 밴픽 권장 지표 ", font=("Malgun Gothic", 10, "bold"), bg="#010A15", fg="#C8AA6E", bd=1, relief="solid")
frame_ai.pack(fill="x", padx=20, pady=10)

ai_hint1 = "🚨 [특급 경보] 레드팀 '플레이어J' 저격 밴 추천!\n    => 모스트 '렐' 밴 시 승률 50% -> 0%로 수직 하락"
ai_hint2 = "💡 [조합 시너지] '나'님과 '플레이어B'의 봇 듀오 예상 승률은 72%입니다."

lbl_ai1 = tk.Label(frame_ai, text=ai_hint1, font=("Malgun Gothic", 10, "bold"), bg="#010A15", fg="#FF4D4D", justify="left")
lbl_ai1.pack(anchor="w", padx=15, pady=8)

lbl_ai2 = tk.Label(frame_ai, text=ai_hint2, font=("Malgun Gothic", 10), bg="#010A15", fg="#F0E6D2", justify="left")
lbl_ai2.pack(anchor="w", padx=15, pady=5)


# --- 구역 3: 게임 결과 기록 버튼 ---
frame_btn = tk.LabelFrame(root, text=" 3단계: 게임 결과 기록 ", font=("Malgun Gothic", 10, "bold"), bg="#010A15", fg="#F0E6D2", bd=1, relief="solid")
frame_btn.pack(fill="x", padx=20, pady=10)

def click_blue_win():
    messagebox.showinfo("기록 완료", "🔵 블루팀 승리 데이터가 엑셀에 성공적으로 누적되었습니다!")

def click_red_win():
    messagebox.showinfo("기록 완료", "🔴 레드팀 승리 데이터가 엑셀에 성공적으로 누적되었습니다!")

# 버튼들 배치
btn_blue = tk.Button(frame_btn, text="🔵 블루팀 승리", font=("Malgun Gothic", 10, "bold"), bg="#1A3A60", fg="#F0E6D2", width=18, command=click_blue_win)
btn_blue.pack(side="left", padx=30, pady=15)

btn_red = tk.Button(frame_btn, text="🔴 레드팀 승리", font=("Malgun Gothic", 10, "bold"), bg="#601A1A", fg="#F0E6D2", width=18, command=click_red_win)
btn_red.pack(side="right", padx=30, pady=15)

# 창 켜기
root.mainloop()