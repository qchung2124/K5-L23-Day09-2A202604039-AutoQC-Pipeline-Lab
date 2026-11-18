# Báo cáo Day 09 — Hoàng Quốc Chung, 2A202604039

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát `10`). Từ lô dữ liệu thô ban đầu gồm **224 ảnh**, bước kiểm tra cửa vào (intake) đã loại bỏ **21 ảnh** lỗi (còn lại **203 ảnh** sạch đưa vào kiểm tra nhãn và xuất ra `submission/export/clean_v1/`). Lý do chính khiến lô bị giữ ở trạng thái **Hold**: dù toàn bộ lỗi bắt buộc (`ERROR`) đã được xử lý về `0` và người duyệt đã dùng hết ngân sách **80/203 ảnh**, vẫn còn **38/203 ảnh (18.72%)** mang cảnh báo chưa được duyệt, vượt ngưỡng cho phép `10.00%` của cổng.

## 2. Lỗi và phân việc
Tổng hợp từ danh sách lỗi thô ban đầu (`02_error_list_v1.txt`, gồm **57 lỗi `ERROR`** và **153 cảnh báo `WARN`**):

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy (autofix) | Trùng byte MD5 100%, quy tắc tất định, xoá an toàn ở bước intake. |
| `DUP_IMAGE_NEAR` | 3 ảnh | Máy (autofix) | Khoảng cách băm nhận thức `phash <= 6`, ảnh biến đổi nhẹ từ ảnh gốc trong lô. |
| `LEAK_TEST` | 5 ảnh | Máy (autofix) | Trùng ảnh với tập `test/` hoặc `gold_val/`, bắt buộc loại để chống rò rỉ dữ liệu. |
| `BAD_SIZE` | 3 ảnh | Máy (autofix) | Cạnh ngắn nhỏ hơn ngưỡng quy định `250px`. |
| `CORRUPT_IMAGE` | 2 ảnh | Máy (autofix) | File ảnh hỏng/cắt cụt, không giải mã được pixel khi gọi `Image.load()`. |
| `BAD_CLASS_NAME` | 2 lỗi | Máy (autofix) | Tên lớp trong `data.yaml` viết sai chuẩn, máy tự ghi đè đúng danh sách `cfg["classes"]`. |
| `BAD_CLASS_ID` | 6 dòng | Máy (autofix) | ID lớp nằm ngoài phạm vi hợp lệ `0..3` (vd: `93`, `4`, `-1`), máy xoá dòng an toàn. |
| `BAD_FORMAT` | 3 dòng | Máy (autofix) | Dòng nhãn thiếu cột hoặc chứa giá trị `nan`/ký tự lạ, không thể dùng huấn luyện. |
| `BOX_ZERO` | 4 dòng | Máy (autofix) | Chiều rộng hoặc chiều cao `<= 0`, box rỗng vô nghĩa. |
| `DUP_BOX` | 7 dòng | Máy (autofix) | Trùng lớp và `IoU > 0.9` với dòng trước đó trong cùng file nhãn. |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy (autofix) | Mép box vượt biên `[0, 1]` quá `0.002`; máy tự cắt (clip) toạ độ về `[0, 1]`. |
| `MISSING_LABEL_FILE` | 6 ảnh | Người (hàng đợi) | Ảnh hợp lệ nhưng thiếu file `.txt`; máy không được phép bịa nhãn hay tạo file rỗng. |
| `POSSIBLE_MISSING` | 53 cảnh báo | Người (hàng đợi) | Model `yolo26l` (`conf >= 0.6`) phát hiện vật thể nhưng nhãn thiếu box; cần người xác nhận. |
| `POSSIBLE_FALSE_POS` | 29 dòng | Người (hàng đợi) | Box nhãn không khớp dự đoán nào của model (`max_IoU < 0.3`); có thể do model bỏ sót. |
| `POSSIBLE_LOOSE_BOX` | 28 cảnh báo | Người (hàng đợi) | Cùng lớp với dự đoán model nhưng `IoU < 0.5`; cần người đối chiếu độ khít khung. |
| `POSSIBLE_WRONG_CLASS` | 18 cảnh báo | Người (hàng đợi) | Box khớp vị trí (`IoU >= 0.5`) nhưng khác lớp dự đoán; dễ nhầm giữa `car`/`truck`/`bus`. |
| `EMPTY_LABEL` | 12 ảnh | Người (hàng đợi) | File nhãn rỗng (0 byte): cần người phân biệt ảnh nền thật hay người gán bỏ quên. |
| `BOX_TINY` | 6 dòng | Người (hàng đợi) | Cạnh ngắn `< 12px`, cảnh báo để kiểm tra vật thể quá nhỏ ngoài guideline. |
| `BOX_HUGE` | 3 dòng | Người (hàng đợi) | Diện tích box `> 0.95` khung hình, cảnh báo nguy cơ box bao trùm nhầm toàn ảnh. |
| `CLASS_RARE` | 4 cảnh báo | Người (hàng đợi) | Lớp xuất hiện ít hơn `5` box trong lô, cảnh báo phân phối mất cân bằng. |

* **Cách xếp ưu tiên trong `05_review_queue.csv`:** Hàng đợi tính điểm ưu tiên dựa trên trọng số rủi ro trong `configs/pipeline.yaml`: các ảnh thiếu file nhãn (`NEEDS_LABEL`, trọng số `10`) như `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219` được đẩy lên đầu hàng để triệt tiêu toàn bộ lỗi bắt buộc (`ERROR`), tiếp theo là các ảnh chồng nhiều cảnh báo ngữ nghĩa nghiêm trọng (`POSSIBLE_WRONG_CLASS`: trọng số `3`, `POSSIBLE_MISSING`: `2`, `POSSIBLE_FALSE_POS`: `2`, `POSSIBLE_LOOSE_BOX`: `1.5`).
* **Hiệu quả xử lý lỗi ngữ nghĩa với ngân sách 80 ảnh:** Trong 125 ảnh vào hàng đợi, người duyệt xử lý trọn vẹn 6 ảnh `NEEDS_LABEL` và 74 ảnh cảnh báo ưu tiên cao nhất, qua đó giải quyết được **71/128 (55.5%)** cảnh báo ngữ nghĩa (còn lại **57** cảnh báo ở `07_error_list_v3.txt`: giảm `POSSIBLE_MISSING` từ `53 → 13`, `POSSIBLE_WRONG_CLASS` từ `18 → 3`, `POSSIBLE_FALSE_POS` từ `29 → 21`, và `POSSIBLE_LOOSE_BOX` từ `28 → 20`).

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | **6** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` (F1: `0.67 → 0.80`) | Giữ Precision tuyệt đối `1.00` để không xoá nhầm ảnh sạch, đồng thời nâng Recall bắt ảnh gần trùng từ `50%` lên `67%`. |
| `second_opinion.conf` | 0.25 | **0.6** | `WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83`; `MISSING`: `0.50 / 1.00` → `0.57 / 1.00` | Lọc bớt báo động giả ở ngưỡng tự tin thấp (`0.25–0.5`) mà vẫn bảo toàn nguyên vẹn Recall `1.00` cho lỗi thiếu nhãn và `0.83` cho lỗi sai lớp. |

* **Điểm calibration có thể đánh lừa trên dữ liệu thật:** Trên bảng sweep của tập `calib` (chỉ 39 ảnh), `phash_dist = 16` cho F1 cao nhất (`0.91`, Recall `0.83`), dễ đánh lừa người chọn lấy ngưỡng `16`. Tuy nhiên, khoảng cách Hamming `16/64` bit là quá lỏng; trên lô `raw` (224 ảnh giao thông có nhiều góc chụp tương đồng) ngưỡng này có nguy cơ xoá nhầm ảnh khác nhau. Khi chọn ngưỡng an toàn `6` và kiểm tra trực tiếp `01_intake.csv`, pipeline chỉ loại đúng **3 cặp** trùng gần đúng (`img_0076`–`img_0042` dist `0`, `img_0143`–`img_0037` dist `0`, `img_0223`–`img_0077` dist `6`), số lượng ảnh loại ở bước intake (`21/224` ảnh) hoàn toàn hợp lý.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
* **(a) Chứng minh cửa chặn hoạt động đúng:** Khi chạy thử với ngân sách duyệt bằng 0 (`python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`), 6 ảnh `MISSING_LABEL_FILE` không có người gán nhãn nên vẫn giữ nguyên `6 lỗi bắt buộc (ERROR)`. Cửa chặn `gate` lập tức trả về quyết định **REWORK** với mã thoát **`EXIT_CODE=20`** và dừng quy trình ở Bước 5 (**không xuất** thư mục dataset `work/exp_nb`), ngăn dữ liệu thiếu nhãn lọt ra ngoài.
* **(b) Các điểm mù của pipeline (có bằng chứng):**
  1. **Ảnh trùng bị biến đổi mạnh (cắt sâu / xoay / thay đổi tỷ lệ khung hình lớn):** Trên tập `calib`, ngay cả với `phash_dist = 6`, Recall của `DUP_IMAGE_NEAR` chỉ đạt `0.67` (bỏ sót `2/6` ảnh gần trùng được chèn cố ý) vì băm nhận thức `phash` nhạy cảm với phép cắt xén mạnh (crop).
  2. **Lỗi ngữ nghĩa mà model đối chiếu cũng mắc phải hoặc nằm ngoài ngưỡng lọc:** Các vật thể nhỏ hơn `min_area_px = 600 px²` bị `second_opinion` bỏ qua khi kiểm tra `POSSIBLE_MISSING`; ngoài ra những ca nhầm lẫn ngữ nghĩa khó giữa các lớp xe (`car` ↔ `truck` ↔ `bus`) hoặc box lệch nhẹ nhưng vẫn đạt `IoU >= 0.5` (như các box có `IoU = 0.49` sát ngưỡng ở `img_0021`) sẽ không bị gắn cờ cảnh báo.
  3. *(Ghi chú thêm 1–2 ví dụ cụ thể bạn đã quan sát trực tiếp trong `work/viz/` ở Bước 1, kèm tên ảnh `img_xxxx`.)*
   - img_0001.jpg — Bỏ sót vật thể lớn: Người mặc quân phục rằn ri đứng ngay bên phải trung tâm ảnh rất rõ nét nhưng hoàn toàn không có bounding box gán nhãn.   
   - img_0030.jpg — Điểm mù do người đứng sát nhau / che khuất (DENSE_IMAGE & điểm mù second_opinion): Nhiều vận động viên đứng xếp hàng ngang ở khu vực giữa sân bị chồng lấp lên nhau, khiến box vẽ bị lệch hoặc thiếu người đứng khuất phía sau — đây là điểm mù điển hình mà ngay cả model đối chiếu yolo26l cũng dễ bỏ sót hoặc gộp nhầm box nếu IoU không chạm ngưỡng.


## 5. Train: raw vs clean (tùy chọn, chấm riêng)
*(Nếu bạn chạy xong Colab: dán bảng từ `submission/results/comparison.md` vào đây và nhận xét chênh lệch mAP50 so với độ lệch chuẩn giữa các seed. Nếu chưa chạy: ghi "Chưa chạy phần train Colab do giới hạn thời gian; tập trung hoàn thiện và kiểm định phần lõi của pipeline QC.")*

Thí nghiệm huấn luyện **yolo26n** trong **20 epoch** trên **2 seed** (so sánh `raw` 224 ảnh và `clean` 203 ảnh):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 203 | 2 | 0.699 ± 0.025 | 0.486 ± 0.013 | 0.796 ± 0.050 | 0.596 ± 0.049 |

Chênh mAP50 (clean − raw) = **-0.027** (trong khi Precision tăng **+0.032** từ `0.764` lên `0.796`, nhưng Recall giảm **-0.053** từ `0.649` xuống `0.596`).

* **Kết luận trung thực:** Độ giảm mAP50 (`|-0.027|`) chỉ xấp xỉ **1.08 lần** độ lệch chuẩn giữa các seed của tập `clean` (`±0.025`), tức nằm sát ngưỡng nhiễu ngẫu nhiên với cỡ mẫu chỉ 2 seed; chưa đủ cơ sở thống kê để khẳng định `clean` kém hơn `raw` về năng lực tổng quát hóa thực tế, dù Precision trên `clean` đã cải thiện rõ rệt.
* **Các giả thuyết giải thích hiện tượng & cách kiểm chứng:**
  1. **Rò rỉ dữ liệu (`LEAK_TEST`) làm điểm số của `raw` cao giả tạo:** Ở bước intake (`01_intake.csv`), pipeline đã phát hiện và loại bỏ **5 ảnh** trong `raw` bị trùng với tập `test/` (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`). Khi train trên `raw`, model được "học tủ" trực tiếp 5 ảnh thuộc tập `test` nên mAP50 của `raw` bị thổi phồng giả tạo. *Cách kiểm:* Đánh giá lại cả hai model trên một tập test mới hoàn toàn độc lập, hoặc loại bỏ 5 ảnh rò rỉ khỏi tập test khi tính điểm cho `raw`.
  2. **Nhãn máy còn sót lại trong `clean` do trạng thái Hold (ngân sách duyệt giới hạn 80 ảnh):** Vì pipeline kết luận **Hold** (`18.72%` ảnh cảnh báo chưa được duyệt), tập `clean` vẫn còn **38 ảnh** chưa qua mắt người duyệt (gồm 13 cảnh báo `POSSIBLE_MISSING` và 21 cảnh báo `POSSIBLE_FALSE_POS`), làm giảm số lượng mẫu huấn luyện sạch và khiến Recall giảm nhẹ từ `0.649` xuống `0.596`. *Cách kiểm:* Cấp thêm ngân sách duyệt để xử lý nốt 38 ảnh tồn đọng (đưa lô về **Release**), sau đó train lại và so sánh kết quả.
  3. **Tập `test` nhỏ (100 ảnh) và chỉ chạy 2 seed / 20 epoch:** Với 100 ảnh test và 20 epoch, dao động ngẫu nhiên giữa các seed (`±0.025` ở `clean`) đủ lớn để che lấp sự cải thiện thực sự của dữ liệu sạch. *Cách kiểm:* Tăng số lượng seed lên `3–5` seed và tăng số epoch hội tụ để giảm phương sai đo lường.

## 6. Quyết định và ghi chú AI
* **(a) Quyết định cuối & hướng xử lý tiếp theo:** Quyết định hiện tại của lô dữ liệu là **Hold** (`18.72%` ảnh còn cảnh báo chưa duyệt, tương đương `38/203` ảnh). Để chuyển trạng thái từ **Hold** sang **Release**, cần bổ sung thêm ngân sách duyệt tối thiểu **18 ảnh** nữa (nâng tổng số ảnh được người duyệt từ `80` lên `>= 98/203` ảnh) nhằm đưa số ảnh cảnh báo tồn đọng xuống dưới `20 ảnh` (`< 10.00%`).
* **(b) Ghi chú sử dụng AI:**
  * *Prompt chính:* Yêu cầu hỗ trợ triển khai 4 module (`label_format`, `gate`, `autofix`, `second_opinion`) bám sát docstring, danh sách mã lỗi và các ca biên trong bộ test `pytest`.
  * *Cách kiểm code AI:* Đối chiếu từng nhánh điều kiện với docstring, chạy `pytest` cho từng module riêng lẻ đến khi toàn bộ `79/79` unit test xanh, sau đó chạy thực nghiệm `make calibrate` và `make run` để kiểm tra chéo các file báo cáo `01_intake.csv`, `03_fixes.csv`, `07_error_list_v3.txt`.
  * *1 lần AI sai / cần chỉnh:* Khi xử lý lỗi dòng trong `autofix.py`, cần lưu ý ưu tiên hành động xoá dòng (`drop_line`) trước cắt toạ độ (`clip_box`) trên cùng một dòng dính 2 lỗi và giữ nguyên chỉ số dòng gốc khi file có dòng trống xen giữa để đảm bảo tính idempotent.