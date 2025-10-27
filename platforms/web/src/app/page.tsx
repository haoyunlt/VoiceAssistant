export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
        <h1 className="text-4xl font-bold mb-4">
          VoiceAssistant AI 🎙️
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          智能客服语音助手平台
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="border rounded-lg p-4">
            <h2 className="text-xl font-semibold mb-2">🤖 GraphRAG</h2>
            <p className="text-gray-600">知识图谱增强检索</p>
          </div>
          <div className="border rounded-lg p-4">
            <h2 className="text-xl font-semibold mb-2">🔄 Multi-Agent</h2>
            <p className="text-gray-600">多智能体协同编排</p>
          </div>
          <div className="border rounded-lg p-4">
            <h2 className="text-xl font-semibold mb-2">☁️ 云原生</h2>
            <p className="text-gray-600">Kubernetes + 微服务</p>
          </div>
        </div>
      </div>
    </main>
  );
}

