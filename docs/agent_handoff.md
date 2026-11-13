# Bàn giao giữa Claude Code và Antigravity

> Scope: this guide applies to explicit Claude Code/Antigravity handoffs. Codex uses its separate [Codex guide](../.codex/README.md) and `finrag-codex-*` skills. The GPT routing in that integration does not change Antigravity's configured model or this handoff procedure.

Lập ngày 2026-11-09. Tài liệu này dành cho bạn (người giao việc và gộp kết quả). Quy tắc cho agent vẫn nằm ở `AGENTS.md`; tài liệu này không thay thế nó. Cách dùng agent con của Claude Code nằm ở `docs/agent_view_guide.md`.

Ý chính: Claude Code làm việc cần suy luận và có rủi ro về số liệu. Antigravity làm việc lặp lại, phạm vi rõ, kiểm tra được bằng test. Hai bên trao đổi qua **file task** trong git, không qua hội thoại.

## 1. Việc nào đi đâu

### Giao cho Antigravity (tốn token nhưng ít cần phán đoán)

Thay cho `finrag-worker` (Sonnet) ở các việc dưới đây:

| Việc | Điều kiện |
|---|---|
| Đồng bộ tài liệu (README, PRODUCT, DESIGN, `docs/`) sau một thay đổi đã xong | Claude hoặc bạn đã nêu rõ điều gì đổi; không viết thêm số liệu hay tuyên bố mới (AGENTS.md Mục 9) |
| Sửa chữ trên giao diện (chuỗi tiếng Việt, nhãn, thông báo) | Không động vào logic tính toán; có test `tests/test_ui_render.py` đi kèm |
| Thêm test theo mẫu có sẵn (cùng cấu trúc, đổi dữ liệu) | Mẫu được chỉ rõ trong file task; không sửa giá trị kỳ vọng cũ |
| Chạy test đầy đủ và các benchmark, tóm tắt pass/fail/skip | Chạy trong nhánh riêng (xem Mục 4) |
| Báo cáo chuyển trạng thái độ phủ trước và sau | Chỉ tổng hợp số từ script, không diễn giải thêm |
| Đổi tên, chuyển chỗ, sửa lỗi chính tả, định dạng code | Không đổi hành vi |
| Cập nhật danh sách trong `AGENTS.md` Mục 13 khi test đã chứng minh một lỗi đã sửa | Chỉ khi file task ghi rõ bằng chứng |
| Tìm kiếm, liệt kê nơi một hàm hoặc chuỗi được dùng | Chỉ đọc, báo lại danh sách |

### Giữ cho Claude Code

| Việc | Lý do |
|---|---|
| Sửa `src/financial/`, `src/ingestion/`, `src/retrieval/`, xác minh, đơn vị, số học | Sai ở đây tạo ra câu trả lời sai mà vẫn được VERIFIED |
| Chẩn đoán vì sao một câu trả lời sai hoặc bị từ chối | Cần lần theo nhiều lớp |
| Thêm dòng catalog, metric, phép toán DSL | Ảnh hưởng độ phủ và độ đúng |
| Lớp LLM, planner, chống chèn lệnh (M4 lớp 3, P2, P3) | Quy tắc 16 đến 18 của AGENTS.md |
| Gán nhãn, tập niêm phong, đo độ chính xác, cổng M4 | Quy tắc đánh giá ở AGENTS.md Mục 7 |
| Review diff do Antigravity tạo ra, nếu nó chạm tới logic | Hai mắt tốt hơn một (nguyên tắc 23) |
| Lập kế hoạch và viết file task | Cần hiểu cả hệ thống |

### Cách chọn nhanh

1. Việc có thể làm sai số liệu tài chính, đơn vị hoặc độ tin cậy của kết quả? → Claude Code.
2. Việc có phạm vi rõ, tiêu chí hoàn thành rõ, kiểm tra được bằng lệnh? → Antigravity.
3. Không chắc? → Claude Code lập file task trước. Nếu lập xong thấy mọi bước đều cơ học thì giao cho Antigravity.

## 2. Quy trình bàn giao

```text
Claude Code                         Antigravity                      Bạn
-----------                         -----------                      ---
1. Viết docs/tasks/<id>.md
   (mục tiêu, phạm vi, lệnh kiểm tra)
                                    2. Tạo nhánh, đọc file task,
                                       làm đúng phạm vi
                                    3. Chạy lệnh kiểm tra, ghi kết quả
                                       vào mục "Báo cáo" của file task,
                                       commit trên nhánh của mình
4. Review diff (bắt buộc nếu
   chạm src/ hoặc test)
                                                                     5. Trả lời "đồng ý"
6. Gộp vào main, chạy test lại
```

Quy tắc:
- Mỗi file task có **một chủ**: đang giao cho agent nào thì chỉ agent đó sửa phần "Báo cáo".
- Mỗi agent làm trên **nhánh riêng** (`antigravity/<id>` hoặc `claude/<id>`). Không bao giờ làm trực tiếp trên `main`.
- Không giao hai agent cùng một file trong cùng lúc.
- Antigravity **không push, không mở pull request, không gộp**. Bạn hoặc phiên điều phối Claude làm việc đó sau khi bạn đồng ý.
- Nếu Antigravity gặp điều file task không nói tới, nó **dừng và ghi vào mục "Vấn đề"**, không tự đoán (AGENTS.md Mục 10, quy tắc 8).

## 3. Luật Antigravity phải tuân thủ

Claude Code bị chặn cứng bởi `.claude/settings.json` (push, đọc `.env`, sửa benchmark). **Luật chặn này không áp dụng cho Antigravity**, vì vậy nó tự chịu các quy tắc sau; hãy dán hoặc trỏ tới phần này trong lời giao việc:

1. Đọc `AGENTS.md` trước khi làm. Khi tài liệu mâu thuẫn, báo lại, không tự chọn.
2. **Không sửa** `data/benchmark/**`, các file gold, hoặc giá trị kỳ vọng trong test để cho test qua.
3. **Không đọc hoặc in nội dung** `.env`. Không commit khóa API.
4. **Không `git push`**, không đổi lịch sử, không gộp vào `main`.
5. Không làm yếu một lớp bảo vệ: không nới dung sai, không xóa kiểm tra, không `skip` test.
6. Không gọi mạng hoặc LLM trong test.
7. Các script benchmark và độ phủ **ghi đè file trong `data/manifests/`**. Chỉ chạy chúng trong nhánh riêng, không chạy ở thư mục chính của bạn.
8. Chuỗi hiển thị cho người dùng viết bằng tiếng Việt; code, chú thích, tài liệu viết bằng tiếng Anh.
9. Tuân thủ toàn bộ các giới hạn về cách diễn đạt và tuyên bố trong AGENTS.md Mục 9; mục đó là nguồn quy tắc chính thức. Số liệu đo phải kèm tên benchmark, cỡ mẫu và ghi chú nó do dự án tự viết.
10. Kết thúc bằng báo cáo theo mẫu ở Mục 5, nêu cả những gì **chưa làm**.

Cần kiểm tra thêm: Antigravity đọc file quy tắc nào khi khởi động. Tài liệu này không xác nhận điều đó. Nếu nó không tự đọc `AGENTS.md`, hãy ghi dòng "Đọc AGENTS.md và docs/agent_handoff.md Mục 3" ngay trong lời giao việc.

## 4. Tránh xung đột và ghi đè

- Tạo nhánh trước khi sửa: `git switch -c antigravity/<id>`.
- Nếu hai agent chạy cùng lúc, mỗi agent dùng một thư mục làm việc riêng: `git worktree add ../finrag-<id> -b antigravity/<id>`. Dữ liệu bị gitignore (`data/processed/`, `data/benchmark/`) là bản sao, nên cần chép sang hoặc dựng lại, và phải ghi điều đó trong báo cáo.
- Trước khi gộp, kiểm tra `git status` trên `main` sạch và nhánh của agent chỉ chứa các file nằm trong phạm vi của file task: `git diff --stat main...<nhánh>`.

## 5. Mẫu file task

Lưu ở `docs/tasks/<id>.md`, trong đó `<id>` ngắn và duy nhất (ví dụ `2026-11-09-k29-formula-order`). Sao chép khối dưới đây.

````markdown
# Task <id>: <tên ngắn>

- Giao cho: Antigravity | Claude Code
- Nhánh: antigravity/<id>
- Người lập: <Claude Code | bạn>, ngày <YYYY-MM-DD>
- Cột mốc / mục kế hoạch: <ví dụ M4, P1.3, K29>

## Mục tiêu
Một đến hai câu. Kết quả cuối cùng nhìn thấy được là gì?

## Bối cảnh
Vì sao làm. Trỏ tới mục AGENTS.md, issue K-số, hoặc file docs liên quan. Không dán nội dung dài.

## Phạm vi
Được sửa (liệt kê chính xác):
- `đường/dẫn/file1.py`
- `tests/test_xxx.py`

Không được sửa (ngoài các luật chung ở docs/agent_handoff.md Mục 3):
- ...

## Các bước
1. Viết test thất bại trước: `tests/...`. Chạy và ghi lại thông báo lỗi.
2. Sửa tối thiểu để test qua.
3. Chạy lệnh kiểm tra ở dưới.
4. Cập nhật tài liệu bị ảnh hưởng: <liệt kê file>, hoặc ghi "không có".

## Lệnh kiểm tra
```bash
python -m pytest -rs
# thêm nếu cần:
# python scripts/evaluate_reasoning.py
```

## Tiêu chí hoàn thành
- [ ] Test mới thất bại trước thay đổi và qua sau thay đổi
- [ ] Toàn bộ test qua; số skip được giải thích
- [ ] Không file nào ngoài phạm vi bị sửa (`git diff --stat`)
- [ ] Không giá trị kỳ vọng, benchmark hay gold bị sửa
- [ ] <tiêu chí riêng của việc này>

## Điều kiện dừng
Dừng và ghi vào "Vấn đề" thay vì tiếp tục, nếu:
- cần sửa file ngoài phạm vi,
- test hiện có thất bại vì lý do không liên quan,
- yêu cầu mâu thuẫn với AGENTS.md,
- không chắc một số liệu hoặc đơn vị đúng hay sai.

---

## Báo cáo (agent điền khi xong)

### Tóm tắt
Đã đổi gì và vì sao.

### File đã sửa
- ...

### Lệnh đã chạy và kết quả
| Lệnh | Kết quả |
|---|---|
| `python -m pytest -rs` | <số passed / failed / skipped> |

### Rủi ro và việc chưa làm
- ...

### Tài liệu có thể đã lỗi thời
- ...

### Vấn đề
Điều agent đã dừng lại vì nó, hoặc "không có".
````

## 6. Ví dụ giao việc ngắn

Lời nhắn bạn đưa cho Antigravity:

```text
Đọc AGENTS.md và docs/agent_handoff.md (Mục 3 là luật bạn phải theo).
Làm docs/tasks/2026-11-09-sync-docs.md trên nhánh antigravity/2026-11-09-sync-docs.
Điền mục "Báo cáo" khi xong và commit trên nhánh đó. Không push.
```

## 7. Hạn chế đã biết

- Antigravity không bị chặn cứng như Claude Code. An toàn dựa vào luật ở Mục 3 và vào việc bạn (hoặc Claude) xem diff trước khi gộp.
- Tài liệu này mô tả quy trình đề xuất, chưa được chạy thử với Antigravity. Sau lần giao việc đầu tiên, hãy sửa lại những chỗ không khớp với cách nó thực sự hoạt động.
- Chưa có số liệu tiết kiệm token. Đừng coi bảng ở Mục 1 là đã đo; nó chỉ là cách phân loại theo rủi ro.
