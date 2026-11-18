"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    # TODO
    raise NotImplementedError("check second_opinion chưa làm")





def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    so_cfg = cfg["second_opinion"]
    conf_thr = so_cfg["conf"]
    min_area_px = so_cfg["min_area_px"]
    fp_conf_thr = so_cfg["fp_conf"]
    iou_missing = so_cfg["iou_missing"]
    iou_match = so_cfg["iou_match"]
    iou_loose = so_cfg["iou_loose"]
    num_classes = len(ds.classes)

    issues: list[Issue] = []

    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue

        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        img_size = ds.image_size(stem)
        if img_size is None:
            continue
        img_w, img_h = img_size

        # Lấy các dòng nhãn hợp lệ kèm số dòng gốc (để báo line cho POSSIBLE_FALSE_POS)
        valid_labeled_lines: list[tuple[int, int, tuple[float, float, float, float]]] = []
        for line_no, text in raw_lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if 0 <= cls_id < num_classes:
                valid_labeled_lines.append((line_no, cls_id, (cx, cy, w, h)))

        img_preds = preds.get(stem, [])

        # 1. Duyệt từng dự đoán của model (theo đúng thứ tự trong preds[stem])
        for p in img_preds:
            p_cls, p_conf, pcx, pcy, pw, ph = int(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[5])
            if p_conf < conf_thr:
                continue
            area_px = (pw * img_w) * (ph * img_h)
            if area_px < min_area_px:
                continue

            p_box = (pcx, pcy, pw, ph)
            cands = []
            for _, l_cls, l_box in valid_labeled_lines:
                iou = iou_xywh(p_box, l_box)
                if iou >= iou_missing:
                    cands.append((iou, l_cls))

            if not cands:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"model dự đoán lớp {p_cls} (conf={p_conf:.2f}) nhưng không có box nhãn khớp",
                        extra={"conf": round(p_conf, 4), "pred_class": p_cls},
                    )
                )
                continue

            same_cls_ious = [iou for iou, l_cls in cands if l_cls == p_cls]
            if same_cls_ious:
                best_same = max(same_cls_ious)
                if best_same < iou_loose:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"box nhãn cùng lớp {p_cls} nhưng khớp lỏng (IoU={best_same:.2f} < {iou_loose})",
                            extra={"conf": round(p_conf, 4), "iou": round(best_same, 4)},
                        )
                    )
            else:
                best_diff = max(iou for iou, _ in cands)
                if best_diff >= iou_match:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            f"nhãn lệch lớp so với dự đoán model lớp {p_cls} (IoU={best_diff:.2f})",
                            extra={"conf": round(p_conf, 4), "iou": round(best_diff, 4), "pred_class": p_cls},
                        )
                    )

        # 2. Duyệt từng dòng nhãn hợp lệ để tìm POSSIBLE_FALSE_POS (dùng fp_conf, không lọc diện tích)
        fp_preds = [
            (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
            for p in img_preds
            if float(p[1]) >= fp_conf_thr
        ]

        for line_no, l_cls, l_box in valid_labeled_lines:
            max_iou = max((iou_xywh(l_box, pb) for pb in fp_preds), default=0.0)
            if max_iou < iou_missing:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"box nhãn lớp {l_cls} không khớp dự đoán nào của model (max_IoU={max_iou:.2f})",
                        line=line_no,
                        extra={"iou": round(max_iou, 4)},
                    )
                )

    return issues