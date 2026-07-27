/**
 * DSA 五大核心模块导航配置
 * 图标使用 lucide-react (项目已安装)
 */
import {
  LayoutDashboard, Brain, ShieldCheck, FileText, Settings,
  Gauge, Sliders, ToggleLeft, GitMerge,
  AlertTriangle, TrendingUp, DollarSign,
  FileBadge, TrendingDown, ListFilter,
  Clock, Plug, ScrollText,
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: any;
  children?: NavItem[];
}

export const NAV_ITEMS: NavItem[] = [
  {
    id: 'dashboard', label: '数据总览仪表盘', path: '/dashboard', icon: LayoutDashboard,
  },
  {
    id: 'strategy', label: '智能策略管理中心', path: '/strategy', icon: Brain,
    children: [
      { id: 'strategy-overview', label: '策略总览看板', path: '/strategy/overview', icon: Gauge },
      { id: 'strategy-config', label: '单策略精细化配置', path: '/strategy/config', icon: Sliders },
      { id: 'strategy-switches', label: '博弈手段开关管理', path: '/strategy/switches', icon: ToggleLeft },
      { id: 'strategy-fusion', label: '多策略权重融合', path: '/strategy/fusion', icon: GitMerge },
    ],
  },
  {
    id: 'risk', label: '风控与绩效监控', path: '/risk', icon: ShieldCheck,
    children: [
      { id: 'risk-monitor', label: '实时风控状态监控', path: '/risk/monitor', icon: AlertTriangle },
      { id: 'risk-performance', label: '策略绩效数据报表', path: '/risk/performance', icon: TrendingUp },
      { id: 'risk-cost', label: '交易成本参数配置', path: '/risk/cost', icon: DollarSign },
    ],
  },
  {
    id: 'research', label: '投研报告输出中心', path: '/research', icon: FileText,
    children: [
      { id: 'research-daily', label: '每日自动策略报告', path: '/research/daily', icon: FileBadge },
      { id: 'research-industry', label: '分层行业前瞻分析', path: '/research/industry', icon: TrendingDown },
      { id: 'research-stocks', label: '个股池与避雷管理', path: '/research/stocks', icon: ListFilter },
    ],
  },
  {
    id: 'ops', label: '系统运维与配置', path: '/ops', icon: Settings,
    children: [
      { id: 'ops-runtime', label: '全局运行配置', path: '/ops/runtime', icon: Clock },
      { id: 'ops-data', label: '数据接口对接', path: '/ops/data', icon: Plug },
      { id: 'ops-logs', label: '全量日志中心', path: '/ops/logs', icon: ScrollText },
    ],
  },
];
