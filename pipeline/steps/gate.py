"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    # TODO
    raise NotImplementedError("gate chưa làm")



def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stem_set = set(image_stems)
    reviewed_set = set(reviewed)
    hold_threshold = cfg["gate"]["warn_ratio_hold"]

    # 1. Đếm toàn bộ lỗi bắt buộc (không bao giờ bỏ qua kể cả khi ảnh đã duyệt)
    error_issues = [i for i in issues if i.severity == ERROR]
    n_errors = len(error_issues)

    # 2. Đếm số ảnh hợp lệ còn cảnh báo chưa được duyệt
    warn_images = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in stem_set and i.image not in reviewed_set
    }
    n_images = len(stem_set)
    n_warn_images = len(warn_images)
    warn_ratio = round(n_warn_images / n_images, 4) if n_images > 0 else 0.0

    # 3. Cây quyết định Release / Hold / Rework
    reasons: list[str] = []
    if n_errors >= 1:
        decision = "Rework"
        reasons.append(f"Còn {n_errors} lỗi bắt buộc (ERROR) chưa được xử lý.")
    elif warn_ratio >= hold_threshold:
        decision = "Hold"
        reasons.append(
            f"Tỉ lệ ảnh còn cảnh báo chưa duyệt là {warn_ratio:.2%} "
            f"({n_warn_images}/{n_images} ảnh) >= ngưỡng {hold_threshold:.2%}."
        )
    else:
        decision = "Release"
        reasons.append(
            f"Không còn lỗi bắt buộc; tỉ lệ ảnh còn cảnh báo là {warn_ratio:.2%} "
            f"({n_warn_images}/{n_images} ảnh) < ngưỡng {hold_threshold:.2%}."
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }