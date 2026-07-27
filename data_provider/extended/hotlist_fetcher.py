# -*- coding: utf-8 -*-
"""
热榜数据抓取器 — 从 ai_mark 子系统融合

基于 NewsNow API 聚合多平台热榜：
  头条/百度/知乎/微博/抖音/B站/华尔街见闻/财联社/36氪等

原始来源：ai_mark/integrations/sources/hotlist/fetcher.py
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ============================================================
# 热榜平台定义
# ============================================================

PLATFORM_IDS = {
    "toutiao": "头条热榜",
    "baidu": "百度热搜",
    "zhihu": "知乎热榜",
    "weibo": "微博热搜",
    "douyin": "抖音热点",
    "bilibili": "B站热搜",
    "kuaishou": "快手热榜",
    "wallstreetcn": "华尔街见闻",
    "cls": "财联社",
    "36kr": "36氪",
    "ithome": "IT之家",
    "sspai": "少数派",
    "hupu": "虎扑",
    "douban": "豆瓣",
}

# 金融相关平台（默认抓取）
FINANCE_PLATFORMS = ["toutiao", "baidu", "weibo", "wallstreetcn", "cls", "36kr"]

# ============================================================
# 域名安全校验规则
# ============================================================

DOMAIN_RULES: Dict[str, str] = {
    "toutiao": "toutiao.com",
    "baidu": "baidu.com",
    "zhihu": "zhihu.com",
    "weibo": "weibo.com",
    "wallstreetcn": "wallstreetcn.com",
    "cls": "cls.cn",
    "36kr": "36kr.com",
    "ithome": "ithome.com",
    "sspai": "sspai.com",
}


@dataclass
class HotlistSourceConfig:
    """热榜数据源配置"""
    id: str
    name: str
    category: str = "hotlist"
    enabled: bool = True
    domain: str = ""


class HotlistFetcher:
    """热榜数据聚合抓取器"""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    DEFAULT_API = "https://newsnow.busiyi.world/api/s"

    def __init__(self, api_url: Optional[str] = None, proxy_url: Optional[str] = None,
                 timeout: int = 15):
        self.api_url = api_url or self.DEFAULT_API
        self.proxy_url = proxy_url
        self.timeout = timeout

    def _get(self, url: str) -> requests.Response:
        proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None
        return requests.get(
            url, headers=self.DEFAULT_HEADERS, proxies=proxies, timeout=self.timeout,
        )

    def _check_domain(self, items: List[Dict], expected_domain: str) -> Optional[str]:
        """域名安全校验 — 防止 SSRF/钓鱼"""
        if not expected_domain:
            return None
        expected = expected_domain.lower().strip()
        for item in items:
            for field in ("url", "mobileUrl"):
                url = item.get(field, "")
                if not url:
                    continue
                parsed = urlparse(url)
                if parsed.scheme != "https":
                    return f"{url} (非HTTPS)"
                hostname = (parsed.hostname or "").lower()
                if hostname != expected and not hostname.endswith("." + expected):
                    return f"{hostname} (来自 {url})"
        return None

    def fetch_platform(self, platform_id: str, max_retries: int = 2) -> Tuple[Optional[List[Dict]], str, Optional[str]]:
        """抓取单个平台热榜"""
        alias = PLATFORM_IDS.get(platform_id, platform_id)
        url = f"{self.api_url}?id={platform_id}&latest"

        for attempt in range(max_retries + 1):
            try:
                resp = self._get(url)
                resp.raise_for_status()
                data = resp.json()

                status = data.get("status", "")
                if status not in ("success", "cache"):
                    raise ValueError(f"状态异常: {status}")

                items = data.get("items", [])
                result = []
                for i, item in enumerate(items, 1):
                    title = item.get("title")
                    if not title or not str(title).strip():
                        continue
                    result.append({
                        "title": str(title).strip(),
                        "rank": i,
                        "url": item.get("url", ""),
                        "mobile_url": item.get("mobileUrl", ""),
                        "platform_id": platform_id,
                        "platform_name": alias,
                        "crawl_time": datetime.now().strftime("%H:%M"),
                    })

                status_info = "最新" if status == "success" else "缓存"
                logger.debug(f"[Hotlist] {alias}: {len(result)}条 ({status_info})")
                return result, platform_id, None

            except Exception as e:
                if attempt < max_retries:
                    wait = random.uniform(2, 5) + attempt * random.uniform(1, 2)
                    logger.warning(f"[Hotlist] {alias} 重试 {attempt+1}/{max_retries}, 等待{wait:.1f}s")
                    time.sleep(wait)
                else:
                    logger.error(f"[Hotlist] {alias} 失败: {e}")
                    return None, platform_id, str(e)

        return None, platform_id, "max retries"

    def fetch_all(self, platforms: Optional[List[str]] = None,
                  request_interval_ms: int = 200) -> Dict[str, Any]:
        """批量抓取多个平台热榜"""
        platforms = platforms or list(PLATFORM_IDS.keys())

        results = {}
        id_to_name = {}
        failed = []
        total_items = 0

        for i, pid in enumerate(platforms):
            items, _, error = self.fetch_platform(pid)
            id_to_name[pid] = PLATFORM_IDS.get(pid, pid)

            if error:
                failed.append({"platform": pid, "error": error})
            elif items:
                # 域名校验
                expected = DOMAIN_RULES.get(pid, "")
                if expected:
                    bad = self._check_domain(items, expected)
                    if bad:
                        logger.warning(f"[安全] {pid} 域名校验失败: {bad}")
                        failed.append({"platform": pid, "error": f"域名校验: {bad}"})
                        continue

                results[pid] = items
                total_items += len(items)

            if i < len(platforms) - 1:
                interval_ms = request_interval_ms + random.randint(-20, 30)
                time.sleep(max(50, interval_ms) / 1000)

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "crawl_time": datetime.now().strftime("%H:%M"),
            "platforms_fetched": len(results),
            "platforms_failed": len(failed),
            "total_items": total_items,
            "results": results,
            "id_to_name": id_to_name,
            "failed": failed,
        }

    def fetch_trending(self, platforms: Optional[List[str]] = None,
                       top_n: int = 20) -> List[Dict]:
        """获取跨平台热门趋势 — 合并多平台热榜，按热度排序"""
        platforms = platforms or FINANCE_PLATFORMS
        data = self.fetch_all(platforms)
        all_items = []
        for pid, items in data["results"].items():
            for item in items[:top_n]:
                all_items.append(item)

        # 按标题去重，合并平台
        merged: Dict[str, Dict] = {}
        for item in all_items:
            title = item["title"]
            if title in merged:
                merged[title]["platforms"].append(item["platform_name"])
                merged[title]["min_rank"] = min(merged[title]["min_rank"], item["rank"])
            else:
                merged[title] = {
                    "title": title,
                    "url": item["url"],
                    "platforms": [item["platform_name"]],
                    "min_rank": item["rank"],
                    "crawl_time": item["crawl_time"],
                }

        trending = sorted(
            merged.values(),
            key=lambda x: (len(x["platforms"]), -x["min_rank"]),
            reverse=True,
        )
        return trending

    @staticmethod
    def format_trending_for_prompt(trending: List[Dict], top_n: int = 15) -> str:
        """将热榜数据格式化为 LLM prompt 可用的文本"""
        lines = ["## 当前跨平台热门趋势（多平台热榜聚合）", ""]
        for i, item in enumerate(trending[:top_n], 1):
            platforms_str = "、".join(item["platforms"])
            lines.append(f"{i}. **{item['title']}** (热度平台: {platforms_str})")
        lines.append("")
        lines.append(f"> 数据来源：NewsNow 多平台热榜聚合，共 {len(trending)} 条趋势")
        return "\n".join(lines)
