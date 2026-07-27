import React, { useEffect, useRef } from 'react';
import { colors } from '../../theme/tokens';

interface SeriesConfig {
  name: string;
  dataKey: string;
  color: string;
}

interface ChartLineProps {
  data: Record<string, any>[];
  series: SeriesConfig[];
  height?: number;
}

const ChartLine: React.FC<ChartLineProps> = ({ data, series, height = 260 }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Lightweight SVG-based line chart (no external dependency)
    if (!containerRef.current || !data.length) return;
    renderSvgChart(containerRef.current, data, series);
  }, [data, series]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%', height, background: colors.card,
        borderRadius: 8, overflow: 'hidden',
      }}
    />
  );
};

function renderSvgChart(container: HTMLDivElement, data: Record<string, any>[], series: SeriesConfig[]) {
  const w = container.clientWidth || 600;
  const h = container.clientHeight || 260;
  const pad = { top: 20, right: 20, bottom: 30, left: 50 };
  const pw = w - pad.left - pad.right;
  const ph = h - pad.top - pad.bottom;
  const n = data.length;

  // Compute global Y range
  let yMin = Infinity, yMax = -Infinity;
  for (const s of series) {
    for (const d of data) {
      const v = Number(d[s.dataKey]) || 0;
      if (v < yMin) yMin = v;
      if (v > yMax) yMax = v;
    }
  }
  if (yMin === yMax) { yMin -= 1; yMax += 1; }

  const sx = (i: number) => pad.left + (i / Math.max(n - 1, 1)) * pw;
  const sy = (v: number) => pad.top + ph - ((v - yMin) / (yMax - yMin)) * ph;

  let paths = series.map(() => '');
  for (const [si, s] of series.entries()) {
    let d = '';
    for (let i = 0; i < n; i++) {
      const v = Number(data[i][s.dataKey]) || 0;
      d += `${i === 0 ? 'M' : 'L'}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`;
    }
    paths[si] = d;
  }

  const yTicks = 5;
  let yLabels = '';
  for (let i = 0; i <= yTicks; i++) {
    const val = yMin + (yMax - yMin) * (i / yTicks);
    const y = sy(val);
    yLabels += `<text x="${pad.left - 8}" y="${y + 4}" text-anchor="end" fill="#94A3B8" font-size="11">${val.toFixed(1)}</text>`;
    if (i > 0 && i < yTicks) {
      yLabels += `<line x1="${pad.left}" y1="${y}" x2="${w - pad.right}" y2="${y}" stroke="rgba(255,255,255,0.05)" />`;
    }
  }

  // Legend
  let legend = '';
  series.forEach((s, i) => {
    const lx = pad.left + i * 120;
    legend += `<rect x="${lx}" y="${h - 18}" width="12" height="12" rx="2" fill="${s.color}" />`;
    legend += `<text x="${lx + 16}" y="${h - 7}" fill="#94A3B8" font-size="11">${s.name}</text>`;
  });

  container.innerHTML = `
    <svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
      ${yLabels}
      ${legend}
      ${series.map((s, i) =>
        `<path d="${paths[i]}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" />`
      ).join('')}
      ${data.map((_, i) =>
        `<circle cx="${sx(i).toFixed(1)}" cy="${sy(Number(data[i][series[0].dataKey]) || 0).toFixed(1)}" r="3" fill="${series[0].color}" opacity="0.6" />`
      ).join('')}
    </svg>
  `;
}

export default ChartLine;
