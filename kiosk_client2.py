"""
[김밥나라 키오스크 클라이언트 - kiosk_client2.py]
- 매장 코드: KIOSK_02 (김밥나라 / 김밥천국)
- 디자인 컨셉: "Cream Ivory & Tomato Red – Modern Korean Snack Bar" (밝고 세련된 프리미엄 분식 키오스크)
- 레이아웃: 좌측 68% (크림 화이트 헤더, 샌드 베이지 배너, 토마토 레드 카테고리 탭, 메뉴 개수 안내, 3열 메뉴 그리드)
            우측 32% (내 주문 헤더, 매장식사/포장 탭, 담긴 목록, 수량 조절, 수저 옵션, 합산 금액, 머스터드 골드 주문 확인 버튼)
- 컬러 팔레트:
    * 전체 배경: #FFF9F2 (따뜻한 크림 아이보리)
    * 메뉴 영역: #FFF5EC (부드러운 크림)
    * 카드 배경: #FFFFFF (순백색)
    * 배너 배경: #F4E8DA (샌드 베이지)
    * 아이콘 배경: #FCECE5 (피치 크림)
    * 메인 포인트: #D94F3D (비비드 토마토 레드)
    * 메뉴 버튼: #B94335 (딥 토마토 레드)
    * 가격 텍스트: #D94F3D (토마토 레드)
    * 기본 텍스트: #49352F (따뜻한 다크 브라운)
    * 보조 텍스트: #A58A79 (뮤트 브라운)
    * 결제 버튼: #F4B942 (머스터드 골드)
    * 결제 버튼 Hover: #D99A24 (딥 머스터드 골드)
    * 구분선: #F0E5DA (연한 베이지)
- 절대 원칙 준수:
  1) 기존 백엔드, DB, 통신, 스레딩 로직 100% 보존
  2) tkinter.Frame 위젯 및 모든 위젯의 pady 속성에 튜플 미사용 (단일 정수만 사용)
  3) 모든 검은색 테두리 제거 및 부드러운 그림자(CLR_SHADOW) 적용
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox
import tkinter.font as tkfont
from typing import Any, Dict, List
import urllib3
import uuid
import requests

from config import BASE_URL, DEFAULT_HEADERS
from database import create_order_transaction, fetch_menus_by_store, init_db

# 로컬 자체 서명 SSL 인증서 경고 숨김
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 백엔드 서버 및 DB 호환 식별자 (절대 보존)
STORE_ID = "KIOSK_02"
STORE_NAME = "김밥천국"  # 서버 및 DB 매핑용 정규 매장명
DISPLAY_BRAND = "김밥나라"  # 키오스크 UI 표시용 브랜드명

# ==============================================================================
# 🎨 Cream Ivory & Tomato Red – Modern Korean Snack Bar 컬러 팔레트 (지정 규격)
# ==============================================================================
CLR_ALL_BG = "#FFF9F2"          # 전체 배경 (따뜻한 크림 아이보리)
CLR_CONTENT_BG = "#FFF5EC"      # 메뉴 영역 (부드러운 크림)
CLR_CARD_BG = "#FFFFFF"         # 카드 배경 (순백색)
CLR_BANNER_BG = "#F4E8DA"       # 배너 배경 (샌드 베이지)
CLR_ICON_BG = "#FCECE5"         # 아이콘 배경 (피치 크림)
CLR_MAIN_POINT = "#D94F3D"      # 메인 포인트 (비비드 토마토 레드)
CLR_MENU_BTN = "#B94335"        # 메뉴 담기 버튼 (딥 토마토 레드)
CLR_MENU_BTN_HOVER = "#9E362A"  # 메뉴 담기 버튼 마우스 호버
CLR_PRICE_TEXT = "#D94F3D"      # 가격 텍스트 (토마토 레드)
CLR_TEXT_BASE = "#49352F"       # 기본 텍스트 (따뜻한 다크 브라운)
CLR_TEXT_MUTED = "#A58A79"      # 보조 텍스트 (뮤트 브라운)
CLR_GOLD = "#F4B942"            # 결제 및 주문 버튼 (머스터드 골드)
CLR_GOLD_HOVER = "#D99A24"      # 결제 버튼 마우스 Hover (딥 머스터드 골드)
CLR_DIVIDER = "#F0E5DA"         # 구분선 (연한 베이지)
CLR_SHADOW = "#EFE3D5"          # 부드러운 카드 그림자 경계선
CLR_OPTION_ACTIVE = "#D94F3D"   # 기호 옵션 활성 (토마토 레드)
CLR_OPTION_BG = "#FCECE5"       # 기호 옵션 활성 배경 (피치 크림)
CLR_DIM = "#2B1D19"             # 완료 모달 딤 배경 (따뜻한 다크 차콜)

# 기존 변수명 호환성 별칭 (안전 보존)
CLR_SUB_POINT = CLR_BANNER_BG
CLR_PRICE_ACCENT = CLR_PRICE_TEXT
CLR_DEEP_BRICK = CLR_MENU_BTN
CLR_BRICK_HOVER = CLR_MENU_BTN_HOVER
CLR_DEEP_FOREST = CLR_MENU_BTN
CLR_FOREST_HOVER = CLR_MENU_BTN_HOVER
CLR_MAIN_BG = CLR_ALL_BG
CLR_SUB_BG = CLR_CONTENT_BG
CLR_MAIN_BROWN = CLR_MENU_BTN
CLR_DEEP_WOOD = CLR_MENU_BTN
CLR_DEEP_HOVER = CLR_MENU_BTN_HOVER
CLR_LIGHT_BROWN = CLR_MAIN_POINT
CLR_SAND_BEIGE = CLR_BANNER_BG
CLR_OAK_BEIGE = CLR_MAIN_POINT

# 분식 메뉴별 비주얼 아이콘 매핑
MENU_ICONS = {
    "기본 김밥": "🍙",
    "참치김밥": "🐟",
    "치즈김밥": "🧀",
    "돈가스 김밥": "🥩",
    "야채 김밥": "🥗",
    "땡초김밥": "🌶️",
    "제육김밥": "🥓",
    "돈가스": "🍛",
    "라면": "🍜",
    "우동": "🍥",
    "떡볶이": "🍢",
}


def draw_round_rect(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int = 16, fill: str = "", outline: str = ""
) -> List[int]:
    """수학적으로 정밀한 둥근 모서리 사각형 (4개 아크 + 2개 사각형)"""
    r = min(radius, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2))
    d = 2 * r
    items = []
    items.append(canvas.create_arc(x1, y1, x1 + d, y1 + d, start=90, extent=90, fill=fill, outline=outline))
    items.append(canvas.create_arc(x2 - d, y1, x2, y1 + d, start=0, extent=90, fill=fill, outline=outline))
    items.append(canvas.create_arc(x2 - d, y2 - d, x2, y2, start=270, extent=90, fill=fill, outline=outline))
    items.append(canvas.create_arc(x1, y2 - d, x1 + d, y2, start=180, extent=90, fill=fill, outline=outline))
    items.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=outline))
    items.append(canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=outline))
    return items


# ==============================================================================
# 🔤 세련된 모던 한글 타이포그래피 시스템 (Typography Management)
# - 기본 폰트: Pretendard
# - 대체 폰트: 맑은 고딕 (Malgun Gothic) (Windows 환경 100% 한글 호환)
# - 정밀 요구 규격 위계 (-px 지정 및 가중치 대비):
#   * 메인 헤더: Bold 25px
#   * 배너 제목: Bold 25px
#   * 메뉴명: SemiBold 17px
#   * 메뉴 가격: Bold 20px
#   * 장바구니 제목: Bold 22px
#   * 총 주문 금액: ExtraBold 30~32px (-31px)
#   * 메뉴 버튼: SemiBold 15px
#   * 결제 버튼: ExtraBold 19px
#   * 보조 설명: Regular 12~14px (-13px)
# ==============================================================================

def resolve_font_families() -> Dict[str, str]:
    """
    Windows 환경에서 실제 설치된 폰트를 감지하여,
    Pretendard 폰트를 우선 적용하고 미설치 시 맑은 고딕(Malgun Gothic)으로 안전 대체합니다.
    """
    try:
        available = set(tkfont.families())
    except Exception:
        available = set()

    # 1. 기본 본문 폰트 (Pretendard -> 맑은 고딕 / Malgun Gothic)
    regular_font = "Malgun Gothic"
    for candidate in [
        "Pretendard",
        "Pretendard Variable",
        "Pretendard Regular",
        "맑은 고딕",
        "Malgun Gothic",
    ]:
        if candidate in available:
            regular_font = candidate
            break

    # 2. SemiBold 패밀리 (별도 패밀리 설치 시 우선 사용, 미설치 시 regular_font)
    semibold_font = regular_font
    for candidate in ["Pretendard SemiBold", "Pretendard-SemiBold"]:
        if candidate in available:
            semibold_font = candidate
            break

    # 3. Bold 패밀리 (별도 패밀리 설치 시 우선 사용, 미설치 시 regular_font)
    bold_font = regular_font
    for candidate in ["Pretendard Bold", "Pretendard-Bold"]:
        if candidate in available:
            bold_font = candidate
            break

    return {
        "regular": regular_font,
        "semibold": semibold_font,
        "bold": bold_font,
    }


class FontConfig:
    """
    [공통 타이포그래피 시스템]
    사용자 요구사항에 맞춘 위계별 정밀 폰트 설정 (픽셀 -px 지정 및 가중치 대비):
    - 메인 헤더: Bold 25px
    - 배너 제목: Bold 25px
    - 메뉴명: SemiBold 17px
    - 메뉴 가격: Bold 20px
    - 장바구니 제목: Bold 22px
    - 총 주문 금액: ExtraBold 30~32px (-31px)
    - 메뉴 버튼: SemiBold 15px
    - 결제 버튼: ExtraBold 19px
    - 보조 설명: Regular 12~14px (-13px)
    """

    def __init__(self) -> None:
        fams = resolve_font_families()
        self.family_regular = fams["regular"]
        self.family_semibold = fams["semibold"]
        self.family_bold = fams["bold"]

        # 1. 메인 헤더: Bold 25px
        self.HEADER_MAIN = (self.family_bold, -25, "bold")
        self.HEADER_SUB = (self.family_regular, -12)

        # 2. 배너 제목: Bold 25px
        self.BANNER_TITLE = (self.family_bold, -25, "bold")
        self.BANNER_SUB = (self.family_regular, -13)

        # 3. 메뉴명: SemiBold 17px
        self.MENU_NAME = (self.family_semibold, -17, "bold")
        self.MENU_NAME_CART = (self.family_semibold, -16, "bold")

        # 4. 메뉴 가격: Bold 20px
        self.MENU_PRICE = (self.family_bold, -20, "bold")
        self.MENU_PRICE_CART = (self.family_bold, -17, "bold")

        # 5. 일반 설명: Regular 12~14px (-13px)
        self.BODY_DESC = (self.family_regular, -13)
        self.BODY_DESC_SMALL = (self.family_regular, -12)

        # 6. 버튼: SemiBold 13~15px
        self.BUTTON = (self.family_semibold, -14, "bold")
        self.BUTTON_LARGE = (self.family_semibold, -15, "bold")  # 메뉴 담기 버튼 15px
        self.BUTTON_SMALL = (self.family_semibold, -12, "bold")

        # 7. 장바구니 제목: Bold 22px
        self.CART_TITLE = (self.family_bold, -22, "bold")

        # 8. 총 주문 금액: ExtraBold 30~32px (-31px)
        self.TOTAL_PRICE = (self.family_bold, -31, "bold")

        # 9. 결제 및 주문하기 버튼: ExtraBold 19px
        self.ORDER_BTN = (self.family_bold, -19, "bold")

        # 10. 완료 대형 주문 번호: Bold 28px
        self.ORDER_NUM_LARGE = (self.family_bold, -28, "bold")


def detect_best_korean_font() -> str:
    """하위 호환용 폰트 감지 함수"""
    return resolve_font_families()["regular"]


def detect_best_en_font() -> str:
    """하위 호환용 영문 폰트 감지 함수"""
    return resolve_font_families()["regular"]


# ==============================================================================
# 💳 모의 주문 결제 프로세서 (MockPaymentProcessor)
# ==============================================================================
class MockPaymentProcessor:
    """
    [모의 주문 결제 프로세서]
    - 기존 백엔드(server.py)와 데이터베이스(database.py) 로직을 일절 건드리지 않고 연동합니다.
    1) '결제하기' 클릭 시 별도의 카드 결제창이나 대기시간 없이 즉시 [결제 성공]으로 간주
    2) 가상 PG 승인 번호(APPR-XXXXXXXX) 생성
    3) 중앙 서버(HTTPS POST /order)로 주문 데이터 전송
    4) 서버 응답(주문 번호 등) 수신 및 반환
    """

    @staticmethod
    def process_payment(payload: Dict[str, Any]) -> Dict[str, Any]:
        approval_no = f"APPR-{uuid.uuid4().hex[:8].upper()}"

        # 1. API 인증 토큰 헤더 보강 (config 기본값 또는 .env 환경변수에서만 참조)
        token = DEFAULT_HEADERS.get("access_token") or os.getenv("BDS_API_KEY", "")
        headers = dict(DEFAULT_HEADERS)
        headers["access_token"] = token

        try:
            resp = requests.post(
                f"{BASE_URL}/order",
                json=payload,
                headers=headers,
                verify=False,
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "order_id": data.get("order_id"),
                    "total_price": data.get("total_price", 0),
                    "approval_no": approval_no,
                    "message": data.get("message", "주문이 정상 접수되었습니다."),
                }
            elif resp.status_code == 403:
                return {
                    "success": False,
                    "error": "인증 실패 (403 Forbidden): 유효하지 않은 API Key입니다. (.env의 BDS_API_KEY를 확인하세요)",
                }
            else:
                return {
                    "success": False,
                    "error": f"서버 응답 오류 ({resp.status_code}): {resp.text}",
                }
        except requests.exceptions.ConnectionError:
            # 중앙 서버(server.py) 미실행 시 단독 데모 모드로 로컬 SQLite DB 트랜잭션 폴백 처리
            try:
                init_db()
                db_result = create_order_transaction(payload)
                return {
                    "success": True,
                    "order_id": db_result.get("order_id"),
                    "total_price": db_result.get("total_price", 0),
                    "approval_no": approval_no,
                    "message": "로컬 DB에 주문이 정상 저장되었습니다 (단독 실행 모드).",
                }
            except Exception as db_err:
                return {
                    "success": False,
                    "error": f"중앙 서버 연결 실패 및 로컬 DB 저장 오류: {db_err}",
                }
        except Exception as exc:
            return {
                "success": False,
                "error": f"통신 중 예외 발생: {exc}",
            }


# ==============================================================================
# 🍙 우드톤 김밥나라 키오스크 메인 UI (ModernGimbapKiosk)
# ==============================================================================
class ModernGimbapKiosk(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"GIMBAP NARA | {DISPLAY_BRAND} 무인 주문 키오스크 ({STORE_ID})")
        self.geometry("1180x800")
        self.minsize(1080, 720)
        self.configure(bg=CLR_ALL_BG)

        # 공통 타이포그래피 설정 시스템 초기화 (Pretendard 우선, 미설치 시 맑은 고딕 안전 대체)
        self.fonts = FontConfig()
        self.font_kr = self.fonts.family_regular
        self.font_en = self.fonts.family_regular

        # 전체화면 상태 변수 및 단축키 바인딩
        self.is_fullscreen = False
        self.bind("<F11>", lambda event: self.toggle_fullscreen())
        self.bind("<Escape>", lambda event: self.exit_fullscreen())

        # 메뉴 로드 (중앙 서버 REST API 우선 호출, 오프라인 시 읽기 전용 폴백)
        self.all_menus: List[Dict[str, Any]] = self._load_store_menus()

        # 카테고리 필터 상태 ('전체', '김밥류', '식사/분식류')
        self.selected_category = "전체"

        # 장바구니 데이터
        self.cart: List[Dict[str, Any]] = []

        # 매장 옵션 상태: order_type('매장식사' or '포장'), spoon_needed('수저필요함' or '수저필요없음')
        self.order_type = "매장식사"
        self.spoon_needed = "수저필요함"

        # 김밥 메뉴별 기호 옵션 추적: {menu_name: {"no_carrot": bool, "no_cucumber": bool}}
        self.gimbap_options: Dict[str, Dict[str, bool]] = {}

        # 모달 오버레이 및 타이머 추적
        self.modal_overlay = None
        self.modal_timer_id = None

        self._build_ui()
        self._refresh_menu_grid()
        self._refresh_cart_ui()

    def _load_store_menus(self) -> List[Dict[str, Any]]:
        """중앙 서버의 REST API(GET /menus/{store_id})로 메뉴를 우선 조회합니다."""
        try:
            resp = requests.get(
                f"{BASE_URL}/menus/{STORE_ID}",
                headers=DEFAULT_HEADERS,
                verify=False,
                timeout=3.0,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        # 서버 미기동 등 오프라인 시 읽기 전용 로컬 메뉴 조회 폴백
        init_db()
        return fetch_menus_by_store(STORE_ID)

    # --------------------------------------------------------------------------
    # 전체화면 토글
    # --------------------------------------------------------------------------
    def toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        if hasattr(self, "fs_btn"):
            self.fs_btn.config(text="창모드 F11" if self.is_fullscreen else "전체화면 F11")

    def exit_fullscreen(self) -> None:
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.attributes("-fullscreen", False)
            if hasattr(self, "fs_btn"):
                self.fs_btn.config(text="전체화면 F11")

    # --------------------------------------------------------------------------
    # UI 빌드 메인 (좌우 2단 분할 구조: 좌 68% / 우 32%)
    # --------------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 1. 상단 글로벌 헤더
        self._build_top_header()

        # 2. 메인 컨텐츠 영역 (좌우 2단 분할 구조: 좌 68% / 우 32%)
        body = tk.Frame(self, bg=CLR_ALL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # 좌측 영역 (약 68%): 상단 배너 + 카테고리 탭 + 메뉴 개수 안내 + 3열 메뉴 카드 그리드
        self.left_pane = tk.Frame(body, bg=CLR_ALL_BG)
        self.left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16))

        # 우측 영역 (약 32% 고정 380px): 플로팅 소프트 섀도우 장바구니 패널 (검은색 테두리 없음)
        right_shadow = tk.Frame(body, bg=CLR_SHADOW, width=380, bd=0)
        right_shadow.pack(side=tk.RIGHT, fill=tk.BOTH)
        right_shadow.pack_propagate(False)

        self.right_pane = tk.Frame(
            right_shadow, bg=CLR_CARD_BG, bd=0, relief=tk.FLAT, highlightthickness=0
        )
        self.right_pane.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # 좌측 및 우측 상세 컴포넌트 빌드
        self._build_left_section()
        self._build_right_cart_section()

    # --------------------------------------------------------------------------
    # [3. 상단 브랜드 헤더] - 순백색(#FFFFFF) 배경, 다크 브라운 메인 타이틀, 토마토 레드 포인트
    # --------------------------------------------------------------------------
    def _build_top_header(self) -> None:
        header = tk.Frame(self, bg=CLR_CARD_BG, height=70, bd=0)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        # 하단 1px 부드러운 베이지 구분선
        divider = tk.Frame(self, bg=CLR_DIVIDER, height=1)
        divider.pack(fill=tk.X, side=tk.TOP)

        # 좌측 김밥 아이콘 및 브랜드명
        logo_frame = tk.Frame(header, bg=CLR_CARD_BG)
        logo_frame.pack(side=tk.LEFT, padx=24, pady=12)

        emblem = tk.Label(
            logo_frame,
            text="🍙",
            font=(self.fonts.family_regular, -20),
            bg=CLR_ICON_BG,
            fg=CLR_MAIN_POINT,
            width=2,
            height=1,
            relief=tk.FLAT,
        )
        emblem.pack(side=tk.LEFT, padx=(0, 14))

        title_box = tk.Frame(logo_frame, bg=CLR_CARD_BG)
        title_box.pack(side=tk.LEFT)

        en_title = tk.Label(
            title_box,
            text="GIMBAP NARA",
            font=self.fonts.HEADER_SUB,
            fg=CLR_MAIN_POINT,
            bg=CLR_CARD_BG,
        )
        en_title.pack(anchor="w")

        kr_title = tk.Label(
            title_box,
            text=f"{DISPLAY_BRAND} 무인 주문 키오스크",
            font=self.fonts.HEADER_MAIN,
            fg=CLR_TEXT_BASE,
            bg=CLR_CARD_BG,
        )
        kr_title.pack(anchor="w")

        # 우측 액션 영역 (보안 배지 + 전체화면 F11 버튼)
        actions_frame = tk.Frame(header, bg=CLR_CARD_BG)
        actions_frame.pack(side=tk.RIGHT, padx=24, pady=12)

        status_badge = tk.Label(
            actions_frame,
            text="● HTTPS 안전연결",
            font=self.fonts.BUTTON_SMALL,
            bg=CLR_ICON_BG,
            fg=CLR_MAIN_POINT,
            padx=12,
            pady=6,
            relief=tk.FLAT,
        )
        status_badge.pack(side=tk.LEFT, padx=(0, 10))

        self.fs_btn = tk.Button(
            actions_frame,
            text="전체화면 F11",
            font=self.fonts.BUTTON,
            bg=CLR_MAIN_POINT,
            fg="#FFFFFF",
            activebackground=CLR_MENU_BTN,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.toggle_fullscreen,
        )
        self.fs_btn.pack(side=tk.LEFT)

    # --------------------------------------------------------------------------
    # 좌측 섹션 (배너 + 카테고리 탭 + 메뉴 개수 안내 + 3열 메뉴 그리드)
    # --------------------------------------------------------------------------
    def _build_left_section(self) -> None:
        # [4. 메인 홍보 배너] - 샌드 베이지(#F4E8DA) 배경, 검은색 테두리 없는 플랫 디자인
        banner = tk.Frame(
            self.left_pane,
            bg=CLR_BANNER_BG,
            bd=0,
            relief=tk.FLAT,
            padx=22,
            pady=16,
        )
        banner.pack(fill=tk.X, pady=8)

        b_text_box = tk.Frame(banner, bg=CLR_BANNER_BG)
        b_text_box.pack(side=tk.LEFT)

        b_sub = tk.Label(
            b_text_box,
            text="GIMBAP NARA SPECIALTY",
            font=self.fonts.BANNER_SUB,
            fg=CLR_MAIN_POINT,
            bg=CLR_BANNER_BG,
        )
        b_sub.pack(anchor="w", pady=2)

        b_main = tk.Label(
            b_text_box,
            text="오늘도, 기분 좋은 한 끼.",
            font=self.fonts.BANNER_TITLE,
            fg=CLR_TEXT_BASE,
            bg=CLR_BANNER_BG,
        )
        b_main.pack(anchor="w")

        b_desc = tk.Label(
            b_text_box,
            text="신선하고 정갈한 재료로 정성을 담아 말아냅니다.",
            font=self.fonts.BODY_DESC,
            fg=CLR_TEXT_MUTED,
            bg=CLR_BANNER_BG,
        )
        b_desc.pack(anchor="w", pady=3)

        b_icon = tk.Label(
            banner,
            text="🍙✨",
            font=("Segoe UI Emoji", -28),
            fg=CLR_MAIN_POINT,
            bg=CLR_BANNER_BG,
        )
        b_icon.pack(side=tk.RIGHT, padx=12)

        # [5. 메뉴 카테고리 탭] - 가로형 알약 탭 (선택: 토마토 레드 #D94F3D, 미선택: 순백색 #FFFFFF)
        tab_container = tk.Frame(self.left_pane, bg=CLR_ALL_BG)
        tab_container.pack(fill=tk.X, pady=6)

        self.category_buttons: Dict[str, tk.Button] = {}
        categories = ["전체", "김밥류", "식사/분식류"]

        for cat in categories:
            btn = tk.Button(
                tab_container,
                text=cat,
                font=self.fonts.BUTTON_LARGE,
                relief=tk.FLAT,
                bd=0,
                padx=20,
                pady=8,
                cursor="hand2",
                command=lambda c=cat: self._set_category(c),
            )
            btn.pack(side=tk.LEFT, padx=(0, 8))
            self.category_buttons[cat] = btn

        self._update_tab_styles()

        # [메뉴 개수 안내 바]
        self.menu_count_bar = tk.Frame(self.left_pane, bg=CLR_ALL_BG)
        self.menu_count_bar.pack(fill=tk.X, pady=6)

        self.menu_count_lbl = tk.Label(
            self.menu_count_bar,
            text=f"총 {len(self.all_menus)}개의 메뉴가 준비되어 있습니다.",
            font=self.fonts.BODY_DESC,
            fg=CLR_TEXT_MUTED,
            bg=CLR_ALL_BG,
        )
        self.menu_count_lbl.pack(side=tk.LEFT, padx=4)

        # [6. 3열 메뉴 카드 그리드 컨테이너] (독립 스크롤)
        grid_container = tk.Frame(self.left_pane, bg=CLR_CONTENT_BG)
        grid_container.pack(fill=tk.BOTH, expand=True)

        self.menu_canvas = tk.Canvas(
            grid_container,
            bg=CLR_CONTENT_BG,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
        )
        self.menu_scrollbar = tk.Scrollbar(
            grid_container,
            orient=tk.VERTICAL,
            command=self.menu_canvas.yview,
            width=8,
        )
        self.menu_scroll_frame = tk.Frame(self.menu_canvas, bg=CLR_CONTENT_BG)

        self.menu_scroll_frame.bind(
            "<Configure>",
            lambda e: self.menu_canvas.configure(
                scrollregion=self.menu_canvas.bbox("all")
            ),
        )
        self.canvas_window = self.menu_canvas.create_window(
            (0, 0), window=self.menu_scroll_frame, anchor="nw"
        )

        self.menu_canvas.bind(
            "<Configure>",
            lambda e: self.menu_canvas.itemconfig(self.canvas_window, width=e.width),
        )

        self.menu_canvas.configure(yscrollcommand=self.menu_scrollbar.set)
        self.menu_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.menu_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._bind_mouse_wheel(self.menu_canvas)

    def _bind_mouse_wheel(self, widget: tk.Widget) -> None:
        def _on_mousewheel(event: Any) -> None:
            widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        widget.bind_all("<MouseWheel>", _on_mousewheel)

    def _set_category(self, cat: str) -> None:
        self.selected_category = cat
        self._update_tab_styles()
        self._refresh_menu_grid()

    def _update_tab_styles(self) -> None:
        for cat, btn in self.category_buttons.items():
            if cat == self.selected_category:
                btn.config(
                    bg=CLR_MAIN_POINT,
                    fg="#FFFFFF",
                    activebackground=CLR_MENU_BTN,
                    activeforeground="#FFFFFF",
                )
            else:
                btn.config(
                    bg=CLR_CARD_BG,
                    fg=CLR_TEXT_BASE,
                    activebackground=CLR_ICON_BG,
                    activeforeground=CLR_TEXT_BASE,
                )

    def _refresh_menu_grid(self) -> None:
        for child in self.menu_scroll_frame.winfo_children():
            child.destroy()

        if self.selected_category == "전체":
            filtered = self.all_menus
        else:
            filtered = [m for m in self.all_menus if m["category"] == self.selected_category]

        # 메뉴 개수 안내 텍스트 업데이트
        if hasattr(self, "menu_count_lbl") and self.menu_count_lbl.winfo_exists():
            self.menu_count_lbl.config(
                text=f"총 {len(filtered)}개의 메뉴가 준비되어 있습니다."
            )

        cols = 3
        for c in range(cols):
            self.menu_scroll_frame.grid_columnconfigure(c, weight=1, uniform="menu_card")

        for idx, menu in enumerate(filtered):
            r = idx // cols
            c = idx % cols
            card = self._create_menu_card(self.menu_scroll_frame, menu)
            card.grid(row=r, column=c, padx=7, pady=7, sticky="nsew")

    # --------------------------------------------------------------------------
    # [6. 개별 메뉴 카드 컴포넌트] - 순백색(#FFFFFF), 테두리 없는 소프트 섀도우, 토마토 레드 담기 버튼
    # --------------------------------------------------------------------------
    def _create_menu_card(self, parent: tk.Widget, menu: Dict[str, Any]) -> tk.Frame:
        m_name = menu["menu_name"]
        is_gimbap = menu.get("category") == "김밥류"

        if m_name not in self.gimbap_options:
            self.gimbap_options[m_name] = {"no_carrot": False, "no_cucumber": False}

        # 소프트 섀도우 래퍼 (테두리 없는 프리미엄 모던 플로팅 카드)
        shadow_box = tk.Frame(
            parent,
            bg=CLR_SHADOW,
            bd=0,
            relief=tk.FLAT,
            padx=1,
            pady=1,
            cursor="hand2",
        )

        card = tk.Frame(
            shadow_box,
            bg=CLR_CARD_BG,
            bd=0,
            relief=tk.FLAT,
            padx=16,
            pady=16,
        )
        card.pack(fill=tk.BOTH, expand=True)

        # 1. 분식 아이콘 (피치 크림 #FCECE5 원형 플레이트)
        icon_char = MENU_ICONS.get(m_name, "🍙")
        icon_plate = tk.Label(
            card,
            text=icon_char,
            font=("Segoe UI Emoji", -26),
            bg=CLR_ICON_BG,
            fg=CLR_MAIN_POINT,
            width=3,
            height=1,
            relief=tk.FLAT,
        )
        icon_plate.pack(pady=6)

        # 2. 메뉴 카테고리 태그
        cat_badge = tk.Label(
            card,
            text=menu.get("category", "분식"),
            font=self.fonts.BODY_DESC_SMALL,
            fg=CLR_TEXT_MUTED,
            bg=CLR_CARD_BG,
        )
        cat_badge.pack(anchor="w")

        # 3. 메뉴명 (Pretendard SemiBold, 17px)
        name_lbl = tk.Label(
            card,
            text=m_name,
            font=self.fonts.MENU_NAME,
            fg=CLR_TEXT_BASE,
            bg=CLR_CARD_BG,
            anchor="w",
            wraplength=190,
            justify="left",
        )
        name_lbl.pack(anchor="w", fill=tk.X, pady=2)

        # 4. 가격 (Pretendard Bold, 20px, 토마토 레드 #D94F3D)
        price_lbl = tk.Label(
            card,
            text=f"{int(menu['price']):,}원",
            font=self.fonts.MENU_PRICE,
            fg=CLR_PRICE_TEXT,
            bg=CLR_CARD_BG,
            anchor="w",
        )
        price_lbl.pack(anchor="w", fill=tk.X, pady=6)

        # 김밥류인 경우: 기호 옵션(당근 제외 / 오이 제외) 미니 토글 바
        if is_gimbap:
            opt_bar = tk.Frame(card, bg=CLR_CARD_BG)
            opt_bar.pack(fill=tk.X, pady=6)

            opt_state = self.gimbap_options[m_name]

            # 당근 제외 토글
            c_bg = CLR_OPTION_BG if opt_state["no_carrot"] else CLR_DIVIDER
            c_fg = CLR_MAIN_POINT if opt_state["no_carrot"] else CLR_TEXT_BASE
            carrot_btn = tk.Button(
                opt_bar,
                text="🥕 당근빼고" if opt_state["no_carrot"] else "🥕 당근포함",
                font=self.fonts.BUTTON_SMALL,
                bg=c_bg,
                fg=c_fg,
                activebackground=c_bg,
                activeforeground=c_fg,
                relief=tk.FLAT,
                bd=0,
                padx=5,
                pady=3,
                cursor="hand2",
            )
            carrot_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
            carrot_btn.config(
                command=lambda m=menu, b=carrot_btn: self._toggle_menu_option(m, "no_carrot", b)
            )

            # 오이 제외 토글
            u_bg = CLR_OPTION_BG if opt_state["no_cucumber"] else CLR_DIVIDER
            u_fg = CLR_MAIN_POINT if opt_state["no_cucumber"] else CLR_TEXT_BASE
            cucumber_btn = tk.Button(
                opt_bar,
                text="🥒 오이빼고" if opt_state["no_cucumber"] else "🥒 오이포함",
                font=self.fonts.BUTTON_SMALL,
                bg=u_bg,
                fg=u_fg,
                activebackground=u_bg,
                activeforeground=u_fg,
                relief=tk.FLAT,
                bd=0,
                padx=5,
                pady=3,
                cursor="hand2",
            )
            cucumber_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))
            cucumber_btn.config(
                command=lambda m=menu, b=cucumber_btn: self._toggle_menu_option(m, "no_cucumber", b)
            )
        else:
            hint_lbl = tk.Label(
                card,
                text="정갈하고 든든한 한 그릇",
                font=self.fonts.BODY_DESC,
                fg=CLR_TEXT_MUTED,
                bg=CLR_CARD_BG,
                anchor="w",
            )
            hint_lbl.pack(anchor="w", fill=tk.X, pady=6)

        # 5. 담기 버튼 (Pretendard SemiBold 15px, 딥 토마토 레드 #B94335)
        add_btn = tk.Button(
            card,
            text="담기  +",
            font=self.fonts.BUTTON_LARGE,
            bg=CLR_MENU_BTN,
            fg="#FFFFFF",
            activebackground=CLR_MENU_BTN_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            bd=0,
            pady=8,
            cursor="hand2",
            command=lambda m=menu: self.add_to_cart(m),
        )
        add_btn.pack(fill=tk.X, side=tk.BOTTOM)

        add_btn.bind("<Enter>", lambda e, b=add_btn: b.config(bg=CLR_MENU_BTN_HOVER))
        add_btn.bind("<Leave>", lambda e, b=add_btn: b.config(bg=CLR_MENU_BTN))

        for w in (shadow_box, card, icon_plate, cat_badge, name_lbl, price_lbl):
            w.bind("<Button-1>", lambda e, m=menu: self.add_to_cart(m))

        return shadow_box

    def _toggle_menu_option(self, menu: Dict[str, Any], opt_key: str, btn: tk.Button) -> None:
        m_name = menu["menu_name"]
        cur = self.gimbap_options[m_name][opt_key]
        self.gimbap_options[m_name][opt_key] = not cur

        new_val = self.gimbap_options[m_name][opt_key]
        if opt_key == "no_carrot":
            txt = "🥕 당근빼고" if new_val else "🥕 당근포함"
        else:
            txt = "🥒 오이빼고" if new_val else "🥒 오이포함"

        bg = CLR_OPTION_BG if new_val else CLR_DIVIDER
        fg = CLR_MAIN_POINT if new_val else CLR_TEXT_BASE
        btn.config(text=txt, bg=bg, fg=fg, activebackground=bg, activeforeground=fg)

    # --------------------------------------------------------------------------
    # [7. 우측 장바구니 디자인] - 흰색 배경의 독립적인 주문 패널 (약 32%)
    # --------------------------------------------------------------------------
    def _build_right_cart_section(self) -> None:
        # (1) 내 주문 제목 및 전체 삭제 버튼
        header_bar = tk.Frame(self.right_pane, bg=CLR_CARD_BG, padx=16, pady=10)
        header_bar.pack(fill=tk.X)

        self.cart_title_lbl = tk.Label(
            header_bar,
            text="내 주문 (0)",
            font=self.fonts.CART_TITLE,
            fg=CLR_TEXT_BASE,
            bg=CLR_CARD_BG,
        )
        self.cart_title_lbl.pack(side=tk.LEFT)

        clear_btn = tk.Button(
            header_bar,
            text="전체 삭제",
            font=self.fonts.BODY_DESC,
            fg=CLR_TEXT_MUTED,
            bg=CLR_CARD_BG,
            activeforeground=CLR_TEXT_BASE,
            activebackground=CLR_CARD_BG,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self.clear_cart,
        )
        clear_btn.pack(side=tk.RIGHT)

        # (2) 매장 식사 / 포장 선택 탭 (피치 크림 바탕 알약형)
        toggle_box = tk.Frame(self.right_pane, bg=CLR_CARD_BG, padx=16, pady=8)
        toggle_box.pack(fill=tk.X)

        toggle_frame = tk.Frame(toggle_box, bg=CLR_ICON_BG, padx=3, pady=3)
        toggle_frame.pack(fill=tk.X)

        self.btn_eat = tk.Button(
            toggle_frame,
            text="🍽️  매장식사",
            font=self.fonts.BUTTON,
            relief=tk.FLAT,
            bd=0,
            pady=7,
            cursor="hand2",
            command=lambda: self._set_order_type("매장식사"),
        )
        self.btn_eat.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_togo = tk.Button(
            toggle_frame,
            text="🛍️  포장하기",
            font=self.fonts.BUTTON,
            relief=tk.FLAT,
            bd=0,
            pady=7,
            cursor="hand2",
            command=lambda: self._set_order_type("포장"),
        )
        self.btn_togo.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        self._update_order_type_style()

        # 웜 구분선
        tk.Frame(self.right_pane, bg=CLR_DIVIDER, height=1).pack(fill=tk.X)

        # (3) 담긴 메뉴 목록 (스크롤 캔버스 프레임 - 독립 스크롤)
        list_container = tk.Frame(self.right_pane, bg=CLR_CARD_BG)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.cart_canvas = tk.Canvas(
            list_container,
            bg=CLR_CARD_BG,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
        )
        self.cart_scrollbar = tk.Scrollbar(
            list_container,
            orient=tk.VERTICAL,
            command=self.cart_canvas.yview,
            width=8,
        )
        self.cart_scroll_frame = tk.Frame(self.cart_canvas, bg=CLR_CARD_BG)

        self.cart_scroll_frame.bind(
            "<Configure>",
            lambda e: self.cart_canvas.configure(
                scrollregion=self.cart_canvas.bbox("all")
            ),
        )
        self.cart_canvas_window = self.cart_canvas.create_window(
            (0, 0), window=self.cart_scroll_frame, anchor="nw"
        )

        self.cart_canvas.bind(
            "<Configure>",
            lambda e: self.cart_canvas.itemconfig(self.cart_canvas_window, width=e.width),
        )

        self.cart_canvas.configure(yscrollcommand=self.cart_scrollbar.set)
        self.cart_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.cart_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # (4) 하단 결제 영역 컨테이너 (고정)
        bottom_container = tk.Frame(
            self.right_pane, bg=CLR_CARD_BG, bd=0, padx=16, pady=16
        )
        bottom_container.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Frame(bottom_container, bg=CLR_DIVIDER, height=1).pack(fill=tk.X, pady=8)

        # 수저 / 티스푼 옵션 카드
        self.spoon_card = tk.Frame(
            bottom_container,
            bg=CLR_ICON_BG,
            padx=12,
            pady=10,
            cursor="hand2",
            relief=tk.FLAT,
            bd=0,
        )
        self.spoon_card.pack(fill=tk.X, pady=8)

        self.spoon_icon_lbl = tk.Label(
            self.spoon_card,
            text="🥄",
            font=("Segoe UI Emoji", -14),
            bg=CLR_ICON_BG,
        )
        self.spoon_icon_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.spoon_text_lbl = tk.Label(
            self.spoon_card,
            text="수저 / 티스푼 필요해요",
            font=self.fonts.BUTTON,
            fg=CLR_TEXT_BASE,
            bg=CLR_ICON_BG,
        )
        self.spoon_text_lbl.pack(side=tk.LEFT)

        self.spoon_switch_lbl = tk.Label(
            self.spoon_card,
            text="ON",
            font=self.fonts.BUTTON_SMALL,
            fg="#FFFFFF",
            bg=CLR_MAIN_POINT,
            padx=8,
            pady=2,
            relief=tk.FLAT,
        )
        self.spoon_switch_lbl.pack(side=tk.RIGHT)

        for w in (self.spoon_card, self.spoon_icon_lbl, self.spoon_text_lbl, self.spoon_switch_lbl):
            w.bind("<Button-1>", lambda e: self._toggle_spoon())

        # 총 주문 금액 영역
        sum_row = tk.Frame(bottom_container, bg=CLR_CARD_BG)
        sum_row.pack(fill=tk.X, pady=8)

        sum_label = tk.Label(
            sum_row,
            text="총 주문 금액",
            font=self.fonts.BUTTON,
            fg=CLR_TEXT_MUTED,
            bg=CLR_CARD_BG,
        )
        sum_label.pack(side=tk.LEFT)

        self.total_price_lbl = tk.Label(
            sum_row,
            text="0원",
            font=self.fonts.TOTAL_PRICE,
            fg=CLR_PRICE_TEXT,
            bg=CLR_CARD_BG,
        )
        self.total_price_lbl.pack(side=tk.RIGHT)

        # 하단 머스터드 골드 "결제하기" 대형 버튼 (#F4B942, ExtraBold 19px)
        self.order_btn = tk.Button(
            bottom_container,
            text="결제하기",
            font=self.fonts.ORDER_BTN,
            bg=CLR_GOLD,
            fg=CLR_TEXT_BASE,
            activebackground=CLR_GOLD_HOVER,
            activeforeground=CLR_TEXT_BASE,
            relief=tk.FLAT,
            bd=0,
            pady=14,
            cursor="hand2",
            command=self.submit_order_async,
        )
        self.order_btn.pack(fill=tk.X, pady=4)

        self.order_btn.bind("<Enter>", lambda e: self._on_order_btn_enter())
        self.order_btn.bind("<Leave>", lambda e: self._on_order_btn_leave())

    def _on_order_btn_enter(self) -> None:
        if self.order_btn["state"] != tk.DISABLED:
            self.order_btn.config(bg=CLR_GOLD_HOVER)

    def _on_order_btn_leave(self) -> None:
        if self.order_btn["state"] != tk.DISABLED:
            self.order_btn.config(bg=CLR_GOLD)

    # --------------------------------------------------------------------------
    # 옵션 상태 관리
    # --------------------------------------------------------------------------
    def _set_order_type(self, order_type: str) -> None:
        self.order_type = order_type
        self._update_order_type_style()

    def _update_order_type_style(self) -> None:
        if self.order_type == "매장식사":
            self.btn_eat.config(
                bg=CLR_MAIN_POINT,
                fg="#FFFFFF",
                activebackground=CLR_MENU_BTN,
                activeforeground="#FFFFFF",
            )
            self.btn_togo.config(
                bg=CLR_ICON_BG,
                fg=CLR_TEXT_BASE,
                activebackground=CLR_DIVIDER,
                activeforeground=CLR_TEXT_BASE,
            )
        else:
            self.btn_togo.config(
                bg=CLR_MAIN_POINT,
                fg="#FFFFFF",
                activebackground=CLR_MENU_BTN,
                activeforeground="#FFFFFF",
            )
            self.btn_eat.config(
                bg=CLR_ICON_BG,
                fg=CLR_TEXT_BASE,
                activebackground=CLR_DIVIDER,
                activeforeground=CLR_TEXT_BASE,
            )

    def _toggle_spoon(self) -> None:
        if self.spoon_needed == "수저필요없음":
            self.spoon_needed = "수저필요함"
            self.spoon_switch_lbl.config(text="ON", bg=CLR_MAIN_POINT, fg="#FFFFFF")
            self.spoon_card.config(bg=CLR_ICON_BG)
            self.spoon_icon_lbl.config(bg=CLR_ICON_BG)
            self.spoon_text_lbl.config(bg=CLR_ICON_BG, fg=CLR_TEXT_BASE)
        else:
            self.spoon_needed = "수저필요없음"
            self.spoon_switch_lbl.config(text="OFF", bg=CLR_DIVIDER, fg=CLR_TEXT_MUTED)
            self.spoon_card.config(bg=CLR_ICON_BG)
            self.spoon_icon_lbl.config(bg=CLR_ICON_BG)
            self.spoon_text_lbl.config(bg=CLR_ICON_BG, fg=CLR_TEXT_BASE)

    # --------------------------------------------------------------------------
    # 장바구니 로직 및 UI 갱신 (수량 조절 - / + 시 즉시 실시간 업데이트)
    # --------------------------------------------------------------------------
    def add_to_cart(self, menu: Dict[str, Any]) -> None:
        m_name = menu["menu_name"]
        is_gimbap = menu.get("category") == "김밥류"

        if is_gimbap:
            opt = self.gimbap_options.get(m_name, {"no_carrot": False, "no_cucumber": False})
            carrot_opt = "당근제외" if opt["no_carrot"] else "당근포함"
            cucumber_opt = "오이제외" if opt["no_cucumber"] else "오이포함"

            if opt["no_carrot"] and opt["no_cucumber"]:
                opt_display = "🥕+🥒 제외"
            elif opt["no_carrot"]:
                opt_display = "🥕 당근제외"
            elif opt["no_cucumber"]:
                opt_display = "🥒 오이제외"
            else:
                opt_display = "기본조리"
        else:
            carrot_opt = "당근포함"
            cucumber_opt = "오이포함"
            opt_display = "기본조리"

        for item in self.cart:
            if (
                item["menu_name"] == m_name
                and item["exclude_carrot"] == carrot_opt
                and item["exclude_cucumber"] == cucumber_opt
            ):
                item["quantity"] += 1
                self._refresh_cart_ui()
                return

        self.cart.append(
            {
                "menu_name": m_name,
                "price": int(menu["price"]),
                "quantity": 1,
                "exclude_carrot": carrot_opt,
                "exclude_cucumber": cucumber_opt,
                "opt_display": opt_display,
            }
        )
        self._refresh_cart_ui()

    def change_item_qty(self, idx: int, delta: int) -> None:
        if 0 <= idx < len(self.cart):
            self.cart[idx]["quantity"] += delta
            if self.cart[idx]["quantity"] <= 0:
                del self.cart[idx]
            self._refresh_cart_ui()

    def remove_item(self, idx: int) -> None:
        if 0 <= idx < len(self.cart):
            del self.cart[idx]
            self._refresh_cart_ui()

    def clear_cart(self) -> None:
        self.cart.clear()
        self._refresh_cart_ui()

    def _refresh_cart_ui(self) -> None:
        for child in self.cart_scroll_frame.winfo_children():
            child.destroy()

        total_qty = sum(item["quantity"] for item in self.cart)
        total_price = sum(item["price"] * item["quantity"] for item in self.cart)

        self.cart_title_lbl.config(text=f"내 주문 ({total_qty})")
        self.total_price_lbl.config(text=f"{total_price:,}원")

        if total_qty > 0:
            self.order_btn.config(
                state=tk.NORMAL,
                bg=CLR_GOLD,
                text=f"{total_price:,}원  결제하기",
            )
        else:
            self.order_btn.config(
                state=tk.NORMAL,
                bg=CLR_GOLD,
                text="결제하기",
            )

        if not self.cart:
            empty_frame = tk.Frame(self.cart_scroll_frame, bg=CLR_CARD_BG, pady=50)
            empty_frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(
                empty_frame,
                text="🍙",
                font=("Segoe UI Emoji", -32),
                bg=CLR_CARD_BG,
                fg=CLR_MAIN_POINT,
            ).pack(pady=6)

            tk.Label(
                empty_frame,
                text="담긴 메뉴가 없습니다",
                font=self.fonts.MENU_NAME_CART,
                fg=CLR_TEXT_BASE,
                bg=CLR_CARD_BG,
            ).pack()

            tk.Label(
                empty_frame,
                text="좌측에서 원하시는 메뉴를 선택해 주세요.",
                font=self.fonts.BODY_DESC,
                fg=CLR_TEXT_MUTED,
                bg=CLR_CARD_BG,
            ).pack(pady=4)
            return

        for idx, item in enumerate(self.cart):
            item_card = tk.Frame(
                self.cart_scroll_frame,
                bg=CLR_CARD_BG,
                padx=12,
                pady=10,
                bd=0,
            )
            item_card.pack(fill=tk.X)

            top_row = tk.Frame(item_card, bg=CLR_CARD_BG)
            top_row.pack(fill=tk.X)

            m_name = tk.Label(
                top_row,
                text=item["menu_name"],
                font=self.fonts.MENU_NAME_CART,
                fg=CLR_TEXT_BASE,
                bg=CLR_CARD_BG,
                anchor="w",
            )
            m_name.pack(side=tk.LEFT)

            del_btn = tk.Button(
                top_row,
                text="✕",
                font=self.fonts.BUTTON,
                fg=CLR_TEXT_MUTED,
                bg=CLR_CARD_BG,
                activeforeground=CLR_MAIN_POINT,
                activebackground=CLR_CARD_BG,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                command=lambda i=idx: self.remove_item(i),
            )
            del_btn.pack(side=tk.RIGHT)

            # 기호 옵션 배지
            opt_row = tk.Frame(item_card, bg=CLR_CARD_BG)
            opt_row.pack(fill=tk.X, pady=4)

            opt_txt = item.get("opt_display", "기본조리")
            opt_is_custom = "제외" in opt_txt
            opt_bg = CLR_OPTION_BG if opt_is_custom else CLR_DIVIDER
            opt_fg = CLR_MAIN_POINT if opt_is_custom else CLR_TEXT_MUTED

            opt_badge = tk.Label(
                opt_row,
                text=opt_txt,
                font=self.fonts.BODY_DESC_SMALL,
                bg=opt_bg,
                fg=opt_fg,
                padx=6,
                pady=2,
            )
            opt_badge.pack(side=tk.LEFT)

            # 수량 조절 버튼 (- / +) 및 금액
            ctrl_row = tk.Frame(item_card, bg=CLR_CARD_BG)
            ctrl_row.pack(fill=tk.X)

            qty_box = tk.Frame(ctrl_row, bg=CLR_ICON_BG, padx=1, pady=1)
            qty_box.pack(side=tk.LEFT)

            minus_btn = tk.Button(
                qty_box,
                text="－",
                font=self.fonts.BUTTON,
                bg=CLR_CARD_BG,
                fg=CLR_TEXT_BASE,
                activebackground=CLR_ICON_BG,
                relief=tk.FLAT,
                bd=0,
                width=2,
                cursor="hand2",
                command=lambda i=idx: self.change_item_qty(i, -1),
            )
            minus_btn.pack(side=tk.LEFT)

            qty_lbl = tk.Label(
                qty_box,
                text=str(item["quantity"]),
                font=self.fonts.BUTTON,
                bg=CLR_ICON_BG,
                fg=CLR_TEXT_BASE,
                width=3,
            )
            qty_lbl.pack(side=tk.LEFT)

            plus_btn = tk.Button(
                qty_box,
                text="＋",
                font=self.fonts.BUTTON,
                bg=CLR_CARD_BG,
                fg=CLR_TEXT_BASE,
                activebackground=CLR_ICON_BG,
                relief=tk.FLAT,
                bd=0,
                width=2,
                cursor="hand2",
                command=lambda i=idx: self.change_item_qty(i, 1),
            )
            plus_btn.pack(side=tk.LEFT)

            sub_total = item["price"] * item["quantity"]
            price_lbl = tk.Label(
                ctrl_row,
                text=f"{sub_total:,}원",
                font=self.fonts.MENU_PRICE_CART,
                fg=CLR_MAIN_POINT,
                bg=CLR_CARD_BG,
            )
            price_lbl.pack(side=tk.RIGHT)

            tk.Frame(self.cart_scroll_frame, bg=CLR_DIVIDER, height=1).pack(
                fill=tk.X, padx=12, pady=6
            )

    # --------------------------------------------------------------------------
    # 4. 모의 주문 결제 프로세서 연동 (기존 백엔드 규격 100% 호환 보존)
    # --------------------------------------------------------------------------
    def submit_order_async(self) -> None:
        """[1단계] 클라이언트: 장바구니 영역의 [결제하기] 버튼 클릭"""
        if not self.cart:
            messagebox.showwarning("장바구니 비어있음", "주문할 메뉴를 먼저 선택해 주세요!")
            return

        payload = {
            "store_id": STORE_ID,
            "store_name": STORE_NAME,
            "order_type": self.order_type,
            "spoon_needed": self.spoon_needed,
            "items": [
                {
                    "menu_name": item["menu_name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                    "temperature": None,
                    "exclude_carrot": item.get("exclude_carrot"),
                    "exclude_cucumber": item.get("exclude_cucumber"),
                }
                for item in self.cart
            ],
        }

        self.order_btn.config(
            state=tk.DISABLED,
            bg=CLR_GOLD,
            text="⚡ 모의 결제 승인 및 주문 전송 중...",
        )

        worker = threading.Thread(
            target=self._run_mock_payment_worker, args=(payload,), daemon=True
        )
        worker.start()

    def _run_mock_payment_worker(self, payload: Dict[str, Any]) -> None:
        """
        [2~3단계]
        2) 모의 결제 처리: 별도 카드 결제창/대기 없이 즉시 [결제 성공] 승인 (가상 승인번호 발급)
        3) 서버로 데이터 전송: FastAPI 중앙 서버 POST /order
        """
        result = MockPaymentProcessor.process_payment(payload)
        if result.get("success"):
            self.after(0, self._on_payment_and_order_success, result)
        else:
            self.after(0, self._on_payment_and_order_error, result.get("error", "알 수 없는 오류"))

    def _on_payment_and_order_success(self, result: Dict[str, Any]) -> None:
        """
        [4단계]
        서버 응답으로 주문 번호(order_id)를 받아와서,
        화면에 '주문이 완료되었습니다. 주문 번호 : #01' 모던 완료 화면 팝업을 띄움
        """
        self.order_btn.config(state=tk.NORMAL, bg=CLR_GOLD)
        order_id = result.get("order_id", 1)
        total_price = result.get("total_price", 0)
        approval_no = result.get("approval_no", "")

        try:
            formatted_no = f"#{int(order_id):02d}"
        except Exception:
            formatted_no = f"#{order_id}"

        self._show_order_complete_modal(formatted_no, total_price, approval_no)
        self.clear_cart()

    def _on_payment_and_order_error(self, err_msg: str) -> None:
        self.order_btn.config(state=tk.NORMAL, bg=CLR_GOLD)
        self._refresh_cart_ui()
        messagebox.showerror("주문 처리 실패", err_msg)

    # --------------------------------------------------------------------------
    # 5. 주문 완료 화면 모달 오버레이 (Order Complete Modal)
    # --------------------------------------------------------------------------
    def _show_order_complete_modal(
        self, formatted_no: str, total_price: int, approval_no: str
    ) -> None:
        """키오스크 화면 중앙에 뜨는 모던 감성 주문 완료 모달 화면"""
        self._close_order_complete_modal()

        self.modal_overlay = tk.Frame(self, bg=CLR_DIM)
        self.modal_overlay.place(x=0, y=0, relwidth=1, relheight=1)

        modal_card = tk.Frame(
            self.modal_overlay,
            bg=CLR_CARD_BG,
            bd=0,
            padx=36,
            pady=32,
            highlightthickness=1,
            highlightbackground=CLR_DIVIDER,
        )
        modal_card.place(relx=0.5, rely=0.5, anchor="center", width=460)

        # 체크 아이콘 (토마토 레드 원형 배지)
        check_icon = tk.Label(
            modal_card,
            text="✔",
            font=self.fonts.BANNER_TITLE,
            bg=CLR_MAIN_POINT,
            fg="#FFFFFF",
            width=2,
            height=1,
            relief=tk.FLAT,
        )
        check_icon.pack(pady=10)

        title_lbl = tk.Label(
            modal_card,
            text="주문이 완료되었습니다!",
            font=self.fonts.BANNER_TITLE,
            fg=CLR_TEXT_BASE,
            bg=CLR_CARD_BG,
        )
        title_lbl.pack(pady=12)

        # 주문 번호 강조 박스 ("주문 번호 : #01")
        order_no_box = tk.Frame(
            modal_card,
            bg=CLR_ICON_BG,
            bd=0,
            relief=tk.FLAT,
            padx=20,
            pady=12,
        )
        order_no_box.pack(fill=tk.X, pady=14)

        order_no_lbl = tk.Label(
            order_no_box,
            text=f"주문 번호 : {formatted_no}",
            font=self.fonts.ORDER_NUM_LARGE,
            fg=CLR_MAIN_POINT,
            bg=CLR_ICON_BG,
        )
        order_no_lbl.pack()

        # 모의 결제 승인 내역 요약 박스
        receipt_box = tk.Frame(modal_card, bg=CLR_BANNER_BG, padx=16, pady=12)
        receipt_box.pack(fill=tk.X, pady=14)

        r_info = [
            ("결제 상태", "모의 결제 즉시 승인 완료"),
            ("승인 번호", approval_no),
            ("결제 금액", f"{total_price:,}원"),
            ("이용 방법", f"{self.order_type} ({self.spoon_needed})"),
        ]
        for label, val in r_info:
            row = tk.Frame(receipt_box, bg=CLR_BANNER_BG)
            row.pack(fill=tk.X, pady=2)
            tk.Label(
                row,
                text=label,
                font=self.fonts.BODY_DESC,
                fg=CLR_TEXT_MUTED,
                bg=CLR_BANNER_BG,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=val,
                font=self.fonts.BUTTON,
                fg=CLR_TEXT_BASE,
                bg=CLR_BANNER_BG,
            ).pack(side=tk.RIGHT)

        guide_lbl = tk.Label(
            modal_card,
            text="주방으로 주문서가 실시간 전송되었습니다.\n주문 번호가 호출되면 픽업대에서 수령해 주세요!",
            font=self.fonts.BODY_DESC,
            fg=CLR_TEXT_MUTED,
            bg=CLR_CARD_BG,
            justify="center",
        )
        guide_lbl.pack(pady=16)

        # 확인 버튼 (머스터드 골드 #F4B942, 카운트다운 포함)
        self.countdown_sec = 5
        self.confirm_btn = tk.Button(
            modal_card,
            text=f"확인 ({self.countdown_sec}초 후 처음으로)",
            font=self.fonts.BUTTON_LARGE,
            bg=CLR_GOLD,
            fg=CLR_TEXT_BASE,
            activebackground=CLR_GOLD_HOVER,
            activeforeground=CLR_TEXT_BASE,
            relief=tk.FLAT,
            bd=0,
            pady=12,
            cursor="hand2",
            command=self._close_order_complete_modal,
        )
        self.confirm_btn.pack(fill=tk.X)

        self.confirm_btn.bind("<Enter>", lambda e: self.confirm_btn.config(bg=CLR_GOLD_HOVER))
        self.confirm_btn.bind("<Leave>", lambda e: self.confirm_btn.config(bg=CLR_GOLD))

        self._run_modal_countdown()

    def _run_modal_countdown(self) -> None:
        if self.modal_overlay and self.countdown_sec > 1:
            self.countdown_sec -= 1
            if hasattr(self, "confirm_btn") and self.confirm_btn.winfo_exists():
                self.confirm_btn.config(
                    text=f"확인 ({self.countdown_sec}초 후 처음으로)"
                )
            self.modal_timer_id = self.after(1000, self._run_modal_countdown)
        else:
            self._close_order_complete_modal()

    def _close_order_complete_modal(self) -> None:
        if self.modal_timer_id:
            try:
                self.after_cancel(self.modal_timer_id)
            except Exception:
                pass
            self.modal_timer_id = None

        if self.modal_overlay and self.modal_overlay.winfo_exists():
            self.modal_overlay.destroy()
            self.modal_overlay = None


if __name__ == "__main__":
    app = ModernGimbapKiosk()
    app.mainloop()
