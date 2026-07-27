# RunFlow 拓扑画布 — XYFlow 重构迁移指南

## 安装依赖

```bash
cd apps/dsa-web
npm install @xyflow/react @dagrejs/dagre
```

## 迁移步骤

### Step 1: 确认依赖安装

```bash
npm ls @xyflow/react @dagrejs/dagre
```

### Step 2: 替换 RunFlowPanel.tsx 中的画布引用

在 `RunFlowPanel.tsx` 中：

```tsx
// 旧引用（自研 SVG 画布）
import { RunFlowGraph } from './RunFlowGraph';

// 新引用（XYFlow 画布）
import RunFlowGraphXY from './RunFlowGraphXY';

// 替换 JSX 中的 <RunFlowGraph ... /> 为 <RunFlowGraphXY ... />
```

### Step 3: 渐进式切换（推荐）

保留两套组件并行，通过 prop 切换：

```tsx
const useXYFlow = true; // feature flag

{useXYFlow ? (
  <RunFlowGraphXY
    lanes={lanes}
    nodes={nodes}
    edges={edges}
    selectedNodeId={selectedNodeId}
    onSelectNode={onSelectNode}
    editable={isEditMode}
    onSaveDag={handleSaveDag}
  />
) : (
  <RunFlowGraph
    lanes={lanes}
    nodes={nodes}
    edges={edges}
    selectedNodeId={selectedNodeId}
    onSelectNode={onSelectNode}
  />
)}
```

### Step 4: 编辑模式

```tsx
const [isEditMode, setIsEditMode] = useState(false);

const handleSaveDag = async (nodes: RunFlowNode[], edges: RunFlowEdge[]) => {
  await api.post('/api/v1/dag/save', { nodes, edges });
  setIsEditMode(false);
};
```

## 新旧对比

| 能力 | 旧 RunFlowGraph | 新 RunFlowGraphXY |
|------|:--:|:--:|
| 自动横向 LR 布局 | ✅ 手写算法 | ✅ dagre 标准布局 |
| 节点拖拽 | ❌ | ✅ |
| 手动连线 | ❌ | ✅ |
| 缩放/平移 | ❌ | ✅ 内置 |
| 小地图 | ❌ | ✅ MiniMap |
| 查看/编辑双模式 | ❌ | ✅ |
| SSE 实时状态推送 | ✅ | ✅ 兼容 |
| 深色主题卡片 | ✅ | ✅ 复刻 |
| 保存自定义 DAG | ❌ | ✅ |

## 文件清单

```
apps/dsa-web/src/components/run-flow/
├── RunFlowGraph.tsx          # 旧画布（保留兼容）
├── RunFlowGraphXY.tsx        # ★ 新 XYFlow 画布
├── xyflowLayout.ts           # ★ dagre 自动布局工具
├── RunFlowPanel.tsx          # 面板容器（改引用）
├── topologyViewModel.ts      # 数据模型（不变）
├── utils.ts                  # 工具函数（不变）
└── ...
```
