'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import type { EntityWithRelations } from '@/lib/knowledgeGraphApi';

interface Node {
  id: string;
  label: string;
  group: string;
  title: string;
  confidence?: number;
}

interface Edge {
  from: string;
  to: string;
  label: string;
  arrows: string;
  title: string;
}

interface KnowledgeGraphVizProps {
  entity?: EntityWithRelations;
  width?: string;
  height?: string;
  onNodeClick?: (nodeId: string) => void;
}

export const KnowledgeGraphViz: React.FC<KnowledgeGraphVizProps> = ({
  entity,
  width = '100%',
  height = '600px',
  onNodeClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || !entity) return;

    // 准备节点和边数据
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    // 添加中心节点
    nodes.push({
      id: entity.id,
      label: entity.properties.text || 'Unknown',
      group: entity.labels[0] || 'UNKNOWN',
      title: `${entity.labels.join(', ')}\nConfidence: ${entity.properties.confidence || 'N/A'}`,
      confidence: entity.properties.confidence,
    });

    // 添加关系和目标节点
    entity.relations?.forEach((relation, idx) => {
      const targetId = relation.target.id;
      const targetLabel = relation.target.properties.text || 'Unknown';

      // 添加目标节点
      if (!nodes.find((n) => n.id === targetId)) {
        nodes.push({
          id: targetId,
          label: targetLabel,
          group: relation.target.labels[0] || 'UNKNOWN',
          title: `${relation.target.labels.join(', ')}\n${targetLabel}`,
        });
      }

      // 添加边
      edges.push({
        from: entity.id,
        to: targetId,
        label: relation.type,
        arrows: 'to',
        title: `${relation.type}\nConfidence: ${relation.properties.confidence || 'N/A'}`,
      });
    });

    // 创建 DataSet
    const nodesDataset = new DataSet(nodes);
    const edgesDataset = new DataSet(edges);

    // 配置选项
    const options = {
      nodes: {
        shape: 'dot',
        size: 20,
        font: {
          size: 14,
          color: '#333',
        },
        borderWidth: 2,
        borderWidthSelected: 4,
      },
      edges: {
        width: 2,
        color: {
          color: '#848484',
          highlight: '#667eea',
          hover: '#667eea',
        },
        font: {
          size: 12,
          align: 'middle',
        },
        smooth: {
          type: 'continuous',
        },
      },
      groups: {
        PERSON: {
          color: {
            background: '#3b82f6',
            border: '#2563eb',
          },
        },
        ORG: {
          color: {
            background: '#10b981',
            border: '#059669',
          },
        },
        GPE: {
          color: {
            background: '#f59e0b',
            border: '#d97706',
          },
        },
        LOC: {
          color: {
            background: '#8b5cf6',
            border: '#7c3aed',
          },
        },
        DATE: {
          color: {
            background: '#ec4899',
            border: '#db2777',
          },
        },
        PRODUCT: {
          color: {
            background: '#06b6d4',
            border: '#0891b2',
          },
        },
        UNKNOWN: {
          color: {
            background: '#6b7280',
            border: '#4b5563',
          },
        },
      },
      physics: {
        enabled: true,
        stabilization: {
          iterations: 100,
        },
        barnesHut: {
          gravitationalConstant: -2000,
          centralGravity: 0.3,
          springLength: 150,
          springConstant: 0.04,
          damping: 0.09,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragView: true,
      },
    };

    // 创建网络
    const network = new Network(
      containerRef.current,
      {
        nodes: nodesDataset,
        edges: edgesDataset,
      },
      options
    );

    // 事件监听
    network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        setSelectedNode(nodeId);
        if (onNodeClick) {
          onNodeClick(nodeId);
        }
      }
    });

    networkRef.current = network;

    // 清理
    return () => {
      network.destroy();
    };
  }, [entity, onNodeClick]);

  if (!entity) {
    return (
      <div
        className="flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed border-gray-300"
        style={{ width, height }}
      >
        <div className="text-center text-gray-500">
          <div className="text-4xl mb-2">🕸️</div>
          <p>No entity selected</p>
          <p className="text-sm mt-1">Search for an entity to visualize</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <div
        ref={containerRef}
        className="border rounded-lg shadow-sm bg-white"
        style={{ width, height }}
      />

      {selectedNode && (
        <div className="absolute top-4 right-4 bg-white p-4 rounded-lg shadow-lg border max-w-xs">
          <div className="text-sm">
            <div className="font-semibold text-gray-700 mb-2">Selected Node</div>
            <div className="text-gray-600">ID: {selectedNode}</div>
          </div>
        </div>
      )}

      <div className="absolute bottom-4 left-4 bg-white p-3 rounded-lg shadow-lg border">
        <div className="text-xs space-y-1">
          <div className="font-semibold text-gray-700 mb-2">Legend</div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span>Person</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span>Organization</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500" />
            <span>Location (GPE)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-purple-500" />
            <span>Location</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-pink-500" />
            <span>Date</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-cyan-500" />
            <span>Product</span>
          </div>
        </div>
      </div>
    </div>
  );
};

