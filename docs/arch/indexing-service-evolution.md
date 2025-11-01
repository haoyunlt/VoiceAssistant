# Indexing Service - Architecture Evolution

## Current Architecture (v2.0.0)

```mermaid
graph TB
    subgraph "Event Source"
        Kafka[Kafka Consumer<br/>document.events]
    end

    subgraph "Indexing Service"
        API[FastAPI<br/>Main Service]
        Proc[Document Processor]
        Parse[Parser Factory<br/>PDF/DOCX/TXT/MD/HTML]
        Chunk[Chunker<br/>RecursiveCharacterTextSplitter]
        Embed[BGE-M3 Embedder<br/>Single Thread]
        Graph[Graph Builder]
    end

    subgraph "Storage Layer"
        MinIO[(MinIO<br/>File Storage)]
        Milvus[(Milvus<br/>Vector DB)]
        Neo4j[(Neo4j<br/>Knowledge Graph)]
        Redis[(Redis<br/>Cache)]
    end

    Kafka -->|consume| Proc
    Proc -->|1. download| MinIO
    Proc -->|2. parse| Parse
    Parse -->|3. chunk| Chunk
    Chunk -->|4. embed| Embed
    Embed -->|5. store| Milvus
    Proc -->|6. build graph| Graph
    Graph -->|store| Neo4j
    Embed -.->|cache| Redis

    style Embed fill:#ff9999
    style Chunk fill:#ffcc99
    style MinIO fill:#99ccff
    style Milvus fill:#99ff99
    style Neo4j fill:#cc99ff
```

**Current Bottlenecks**:
- 🔴 **Embedder**: Single thread, CPU utilization < 30%
- 🟠 **Chunker**: Fixed rules, breaks semantic boundaries
- 🟡 **No retry**: Kafka consumer message loss risk
- 🟡 **No pooling**: Milvus connection exhaustion
- 🟡 **No streaming**: Large docs cause OOM

---

## Target Architecture (v3.0.0 - After N4)

```mermaid
graph TB
    subgraph "Event Source"
        Kafka[Kafka Consumer<br/>w/ Retry + DLQ]
    end

    subgraph "Indexing Service"
        API[FastAPI<br/>w/ OpenTelemetry]

        subgraph "Idempotency Layer"
            Idemp[Redis Dedup<br/>TTL=24h]
        end

        subgraph "Processing Pipeline"
            Proc[Document Processor<br/>w/ Streaming]
            Parse[Smart Parser<br/>Multimodal Support]

            subgraph "Chunking Strategy"
                ChunkFixed[Fixed Chunker]
                ChunkSem[Semantic Chunker]
                ChunkAdapt[Adaptive Chunker]
            end

            subgraph "Embedding Pool"
                Embed1[BGE-M3 Worker 1]
                Embed2[BGE-M3 Worker 2]
                Embed3[BGE-M3 Worker 3]
                Embed4[BGE-M3 Worker 4]
            end

            Dedup[Deduplication<br/>SimHash]
            Quality[Quality Evaluator]
            Token[Token Counter<br/>Cost Tracker]
        end

        subgraph "Graph Enhancement"
            Graph[Graph Builder]
            NER[NER Extractor<br/>spaCy]
            Relation[Relationship Miner]
        end
    end

    subgraph "Storage Layer"
        MinIO[(MinIO<br/>Files + Images)]

        subgraph "Vector Store"
            MilvusPool[Connection Pool<br/>min=5, max=20]
            MilvusWAL[WAL<br/>Failed Inserts]
            Milvus[(Milvus<br/>Vector DB)]
        end

        Neo4j[(Neo4j<br/>Rich Graph)]

        subgraph "Cache & State"
            RedisPool[Redis Pool]
            RedisVer[Version Store]
            RedisCache[Embedding Cache]
        end
    end

    subgraph "Observability"
        Prom[Prometheus<br/>Metrics]
        Jaeger[Jaeger<br/>Traces]
        Grafana[Grafana<br/>Dashboards]
    end

    Kafka -->|consume| Idemp
    Idemp -->|dedupe| Proc
    Proc -->|1. download| MinIO
    Proc -->|2. parse| Parse
    Parse -->|multimodal| MinIO
    Parse -->|3. dedup| Dedup
    Dedup -->|4. chunk| ChunkSem
    ChunkSem -->|5. parallel embed| Embed1
    ChunkSem -->|5. parallel embed| Embed2
    ChunkSem -->|5. parallel embed| Embed3
    ChunkSem -->|5. parallel embed| Embed4
    Embed1 -->|batch insert| MilvusPool
    Embed2 -->|batch insert| MilvusPool
    Embed3 -->|batch insert| MilvusPool
    Embed4 -->|batch insert| MilvusPool
    MilvusPool -->|persist| Milvus
    MilvusPool -.->|on failure| MilvusWAL

    Proc -->|6. extract| NER
    NER -->|7. mine| Relation
    Relation -->|8. build| Graph
    Graph -->|store| Neo4j

    Proc -->|9. evaluate| Quality
    Proc -->|10. count| Token

    Embed1 -.->|cache| RedisCache
    Proc -.->|version| RedisVer

    API -->|metrics| Prom
    API -->|traces| Jaeger
    Prom -->|visualize| Grafana
    Jaeger -->|visualize| Grafana

    style Embed1 fill:#99ff99
    style Embed2 fill:#99ff99
    style Embed3 fill:#99ff99
    style Embed4 fill:#99ff99
    style ChunkSem fill:#99ff99
    style MilvusPool fill:#99ff99
    style Idemp fill:#99ff99
    style Quality fill:#ffcc99
    style Token fill:#ffcc99
    style NER fill:#cc99ff
```

**Key Improvements**:
- ✅ **Parallel Embedding**: 4 workers, CPU utilization > 80%
- ✅ **Semantic Chunking**: Preserves semantic boundaries
- ✅ **Idempotency**: Redis deduplication
- ✅ **Connection Pool**: Milvus pool + WAL
- ✅ **Streaming**: Support 500MB documents
- ✅ **Multimodal**: Image/table extraction
- ✅ **Quality**: Automated evaluation
- ✅ **Observability**: OpenTelemetry traces

---

## Performance Comparison

| Metric | Current (v2.0) | Quick Wins | N1 | N2 | N3 | Target (v3.0) |
|--------|---------------|------------|----|----|----|--------------|
| **Throughput** | 10 docs/s | 25 docs/s | 40 docs/s | 45 docs/s | 45 docs/s | **50 docs/s** |
| **p95 Latency** | 5s | 3.5s | 2.5s | 2.3s | 2.3s | **2.5s** |
| **Max Doc Size** | 100MB | 100MB | 500MB | 500MB | 500MB | **500MB** |
| **CPU Util** | 30% | 40% | 80% | 80% | 80% | **80%** |
| **Success Rate** | 95% | 99% | 99.5% | 99.5% | 99.5% | **99.5%** |
| **Message Loss** | 5% | 0.5% | 0.25% | 0.25% | 0.25% | **0.25%** |
| **Chunk F1** | 0.65 | 0.65 | 0.65 | 0.85 | 0.85 | **0.85** |
| **Info Extract** | 60% | 60% | 60% | 60% | 78% | **78%** |

---

## Component Evolution Roadmap

### Phase 0: Quick Wins (Week 1-2)
```
Before:
  Embedder [Single Thread] → Milvus [Single Insert]

After:
  Embedder [Warmed Up] → Milvus [Batch Insert, size=500]
  + Redis Dedup
  + Kafka Retry (3x)
```

### Phase 1: N1 - Streaming & Parallelization (Week 3-4)
```
Before:
  Parse [In-Memory] → Chunk → Embed [Single]

After:
  Parse [Streaming, 5MB batch] → Chunk → Embed [4 Workers] → Pool [min=5, max=20]
  + Checkpoint Resume
  + WAL for failures
```

### Phase 2: N2 - Smart Chunking & Quality (Week 5-6)
```
Before:
  RecursiveCharacterTextSplitter [Fixed Rules]

After:
  SemanticChunker [Similarity-based]
  + Deduplication (SimHash)
  + Quality Evaluator
  + Multi-language Adaptive
```

### Phase 3: N3 - Multimodal & NER (Week 7-9)
```
Before:
  PDF → Text Only

After:
  PDF → Text + Images + Tables
  + OCR (PaddleOCR)
  + NER (spaCy)
  + Relationship Mining
```

### Phase 4: N4 - Observability (Week 10-11)
```
Before:
  Prometheus Metrics Only

After:
  OpenTelemetry Traces
  + Token/Cost Tracking
  + SLO Error Budget
  + Grafana Dashboards
```

---

## Migration Strategy

### 1. Feature Flags
```yaml
# configs/algo-services.yaml
indexing:
  features:
    streaming_parser: false  # Enable in N1
    semantic_chunking: false  # Enable in N2
    multimodal_extraction: false  # Enable in N3
    parallel_embedding: false  # Enable in N1
    deduplication: false  # Enable in N2
```

### 2. Gradual Rollout
```
Week 1-2: Quick Wins → All tenants
Week 3-4: N1 → Canary 5% → 50% → 100%
Week 5-6: N2 → Canary 10% → 100%
Week 7-9: N3 → Opt-in → Gradual
Week 10-11: N4 → All tenants
```

### 3. A/B Testing
- **Chunking Strategy**: Fixed vs Semantic (measure retrieval accuracy)
- **Embedding Workers**: 1 vs 2 vs 4 (measure throughput)
- **Batch Size**: 100 vs 500 vs 1000 (measure latency)

---

## Rollback Plan

### Automatic Rollback Triggers
1. Success rate < 98% for 5 minutes
2. p95 latency > 5s for 10 minutes
3. Error rate spike > 5%
4. Memory usage > 90%

### Manual Rollback
```bash
# Feature flag rollback
kubectl set env deployment/indexing-service \
  FEATURE_SEMANTIC_CHUNKING=false

# Full deployment rollback
kubectl rollout undo deployment/indexing-service
```

---

## Success Criteria

### Quick Wins
- ✅ Throughput +150%
- ✅ Cold start -90%
- ✅ Message loss -95%

### N1
- ✅ p95 < 2.5s
- ✅ Support 500MB docs
- ✅ CPU util > 80%

### N2
- ✅ Chunk F1 > 0.85
- ✅ Dedup rate > 90%
- ✅ Quality score > 0.80

### N3
- ✅ Info extract +30%
- ✅ Image/table extraction > 85%
- ✅ NER F1 > 0.80

### N4
- ✅ MTTD < 2min
- ✅ Cost visibility 100%
- ✅ SLO compliance

---

**Version**: 1.0
**Last Updated**: 2025-11-01
**Next Review**: After N1 completion


