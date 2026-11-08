# Statement layout (Circular 200 forms B01-DN, B02-DN, B03-DN)

Use this to locate lines and to cross-check. It describes the common Circular 200 layout used by most non-financial companies in the corpus. It does **not** hold for Circular 133 (small enterprises), banks (their own forms), securities companies (Circular 334, codes such as 001–009 off-balance and a 500 section), or insurers. Line codes can differ by year and by company; the page in front of you wins. FinRAG's catalog (`src/financial/program/catalog.py`) covers 41 of these lines plus the eight base metrics.

## Balance sheet (Bảng cân đối kế toán)

| Code | Line | Notes |
|---|---|---|
| 100 | A. Tài sản ngắn hạn | = 110 + 120 + 130 + 140 + 150 |
| 110 | I. Tiền và các khoản tương đương tiền | 111 Tiền, 112 Các khoản tương đương tiền |
| 120 | II. Đầu tư tài chính ngắn hạn | 121, 122 (provision, negative), 123 |
| 130 | III. Các khoản phải thu ngắn hạn | 131 phải thu khách hàng, 132 trả trước cho người bán, 136 phải thu khác, 137 dự phòng (negative) |
| 140 | IV. Hàng tồn kho | 141 Hàng tồn kho, 149 dự phòng (negative) |
| 150 | V. Tài sản ngắn hạn khác | 151, 152 VAT khấu trừ, 153, 155 |
| 200 | B. Tài sản dài hạn | = 210 + 220 + 230 + 240 + 250 + 260 |
| 220 | II. Tài sản cố định | 221 hữu hình (222 nguyên giá, 223 hao mòn), 224 thuê tài chính, 227 vô hình |
| 230 / 240 / 250 / 260 | BĐS đầu tư / TS dở dang dài hạn / đầu tư tài chính dài hạn / TS dài hạn khác | 269 lợi thế thương mại (consolidated) |
| **270** | **TỔNG CỘNG TÀI SẢN** | = 100 + 200 |
| 300 | C. Nợ phải trả | = 310 + 330 |
| 310 | I. Nợ ngắn hạn | 311 phải trả người bán, 312 người mua trả trước, 318 DT chưa thực hiện NH, 320 vay và nợ thuê TC NH |
| 330 | II. Nợ dài hạn | 336 DT chưa thực hiện DH, 338 vay và nợ thuê TC DH, 341 thuế TN hoãn lại phải trả |
| 400 | D. Vốn chủ sở hữu | = 410 + 430 |
| 410 | I. Vốn chủ sở hữu | 411 vốn góp, 412 thặng dư, 415 cổ phiếu quỹ (negative), 421 LNST chưa phân phối, 429 lợi ích cổ đông không kiểm soát |
| 430 | II. Nguồn kinh phí và quỹ khác | |
| **440** | **TỔNG CỘNG NGUỒN VỐN** | = 300 + 400, and equals 270 |

Identities the verifier uses: 270 = 300 + 400 (minority interest outside 400 handled since K20), 270 = 100 + 200.

## Income statement (Báo cáo kết quả hoạt động kinh doanh)

| Code | Line | Identity |
|---|---|---|
| 01 | Doanh thu bán hàng và cung cấp dịch vụ | |
| 02 | Các khoản giảm trừ doanh thu | |
| **10** | **Doanh thu thuần** | = 01 − 02 |
| 11 | Giá vốn hàng bán | |
| 20 | Lợi nhuận gộp | = 10 − 11 |
| 21 / 22 (23) | Doanh thu tài chính / Chi phí tài chính (trong đó lãi vay) | |
| 24 | Phần lãi (lỗ) trong công ty liên doanh, liên kết | consolidated only |
| 25 / 26 | Chi phí bán hàng / Chi phí quản lý doanh nghiệp | |
| 30 | Lợi nhuận thuần từ hoạt động kinh doanh | = 20 + (21 − 22) + 24 − (25 + 26) |
| 31 / 32 / 40 | Thu nhập khác / Chi phí khác / Lợi nhuận khác | 40 = 31 − 32 |
| 50 | Tổng lợi nhuận kế toán trước thuế | = 30 + 40 |
| 51 / 52 | Chi phí thuế TNDN hiện hành / hoãn lại | |
| **60** | **Lợi nhuận sau thuế TNDN** | = 50 − 51 − 52; consolidated: = 61 + 62 |
| 61 / 62 | LNST của công ty mẹ / của cổ đông không kiểm soát | |
| 70 / 71 | Lãi cơ bản / suy giảm trên cổ phiếu | **VND per share**, not scaled by the table unit |

## Cash flow, indirect method (Báo cáo lưu chuyển tiền tệ)

| Code | Line |
|---|---|
| 01 | Lợi nhuận trước thuế (same figure as income statement 50) |
| 02–07 | Adjustments: khấu hao, dự phòng, chênh lệch tỷ giá, lãi lỗ đầu tư, chi phí lãi vay, khác |
| 08 | Lợi nhuận từ HĐKD trước thay đổi vốn lưu động |
| 09–17 | Working-capital changes (10 = tăng, giảm hàng tồn kho), lãi vay đã trả, thuế đã nộp |
| **20** | Lưu chuyển tiền thuần từ hoạt động kinh doanh |
| 21–27 / **30** | Investing lines / Lưu chuyển tiền thuần từ hoạt động đầu tư |
| 31–36 / **40** | Financing lines / Lưu chuyển tiền thuần từ hoạt động tài chính |
| 50 | Lưu chuyển tiền thuần trong kỳ = 20 + 30 + 40 |
| 60 | Tiền và tương đương tiền đầu kỳ |
| 61 | Ảnh hưởng của thay đổi tỷ giá |
| 70 | Tiền và tương đương tiền cuối kỳ = 50 + 60 + 61, equal to balance-sheet 110 at year end |

## Codes shared between statements

01, 02, 10, 11, 20, 21, 22, 23, 24, 25, 26, 30, 31, 32, 40, 50, 60, 61 and 70 exist in both the income statement and the cash flow. Line 60 was the known case (K5); the others are the same problem. Decide the statement from the page title and the label, never from the code.

## Cross-statement checks worth knowing

- Cash flow 01 (profit before tax) = income statement 50.
- Cash flow 70 (closing cash) = balance sheet 110 closing; cash flow 60 (opening cash) = balance sheet 110 opening.
- Balance sheet 421 (retained earnings) moves with income statement 60 less dividends and fund allocations; a loose check only.
- Next year's report repeats this year's figures in its comparative column; differences are restatements (K22) or reading errors.
