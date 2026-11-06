# 🛒 멀티 클라이언트 키오스크 및 주방/고객 연동 시스템

본 프로젝트는 **FastAPI** 중앙 서버와 **MySQL** 데이터베이스를 기반으로, 여러 대의 독립된 키오스크와 주방 화면, 그리고 **고객용 가상 모바일 폰**이 실시간으로 연동되는 통합 주문 및 매장 관리 시스템입니다.

---

## 🛠️ 1. 기술 스택 (Tech Stack)

| 구분 | 사용 기술 및 라이브러리 |
| :--- | :--- |
| **Backend Server** | Python 3.x, FastAPI, Uvicorn |
| **Database** | MySQL (`pymysql` / `mysql-connector-python`) |
| **GUI Clients** | Python `Tkinter` (내장 GUI 라이브러리) |
| **Communication & Protocol** | HTTPS REST API (`requests`), Background Polling (1~2초 간격) |
| **Security & Authentication** | 1) **HTTPS (SSL/TLS)** 통신 구간 암호화 (`cert.pem`, `key.pem`)<br/>2) **API 키(API Key)** 기반 클라이언트 인증 헤더 (`access_token`) |

---

## 🏗️ 2. 시스템 아키텍처 및 구성

시스템은 하나의 중앙 서버와 4개의 독립된 `Tkinter` 클라이언트 프로그램으로 구성됩니다.

1. **중앙 서버 (`server.py`):** FastAPI 기반 백엔드, HTTPS(SSL/TLS) 및 API Key 인증 적용, MySQL DB와 연동하여 주문 접수 및 상태 관리
2. **보다수 커피 키오스크 (`kiosk_client1.py`):** 음료 메뉴(`HOT`/`ICE` 선택, 포장/매장식사, 수저 옵션) 주문 기기
3. **김밥천국 키오스크 (`kiosk_client2.py`):** 김밥 및 식사 메뉴(`당근`/`오이` 제외, 포장/매장식사, 수저 옵션) 주문 기기
4. **주방 화면 (`kitchen_client.py`):** 신규 주문 폴링 조회, **[주문 접수]** 및 **[조리 완료]** 처리
5. **고객용 가상 모바일 폰 (`app_client.py`):** 스마트폰 형태의 UI를 띄워 주문 상태 변경(*조리 시작 안내*) 및 *조리 완료 픽업 알림*을 실시간 문자/알림톡 형태로 폴링 수신

---

## ☕ 3. 매장별 메뉴 및 옵션 구성

### 1) 보다수 커피 (`KIOSK_01` - `kiosk_client1.py`)
* **공통 옵션**: 매장 식사 / 포장 (To-go) | 수저 필요 여부
* **음료별 옵션**: `HOT` / `ICE` 선택 가능
* **메뉴 구성 (12종)**:
  * **커피**: 아메리카노(3,000원), 카페라떼(3,500원), 바닐라라떼(4,000원), 헤이즐럿라떼(4,000원), 돌체라떼(4,500원)
  * **스무디**: 플레인 요거트 스무디(4,500원), 딸기 요거트 스무디(4,800원)
  * **차/기타**: 아이스티(3,000원), 레몬차(4,000원), 자몽차(4,000원), 유자차(4,000원), 쌍화탕(4,500원)

### 2) 김밥천국 (`KIOSK_02` - `kiosk_client2.py`)
* **공통 옵션**: 매장 식사 / 포장 (To-go) | 수저 필요 여부
* **김밥류 전용 옵션**: `당근 제외` / `오이 제외` 선택 가능
* **메뉴 구성 (11종)**:
  * **김밥류**: 기본 김밥(3,000원), 참치김밥(4,000원), 치즈김밥(4,000원), 돈가스 김밥(4,500원), 야채 김밥(3,500원), 땡초김밥(4,000원), 제육김밥(4,500원)
  * **식사/분식류**: 돈가스(8,000원), 라면(4,000원), 우동(5,000원), 떡볶이(4,500원)

---

## 🔄 4. 핵심 동작 시나리오

### [1단계] 주문하기 (키오스크 $\rightarrow$ 중앙 서버 $\rightarrow$ DB)
* **주체:** 키오스크 (보다수 커피 또는 김밥천국)
* **동작:** 손님이 메뉴와 옵션을 선택하고 모의 결제 버튼을 누름.
* **통신:** 키오스크가 백그라운드 스레드를 통해 FastAPI 서버로 HTTPS 주문 요청 전송 (`POST /order`, `access_token` API 키 헤더 포함).
* **결과:** 중앙 서버가 API 키 검증 후 MySQL 데이터베이스(`orders`, `order_items`)에 안전하게 저장(초기 상태: `PENDING`).

### [2단계] 주방에서 확인 및 접수 (주방 화면 $\leftrightarrow$ 중앙 서버 $\leftrightarrow$ 고객용 가상 모바일 폰)
* **주체:** 주방 화면 (`kitchen_client.py`)
* **동작:** 주방 화면이 켜져 있는 동안 백그라운드 스레드에서 **1~2초 간격으로 폴링(Polling)** 요청 (`GET /orders/pending`, *"새 주문이 있나요?"*).
* **결과:** 중앙 서버가 미접수된 주문 내역을 주방 화면에 전달.
* **접수 처리:** 주방 직원이 **[주문 접수]** 버튼을 누르면, 주방 화면이 서버로 상태 변경 요청(`PATCH /orders/{order_id}/accept`)을 보냄 (`COOKING` 상태로 변경). **고객용 가상 모바일 폰** 또한 폴링을 통해 이를 감지하고 스마트폰 화면에 *"고객님의 주문이 접수되어 조리 시작되었습니다"* 알림 배너/메시지 표시.

### [3단계] 조리 완료 및 알림 받기 (고객용 가상 모바일 폰 $\leftrightarrow$ 중앙 서버)
* **주체:** 주방 화면 (`kitchen_client.py`) 및 고객용 가상 모바일 폰 (`app_client.py`)
* **조리 완료:** 주방 직원이 요리가 끝나고 **[조리 완료]** 버튼을 누르면(`PATCH /orders/{order_id}/complete`), 서버 DB에 해당 주문 상태가 `COMPLETED`로 변경되고 알림 데이터 생성.
* **폴링 통신:** 고객용 가상 모바일 폰이 백그라운드 스레드에서 **1~2초 간격**으로 서버에 확인 (`GET /orders/{order_id}/status`, *"내 번호로 온 알림이 있니?"*).
* **결과:** 중앙 서버가 조리 완료 데이터를 전송하고, **고객용 가상 모바일 폰** 화면에 픽업 알림 메시지/팝업 출력.

---

## 🧵 5. 멀티스레딩(Multi-threading) 적용 위치

* **키오스크 (`kiosk_client1.py`, `kiosk_client2.py`):** 결제 버튼을 누르고 서버와 HTTPS 통신할 때 메인 화면(UI)이 멈추는(렉) 현상을 방지하기 위해 백그라운드 스레드 사용.
* **주방 화면 (`kitchen_client.py`):** 1~2초 간격으로 서버에 신규 주문을 조회(폴링)하기 위한 백그라운드 반복 스레드 구동.
* **고객용 가상 모바일 폰 (`app_client.py`):** 1~2초 간격으로 주문 상태 변화 및 조리 완료 알림을 조회(폴링)하기 위한 백그라운드 반복 스레드 구동.
* *참고:* UI 조작은 `Tkinter` 메인 스레드 안전 규칙(`root.after()` 등)을 준수하며, 데이터 동기화는 중앙 MySQL 데이터베이스를 거치므로 복잡한 스레드 락(Lock) 구현 없이 안전하게 처리됩니다.

---

## 🔒 6. 보안 및 인증 설계

1. **HTTPS (SSL/TLS) 통신 구간 암호화:**
   * 자체 서명 SSL 인증서(`cert.pem`, `key.pem`)를 생성하여 Uvicorn 서버에 적용합니다.
   * 클라이언트와 중앙 서버 간 전송되는 모든 HTTP 헤더(`access_token`) 및 주문 데이터(JSON 페이로드)를 SSL/TLS로 암호화하여 패킷 스니핑 및 중간자 공격(MITM)을 방지합니다.
2. **API 키 기반 클라이언트 인증:**
   * 인가된 클라이언트(키오스크 1·2, 주방 화면, 고객용 가상 모바일 폰)와 중앙 서버 간에 공유된 비밀 API 키를 사용합니다.
   * 서버로 요청을 보낼 때 HTTP 헤더(`access_token`)에 API 키를 담아 전송하며, 서버는 FastAPI의 `Security`(`APIKeyHeader`) 기능을 통해 이를 검증하여 유효한 기기의 요청만 허용하고 외부 접근을 안전하게 차단합니다.

---

## 🗄️ 7. 데이터베이스 테이블 구조 (MySQL Schema)

* `stores`: 매장/키오스크 기기 정보 (`store_id`, `store_name`, `device_ip`)
* `menus`: 메뉴 정보 (`menu_id`, `store_id`, `category`, `menu_name`, `price`)
* `orders`: 주문 마스터 및 상태 정보 (`order_id`, `store_id`, `order_type`, `spoon_needed`, `total_price`, `status`, `notified_accepted`, `notified_completed`, `order_time`)
* `order_items`: 주문 세부 옵션 정보 (`item_id`, `order_id`, `menu_id`, `quantity`, `temperature`, `exclude_carrot`, `exclude_cucumber`)

---

## 🚀 8. 실행 방법 (Quick Start)

### 1단계: 필요 라이브러리 설치
```bash
pip install fastapi uvicorn pymysql requests cryptography
```

### 2단계: SSL 인증서 생성 및 중앙 서버 실행
```bash
python generate_cert.py
python server.py
```

### 3단계: 4개 클라이언트 실행 (개별 터미널 창)
```bash
# 1. 보다수 커피 키오스크 실행
python kiosk_client1.py

# 2. 김밥천국 키오스크 실행
python kiosk_client2.py

# 3. 주방 화면 실행
python kitchen_client.py

# 4. 고객용 가상 모바일 폰 실행
python app_client.py
```
