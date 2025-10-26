# Integration Tests

集成测试目录，测试服务间的交互。

## 运行测试

```bash
# 启动测试环境
docker-compose -f docker-compose.test.yml up -d

# 运行集成测试
cd tests/integration
go test -v ./...

# 清理测试环境
docker-compose -f docker-compose.test.yml down
```

## 测试范围

- 服务间 gRPC 调用
- 数据库读写
- 缓存操作
- 消息队列
- 外部 API 调用

