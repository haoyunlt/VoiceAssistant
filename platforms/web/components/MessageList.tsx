import type { Message } from '@/store/chatStore';
import React, { useEffect, useRef } from 'react';
import { MessageItem } from './MessageItem';

interface MessageListProps {
  messages: Message[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400">
        <div className="text-6xl mb-4">💬</div>
        <h2 className="text-xl font-semibold mb-2">Start a Conversation</h2>
        <p className="text-sm">Send a message to begin chatting with the AI assistant</p>
        <div className="mt-8 grid grid-cols-2 gap-4 max-w-xl">
          <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors cursor-pointer">
            <div className="text-sm font-medium mb-1">🌟 Ask anything</div>
            <div className="text-xs text-gray-500">I can help with various topics</div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors cursor-pointer">
            <div className="text-sm font-medium mb-1">💡 Get ideas</div>
            <div className="text-xs text-gray-500">Creative suggestions and brainstorming</div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors cursor-pointer">
            <div className="text-sm font-medium mb-1">📊 Analyze data</div>
            <div className="text-xs text-gray-500">Process and understand information</div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors cursor-pointer">
            <div className="text-sm font-medium mb-1">🔍 Search knowledge</div>
            <div className="text-xs text-gray-500">Query the knowledge base</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-6">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};
