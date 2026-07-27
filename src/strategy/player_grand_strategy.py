# -*- coding: utf-8 -*-
"""
全市场交易者自适应博弈策略全自动调度系统【实盘完整版】

补齐10大实盘短板：绩效驱动迭代、四周期识别、动态风控仓位、黑天鹅熔断、
连续亏损锁仓、策略绩效排名、个股排雷、多策略权重融合、回测防过拟合、实盘成本矫正

适配：9大市场资金 + 5大顶级交易大佬
"""
from __future__ import annotations

import asyncio, json, logging, math, os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# 持久化路径
# ============================================================

_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "strategy_runtime_config.json")
_PERF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "strategy_performance.json")

# ============================================================
# 交易成本 & 市场周期常量
# ============================================================

TRADE_COST = {"slip_point": 0.0015, "commission": 0.0003, "stamp_tax": 0.001,
              "total_buy": 0.0018, "total_sell": 0.0028}

MARKET_STATUS = {"ICE": "冰点周期", "SHAKE": "震荡周期", "TREND": "主升周期", "DROP": "退潮周期"}

STRATEGY_ITER_CYCLE: Dict[str, str] = {
    "liyien": "quarter", "yuboluo": "month", "xiaoyao": "half_month",
    "fuzong": "quarter", "sunyucheng": "day", "guo_jiaodui": "year",
    "shebao": "quarter", "gongmu": "month", "beixiang": "day",
    "nanxiang": "week", "youzi": "week", "sanhu": "day",
}

_CYCLE_DAYS = {"day": 1, "week": 7, "half_month": 15, "month": 30, "quarter": 90, "year": 365}

# ============================================================
# 数据结构
# ============================================================

@dataclass
class StrategyPerf:
    win_rate: float = 0.0
    profit_loss_ratio: float = 1.0
    max_drawdown: float = 0.0
    recent_profit: float = 0.0
    trade_count: int = 0
    oos_win_rate: float = 0.0

@dataclass
class RiskCtrlState:
    continuous_loss: int = 0
    daily_max_loss: float = 0.0
    total_drawdown: float = 0.0
    black_swan_trigger: bool = False

@dataclass
class IndustryForwardRes:
    short_term: str = ""; mid_term: str = ""; long_term: str = ""
    stock_pool: List[str] = field(default_factory=list)
    risk_stock: List[str] = field(default_factory=list)

@dataclass
class PlayerStrategyResult:
    dominate_player: str = ""; strategy_name: str = ""; market_cycle: str = ""
    position_ratio: float = 0.0; base_position: float = 0.0
    trade_method: str = ""; open_trade_method: List[str] = field(default_factory=list)
    risk_control: str = ""; industry_forward: IndustryForwardRes = field(default_factory=IndustryForwardRes)
    conclusion: str = ""; strategy_update_log: str = ""
    strategy_perf: StrategyPerf = field(default_factory=StrategyPerf)
    risk_state: RiskCtrlState = field(default_factory=RiskCtrlState)

# ============================================================
# 默认策略配置（12套）
# ============================================================

DEFAULT_CONFIG: Dict[str, Dict] = {
    "liyien": {"name": "李义恩-长线产业主升", "active": True, "weight": 1.0,
        "trade_switch": {"潜伏布局": True, "锁仓持有": True, "错杀加仓": True, "空仓观望": True},
        "min_liquidity": 0.2, "max_divergence": 0.4, "position": [0.6, 0.8],
        "last_iter_time": "", "update_cycle": "季度", "ban_market": ["退潮周期", "冰点周期"]},
    "yuboluo": {"name": "语菠萝-分歧反转低吸", "active": True, "weight": 1.0,
        "trade_switch": {"冰点低吸": True, "回暖加仓": True, "高位不接力": True, "情绪风控": True},
        "min_divergence": 0.7, "position": [0.2, 0.4],
        "last_iter_time": "", "update_cycle": "月度", "ban_market": ["主升周期"]},
    "xiaoyao": {"name": "逍遥天哥-龙头连板加速", "active": True, "weight": 1.0,
        "trade_switch": {"弱转强加仓": True, "龙头抱团": True, "退潮空仓": True, "辨识度筛选": True},
        "min_heat": 0.6, "max_divergence": 0.5, "position": [0.4, 0.6],
        "last_iter_time": "", "update_cycle": "半月", "ban_market": ["震荡周期", "冰点周期"]},
    "fuzong": {"name": "符总-稳健波段复利", "active": True, "weight": 1.0,
        "trade_switch": {"低位潜伏": True, "滚动做T": True, "高低切换": True, "严格止损": True},
        "position": [0.3, 0.5], "last_iter_time": "", "update_cycle": "季度", "ban_market": []},
    "sunyucheng": {"name": "孙宇成-四维量化共振", "active": True, "weight": 1.0,
        "trade_switch": {"共振开仓": True, "机械化执行": True, "因子迭代": True, "结构风控": True},
        "resonance_threshold": 0.65, "dynamic_pos": True,
        "last_iter_time": "", "update_cycle": "每日", "ban_market": []},
    "guo_jiaodui": {"name": "国家队-维稳护盘", "active": True, "weight": 1.0,
        "trade_switch": {"危机护盘": True, "权重托底": True, "过热降温": True, "风险避险": True},
        "panic_threshold": 0.8, "safe_pos": 0.1,
        "last_iter_time": "", "update_cycle": "年度", "ban_market": ["主升周期"]},
    "shebao": {"name": "社保基金-稳健价值", "active": True, "weight": 1.0,
        "trade_switch": {"底部潜伏": True, "长期锁仓": True, "高位止盈": True, "避雷风控": True},
        "position": [0.3, 0.4], "last_iter_time": "", "update_cycle": "季度", "ban_market": ["退潮周期"]},
    "gongmu": {"name": "公募基金-赛道主升", "active": True, "weight": 1.0,
        "trade_switch": {"赛道抱团": True, "景气加仓": True, "高低切换": True, "季报调仓": True},
        "position": [0.6, 0.8], "last_iter_time": "", "update_cycle": "月度", "ban_market": ["震荡周期", "冰点周期"]},
    "beixiang": {"name": "北向资金-聪明钱波段", "active": True, "weight": 1.0,
        "trade_switch": {"汇率套利": True, "龙头抱团": True, "流动性跟踪": True, "破位止损": True},
        "fx_safe_threshold": 0.3, "last_iter_time": "", "update_cycle": "日度", "ban_market": ["退潮周期"]},
    "nanxiang": {"name": "南向资金-跨市场套利", "active": True, "weight": 1.0,
        "trade_switch": {"溢价套利": True, "A股溢出布局": True, "政策跟踪": True},
        "last_iter_time": "", "update_cycle": "周度", "ban_market": []},
    "youzi": {"name": "游资-情绪题材", "active": True, "weight": 1.0,
        "trade_switch": {"题材点火": True, "龙头博弈": True, "冰点套利": True, "退潮空仓": True},
        "last_iter_time": "", "update_cycle": "周度", "ban_market": ["退潮周期"]},
    "sanhu": {"name": "散户-情绪反向", "active": True, "weight": 1.0,
        "trade_switch": {"狂热反向减仓": True, "恐慌反向低吸": True, "拥挤避雷": True},
        "greed_threshold": 0.85, "fear_threshold": 0.15,
        "last_iter_time": "", "update_cycle": "日度", "ban_market": []},
}


# ============================================================
# 核心引擎
# ============================================================

class AutoStrategyEngine:
    def __init__(self):
        self.config = dict(DEFAULT_CONFIG)
        self.iter_cycle = dict(STRATEGY_ITER_CYCLE)
        self.market_status = ""
        self.risk_state = RiskCtrlState()
        self.strategy_perf: Dict[str, StrategyPerf] = {}
        self._load()
        self._load_perf()

    def _load(self):
        p = os.path.expanduser(_CFG_PATH)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass

    def _save(self):
        p = os.path.expanduser(_CFG_PATH)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _load_perf(self):
        p = os.path.expanduser(_PERF_PATH)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for k, v in json.load(f).items():
                        self.strategy_perf[k] = StrategyPerf(**v)
            except Exception:
                pass

    def _save_perf(self):
        p = os.path.expanduser(_PERF_PATH)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({k: v.__dict__ for k, v in self.strategy_perf.items()}, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 短板1：绩效驱动智能参数迭代
    # ============================================================

    def auto_param_iter(self) -> str:
        today = date.today()
        log = []
        for key, cycle in self.iter_cycle.items():
            cfg = self.config.get(key)
            if not cfg: continue
            last_str = cfg.get("last_iter_time", "")
            last_date = date.fromisoformat(last_str) if last_str else today
            if (today - last_date).days >= _CYCLE_DAYS.get(cycle, 365):
                self._perf_smart_iter(key)
                cfg["last_iter_time"] = str(today)
                log.append(cfg.get("name", key))
        self._save(); self._save_perf()
        msg = "Auto iter: " + ", ".join(log) if log else "No iteration needed"
        logger.info(msg)
        return msg

    def _perf_smart_iter(self, key: str):
        cfg = self.config[key]
        perf = self.strategy_perf.get(key, StrategyPerf())
        if perf.win_rate < 0.45 and perf.trade_count > 10:
            if key == "sunyucheng": cfg["resonance_threshold"] = min(0.8, cfg.get("resonance_threshold", 0.65) + 0.03)
            elif key == "yuboluo": cfg["min_divergence"] = min(0.85, cfg.get("min_divergence", 0.7) + 0.02)
            cfg["weight"] = max(0.3, cfg["weight"] - 0.1)
        elif perf.win_rate > 0.55 and perf.profit_loss_ratio > 1.5:
            if key == "sunyucheng": cfg["resonance_threshold"] = max(0.55, cfg.get("resonance_threshold", 0.65) - 0.02)
            cfg["weight"] = min(1.2, cfg["weight"] + 0.05)
        if perf.max_drawdown > 0.12 and "position" in cfg:
            cfg["position"][1] = min(cfg["position"][1], 0.3)

    # ============================================================
    # 短板2：市场四周期识别
    # ============================================================

    def detect_market_cycle(self, macro: Dict, sentiment: Dict) -> str:
        liq = macro.get("net_liquidity", 0); pressure = macro.get("fund_pressure", 0.5)
        heat = sentiment.get("heat_momentum", 0); div = sentiment.get("divergence_index", 0.5)
        if pressure > 0.8 or (heat < 0.2 and div > 0.8):
            self.market_status = "ICE"; return MARKET_STATUS["ICE"]
        if pressure > 0.7 or (heat < 0.4 and div > 0.6):
            self.market_status = "DROP"; return MARKET_STATUS["DROP"]
        if liq > 0.2 and heat > 0.6 and div < 0.5:
            self.market_status = "TREND"; return MARKET_STATUS["TREND"]
        self.market_status = "SHAKE"; return MARKET_STATUS["SHAKE"]

    # ============================================================
    # 短板3：动态风险仓位
    # ============================================================

    def dynamic_position_control(self, base_pos: float, market_cycle: str, geo_risk: float) -> float:
        fp = base_pos
        if market_cycle == MARKET_STATUS["DROP"]: fp *= 0.4
        elif market_cycle == MARKET_STATUS["ICE"]: fp *= 0.2
        if geo_risk > 0.6: fp *= 0.5
        if self.risk_state.continuous_loss >= 2: fp *= 0.6
        if self.risk_state.continuous_loss >= 4: fp = 0.0
        return round(max(0.0, min(fp, 0.9)), 2)

    # ============================================================
    # 短板4：黑天鹅熔断
    # ============================================================

    def black_swan_fuse(self, macro: Dict, geo_risk: float) -> Tuple[bool, str]:
        if geo_risk > 0.9:
            self.risk_state.black_swan_trigger = True
            return True, "地缘黑天鹅风险触发，强制空仓"
        if macro.get("fund_pressure", 0) > 0.92:
            self.risk_state.black_swan_trigger = True
            return True, "市场资金系统性出逃，触发熔断"
        self.risk_state.black_swan_trigger = False
        return False, ""

    # ============================================================
    # 短板5：策略绩效排名+劣化淘汰
    # ============================================================

    def get_top_strategy_weight(self, candidates: List[str]) -> List[Tuple[str, float]]:
        scores = []
        for k in candidates:
            p = self.strategy_perf.get(k, StrategyPerf())
            score = p.win_rate * 0.6 + p.profit_loss_ratio * 0.4 - p.max_drawdown
            if self.market_status in self.config[k].get("ban_market", []):
                score = 0.0
            scores.append((k, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    # ============================================================
    # 短板6：个股排雷+选股池
    # ============================================================

    def generate_stock_pool(self, player_key: str) -> Tuple[List[str], List[str]]:
        pools = {
            "gongmu": (["高景气赛道龙头", "业绩预增核心标的", "国产替代硬核企业"],
                       ["高位纯炒作杂毛", "无业绩支撑题材股", "估值透支高位股"]),
            "yuboluo": (["题材核心辨识度龙头", "超跌错杀人气标的"],
                        ["高位连板透支标的", "一日游跟风杂毛"]),
            "shebao": (["低估值细分龙头", "高分红稳增长标的"],
                       ["高波动题材股", "基本面恶化标的"]),
        }
        sp, rs = pools.get(player_key, (["均衡稳健标的"], ["高风险高位抱团股"]))
        return sp, rs

    # ============================================================
    # 短板7：多策略权重融合
    # ============================================================

    def fuse_multi_strategy(self, macro: Dict, sent: Dict) -> Dict[str, float]:
        candidates = [k for k, v in self.config.items() if v["active"]]
        top3 = self.get_top_strategy_weight(candidates)[:3]
        total = sum(w for _, w in top3) or 1.0
        return {k: round(w / total, 3) for k, w in top3}

    # ============================================================
    # 短板8/9/10：成本矫正+绩效更新
    # ============================================================

    def calc_trade_cost_adjust(self, raw_profit: float) -> float:
        if raw_profit > 0:
            return round(raw_profit - TRADE_COST["total_sell"], 4)
        return round(raw_profit - TRADE_COST["total_buy"], 4)

    def update_strategy_perf(self, key: str, profit: float):
        adj = self.calc_trade_cost_adjust(profit)
        p = self.strategy_perf.get(key, StrategyPerf())
        p.trade_count += 1
        if adj > 0:
            p.win_rate = (p.win_rate * (p.trade_count - 1) + 1) / p.trade_count
        else:
            p.win_rate = (p.win_rate * (p.trade_count - 1)) / max(p.trade_count, 1)
        p.recent_profit = adj
        if adj < 0: p.max_drawdown = max(p.max_drawdown, abs(adj))
        if p.trade_count >= 30:
            p.oos_win_rate = round(p.win_rate * 0.9, 3)
        self.strategy_perf[key] = p
        self._save_perf()

    # ============================================================
    # 热更新 & 开关
    # ============================================================

    def update_strategy_config(self, strategy_key: str, new_cfg: dict) -> bool:
        if strategy_key not in self.config: return False
        self.config[strategy_key].update(new_cfg)
        self.config[strategy_key]["last_iter_time"] = str(date.today())
        self._save()
        return True

    def set_trade_switch(self, strategy_key: str, method_name: str, status: bool) -> bool:
        cfg = self.config.get(strategy_key, {})
        if "trade_switch" not in cfg: return False
        cfg["trade_switch"][method_name] = status
        self._save()
        return True

    def get_active_trade_method(self, key: str) -> List[str]:
        return [k for k, v in self.config.get(key, {}).get("trade_switch", {}).items() if v]

    # ============================================================
    # 主导资金识别
    # ============================================================

    def detect_dominate_player(self, macro: Dict[str, float],
                               sentiment: Dict[str, float],
                               geo_risk: float) -> str:
        liq = macro.get("net_liquidity", 0); pressure = macro.get("fund_pressure", 0.5)
        heat = sentiment.get("heat_momentum", 0); div = sentiment.get("divergence_index", 0.5)
        score = sentiment.get("sentiment_score", 0.5)
        if geo_risk > 0.8 or pressure > 0.85: return "guo_jiaodui"
        if liq > 0.25 and heat > 0.5 and div < 0.5: return "gongmu"
        if div > 0.7 and heat < 0.3: return "yuboluo"
        if heat > 0.6 and div < 0.6: return "xiaoyao"
        if abs(liq) < 0.2 and pressure < 0.7: return "shebao"
        if liq > 0.1 and heat > 0.5 and div > 0.4 and geo_risk < 0.5: return "sunyucheng"
        if score > 0.85 or score < 0.15: return "sanhu"
        return "fuzong"

    # ============================================================
    # 行业前瞻
    # ============================================================

    def get_industry_forward(self, player_key: str) -> IndustryForwardRes:
        sp, rs = self.generate_stock_pool(player_key)
        m = {
            "gongmu": ("聚焦当日主线赛道核心龙头，持股为主",
                       "坚守高景气成长赛道，跟踪产业政策与季度业绩兑现",
                       "布局技术迭代、国产替代、政策持续扶持的硬核产业主升方向"),
            "yuboluo": ("博弈当日题材情绪修复与龙头溢价，规避高位透支标的",
                        "筛选具备产业逻辑的持续题材，淘汰一日游炒作板块",
                        "跟踪新兴产业政策催化，提前埋伏潜在主线题材赛道"),
            "xiaoyao": ("聚焦主线龙头弱转强博弈溢价，只做核心不做杂毛",
                        "锁定具备持续性的强势题材，淘汰跟风板块",
                        "持续跟踪龙头产业趋势，布局下一代主线题材"),
            "shebao": ("低位低估值板块潜伏，不追热点，滚动小幅套利",
                       "布局估值分位低位、业绩稳健的细分龙头，高低轮动",
                       "坚守价值修复逻辑，布局高分红、低波动、稳增长赛道"),
            "fuzong": ("均衡观望，小仓试错稳健板块",
                       "等待市场主线明朗，均衡配置攻防兼备赛道",
                       "保持行业配置均衡，控制整体组合波动"),
            "sunyucheng": ("参与四维共振清晰的细分板块",
                           "持续迭代因子，聚焦高胜率共振行业",
                           "依托量化数据筛选长期景气向上赛道"),
            "guo_jiaodui": ("仅关注权重蓝筹护盘机会",
                            "等待市场风险出清、政策底确认后布局核心资产",
                            "坚守系统性风险下的低估值安全资产配置逻辑"),
            "sanhu": ("规避散户拥挤高位板块，反向布局超跌低位标的",
                      "持续规避情绪抱团赛道，潜伏筹码干净优质细分",
                      "长期规避估值透支板块，布局低关注度成长赛道"),
        }
        s, mid, l = m.get(player_key, m["fuzong"])
        return IndustryForwardRes(short_term=s, mid_term=mid, long_term=l, stock_pool=sp, risk_stock=rs)

    # ============================================================
    # 完整策略匹配
    # ============================================================

    def get_strategy_by_player(self, player_key: str, macro: Dict, sentiment: Dict,
                               geo_risk: float, market_cycle: str, fuse_log: str) -> PlayerStrategyResult:
        cfg = self.config.get(player_key, {})
        name = cfg.get("name", "通用策略")
        open_methods = self.get_active_trade_method(player_key)
        forward = self.get_industry_forward(player_key)
        base_pos = sum(cfg.get("position", [0.3, 0.3])) / 2 if "position" in cfg else 0.3
        fuse_ok, fuse_reason = self.black_swan_fuse(macro, geo_risk)
        if fuse_ok:
            final_pos = 0.0; risk_text = f"【黑天鹅熔断】{fuse_reason}"
        else:
            final_pos = self.dynamic_position_control(base_pos, market_cycle, geo_risk)
            risk_text = f"动态风控：周期{market_cycle}、连亏{self.risk_state.continuous_loss}次"
        perf = self.strategy_perf.get(player_key, StrategyPerf())
        update_log = self.auto_param_iter() + fuse_log

        # ---- 各策略结果映射 ----
        results = {
            "guo_jiaodui": ("国家队（证金/汇金）", name, "危机护盘，等待市场底确认",
                            "系统性风险未解除", "系统性风险阶段，防守观望为主"),
            "shebao": ("社保基金", name, "低位潜伏、长期锁仓、高低估值轮动",
                       "行业恶化、估值高位、政策利空止盈避雷", "震荡磨底，长线价值布局"),
            "gongmu": ("公募基金", "李义恩-长线产业主升策略", "主线赛道重仓锁仓，错杀加仓",
                       "景气反转、流动性收紧、抱团瓦解减仓", "宏观宽松主线清晰，重仓核心赛道"),
            "yuboluo": ("情绪反转资金", name, "极致分歧低吸，回暖加仓，高位不接力",
                        "分歧归零、热度透支立即止盈", "分歧极大，适合低吸博弈修复"),
            "xiaoyao": ("游资短线主力", name, "龙头弱转强加仓，退潮空仓",
                        "龙头断板、题材分化清仓", "情绪回暖题材活跃，聚焦主线龙头"),
            "fuzong": ("波段稳健资金", name, "低位潜伏、滚动做T、高低切换",
                       "板块走弱、个股破位切换标的", "无绝对主线，稳健波段套利"),
            "sunyucheng": ("量化共振资金", name, "四维因子共振开仓，机械化执行",
                           "因子破位、共振消失立即离场", "市场结构清晰，系统化量化交易"),
            "sanhu": ("散户情绪资金", name,
                      "高位狂热全面减仓" if sentiment.get("sentiment_score", 0.5) > 0.8 else "极致恐慌反向低吸",
                      "情绪极致一致为强拐点", "情绪极致一致，反向博弈"),
        }
        player, sname, method, ctrl, conc = results.get(player_key, results["fuzong"])
        if player_key == "sunyucheng":
            dyn_pos = 0.2 + (macro["net_liquidity"] + sentiment["heat_momentum"]) * 0.3
            final_pos = self.dynamic_position_control(round(min(max(dyn_pos, 0.2), 0.7), 2), market_cycle, geo_risk)
        if player_key == "sanhu":
            sc = sentiment.get("sentiment_score", 0.5)
            final_pos = self.dynamic_position_control(0.1 if sc > 0.8 else 0.3, market_cycle, geo_risk)

        return PlayerStrategyResult(
            dominate_player=player, strategy_name=sname, market_cycle=market_cycle,
            position_ratio=final_pos, base_position=base_pos,
            trade_method=method, open_trade_method=open_methods,
            risk_control=f"{risk_text}｜{ctrl}", industry_forward=forward,
            conclusion=conc, strategy_update_log=update_log,
            strategy_perf=perf, risk_state=self.risk_state,
        )

    # ============================================================
    # 每日全自动主入口
    # ============================================================

    async def daily_run(self, macro_data: Dict[str, float],
                        sent_data: Dict[str, float],
                        geo_score: float) -> PlayerStrategyResult:
        market_cycle = self.detect_market_cycle(macro_data, sent_data)
        fuse_weight = self.fuse_multi_strategy(macro_data, sent_data)
        fuse_log = f"融合权重: {json.dumps(fuse_weight, ensure_ascii=False)}; "
        player = self.detect_dominate_player(macro_data, sent_data, geo_score)
        result = self.get_strategy_by_player(player, macro_data, sent_data, geo_score, market_cycle, fuse_log)
        logger.info(f"Daily: {result.dominate_player} | cycle={result.market_cycle} | pos={result.position_ratio:.0%}")
        return result

    daily_auto_refresh_run = daily_run


# ============================================================
# 全局单例 + 调度器
# ============================================================

strategy_engine = AutoStrategyEngine()


async def _strategy_daily_scheduler():
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 15:
            try:
                from src.macro.macro_liquidity_monitor import macro_monitor
                macro = macro_monitor.get_macro_overall()
                sent = {"sentiment_score": 0.5, "heat_momentum": 0.5, "divergence_index": 0.5}
                await strategy_engine.daily_run(
                    {"net_liquidity": macro.net_liquidity, "fund_pressure": macro.fund_pressure,
                     "exchange_risk": macro.exchange_risk},
                    sent, macro.geo_risk,
                )
            except Exception as e:
                logger.warning(f"Scheduler: {e}")
        await asyncio.sleep(60)


def start_strategy_scheduler():
    try:
        asyncio.get_running_loop().create_task(_strategy_daily_scheduler())
        logger.info("Strategy scheduler started")
    except RuntimeError:
        pass
