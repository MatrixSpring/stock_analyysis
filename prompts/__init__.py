# -*- coding: utf-8 -*-
"""
Prompt 模板统一管理 — Jinja2 渲染引擎
Usage:
    from prompts import render
    text = render("stock_analysis", symbol="600519", industry="白酒", ...)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_CACHE: Dict[str, str] = {}


def _load_template(name: str) -> str:
    """从文件加载模板源码"""
    key = f"{name}"
    if key in _CACHE:
        return _CACHE[key]
    path = _TEMPLATE_DIR / f"{name}.txt"
    if path.exists():
        content = path.read_text(encoding="utf-8")
        _CACHE[key] = content
        return content
    path = _TEMPLATE_DIR / f"{name}.j2"
    if path.exists():
        content = path.read_text(encoding="utf-8")
        _CACHE[key] = content
        return content
    raise FileNotFoundError(f"Template not found: {name} (.txt or .j2)")


def render(template_name: str, **kwargs) -> str:
    """
    简易模板渲染（变量替换：{{ var_name }}）
    """
    template = _load_template(template_name)
    result = template
    for k, v in kwargs.items():
        placeholder = "{{ " + k + " }}"
        if placeholder in result:
            result = result.replace(placeholder, str(v))
        placeholder_space = "{{" + k + "}}"
        if placeholder_space in result:
            result = result.replace(placeholder_space, str(v))
    # 处理 if 块（简化版）
    return result


def list_templates() -> list:
    """列出所有可用模板"""
    templates = []
    for pattern in ("*.txt", "*.j2"):
        for p in _TEMPLATE_DIR.glob(pattern):
            templates.append(p.stem)
    return sorted(set(templates))


def render_with_jinja2(template_name: str, **kwargs) -> str:
    """使用 Jinja2 渲染（需 pip install jinja2）"""
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
        tmpl = env.get_template(f"{template_name}.j2")
        return tmpl.render(**kwargs)
    except ImportError:
        logger.warning("Jinja2 not installed, falling back to simple renderer")
        return render(template_name, **kwargs)
