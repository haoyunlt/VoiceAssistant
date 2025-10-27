import { create } from 'zustand';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  streaming?: boolean;
  vendor?: string;
}

interface ChatStore {
  messages: Message[];
  isLoading: boolean;
  isConnected: boolean;

  // Actions
  addMessage: (message: Message) => void;
  updateMessage: (id: string, content: string) => void;
  updateLastMessage: (content: string) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setConnected: (connected: boolean) => void;

  // Helpers
  getLastMessage: () => Message | undefined;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  isLoading: false,
  isConnected: false,

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateMessage: (id, content) =>
    set((state) => ({
      messages: state.messages.map((msg) => (msg.id === id ? { ...msg, content } : msg)),
    })),

  updateLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      const lastMessage = messages[messages.length - 1];

      if (lastMessage) {
        lastMessage.content = content;
      }

      return { messages };
    }),

  clearMessages: () => set({ messages: [] }),

  setLoading: (loading) => set({ isLoading: loading }),

  setConnected: (connected) => set({ isConnected: connected }),

  getLastMessage: () => {
    const state = get();
    return state.messages[state.messages.length - 1];
  },
}));
