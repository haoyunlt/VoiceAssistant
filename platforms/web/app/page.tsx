'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to chat page
    router.push('/chat');
  }, [router]);

  return (
    <div className="flex items-center justify-center h-screen bg-gray-50">
      <div className="text-center">
        <div className="text-6xl mb-4">🤖</div>
        <h1 className="text-2xl font-bold text-gray-800 mb-2">VoiceHelper</h1>
        <p className="text-gray-600">Loading...</p>
      </div>
    </div>
  );
}
