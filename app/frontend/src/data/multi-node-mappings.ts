export interface MultiNodeDefinition {
  name: string;
  nodes: {
    componentName: string;
    offsetX: number;
    offsetY: number;
  }[];
  edges: {
    source: string;
    target: string;
  }[];
}

const multiNodeDefinition: Record<string, MultiNodeDefinition> = {
  "A股价值投资": {
    name: "A股价值投资",
    nodes: [
      { componentName: "Stock Input", offsetX: 0, offsetY: 0 },
      { componentName: "段永平", offsetX: 400, offsetY: -400 },
      { componentName: "董承非", offsetX: 400, offsetY: 0 },
      { componentName: "陈光明", offsetX: 400, offsetY: 400 },
      { componentName: "Portfolio Manager", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Stock Input", target: "段永平" },
      { source: "Stock Input", target: "董承非" },
      { source: "Stock Input", target: "陈光明" },
      { source: "段永平", target: "Portfolio Manager" },
      { source: "董承非", target: "Portfolio Manager" },
      { source: "陈光明", target: "Portfolio Manager" },
    ],
  },
  "数据分析": {
    name: "数据分析",
    nodes: [
      { componentName: "Stock Input", offsetX: 0, offsetY: 0 },
      { componentName: "Technical Analyst", offsetX: 400, offsetY: -550 },
      { componentName: "Fundamentals Analyst", offsetX: 400, offsetY: -200 },
      { componentName: "Sentiment Analyst", offsetX: 400, offsetY: 150 },
      { componentName: "Valuation Analyst", offsetX: 400, offsetY: 500 },
      { componentName: "Portfolio Manager", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Stock Input", target: "Technical Analyst" },
      { source: "Stock Input", target: "Fundamentals Analyst" },
      { source: "Stock Input", target: "Sentiment Analyst" },
      { source: "Stock Input", target: "Valuation Analyst" },
      { source: "Technical Analyst", target: "Portfolio Manager" },
      { source: "Fundamentals Analyst", target: "Portfolio Manager" },
      { source: "Sentiment Analyst", target: "Portfolio Manager" },
      { source: "Valuation Analyst", target: "Portfolio Manager" },

    ],
  },
  "A股成长投资": {
    name: "A股成长投资",
    nodes: [
      { componentName: "Stock Input", offsetX: 0, offsetY: 0 },
      { componentName: "傅鹏博", offsetX: 400, offsetY: -400 },
      { componentName: "刘彦春", offsetX: 400, offsetY: 0 },
      { componentName: "谢治宇", offsetX: 400, offsetY: 400 },
      { componentName: "Portfolio Manager", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Stock Input", target: "傅鹏博" },
      { source: "Stock Input", target: "刘彦春" },
      { source: "Stock Input", target: "谢治宇" },
      { source: "傅鹏博", target: "Portfolio Manager" },
      { source: "刘彦春", target: "Portfolio Manager" },
      { source: "谢治宇", target: "Portfolio Manager" },
    ],
  },
};

export function getMultiNodeDefinition(name: string): MultiNodeDefinition | null {
  return multiNodeDefinition[name] || null;
}

export function isMultiNodeComponent(componentName: string): boolean {
  return componentName in multiNodeDefinition;
} 