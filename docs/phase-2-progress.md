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

## 5. Tiến độ Phase 2.5 — Frontend Pagination Integration cho Todo & Chat API

### Mục tiêu đã hoàn thành
- **Xử lý Response Envelope Schema `{ items, next_cursor }`:**
  - Cập nhật hàm `fetchTodos` và `fetchChatHistory` trong `frontend/src/App.jsx` để lưu trữ dữ liệu danh sách `items` và lưu `next_cursor` vào state riêng biệt (`todoNextCursor`, `chatNextCursor`).
- **Thêm nút "Tải thêm công việc" (Todo Pagination):**
  - Hiển thị nút *"Tải thêm công việc"* ở cuối danh sách công việc khi `todoNextCursor != null`.
  - Vô hiệu hoá button khi đang thực hiện request (`loadingMoreTodos` hoặc `loading`).
  - Sử dụng Set ID để lọc loại bỏ phần tử trùng lặp (**deduplication**), không tạo dư thừa công việc khi nối dữ liệu trang mới.
  - Bảo toàn danh sách công việc hiện tại nếu request lấy trang mới gặp sự cố mạng hoặc lỗi API.
- **Tự động Reset Pagination Cursor khi có thay đổi:**
  - Tự động xóa `todoNextCursor` về `null` và fetch lại trang đầu tiên (`reset = true`) khi:
    1. Người dùng bấm tạo công việc mới (`handleCreateTodo`).
    2. Chỉnh sửa chi tiết công việc (`handleUpdateTodo`) hoặc đánh dấu chuyển trạng thái (`toggleTodoStatus`).
    3. Xóa công việc (`handleDeleteTodo`).
    4. Thay đổi bộ lọc trạng thái (`filter`) hoặc chọn tiêu chí/thứ tự sắp xếp (`sortField`, `sortOrder`).
    5. Trợ lý AI thực hiện cập nhật cơ sở dữ liệu (`should_refresh === true`).
- **Kết nối Filter Status & Sort Allowlist trực tiếp với Backend:**
  - Truyền query parameter `status` (`pending`, `in_progress`, `completed`, `overdue`) trực tiếp tới API `GET /api/todos`, loại bỏ việc giả lập lọc mảng client-side không chính xác.
  - Thêm bộ chọn Sắp xếp (Sort dropdown) cho phép sắp xếp theo `created_at` (ngày tạo), `updated_at` (cập nhật) và `deadline` (hạn chót) theo thứ tự `asc`/`desc`.
- **Tải lịch sử Chat cũ hơn (Chat History Pagination):**
  - Ban đầu chỉ tải 1 trang tin nhắn mới nhất (10 tin nhắn).
  - Hiển thị nút *"📜 Tải tin nhắn cũ hơn"* phía trên cùng của giao diện chat khi `chatNextCursor != null`.
  - Khi người dùng click, request trang lịch sử cũ hơn và **prepend** vào đầu mảng `chatMessages` mà vẫn bảo đảm thứ tự hội thoại từ cũ đến mới (**old-to-new**) không bị đảo loạn hay trùng lặp.
  - Tắt hiệu ứng cuộn tự động xuống đáy khi đang tải lịch sử cũ hơn để tránh trải nghiệm giật lắc.
- **Đảm bảo Timezone Browser cho Deadline:**
  - Hàm `formatDeadline()` chuyển đổi ISO UTC string trả về từ API thành định dạng ngày giờ địa phương hiển thị đúng theo múi giờ trình duyệt người dùng qua `toLocaleString('vi-VN')`.
- **Code Quality & Build Verification:**
  - Chạy `npm run lint`: **PASSED (0 errors, 0 warnings)**.
  - Chạy `npm run build`: **PASSED (Vite build thành công trong 4.23s)**.
  - Chạy `pytest -v`: **PASSED (23/23 tests 100% SUCCESS)**.

---

## 6. Danh sách File thay đổi / Tạo mới

| File | Loại thay đổi | Mô tả |
| :--- | :--- | :--- |
| `backend/app/utils.py` | Modify | Thêm hàm helper `encode_cursor()` và `decode_cursor()` xử lý base64 URL-safe cursor. |
| `backend/app/models.py` | Modify | Định nghĩa `PaginatedTodoResponse` và `PaginatedChatHistoryResponse`. |
| `backend/app/limiter.py` | New | Cung cấp shared `Limiter` instance tránh circular imports giữa main và routers. |
| `backend/app/services/todo_service.py` | Modify | Xây dựng logic cursor pagination, status filter, sort allowlist và limit validation trong `get_user_todos()`. |
| `backend/app/routers/todos.py` | Modify | Thêm Query parameters và đổi response model `GET /api/todos` sang `PaginatedTodoResponse`. |
| `backend/app/routers/chat.py` | New | Router cho các endpoints Chat (`/api/chat/history`, `/api/chat`), tích hợp pagination old-to-new. |
| `backend/app/main.py` | Modify | Tích hợp `chat_router` và gỡ các endpoint chat dư thừa khỏi file monolith. |
| `frontend/src/App.jsx` | Modify | Tích hợp UI pagination "Tải thêm công việc", "Tải tin nhắn cũ hơn", dropdown Sắp xếp, backend status filtering, deduplication, và reset cursor. |
| `README.md` | Modify | Cập nhật tài liệu API, tham số pagination, validation error và response examples. |
| `backend/tests/test_pagination_filter_sort.py` | New | Bộ unit tests kiểm thử toàn bộ tính năng Phase 2.4/2.5. |
| `backend/tests/test_timezone_and_overdue.py` | Modify | Cập nhật assertion kiểm tra `result["items"]` phù hợp với schema paginated response mới. |
| `docs/phase-2-progress.md` | Update | Cập nhật tiến độ Phase 2.1 - 2.5, danh sách file, migration notes và test results. |

---

## 7. Migration & Compatibility Notes

> [!NOTE]
> **API Envelope Breaking Change & Frontend Integration:**
> - `GET /api/todos`: Trả về envelope object `{ "items": [...], "next_cursor": "..." }`.
> - `GET /api/chat/history`: Trả về envelope object `{ "items": [...], "next_cursor": "..." }`.
> 
> **Frontend Pagination & Infinite Scopes:**
> Phía Frontend `App.jsx` đã hoàn toàn được kết nối với backend cursor pagination. Mọi thao tác lọc status hoặc đổi tiêu chí sắp xếp đều gọi API trực tiếp với các query parameters tương ứng. Khi tải trang mới, dữ liệu cũ được bảo toàn và chống trùng lặp bằng ID set.

---

## 8. Kết quả Kiểm thử (Test Results)

Lệnh kiểm thử Frontend:
```bash
cd frontend
npm run lint
npm run build
```
**Kết quả Frontend:**
- ESLint: **0 errors, 0 warnings**
- Vite Build: **PASSED (dist bundle built in 4.23s)**

Lệnh kiểm thử Backend:
```powershell
cd backend
.\venv\Scripts\pytest -v
```
**Kết quả Backend:** `23 passed in 10.86s` (100% SUCCESS)

---

## 9. Context cho Agent tiếp theo

### Đã hoàn thành trong Phase 2:
1. **Phase 2.1:** MongoDB Idempotent Indexing và xử lý race condition `DuplicateKeyError`.
2. **Phase 2.2:** Tách Todo Router (`todos.py`) & Service (`todo_service.py`), ép buộc ownership query `_id` + `user_id`.
3. **Phase 2.3:** Chuẩn hóa timezone UTC (`utc_now()`, `make_utc()`), `GET /api/todos` read-only, tách overdue job độc lập.
4. **Phase 2.4:** Cursor Pagination, Status Filter, Sort Allowlist cho Todo & Chat API, tách Chat Router (`chat.py`), trả về schema chuẩn `{ "items": [...], "next_cursor": "..." }`.
5. **Phase 2.5:** Tích hợp Frontend Pagination cho Todo ("Tải thêm công việc"), Chat History ("Tải tin nhắn cũ hơn"), backend status filter, sort controls, deduplication, reset cursor và kiểm thử linter/build 100% thành công.

### Các việc còn lại trong các pha tiếp theo:
- [ ] **Cookie-based JWT Auth (Phase 2.6):** Chuyển JWT từ `localStorage` sang Cookie `HttpOnly; Secure; SameSite=Strict` kết hợp CSRF Protection Token.
- [ ] **Refresh Token Mechanism (Phase 2.7):** Triển khai cơ chế Refresh Token Rotation để cấp lại access token ngắn hạn mà không yêu cầu user đăng nhập lại.
- [ ] **Redis Storage cho Rate Limiter (Phase 2.8):** Chuyển `slowapi` storage từ memory sang Redis hỗ trợ ứng dụng scale multi-instance.


