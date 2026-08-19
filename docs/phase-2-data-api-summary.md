# Phase 2 Summary — Data Architecture, Data Integrity & API Contracts

## 1. Scope & Status Overview

Phase 2 focuses on hardening data architecture, database performance, timezone standards, API refactoring, cursor pagination, and frontend integration.

| Hạng mục | Trạng thái | Mô tả |
| :--- | :--- | :--- |
| **Phase 2.1 — Indexes & Data Integrity** | **HOÀN THÀNH** | Tạo 4 MongoDB indexes tự động (idempotent); xử lý race condition `DuplicateKeyError` cho email registration an toàn. |
| **Phase 2.2 — Todo Router & Ownership** | **HOÀN THÀNH** | Tách router `todos.py` & service `todo_service.py`; củng cố truy vấn ép buộc sở hữu `_id` + `user_id`. |
| **Phase 2.3 — Timezone & Overdue Job** | **HOÀN THÀNH** | Timezone-aware UTC (`utc_now()`), `GET /api/todos` strictly read-only, job overdue độc lập bảo toàn task `completed`. |
| **Phase 2.4 — Cursor Pagination API** | **HOÀN THÀNH** | Base64 cursor pagination cho Todo & Chat API; allowlist `status`, `sort`, `order`; `GET /api/chat/history` đảo old-to-new; ném HTTP 400 chuẩn. |
| **Phase 2.5 — Frontend Integration** | **HOÀN THÀNH** | Tích hợp React 19 UI pagination ("Tải thêm công việc", "Tải tin nhắn cũ hơn"), status filter, sort dropdown, deduplication, reset cursor. |
| **Phase 2.6 — Regression & Handoff** | **HOÀN THÀNH** | Audit toàn bộ codebase, loại bỏ deprecation warnings, cập nhật README & tài liệu tổng kết Phase 2. |

---

## 2. Comprehensive API Contract

### 2.1 Auth Endpoints (`backend/app/routers/auth.py`)
- `POST /api/auth/register`: Đăng ký email/password. Xử lý `DuplicateKeyError` trả về HTTP 400 `"Tài khoản Gmail này đã được đăng ký trước đó."`.
- `POST /api/auth/login`: Đăng nhập lấy Bearer Access Token.
- `POST /api/auth/google-login`: Đăng nhập OAuth Google.
- `GET /api/auth/me`: Lấy thông tin user hiện tại.
- `PUT /api/auth/hf-token`: Cập nhật Hugging Face API token.

### 2.2 Todo Endpoints (`backend/app/routers/todos.py`)
- `GET /api/todos`:
  - **Query Params**: `limit` (default: 10, range: 1-100), `cursor` (string base64), `status` (`pending`, `in_progress`, `completed`, `overdue`), `sort` (`created_at`, `updated_at`, `deadline`), `order` (`asc`, `desc`).
  - **Response Schema (`PaginatedTodoResponse`)**:
    ```json
    {
      "items": [
        {
          "id": "64a1b2c3d4e5f67890123456",
          "user_id": "507f1f77bcf86cd799439011",
          "title": "Tên công việc",
          "description": "Mô tả",
          "status": "pending",
          "deadline": "2026-08-20T13:00:00+00:00",
          "created_at": "2026-08-19T14:00:00+00:00",
          "updated_at": "2026-08-19T14:00:00+00:00",
          "reminded": false
        }
      ],
      "next_cursor": "eyJ2IjogIjIwMjYtMDgtMTlUMTQ6MDA6MDArMDA6MDAiLCAiaWQiOiAiNjRhMWIyYzNkNGU1ZjY3ODkwMTIzNDU2In0="
    }
    ```
- `POST /api/todos`: Tạo task mới (cung cấp title, description, deadline ISO string).
- `PUT /api/todos/{todo_id}`: Cập nhật task (hỗ trợ `deadline: null` để xóa hạn chót).
- `DELETE /api/todos/{todo_id}`: Xóa task theo ID (kiểm tra `_id` và `user_id`).

### 2.3 Chat Endpoints (`backend/app/routers/chat.py`)
- `GET /api/chat/history`:
  - **Query Params**: `limit` (default: 10, range: 1-100), `cursor` (string base64).
  - **Response Schema (`PaginatedChatHistoryResponse`)**: Items trả về theo thứ tự **old-to-new** trong từng trang chunk.
    ```json
    {
      "items": [
        {
          "sender": "user",
          "content": "Lời nhắn từ người dùng",
          "timestamp": "2026-08-19T14:05:00+00:00"
        },
        {
          "sender": "assistant",
          "content": "Phản hồi từ AI Assistant",
          "timestamp": "2026-08-19T14:05:02+00:00"
        }
      ],
      "next_cursor": "eyJ2IjogIjIwMjYtMDgtMTlUMTQ6MDU6MDArMDA6MDAiLCAiaWQiOiAiNjRhMmIzYzRkNWU2ZjY3ODkwMTIzNDU3In0="
    }
    ```
- `POST /api/chat`: Gửi lời nhắn hội thoại AI Agent.
- `DELETE /api/chat/history`: Xóa toàn bộ lịch sử chat của user.

---

## 3. Indexes & Migration Notes

### MongoDB Indexes (`app/database.py`)
Hệ thống khởi tạo 4 indexes tự động khi ứng dụng khởi chạy (`connect_to_mongo()`):

1. **`users`**: `{ email: 1 }` (unique: `true`)
2. **`todos`**: `{ user_id: 1, created_at: -1 }`
3. **`todos`**: `{ user_id: 1, status: 1, deadline: 1 }`
4. **`chat_messages`**: `{ user_id: 1, timestamp: -1 }`

### Migration Strategy & Safety:
- Khởi tạo index hoàn toàn **idempotent** (`create_index` tự skip nếu index đã tồn tại).
- Nếu cơ sở dữ liệu legacy chứa các email trùng lặp khiến `create_index` ném `DuplicateKeyError`, hàm ghi warning log chi tiết và bỏ qua, **tuyệt đối không tự ý xóa hoặc thay đổi dữ liệu của người dùng**.

---

## 4. Timezone Standardization

- **Backend Standard**: Mọi timestamp trong hệ thống (`created_at`, `updated_at`, `deadline`, `timestamp`) đều tạo và lưu dưới dạng UTC timezone-aware objects (`utc_now()`, `timezone.utc`).
- **Eliminated Legacy Deprecations**: Loại bỏ hoàn toàn `datetime.utcnow()` và `datetime.utcfromtimestamp()` bị ném cảnh báo deprecation trong Python 3.12+.
- **Overdue Job Processing**: `update_overdue_todos` so sánh deadline UTC với `utc_now()`. Chỉ chuyển task `pending`/`in_progress` sang `overdue`, giữ nguyên công việc `completed`.
- **Frontend Browser Display**: Frontend nhận ISO 8601 UTC string từ backend và hiển thị theo múi giờ địa phương của trình duyệt người dùng qua `toLocaleString('vi-VN')`.

---

## 5. Automated Test Results

### 5.1 Backend Pytest Suite (`cd backend; .\venv\Scripts\pytest -v`)
**Result: 23 passed in 10.52s (100% SUCCESS, 0 failures)**

1. `test_init_indexes_creates_all_indexes_idempotently` — **PASSED**
2. `test_init_indexes_handles_duplicate_key_error_gracefully` — **PASSED**
3. `test_register_user_handles_duplicate_key_error` — **PASSED**
4. `test_encode_decode_cursor_valid_and_invalid` — **PASSED**
5. `test_get_todos_invalid_query_parameters_return_400` — **PASSED**
6. `test_get_user_todos_multi_page_pagination` — **PASSED**
7. `test_get_user_todos_status_filter_and_sort_construction` — **PASSED**
8. `test_get_user_todos_always_scopes_by_authenticated_user_id` — **PASSED**
9. `test_get_chat_history_paginated_and_old_to_new_order` — **PASSED**
10. `test_production_fails_fast_on_invalid_secret_key` — **PASSED**
11. `test_jwt_ttl_from_config` — **PASSED**
12. `test_cors_origin_allowlist` — **PASSED**
13. `test_input_validation_password_length` — **PASSED**
14. `test_input_validation_title_and_message` — **PASSED**
15. `test_google_login_rejects_empty_or_invalid_token` — **PASSED**
16. `test_rate_limit_auth_endpoints` — **PASSED**
17. `test_create_todo_normalizes_plus_07_timezone_to_utc` — **PASSED**
18. `test_update_todo_deadline_null_clears_deadline_and_resets_reminded` — **PASSED**
19. `test_get_todos_is_strictly_read_only` — **PASSED**
20. `test_update_overdue_todos_job_transitions_pending_tasks_not_completed` — **PASSED**
21. `test_user_a_cannot_update_user_b_todo` — **PASSED**
22. `test_user_a_cannot_delete_user_b_todo` — **PASSED**
23. `test_update_todo_service_verifies_user_id_in_read_and_update_queries` — **PASSED**

### 5.2 Frontend Code Verification
- `cd frontend; npm run lint`: **PASSED (0 errors, 0 warnings)**
- `cd frontend; npm run build`: **PASSED (Vite client bundle compiled successfully in 4.23s)**

---

## 6. Breaking Changes & Design Decisions

1. **Envelope Response Format**:
   - `GET /api/todos`: Đổi từ top-level array `[...]` sang envelope object `{ "items": [...], "next_cursor": "..." | null }`.
   - `GET /api/chat/history`: Đổi từ `{ "messages": [...] }` sang envelope object `{ "items": [...], "next_cursor": "..." | null }`.
2. **Old-to-New Chat Chunk Ordering**:
   - Backend phân trang tin nhắn chat theo thứ tự thời gian giảm dần (để lấy chunk tin nhắn mới nhất / cũ hơn), sau đó **đảo ngược lại thành old-to-new** trước khi trả về client để UI render liền mạch.
3. **Decoupled Architecture**:
   - Toàn bộ router và service đã được phân tách mô đun: `todos.py`, `todo_service.py`, `chat.py`, `limiter.py`.

---

## 7. Known Limitations

- **Storage Rate Limiter**: Hiện tại `slowapi` đang sử dụng In-Memory Storage (`memory://`). Trong môi trường làm việc thực tế với nhiều instance backend (multi-instance/cluster), rate limit cần chuyển sang bộ nhớ tập trung Redis ở Phase 2.8.
- **JWT Storage**: JWT Access Token hiện đang lưu trữ tại Client `localStorage`. Cần chuyển sang Cookie `HttpOnly` kết hợp Refresh Token Rotation ở Phase 2.6/2.7.

---

## 8. Context Needed Before Phase 3

Nội dung cần đọc trước khi bắt đầu Phase 3:
1. `docs/phase-2-data-api-summary.md` (Tài liệu này).
2. `docs/phase-1-security-summary.md`.
3. `README.md` — Xem phần API Endpoints & Pagination Contract.
4. `backend/app/routers/todos.py` & `backend/app/routers/chat.py`.
5. `backend/app/agent/tools.py` & `backend/app/agent/graph.py` — Hiểu cách AI Agent tích hợp với Todo & Chat Service.
