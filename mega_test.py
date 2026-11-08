try:
    import customtkinter as ctk
except ImportError:
    import subprocess
    import sys
    print("[알림] customtkinter 라이브러리가 없어 자동 설치를 진행합니다...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

# 메가커피풍 컬러 팔레트
MEGA_YELLOW = "#FAD232"
MEGA_ORANGE = "#F39C12"
DARK_BROWN = "#3E2723"

class MegaKiosk(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("보다수 커피 - 메가커피 스타일")
        self.geometry("900x600")
        self.configure(fg_color=MEGA_YELLOW) # 쨍한 노란색 배경

        # 1. 상단 타이틀
        title_label = ctk.CTkLabel(self, text="Easy KIOSK", font=("Malgun Gothic", 24, "bold"), text_color=DARK_BROWN)
        title_label.pack(pady=15)

        # 2. 카테고리 탭 (검은/갈색 버튼)
        tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        tab_frame.pack(fill="x", padx=20, pady=5)
        
        categories = ["티", "커피(콜드브루)", "음료", "디저트", "병음료"]
        for i, cat in enumerate(categories):
            # 첫 번째 탭만 어둡게, 나머지는 주황색으로
            btn_color = DARK_BROWN if i == 0 else MEGA_ORANGE 
            btn = ctk.CTkButton(tab_frame, text=cat, fg_color=btn_color, text_color="white", corner_radius=20, width=120, height=40, font=("Malgun Gothic", 15, "bold"))
            btn.pack(side="left", padx=5)

        # 3. 메뉴 카드 그리드 (둥근 모서리의 하얀색 프레임)
        menu_frame = ctk.CTkFrame(self, fg_color="transparent")
        menu_frame.pack(expand=True, fill="both", padx=20, pady=10)

        # 샘플 메뉴 데이터
        dummy_menus = [
            ("복숭아아이스티", "3,000원"), ("(ICE)허니자몽블랙티", "3,500원"),
            ("(ICE)사과유자차", "3,500원"), ("(ICE)유자차", "3,000원"),
            ("(ICE)자몽차", "3,000원")
        ]

        # 반복문으로 하얀색 메뉴 카드 5개 생성
        for i, (name, price) in enumerate(dummy_menus):
            card = ctk.CTkFrame(menu_frame, fg_color="white", corner_radius=15, width=150, height=190)
            card.grid(row=0, column=i, padx=10, pady=10)
            card.grid_propagate(False) # 카드 크기를 고정
            card.pack_propagate(False) # 내부 위젯 pack 시 카드 크기 고정

            # 이미지 들어갈 자리 (임시 회색 박스)
            img_placeholder = ctk.CTkFrame(card, fg_color="#E0E0E0", width=100, height=100, corner_radius=10)
            img_placeholder.pack(pady=10)
            
            # 메뉴명 (검은색)
            name_label = ctk.CTkLabel(card, text=name, font=("Malgun Gothic", 13, "bold"), text_color="black")
            name_label.pack()
            
            # 가격 (빨간색)
            price_label = ctk.CTkLabel(card, text=price, font=("Malgun Gothic", 15, "bold"), text_color="#D32F2F")
            price_label.pack()

if __name__ == "__main__":
    app = MegaKiosk()
    app.mainloop()