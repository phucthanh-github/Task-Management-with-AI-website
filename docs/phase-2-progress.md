# Phase 2 Progress — Architecture & Data Integrity

## 1. Tiến độ Phase 2.1 — MongoDB Indexes & Data Integrity

### Mục tiêu đã hoàn thành
- Thiết lập cơ chế khởi tạo MongoDB indexes idempotent tự động chạy sau khi ứng dụng kết nối thành công với cơ sở dữ liệu (`connect_to_mongo()`).
- Khởi tạo 4 indexes tối ưu hiệu năng truy vấn và bảo vệ tính toàn vẹn dữ liệu:
  1. `users`: `{ email: 1 }` (unique: `True`) — Đảm bảo tính duy nhất của tài khoản email.
  2. `todos`: `{ user_id: 1, created_at: -1 }` — Tối ưu truy vấn danh sách công việc theo người dùng xếp theo thời gian tạo mới nhất.
  3. `todos`: `{ user_id: 1, status: 1, deadline: 1 }` — Tối ưu tìm kiếm/lọc công việc theo trạng thái và thời hạn deadline.
  4. `chat_messages`: `{ user_id: 1, timestamp: -1 }` — Tối ưu truy vấn lịch sử trò chuyện AI theo người dùng.
- Xử lý ném và bắt `DuplicateKeyError` tại các endpoint đăng ký tài khoản (`POST /api/auth/register` và `POST /api/auth/google-login`) để phòng chống race condition khi 2 request trùng email tới đồng thời. Endpoint trả về lỗi HTTP 400 an toàn: `"Tài khoản Gmail này đã được đăng ký trước đó."`.
- Bảo toàn dữ liệu hiện có: Nếu khởi tạo unique index thất bại do cơ sở dữ liệu cũ chứa các email bị trùng, hệ thống ghi log cảnh báo chi tiết và không tự ý sửa/xoá dữ liệu người dùng.
- Bổ sung bộ unit test tự động kiểm tra tính idempotent của index initialization và khả năng xử lý `DuplicateKeyError`.

---

## 2. Tiến độ Phase 2.2 — Tách Todo API & Củng cố Ownership Enforcement

### Mục tiêu đã hoàn thành
- Tách toàn bộ các endpoint Todo khỏi monolith `backend/app/main.py` sang router riêng tại `backend/app/routers/todos.py`.
- Tách toàn bộ logic nghiệp vụ CRUD Todo sang tầng Service riêng tại `backend/app/services/todo_service.py` (`TodoService`).
- Tích hợp router vào ứng dụng FastAPI trong `backend/app/main.py` qua `app.include_router(todos_router)`.
- Giữ nguyên tuyệt đối hợp đồng REST API cho Client & Frontend:
  - `GET /api/todos`
  - `POST /api/todos`
  - `PUT /api/todos/{todo_id}`
  - `DELETE /api/todos/{todo_id}`
- Củng cố triệt để ràng buộc quyền sở hữu (Ownership Enforcement):
  - Mọi thao tác truy vấn (Read, Write, Update, Read-after-update, Delete) đối với collection `todos` đều ép buộc chứa điều kiện `{ "_id": obj_id, "user_id": user_id }`.
  - Đảm bảo User A hoàn toàn không thể truy cập, chỉnh sửa hoặc xóa dữ liệu công việc của User B.
- Tương thích AI Agent: `backend/app/agent/tools.py` giữ nguyên tương thích, các thao tác `ActionTool` đã được đảm bảo phạm vi `user_id`.
- Viết bộ unit test tự động kiểm thử cách ly quyền sở hữu trong `backend/tests/test_todo_ownership.py`.

---

## 3. Tiến độ Phase 2.3 — Timezone Standardization & Overdue Decoupling

### Mục tiêu đã hoàn thành
- **Timezone Standardization (`backend/app/utils.py`):**
  - Xây dựng helper `utc_now()` (`datetime.now(timezone.utc)`) và `make_utc()` chuẩn hóa toàn bộ datetime nghiệp vụ mới về timezone-aware UTC objects.
  - Loại bỏ các lệnh `datetime.utcnow()` bị deprecated và loại bỏ việc xóa `tzinfo` (`tzinfo=None`).
- **GET /api/todos Strictly Read-Only:**
  - Loại bỏ hoàn toàn side-effect ghi DB (`update_one`) khỏi `get_user_todos()`. `GET /api/todos` hiện tại là endpoint thuần chỉ đọc.
- **Standalone Overdue Job (`TodoService.update_overdue_todos`):**
  - Đưa logic chuyển trạng thái overdue thành hàm service và background job riêng chạy định kỳ trong `scheduler.py`.
  - Đảm bảo chỉ chuyển trạng thái công việc `pending` hoặc `in_progress` quá hạn thành `overdue`, tuyệt đối **không thay đổi trạng thái các công việc đã `completed`**.
- **Deadline Update Semantics:**
  - Hỗ trợ gửi `deadline: null` để xóa deadline công việc và reset `reminded = False`.
  - Cập nhật deadline mới tự động chuẩn hóa về UTC và reset `reminded = False`.
  - Kiểm tra `title` khi cập nhật không được chỉ chứa khoảng trắng rỗng (HTTP 400).
- **Đồng bộ AI Agent Tools:**
  - Cập nhật `parse_deadline_str` và rule-based fallback trong `tools.py` và `graph.py` chuẩn hóa theo UTC convention.
- **Automated Unit Tests (`backend/tests/test_timezone_and_overdue.py`):**
  - Bổ sung 4 unit test bao phủ: xử lý deadline input dạng `+07:00`, xóa deadline với `null`, đảm bảo GET /api/todos read-only, và chạy job overdue độc lập.

---

## 4. Danh sách File thay đổi / Tạo mới

| File | Loại thay đổi | Mô tả |
| :--- | :--- | :--- |
| `backend/app/utils.py` | New | Cung cấp helper functions `utc_now()` và `make_utc()` chuẩn hóa datetime dạng timezone-aware UTC. |
| `backend/app/database.py` | Modify | Định nghĩa hàm `init_indexes()` tự động tạo 4 indexes MongoDB. |
| `backend/app/services/todo_service.py` | Modify | Đóng gói CRUD Todo với `user_id` + `_id`, gỡ ghi DB khỏi `get_user_todos()`, cập nhật semantics deadline và thêm `update_overdue_todos()`. |
| `backend/app/scheduler.py` | Modify | Chuyển sang `utc_now()` và đăng ký job định kỳ `update_overdue_todos_job`. |
| `backend/app/agent/tools.py` | Modify | Chuẩn hóa `parse_deadline_str` và `execute_action_tool` sử dụng `utc_now()` và `make_utc()`. |
| `backend/app/agent/graph.py` | Modify | Cập nhật fallback và prompt formatting sử dụng `utc_now()`. |
| `backend/app/models.py` & `auth.py` | Modify | Cập nhật `ChatMessageModel` và JWT expiration sử dụng `utc_now()`. |
| `backend/app/main.py` | Modify | Bắt `DuplicateKeyError`, chuyển sang `utc_now()` và đăng ký `todos_router`. |
| `backend/app/routers/todos.py` | New | Router cho các endpoints `/api/todos`. |
| `backend/tests/test_database_indexes.py` | New | Unit tests kiểm tra khởi tạo index idempotent và ném HTTP 400 khi trùng email. |
| `backend/tests/test_todo_ownership.py` | New | Unit tests chứng minh User A không thể truy cập/sửa/xoá Todo của User B. |
| `backend/tests/test_timezone_and_overdue.py` | New | Unit tests chứng minh timezone `+07:00` chuẩn hóa UTC, `deadline: null`, GET read-only và overdue job. |
| `docs/phase-2-progress.md` | Update | Cập nhật tiến độ Phase 2.1, 2.2, 2.3, file thay đổi, test results và migration notes. |

---

## 5. Migration & Compatibility Notes

> [!NOTE]
> **Legacy Naive Datetime Strategy:**
> Dữ liệu naive UTC sẵn có trong MongoDB được PyMongo tự động chuyển thành BSON Date (UTC milliseconds epoch). Các truy vấn thời gian sử dụng `make_utc()` và `utc_now()` tương thích hoàn toàn với dữ liệu cũ mà không cần chạy destructive database migration.
> 
> **Deadline Update Semantics:**
> - Trường deadline không truyền: Giữ nguyên giá trị cũ.
> - Trường deadline = `null`: Xóa deadline (`deadline = None`) và reset `reminded = False`.
> - Trường deadline = string ISO (ví dụ: `2026-08-20T20:00:00+07:00`): Tự động chuyển đổi về UTC (`2026-08-20T13:00:00+00:00`) và reset `reminded = False`.

---

## 6. Kết quả Kiểm thử (Test Results)

Lệnh kiểm thử toàn bộ backend suite:
```powershell
cd backend
.\venv\Scripts\pytest -v
```

**Kết quả:** `17 passed in 3.91s` (100% SUCCESS)
- `tests/test_database_indexes.py::test_init_indexes_creates_all_indexes_idempotently` — **PASSED**
- `tests/test_database_indexes.py::test_init_indexes_handles_duplicate_key_error_gracefully` — **PASSED**
- `tests/test_database_indexes.py::test_register_user_handles_duplicate_key_error` — **PASSED**
- `tests/test_security.py::test_production_fails_fast_on_invalid_secret_key` — **PASSED**
- `tests/test_security.py::test_jwt_ttl_from_config` — **PASSED**
- `tests/test_security.py::test_cors_origin_allowlist` — **PASSED**
- `tests/test_security.py::test_input_validation_password_length` — **PASSED**
- `tests/test_security.py::test_input_validation_title_and_message` — **PASSED**
- `tests/test_security.py::test_google_login_rejects_empty_or_invalid_token` — **PASSED**
- `tests/test_security.py::test_rate_limit_auth_endpoints` — **PASSED**
- `tests/test_timezone_and_overdue.py::test_create_todo_normalizes_plus_07_timezone_to_utc` — **PASSED**
- `tests/test_timezone_and_overdue.py::test_update_todo_deadline_null_clears_deadline_and_resets_reminded` — **PASSED**
- `tests/test_timezone_and_overdue.py::test_get_todos_is_strictly_read_only` — **PASSED**
- `tests/test_timezone_and_overdue.py::test_update_overdue_todos_job_transitions_pending_tasks_not_completed` — **PASSED**
- `tests/test_todo_ownership.py::test_user_a_cannot_update_user_b_todo` — **PASSED**
- `tests/test_todo_ownership.py::test_user_a_cannot_delete_user_b_todo` — **PASSED**
- `tests/test_todo_ownership.py::test_update_todo_service_verifies_user_id_in_read_and_update_queries` — **PASSED**

---

## 7. Context cho Agent tiếp theo

### Đã hoàn thành trong Phase 2:
1. **Phase 2.1:** MongoDB Idempotent Indexing (`users.email` unique, `todos` multi-field indexes, `chat_messages` timestamp) và xử lý race condition `DuplicateKeyError`.
2. **Phase 2.2:** Tách Todo API thành Router (`backend/app/routers/todos.py`) & Service (`backend/app/services/todo_service.py`), ép buộc ownership query bằng cả `_id` + `user_id`.
3. **Phase 2.3:** Chuẩn hóa timezone-aware UTC (`utc_now()`, `make_utc()`), `GET /api/todos` thuần chỉ đọc, tách overdue transition thành background job độc lập, và cập nhật semantics cho deadline update.

### Các việc còn lại trong các pha tiếp theo:
- [ ] **Cookie-based JWT Auth (Phase 2.4):** Chuyển JWT từ `localStorage` sang Cookie `HttpOnly; Secure; SameSite=Strict` kết hợp CSRF Protection Token.
- [ ] **Refresh Token Mechanism (Phase 2.5):** Triển khai cơ chế Refresh Token Rotation để cấp lại access token ngắn hạn mà không yêu cầu user đăng nhập lại.
- [ ] **Redis Storage cho Rate Limiter (Phase 2.6):** Chuyển `slowapi` storage từ memory sang Redis hỗ trợ ứng dụng scale multi-instance.
