import React, { useState } from 'react';
import GraphView from './components/GraphView';
import ChatInterface from './components/ChatInterface';
import './App.css';

const App = () => {
  const [botResponseText, setBotResponseText] = useState("");

  return (
    <div className="app-layout">
      {/* Background Graph Layer */}
      <div className="graph-container">
        <GraphView botResponseText={botResponseText} />
      </div>

      {/* Floating Chat Panel */}
      <div className="chat-overlay">
        <ChatInterface onBotResponse={setBotResponseText} />
      </div>
    </div>
  );
};

export default App;
