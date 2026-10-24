import base64
import collections
import hashlib
import math

SKILL_META = {
    "name": "text_entropy_hash",
    "description": "Phân tích lý thuyết thông tin văn bản: tính Shannon Entropy, tạo mã băm SHA-256, mã hóa Base64 và đếm tần suất ký tự/từ.",
    "keywords": ["entropy", "sha256", "băm", "hash", "base64", "tần suất từ", "độ dài chuỗi", "shannon"],
    "parameters": {
        "query": "Văn bản cần tính entropy hoặc băm SHA-256"
    }
}

def run(query: str = "", **kwargs) -> dict:
    text = str(query).strip()
    if not text:
        return {"error": "Chuỗi đầu vào rỗng."}

    length = len(text)
    counts = collections.Counter(text)
    entropy = -sum((c / length) * math.log2(c / length) for c in counts.values())
    sha256_hex = hashlib.sha256(text.encode("utf-8")).hexdigest()
    b64_str = base64.b64encode(text.encode("utf-8")).decode("ascii")
    words = text.split()

    return {
        "char_length": length,
        "word_count": len(words),
        "shannon_entropy_bits_per_char": round(entropy, 4),
        "sha256": sha256_hex,
        "base64": b64_str[:120],
        "top_5_chars": counts.most_common(5)
    }

def self_test() -> bool:
    res = run(query="NEXUS-ZERO self evolving AI")
    return res.get("char_length") == 27 and len(res.get("sha256", "")) == 64