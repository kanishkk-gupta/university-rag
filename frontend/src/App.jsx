import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navigation from './components/Navigation';
import LLMApp from './pages/LLMApp';
import KnowledgeBase from './pages/KnowledgeBase';
import RAG from './pages/RAG';
import Orchestration from './pages/Orchestration';
import Dockerized from './pages/Dockerized';
import Evaluation from './pages/Evaluation';
import Codebase from './pages/Codebase';
import Guardrails from './pages/Guardrails';
import './styles/index.css';

function App() {
  return (
    <Router>
      <div className="app-container">
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<LLMApp />} />
            <Route path="/llm-app" element={<LLMApp />} />
            <Route path="/knowledge-base" element={<KnowledgeBase />} />
            <Route path="/rag" element={<RAG />} />
            <Route path="/orchestration" element={<Orchestration />} />
            <Route path="/docker" element={<Dockerized />} />
            <Route path="/dockerized" element={<Dockerized />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/codebase" element={<Codebase />} />
            <Route path="/guardrails" element={<Guardrails />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
