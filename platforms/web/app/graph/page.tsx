'use client';

import { KnowledgeGraphViz } from '@/components/KnowledgeGraphViz';
import { Navigation } from '@/components/Navigation';
import { kgApi, type EntityWithRelations, type GraphStatistics } from '@/lib/knowledgeGraphApi';
import {
  AlertCircle,
  Download,
  Loader2,
  Network,
  RefreshCw,
  Search,
  TrendingUp,
} from 'lucide-react';
import { useEffect, useState } from 'react';

export default function GraphPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntity, setSelectedEntity] = useState<EntityWithRelations | null>(null);
  const [statistics, setStatistics] = useState<GraphStatistics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extractText, setExtractText] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);

  // 加载统计信息
  useEffect(() => {
    loadStatistics();
  }, []);

  const loadStatistics = async () => {
    try {
      const stats = await kgApi.getStatistics();
      setStatistics(stats);
    } catch (err) {
      console.error('Failed to load statistics:', err);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const entity = await kgApi.queryEntity(searchQuery.trim());
      setSelectedEntity(entity);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to find entity');
      setSelectedEntity(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExtract = async () => {
    if (!extractText.trim()) return;

    setIsExtracting(true);
    setError(null);

    try {
      const result = await kgApi.extractFromText(extractText.trim(), 'web-ui');

      alert(
        `Extraction completed!\n\n` +
          `Entities: ${result.entities_stored}/${result.entities_extracted}\n` +
          `Relations: ${result.relations_stored}/${result.relations_extracted}`
      );

      setExtractText('');
      loadStatistics();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to extract entities');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleExport = () => {
    if (!selectedEntity) return;

    const data = JSON.stringify(selectedEntity, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `entity-${selectedEntity.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      {/* Header */}
      <header className="bg-white shadow-sm px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Knowledge Graph</h1>
              <p className="text-sm text-gray-600 mt-1">
                Explore entities and relationships
              </p>
            </div>
            <button
              onClick={loadStatistics}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="Refresh statistics"
            >
              <RefreshCw className="w-5 h-5 text-gray-600" />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Sidebar - Statistics & Controls */}
          <div className="space-y-6">
            {/* Statistics */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="w-5 h-5 text-primary-500" />
                <h2 className="text-lg font-semibold">Statistics</h2>
              </div>

              {statistics ? (
                <div className="space-y-4">
                  <div>
                    <div className="text-3xl font-bold text-primary-500">
                      {statistics.total_nodes.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-600">Total Nodes</div>
                  </div>

                  <div>
                    <div className="text-3xl font-bold text-green-500">
                      {statistics.total_relationships.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-600">Total Relationships</div>
                  </div>

                  <div className="pt-4 border-t">
                    <div className="text-sm font-semibold text-gray-700 mb-2">
                      Entities by Type
                    </div>
                    <div className="space-y-2">
                      {statistics.label_statistics.slice(0, 5).map((stat) => (
                        <div key={stat.label} className="flex items-center justify-between">
                          <span className="text-sm text-gray-600">{stat.label}</span>
                          <span className="text-sm font-medium">{stat.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                </div>
              )}
            </div>

            {/* Search Entity */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <Search className="w-5 h-5 text-primary-500" />
                <h2 className="text-lg font-semibold">Search Entity</h2>
              </div>

              <div className="space-y-3">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Enter entity name..."
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <button
                  onClick={handleSearch}
                  disabled={isLoading || !searchQuery.trim()}
                  className="w-full px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4" />
                      Search
                    </>
                  )}
                </button>
              </div>

              {error && (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </div>

            {/* Extract Entities */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <Network className="w-5 h-5 text-primary-500" />
                <h2 className="text-lg font-semibold">Extract Entities</h2>
              </div>

              <div className="space-y-3">
                <textarea
                  value={extractText}
                  onChange={(e) => setExtractText(e.target.value)}
                  placeholder="Enter text to extract entities and relations..."
                  rows={4}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                />
                <button
                  onClick={handleExtract}
                  disabled={isExtracting || !extractText.trim()}
                  className="w-full px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isExtracting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Extracting...
                    </>
                  ) : (
                    <>
                      <Network className="w-4 h-4" />
                      Extract
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Main Content - Graph Visualization */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">
                  {selectedEntity
                    ? `${selectedEntity.properties.text} (${selectedEntity.labels.join(', ')})`
                    : 'Graph Visualization'}
                </h2>
                {selectedEntity && (
                  <button
                    onClick={handleExport}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Export entity data"
                  >
                    <Download className="w-5 h-5 text-gray-600" />
                  </button>
                )}
              </div>

              <KnowledgeGraphViz
                entity={selectedEntity || undefined}
                height="700px"
                onNodeClick={(nodeId) => {
                  console.log('Node clicked:', nodeId);
                }}
              />

              {selectedEntity && (
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm space-y-2">
                    <div>
                      <span className="font-semibold">Entity:</span>{' '}
                      {selectedEntity.properties.text}
                    </div>
                    <div>
                      <span className="font-semibold">Type:</span>{' '}
                      {selectedEntity.labels.join(', ')}
                    </div>
                    <div>
                      <span className="font-semibold">Confidence:</span>{' '}
                      {selectedEntity.properties.confidence
                        ? (selectedEntity.properties.confidence * 100).toFixed(1) + '%'
                        : 'N/A'}
                    </div>
                    <div>
                      <span className="font-semibold">Relations:</span>{' '}
                      {selectedEntity.relations?.length || 0}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

