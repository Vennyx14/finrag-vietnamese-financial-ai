# Kế hoạch phát triển FinRAG (từ hiện trạng đến luận văn 2027)

Lập ngày 2026-11-07. Tài liệu này chi tiết hóa Mục 5 của `AGENTS.md`. Nếu hai tài liệu khác nhau, `AGENTS.md` được ưu tiên, và agent phải báo xung đột thay vì tự chọn.

## 0. Cách đọc

### Ký hiệu

| Nhãn | Nghĩa |
|---|---|
| **[AUTO]** | Agent tự làm trọn: đọc code, viết test, code, chạy test, viết báo cáo, commit khi bạn bảo. Bạn không cần biết kế toán. |
| **[DUYỆT]** | Agent dừng lại hỏi bạn một câu có/không, kèm phương án đề xuất. Bạn chỉ cần trả lời. Đây là quyết định chính sách, không phải việc kiểm tra số liệu. |
| **[BẠN]** | Việc agent không làm thay được: tạo tài khoản, giữ bí mật, sao lưu, tìm người duyệt, viết và bảo vệ luận văn. |

Bạn đã nói không có ai duyệt nhãn số liệu. Vì vậy mọi nhãn trong kế hoạch này vẫn là **silver**, không phải gold, và mọi kết quả phải ghi rõ "chưa có người kiểm định nhãn". Bước P6.4 là cách duy nhất để có gold, và đó là tùy chọn.

### Cách giao việc

Mỗi bước có một mã (ví dụ `P2.1`). Để giao, bạn chỉ cần nhắn:

> Làm P2 theo docs/development_plan.md. Tự quyết những gì hợp lý, chỉ hỏi ở các điểm [DUYỆT].

Với mỗi bước, agent đi theo vòng của `AGENTS.md` Mục 10: hiểu → kế hoạch → viết test trước → code → chạy toàn bộ test → báo cáo (tóm tắt, file đổi, lệnh đã chạy, rủi ro, tài liệu bị cũ) → commit khi bạn đồng ý. Agent không bắt đầu giai đoạn kế tiếp khi chưa qua cổng của giai đoạn hiện tại.

### Hiện trạng (đo ngày 2026-11-07)

| Hạng mục | Trạng thái |
|---|---|
| Test | 523 passed, 0 skipped (có dữ liệu cục bộ) |
| M0 đến M3 | Xong |
| M4 lớp 1 (catalog 41 dòng) và lớp 2 (template planner) | Xong, không dùng LLM |
| M4 lớp 3 (LLM planner) | Chưa bắt đầu; `src/nlp/llm.py` còn rỗng |
| Khóa API cho LLM | Chưa có file `.env` |
| Độ phủ trên 766 câu phát triển | 111 câu được trả lời (14,5%); đây là độ phủ, không phải độ chính xác |
| Tập niêm phong | 246 câu, chưa có nhãn, chưa chạy lần nào |

655 câu phát triển còn bị từ chối. Lý do lớn nhất theo `data/manifests/question_coverage.csv`:

| Lý do từ chối | Số câu (xấp xỉ) |
|---|---:|
| Câu hỏi về nhiều công ty | 245 |
| Chỉ tiêu chưa hỗ trợ hoặc không nhận ra | 174 |
| Nhiều kỳ hoặc chuỗi thời gian | 138 |
| Mã thuộc ngân hàng, công ty tài chính (không có dữ kiện, K17) | khoảng 90 |
| Khác (không thấy số liệu, thiếu mã, mâu thuẫn số liệu) | còn lại |

Các nhóm này chồng lấn nhau, nên tổng không bằng 655.

---

## 1. Lộ trình tổng quát

| Giai đoạn | Mục tiêu | Mốc trong AGENTS.md | Phần tự động | Phần của bạn |
|---|---|---|---|---|
| **P0** | Chuẩn bị | — | Kiểm tra khóa API | Tạo khóa API, sao lưu dữ liệu |
| **P1** | Dọn nợ nhỏ | — | Toàn bộ | Duyệt giao K24 |
| **P2** | Lớp gọi LLM | M4 | Toàn bộ | — |
| **P3** | LLM planner (lớp 3) | M4 | Toàn bộ | Duyệt bật lớp 3 trên tập phát triển |
| **P4** | Mở rộng độ phủ | M4 | Toàn bộ | Duyệt từng hướng mở rộng |
| **P5** | Đóng băng và đo tập niêm phong | Cổng M4 | Gán nhãn, chấm điểm | Duyệt chính sách cổng, quyết định bật lớp |
| **P6** | Bộ đánh giá và ablation | M5 | Gần như toàn bộ | Tùy chọn: tìm người duyệt gold |
| **P7** | Thí nghiệm và phân tích lỗi | M6 | Toàn bộ | Duyệt chi phí API nếu vượt gói miễn phí |
| **P8** | Hoàn thiện sản phẩm và tái lập | — | Toàn bộ | Quyết định công khai repo |
| **P9** | Mở rộng phạm vi (tùy chọn) | Deferred | Toàn bộ | Duyệt từng hạng mục |
| **P10** | Luận văn | — | Bản nháp kỹ thuật | Viết, làm việc với giảng viên, bảo vệ |

Thứ tự đề xuất: P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P10. P9 chỉ làm khi còn thời gian và bạn đồng ý.

Nếu thiếu thời gian, điểm dừng an toàn là sau P7: hệ thống chạy được, có số đo và có phân tích lỗi đủ cho một luận văn.

---

## P0. Chuẩn bị

| Bước | Nhãn | Việc |
|---|---|---|
| P0.1 | **[BẠN]** | Tạo khóa API Groq (`https://console.groq.com/keys`, có gói Free) và dán vào dòng `GROQ_API_KEY` trong `.env`. Không gửi khóa qua chat, không commit. Ngày 2026-11-08 agent đã tạo sẵn `.env` theo `.env.example` (nhà cung cấp, địa chỉ API và model đã điền), và bạn đồng ý dùng Groq trước thay cho Cerebras: Cerebras nay đòi thêm thẻ để nhận 5 USD dùng một lần, hết hạn sau 30 ngày; OpenRouter cần nạp credit. Groq bị chặn trên một số mạng, nhưng mạng của máy bạn gọi được (kiểm tra cùng ngày). Có trả phí cho P3 hay không sẽ quyết sau khi đo lượng token thật. |
| P0.2 | **[AUTO]** | Chạy `python scripts/check_llm_key.py` để xác nhận khóa dùng được. Khóa không bao giờ được in ra. |
| P0.3 | **[BẠN]** | Sao lưu ra ổ đám mây hoặc USB: `data/processed/holdout/holdout_v1_ids.json` (mất file này là mất tập niêm phong), `data/processed/gold_drafts/`, và `data/external/`. Các thư mục này bị gitignore nên không có trên GitHub. |
| P0.4 | **[AUTO]** | Ghi mã SHA-256 của file holdout vào báo cáo để kiểm tra lại bản sao lưu về sau. |

**Xong khi:** khóa dùng được và bạn đã sao lưu.

---

## P1. Dọn nợ nhỏ

| Bước | Nhãn | Việc |
|---|---|---|
| P1.1 | **[DUYỆT]** | Giao K24 (mã viết thường như `fpt` không nhận ra) vào giai đoạn này? Đề xuất: **có**, chỉ nhận mã viết thường khi mã đó có trong danh sách 100 mã đã biết, để tránh nhận nhầm từ tiếng Việt. Bạn đã đồng ý ngày 2026-11-08. |
| P1.2 | **[AUTO]** | Sửa K24 trong `src/pipeline/query.py`, viết test trước, chạy lại báo cáo độ phủ và báo cáo các câu đổi trạng thái. Xong 2026-11-08. |
| P1.3 | **[AUTO]** | Đồng bộ tài liệu đã cũ: `AGENTS.md` Mục 2 còn ghi "không có program/DSL layer"; danh sách placeholder rỗng cần cập nhật. Kiểm tra README, PRODUCT.md, DESIGN.md theo Mục 9. Xong 2026-11-08: AGENTS.md Mục 2, PRODUCT.md (phạm vi lớp program, số dữ kiện, trạng thái mốc), README, DESIGN.md; ghi thêm K42. |
| P1.4 | **[AUTO]** | Thêm CI (GitHub Actions) chạy test trên mini fixture, để repo sạch vẫn có test chạy được thay vì bị skip (K12). CI đã có từ 2026-11-02 (`.github/workflows/ci.yml`). Kiểm tra lại 2026-11-08 trên bản clone sạch với môi trường mới: 506 test chạy, 65 skip có lý do, 0 fail. |
| P1.5 | **[AUTO]** | Sửa K26: số liệu trên mỗi cổ phiếu (EPS) bị nhân theo đơn vị của bảng, ví dụ HAG 2024 ra 997.000 đồng thay vì 997 đồng mà vẫn VERIFIED. Bạn duyệt làm trước các bước khác ngày 2026-11-08. Xong cùng ngày: test viết trước, sửa phần trích xuất, dựng lại dữ liệu, so sánh trước và sau. |
| P1.6 | **[AUTO]** | Sửa K40: ba câu giao diện nói quá mức kiểm chứng; chi tiết ở K40 trong `AGENTS.md`. Bạn duyệt ngày 2026-11-08. Xong cùng ngày. |

**Xong khi:** toàn bộ test pass, số skip được báo, tài liệu không còn mâu thuẫn với code.

---

## P2. Lớp gọi LLM (`src/nlp/llm.py`)

Mục tiêu: một lớp gọi LLM nhỏ, kiểm thử được, không có đường lui thầm lặng.

| Bước | Nhãn | Việc |
|---|---|---|
| P2.1 | **[AUTO]** | Định nghĩa giao diện `LLMProvider` (đầu vào: messages, nhiệt độ, giới hạn token; đầu ra: văn bản và metadata gồm model, số token, độ trễ). |
| P2.2 | **[AUTO]** | `OpenAICompatibleProvider` dùng chung cho Cerebras, OpenRouter, Groq (cùng chuẩn API). Dùng thư viện chuẩn `urllib` như `scripts/check_llm_key.py`, nên không thêm phụ thuộc. Model và base URL đọc từ `.env`. Tên biến đặt ngày 2026-11-08 trong `.env.example`: `FINRAG_LLM_PROVIDER` chọn nhà cung cấp; mỗi nhà cung cấp có `<TÊN>_API_KEY`, `<TÊN>_BASE_URL`, `<TÊN>_MODEL`. Model mặc định là `gpt-oss-120b` ở cả ba nhà cung cấp, khác họ với model Claude đã điền nhãn silver. |
| P2.3 | **[AUTO]** | `MockProvider` chỉ dùng trong test. Ứng dụng từ chối khởi động với mock ngoài test (nguyên tắc 18). |
| P2.4 | **[AUTO]** | Bộ đệm đĩa theo hash (model, prompt, tham số) trong `data/processed/llm_cache/` để chạy lại cho kết quả giống hệt và tiết kiệm lượt gọi miễn phí. |
| P2.5 | **[AUTO]** | Lỗi có kiểu: hết hạn mức, mất mạng, phản hồi sai định dạng. Thử lại có giới hạn. Khi LLM lỗi, câu trả lời nói rõ "LLM không khả dụng", không âm thầm quay về câu trả lời khác. |
| P2.6 | **[AUTO]** | Test: không gọi mạng trong test (nguyên tắc 6 của Mục 10); một test kiểm tra rằng khóa không xuất hiện trong log hay thông báo lỗi. |

**Xong khi:** test pass, một lệnh smoke thật (`python scripts/check_llm_key.py` hoặc tương đương) trả lời được, không thêm phụ thuộc mới.

---

## P3. LLM planner (M4 lớp 3)

Mục tiêu: LLM chỉ chọn **chương trình và ràng buộc** (dòng nào, công ty nào, kỳ nào, phép toán nào), không bao giờ tạo ra con số. Phép tính vẫn do executor đã có test thực hiện.

Thứ tự chạy giữ nguyên: `resolve_query` → template planner (lớp 2) → LLM planner (lớp 3, chỉ khi hai lớp trước từ chối).

| Bước | Nhãn | Việc |
|---|---|---|
| P3.1 | **[AUTO]** | Prompt gồm: câu hỏi (đặt trong JSON như dữ liệu, không phải lệnh), danh sách dòng catalog, danh sách phép toán cho phép, công ty và kỳ đã trích bởi parser chuẩn. Đầu ra là JSON có cấu trúc: `program` hoặc `refuse` kèm lý do. |
| P3.2 | **[AUTO]** | Kiểm tra đầu ra bằng model chương trình hiện có trong `src/financial/program/models.py`: phép toán ngoài danh sách, dòng không có trong catalog, hằng số tự đặt ra, hoặc JSON hỏng đều bị từ chối. Không `eval`, không `exec`. |
| P3.3 | **[AUTO]** | Kiểm tra độc lập: mỗi dòng catalog được dùng phải có căn cứ từ ngữ trong câu hỏi; công ty và kỳ trong chương trình phải khớp với lần parse độc lập (nguyên tắc 23). Không khớp thì `REJECTED` hoặc `WARNING`. |
| P3.4 | **[AUTO]** | Ghi vết đầy đủ: prompt, phản hồi thô, model, chương trình, ràng buộc, kết quả kiểm tra. Trên UI, câu trả lời từ lớp 3 có nhãn riêng để người dùng biết nó đến từ LLM planner. |
| P3.5 | **[AUTO]** | Test bằng mock: chương trình đúng, chương trình có phép toán lạ, chương trình chứa số, câu hỏi chứa lệnh chèn (prompt injection), LLM lỗi. |
| P3.6 | **[AUTO]** | Chạy trên 766 câu phát triển (không chạm 246 câu niêm phong). Báo cáo: độ phủ mới theo lớp, câu đổi trạng thái, điểm trên silver v2 và 42 nhãn đóng băng trước M4. Agent đọc lại mọi câu trả lời mới để tìm lỗi, và ghi rõ việc đọc này không độc lập. |
| P3.7 | **[DUYỆT]** | Bật lớp 3 trên tập phát triển? Agent trình bày: độ phủ tăng bao nhiêu, có câu nào trước đúng nay sai không, chi phí và độ trễ. Đề xuất mặc định: bật nếu không có câu nào trước đúng nay sai. |

**Xong khi:** các test trên pass, báo cáo `docs/m4_layer_3_report.md` có số đo, và bạn đã trả lời P3.7.

---

## P4. Mở rộng độ phủ (vẫn trong M4)

Mỗi hướng là một thay đổi riêng, có báo cáo đổi trạng thái riêng. Agent làm theo thứ tự lợi ích lớn trước, và hỏi trước khi bắt đầu mỗi hướng.

| Bước | Nhãn | Hướng | Lý do |
|---|---|---|---|
| P4.1 | **[DUYỆT]** + **[AUTO]** | Câu hỏi nhiều công ty (so sánh, xếp hạng) qua program layer | Nhóm bị từ chối lớn nhất (khoảng 245 câu) |
| P4.2 | **[DUYỆT]** + **[AUTO]** | Chuỗi nhiều kỳ (ví dụ 3 năm liên tiếp, CAGR nếu bạn duyệt thêm phép toán) | Khoảng 138 câu |
| P4.3 | **[DUYỆT]** + **[AUTO]** | Thêm dòng vào catalog cho các chỉ tiêu thường gặp chưa hỗ trợ | Phần lớn trong 174 câu "chưa hỗ trợ"; mỗi dòng mới cần bạn đồng ý về tên gọi, theo cách đã làm với dòng 50 |
| P4.4 | **[DUYỆT]** + **[AUTO]** | Lớp 4: bảng thuyết minh (note tables) | 5 nhãn đóng băng bị từ chối vì số nằm trong thuyết minh. Cần sửa phần ingestion nên lớn hơn các hướng khác |

Câu hỏi cho bạn ở mỗi hướng có dạng: "Thêm phép toán X / dòng Y, có không?" kèm đề xuất. Bạn không cần đọc báo cáo tài chính để trả lời.

**Xong khi:** mỗi hướng được duyệt có test, có báo cáo đổi trạng thái, không có câu nào trước đúng nay sai trên silver.

---

## P5. Đóng băng code và đo tập niêm phong (cổng M4)

Đây là lần đo duy nhất trên tập niêm phong. Sau khi xem kết quả từng câu và sửa code, tập này trở thành dữ liệu phát triển (quy tắc 4 trong `docs/holdout_v1_seal.md`).

### Vấn đề cỡ mẫu cần biết trước

Cổng yêu cầu cận trên Wilson 95% của tỷ lệ sai-mà-vẫn-được-xác-minh không vượt 5%. Cận này phụ thuộc số câu được trả lời:

| Số câu sai | Cần ít nhất bao nhiêu câu được trả lời |
|---:|---:|
| 0 | 73 |
| 1 | 110 |
| 2 | 142 |

Với độ phủ hiện tại (14,5%), tập niêm phong chỉ cho khoảng 36 câu được trả lời. Dù không sai câu nào, cận trên vẫn khoảng 9,6%, tức là trượt cổng chỉ vì mẫu nhỏ. Vì vậy cổng chỉ có khả năng đạt khi P3 và P4 nâng độ phủ lên khoảng 30% trở lên.

| Bước | Nhãn | Việc |
|---|---|---|
| P5.1 | **[DUYỆT]** | Chính sách cổng khi mẫu quá nhỏ. Đề xuất: (a) đo gộp mọi câu được trả lời, không tách theo lớp; (b) nếu trượt chỉ vì cỡ mẫu và không có câu sai, lớp vẫn được bật nhưng gắn nhãn "thử nghiệm" trên UI, và luận văn ghi rõ cổng chưa được chứng minh. |
| P5.2 | **[DUYỆT]** | Có chia tập niêm phong theo công ty thành hai nửa không: nửa A cho cổng M4, nửa B giữ cho số liệu cuối cùng của luận văn ở P7? Đề xuất: **không chia**, vì mỗi nửa quá nhỏ để có cận tin cậy; thay vào đó dùng P6.5 cho số liệu cuối. |
| P5.3 | **[AUTO]** | Đóng băng code: tạo git tag, ghi commit vào `docs/holdout_v1_seal.md`. |
| P5.4 | **[AUTO]** | Gán nhãn 246 câu niêm phong **trước khi** chạy hệ thống: agent đọc trang OCR gốc, ghi toán hạng kèm vị trí trang/bảng/dòng, và một script độc lập (không import code suy luận của FinRAG) tính đáp án. Agent là một họ model khác với LLM planner, đúng quy tắc ở Mục 7. Nhãn lưu trong `data/processed/holdout/` và ghi hash. |
| P5.5 | **[AUTO]** | Chạy hệ thống một lần, chỉ in điểm tổng hợp: độ phủ, tỷ lệ sai-mà-vẫn-được-xác-minh với khoảng Wilson, từ chối thừa, theo từng loại câu hỏi. Ghi vào nhật ký đánh giá. |
| P5.6 | **[DUYỆT]** | Quyết định bật từng lớp theo P5.1. |

**Xong khi:** nhật ký đánh giá có một dòng kết quả, bạn đã quyết định bật lớp, `AGENTS.md` Mục 2 và 5 được cập nhật. M4 đóng.

---

## P6. Bộ đánh giá và ablation (M5)

| Bước | Nhãn | Việc |
|---|---|---|
| P6.1 | **[AUTO]** | Viết `src/evaluation/evaluator.py`: EA, PA, độ đúng phân giải khái niệm, độ đúng chọn fact, độ chính xác và độ phủ của từ chối, tỷ lệ từ chối thừa, tỷ lệ sai-mà-vẫn-được-xác-minh, độ đúng trích dẫn, khoảng Wilson, báo cáo theo loại câu hỏi (Mục 7). Có test riêng. |
| P6.2 | **[AUTO]** | Ba cấu hình: oracle-bindings (cho sẵn chương trình đúng), oracle-facts (cho sẵn fact đúng), full pipeline. Để tách lỗi do hiểu câu hỏi, do chọn số liệu, hay do tính toán. |
| P6.3 | **[AUTO]** | Mở rộng tập silver lên 150 đến 200 câu có đáp án số, chia theo công ty, nhãn đóng băng trước khi chạy hệ thống. Vẫn là silver. |
| P6.4 | **[BẠN]**, tùy chọn | Tìm một người có nền tảng kế toán (ví dụ sinh viên kế toán, kiểm toán) duyệt khoảng 50 đến 100 câu. Agent chuẩn bị gói duyệt (`data/benchmark/review_packets/`) và một trang duyệt đơn giản: người duyệt chỉ xem câu hỏi, ảnh/văn bản trang gốc, số đề xuất, và bấm đúng/sai. Đây là cách duy nhất để có nhãn **gold**, và làm luận văn mạnh hơn rõ rệt. |
| P6.5 | **[AUTO]** | Nếu bạn đồng ý (ADR-0001 cho phép dùng làm đánh giá), thêm một bộ dữ liệu ngoài như ViNumQA chỉ để đánh giá phần lập chương trình, tách hẳn khỏi corpus chính. Agent kiểm tra giấy phép trước khi tải. |

**Xong khi:** một lệnh chạy ra toàn bộ bảng số liệu M5, có cỡ mẫu và khoảng tin cậy.

---

## P7. Thí nghiệm và phân tích lỗi (M6)

| Bước | Nhãn | Việc |
|---|---|---|
| P7.1 | **[AUTO]** | So sánh: chỉ đường xác định (lớp 0 đến 2), chỉ program (lớp 3), kết hợp. |
| P7.2 | **[AUTO]** | Thang baseline ở Mục 7: parser regex → LLM zero-shot → few-shot → tự đánh giá → nhiều đường (multi-path, bỏ phiếu) → thêm bộ xác minh. Baseline "LLM tự tính đáp án" chỉ tồn tại trong thí nghiệm để so sánh, không bao giờ vào sản phẩm (nguyên tắc 16). |
| P7.3 | **[AUTO]** | Phân tích lỗi: phân loại mọi câu sai và câu từ chối thừa theo nguyên nhân (hiểu câu hỏi, chọn số liệu, đơn vị, OCR, xác minh bỏ sót). |
| P7.4 | **[AUTO]** | Báo cáo độ trễ, tỷ lệ lỗi, số lượt gọi và chi phí API riêng cho từng cấu hình. |
| P7.5 | **[DUYỆT]** | Nếu gói miễn phí không đủ cho mọi cấu hình: trả phí (agent ước tính trước), hoặc chạy trên một mẫu nhỏ hơn và ghi rõ. Đề xuất: chạy mẫu nhỏ hơn trước. |
| P7.6 | **[DUYỆT]** | Kết luận: LLM planner có đáng với độ phức tạp của nó không (giữ, giữ ở chế độ thử nghiệm, hay bỏ). Agent đưa đề xuất dựa trên số đo. |

**Xong khi:** `docs/m6_experiments.md` có bảng so sánh, phân tích lỗi và kết luận.

---

## P8. Hoàn thiện sản phẩm và tái lập

| Bước | Nhãn | Việc |
|---|---|---|
| P8.1 | **[AUTO]** | UI: hiển thị vết chương trình cho câu trả lời từ lớp 2 và 3, nhãn "thử nghiệm" theo P5.1, thông báo từ chối rõ ràng hơn. |
| P8.2 | **[AUTO]** | `scripts/reproduce_all.py`: một lệnh chạy từ dữ liệu thô ra mọi bảng số liệu trong luận văn, kèm phiên bản dữ liệu và commit. |
| P8.3 | **[AUTO]** | Viết `scripts/run_demo.py` (đang rỗng) với vài câu hỏi minh họa, gồm cả câu bị từ chối. |
| P8.4 | **[AUTO]** | Đồng bộ README, PRODUCT.md, DESIGN.md, `docs/CV_PROJECT.md` với số đo cuối, không dùng các cụm từ bị cấm ở Mục 9. |
| P8.5 | **[DUYỆT]** | Thư mục `api/` (REST API) có cần không? Đề xuất: **không**, vì Streamlit đủ cho demo và luận văn; nếu cần thì thêm FastAPI kèm lý do phụ thuộc. |
| P8.6 | **[BẠN]** | Quyết định công khai repo GitHub hay không. Agent kiểm tra trước rằng không có khóa, dữ liệu thô hay văn bản câu hỏi ViFinQA trong lịch sử git. |

---

## P9. Mở rộng phạm vi (tùy chọn, mỗi mục cần duyệt riêng)

Các mục này đang bị hoãn trong `AGENTS.md`. Agent chỉ bắt đầu khi bạn nói rõ.

| Mục | Lợi ích | Chi phí |
|---|---|---|
| Biểu mẫu ngân hàng (K17) | Khoảng 90 câu phát triển và 22 mã | Lớn: biểu mẫu báo cáo khác hẳn, cần catalog riêng |
| Adapter cho repo OCR | Thêm báo cáo mới, tạo được tập kiểm tra mới thật sự sạch | Trung bình; cần rà tương thích trước |
| Truy hồi dense hoặc hybrid | Có thể giúp câu hỏi diễn đạt lạ | Trung bình; phải chứng minh hơn BM25 bằng thí nghiệm |

---

## P10. Luận văn

| Bước | Nhãn | Việc |
|---|---|---|
| P10.1 | **[BẠN]** | Chốt đề tài, giảng viên hướng dẫn, mẫu trình bày của trường, hạn nộp. |
| P10.2 | **[AUTO]** | Soạn bản nháp kỹ thuật từ repo: kiến trúc, hợp đồng dữ liệu, phương pháp đánh giá, bảng số liệu, phân tích lỗi, hạn chế. Mọi con số dẫn về lệnh đã chạy. |
| P10.3 | **[BẠN]** | Viết lại theo giọng của bạn, phần tổng quan tài liệu, làm việc với giảng viên. Agent hỗ trợ sửa và kiểm tra số liệu khớp với repo. |
| P10.4 | **[AUTO]** | Hình và bảng cho luận văn, slide bảo vệ dựa trên số đo thật. |
| P10.5 | **[BẠN]** | Bảo vệ. Agent có thể soạn danh sách câu hỏi hội đồng hay hỏi và câu trả lời dựa trên số liệu. |

---

## Tổng hợp việc bạn phải làm thủ công

| Khi nào | Việc | Thời gian ước tính |
|---|---|---|
| P0 | Tạo khóa API, tạo `.env` | 10 phút |
| P0 | Sao lưu `data/processed/holdout/`, `gold_drafts/`, `data/external/` | 10 phút, nhắc lại sau mỗi giai đoạn |
| Mỗi điểm [DUYỆT] | Trả lời có/không | Vài phút mỗi lần |
| P6.4 (tùy chọn) | Tìm người có nền tảng kế toán duyệt 50 đến 100 câu | Phụ thuộc người duyệt |
| P7.5 | Quyết định chi phí API nếu cần | Vài phút |
| P8.6 | Quyết định công khai repo | Vài phút |
| P10 | Viết, làm việc với giảng viên, bảo vệ luận văn | Phần lớn công sức của bạn |

Mọi việc còn lại, gồm code, test, đo đạc, gán nhãn silver, báo cáo và tài liệu, là **[AUTO]**.

## Rủi ro chính

| Rủi ro | Hệ quả | Cách xử lý |
|---|---|---|
| Không có người duyệt nhãn | Không có số liệu gold; hội đồng có thể hỏi về độ tin cậy của nhãn | P6.4; nếu không được thì ghi rõ giới hạn và nhấn mạnh kiểm tra trích dẫn trên trang gốc |
| Độ phủ thấp làm cổng 5% không chứng minh được | Lớp mới không được bật chính thức | P3 và P4 trước P5; chính sách P5.1 |
| Gói API miễn phí bị giới hạn hoặc đổi điều khoản | Thí nghiệm P7 chậm hoặc không chạy lại được | Bộ đệm đĩa ở P2.4; hỗ trợ nhiều nhà cung cấp |
| Mất file holdout hoặc dữ liệu cục bộ | Mất tập niêm phong, không tái lập được | P0.3 |
| Tập niêm phong dùng một lần | Sau P5 không còn tập kiểm tra sạch trên corpus này | P5.2, P6.5, hoặc adapter OCR ở P9 để có báo cáo mới |
