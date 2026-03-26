import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const ChatInterface = ({ onBotResponse }) => {
  const [messages, setMessages] = useState([
    { id: 'init', role: 'assistant', content: 'Hi! I can help you analyze the Order to Cash process.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/api/v1/chat', { question: userMsg });
      
      const answer = response.data.answer || "No response generated.";
      setMessages(prev => [...prev, { 
        id: Date.now().toString() + 'r', 
        role: 'assistant', 
        content: answer
      }]);

      if (onBotResponse) {
        onBotResponse(answer);
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages(prev => [...prev, { 
        id: Date.now().toString() + 'e', 
        role: 'assistant', 
        content: "Sorry, I encountered an error connecting to the backend. Is the server running?"
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#f8fafc', color: '#1e293b' }}>
      
      {/* Chat Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #f1f5f9', background: '#ffffff' }}>
        <h2 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>Chat with Graph</h2>
        <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>Order to Cash</p>
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', background: '#f8fafc' }}>
        {messages.map(msg => (
          <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            
            {/* Sender Label */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
              <div style={{ 
                width: 28, height: 28, borderRadius: '50%', background: msg.role === 'user' ? '#cbd5e1' : '#0f172a',
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: '12px', fontWeight: 'bold'
              }}>
                {msg.role === 'user' ? '👤' : 'D'}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{msg.role === 'user' ? 'You' : 'Dodge AI'}</span>
                {msg.role === 'assistant' && <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Graph Agent</span>}
              </div>
            </div>

            {/* Bubble */}
            <div style={{
              maxWidth: '85%',
              background: msg.role === 'user' ? '#1e293b' : 'transparent',
              color: msg.role === 'user' ? '#f8fafc' : '#334155',
              padding: msg.role === 'user' ? '12px 16px' : '0 4px',
              borderRadius: '12px',
              borderBottomRightRadius: msg.role === 'user' ? 0 : '12px',
              fontSize: '0.9rem',
              lineHeight: '1.5',
              wordBreak: 'break-word',
              whiteSpace: 'pre-wrap'
            }}>
              {typeof msg.content === 'object' ? JSON.stringify(msg.content, null, 2) : msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div style={{ padding: '0 24px 24px 24px', background: '#f8fafc' }}>
        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#64748b' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: loading ? '#f59e0b' : '#22c55e' }}></div>
            Dodge AI is {loading ? 'thinking...' : 'awaiting instructions'}
          </div>
          
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
              placeholder="Analyze anything"
              rows={1}
              style={{
                flex: 1,
                border: 'none',
                background: 'transparent',
                outline: 'none',
                resize: 'none',
                fontSize: '0.9rem',
                color: '#334155',
                padding: '4px 0',
                fontFamily: 'inherit'
              }}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: 'none',
                background: input.trim() ? '#475569' : '#cbd5e1',
                color: 'white',
                cursor: input.trim() ? 'pointer' : 'not-allowed',
                fontWeight: '500',
                fontSize: '0.85rem',
                transition: 'background 0.2s'
              }}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    
    </div>
  );
};

export default ChatInterface;
