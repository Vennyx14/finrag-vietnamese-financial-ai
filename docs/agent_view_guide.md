# Hướng dẫn dùng Agent view cho FinRAG

> This guide is for Claude Code. For the GPT-only Codex coordinator, roles and workspace procedure, use [the Codex guide](../.codex/README.md) and AGENTS.md section 10 rule 12.

Lập ngày 2026-11-08 với Claude Code 2.1.304, gói Claude Pro, Windows. Agent view đang ở dạng *research preview*, nên phím tắt và hành vi có thể đổi theo phiên bản. Khi thấy khác tài liệu này, gõ `?` trong agent view hoặc xem <https://code.claude.com/docs/en/agent-view>.

Quy tắc cho agent nằm ở `AGENTS.md`, Mục 10, quy tắc 11. Tài liệu này dành cho bạn, người giao việc và gộp kết quả.

## Chế độ tự động (khuyến nghị): bạn chỉ ngồi xem

Bạn chỉ trò chuyện với **một phiên Claude trong VS Code, mở ở repo chính**. Đây là phiên điều phối. Nó giao việc cho agent con chạy trong worktree riêng, đọc lại kết quả, và chỉ hỏi bạn ở các cổng. Bạn không cần mở agent view.

### Giao việc

Gõ một câu vào phiên điều phối, ví dụ:

```text
Làm P2 theo docs/development_plan.md bằng finrag-worker-opus.
Sửa K29 bằng finrag-worker.
Tiếp tục kế hoạch, tự chọn agent.
```

Nêu tên agent trong câu giao việc, để phiên điều phối biết bạn muốn giao cho agent con thay vì tự làm.

### Bốn agent và cách chọn model

| Agent | Model | Dùng cho |
|---|---|---|
| `finrag-worker` | Sonnet | Việc đã rõ cách làm: đồng bộ tài liệu, chữ trên giao diện, lỗi đã mô tả rõ trong AGENTS.md Mục 13, thêm test, chạy đo hồi quy |
| `finrag-worker-opus` | Opus, mức suy luận high | **Mặc định cho code và logic**: sửa lỗi trong `src/` và `ui/`, lớp gọi LLM (P2), mở rộng độ phủ (P4), script đánh giá và thí nghiệm (P6, P7), chẩn đoán câu trả lời sai |
| `finrag-worker-deep` | Opus, mức suy luận cao nhất (max) | Chỉ việc cực khó, cần suy luận nhiều bước và phải chính xác tuyệt đối: LLM planner và chống chèn lệnh (P3.1 đến P3.3), thay đổi cách xác minh độc lập, sửa phần đọc số hoặc ingestion làm dựng lại toàn bộ dữ kiện, gán nhãn và đo tập niêm phong (P5), và việc mà `finrag-worker-opus` không giải quyết được |
| `finrag-reviewer` | Opus, chỉ đọc; high, hoặc max cho nhánh của `finrag-worker-deep` | Đọc lại độc lập mọi nhánh đụng tới logic tài chính, ingestion, LLM hay đánh giá, trước khi hỏi bạn có gộp không |

Nếu bạn nói "tự chọn agent", phiên điều phối chọn theo bảng trong skill `finrag-task`, mục "Delegated mode". Phần lớn việc code đi Opus high. Một việc chỉ lên max khi vừa cần suy luận dài nhiều bước, vừa có cái giá đắt nếu sai: câu trả lời sai mà vẫn được xác minh, hoặc phí mất tập niêm phong chỉ dùng được một lần. Khi phân vân giữa high và max, nó chọn high, rồi nâng lên max nếu agent dừng lại hoặc bước đọc lại phát hiện lỗi logic. Thứ tự nâng cấp: Sonnet → Opus high → Opus max; agent sau làm tiếp trên nhánh của agent trước. Opus tiêu hạn mức Pro nhanh hơn Sonnet, và max nhanh hơn high.

### Một vòng làm việc

1. Phiên điều phối kiểm tra cổng trong AGENTS.md, rồi giao việc. Bạn thấy một dòng: agent nào, vì sao.
2. Agent con làm trọn quy trình: viết test trước, code, chạy toàn bộ test, đo hồi quy, cập nhật tài liệu, commit trên nhánh riêng.
3. Nếu gặp câu hỏi kỹ thuật, phiên điều phối tự trả lời. Câu hỏi chính sách thì nó hỏi bạn, kèm đề xuất.
4. Phiên điều phối đọc thay đổi, chạy `finrag-reviewer` nếu cần, rồi hỏi bạn đúng một câu: gộp vào `main` không?
5. Bạn trả lời "đồng ý". Phiên điều phối gộp, chạy test trên `main`, xóa worktree và nhánh, rồi đề xuất bước tiếp theo.

### Cần nhớ

- **Giữ cửa sổ VS Code mở** khi agent đang chạy, vì agent con chạy bên trong phiên điều phối.
- **Đôi khi có yêu cầu cấp quyền** hiện trong VS Code, kèm tên agent đang hỏi. Duyệt nếu hợp lý; nhấn `Esc` để từ chối riêng lệnh đó.
- **Tối đa 2 agent con cùng lúc**, và chỉ khi chúng sửa các file khác nhau. P2, P3, P4 phải làm nối tiếp, nên thường chỉ có 1.
- **Mỗi bước kế hoạch nên dùng một cuộc trò chuyện mới.** Hội thoại dài làm mỗi lượt tốn hạn mức hơn.
- **Agent không push.** Bạn tự chạy `git push` khi muốn cập nhật GitHub.

### Luật chặn cứng (`.claude/settings.json`)

Ở chế độ auto, Claude được push lên mọi nhánh, kể cả `main`, và được đọc `.env` mà không hỏi. Repo chặn ba việc này cho mọi phiên, kể cả phiên của bạn:

| Luật | Tác dụng |
|---|---|
| `Bash(git push *)`, `PowerShell(git push *)` | Chặn lệnh push viết theo cách thông thường. Một lệnh viết khác, như `git -C . push`, vẫn lọt qua, nên quy tắc 11 trong AGENTS.md vẫn là lớp bảo vệ chính. |
| `Read(.env)` | Claude không đọc được khóa API, nên khóa không lọt vào cuộc trò chuyện. Code và script như `scripts/check_llm_key.py` vẫn đọc `.env` bình thường. |
| `Edit(**/data/benchmark/**)` | Claude không sửa tay được benchmark và nhãn gold (AGENTS.md Mục 7). Script tạo benchmark vẫn chạy được. |

Muốn bỏ một luật, xóa dòng tương ứng trong `.claude/settings.json` rồi commit.

---

## Tóm tắt nhanh (khi tự dùng agent view)

1. Commit mọi thứ bạn muốn agent thấy. Agent chỉ thấy những gì đã commit.
2. Mở terminal trong VS Code ở gốc repo, thấy chữ `(.venv)` ở đầu dòng lệnh, rồi chạy:
   ```powershell
   claude agents --model sonnet --permission-mode auto
   ```
3. Gõ một việc rồi nhấn `Enter`. Mỗi việc là một phiên chạy nền, trong worktree riêng.
4. Hàng màu vàng là phiên đang cần bạn. Chọn hàng đó, nhấn `Space` để xem và trả lời.
5. Khi phiên xong (màu xanh lá): xem nhánh của nó, `git merge` vào `main`, chạy lại test, rồi nhấn `Ctrl+X` hai lần để xóa phiên.
6. Với gói Pro, chạy tối đa 2 phiên cùng lúc.

---

## 1. Repo đã được cấu hình những gì

| Ở đâu | Nội dung | Vì sao |
|---|---|---|
| `.claude/settings.json` | `worktree.baseRef: "head"` | Worktree mới tách từ commit mới nhất ở máy bạn. Mặc định (`"fresh"`) tách từ `origin/main` trên GitHub, nên sẽ thiếu mọi commit chưa push. |
| `.worktreeinclude` | Chép `.env`, `.claude/settings.local.json`, `data/processed/`, `data/benchmark/`, và các file ViFinQA mà code đọc | Các file này bị gitignore nên worktree mới không có. Thiếu dữ liệu thì test tích hợp bị skip. |
| `.gitignore` | Thêm `.claude/worktrees/` và `.claude/settings.local.json` | Worktree không hiện thành file lạ trong repo chính; cài đặt cá nhân không bị commit. |
| `.git/config` (chỉ máy này) | `core.longpaths = true` | Cho Git xử lý đường dẫn dài hơn 260 ký tự trên Windows. Cài đặt này không nằm trong commit; nếu clone lại repo thì chạy lại `git config core.longpaths true`. |
| `AGENTS.md`, Mục 10, quy tắc 11 | Agent chuyển vào worktree trước khi chạy script; commit trên nhánh riêng; không push, không mở PR, không merge | Agent view mặc định tự push nhánh lên GitHub và có thể mở pull request nháp. Quy tắc này giữ mọi thứ ở máy bạn. Việc gộp do bạn làm, hoặc do phiên điều phối làm sau khi bạn "đồng ý". |
| `.claude/agents/` | `finrag-worker`, `finrag-worker-opus`, `finrag-worker-deep`, `finrag-reviewer` | Agent con cho chế độ tự động (mục đầu tài liệu) |
| `.claude/settings.json` | Luật chặn `git push`, đọc `.env`, sửa `data/benchmark/` | Xem "Luật chặn cứng" ở mục đầu tài liệu |

**Không chép `data/external/ViFinQA/.cache/`.** Đây chỉ là cache tải xuống của HuggingFace, không đoạn code nào đọc tới. Trong worktree, đường dẫn của nó vượt giới hạn 260 ký tự của Windows, và Git báo `Filename too long` khi xóa worktree. Khi thêm bộ dữ liệu mới vào `data/external/`, nhớ thêm dòng tương ứng vào `.worktreeinclude`.

**Đã kiểm chứng ngày 2026-11-08**, bằng `claude -p --worktree`:

- Worktree tách đúng từ commit mới nhất ở máy.
- Tạo worktree mất khoảng 30 giây, chiếm khoảng 700 MB.
- Số file dữ liệu trong worktree khớp với repo chính.
- Toàn bộ 523 test pass, 0 skipped.
- `git worktree remove` xóa sạch.

Theo tài liệu, `.worktreeinclude` áp dụng cho mọi worktree mà Claude Code tạo bằng Git. Bài kiểm tra ở Mục 4 xác nhận điều này riêng cho agent view trên máy bạn.

---

## 2. Bốn điều cần nhớ

1. **Agent chỉ thấy những gì đã commit.** Thay đổi chưa commit trong repo chính không có trong worktree, kể cả skill đang viết dở. Commit trước, rồi mới giao việc.
   - Vì `.claude/skills/` đã được commit, worktree chỉ nạp các skill có trong commit. Skill mới phải được commit thì phiên giao *sau đó* mới dùng được.
2. **Mỗi phiên tốn hạn mức như một phiên thường.** Tài liệu ghi: chạy 10 agent song song thì hết hạn mức nhanh khoảng 10 lần. Hai phiên là hết nhanh gấp đôi.
3. **Dữ liệu trong worktree là bản sao chụp lúc tạo worktree.** Nếu một phiên chạy `scripts/prepare_data.py`, sau khi gộp bạn phải chạy lại lệnh đó ở repo chính.
4. **Phiên bạn đẩy xuống nền bằng `←` hoặc `/bg` không có worktree riêng.** Nó tiếp tục sửa file ngay trong thư mục đang mở. Chỉ phiên được giao từ ô nhập của agent view (hoặc bằng `claude --bg`) mới được cách ly.

---

## 3. Mở agent view

1. Trong VS Code, mở terminal (`` Ctrl+` ``) ở gốc repo. Kiểm tra có `(.venv)` ở đầu dòng lệnh. Nếu không có, chạy `.\.venv\Scripts\Activate.ps1`.
   - Lý do: phiên nền dùng `PATH` của terminal mà bạn giao việc từ đó. Có `.venv` thì lệnh `python` của agent mới trỏ đúng tới môi trường của dự án.
2. Chạy:
   ```powershell
   claude agents --model sonnet --permission-mode auto
   ```
   - `--model sonnet`: model mặc định cho các phiên giao từ cửa sổ này. Xem Mục 5.3.
   - `--permission-mode auto`: phiên tự chạy lệnh mà không dừng hỏi từng lệnh. Một bộ phân loại sẽ chặn các hành động rủi ro. Với gói Pro, việc kiểm tra này chạy phía máy chủ và không tính vào hạn mức. Bạn có thể xác nhận bằng `/status` trong một phiên, dòng **Auto mode server** phải là `Enabled`.
   - Muốn chặt hơn thì dùng `--permission-mode acceptEdits`: tự sửa file nhưng hỏi trước mỗi lệnh. Khi đó phiên sẽ thường xuyên đứng chờ ở trạng thái vàng.
3. Lần đầu có thể hiện hộp thoại tin cậy thư mục (*trust*). Chọn đồng ý.

Luôn mở agent view từ **gốc repo chính**, không mở từ bên trong `.claude/worktrees/`.

---

## 4. Bài kiểm tra lần đầu (khoảng 2 phút, rất ít hạn mức)

Trong ô nhập của agent view, gõ `/model haiku`, nhấn `Enter`, rồi giao việc sau:

```text
Làm việc trong một worktree. Đây là việc kiểm tra môi trường; không sửa file nào.
Sau khi vào worktree, chạy hai lệnh:
python -c "import sys, src; print(sys.executable); print(src.__file__)"
python -m pytest -q -rs -p no:cacheprovider
Báo lại: hai đường dẫn được in ra, và số test passed, failed, skipped.
```

Kết quả đúng:

- Dòng 1 là `E:\Project\finrag-vietnamese-financial-ai\.venv\Scripts\python.exe`.
- Dòng 2 là `...\.claude\worktrees\<tên>\src\__init__.py`. Phải có `.claude\worktrees`. Nếu không có, agent đang chạy trong repo chính.
- `0 skipped`.

Xong thì gõ `/model default` để trở về Sonnet, rồi chọn phiên kiểm tra và nhấn `Ctrl+X` hai lần để xóa nó. Nếu kết quả khác, xem Mục 10.

---

## 5. Giao việc

### 5.1 Việc nào chạy song song được

| Chạy song song được | Lý do |
|---|---|
| Một bước chính (ví dụ P2) cùng một việc nhỏ (ví dụ K24) | Sửa các file khác nhau (`src/nlp/llm.py` và `src/pipeline/query.py`) |
| Một bước code cùng việc đồng bộ tài liệu cho bước *đã gộp* | Tài liệu nằm ở file khác code |
| Một bước code cùng việc chẩn đoán một câu hỏi (`finrag-diagnose`) | Chẩn đoán chủ yếu là đọc |

| Không chạy song song | Lý do |
|---|---|
| P2 với P3, P3 với P4 | Bước sau cần code của bước trước. AGENTS.md cấm bắt đầu mốc sau khi mốc trước chưa qua cổng. |
| Hai việc sửa cùng một file | Gây xung đột khi gộp |
| Bất cứ việc gì đụng tới tập niêm phong (P5) | Chỉ được đo **một lần**. Dùng một phiên duy nhất, sau khi mọi nhánh đã gộp. |
| Hai phiên cùng chạy `prepare_data.py` | Mỗi phiên tạo bản dữ liệu riêng, kết quả không so được với nhau |

### 5.2 Viết prompt

Ô nhập cần một **mô tả việc**, không phải lời chào. Mẫu:

```text
Làm <mã bước> theo docs/development_plan.md.
Phạm vi: <các file hoặc thư mục được sửa>. Không sửa file khác.
Dừng và hỏi tôi ở điểm [DUYỆT]. Không tự sang bước khác.
Xong khi: toàn bộ test pass. Báo số passed/failed/skipped và tên nhánh.
```

Ví dụ:

```text
Sửa K24 trong AGENTS.md (mã viết thường như "fpt" không được nhận).
Phạm vi: src/pipeline/query.py và test liên quan. Không sửa file khác.
Viết test thất bại trước, rồi sửa. Dừng và hỏi tôi ở điểm [DUYỆT].
Xong khi: toàn bộ test pass. Báo số passed/failed/skipped và tên nhánh.
```

Mẹo:

- Mỗi phiên làm **một** việc. Việc tiếp theo thì giao một phiên mới.
- Không cần gọi skill bằng tay. Các skill `finrag-*` thường tự được dùng theo nội dung việc. Ví dụ "làm P2" sẽ kích hoạt `finrag-task`.
- Không cần nhắc "chuyển vào worktree" hay "đừng push". AGENTS.md đã có quy tắc đó. Chỉ nhắc lại nếu thấy agent làm sai.
- Đặt tên phiên theo mã bước (`Ctrl+R`, ví dụ `P2`, `K24`) để dễ nhận ra.
- `Shift+Enter` để xuống dòng trong ô nhập. `Ctrl+Enter` để giao việc và vào phiên ngay (nếu bảng `?` có liệt kê phím này cho terminal của bạn). Prompt dài hơn 800 ký tự hoặc 3 dòng sẽ được thu gọn thành `[Pasted text #N]`; nội dung vẫn được gửi đầy đủ.

### 5.3 Chọn model

| Việc | Model |
|---|---|
| Việc nhỏ, sửa lỗi rõ ràng, đồng bộ tài liệu | Sonnet (mặc định trong cửa sổ đã mở bằng `--model sonnet`) |
| Thiết kế lớp LLM, planner (P2, P3), phân tích lỗi khó | Opus, nếu gói của bạn có |
| Kiểm tra môi trường, việc chỉ chạy lệnh | Haiku |

Gõ `/model opus` vào ô nhập trước khi giao việc nặng. Lệnh này chỉ áp dụng cho các phiên giao *sau đó* trong cửa sổ hiện tại. `/model default` để trở về mặc định. Để đổi model cho một phiên đang chạy, gửi `/model <tên>` làm câu trả lời trong khung xem nhanh (peek).

---

## 6. Theo dõi và trả lời

### Trạng thái

| Trạng thái | Màu | Ý nghĩa | Bạn làm gì |
|---|---|---|---|
| Working | Biểu tượng chuyển động | Đang chạy | Không cần làm gì |
| Needs input | Vàng | Chờ câu trả lời hoặc chờ cấp quyền | Xem bên dưới |
| Idle | Mờ | Chờ việc tiếp theo | Giao tiếp hoặc xóa |
| Completed | Xanh lá | Xong | Gộp kết quả (Mục 7) |
| Failed | Đỏ | Lỗi | Xem nhanh để biết lý do; trả lời để chạy tiếp |
| Stopped | Xám | Đã dừng | Trả lời để chạy tiếp từ hội thoại đã lưu |

### Trả lời phiên đang chờ

- Gõ `s:blocked` vào ô nhập để lọc ra các phiên đang chờ bạn.
- Chọn hàng, nhấn `Space` để mở khung xem nhanh (peek). Khung này hiện câu hỏi đầy đủ. Gõ câu trả lời rồi nhấn `Enter`. Với câu hỏi có lựa chọn, nhấn số của lựa chọn.
- **Câu hỏi cấp quyền không trả lời được trong khung xem nhanh.** Nhấn `→` (hoặc `Enter`) để vào phiên, trả lời, rồi nhấn `←` trên ô nhập trống để ra.
  - Trên Windows, nếu nhấn `←` trong khoảng nửa giây sau khi vào phiên, sẽ hiện `Ambiguous ←, press again to detach`. Nhấn `←` lần nữa.
- Khi agent view đang mở, bạn nhận chuông hoặc thông báo của terminal mỗi khi một phiên cần bạn, xong, hoặc lỗi. Tiêu đề tab terminal cũng hiện số phiên đang chờ.

### Các thao tác khác

- `/stop` gửi trong khung xem nhanh sẽ dừng phiên. `/usage` xem hạn mức.
- Ra khỏi phiên **không** dừng phiên; nó vẫn chạy nền.
- Phiên đã xong, hoặc đang chờ việc tiếp theo (không phải đang chờ cấp quyền), nếu không ai vào trong khoảng 1 giờ, sẽ bị tắt tiến trình để giải phóng máy. Khi đó nó không tốn hạn mức. Vào lại thì phiên chạy tiếp từ chỗ cũ. `Ctrl+T` ghim phiên để giữ tiến trình luôn chạy.
- Phiên chạy trên máy bạn. Tắt máy thì phiên dừng; mở lại agent view và trả lời phiên để chạy tiếp.

---

## 7. Nhận kết quả và gộp vào `main`

Khi một phiên chuyển sang xanh lá:

1. Nhấn `Space` để đọc báo cáo cuối. Báo cáo gồm: đã làm gì, file đổi, số test, tên nhánh.
2. Xem thay đổi, trong terminal ở repo chính:
   ```powershell
   git worktree list                          # nhánh của từng phiên
   git log --oneline main..<nhánh>            # các commit của phiên
   git diff --stat main...<nhánh>             # file nào đổi
   git diff main...<nhánh>                    # nội dung thay đổi
   ```
   Nhánh thường có dạng `worktree-<tên>`. Tên chính xác có trong báo cáo và trong `git worktree list`.
3. Gộp và kiểm tra lại, khi đang đứng ở `main`:
   ```powershell
   git merge <nhánh>
   python -m pytest -rs
   ```
   - Nếu phiên có dựng lại dữ liệu, chạy thêm `python scripts/prepare_data.py` ở repo chính.
   - Nếu Git báo thay đổi chưa commit sẽ bị ghi đè: commit những thay đổi đó (hoặc chờ phiên đang sửa ở repo chính xong) rồi gộp lại.
4. Xóa phiên: chọn hàng, nhấn `Ctrl+X` hai lần trong vòng 2 giây. Vì commit của phiên đã nằm trong `main`, việc xóa sẽ không bị chặn. Sau đó chạy `git branch`. Nếu nhánh vẫn còn, xóa bằng `git branch -d <nhánh>`. Lệnh `-d` sẽ từ chối xóa nhánh chưa gộp, nên an toàn.
5. Khi muốn cập nhật GitHub, tự chạy `git push`. Agent không push.

**Khi xung đột lúc gộp:**

1. Chạy `git merge --abort`.
2. Vào phiên đó và nhắn: "Gộp `main` mới nhất vào nhánh của bạn, sửa xung đột, chạy lại toàn bộ test, rồi commit."
3. Gộp lại như bước 3.

Cách này dùng được vì các worktree chung kho Git với repo chính, nên agent thấy nhánh `main` của bạn.

**Khi không muốn giữ kết quả:** nhấn `Ctrl+X` hai lần. Nếu nhánh có commit chưa gộp, lần xóa đầu bị từ chối và hiện số commit. Xóa thêm lần nữa thì worktree cùng các commit đó bị bỏ. **Đọc kỹ thông báo trước khi xóa lần hai.**

---

## 8. Tiết kiệm hạn mức Pro

- **Chạy tối đa 2 phiên cùng lúc.** Khi gần chạm giới hạn, dừng phiên phụ (`Ctrl+X`) và giữ một phiên.
- **Dùng Sonnet cho việc nhỏ**, để dành Opus cho việc cần suy luận nhiều. Xem hạn mức bằng `/usage`.
- **Một bước một phiên.** Hội thoại càng dài thì mỗi lượt càng tốn, vì toàn bộ ngữ cảnh được gửi lại. Bước sau nên giao trong phiên mới.
- **Prompt rõ ràng và có phạm vi** (Mục 5.2). Agent ít phải hỏi lại, nên tốn ít lượt hơn.
- **Không dùng `/batch` hay agent teams với gói Pro.** Chúng chạy cùng lúc nhiều agent và tiêu hạn mức rất nhanh.
- Khoản tốn nhỏ: dòng tóm tắt trên mỗi hàng dùng một yêu cầu ngắn tới model loại Haiku sau mỗi lượt. Bộ kiểm tra của chế độ `auto` không tính phí với gói Pro.

---

## 9. Dọn dẹp và dung lượng

- Mỗi worktree chiếm khoảng 700 MB (gần như toàn bộ là dữ liệu chép sang).
- Xóa phiên trong agent view sẽ xóa luôn worktree của phiên đó. Lệnh `claude rm <id>` thì giữ lại worktree nếu còn thay đổi chưa commit.
- Thỉnh thoảng kiểm tra worktree còn sót:
  ```powershell
  git worktree list
  git worktree remove <đường dẫn>      # nếu báo "locked": chạy git worktree unlock <đường dẫn> trước
  git worktree prune                   # gỡ đăng ký worktree mà thư mục đã mất
  ```
- Claude Code cũng tự quét định kỳ. Worktree của phiên nền cũ hơn số ngày trong cài đặt `cleanupPeriodDays` sẽ bị xóa, trừ khi còn thay đổi hoặc còn commit chưa push. Đừng dựa vào cơ chế này: gộp xong thì xóa phiên luôn.

---

## 10. Sự cố thường gặp

| Dấu hiệu | Nguyên nhân | Cách xử lý |
|---|---|---|
| Agent không thấy code hoặc skill mới | Chưa commit | Commit, rồi giao một phiên mới. Phiên cũ vẫn ở commit cũ. |
| Test bị skip trong phiên | Dữ liệu không được chép sang | Kiểm tra file có tồn tại ở repo chính và có khớp mẫu trong `.worktreeinclude`. Sửa xong thì giao phiên mới. |
| `python` không chạy được, hoặc thiếu `pandas` | Giao việc từ terminal chưa kích hoạt `.venv` | Thoát agent view (`Ctrl+C` hai lần), chạy `.\.venv\Scripts\Activate.ps1`, mở lại agent view và giao lại việc. |
| Agent chạy script khi vẫn đang ở repo chính, làm `data/manifests/` bị đổi | Phiên chưa chuyển vào worktree | Khôi phục bằng `git checkout -- data/manifests`, sau khi chắc rằng bạn không cần thay đổi đó. Nhắc agent làm đúng AGENTS.md, Mục 10, quy tắc 11. |
| Phiên vàng mãi | Đang chờ cấp quyền | Vào phiên (`→`) để trả lời |
| Xóa phiên bị từ chối vì commit chưa push | Nhánh có commit chưa gộp vào `main` | Gộp trước (Mục 7), hoặc xóa lần nữa để bỏ hẳn |
| `Filename too long` | Đường dẫn trong worktree vượt 260 ký tự | `core.longpaths` đã bật cho Git. Giữ tên worktree ngắn (dưới 40 ký tự) và không chép thư mục có đường dẫn sâu. |
| Có nhánh `worktree-*` xuất hiện trên GitHub | Agent đã push dù có quy tắc | `git push origin --delete <nhánh>`, rồi nhắc "không push" trong prompt các lần sau |
| `claude agents` chỉ in ra danh sách subagent | Bản Claude Code cũ | `claude update` |
| Phiên đỏ (Failed) sau khi tắt máy | Phiên chạy trên máy, tắt máy là dừng | Chọn phiên và trả lời để chạy tiếp từ hội thoại đã lưu |

---

## 11. Phím tắt và lệnh

### Trong agent view

| Phím | Tác dụng |
|---|---|
| `↑` / `↓` | Chọn hàng |
| `Enter` | Giao việc (khi đang gõ), hoặc vào phiên đang chọn |
| `Ctrl+Enter` | Giao việc và vào phiên ngay |
| `Shift+Enter` | Xuống dòng trong ô nhập |
| `Space` | Mở hoặc đóng khung xem nhanh |
| `→` | Vào phiên |
| `←` (ô nhập trống, khi đang ở trong phiên) | Ra khỏi phiên, quay về danh sách |
| `Alt+1` … `Alt+9` | Vào phiên số 1–9 |
| `Ctrl+R` | Đổi tên phiên |
| `Ctrl+T` | Ghim hoặc bỏ ghim |
| `Ctrl+S` | Nhóm theo trạng thái hoặc theo thư mục |
| `Ctrl+F` | Tìm theo tên |
| `Ctrl+X` | Dừng; nhấn lần nữa trong 2 giây để xóa |
| `Esc` | Đóng khung xem nhanh hoặc xóa ô nhập |
| `Ctrl+C` hai lần | Thoát agent view (các phiên vẫn chạy) |
| `?` | Danh sách phím tắt |

### Bộ lọc trong ô nhập

| Bộ lọc | Hiện ra |
|---|---|
| `s:blocked` | Các phiên đang chờ bạn |
| `n:K24` | Phiên có tên hoặc prompt đầu chứa "K24" |
| `o:` | Các phiên đã có kết quả |

### Lệnh từ terminal

| Lệnh | Tác dụng |
|---|---|
| `claude agents --json` | Liệt kê các phiên đang chạy dưới dạng JSON |
| `claude --bg "<việc>"` | Giao việc mà không cần mở agent view |
| `claude attach <tên>` | Vào một phiên trong terminal này |
| `claude logs <tên>` | In phần đầu ra gần nhất |
| `claude stop <id>` | Dừng phiên |
| `claude rm <id>` | Gỡ phiên khỏi danh sách (giữ hội thoại) |
| `claude daemon status` | Xem tiến trình quản lý phiên nền |

---

## Nguồn

- Agent view: <https://code.claude.com/docs/en/agent-view>
- Worktree, `.worktreeinclude`, `worktree.baseRef`: <https://code.claude.com/docs/en/worktrees>
- So sánh các cách chạy song song: <https://code.claude.com/docs/en/agents>
- Bộ kiểm tra của chế độ auto và phí: <https://code.claude.com/docs/en/auto-mode-classifier-billing>
