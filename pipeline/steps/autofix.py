"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    # TODO
    raise NotImplementedError("autofix chưa làm")



DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMAGE_PREFIXES = ("DUP_IMAGE_",)
REMOVE_IMAGE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _is_remove_image(code: str) -> bool:
    return code in REMOVE_IMAGE_CODES or code.startswith(REMOVE_IMAGE_PREFIXES)


def _clip_yolo_line(raw_line: str) -> str | None:
    """Cắt box (cx, cy, w, h) về [0, 1]. Trả về chuỗi mới hoặc None nếu box nằm hẳn ngoài ảnh."""
    cls_id, cx, cy, w, h = parse_yolo_line(raw_line)
    x1 = max(0.0, min(1.0, cx - w / 2.0))
    y1 = max(0.0, min(1.0, cy - h / 2.0))
    x2 = max(0.0, min(1.0, cx + w / 2.0))
    y2 = max(0.0, min(1.0, cy + h / 2.0))
    nw, nh = x2 - x1, y2 - y1
    if nw <= 0.0 or nh <= 0.0:
        return None
    ncx, ncy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    return f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]
    fixes: list[dict] = []

    # 1. Xử lý lỗi cấp dataset: BAD_CLASS_NAME trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        before_names = ds.yaml_names()
        target_classes = list(cfg["classes"])
        if ds.yaml_path.exists():
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        else:
            data = {}
        data["nc"] = len(target_classes)
        data["names"] = target_classes
        ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append({
            "image": "data.yaml",
            "line": None,
            "action": "rename_classes",
            "before": str(before_names),
            "after": str(target_classes),
        })

    # 2. Xoá các ảnh bị lỗi ở bước intake (DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE)
    removed_stems: set[str] = set()
    for iss in errors:
        if _is_remove_image(iss.code) and iss.image not in removed_stems:
            removed_stems.add(iss.image)
            img_p = ds.image_path(iss.image)
            lbl_p = ds.label_path(iss.image)
            if img_p and img_p.exists():
                img_p.unlink()
            if lbl_p.exists():
                lbl_p.unlink()
            fixes.append({
                "image": iss.image,
                "line": None,
                "action": "remove_image",
                "before": iss.code,
                "after": "(đã xoá ảnh và nhãn)",
            })

    # 3. Ghi nhận các ảnh thiếu file nhãn (không tạo file rỗng)
    needs_label_seen: set[str] = set()
    for iss in errors:
        if iss.code == "MISSING_LABEL_FILE" and iss.image not in removed_stems and iss.image not in needs_label_seen:
            needs_label_seen.add(iss.image)
            fixes.append({
                "image": iss.image,
                "line": None,
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    # 4. Gom lỗi theo từng file nhãn và số dòng GỐC (xoá dòng luôn thắng cắt box)
    line_ops: dict[str, dict[int, str]] = defaultdict(dict)
    for iss in errors:
        if iss.image in removed_stems or iss.line is None:
            continue
        if iss.code in DROP_CODES:
            line_ops[iss.image][iss.line] = "drop"
        elif iss.code == "BOX_OUT_OF_IMAGE":
            if line_ops[iss.image].get(iss.line) != "drop":
                line_ops[iss.image][iss.line] = "clip"

    for stem, ops in line_ops.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        orig_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines: list[str] = []

        for idx, raw in enumerate(orig_lines, 1):
            op = ops.get(idx)
            if op == "drop":
                fixes.append({
                    "image": stem,
                    "line": idx,
                    "action": "drop_line",
                    "before": raw,
                    "after": "",
                })
            elif op == "clip":
                try:
                    clipped = _clip_yolo_line(raw)
                except ValueError:
                    clipped = None

                if clipped is None:
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": raw,
                        "after": "",
                    })
                else:
                    new_lines.append(clipped)
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "clip_box",
                        "before": raw,
                        "after": clipped,
                    })
            else:
                new_lines.append(raw)

        lbl_p.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

    return fixes