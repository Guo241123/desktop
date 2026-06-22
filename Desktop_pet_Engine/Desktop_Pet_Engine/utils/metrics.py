"""运行指标统计 — 请求数、Token 用量、费用、缓存命中率"""

import time
from datetime import datetime

_start_time = time.time()
_request_count = 0
_token_input_total = 0
_token_output_total = 0
_cost_total = 0.0
_cache_hits = 0
_cache_misses = 0

# DeepSeek 价格（每 1K tokens）
_PRICE_INPUT = 0.0005    # 输入 ¥0.0005/1K
_PRICE_OUTPUT = 0.002    # 输出 ¥0.002/1K


def record_request(input_tokens: int = 0, output_tokens: int = 0,
                   cache_hit: bool = False):
    global _request_count, _token_input_total, _token_output_total
    global _cost_total, _cache_hits, _cache_misses

    _request_count += 1
    _token_input_total += input_tokens
    _token_output_total += output_tokens
    _cost_total += (input_tokens / 1000) * _PRICE_INPUT
    _cost_total += (output_tokens / 1000) * _PRICE_OUTPUT
    if cache_hit:
        _cache_hits += 1
    else:
        _cache_misses += 1


def get_metrics() -> dict:
    runtime = int(time.time() - _start_time)
    total_reqs = _request_count
    total_cache = _cache_hits + _cache_misses
    cache_rate = round((_cache_hits / total_cache * 100), 1) if total_cache > 0 else 0

    return {
        "runtime": runtime,
        "runtime_str": f"{runtime // 3600:02d}:{(runtime % 3600) // 60:02d}:{runtime % 60:02d}",
        "request_count": total_reqs,
        "token_input": _token_input_total,
        "token_output": _token_output_total,
        "token_input_str": _fmt_tokens(_token_input_total),
        "token_output_str": _fmt_tokens(_token_output_total),
        "cache_hit_rate": cache_rate,
        "cost": round(_cost_total, 4),
        "cost_str": f"¥{_cost_total:.4f}",
        "start_time": datetime.fromtimestamp(_start_time).strftime("%H:%M:%S"),
    }


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)
