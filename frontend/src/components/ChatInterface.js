import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

const ChatInterface = ({ selectedDocument, ws }) => {
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (selectedDocument) {
      setMessages([{
        type: 'assistant',
        content: `Je suis prêt à répondre à vos questions sur le document: 
**${selectedDocument.filename}**.
N'hésitez pas à être précis dans vos questions.`,
        timestamp: new Date()
      }]);
    } else {
      setMessages([{
        type: 'assistant',
        content: `Bienvenue dans l'assistant médical RAG CHU.

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
    const questionToSend = currentMessage;
    setCurrentMessage('');
    setIsLoading(true);

    // ID pour le message assistant
    const assistantMessageId = Date.now();

    // Timeout de sécurité pour éviter les blocages
    const timeoutId = setTimeout(() => {
      console.warn('Timeout: Réinitialisation forcée de isLoading');
      setIsLoading(false);
    }, 30000); // 30 secondes de timeout

    try {
      // Utiliser directement l'endpoint normal pour simplicité et fiabilité
      console.log('💬 Utilisation endpoint normal /api/chat');
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: questionToSend,
          document_id: selectedDocument.document_id
        }),
      });

      if (!response.ok) {
        clearTimeout(timeoutId);
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

      // Récupérer la réponse complète
      const result = await response.json();
      
      // Afficher la réponse directement
      const assistantMessage = {
        id: assistantMessageId,
        type: 'assistant',
        content: result.response,
        timestamp: new Date(),
        isStreaming: false
      };
      setMessages(prev => [...prev, assistantMessage]);
      clearTimeout(timeoutId);
      setIsLoading(false);

    } catch (error) {
      console.error('Erreur chat:', error);
      // Créer un message d'erreur
      const errorMessage = {
        id: assistantMessageId,
        type: 'assistant',
        content: `Erreur : ${error.message}`,
        timestamp: new Date(),
        isStreaming: false
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      clearTimeout(timeoutId);
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

  return (
    <div className="card">
      <h2>{selectedDocument ? `Chat avec ${selectedDocument.filename}` : 'Assistant Médical'}</h2>
      
      <div className="chat-container">
        <div className="chat-messages">
          {messages
            .filter(message => message.content && message.content.trim() !== '')
            .map((message, index) => (
            <div
              key={message.id || index}
              className={`message ${message.type === 'user' ? 'message-user' : 'message-assistant'}`}
            >
              <div className="message-content">
                {message.type === 'user' ? (
                  <p>{message.content}</p>
                ) : (
                  <div>
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div className="medical-spinner"></div>
                  <span style={{ 
                    fontSize: '0.9rem', 
                    color: 'rgba(255,255,255,0.9)',
                    fontWeight: '400'
                  }}>
                    Consultation des protocoles de soins
                  </span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

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