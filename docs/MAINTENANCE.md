# 유지보수 안내

현재 구현의 기준 문서입니다. 같은 폴더의 기존 기획 문서는 개편 전 파일명을 포함합니다.

## 책임과 의존 방향

```text
CustomTkinter 화면 (clients/base.py, clients/kitchen.py)
    → HTTP 클라이언트 (clients/api.py)
    → FastAPI 라우터 (api/)
    → SQLite 쿼리·트랜잭션 (storage/)

UI 공통 디자인: clients/ui.py
장바구니 규칙: clients/cart.py
요청·응답 계약: schemas.py
환경·경로: config.py
앱 조립과 실행: server.py, launcher.py, 프로젝트 루트 app.py
```

클라이언트는 DB를 직접 읽지 않습니다. 메뉴 조회도 HTTPS API를 사용합니다. 서버 API와 DB 모듈은 Tkinter를 import하지 않습니다.

## UI 유지보수

| 변경할 내용 | 파일 / 위치 |
|---|---|
| 공통 색상·폰트·버튼·전체화면·창 크기 | `kiosk/clients/ui.py` |
| 메뉴 종류별 일러스트 | `ui.py`의 `menu_art` |
| 메뉴 카드·카테고리·장바구니 배치 | `base.py`의 `_build_ui`, `_build_checkout`, `render_menus` |
| 옵션·주문 확인·접수번호 팝업 | `base.py`의 `open_options`, `confirm_order`, `show_success` |
| 매장 이름과 식별 코드 | `coffee.py`, `gimbap.py` |
| 동일 메뉴·옵션 병합, 합계와 주문 JSON 구성 | `cart.py` |
| 주방 주문 카드·상태별 열·매장 필터 | `kitchen.py`의 `_build_ui`, `render_orders`, `_order_card` |
| 실행창 디자인과 프로세스 수명 | `kiosk/launcher.py` |

네트워크 작업은 백그라운드 스레드에서 실행하고 결과를 `queue.Queue`에 넣습니다. 위젯은 `after`로 실행되는 메인 스레드에서만 변경합니다. 서버 응답이 오기 전에는 중복 접수와 장바구니 변경을 막습니다. 주문 POST는 통신 실패 시 자동 재시도하지 않습니다.

## API 유지보수

| API | 서버 라우터 | DB 처리 |
|---|---|---|
| `GET /menus/{store_id}` | `api/menus.py` | `storage/menus.py` |
| `POST /order` | `api/orders.py` | `storage/orders.py` |
| `GET /orders/kitchen` | `api/kitchen.py` | `storage/orders.py` |
| `PATCH /orders/{id}/accept`, `/complete` | `api/kitchen.py` | `storage/orders.py` |
| `GET /orders/notifications` | `api/notifications.py` | `storage/notifications.py` |
| 공통 인증 | `api/security.py` | — |

JSON 필드를 바꾸면 `schemas.py`, 해당 라우터, `clients/cart.py` 또는 화면의 응답 처리, API 테스트를 함께 확인합니다. 연결 주소, 헤더, 타임아웃 처리는 `clients/api.py`와 `config.py`에서 관리합니다. UI에서 직접 `requests` 요청을 추가하지 않습니다.

## DB 유지보수

- 연결·WAL·외래키 설정: `storage/connection.py`
- 테이블 생성 및 최초 적재: `storage/setup.py`
- 최초 메뉴 데이터: `storage/seed.py`
- 기능별 SQL: `storage/menus.py`, `orders.py`, `notifications.py`
- 운영 파일: 프로젝트 루트 `kiosk.db`

`seed.py`는 빈 메뉴 테이블의 최초 적재용입니다. 값을 고쳐도 기존 DB 메뉴는 자동 수정되지 않습니다. 기존 메뉴 변경은 DB 백업 후 명시적인 UPDATE로 처리합니다. 테이블 구조를 바꿀 때는 기존 DB에 적용할 마이그레이션도 별도로 작성해야 합니다. 주문과 품목은 현재와 같이 하나의 트랜잭션으로 저장합니다.

## 변경 후 확인

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

API 테스트는 임시 DB를 사용합니다. `tests/gui_smoke.py`는 실제 창을 잠시 표시하고 네트워크와 DB를 대체해 UI 흐름을 검증합니다. 스크린샷은 `logs/ui-review/`에 저장하며 Git에 포함하지 않습니다.

```powershell
.\.venv\Scripts\python.exe tests/gui_smoke.py coffee
.\.venv\Scripts\python.exe tests/gui_smoke.py gimbap
.\.venv\Scripts\python.exe tests/gui_smoke.py kitchen
.\.venv\Scripts\python.exe tests/gui_smoke.py launcher
```

실제 카드 결제·영수증 프린터·고객 모바일 알림 GUI는 현재 구현에 포함되지 않습니다. 접수 완료는 결제 완료를 의미하지 않습니다.

## 관리자 인증 유지보수

- `kiosk/admin_auth.py`: scrypt 해시·검증, 초기화, 현재 비밀번호 확인 후 변경, 원자적 파일 저장. UI·HTTP·주문 DB에 의존하지 않습니다.
- `kiosk/clients/admin.py`: 로그인·비밀번호 변경 폼. 해시 연산은 작업 스레드에서 실행하고 UI는 큐 결과를 처리합니다. 같은 폼에서 5회 실패하면 30초 대기합니다. 이 제한은 프로세스 재시작으로 초기화되는 화면 수준의 제한입니다.
- `app.py`: 운영 센터와 주방 실행 전에 로그인 성공을 확인합니다. 고객 화면·서버 실행 모드에는 이 로컬 로그인 관문을 적용하지 않습니다.
- `kiosk/config.py`의 `ADMIN_ENV_FILE`: 프로젝트 루트 `.env.admin` 경로.
- `.env.admin`: `ADMIN_PASSWORD_HASH`, `ADMIN_PASSWORD_INITIAL` 두 항목. 생성·변경은 관리자 모듈에 맡기고 수동으로 비밀번호 평문을 넣지 않습니다. 삭제하면 다음 실행 시 초기 비밀번호로 새로 생성되므로, 실제 운영에서는 해당 파일과 소스코드에 대한 OS 쓰기 권한을 제한해야 합니다.

해시 형식은 `scrypt$131072$8$1$<16바이트 솔트 hex>$<32바이트 해시 hex>`입니다. 무작위 솔트와 상수 시간 비교를 사용합니다. 초기 비밀번호는 요청된 `1234`이고, 변경 시 8~128자를 요구합니다. 저장 오류가 나면 이전 설정을 유지합니다. 이미 열린 관리자 화면은 비밀번호 변경으로 강제 로그아웃되지 않으며, 다음 로그인부터 새 비밀번호가 필요합니다.

관리자 화면 로그인과 기존 REST API Key는 별개입니다. 네트워크 API에 사용자별 관리자 권한이 필요해지면 서버 측 로그인·세션·권한 검증을 별도로 추가해야 합니다.

검증: `tests/test_admin_auth.py`는 임시 파일로 초기화·비밀번호 변경·손상·저장 실패·접근 관문을 확인합니다. `tests/gui_admin_smoke.py`는 임시 인증 파일로 실제 로그인·변경 UI를 검증하며 운영 비밀번호를 변경하지 않습니다.
# 모바일 픽업 앱

모바일 UI는 `mobile/`, API는 `kiosk/api/mobile.py`, 데이터 처리는 `kiosk/storage/`에서 관리합니다. 주문 저장 로직은 Tkinter 키오스크와 모바일이 공유합니다. 푸시 네트워크 발송은 `kiosk/push.py`의 별도 작업 스레드가 담당합니다. 파일별 역할과 로컬 아이폰 설치 절차는 [MOBILE_DEMO.md](MOBILE_DEMO.md)를 참고하세요.
