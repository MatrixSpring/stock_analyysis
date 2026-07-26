# -*- coding: utf-8 -*-
"""
行业景气度打分 + 产业链上下游分析（对标 Seeking Alpha）

实现板块轮动、行业强弱、产业链传导、政策催化研判
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 产业链知识库
# ============================================================

_INDUSTRY_CHAIN_LIBRARY: Dict[str, Dict[str, Any]] = {
    "半导体": {
        "upstream": "光刻胶、硅片、电子特气、半导体设备(刻蚀/薄膜/检测)",
        "midstream": "芯片设计(EDA/IP)、晶圆制造、封装测试",
        "downstream": "消费电子、AI服务器、汽车电子、通信基站、物联网",
        "key_drivers": ["AI算力需求", "国产替代", "先进制程突破", "消费电子周期"],
        "key_risks": ["美国制裁升级", "产能过剩", "技术壁垒", "下游需求疲软"],
    },
    "新能源": {
        "upstream": "锂矿、钴矿、稀土、多晶硅、光伏玻璃",
        "midstream": "动力电池(正极/负极/隔膜/电解液)、光伏组件、风电整机",
        "downstream": "新能源车、储能电站、光伏电站、充电桩、氢能",
        "key_drivers": ["碳中和政策", "技术降本", "出口高增", "储能需求爆发"],
        "key_risks": ["产能过剩", "补贴退坡", "原材料波动", "贸易壁垒"],
    },
    "人工智能": {
        "upstream": "GPU/TPU芯片、光模块(800G/1.6T)、HBM存储、服务器",
        "midstream": "大模型训练/推理、AI应用(SaaS)、数据中心、云计算",
        "downstream": "金融AI、医疗AI、自动驾驶、智能制造、教育AI",
        "key_drivers": ["大模型迭代", "算力基建投资", "企业AI化转型", "政策支持"],
        "key_risks": ["芯片管制", "估值泡沫", "监管趋严", "商业化不及预期"],
    },
    "券商金融": {
        "upstream": "资本市场改革政策、货币政策、监管框架",
        "midstream": "券商(经纪/投行/资管)、银行(信贷/理财)、保险(寿险/财险)",
        "downstream": "企业融资(IPO/增发/债券)、居民理财、机构投资",
        "key_drivers": ["市场成交量", "IPO节奏", "财富管理转型", "降息周期"],
        "key_risks": ["成交量萎缩", "信用风险", "监管收紧", "利差收窄"],
    },
    "消费": {
        "upstream": "农产品(粮油/畜牧)、食品原料、包装材料",
        "midstream": "食品饮料加工、家电制造、纺织服装、日化用品",
        "downstream": "电商零售、商超便利店、餐饮连锁、出口贸易",
        "key_drivers": ["消费复苏", "品牌升级", "渠道变革", "下沉市场"],
        "key_risks": ["消费降级", "原材料涨价", "竞争加剧", "人口结构变化"],
    },
    "医药": {
        "upstream": "原料药/中间体、化工辅料、生物试剂",
        "midstream": "创新药研发、仿制药、医疗器械(影像/体外诊断)、CXO外包",
        "downstream": "医院/诊所、连锁药房、体检中心、互联网医疗",
        "key_drivers": ["创新药出海", "老龄化需求", "集采边际改善", "医疗器械国产化"],
        "key_risks": ["集采降价", "研发失败", "FDA审批", "医保控费"],
    },
    "军工": {
        "upstream": "高温合金、钛合金、碳纤维、特种芯片",
        "midstream": "航空航天(大飞机/卫星)、舰船、兵器、电子对抗",
        "downstream": "国防装备列装、军贸出口、军民融合",
        "key_drivers": ["国防预算增长", "装备更新换代", "地缘紧张", "军民融合"],
        "key_risks": ["订单波动", "技术封锁", "军品定价", "交付周期"],
    },
    "电力": {
        "upstream": "煤炭、天然气、铀矿、水风光资源",
        "midstream": "火电、水电、核电、风电、光伏发电",
        "downstream": "工业用电、居民用电、电动车充电、数据中心供电",
        "key_drivers": ["电价改革", "新能源转型", "AI算力用电", "容量电价"],
        "key_risks": ["煤价波动", "弃风弃光", "电力过剩", "政策调整"],
    },
    "光伏": {
        "upstream": "硅料、硅片、银浆、光伏玻璃、逆变器元器件",
        "midstream": "电池片(PERC/TOPCon/HJT)、组件、逆变器、支架",
        "downstream": "集中式光伏电站、分布式光伏、BIPV、储能配套",
        "key_drivers": ["碳中和目标", "组件降价", "海外出口", "分布式爆发"],
        "key_risks": ["产能过剩", "贸易壁垒", "技术迭代", "电网消纳"],
    },
    "锂电": {
        "upstream": "锂矿(盐湖/锂辉石)、钴镍、电解液(六氟磷酸锂)、隔膜、正极/负极材料",
        "midstream": "动力电池(方形/圆柱/软包)、储能电池、电池回收",
        "downstream": "新能源车企、储能电站、电动工具、两轮电动车",
        "key_drivers": ["电动车渗透率", "储能需求爆发", "材料降价", "固态电池突破"],
        "key_risks": ["锂价波动", "产能过剩", "钠电池替代", "车企自研电池"],
    },
    "地产基建": {
        "upstream": "水泥、钢材、玻璃、防水材料、管材",
        "midstream": "房地产开发、基建工程、建筑装饰、物业运营",
        "downstream": "城市建设更新、保障性住房、轨道交通、水利工程",
        "key_drivers": ["政策松绑", "城中村改造", "利率下行", "基建投资"],
        "key_risks": ["销售下滑", "债务风险", "交付不确定性", "人口下行"],
    },
}


class IndustryChainAnalyzer:
    """行业景气度 + 产业链分析器。

    使用方式：
        analyzer = IndustryChainAnalyzer()
        result = analyzer.analyze(
            industry="半导体",
            policy_level="强力扶持",
            fund_heat="持续流入",
            profit_growth=25.0,
        )
    """

    # 政策等级 → 得分
    POLICY_SCORE = {
        "强力扶持": 95,
        "温和利好": 72,
        "中性": 50,
        "偏空": 30,
        "利空压制": 10,
    }

    # 资金热度 → 得分
    FUND_HEAT_SCORE = {
        "抱团热门": 92,
        "持续流入": 75,
        "震荡存量": 50,
        "资金流出": 28,
        "大幅撤离": 8,
    }

    def __init__(self):
        self._chain_lib = _INDUSTRY_CHAIN_LIBRARY

    # ============================================================
    # 景气度计算
    # ============================================================

    def calc_boom_score(
        self,
        policy_score: float,
        fund_score: float,
        profit_score: float,
        w_policy: float = 0.35,
        w_fund: float = 0.40,
        w_profit: float = 0.25,
    ) -> float:
        """加权行业景气综合得分。

        Args:
            policy_score: 政策面得分 0-100
            fund_score: 资金面得分 0-100
            profit_score: 盈利面得分 0-100
        """
        total = policy_score * w_policy + fund_score * w_fund + profit_score * w_profit
        return round(max(0, min(100, total)), 2)

    def get_profit_score(self, profit_growth: float) -> float:
        """利润增速 → 0-100 得分"""
        if profit_growth > 50:
            return 95.0
        elif profit_growth > 25:
            return 80.0
        elif profit_growth > 10:
            return 65.0
        elif profit_growth > 0:
            return 55.0
        elif profit_growth > -10:
            return 40.0
        else:
            return 20.0

    # ============================================================
    # 产业链信息
    # ============================================================

    def get_chain_info(self, industry: str) -> Dict[str, Any]:
        """获取行业产业链上下游信息。

        Returns:
            {upstream, midstream, downstream, key_drivers, key_risks}
            未知行业返回通用描述
        """
        return self._chain_lib.get(
            industry,
            {
                "upstream": f"{industry}行业上游（原材料、核心零部件、能源供应）",
                "midstream": f"{industry}行业中游（生产制造、技术研发、平台运营）",
                "downstream": f"{industry}行业下游（终端消费、应用场景、出口渠道）",
                "key_drivers": ["政策催化", "技术创新", "需求增长", "国产替代"],
                "key_risks": ["政策风险", "市场竞争", "技术迭代", "成本上升"],
            },
        )

    def get_chain_text(self, industry: str) -> str:
        """产业链文本描述"""
        chain = self.get_chain_info(industry)
        return (
            f"上游：{chain['upstream']}\n"
            f"中游：{chain['midstream']}\n"
            f"下游：{chain['downstream']}"
        )

    # ============================================================
    # 综合研判
    # ============================================================

    def rank(self, boom_score: float) -> str:
        """景气度 → 配置建议"""
        if boom_score >= 80:
            return "行业高度景气，优先配置，可作为核心赛道"
        elif boom_score >= 65:
            return "行业景气上行，积极布局，精选龙头个股"
        elif boom_score >= 45:
            return "行业震荡分化，结构性机会为主，波段操作"
        elif boom_score >= 30:
            return "行业景气偏弱，控制仓位，仅参与确定性机会"
        else:
            return "行业低迷不振，规避为主，耐心等待右侧信号"

    def analyze(
        self,
        industry: str,
        policy_level: str = "中性",
        fund_heat: str = "震荡存量",
        profit_growth: float = 0.0,
    ) -> Dict[str, Any]:
        """完整行业景气度分析。

        Args:
            industry: 行业名（如 "半导体", "新能源", "人工智能"）
            policy_level: 政策等级
            fund_heat: 资金热度
            profit_growth: 行业利润增速 %

        Returns:
            {industry_name, boom_score, policy_level, fund_heat,
             profit_growth, chain_info, rank_desc, key_drivers, key_risks}
        """
        p_score = self.POLICY_SCORE.get(policy_level, 50)
        f_score = self.FUND_HEAT_SCORE.get(fund_heat, 50)
        profit_score = self.get_profit_score(profit_growth)

        boom = self.calc_boom_score(p_score, f_score, profit_score)
        chain = self.get_chain_info(industry)
        rank_desc = self.rank(boom)

        result = {
            "industry_name": industry,
            "boom_score": boom,
            "policy_level": policy_level,
            "policy_score": p_score,
            "fund_heat": fund_heat,
            "fund_score": f_score,
            "profit_growth": profit_growth,
            "profit_score": profit_score,
            "upstream": chain["upstream"],
            "midstream": chain["midstream"],
            "downstream": chain["downstream"],
            "chain_text": (
                f"上游：{chain['upstream']}\n"
                f"中游：{chain['midstream']}\n"
                f"下游：{chain['downstream']}"
            ),
            "key_drivers": chain["key_drivers"],
            "key_risks": chain["key_risks"],
            "rank_desc": rank_desc,
        }

        logger.info(
            f"[IndustryChain] {industry}: 景气度={boom}, "
            f"政策={policy_level}({p_score}), "
            f"资金={fund_heat}({f_score}), "
            f"利润增速={profit_growth}%"
        )

        return result

    def batch_analyze(
        self, industries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量分析多个行业并排名。

        Args:
            industries: [{"industry": "半导体", "policy_level": "温和利好",
                          "fund_heat": "持续流入", "profit_growth": 25.0}]

        Returns:
            按景气度降序排列的分析结果
        """
        results = []
        for item in industries:
            try:
                r = self.analyze(
                    industry=item.get("industry", "未知行业"),
                    policy_level=item.get("policy_level", "中性"),
                    fund_heat=item.get("fund_heat", "震荡存量"),
                    profit_growth=float(item.get("profit_growth", 0)),
                )
                results.append(r)
            except Exception as e:
                logger.warning(f"[IndustryChain] 分析失败: {item.get('industry')}: {e}")

        results.sort(key=lambda x: x["boom_score"], reverse=True)
        return results

    # ============================================================
    # 行业对标／轮动
    # ============================================================

    def compare_industries(
        self, analyses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """行业横向对比，找出最景气/最弱势行业"""
        if not analyses:
            return {"top": None, "bottom": None, "ranking": []}

        sorted_list = sorted(analyses, key=lambda x: x["boom_score"], reverse=True)
        return {
            "top_industry": sorted_list[0]["industry_name"],
            "top_score": sorted_list[0]["boom_score"],
            "bottom_industry": sorted_list[-1]["industry_name"],
            "bottom_score": sorted_list[-1]["boom_score"],
            "ranking": [
                {
                    "name": a["industry_name"],
                    "score": a["boom_score"],
                    "rank": a["rank_desc"],
                }
                for a in sorted_list
            ],
        }


# ============================================================
# 全局实例
# ============================================================

industry_analyzer = IndustryChainAnalyzer()
