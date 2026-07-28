/**
 * 多模型共识推演 — 前端类型定义
 * 与后端 api/v1/schemas/forecast.py 对齐
 */

export interface WeightConfigItem {
  name: string;
  weight: number;
  win_rate?: number;
}

export interface ModelDetailItem {
  name: string;
  score: number;
  confidence: number;
  dynamic_weight: number;
  status: 'normal' | 'diverge' | 'error';
  desc: string;
}

export interface ProcessLogItem {
  time: string;
  msg: string;
  type: 'info' | 'success' | 'warn' | 'error';
}

export interface ConsensusResult {
  consensus_score: number;
  trend: 'up' | 'down' | 'oscillation';
  confidence: number;
  valid_model_count: number;
  total_model_count: number;
  diverge_level: number; // 0=无 1=轻微 2=显著
}

export interface ChartModelDataItem {
  name: string;
  score: number;
  confidence: number;
  weight: number;
}

export interface ChartConsensusDataItem {
  label: string;
  consensus_score: number;
}

export interface MultiConsensusData {
  consensus: ConsensusResult;
  model_detail: ModelDetailItem[];
  chart_model_data: ChartModelDataItem[];
  chart_consensus_data: ChartConsensusDataItem[];
  process_logs: ProcessLogItem[];
}

export interface MultiConsensusResponse {
  code: number;
  msg: string;
  data: MultiConsensusData | null;
}

export interface MultiConsensusRequest {
  weight_config: WeightConfigItem[];
  stock_code?: string;
}
