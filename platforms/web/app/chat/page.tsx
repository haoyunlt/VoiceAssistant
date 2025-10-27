'use client';

import { InputBox } from '@/components/InputBox';
import { MessageList } from '@/components/MessageList';
import { Navigation } from '@/components/Navigation';
import { useWebSocket } from '@/lib/useWebSocket';
import { useChatStore } from '@/store/chatStore';
import { Download, Menu, Settings, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function ChatPage() {
  const [wsUrl] = useState('ws://localhost:8003/ws/agent');
  const [showSidebar, setShowSidebar] = useState(false);

  const { sendMessage, lastMessage, readyState } = useWebSocket(wsUrl);

  const {
    messages,
    addMessage,
    updateLastMessage,
    clearMessages,
    isLoading,
    setLoading,
    setConnected,
  } = useChatStore();

  // Update connection status
  useEffect(() => {
    setConnected(readyState === WebSocket.OPEN);
  }, [readyState, setConnected]);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    const { type, content, vendor, ...rest } = lastMessage;

    console.log('Received message:', type, lastMessage);

    switch (type) {
      case 'connected':
        addMessage({
          id: `system-${Date.now()}`,
          role: 'system',
          content: 'Connected to AI Assistant',
          timestamp: Date.now(),
        });
        break;

      case 'stream_start':
        setLoading(true);
        addMessage({
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: '',
          timestamp: Date.now(),
          streaming: true,
        });
        break;

      case 'stream_chunk':
        if (content) {
          const lastMsg = messages[messages.length - 1];
          if (lastMsg && lastMsg.streaming) {
            updateLastMessage(lastMsg.content + content);
          }
        }
        break;

      case 'stream_end':
        setLoading(false);
        // Mark last message as no longer streaming
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.streaming) {
          useChatStore.setState((state) => ({
            messages: state.messages.map((msg, idx) =>
              idx === state.messages.length - 1 ? { ...msg, streaming: false } : msg
            ),
          }));
        }
        break;

      case 'agent_response':
        addMessage({
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content,
          timestamp: Date.now(),
          vendor,
        });
        setLoading(false);
        break;

      case 'error':
        addMessage({
          id: `system-${Date.now()}`,
          role: 'system',
          content: `Error: ${rest.error || 'Unknown error'}`,
          timestamp: Date.now(),
        });
        setLoading(false);
        break;

      case 'pong':
        // Heartbeat response, no action needed
        break;

      default:
        console.log('Unknown message type:', type);
    }
  }, [lastMessage, messages, addMessage, updateLastMessage, setLoading]);

  // Handle sending messages
  const handleSend = (message: string) => {
    // Add user message to chat
    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    });

    // Send to WebSocket
    sendMessage({
      type: 'streaming_query',
      query: message,
    });

    setLoading(true);
  };

  // Handle clear chat
  const handleClear = () => {
    if (confirm('Are you sure you want to clear all messages?')) {
      clearMessages();
    }
  };

  // Handle export chat
  const handleExport = () => {
    const chatData = JSON.stringify(messages, null, 2);
    const blob = new Blob([chatData], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-export-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <Navigation />

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar (mobile) */}
        {showSidebar && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
            onClick={() => setShowSidebar(false)}
          />
        )}

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <header className="bg-white shadow-sm px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="lg:hidden p-2 hover:bg-gray-100 rounded-lg"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-gray-800">AI Assistant</h1>
              <div className="flex items-center gap-2 mt-1">
                <div
                  className={`w-2 h-2 rounded-full ${
                    readyState === WebSocket.OPEN ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <span className="text-xs sm:text-sm text-gray-600">
                  {readyState === WebSocket.OPEN
                    ? 'Connected'
                    : readyState === WebSocket.CONNECTING
                    ? 'Connecting...'
                    : 'Disconnected'}
                </span>
                {readyState === WebSocket.OPEN && (
                  <span className="text-xs text-gray-400">• {messages.length} messages</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleExport}
              disabled={messages.length === 0}
              className="p-2 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              title="Export chat"
            >
              <Download className="w-5 h-5 text-gray-600" />
            </button>
            <button
              onClick={handleClear}
              disabled={messages.length === 0}
              className="p-2 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              title="Clear chat"
            >
              <Trash2 className="w-5 h-5 text-gray-600" />
            </button>
            <button className="p-2 hover:bg-gray-100 rounded-lg" title="Settings">
              <Settings className="w-5 h-5 text-gray-600" />
            </button>
          </div>
          </header>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto">
            <MessageList messages={messages} />
          </div>

          {/* Input */}
          <InputBox
            onSend={handleSend}
            isLoading={isLoading}
            isConnected={readyState === WebSocket.OPEN}
          />
        </div>
      </div>
    </div>
  );
}
