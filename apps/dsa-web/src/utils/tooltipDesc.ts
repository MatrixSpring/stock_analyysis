/** 指标释义字典 — 全局悬浮 Tooltip */
const desc: Record<string, string> = {
  trendScore: '市场趋势分：0-100，数值越高代表市场整体上涨动量越强，赚钱效应越好',
  volatility: '波动率：衡量市场震荡剧烈程度，数值越高短线波动越大',
  momentum: '动量强度：代表当前趋势延续性，越高趋势越稳固',
  riskScore: '综合风险分：0-100，分数越高市场系统性风险越大',
  fundNet: '资金净流入：统计周期内主力资金净买入净额',
  fundRatio: '资金占比：当前资金在整体成交额中的占比，判断资金集中度',
  policyPower: '政策利好强度：0-10分，分数越高对行业基本面提振越强',
  policyProgress: '政策落地进度：0-100%，代表政策实际落地兑现程度',
  gameWinRate: '博弈胜率：主力资金获胜概率，越高短线上涨概率越大',
};
export default desc;
