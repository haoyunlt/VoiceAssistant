import type { Message } from '@/store/chatStore';
import { Bot, Loader2, User } from 'lucide-react';
import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';

interface MessageItemProps {
  message: Message;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center py-2">
        <div className="bg-gray-100 text-gray-600 text-sm px-4 py-2 rounded-full">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center">
          <Bot className="w-5 h-5 text-white" />
        </div>
      )}

      <div
        className={`max-w-[70%] rounded-lg px-4 py-3 ${
          isUser ? 'bg-primary-500 text-white' : 'bg-white shadow-sm border border-gray-200'
        }`}
      >
        <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{
              code: ({ node, inline, className, children, ...props }) => {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <pre className={className}>
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {message.content || ''}
          </ReactMarkdown>
        </div>

        {message.streaming && (
          <div className="flex items-center gap-2 mt-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-xs opacity-75">Thinking...</span>
          </div>
        )}

        {message.vendor && <div className="text-xs opacity-50 mt-2">via {message.vendor}</div>}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
          <User className="w-5 h-5 text-white" />
        </div>
      )}
    </div>
  );
};
