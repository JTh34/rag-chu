import React, { useState } from 'react';
import { useDropzone } from 'react-dropzone';

const DocumentUpload = ({ onDocumentUploaded, onDocumentAnalyzed }) => {
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  const uploadDocument = async (file) => {
    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errorMessage = `Erreur HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (jsonError) {
          // Si ce n'est pas du JSON, utiliser le texte brut
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
      onDocumentUploaded(result);
      
      // Démarrer automatiquement l'analyse
      await analyzeDocument(result.document_id);
      
    } catch (error) {
      console.error('Erreur upload:', error);
      setError(error.message);
    } finally {
      setIsUploading(false);
    }
  };

  const analyzeDocument = async (documentId) => {
    setIsAnalyzing(true);
    setError(null);

    try {
      const response = await fetch(`/api/analyze/${documentId}`, {
        method: 'POST',
      });

      if (!response.ok) {
        let errorMessage = `Erreur HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (jsonError) {
          // Si ce n'est pas du JSON, utiliser le texte brut
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
      onDocumentAnalyzed(documentId);
      
    } catch (error) {
      console.error('Erreur analyse:', error);
      setError(error.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        uploadDocument(acceptedFiles[0]);
      }
    },
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png']
    },
    maxFiles: 1,
    disabled: isUploading || isAnalyzing
  });

  return (
    <div className="card">
      <h2>Documents</h2>
      
      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      <div
        {...getRootProps()}
        className={`upload-zone ${isDragActive ? 'drag-active' : ''}`}
      >
        <input {...getInputProps()} />
        
        <div className="upload-icon">
          {isUploading || isAnalyzing ? '⟳' : '+'}
        </div>
        
        <p className="upload-text">
          {isUploading ? 'Upload...' :
           isAnalyzing ? 'Analyse...' :
           isDragActive ? 'Déposer ici' :
           'Glisser ou cliquer'}
        </p>
        
        <p className="upload-hint">
          PDF, DOCX, Images
        </p>
        
        {(isUploading || isAnalyzing) && (
          <div className="loading"></div>
        )}
      </div>
    </div>
  );
};

export default DocumentUpload; 