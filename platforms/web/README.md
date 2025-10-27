# VoiceAssistant Web Frontend

基于 Next.js 和 React 的 VoiceAssistant Web 前端应用。

## 🚀 快速开始

### 安装依赖

```bash
npm install
# 或
yarn install
# 或
pnpm install
```

### 开发环境

```bash
npm run dev
# 或
yarn dev
# 或
pnpm dev
```

打开 [http://localhost:3000](http://localhost:3000) 查看应用。

### 生产构建

```bash
npm run build
npm run start
```

## 📁 项目结构

```
web/
├── app/               # Next.js 13+ App Router
├── components/        # React 组件
├── lib/              # 工具库
├── public/           # 静态资源
├── styles/           # 样式文件
└── package.json      # 依赖配置
```

## 🛠️ 技术栈

- **框架**: Next.js 14
- **UI**: React 18, Tailwind CSS, shadcn/ui
- **状态管理**: React Context / Zustand
- **API 客户端**: Axios / SWR
- **WebSocket**: Socket.io-client

## 🔧 配置

环境变量配置在 `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_WS_URL=ws://localhost:8002
```

## 📦 主要功能

- 实时对话界面
- 语音输入支持
- 历史记录查看
- 知识库管理
- 用户设置

## 🧪 测试

```bash
npm run test
```

## 📝 代码规范

```bash
# ESLint
npm run lint

# Prettier
npm run format
```

## 📄 许可证

MIT
