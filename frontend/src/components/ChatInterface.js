import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

const ChatInterface = ({ selectedDocument, ws }) => {
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (selectedDocument) {
      setMessages([{
        type: 'assistant',
        content: `Bonjour ! Je suis prêt à répondre à vos questions sur le document **${selectedDocument.filename}**.

N'hésitez pas à être précis dans vos questions !`,
        timestamp: new Date()
      }]);
      // Afficher les suggestions quand un document est sélectionné
      setShowSuggestions(true);
    } else {
      setMessages([{
        type: 'assistant',
        content: `Bienvenue dans l'assistant médical RAG CHU !

**Pour commencer :**
1. Uploadez un document médical (PDF, DOCX, Image)
2. Attendez l'analyse automatique
3. Sélectionnez le document dans la liste
4. Posez vos questions !

**Conseils :**
- Utilisez des documents médicaux authentiques
- Posez des questions précises sur les traitements, posologies, critères...
- Consultez la console debug à droite pour suivre l'analyse`,
        timestamp: new Date()
      }]);
      // Masquer les suggestions si pas de document
      setShowSuggestions(false);
    }
  }, [selectedDocument]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async () => {
    if (!currentMessage.trim() || isLoading || !selectedDocument) return;

    const userMessage = {
      type: 'user',
      content: currentMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentMessage('');
    setIsLoading(true);
    
    // Masquer les suggestions après le premier message envoyé
    setShowSuggestions(false);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: currentMessage,
          document_id: selectedDocument.document_id
        }),
      });

      if (!response.ok) {
        let errorMessage = `Erreur HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (jsonError) {
          const errorText = await response.text();
          errorMessage = errorText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const responseText = await response.text();
      let result;
      try {
        result = JSON.parse(responseText);
      } catch (jsonError) {
        console.error('Réponse non-JSON reçue:', responseText);
        throw new Error('Réponse invalide du serveur');
      }

      const assistantMessage = {
        type: 'assistant',
        content: result.response,
        sources: result.sources,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (error) {
      console.error('Erreur chat:', error);
      const errorMessage = {
        type: 'assistant',
        content: `Erreur : ${error.message}`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTimestamp = (timestamp) => {
    return timestamp.toLocaleTimeString('fr-FR', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const suggestedQuestions = [
    "Quelle est la posologie recommandée ?",
    "Quels sont les critères de gravité ?",
    "Y a-t-il des contre-indications ?",
    "Quelle est la durée de traitement ?",
    "Quelles sont les alternatives thérapeutiques ?"
  ];

  return (
    <div className="card">
      <h2>{selectedDocument ? `Chat avec ${selectedDocument.filename}` : 'Assistant Médical'}</h2>
      
      <div className="chat-container">
        <div className="chat-messages">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`message ${message.type === 'user' ? 'message-user' : 'message-assistant'}`}
            >
              <div className="message-content">
                {message.type === 'user' ? (
                  <p>{message.content}</p>
                ) : (
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                )}
              </div>
              

              
              <div style={{ fontSize: '0.7rem', opacity: 0.6, marginTop: '0.5rem' }}>
                {formatTimestamp(message.timestamp)}
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="message message-assistant">
              <div className="message-content">
                <div className="loading"></div>
                <span style={{ marginLeft: '0.5rem' }}>Réflexion en cours...</span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions au-dessus de la zone de saisie */}
        {showSuggestions && selectedDocument && (
          <div style={{ 
            marginBottom: '1rem', 
            padding: '1rem',
            background: 'rgba(255,255,255,0.05)',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.1)'
          }}>
            <p style={{ 
              fontSize: '0.9rem', 
              color: 'rgba(255,255,255,0.8)', 
              marginBottom: '0.75rem',
              fontWeight: '500'
            }}>
              Suggestions de questions :
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {suggestedQuestions.map((question, index) => (
                <button
                  key={index}
                  onClick={() => setCurrentMessage(question)}
                  className="btn btn-secondary btn-small"
                  style={{ 
                    fontSize: '0.8rem',
                    padding: '0.4rem 0.8rem',
                    background: 'rgba(15, 118, 110, 0.2)',
                    border: '1px solid rgba(15, 118, 110, 0.3)',
                    color: 'rgba(255,255,255,0.9)'
                  }}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="chat-input-container">
          <textarea
            className="input chat-input textarea"
            placeholder={selectedDocument ? "Posez votre question médicale..." : "Sélectionnez d'abord un document..."}
            value={currentMessage}
            onChange={(e) => setCurrentMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading || !selectedDocument}
            rows={3}
          />
          
          <button
            onClick={sendMessage}
            disabled={!currentMessage.trim() || isLoading || !selectedDocument}
            className="btn"
          >
            {isLoading ? <div className="loading"></div> : '→'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface; 