# 보다수 키오스크

커피·김밥 키오스크, 주방 종합창과 HTTPS 중앙 서버를 기능별 모듈로 구성한 Python 프로젝트입니다. 화면은 Tkinter 기반 CustomTkinter를 사용합니다.

## 실행

**아이폰 로컬 시연:** `start-mobile.bat`을 실행하세요. PC와 아이폰을 같은 와이파이에 연결하고, 표시되는 준비 페이지에서 인증서 설치 → 홈 화면 추가 → 알림 허용을 진행합니다. [아이폰 시연 안내](docs/MOBILE_DEMO.md)에 전체 절차가 있습니다. 앱 주문은 `A001`처럼 표시되고 기존 주방 종합창에서 처리됩니다. 결제 없는 PWA 시연이며, 실제 푸시는 인터넷 연결이 필요합니다.

Windows에서는 **`start.bat`을 더블클릭**하세요. 프로젝트 가상환경을 사용하며, 필요한 패키지가 없으면 최초 설치합니다. 실행창에서 **보다수 커피 / 김밥천국 / 주방 종합창**을 선택합니다. 이미 실행 중인 서버가 있으면 연결해서 사용합니다.

관리자 로그인 초기 비밀번호는 **`1234`**입니다. 운영 센터 하단의 **관리자 비밀번호 변경**에서 현재 비밀번호와 새 비밀번호를 입력해 변경합니다. 새 비밀번호는 8~128자이며, 확인 입력이 일치해야 합니다.

프로젝트 루트의 `.env.admin`에는 무작위 솔트와 scrypt 해시만 저장하며, Git에 포함하지 않습니다. 파일이 처음 없을 때만 초기 설정을 생성합니다. 손상된 파일은 초기 비밀번호로 자동 복구하지 않습니다. 운영 센터와 주방 화면 실행 시 로그인하며, 주방은 독립 프로세스이므로 별도로 로그인합니다. 커피·김밥 고객 화면에는 관리자 비밀번호를 요구하지 않습니다.

이 인증은 로컬 관리자 화면 접근용입니다. 서버 REST API는 기존 API Key 인증을 사용하며 관리자 로그인 세션과 연동되지 않습니다. `.env.admin` 파일과 소스코드의 접근 권한은 운영체제 계정으로 관리해야 합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

가상환경이 활성화되어 있다면 `python app.py`로 실행합니다.
실행창이 서버를 자동으로 시작하며, 서버 준비 후 **보다수 커피 / 김밥천국** 버튼으로 매장 화면을 엽니다.
실행창을 닫으면 해당 실행창에서 시작한 서버와 매장 화면을 함께 종료합니다.
다른 실행창에서 시작한 서버는 종료하지 않습니다. 실행 오류는 `logs/server.log`에 기록됩니다.

서버나 매장 화면만 실행할 수도 있습니다. 매장 단독 실행 시 서버가 먼저 실행 중이어야 합니다.

```powershell
python app.py --mode server
python app.py --mode coffee
python app.py --mode gimbap
python app.py --mode kitchen
```

## 구조

```text
app.py                    # 모든 실행 모드의 진입점
kiosk/
  launcher.py             # 통합 실행창, 서버 준비 확인, 자식 프로세스 종료
  server.py               # FastAPI 앱과 HTTPS 서버 실행
  config.py               # 네트워크·API Key·파일 경로 설정
  certificates.py         # 자체 서명 인증서 생성
  schemas.py              # API 요청·응답 규격
  api/
    security.py           # 공통 API Key 인증
    menus.py              # 메뉴 조회
    orders.py             # 주문 생성
    kitchen.py            # 주방 주문 조회·접수·완료
    notifications.py      # 고객 알림 조회
  storage/
    connection.py         # SQLite 연결, WAL·외래키 설정
    setup.py              # 테이블 생성과 초기 데이터 적재
    seed.py               # 매장·메뉴 초기 데이터
    menus.py              # 메뉴 조회 SQL
    orders.py             # 주문 트랜잭션과 상태 관리 SQL
    notifications.py      # 알림 조회와 수신 상태 SQL
  clients/
    api.py                # 클라이언트 HTTP 통신·인증 헤더·타임아웃
    ui.py                 # 공통 색상·폰트·버튼·창·메뉴 일러스트
    cart.py               # UI에 의존하지 않는 장바구니 규칙·주문 데이터 구성
    base.py               # 고객 메뉴·옵션·장바구니·주문 확인·접수번호 화면
    coffee.py             # 커피 매장 설정
    gimbap.py             # 김밥 매장 설정
    kitchen.py            # 주방 카드 보드·매장 필터·접수·조리 완료
examples/
  mega_kiosk.py           # 기존 CustomTkinter 디자인 실험 (통합 앱과 별개)
docs/                     # 기존 기획·발표 자료와 이전 README
tests/                   # 임시 DB 주문 흐름·공통 클라이언트 검증
```

`kiosk.db`, `cert.pem`, `key.pem`은 기존 프로젝트 루트 경로를 그대로 사용합니다.
환경변수 `BDS_SERVER_HOST`, `BDS_SERVER_PORT`, `BDS_API_KEY`도 유지합니다.

고객 화면은 메뉴 선택 → 옵션 선택 → 주문 확인 → 접수번호 순서로 진행합니다. 주방 종합창은 두 매장의 접수 대기·조리 중 주문을 1.5초 간격으로 조회하고, 접수·완료를 처리합니다. `F11`로 전체화면, `Esc`로 전체화면을 해제합니다.

실제 결제 단말기와 영수증 프린터는 연동하지 않습니다. 고객 모바일 알림은 REST API만 제공하며, 별도 모바일 GUI는 아직 없습니다.
API 문서는 기본 `https://127.0.0.1:8443/docs`에서 확인합니다. 자체 서명 인증서이므로 브라우저에서 인증서 확인이 필요할 수 있습니다.

`docs/`의 기존 문서는 개편 이전 파일명을 포함하는 당시 자료입니다. 현재 실행 방법과 파일 위치는 이 README를 기준으로 합니다.
API·UI·DB별 변경 위치와 의존 관계는 [유지보수 안내](docs/MAINTENANCE.md)를 확인하세요.

## 검증

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

테스트는 임시 DB를 사용합니다. 두 매장 메뉴 수, 인증, 매장별 옵션, 주문 금액, 주문 접수·완료, 알림 중복 수신 방지, 실패 시 롤백과 공통 장바구니·전송 데이터를 검증합니다.
