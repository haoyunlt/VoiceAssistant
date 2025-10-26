# End-to-End Tests

端到端测试目录，测试完整的用户流程。

## 运行测试

```bash
cd tests/e2e
npm install
npx playwright test
```

## 测试场景

- 用户注册和登录
- 创建对话
- 发送消息
- 上传文档
- 查看分析报表

## 配置

在 `.env.test` 中配置测试环境 URL。

