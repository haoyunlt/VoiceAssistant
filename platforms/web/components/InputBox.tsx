import { Loader2, Mic, Send, X } from 'lucide-react';
import React, { KeyboardEvent, useRef, useState } from 'react';

interface InputBoxProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  isConnected: boolean;
}

export const InputBox: React.FC<InputBoxProps> = ({ onSend, isLoading, isConnected }) => {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || isLoading || !isConnected) return;

    onSend(input.trim());
    setInput('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);

    // Auto-resize textarea
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  };

  const handleVoiceInput = () => {
    // TODO: Implement voice input
    setIsRecording(!isRecording);
  };

  return (
    <div className="border-t bg-white px-6 py-4">
      {!isConnected && (
        <div className="mb-3 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ⚠️ Disconnected from server. Trying to reconnect...
        </div>
      )}

      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyPress={handleKeyPress}
            placeholder={
              isConnected
                ? 'Type your message... (Shift+Enter for new line)'
                : 'Connecting to server...'
            }
            disabled={isLoading || !isConnected}
            rows={1}
            className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
            style={{ minHeight: '48px', maxHeight: '200px' }}
          />

          {input && (
            <button
              onClick={() => setInput('')}
              className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        <button
          onClick={handleVoiceInput}
          disabled={isLoading || !isConnected}
          className={`p-3 rounded-lg transition-all ${
            isRecording
              ? 'bg-red-500 text-white hover:bg-red-600'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
          title="Voice input (Coming soon)"
        >
          <Mic className="w-5 h-5" />
        </button>

        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim() || !isConnected}
          className="px-6 py-3 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="hidden sm:inline">Sending...</span>
            </>
          ) : (
            <>
              <Send className="w-5 h-5" />
              <span className="hidden sm:inline">Send</span>
            </>
          )}
        </button>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-4">
          <span>Press Enter to send, Shift+Enter for new line</span>
        </div>
        <div>{input.length > 0 && <span>{input.length} characters</span>}</div>
      </div>
    </div>
  );
};
