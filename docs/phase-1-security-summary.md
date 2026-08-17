# Phase 1 — Security Hardening Summary

## 1. Mục tiêu giai đoạn
Đưa ứng dụng ToDoList AI về trạng thái an toàn cơ bản sẵn sàng deploy public mà không refactor kiến trúc lớn, không thay đổi AI workflow, và không triển khai các tính năng nâng cao của các giai đoạn sau (như queue, pagination, cookie refactor).

Phạm vi chính bao gồm:
- Loại bỏ bí mật hard-code, thêm validation fail-fast cho cấu hình production.
- Rút ngắn thời hạn JWT access token về mức an toàn.
- Cấu hình CORS allowlist tường minh, loại bỏ regex wildcard.
- Vô hiệu hoá nút demo/quick-login trong production bundle và code execution path.
- Chuẩn hoá quy trình xác minh Google ID Token server-side bằng thư viện chính thức.
- Áp dụng rate limiting theo IP cho các API nhạy cảm và bổ sung input validation nghiêm ngặt.
- Chuẩn hoá error response, che giấu raw stack trace / raw exception khỏi API client và redact credential trong log.
- Viết bộ unit test tự động và cập nhật tài liệu cấu hình môi trường.

---

## 2. Tổng quan thay đổi

| Hạng mục | Trạng thái | File liên quan | Kết quả |
| :--- | :--- | :--- | :--- |
| **Secret & Configuration** | Hoàn thành | `backend/app/config.py`, `backend/.env.example` | Loại bỏ fallback hard-code; thêm fail-fast validator cho `APP_ENV=production`. |
| **JWT Expiration** | Hoàn thành | `backend/app/config.py`, `backend/app/auth.py` | TTL mặc định giảm từ 24h xuống 60 phút, động theo `ACCESS_TOKEN_EXPIRE_MINUTES`. |
| **CORS Restriction** | Hoàn thành | `backend/app/config.py`, `backend/app/main.py` | Gỡ `allow_origin_regex`; chỉ dùng allowlist tường minh từ `FRONTEND_URL` và `CORS_ALLOWED_ORIGINS`. |
| **Demo Login Safety** | Hoàn thành | `frontend/src/App.jsx`, `frontend/.env`, `frontend/.env.example` | Nút demo đổi tên thành *"Development demo login"*, chỉ render & thực thi khi `VITE_DEV_DEMO_ENABLED === 'true'`. |
| **Google Sign-In Verification** | Hoàn thành | `backend/app/main.py`, `backend/requirements.txt` | Xác minh ID token qua `google.oauth2.id_token` với đầy đủ kiểm tra `aud`, `iss`, `exp`, `email_verified`. |
| **Rate Limiting** | Hoàn thành | `backend/app/main.py`, `backend/app/config.py`, `backend/requirements.txt` | Áp dụng `slowapi` cho `/api/auth/register`, `/api/auth/login`, `/api/auth/google-login`, `/api/chat`. Trả HTTP 429 khi vi phạm. |
| **Input Validation** | Hoàn thành | `backend/app/models.py` | Ràng buộc độ dài password (8-128), title (max 200), description (max 2000), chat message (max 2000), chặn chuỗi toàn khoảng trắng. |
| **Error Handling & Logging** | Hoàn thành | `backend/app/main.py` | Thêm global exception handlers, giấu raw exception detail khỏi response client, redact credentials khi log. |
| **Automated Security Tests** | Hoàn thành | `backend/tests/test_security.py`, `backend/tests/__init__.py` | Viết 7 unit tests tự động với pytest và FastAPI TestClient (mock MongoDB dependency). |
| **Security Documentation** | Hoàn thành | `README.md`, `backend/.env.example`, `frontend/.env.example` | Cập nhật tài liệu cấu hình môi trường, hướng dẫn demo mode và lưu ý bảo mật. |

---

## 3. Thay đổi chi tiết

### 3.1 Configuration và JWT
- **Vấn đề ban đầu:** `SECRET_KEY` trong `backend/app/config.py` có giá trị fallback hard-code không an toàn (`"e83a45a3..."`). TTL của JWT token bị gán cứng 1440 phút (24 giờ).
- **Cách triển khai:** 
  - Khai báo thêm biến môi trường: `APP_ENV`, `CORS_ALLOWED_ORIGINS`, `DEV_DEMO_ENABLED`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_CHAT`.
  - Giảm `ACCESS_TOKEN_EXPIRE_MINUTES` mặc định xuống `60` phút.
  - Sử dụng Pydantic `model_validator(mode="after")` trong `Settings`: Nếu `APP_ENV == "production"`, hệ thống ném `ValueError` ngay lúc khởi động nếu `SECRET_KEY` bị thiếu, dưới 32 ký tự, hoặc khớp với danh sách placeholder nguy hiểm; đồng thời kiểm tra `MONGODB_URL`, `FRONTEND_URL`, `GOOGLE_CLIENT_ID`.
  - Trong `backend/app/auth.py`, hàm `create_access_token` tự động đọc `settings.ACCESS_TOKEN_EXPIRE_MINUTES`.
- **File & Symbol chính:** 
  - `backend/app/config.py`: `Settings`, `PLACEHOLDER_SECRETS`, `validate_security_settings()`, `get_cors_origins()`.
  - `backend/app/auth.py`: `create_access_token()`.
- **Hành vi mới:** Server dừng khởi động ngay ở môi trường production nếu thiếu cấu hình bảo mật. Token hết hạn sau 60 phút thay vì 24h.
- **Lưu ý deployment:** Bắt buộc đặt `APP_ENV=production` và sinh `SECRET_KEY` ngẫu nhiên mạnh (`openssl rand -hex 32`) trên server production.

### 3.2 CORS
- **Vấn đề ban đầu:** Middleware CORS trong `backend/app/main.py` dùng `allow_origin_regex=r"https?://.*"`, cho phép bất kỳ trang web nào gửi cross-origin request có `allow_credentials=True`.
- **Cách triển khai:** 
  - Loại bỏ hoàn toàn thuộc tính `allow_origin_regex`.
  - Xây dựng phương thức `settings.get_cors_origins()` hợp nhất danh sách origin từ `FRONTEND_URL` và `CORS_ALLOWED_ORIGINS` (phân tách bởi dấu phẩy). Chỉ cho phép các origin localhost (`http://localhost:5173`, `http://127.0.0.1:5173`, v.v.) khi `APP_ENV == "development"`.
- **File & Symbol chính:** 
  - `backend/app/config.py`: `Settings.get_cors_origins()`.
  - `backend/app/main.py`: `CORSMiddleware`.
- **Hành vi mới:** Cross-origin request từ origin không thuộc allowlist bị trình duyệt chặn CORS preflight.

### 3.3 Demo login / Development-only behavior
- **Vấn đề ban đầu:** `frontend/src/App.jsx` chứa nút *"Chạy Thử Nghiệm Nhanh (Bypass Google Auth)"* dùng email/password test hardcode trong mã nguồn bundle (`testuser@gmail.com` / `testpassword123`).
- **Cách triển khai:** 
  - Đổi tên nút thành *"Development demo login"*.
  - Kiểm tra điều kiện `import.meta.env.VITE_DEV_DEMO_ENABLED === 'true'`. Chỉ khi biến này bằng `'true'` thì nút mới được render trên UI và handler `handleLocalBypassLogin` mới cho phép chạy.
  - Chuyển credentials demo sang đọc từ `import.meta.env.VITE_DEV_DEMO_EMAIL` và `import.meta.env.VITE_DEV_DEMO_PASSWORD` với fallback an toàn cho môi trường dev local.
- **File & Symbol chính:** 
  - `frontend/src/App.jsx`: `IS_DEV_DEMO_ENABLED`, `handleLocalBypassLogin()`.
  - `frontend/.env.example`, `frontend/.env`: `VITE_DEV_DEMO_ENABLED=false`.
- **Hành vi mới:** Trong production build (`VITE_DEV_DEMO_ENABLED=false`), giao diện đăng nhập hoàn toàn không hiển thị nút demo.

### 3.4 Google Sign-In
- **Vấn đề ban đầu:** Endpoint `/api/auth/google-login` tự gọi HTTP endpoint `https://oauth2.googleapis.com/tokeninfo` không qua kiểm tra audience (`aud`), issuer (`iss`), chữ ký RSA hay trạng thái `email_verified`.
- **Cách triển khai:** 
  - Tích hợp thư viện chính thức `google-auth` (`google.oauth2.id_token`).
  - Thực hiện xác minh 5 bước: Chữ ký token với public key Google, expiration (`exp`), `aud == settings.GOOGLE_CLIENT_ID`, `iss` thuộc Google (`accounts.google.com`), và `email_verified == True`.
  - Trả HTTP 400 với thông điệp chung nếu xác minh thất bại; không trả raw exception detail.
- **File & Symbol chính:** 
  - `backend/app/main.py`: `POST /api/auth/google-login`, `id_token.verify_oauth2_token()`.
  - `backend/requirements.txt`: `google-auth>=2.0.0`.
- **Hành vi mới:** ID token giả mạo, hết hạn, chưa verify email hoặc sai audience sẽ bị từ chối với HTTP 400.

### 3.5 Rate limiting và validation
- **Vấn đề ban đầu:** Chưa giới hạn số lượng request theo IP. Schemas chưa giới hạn độ dài input, nhận chuỗi toàn khoảng trắng hoặc password ngắn/yếu.
- **Cách triển khai:** 
  - Cài đặt và tích hợp `slowapi` (`Limiter(key_func=get_remote_address)`).
  - Áp dụng trang trí `@limiter.limit(settings.RATE_LIMIT_AUTH)` cho `/api/auth/register`, `/api/auth/login`, `/api/auth/google-login` (mặc định 5 req/phút).
  - Áp dụng `@limiter.limit(settings.RATE_LIMIT_CHAT)` cho `/api/chat` (mặc định 20 req/phút).
  - Bổ sung validation Pydantic trong `backend/app/models.py`:
    - `UserRegister`: `password` 8-128 ký tự, validator chặn khoảng trắng rỗng.
    - `UserLogin`: `password` 1-128 ký tự, validator chặn khoảng trắng rỗng.
    - `TodoCreate` / `TodoUpdate`: `title` max 200 ký tự (chặn khoảng trắng rỗng), `description` max 2000 ký tự.
    - `ChatMessagePayload`: `message` 1-2000 ký tự (chặn khoảng trắng rỗng).
- **File & Symbol chính:** 
  - `backend/app/main.py`: `limiter`, `custom_rate_limit_handler()`, `@limiter.limit()`.
  - `backend/app/models.py`: `UserRegister`, `UserLogin`, `TodoCreate`, `TodoUpdate`, `ChatMessagePayload`.
- **Hành vi mới:** Gửi quá số lượng request nhận HTTP 429 (`"Bạn đã gửi quá nhiều yêu cầu..."`). Gửi password dưới 8 ký tự hoặc title/chat toàn khoảng trắng nhận HTTP 422.

### 3.6 Error handling và logging
- **Vấn đề ban đầu:** Một số endpoint dùng `except Exception as e` và trả về `detail=f"... {str(e)}"` làm rò rỉ thông tin nội bộ (như lỗi kết nối DB, stack trace hoặc lỗi provider).
- **Cách triển khai:** 
  - Thêm `@app.exception_handler(RateLimitExceeded)` trả về HTTP 429 JSON chuẩn hoá.
  - Thêm `@app.exception_handler(Exception)` bắt mọi ngoại lệ không mong muốn, ghi log phía server (không ghi password/token) và trả về HTTP 500 JSON trung tính (`"Đã xảy ra lỗi máy chủ nội bộ. Vui lòng thử lại sau."`).
  - Loại bỏ các chuỗi `str(e)` trong `google_login` và `send_chat_message`.
- **File & Symbol chính:** 
  - `backend/app/main.py`: `global_exception_handler()`, `logger`.
- **Hành vi mới:** Phía client không còn nhận được raw Python exception string hay traceback khi có lỗi hệ thống.

### 3.7 Tests và quality checks
- **Vấn đề ban đầu:** Chưa có thư mục test tự động cho backend security.
- **Cách triển khai:** 
  - Tạo bộ unit test `backend/tests/test_security.py` sử dụng `pytest` và `fastapi.testclient.TestClient`.
  - Sử dụng FastAPI `dependency_overrides[get_db]` để mock MongoDB database, đảm bảo test chạy độc lập không phụ thuộc vào cơ sở dữ liệu thật.
  - Viết 7 test cases bao phủ: Fail-fast configuration, JWT TTL, CORS allowlist, Password length validation, Title/Chat payload validation, Google auth rejection, và Rate limiting HTTP 429.
- **File & Symbol chính:** 
  - `backend/tests/test_security.py`, `backend/tests/__init__.py`.
- **Hành vi mới:** Có thể kiểm thử tự động toàn bộ tính năng bảo mật bằng lệnh `pytest`.

### 3.8 Documentation / environment variables
- **Vấn đề ban đầu:** `.env.example` thiếu nhiều biến cấu hình bảo mật mới. README thiếu hướng dẫn chi tiết về thiết lập an toàn.
- **Cách triển khai:** 
  - Cập nhật `backend/.env.example` với đầy đủ các biến: `APP_ENV`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `GOOGLE_CLIENT_ID`, `DEV_DEMO_ENABLED`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_CHAT`.
  - Tạo `frontend/.env.example` bổ sung `VITE_DEV_DEMO_ENABLED`.
  - Bổ sung phần **Security Configuration** và hướng dẫn **Local Development Demo Login** vào `README.md`.
- **File & Symbol chính:** 
  - `README.md`, `backend/.env.example`, `frontend/.env.example`.

---

## 4. API và hành vi thay đổi

### Endpoints có sự thay đổi về hành vi:
1. `POST /api/auth/register`
   - Bổ sung Rate Limit (mặc định 5 req/phút). Vượt quá nhận HTTP `429 Too Many Requests`.
   - Bổ sung Password Validation (8–128 ký tự, không được chỉ chứa toàn khoảng trắng). Mật khẩu yếu nhận HTTP `422 Unprocessable Content`.
2. `POST /api/auth/login`
   - Bổ sung Rate Limit (mặc định 5 req/phút). Vượt quá nhận HTTP `429`.
   - Bổ sung Validation mật khẩu không chứa toàn khoảng trắng.
3. `POST /api/auth/google-login`
   - Bổ sung Rate Limit (mặc định 5 req/phút).
   - Thay thế cơ chế verify Google TokenInfo bằng `google.oauth2.id_token`. Token không hợp lệ/hết hạn/sai audience/chưa verify email trả về HTTP `400 Bad Request` với thông điệp an toàn.
4. `POST /api/chat`
   - Bổ sung Rate Limit (mặc định 20 req/phút).
   - Đổi request body payload sang `ChatMessagePayload` (tin nhắn từ 1–2000 ký tự, không chấp nhận toàn khoảng trắng). Vi phạm trả HTTP `422`.
   - Ngoại lệ xử lý LangGraph AI không làm rò rỉ `str(e)` ra response.
5. `POST /api/todos` & `PUT /api/todos/{todo_id}`
   - Bổ sung Pydantic validation cho `title` (max 200 ký tự, không chấp nhận toàn khoảng trắng) và `description` (max 2000 ký tự).

### Các biến môi trường mới / thay đổi mặc định:
- `APP_ENV`: Mặc định `development`.
- `SECRET_KEY`: Không còn fallback string nguy hiểm. Phải cấu hình trong `.env`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Mặc định đổi từ `1440` (24h) thành `60` (1 giờ).
- `CORS_ALLOWED_ORIGINS`: Chuỗi danh sách các origin được phép, phân tách bằng dấu phẩy.
- `DEV_DEMO_ENABLED` (Backend) & `VITE_DEV_DEMO_ENABLED` (Frontend): Mặc định `false`.
- `RATE_LIMIT_AUTH`: Mặc định `"5/minute"`.
- `RATE_LIMIT_CHAT`: Mặc định `"20/minute"`.

### Breaking changes cần lưu ý khi Frontend / Deploy kết nối:
- Đăng ký tài khoản bắt buộc mật khẩu từ 8 ký tự trở lên (trước đây nhận cả mật khẩu ngắn).
- Gửi tin nhắn chat hoặc title todo rỗng/toàn khoảng trắng sẽ bị từ chối ở tầng Pydantic (HTTP 422).
- Nếu frontend chạy ở địa chỉ domain/port khác ngoài `FRONTEND_URL` hoặc `http://localhost:5173`, bắt buộc phải khai báo domain đó vào `CORS_ALLOWED_ORIGINS` trong `backend/.env`.

---

## 5. Security decisions

1. **Fail-Fast Configuration Strategy:**
   - *Quyết định:* Trong môi trường `production` (`APP_ENV=production`), server FastAPI phải dừng khởi động lập tức nếu phát hiện `SECRET_KEY` yếu, ngắn dưới 32 ký tự, hoặc thiếu `MONGODB_URL`, `FRONTEND_URL`, `GOOGLE_CLIENT_ID`.
   - *Lý do:* Rất nhiều sự cố lộ thông tin xảy ra do ứng dụng chạy production với cấu hình mặc định/dev mà quản trị viên không hay biết.

2. **Strict CORS Allowlist mà không dùng Regex Wildcard:**
   - *Quyết định:* Loại bỏ hoàn toàn `allow_origin_regex=r"https?://.*"`.
   - *Lý do:* Cấu hình regex wildcard kết hợp `allow_credentials=True` tạo ra lỗ hổng CORS nghiêm trọng, cho phép bất kỳ trang web độc hại nào thực hiện request có chứa thông tin xác thực.

3. **Tách rời Demo Login theo Feature Flag:**
   - *Quyết định:* Đổi tên nút demo và kiểm tra biến `VITE_DEV_DEMO_ENABLED === 'true'`.
   - *Lý do:* Ngăn chặn việc lỡ tay bundle các nút bypass auth hoặc tài khoản test cố định vào bản build production.

4. **Khai thác thư viện chính thức Google Auth:**
   - *Quyết định:* Dùng `google.oauth2.id_token.verify_oauth2_token` thay vì tự gửi HTTP request tới tokeninfo API endpoint.
   - *Lý do:* Thư viện chính thức tự động kiểm tra chữ ký RSA mã hoá bằng Google public keys, xác minh thời gian hết hạn và audience chính xác hơn.

---

## 6. Validation đã thực hiện

### Lệnh thực tế đã chạy và kết quả:

1. **Backend Unit Tests (`pytest`)**
   - Lệnh: `.\venv\Scripts\pytest -v` (tại `backend/`)
   - Kết quả: **7/7 PASSED** (100%)
     - `test_production_fails_fast_on_invalid_secret_key` — **PASSED**
     - `test_jwt_ttl_from_config` — **PASSED**
     - `test_cors_origin_allowlist` — **PASSED**
     - `test_input_validation_password_length` — **PASSED**
     - `test_input_validation_title_and_message` — **PASSED**
     - `test_google_login_rejects_empty_or_invalid_token` — **PASSED**
     - `test_rate_limit_auth_endpoints` — **PASSED**

2. **Frontend Static Code Analysis (`eslint`)**
   - Lệnh: `npm run lint` (tại `frontend/`)
   - Kết quả: **PASSED** (0 errors, 0 warnings).

3. **Frontend Production Build (`vite build`)**
   - Lệnh: `npm run build` (tại `frontend/`)
   - Kết quả: **PASSED** (Bundle tạo ra thành công trong 641ms).

### Kiểm thử chưa thực hiện và lý do:
- **Xác minh Google Token thật từ Google Console Production:** Cần Google Client ID và ID Token thật do người dùng cấp trên trình duyệt thực tế. (Đã được bao phủ bằng mock validation trong unit test).
- **Load testing / Stress testing cho Rate Limit dưới lưu lượng lớn:** Chỉ mới verify chức năng rate limit phản hồi 429 thành công qua TestClient.

---

## 7. Việc còn lại / Known limitations

Các hạng mục chưa thực hiện (được phân loại theo các giai đoạn tiếp theo):

### Phase 2: Refactoring & Architecture Enhancements (Ưu tiên P1)
- [ ] **Cookie-based JWT Auth:** Chuyển JWT từ `localStorage` sang Cookie `HttpOnly; Secure; SameSite=Strict` kết hợp CSRF Protection Token.
- [ ] **Refresh Token Mechanism:** Triển khai cơ chế Refresh Token Rotation để giảm bớt rủi ro khi Access Token hết hạn 60 phút.
- [ ] **Redis Rate Limiter Storage:** Chuyển `slowapi` storage từ memory sang Redis để hỗ trợ ứng dụng khi scale-out multi-instance.

### Phase 3: Performance & Scalability (Ưu tiên P2)
- [ ] **Pagination API:** Thêm phân trang (`page`, `limit`) cho `/api/todos` và `/api/chat/history` để tránh quá tải dữ liệu MongoDB.
- [ ] **Async Task Queue:** Đưa tác vụ gửi mail SMTP scheduler và gọi AI LLM vào Celery/Redis queue.

---

## 8. Context cho agent tiếp theo

### Danh sách file cần đọc trước khi tiếp tục:
1. `backend/app/config.py`: Đọc hiểu logic Settings, validation fail-fast và CORS generator.
2. `backend/app/main.py`: Nơi khai báo FastAPI, middleware CORS, Limiter và các Exception Handlers.
3. `backend/app/models.py`: Các Pydantic schemas chứa quy tắc input validation.
4. `backend/app/auth.py`: Hàm tạo và xác thực JWT token.
5. `frontend/src/App.jsx`: Logic UI và quản lý trạng thái token/auth.
6. `backend/tests/test_security.py`: Bộ test suite hiện có của hệ thống.

### Các ràng buộc bảo mật cần giữ nguyên:
- **KHÔNG** khôi phục lại fallback hard-code cho `SECRET_KEY`.
- **KHÔNG** đưa `allow_origin_regex=r"https?://.*"` trở lại middleware CORS.
- **KHÔNG** hiển thị nút demo login nếu `VITE_DEV_DEMO_ENABLED` không phải `'true'`.
- **KHÔNG** bỏ decorator `@limiter.limit(...)` tại các endpoint auth và chat.
- **KHÔNG** dùng `str(e)` để trả về raw exception detail cho client trong exception handlers.

### Lệnh chạy môi trường chuẩn:
- **Backend:**
  ```powershell
  cd backend
  .\venv\Scripts\activate
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```
- **Frontend:**
  ```bash
  cd frontend
  npm run dev
  ```
- **Chạy Tests Backend:**
  ```powershell
  cd backend
  .\venv\Scripts\pytest -v
  ```

### Khuyến nghị thứ tự triển khai Phase 2:
1. Thiết kế cơ chế Cookie HttpOnly thay cho `localStorage`.
2. Bổ sung endpoint Refresh Token (`POST /api/auth/refresh`).
3. Cấu hình Redis backend storage cho Rate Limiter.
