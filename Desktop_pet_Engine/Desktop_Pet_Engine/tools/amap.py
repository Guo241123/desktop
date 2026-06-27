"""tools/amap.py — 高德地图工具集

提供天气查询和行政区划编码查询，使用高德 Web 服务 API。
在 .env 中配置：AMAP_WEATHER_AK=你的高德Web服务AK
"""

import logging

import requests
from langchain.tools import tool

from config.settings import get_env

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────
AMAP_WEATHER_AK = get_env("AMAP_WEATHER_AK", "")
AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
AMAP_GEO_URL = "https://restapi.amap.com/v3/geocode/geo"


@tool
def get_county_weather(city_code: str, extensions: str = "all"):
    """
    查询国内区县天气，支持实况 + 7 天预报，使用高德天气 API

    :param city_code: 区县 6 位行政区划 adcode，如长沙县 430121，精准定位县城；也可直接传县名文本
    :param extensions: base=仅实况天气，all=实况+7天预报，默认 all
    :return: 天气完整 JSON 数据字符串，失败返回错误信息
    """
    if not AMAP_WEATHER_AK:
        return "⚠️ 未配置高德 API Key，请在 .env 中设置 AMAP_WEATHER_AK"

    params = {
        "key": AMAP_WEATHER_AK,
        "city": city_code,
        "extensions": extensions,
        "output": "json",
    }
    try:
        resp = requests.get(AMAP_WEATHER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            err_msg = f"天气查询失败，高德返回错误：{data.get('info', '未知错误')}"
            logger.error(err_msg)
            return err_msg
        logger.info("区县 %s 天气查询成功", city_code)
        return str(data)
    except requests.exceptions.RequestException as e:
        return f"网络请求异常，查询天气失败：{e}"
    except Exception as e:
        return f"查询天气未知异常：{e}"


@tool
def get_city_adcode(city_name: str):
    """
    根据市县名称查询 6 位行政区划 adcode，解决同名地区匹配问题，搭配天气工具使用

    :param city_name: 市/县名称，例如：宁乡县、桂阳县、长沙市
    :return: 匹配到的 adcode 编号，失败返回提示文本
    """
    if not AMAP_WEATHER_AK:
        return "⚠️ 未配置高德 API Key，请在 .env 中设置 AMAP_WEATHER_AK"

    params = {
        "key": AMAP_WEATHER_AK,
        "address": city_name,
        "output": "json",
    }
    try:
        resp = requests.get(AMAP_GEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1" or len(data.get("geocodes", [])) == 0:
            return f"未查询到 {city_name} 对应的行政区划编码"
        adcode = data["geocodes"][0]["adcode"]
        logger.info("%s 匹配 adcode：%s", city_name, adcode)
        return adcode
    except Exception as e:
        return f"获取行政区编码异常：{e}"
