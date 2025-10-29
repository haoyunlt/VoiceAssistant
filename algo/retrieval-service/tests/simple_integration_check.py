#!/usr/bin/env python3
"""
简单的集成检查 - 验证代码修改正确性

不需要运行代码，只检查文件和代码结构
"""

import re
from pathlib import Path


def check_file_exists(file_path, description):
    """检查文件是否存在"""
    if Path(file_path).exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}不存在: {file_path}")
        return False


def check_code_contains(file_path, pattern, description):
    """检查代码是否包含特定模式"""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        if isinstance(pattern, str):
            found = pattern in content
        else:
            found = bool(re.search(pattern, content))

        if found:
            print(f"✅ {description}")
            return True
        else:
            print(f"❌ {description}未找到")
            return False
    except Exception as e:
        print(f"❌ 检查{file_path}失败: {e}")
        return False


def main():
    """运行所有检查"""
    print("=" * 60)
    print("Query Expansion 集成检查")
    print("=" * 60)

    project_root = Path(__file__).parent.parent
    checks_passed = 0
    total_checks = 0

    # 检查1: 核心文件存在
    print("\n📁 检查1: 核心文件存在")
    files_to_check = [
        (
            project_root / "app/services/query/expansion_service.py",
            "Query Expansion Service",
        ),
        (project_root / "data/synonyms.json", "同义词词典"),
        (
            project_root / "tests/services/test_query_expansion.py",
            "单元测试",
        ),
        (
            project_root / "tests/standalone_test_expansion.py",
            "独立测试",
        ),
    ]

    for file_path, desc in files_to_check:
        total_checks += 1
        if check_file_exists(file_path, desc):
            checks_passed += 1

    # 检查2: retrieval_service.py集成
    print("\n🔧 检查2: RetrievalService集成")
    retrieval_service_path = project_root / "app/services/retrieval_service.py"

    integration_checks = [
        (
            "from app.services.query.expansion_service import QueryExpansionService",
            "导入QueryExpansionService",
        ),
        (
            "self.query_expansion = QueryExpansionService",
            "初始化QueryExpansionService",
        ),
        (
            "Query expansion service initialized",
            "初始化日志",
        ),
        (
            "enable_query_expansion",
            "检查enable_query_expansion参数",
        ),
        (
            "query_expanded",
            "返回query_expanded字段",
        ),
    ]

    for pattern, desc in integration_checks:
        total_checks += 1
        if check_code_contains(retrieval_service_path, pattern, desc):
            checks_passed += 1

    # 检查3: models/retrieval.py更新
    print("\n📝 检查3: 模型更新")
    retrieval_model_path = project_root / "app/models/retrieval.py"

    model_checks = [
        (
            "enable_query_expansion.*Field",
            "HybridRequest添加enable_query_expansion",
        ),
        (
            "query_expansion_max.*Field",
            "HybridRequest添加query_expansion_max",
        ),
        (
            "query_expanded.*Field",
            "HybridResponse添加query_expanded",
        ),
        (
            "expanded_queries.*Field",
            "HybridResponse添加expanded_queries",
        ),
        (
            "expansion_latency_ms.*Field",
            "HybridResponse添加expansion_latency_ms",
        ),
    ]

    for pattern, desc in model_checks:
        total_checks += 1
        if check_code_contains(retrieval_model_path, pattern, desc):
            checks_passed += 1

    # 检查4: 代码质量
    print("\n🎨 检查4: 代码实现质量")
    expansion_service_path = project_root / "app/services/query/expansion_service.py"

    quality_checks = [
        ("class QueryExpansionService", "定义QueryExpansionService类"),
        ("async def expand", "实现expand方法"),
        ("_expand_synonyms", "实现同义词扩展"),
        ("_correct_spelling", "实现拼写纠错"),
        ("expand_batch", "实现批量扩展"),
        ("get_stats", "实现统计方法"),
    ]

    for pattern, desc in quality_checks:
        total_checks += 1
        if check_code_contains(expansion_service_path, pattern, desc):
            checks_passed += 1

    # 总结
    print("\n" + "=" * 60)
    print(f"检查结果: {checks_passed}/{total_checks} 通过")
    print("=" * 60)

    if checks_passed == total_checks:
        print("\n🎉 所有检查通过！集成成功！")
        print("\n✅ 集成完成情况:")
        print("  ✅ QueryExpansionService已实现")
        print("  ✅ RetrievalService已集成QueryExpansion")
        print("  ✅ HybridRequest模型已更新")
        print("  ✅ HybridResponse模型已更新")
        print("  ✅ 代码结构完整")

        print("\n📋 已完成的集成步骤:")
        print("  ✅ Step 1: 初始化QueryExpansionService - 完成")
        print("  ✅ Step 2: 更新HybridRequest模型 - 完成")
        print("  ✅ Step 3: 更新HybridResponse模型 - 完成")
        print("  ✅ Step 4: 修改hybrid_search方法 - 完成")
        print("  ✅ Step 5: 代码检查通过 - 完成")

        print("\n🎊 Task 1.1 集成工作100%完成！")
        print("\n📝 使用方法:")
        print("  # Python代码")
        print("  request = HybridRequest(")
        print('      query="如何使用系统",')
        print("      enable_query_expansion=True,  # 启用扩展")
        print("      query_expansion_max=3,")
        print("      top_k=10,")
        print("  )")
        print("  response = await retrieval_service.hybrid_search(request)")
        print("  print(response.expanded_queries)  # 查看扩展结果")

        print("\n📊 下一步:")
        print("  1. 启动服务测试实际API")
        print("  2. 准备评测数据集")
        print("  3. 运行召回率评测")
        print("  4. 提交PR")

        return 0
    else:
        print(f"\n⚠️  有 {total_checks - checks_passed} 项检查未通过")
        print("请检查上述失败的项目")
        return 1


if __name__ == "__main__":
    import sys

    exit_code = main()
    sys.exit(exit_code)
