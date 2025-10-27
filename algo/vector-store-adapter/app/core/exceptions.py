"""自定义异常"""


class VectorStoreException(Exception):
    """向量存储基础异常"""

    def __init__(self, message: str, backend: str = None, details: dict = None):
        self.message = message
        self.backend = backend
        self.details = details or {}
        super().__init__(self.message)


class BackendNotAvailableException(VectorStoreException):
    """后端不可用异常"""

    pass


class BackendNotInitializedException(VectorStoreException):
    """后端未初始化异常"""

    pass


class CollectionNotFoundException(VectorStoreException):
    """集合不存在异常"""

    pass


class InvalidVectorDimensionException(VectorStoreException):
    """向量维度无效异常"""

    pass


class InsertFailedException(VectorStoreException):
    """插入失败异常"""

    pass


class SearchFailedException(VectorStoreException):
    """搜索失败异常"""

    pass


class DeleteFailedException(VectorStoreException):
    """删除失败异常"""

    pass

