import React, { useState, useEffect } from 'react';
import DocumentUpload from './components/DocumentUpload';
import DocumentList from './components/DocumentList';
import ChatInterface from './components/ChatInterface';
import DebugConsole from './components/DebugConsole';
import './App.css';

function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [ws, setWs] = useState(null);

  // Initialisation du WebSocket
  useEffect(() => {
    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // Frontend sur port 3000, backend sur port 8000
      const wsUrl = `${protocol}//localhost:8000/ws`;
      
      const websocket = new WebSocket(wsUrl);
      
      websocket.onopen = () => {
        console.log('WebSocket connecté sur:', wsUrl);
        setWs(websocket);
      };
      
      websocket.onmessage = (event) => {
        console.log('Message WebSocket reçu dans App.js:', event.data);
        try {
          const data = JSON.parse(event.data);
          console.log('Message parsé:', data);
        } catch (e) {
          console.log('Message brut (non-JSON):', event.data);
        }
      };
      
      websocket.onclose = () => {
        console.log('WebSocket fermé, tentative de reconnexion...');
        setWs(null);
        setTimeout(connectWebSocket, 3000);
      };
      
      websocket.onerror = (error) => {
        console.error('Erreur WebSocket:', error);
      };
    };

    connectWebSocket();
    
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []); // Ne pas inclure ws dans les dépendances pour éviter les reconnexions

  // Vérification de l'état du backend
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await fetch('/api/health');
        setIsBackendReady(response.ok);
      } catch (error) {
        console.error('Backend non disponible:', error);
        setIsBackendReady(false);
      }
    };

    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Chargement initial des documents
  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const response = await fetch('/api/documents');
      if (response.ok) {
        const data = await response.json();
        // S'assurer que nous avons un tableau
        const docs = Array.isArray(data) ? data : (data.documents && Array.isArray(data.documents) ? data.documents : []);
        setDocuments(docs);
      } else {
        console.warn('Erreur HTTP lors du chargement des documents:', response.status);
        setDocuments([]); // Réinitialiser à un tableau vide en cas d'erreur
      }
    } catch (error) {
      console.error('Erreur chargement documents:', error);
      setDocuments([]); // Réinitialiser à un tableau vide en cas d'erreur
    }
  };

  const handleDocumentUploaded = (newDoc) => {
    setDocuments(prev => [...prev, newDoc]);
    loadDocuments(); // Recharger pour avoir les infos complètes
  };

  const handleDocumentAnalyzed = (documentId) => {
    loadDocuments(); // Recharger pour mettre à jour le statut
  };

  const handleDocumentSelected = (doc) => {
    setSelectedDocument(doc);
  };

  const handleDocumentDeleted = (documentId) => {
    setDocuments(prev => prev.filter(doc => doc.document_id !== documentId));
    if (selectedDocument?.document_id === documentId) {
      setSelectedDocument(null);
    }
  };

  return (
    <div className="App">
      {/* Header */}
      <header className="app-header">
        <h1>RAG CHU - Assistant Médical IA</h1>
        <p>
          Analysez vos documents médicaux et posez vos questions
          {isBackendReady ? (
            <span style={{ color: '#10b981', marginLeft: '1rem' }}>
              ● Backend connecté
            </span>
          ) : (
            <span style={{ color: '#ef4444', marginLeft: '1rem' }}>
              ● Backend déconnecté
            </span>
          )}
        </p>
      </header>

      {/* Layout principal en 3 colonnes */}
      <div className="app-grid">
        
        {/* Colonne gauche - Documents (étroite) */}
        <div className="left-column">
          <DocumentUpload
            onDocumentUploaded={handleDocumentUploaded}
            onDocumentAnalyzed={handleDocumentAnalyzed}
          />
          
          <DocumentList
            documents={documents}
            selectedDocument={selectedDocument}
            onDocumentSelected={handleDocumentSelected}
            onDocumentDeleted={handleDocumentDeleted}
            onRefresh={loadDocuments}
          />
        </div>

        {/* Colonne centre - Chat (large) */}
        <div className="center-column">
          <ChatInterface
            selectedDocument={selectedDocument}
            ws={ws}
          />
        </div>

        {/* Colonne droite - Console Debug (fixe) */}
        <div className="right-column">
          <DebugConsole ws={ws} />
        </div>

      </div>
    </div>
  );
}

export default App; 