# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Tiến Đạt
- **Student ID**: 2A202600595
- **Date**: 2026-06-01
- **Role**: Tool/database integration owner

> **Scope note**: Báo cáo này ghi nhận phần tôi thực hiện cho database giả lập `src/database/banggia.xlsx` và module tool kết nối vào database này.
---

## I. Technical Contribution (15 Points)

### 1. Modules Implemented

Tôi phụ trách tạo database giả lập và xây dựng module tool để ReAct Agent có thể truy vấn dữ liệu bảng giá trong file Excel `banggia.xlsx`. 

- `src/database/banggia.xlsx`: database giả lập dùng chung cho toàn bộ bài lab, chứa bảng giá sản phẩm theo category, shop, giá, discount, rating, thời gian giao hàng và mô tả.
- `src/tools/catalog_tools.py`: chứa toàn bộ logic đọc file Excel, model dữ liệu sản phẩm, search, compare, tính tổng giỏ hàng và expose tool cho agent.
- `src/tools/README.md`: tài liệu hướng dẫn cách import và gọi tool.

### 2. Database Design In `banggia.xlsx`
Tôi tạo file `src/database/banggia.xlsx` làm database giả lập cho toàn bộ bài tập. File này có 50 dòng dữ liệu, chia theo các category chính để agent có đủ case so sánh và truy vấn:

- `keyboard`
- `mouse`
- `charger`
- `headphone`
- `monitor`

Mỗi dòng trong database có các trường:

- `category`: nhóm sản phẩm.
- `product_name`: tên sản phẩm.
- `shop_name`: tên shop bán hàng.
- `price`: giá gốc.
- `discount_percent`: phần trăm giảm giá.
- `price_after_discount`: giá sau giảm, được tool dùng để so sánh và tính tổng.
- `rating`: điểm đánh giá.
- `max_delivery_days`: số ngày giao hàng tối đa.
- `description`: mô tả ngắn để hỗ trợ search theo nhu cầu người dùng.

Database này giúp nhóm có cùng một nguồn dữ liệu để test Chatbot vs ReAct Agent, đặc biệt cho các câu hỏi về giá rẻ nhất, giá cao nhất, rating tốt nhất, discount cao nhất và tính tổng giỏ hàng.

### 3. Main Components In `catalog_tools.py`
Trong `src/tools/catalog_tools.py`, tôi đã xây dựng các thành phần chính:
- `ProductOffer`: dataclass biểu diễn một dòng sản phẩm trong `banggia.xlsx`.
- `ExcelCatalogRepository`: đọc dữ liệu từ file Excel, validate cột bắt buộc, cache danh sách sản phẩm và cung cấp hàm search/find product.
- `CatalogTools`: facade để các thành viên khác gọi trực tiếp trong Python hoặc truyền vào ReAct Agent.
- `build_catalog_tools`: tạo danh sách tool dạng dictionary gồm `name`, `description`, `parameters`, `func`.
- Các helper nội bộ để đọc `.xlsx` bằng standard library, normalize text, sort kết quả, parse quantity và trả JSON.

### 4. Tool Functions Delivered
Ở phiên bản tôi triển khai ban đầu, tôi đã bàn giao các tool sau; sau đó thành viên khác mở rộng `max_results` để Observation trả về nhiều dữ liệu hơn:
- `search_products`: tìm sản phẩm theo query hoặc category.
- `get_product_price`: lấy giá chi tiết của một sản phẩm cụ thể.
- `compare_products`: so sánh danh sách sản phẩm theo các tiêu chí cơ bản tại thời điểm triển khai.
- `calculate_cart_total`: tính tổng tiền giỏ hàng dựa trên `price_after_discount`.

Kết quả trả về được thiết kế dạng dictionary khi gọi trực tiếp, và dạng JSON string khi agent gọi qua `func`, phù hợp để đưa vào `Observation` của ReAct loop.

### 5. Code Quality Highlights
- Database có schema rõ ràng, đủ các cột cần thiết cho agent truy vấn và so sánh.
- Dữ liệu giả lập có nhiều category/shop để tạo đủ tình huống test, không chỉ một case đơn lẻ.
- Không thêm dependency mới như `pandas` hoặc `openpyxl`; tool đọc `.xlsx` bằng Python standard library.
- Dùng integer VND cho các trường tiền tệ để tránh lỗi floating-point khi tính tổng.
- Có validate header của file Excel để phát hiện sớm khi database sai schema.
- Có cache dữ liệu sau lần đọc đầu tiên để giảm việc đọc lại file Excel.
- Có normalize text để hỗ trợ truy vấn không dấu và có dấu tốt hơn.
- README giải thích cách import và cách gọi tool cho các thành viên khác.
---

## II. Debugging Case Study (10 Points)
### Problem Description
Khi bắt đầu triển khai adapter đọc `banggia.xlsx`, tôi thử đọc file Excel bằng `openpyxl`, nhưng môi trường hiện tại báo lỗi:
```text
ModuleNotFoundError: No module named 'openpyxl'
```
Nếu thêm dependency mới thì các thành viên khác cũng phải cài lại môi trường, dễ gây lỗi phụ trong lab. Ngoài ra, khi test search, query như `"ban phim khong day"` có thể bị nhiễu kết quả vì các từ chung như `"khong"` và `"day"` xuất hiện trong mô tả của nhiều loại sản phẩm.

### Evidence / Test Source

Ở thời điểm debug, lỗi thiếu `openpyxl` xuất hiện trực tiếp khi chạy thử adapter đọc Excel trong môi trường local. Sau khi đổi sang reader bằng standard library, tôi dùng smoke test trực tiếp bằng Python để xác nhận tool đọc được database và trả kết quả đúng:

```python
from src.tools.catalog_tools import CatalogTools, ExcelCatalogRepository

repository = ExcelCatalogRepository()
tools = CatalogTools(repository)

offers = repository.list_offers()
assert len(offers) == 50

result = tools.search_products(query="ban phim khong day", max_results=5)
assert result["count"] > 0
```

Sau khi module tool được tích hợp vào ReAct Agent, các lỗi tool/runtime cũng có thể được theo dõi qua logging của agent như `AGENT_TOOL_CALL` và `AGENT_TOOL_ERROR` trong `src/agent/agent.py`. Với riêng lỗi thiếu `openpyxl`, bằng chứng chính là traceback local trước khi quyết định không dùng dependency này.

### Diagnosis

- Lỗi đọc Excel đến từ thiếu package ngoài môi trường, không phải do dữ liệu.
- File `.xlsx` thực chất là file ZIP chứa XML, và file `banggia.xlsx` của lab có schema đơn giản nên có thể đọc bằng standard library.
- Lỗi search nhiễu đến từ scoring ban đầu quá lỏng, chỉ cần match token rời rạc là sản phẩm không mong muốn có thể lọt vào kết quả.

### Solution

- Viết reader đọc worksheet đầu tiên bằng `zipfile` và `xml.etree.ElementTree`.
- Validate đủ các cột bắt buộc: `category`, `product_name`, `shop_name`, `price`, `discount_percent`, `price_after_discount`, `rating`, `max_delivery_days`, `description`.
- Chuẩn hóa text bằng cách lower-case, remove accent và collapse whitespace.
- Thiết kế output có cấu trúc rõ ràng để agent có thể đọc observation và tiếp tục reasoning.

Kết quả: tool load được 50 dòng dữ liệu từ `banggia.xlsx`, trả về sản phẩm/giá/rating/discount có cấu trúc và có thể tích hợp trực tiếp vào ReAct Agent.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)
### 1. Reasoning

Chatbot thông thường có thể trả lời nghe hợp lý nhưng không có khả năng kiểm chứng dữ liệu bảng giá. Với ReAct Agent, model có thể tách bài toán thành các bước: xác định cần tra dữ liệu, gọi tool, nhận observation, sau đó mới tổng hợp câu trả lời.

Điều này quan trọng với các câu hỏi cần dữ liệu thật như:

- Sản phẩm nào rẻ nhất?
- Sản phẩm nào đang giảm giá nhiều?
- Giá sau giảm của sản phẩm là bao nhiêu?
- Tổng tiền nếu mua nhiều sản phẩm là bao nhiêu?

### 2. Reliability

Agent đáng tin hơn chatbot khi câu trả lời phụ thuộc vào database. Thay vì tự đoán giá, agent gọi `CatalogTools` để lấy dữ liệu thật từ `banggia.xlsx`.

Tuy nhiên, Agent có thể tệ hơn Chatbot nếu:

- Tool description không rõ, khiến LLM chọn sai tool.
- Model tạo argument sai schema.
- Tool search trả kết quả nhiễu hoặc không đúng ý định.
- Observation quá dài làm agent khó tổng hợp câu trả lời.

### 3. Observation

Observation là điểm khác biệt lớn giữa chatbot và agent. Khi tool trả về danh sách sản phẩm, giá sau giảm, rating và shop, agent có căn cứ cụ thể để trả lời. Nếu tool trả về rỗng hoặc báo lỗi, agent cũng có tín hiệu để thử query khác hoặc nói rõ là không tìm thấy dữ liệu.

---

## IV. Future Improvements (5 Points)

- **Tool schema**: dùng Pydantic để validate input/output, giảm lỗi agent truyền sai argument.
- **Telemetry**: mở rộng log ở mức catalog tool, ví dụ `EMPTY_RESULT`, `INVALID_ARGUMENT`, `TOOL_LATENCY`, để phân tích chất lượng từng tool rõ hơn bên cạnh log agent hiện có như `AGENT_TOOL_CALL` và `AGENT_TOOL_ERROR`.
- **Data source scalability**: sau này có thể thay Excel bằng SQLite, PostgreSQL hoặc API nhưng giữ nguyên interface tool.
- **Search quality**: bổ sung synonym tiếng Việt, fuzzy matching và ranking tốt hơn.
- **Agent reliability**: thêm guardrail khi tool không có kết quả, khi product name quá mơ hồ, hoặc khi agent lặp lại cùng một action.

---

## Personal Contribution Summary

Tôi đã tạo database giả lập `src/database/banggia.xlsx` và xây dựng phần tool để Agent có thể truy vấn dữ liệu thật từ file này. Bản code cuối cùng được gom gọn trong `src/tools/catalog_tools.py`, kèm README hướng dẫn cách gọi tool. Đóng góp này giúp team có một nguồn dữ liệu chung và một lớp tool ổn định để tích hợp vào ReAct loop, evaluation và demo.
