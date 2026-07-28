import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  MultiConsensusRequest,
  MultiConsensusResponse,
} from '../types/forecast';

export const forecastApi = {
  /**
   * 多模型共识推演 — 同步接口，返回完整推演过程。
   */
  getMultiModelConsensus: async (
    data: MultiConsensusRequest
  ): Promise<MultiConsensusResponse> => {
    const requestData = {
      weight_config: data.weight_config.map((item) => ({
        name: item.name,
        weight: item.weight,
        win_rate: item.win_rate,
      })),
      ...(data.stock_code && { stock_code: data.stock_code }),
    };

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/forecast/consensus',
      requestData
    );

    return toCamelCase<MultiConsensusResponse>(response.data);
  },
};
