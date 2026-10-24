import math
import re
import statistics

SKILL_META = {
    "name": "statistical_analyzer",
    "description": "Phân tích thống kê mô tả chuỗi số: tính trung bình (mean), trung vị (median), phương sai, độ lệch chuẩn (stdev), tứ phân vị (IQR) và tìm giá trị ngoại lai (outliers).",
    "keywords": ["thống kê", "trung bình", "trung vị", "độ lệch chuẩn", "ngoại lai", "outlier", "outliers", "phương sai", "statistics", "mean", "median", "stdev", "chuỗi số", "dữ liệu"],
    "parameters": {
        "query": "Chuỗi văn bản chứa danh sách các con số cần phân tích thống kê"
    }
}

def _extract_numbers(text: str) -> list[float]:
    raw = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", text)
    return [float(x) for x in raw]

def run(query: str = "", **kwargs) -> dict:
    nums = kwargs.get("numbers")
    if not nums:
        nums = _extract_numbers(str(query))
    if not nums or len(nums) < 2:
        return {"error": "Cần ít nhất 2 con số để phân tích thống kê."}

    sorted_nums = sorted(nums)
    n = len(sorted_nums)
    mean_val = statistics.mean(sorted_nums)
    median_val = statistics.median(sorted_nums)
    stdev_val = statistics.stdev(sorted_nums) if n > 1 else 0.0
    variance_val = statistics.variance(sorted_nums) if n > 1 else 0.0

    mid = n // 2
    lower_half = sorted_nums[:mid]
    upper_half = sorted_nums[mid + (1 if n % 2 != 0 else 0):]
    q1 = statistics.median(lower_half) if lower_half else sorted_nums[0]
    q3 = statistics.median(upper_half) if upper_half else sorted_nums[-1]
    iqr = q3 - q1
    low_fence = q1 - 1.5 * iqr
    high_fence = q3 + 1.5 * iqr

    iqr_outliers = [x for x in sorted_nums if x < low_fence or x > high_fence]
    z_outliers = [
        x for x in sorted_nums
        if stdev_val > 0 and abs((x - mean_val) / stdev_val) >= 2.0
    ]

    return {
        "count": n,
        "sorted_values": sorted_nums,
        "sum": round(sum(sorted_nums), 4),
        "min": sorted_nums[0],
        "max": sorted_nums[-1],
        "mean": round(mean_val, 4),
        "median": round(median_val, 4),
        "stdev": round(stdev_val, 4),
        "variance": round(variance_val, 4),
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(iqr, 4),
        "iqr_bounds": [round(low_fence, 4), round(high_fence, 4)],
        "outliers_iqr": iqr_outliers,
        "outliers_zscore_gt2": z_outliers
    }

def self_test() -> bool:
    res = run(query="Phân tích [10, 12, 14, 15, 16, 18, 20, 100]")
    return (
        res.get("count") == 8
        and 100.0 in res.get("outliers_iqr", [])
        and round(res.get("median", 0), 1) == 15.5
    )