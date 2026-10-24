import math
import re

SKILL_META = {
    "name": "safe_math_solver",
    "description": "Giải toán số học an toàn: kiểm tra số nguyên tố, phân tích thừa số, tính giai thừa, ước chung lớn nhất (GCD), bội chung nhỏ nhất (LCM) và dãy Fibonacci.",
    "keywords": ["nguyên tố", "prime", "giai thừa", "factorial", "fibonacci", "ước chung", "gcd", "lcm", "bội chung", "thừa số"],
    "parameters": {
        "query": "Câu hỏi toán học chứa các số nguyên"
    }
}

def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

def _prime_factors(n: int) -> list[int]:
    factors = []
    d = 2
    temp = abs(n)
    while d * d <= temp:
        while temp % d == 0:
            factors.append(d)
            temp //= d
        d += 1
    if temp > 1:
        factors.append(temp)
    return factors

def run(query: str = "", **kwargs) -> dict:
    ints = [int(x) for x in re.findall(r"\b\d+\b", str(query))]
    if not ints:
        return {"error": "Không tìm thấy số nguyên nào trong câu hỏi."}

    primary = ints[0]
    result = {
        "input_numbers": ints,
        "primary_number": primary,
        "is_prime": _is_prime(primary),
        "prime_factors": _prime_factors(primary) if primary <= 10**9 else [],
    }
    if primary <= 50:
        result["factorial"] = math.factorial(primary)
        a, b = 0, 1
        fib = []
        for _ in range(min(primary, 30)):
            fib.append(a)
            a, b = b, a + b
        result["fibonacci_sequence"] = fib

    if len(ints) >= 2:
        g = ints[0]
        l = ints[0]
        for x in ints[1:]:
            g = math.gcd(g, x)
            l = math.lcm(l, x)
        result["gcd_all"] = g
        result["lcm_all"] = l

    return result

def self_test() -> bool:
    r1 = run(query="Kiểm tra số nguyên tố và ước chung của 12 và 18")
    return r1.get("gcd_all") == 6 and r1.get("lcm_all") == 36 and r1.get("is_prime") is False