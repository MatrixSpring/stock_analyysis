# -*- coding: utf-8 -*-
"""
Prompt 加载器 — 统一管理所有 Prompt 模板，支持版本切换

Usage:
    from src.prompt_loader import prompt_loader
    text = prompt_loader.render("stock_analysis", symbol="600519", ...)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts" / "templates"
_CACHE: Dict[str, str] = {}
_VERSION = "v2.0"


class PromptLoader:
    """Prompt 统一加载器"""

    def __init__(self, template_dir: Optional[Path] = None):
        self._dir = template_dir or PROMPT_DIR
        self._cache: Dict[str, str] = {}
        self.version = _VERSION

    def load(self, name: str, version: Optional[str] = None) -> str:
        """加载模板源码"""
        key = f"{name}:{version or self.version}"
        if key in self._cache:
            return self._cache[key]

        # 尝试版本化文件名
        if version:
            path = self._dir / f"{name}_{version}.txt"
            if path.exists():
                content = path.read_text(encoding="utf-8")
                self._cache[key] = content
                return content

        # 默认文件名
        for ext in (".txt", ".j2"):
            path = self._dir / f"{name}{ext}"
            if path.exists():
                content = path.read_text(encoding="utf-8")
                self._cache[key] = content
                return content

        raise FileNotFoundError(f"Template '{name}' not found in {self._dir}")

    def render(self, template_name: str, **kwargs) -> str:
        """渲染模板（简单变量替换）"""
        template = self.load(template_name)
        result = template
        for k, v in kwargs.items():
            result = result.replace("{{ " + k + " }}", str(v))
            result = result.replace("{{" + k + "}}", str(v))
        return result

    def render_jinja2(self, name: str, **kwargs) -> str:
        """Jinja2 渲染（需安装 jinja2）"""
        try:
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader(str(self._dir)))
            tmpl = env.get_template(f"{name}.j2" if not name.endswith(".j2") else name)
            return tmpl.render(**kwargs)
        except ImportError:
            return self.render(name, **kwargs)

    def list_templates(self) -> List[str]:
        templates = []
        for p in self._dir.glob("*.txt"):
            templates.append(p.stem)
        for p in self._dir.glob("*.j2"):
            templates.append(p.stem)
        return sorted(set(templates))

    def get_template_info(self, name: str) -> Dict[str, Any]:
        try:
            content = self.load(name)
            return {
                "name": name, "version": self.version,
                "size": len(content), "lines": content.count("\n") + 1,
            }
        except FileNotFoundError:
            return {"name": name, "exists": False}


# 全局单例
prompt_loader = PromptLoader()


def render_prompt(name: str, **kwargs) -> str:
    return prompt_loader.render(name, **kwargs)
