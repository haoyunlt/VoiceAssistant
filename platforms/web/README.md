# VoiceAssistant Web Frontend

> **实时 AI 对话界面** - React 18 + Next.js 14 + TypeScript + TailwindCSS

---

## 🚀 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问: `http://localhost:3000`

### 3. 确保后端服务运行

```bash
# Agent Engine (WebSocket 服务)
cd ../../algo/agent-engine
python main.py  # 运行在 localhost:8003
```

---

## 📦 技术栈

| 技术           | 版本    | 用途          |
| -------------- | ------- | ------------- |
| React          | 18.2.0  | UI 框架       |
| Next.js        | 14.0.4  | React 框架    |
| TypeScript     | 5.3.3   | 类型安全      |
| TailwindCSS    | 3.4.0   | 样式框架      |
| Zustand        | 4.4.7   | 状态管理      |
| React Markdown | 9.0.1   | Markdown 渲染 |
| Lucide React   | 0.303.0 | 图标库        |

---

## 🏗️ 项目结构

```
platforms/web/
├── app/
│   ├── layout.tsx          # 根布局
│   ├── page.tsx            # 首页（重定向到 /chat）
│   ├── globals.css         # 全局样式
│   └── chat/
│       └── page.tsx        # 聊天界面
├── components/
│   ├── MessageItem.tsx     # 消息项组件
│   ├── MessageList.tsx     # 消息列表
│   └── InputBox.tsx        # 输入框
├── lib/
│   └── useWebSocket.ts     # WebSocket Hook
├── store/
│   └── chatStore.ts        # Zustand 状态管理
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.js
```

---

## ✨ 核心功能

### 1. 实时 WebSocket 通信

- ✅ 自动连接/重连
- ✅ 心跳保活（30s 间隔）
- ✅ 指数退避重连策略
- ✅ 连接状态实时显示

### 2. 流式消息显示

- ✅ 实时逐字显示
- ✅ Markdown 渲染
- ✅ 代码高亮
- ✅ 打字机效果

### 3. 聊天功能

- ✅ 发送消息
- ✅ 清空对话
- ✅ 导出对话（JSON）
- ✅ 消息历史滚动
- ✅ 快捷键支持（Enter 发送，Shift+Enter 换行）

### 4. 用户体验

- ✅ 响应式设计（Mobile + Desktop）
- ✅ 加载状态显示
- ✅ 错误提示
- ✅ 空状态引导
- ✅ 字符计数

---

## 🎨 界面截图

### 聊天界面

- 现代化设计
- 流畅的流式显示
- Markdown + 代码高亮
- 实时连接状态

### 空状态

- 引导提示
- 快捷功能卡片
- 友好的用户界面

---

## 🔧 配置

### WebSocket URL

默认: `ws://localhost:8003/ws/agent`

修改: `app/chat/page.tsx`

```typescript
const [wsUrl] = useState('ws://localhost:8003/ws/agent');
```

### 样式定制

TailwindCSS 配置: `tailwind.config.ts`

```typescript
theme: {
  extend: {
    colors: {
      primary: {
        500: '#667eea',  // 主色
        // ...
      },
    },
  },
}
```

---

## 📊 性能优化

### 已实现

1. **组件优化**

   - React.memo 避免不必要的重渲染
   - useCallback 缓存函数引用
   - 虚拟滚动（待实现）

2. **WebSocket 优化**

   - 自动重连（指数退避）
   - 心跳保活
   - 消息队列（待实现）

3. **渲染优化**
   - 按需加载 Markdown
   - 代码高亮懒加载
   - 图片懒加载（待实现）

### 待优化

- [ ] 虚拟滚动（大量消息）
- [ ] 消息分页加载
- [ ] 图片/文件上传
- [ ] 离线缓存

---

## 🧪 测试

### 手动测试

1. 确保后端运行
2. 启动前端: `npm run dev`
3. 访问 `http://localhost:3000/chat`
4. 发送消息测试

### 功能测试清单

- [ ] 连接 WebSocket
- [ ] 发送消息
- [ ] 接收流式响应
- [ ] Markdown 渲染
- [ ] 代码高亮
- [ ] 清空对话
- [ ] 导出对话
- [ ] 断线重连
- [ ] 移动端适配

---

## 🚀 部署

### 开发环境

```bash
npm run dev
```

### 生产构建

```bash
npm run build
npm start
```

### Docker 部署

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
```

---

## 📝 后续开发计划

### Phase 1: 核心功能完善（本阶段）

- [x] WebSocket 通信
- [x] 聊天界面
- [x] 流式显示
- [x] Markdown 渲染
- [ ] 语音输入
- [ ] 文件上传

### Phase 2: 高级功能

- [ ] 多会话管理
- [ ] 会话历史
- [ ] 用户设置
- [ ] 主题切换
- [ ] 国际化

### Phase 3: 性能与体验

- [ ] 虚拟滚动
- [ ] 离线支持
- [ ] PWA
- [ ] 性能监控

---

## 🐛 常见问题

### Q: WebSocket 连接失败？

**A**: 确保 Agent Engine 正在运行：

```bash
cd algo/agent-engine
python main.py
```

### Q: 消息不显示？

**A**: 检查浏览器控制台，确认 WebSocket 消息格式正确。

### Q: 样式不生效？

**A**: 重启开发服务器：

```bash
npm run dev
```

---

## 📞 支持

**文档**: 本 README
**Sprint 4 计划**: `../../SPRINT4_PLAN.md`
**WebSocket 文档**: `../../algo/agent-engine/WEBSOCKET_README.md`

---

**版本**: v1.0.0
**最后更新**: 2025-10-27
**状态**: ✅ 核心功能完成
