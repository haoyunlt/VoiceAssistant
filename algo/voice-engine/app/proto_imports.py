"""
Proto imports helper

自动添加proto生成代码到Python路径
"""

import sys
from pathlib import Path

# 添加proto生成代码目录到Python路径
_proto_path = Path(__file__).parent.parent.parent.parent / "api" / "gen" / "python"
if _proto_path.exists() and str(_proto_path) not in sys.path:
    sys.path.insert(0, str(_proto_path))

# 现在可以导入proto生成的模块
# 例如：
# from rag.v1 import rag_pb2, rag_pb2_grpc
# from retrieval.v1 import retrieval_pb2, retrieval_pb2_grpc
