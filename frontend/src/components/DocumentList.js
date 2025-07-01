import React from 'react';

const DocumentList = ({ 
  documents, 
  selectedDocument, 
  onDocumentSelected, 
  onDocumentDeleted, 
  onRefresh 
}) => {
  
  const handleDelete = async (documentId, event) => {
    event.stopPropagation();
    
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer ce document ?')) {
      return;
    }

    try {
      const response = await fetch(`/api/documents/${documentId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        onDocumentDeleted(documentId);
      } else {
        console.error('Erreur suppression');
      }
    } catch (error) {
      console.error('Erreur suppression:', error);
    }
  };

  const getStatusClass = (status) => {
    switch (status) {
      case 'ready': return 'status-ready';
      case 'uploaded': return 'status-uploaded';
      case 'error': return 'status-error';
      default: return 'status-uploaded';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'ready': return 'Prêt';
      case 'uploaded': return 'Uploadé';
      case 'error': return 'Erreur';
      default: return 'En cours';
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Vérification de sécurité pour documents
  const safeDocuments = Array.isArray(documents) ? documents : [];

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1rem' }}>Liste ({safeDocuments.length})</h2>
        <button 
          onClick={onRefresh}
          className="btn btn-secondary btn-small"
          style={{ padding: '0.3rem 0.6rem', fontSize: '0.7rem' }}
                  >
            ↻
          </button>
      </div>

      {safeDocuments.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '1rem', color: 'rgba(255,255,255,0.6)', fontSize: '0.8rem' }}>
          Aucun document
        </div>
      ) : (
        <div className="documents-list">
          {safeDocuments.map((doc) => (
            <div
              key={doc.document_id}
              className={`document-item ${
                selectedDocument?.document_id === doc.document_id ? 'selected' : ''
              }`}
              onClick={() => onDocumentSelected(doc)}
            >
              <div className="document-content">
                <div className="document-name">
                  {doc.filename.length > 20 ? doc.filename.substring(0, 20) + '...' : doc.filename}
                </div>
                
                <div className="document-status">
                  {getStatusLabel(doc.status)}
                  {doc.total_chunks && ` • ${doc.total_chunks} chunks`}
                </div>
              </div>
              
              <button 
                className="delete-btn"
                onClick={(e) => handleDelete(doc.document_id, e)}
                title="Supprimer ce document"
              >
                🗑️
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DocumentList; 