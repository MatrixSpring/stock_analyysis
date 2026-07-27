/** DSA 全局 TS 类型 — 对标 vn.py / EasyQuant 规范 */

export type MarketCycleType = 'TREND' | 'SHAKE' | 'DROP' | 'ICE'
export type StrategyStatusType = 'run' | 'stop' | 'bad'
export type IterCycleType = 'day' | 'twoDay' | 'week'
export type TagType = 'success' | 'warning' | 'danger' | 'primary'

export interface StrategyItem {
  id: string; name: string; status: StrategyStatusType; statusText: string
  weight: string; iterTime: IterCycleType; lastIter: string
  matchCycle: string; score: number
}

export interface GameSwitchItem { name: string; status: boolean; rate: string }
export interface WeightItem { name: string; value: number }

export interface RiskLogItem { time: string; type: string; desc: string; action: string }

export interface PerformanceItem {
  name: string; score: number; winRate: string; ratio: number
  draw: string; count: number; status: string; tag: TagType
}

export interface WarnItem { name: string; desc: string }
export interface CostFormItem { slip: number; fee: number; tax: number }
export interface PageParams { page: number; pageSize: number; total: number }
