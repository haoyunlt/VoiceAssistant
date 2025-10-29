#!/usr/bin/env bash
#
# Retrieval Service 优化项目初始化脚本
#
# 用途:
# 1. 创建必要的目录结构
# 2. 准备配置文件模板
# 3. 下载测试数据集
# 4. 设置开发环境
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RETRIEVAL_SERVICE="$PROJECT_ROOT/algo/retrieval-service"

echo "🚀 Retrieval Service 优化项目初始化"
echo "================================================"
echo ""

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查前置条件
check_prerequisites() {
    log_info "检查前置条件..."

    # 检查Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi

    # 检查目录
    if [ ! -d "$RETRIEVAL_SERVICE" ]; then
        log_error "Retrieval service 目录不存在: $RETRIEVAL_SERVICE"
        exit 1
    fi

    log_info "前置条件检查通过 ✓"
}

# 创建目录结构
create_directories() {
    log_info "创建目录结构..."

    # Phase 1-4 新增服务目录
    mkdir -p "$RETRIEVAL_SERVICE/app/services/query"
    mkdir -p "$RETRIEVAL_SERVICE/app/services/cache"
    mkdir -p "$RETRIEVAL_SERVICE/app/services/adaptive"
    mkdir -p "$RETRIEVAL_SERVICE/app/agents"
    mkdir -p "$RETRIEVAL_SERVICE/app/agents/tools"

    # 评测目录
    mkdir -p "$RETRIEVAL_SERVICE/tests/eval/retrieval"
    mkdir -p "$RETRIEVAL_SERVICE/tests/eval/retrieval/datasets"
    mkdir -p "$RETRIEVAL_SERVICE/tests/eval/retrieval/reports"

    # 性能测试
    mkdir -p "$RETRIEVAL_SERVICE/tests/load/k6"

    # 配置目录
    mkdir -p "$PROJECT_ROOT/configs/retrieval"

    # 模型目录
    mkdir -p "$RETRIEVAL_SERVICE/models/intent_classifier"
    mkdir -p "$RETRIEVAL_SERVICE/models/reranker"

    log_info "目录结构创建完成 ✓"
}

# 创建配置文件模板
create_config_templates() {
    log_info "创建配置文件模板..."

    # Query optimization config
    cat > "$PROJECT_ROOT/configs/retrieval/query_optimization.yaml" <<'EOF'
# Query Optimization Configuration

expansion:
  enabled: false  # Phase 1 启用
  methods:
    - synonym
    - spelling
  max_expansions: 3
  synonym_dict_path: "data/synonyms.json"

multi_query:
  enabled: false  # Phase 1 启用
  num_queries: 3
  llm_model: "qwen-7b"
  llm_endpoint: "http://model-adapter:8000"
  temperature: 0.7
  timeout_ms: 3000

hyde:
  enabled: false  # Phase 1 启用
  num_hypotheses: 3
  fusion_method: "avg"  # avg, max, concat
  llm_model: "qwen-7b"
  temperature: 0.7

intent_classification:
  enabled: false  # Phase 1 启用
  model_path: "models/intent_classifier/bert-tiny"
  labels:
    - factual
    - procedural
    - navigational
    - comparative
EOF

    # Cache config
    cat > "$PROJECT_ROOT/configs/retrieval/cache.yaml" <<'EOF'
# Semantic Cache Configuration

strategy: "two_level"  # single, two_level

l1_cache:
  enabled: true
  ttl_seconds: 3600
  max_size_mb: 512
  eviction_policy: "lru"

l2_cache:
  enabled: false  # Phase 2 启用
  ttl_seconds: 21600
  similarity_threshold: 0.95
  max_items: 10000
  embedding_batch_size: 32

warming:
  enabled: false  # Phase 2 启用
  schedule: "0 */6 * * *"
  top_n_queries: 1000
  source: "analytics"  # analytics, manual
EOF

    # Reranking config
    cat > "$PROJECT_ROOT/configs/retrieval/reranking.yaml" <<'EOF'
# Reranking Configuration

strategy: "single"  # single, multi_stage

single_stage:
  model: "BAAI/bge-reranker-base"
  top_k: 10
  batch_size: 32

multi_stage:
  enabled: false  # Phase 2 启用

  stage1:
    model: "BAAI/bge-reranker-base"
    top_k: 20
    batch_size: 64

  stage2:
    model: "BAAI/bge-reranker-large"
    top_k: 10
    batch_size: 32
    use_llm: false
    llm_model: "gpt-4"
    llm_endpoint: "http://model-adapter:8000"
EOF

    # Adaptive retrieval config
    cat > "$PROJECT_ROOT/configs/retrieval/adaptive.yaml" <<'EOF'
# Adaptive Retrieval Configuration

enabled: false  # Phase 4 启用

complexity_evaluator:
  method: "rule_based"  # rule_based, ml
  model_path: "models/complexity_evaluator"

strategies:
  simple:
    trigger:
      word_count_max: 10
      entity_count_max: 0
    retrieval:
      method: "vector_only"
      top_k: 10
    timeout_ms: 200
    cost_weight: 1.0

  medium:
    trigger:
      word_count_max: 30
      entity_count_max: 2
    retrieval:
      method: "hybrid"
      fusion: "rrf"
      enable_rerank: false
    timeout_ms: 500
    cost_weight: 3.0

  complex:
    trigger:
      word_count_max: 999
    retrieval:
      method: "agent"
      enable_multi_query: true
      enable_rerank: true
      rerank_top_k: 10
    timeout_ms: 3000
    cost_weight: 10.0
EOF

    log_info "配置文件模板创建完成 ✓"
}

# 创建评测数据集下载脚本
create_dataset_script() {
    log_info "创建评测数据集下载脚本..."

    cat > "$RETRIEVAL_SERVICE/tests/eval/retrieval/download_datasets.sh" <<'EOF'
#!/usr/bin/env bash
# 下载评测数据集

set -euo pipefail

DATASETS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/datasets"

echo "下载评测数据集到: $DATASETS_DIR"

# MS MARCO Dev Small (1000 queries)
if [ ! -f "$DATASETS_DIR/ms_marco_dev_small.jsonl" ]; then
    echo "下载 MS MARCO Dev Small..."
    # TODO: 替换为实际下载链接
    # wget https://example.com/ms_marco_dev_small.jsonl.gz -O "$DATASETS_DIR/ms_marco_dev_small.jsonl.gz"
    # gunzip "$DATASETS_DIR/ms_marco_dev_small.jsonl.gz"
    echo "⚠️  需要手动下载 MS MARCO 数据集"
else
    echo "✓ MS MARCO 数据集已存在"
fi

# Natural Questions (可选)
if [ ! -f "$DATASETS_DIR/natural_questions.jsonl" ]; then
    echo "下载 Natural Questions..."
    # TODO: 下载链接
    echo "⚠️  需要手动下载 Natural Questions 数据集"
else
    echo "✓ Natural Questions 数据集已存在"
fi

echo "数据集准备完成"
EOF

    chmod +x "$RETRIEVAL_SERVICE/tests/eval/retrieval/download_datasets.sh"

    log_info "评测数据集下载脚本创建完成 ✓"
}

# 创建评测配置
create_eval_config() {
    log_info "创建评测配置..."

    cat > "$RETRIEVAL_SERVICE/tests/eval/retrieval/config.yaml" <<'EOF'
# Retrieval Evaluation Configuration

datasets:
  - name: "ms_marco_dev_small"
    path: "datasets/ms_marco_dev_small.jsonl"
    format: "jsonl"
    fields:
      query: "query"
      doc_id: "doc_id"
      relevance: "label"
    enabled: true

metrics:
  - "mrr@10"
  - "ndcg@10"
  - "recall@5"
  - "recall@10"
  - "precision@5"

strategies:
  - name: "vector_only"
    config:
      method: "vector"
      top_k: 10

  - name: "hybrid_rrf"
    config:
      method: "hybrid"
      fusion: "rrf"
      top_k: 10
      enable_rerank: false

  - name: "hybrid_rerank"
    config:
      method: "hybrid"
      fusion: "rrf"
      top_k: 10
      enable_rerank: true

baseline:
  name: "vector_only"
  metrics:
    mrr@10: 0.65
    ndcg@10: 0.70
    recall@10: 0.75

output:
  report_dir: "reports"
  format: "html"  # html, json, markdown
  detailed: true
EOF

    log_info "评测配置创建完成 ✓"
}

# 创建占位文件
create_placeholder_files() {
    log_info "创建占位文件..."

    # Query services
    touch "$RETRIEVAL_SERVICE/app/services/query/__init__.py"
    touch "$RETRIEVAL_SERVICE/app/services/query/expansion_service.py"
    touch "$RETRIEVAL_SERVICE/app/services/query/multi_query_service.py"
    touch "$RETRIEVAL_SERVICE/app/services/query/hyde_service.py"
    touch "$RETRIEVAL_SERVICE/app/services/query/intent_classifier.py"

    # Cache services
    touch "$RETRIEVAL_SERVICE/app/services/cache/__init__.py"
    touch "$RETRIEVAL_SERVICE/app/services/cache/semantic_cache.py"
    touch "$RETRIEVAL_SERVICE/app/services/cache/warming_service.py"

    # Adaptive services
    touch "$RETRIEVAL_SERVICE/app/services/adaptive/__init__.py"
    touch "$RETRIEVAL_SERVICE/app/services/adaptive/retrieval_service.py"
    touch "$RETRIEVAL_SERVICE/app/services/adaptive/complexity_evaluator.py"

    # Evaluation
    touch "$RETRIEVAL_SERVICE/tests/eval/retrieval/__init__.py"
    touch "$RETRIEVAL_SERVICE/tests/eval/retrieval/metrics.py"
    touch "$RETRIEVAL_SERVICE/tests/eval/retrieval/run_evaluation.py"

    log_info "占位文件创建完成 ✓"
}

# 创建README
create_readme() {
    log_info "创建README..."

    cat > "$RETRIEVAL_SERVICE/tests/eval/retrieval/README.md" <<'EOF'
# Retrieval Service 评测

## 快速开始

### 1. 下载数据集

```bash
./download_datasets.sh
```

### 2. 运行Baseline评测

```bash
python run_evaluation.py --baseline --config config.yaml
```

### 3. 评测新策略

```bash
python run_evaluation.py --strategy hybrid_rerank --compare-with baseline
```

### 4. 查看报告

```bash
open reports/eval_latest.html
```

## 评测指标

- **MRR@10**: Mean Reciprocal Rank at 10
- **NDCG@10**: Normalized Discounted Cumulative Gain at 10
- **Recall@K**: 召回率
- **Precision@K**: 精确率

## 添加自定义数据集

编辑 `config.yaml`:

```yaml
datasets:
  - name: "my_dataset"
    path: "datasets/my_dataset.jsonl"
    format: "jsonl"
    fields:
      query: "query"
      doc_id: "doc_id"
      relevance: "label"
```

数据格式:
```json
{"query": "如何使用Python", "doc_id": "doc_123", "label": 1}
```
EOF

    log_info "README创建完成 ✓"
}

# 创建Git分支
create_git_branch() {
    log_info "创建Git分支..."

    cd "$PROJECT_ROOT"

    if git rev-parse --verify feat/retrieval-optimization-setup &>/dev/null; then
        log_warn "分支 feat/retrieval-optimization-setup 已存在"
    else
        git checkout -b feat/retrieval-optimization-setup
        log_info "创建分支: feat/retrieval-optimization-setup ✓"
    fi
}

# 输出后续步骤
print_next_steps() {
    echo ""
    echo "================================================"
    echo "✅ 初始化完成！"
    echo "================================================"
    echo ""
    echo "📋 后续步骤:"
    echo ""
    echo "1. 查看路线图:"
    echo "   cat docs/roadmap/README.md"
    echo ""
    echo "2. 下载评测数据集:"
    echo "   cd algo/retrieval-service/tests/eval/retrieval"
    echo "   ./download_datasets.sh"
    echo ""
    echo "3. 运行Baseline评测:"
    echo "   cd algo/retrieval-service"
    echo "   python tests/eval/retrieval/run_evaluation.py --baseline"
    echo ""
    echo "4. 开始实现Task 1.1 (Query Expansion):"
    echo "   - 编辑: app/services/query/expansion_service.py"
    echo "   - 参考: docs/arch/retrieval-service-tech-guide.md"
    echo ""
    echo "5. 创建GitHub Issues:"
    echo "   python scripts/create_roadmap_issues.py"
    echo ""
    echo "📚 文档位置:"
    echo "   - 优化方案: docs/roadmap/retrieval-service-optimization.md"
    echo "   - 任务清单: docs/roadmap/retrieval-optimization-tasks.md"
    echo "   - 技术指南: docs/arch/retrieval-service-tech-guide.md"
    echo ""
    echo "🚀 祝开发顺利！"
    echo ""
}

# 主函数
main() {
    check_prerequisites
    create_directories
    create_config_templates
    create_dataset_script
    create_eval_config
    create_placeholder_files
    create_readme
    # create_git_branch  # 可选
    print_next_steps
}

# 执行
main "$@"
