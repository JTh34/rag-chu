import React, { useState, useEffect, useRef } from 'react';

const DebugConsole = ({ ws }) => {
  const [logs, setLogs] = useState([]);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const consoleRef = useRef();

  useEffect(() => {
    if (ws) {
      const handleMessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message reçu:', data); // Debug
          
          // Accepter tous les types de messages avec un mapping intelligent
          let level = data.level || 'info';
          let message = data.message || data.text || 'Message sans contenu';
          
          // Mapper les types vers des niveaux de log appropriés
          if (data.type === 'error') level = 'error';
          if (data.type === 'analysis_complete') level = 'success';
          if (data.type === 'upload_success') level = 'success';
          if (data.type === 'analysis_start') level = 'vision';
          if (data.type === 'rag_creation') level = 'chunking';
          
          addLog(level, message, data.details);
          
        } catch (error) {
          console.error('Erreur parsing WebSocket:', error);
          // Message non-JSON, probablement du debug brut
          addLog('info', event.data);
        }
      };

      ws.addEventListener('message', handleMessage);
      return () => ws.removeEventListener('message', handleMessage);
    }
  }, [ws]);

  const addLog = (level, message, details = null) => {
    const timestamp = new Date().toLocaleTimeString();
    const newLog = {
      id: Date.now() + Math.random(),
      timestamp,
      level,
      message,
      details
    };

    setLogs(prev => {
      const updated = [...prev, newLog];
      // Garder seulement les 100 derniers logs
      return updated.slice(-100);
    });

    // Auto-scroll si activé
    if (isAutoScroll && consoleRef.current) {
      setTimeout(() => {
        consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
      }, 100);
    }
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const getLogClass = (level) => {
    const baseClass = 'debug-log';
    switch (level.toLowerCase()) {
      case 'error': return `${baseClass} error`;
      case 'warn':
      case 'warning': return `${baseClass} warning`;
      case 'success': return `${baseClass} success`;
      case 'vision': return `${baseClass} vision`;
      case 'chunking': return `${baseClass} chunking`;
      case 'rag': return `${baseClass} rag`;
      default: return `${baseClass} info`;
    }
  };

  const formatMessage = (message, details) => {
    let formattedMessage = message;
    
    // Ajouter les détails si disponibles
    if (details) {
      if (typeof details === 'object') {
        // Formatage spécial pour les chunks RAG
        if (details.chunk_index && details.similarity_score !== undefined) {
          formattedMessage += `\n  Score: ${details.similarity_score.toFixed(3)}`;
          if (details.metadata?.page) {
            formattedMessage += ` | Page: ${details.metadata.page}`;
          }
          if (details.content_preview) {
            formattedMessage += `\n  Content: "${details.content_preview}"`;
          }
        } 
        // Formatage pour les résumés de recherche
        else if (details.chunks_found !== undefined) {
          formattedMessage += `\n  Query: "${details.query}"`;
          formattedMessage += `\n  Collection: ${details.collection}`;
          formattedMessage += `\n  Found: ${details.chunks_found}/${details.chunks_expected}`;
        }
        // Formatage JSON par défaut
        else {
          formattedMessage += '\n' + JSON.stringify(details, null, 2);
        }
      } else {
        formattedMessage += '\n' + details;
      }
    }
    
    return formattedMessage;
  };

  // Ajouter quelques logs d'exemple au démarrage
  useEffect(() => {
    addLog('info', 'Console de debug initialisée');
    if (ws) {
      addLog('success', 'WebSocket connecté et prêt');
    } else {
      addLog('warning', 'WebSocket non connecté');
    }
  }, [ws]);

  return (
    <div className="debug-console">
      <div className="debug-console-header">
        <h3>
          Console Debug
        </h3>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)' }}>
            <input
              type="checkbox"
              checked={isAutoScroll}
              onChange={(e) => setIsAutoScroll(e.target.checked)}
              style={{ marginRight: '0.3rem' }}
            />
            Auto-scroll
          </label>
          <button
            onClick={clearLogs}
            className="btn btn-small"
            style={{ 
              padding: '0.3rem 0.6rem', 
              fontSize: '0.7rem',
              background: 'rgba(255,255,255,0.1)',
              border: '1px solid rgba(255,255,255,0.2)'
            }}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="debug-console-content" ref={consoleRef}>
        {logs.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '2rem', 
            color: 'rgba(255,255,255,0.5)',
            fontStyle: 'italic'
          }}>
            En attente de logs...
          </div>
        ) : (
          logs.map(log => (
            <div key={log.id} className={getLogClass(log.level)}>
              <span className="debug-timestamp">[{log.timestamp}]</span>
              <span className="debug-level">[{log.level.toUpperCase()}]</span>
              <div className="debug-message">
                {formatMessage(log.message, log.details)}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default DebugConsole; 