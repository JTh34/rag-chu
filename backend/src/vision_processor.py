
import base64
import io
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import fitz  # PyMuPDF
from PIL import Image
import anthropic
from langchain.docstore.document import Document as LangChainDocument
from dataclasses import dataclass
from docx import Document as DocxDocument
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit

from .config import settings

logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    """Structure d'un chunk avec métadonnées enrichies"""
    content: str
    metadata: Dict
    bbox: Tuple[int, int, int, int]  # Bounding box dans l'image
    confidence: float # confiance dans l'analyse

class VisualDocumentAnalyzer:
    """Analyseur de documents basé sur Claude Vision"""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        api_key = anthropic_api_key or settings.anthropic_api_key
        if not api_key:
            raise ValueError("Clé API Anthropic requise")
            
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = settings.anthropic_model
        
    def convert_doc_to_images(self, doc_path: str, dpi: int = 200) -> List[Image.Image]:
        """Convertit un document en images haute résolution"""
        
        # Si c'est un .docx, le convertir en PDF d'abord
        if doc_path.endswith('.docx'):
            pdf_path = self._docx_to_pdf(doc_path)
        else:
            pdf_path = doc_path
            
        # Extraire les images du PDF
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # Matrice de transformation pour haute résolution
            mat = fitz.Matrix(dpi/72, dpi/72) # Améliorer la résolution de l'image
            pix = page.get_pixmap(matrix=mat) # Générer un pixmap
            
            # Convertir en PIL
            img_data = pix.tobytes("png") # Convertir en bytes
            img = Image.open(io.BytesIO(img_data)) # Charger l'image dans PIL
            images.append(img)  
            
        doc.close()
        return images
    
    def _docx_to_pdf(self, docx_path: str) -> str:
        """Convertit DOCX en PDF directement avec python-docx et reportlab"""

        logger.info("Conversion DOCX vers PDF avec python-docx")
        return self._extract_text_from_docx(docx_path)
    
    def _extract_text_from_docx(self, docx_path: str) -> str:
        """Extrait le texte directement du DOCX et le sauve comme PDF temporaire"""
 
        
        try:
            # Extraire le texte du DOCX 
            doc = DocxDocument(docx_path)
            text_content = []
            
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if text:
                    # Préserver la structure des titres
                    if paragraph.style.name.startswith('Heading'):
                        text_content.append(f"\n*** {text} ***\n")
                    else:
                        text_content.append(text)
            
            # Traiter aussi les tableaux
            for table in doc.tables:
                text_content.append("\n=== TABLEAU ===")
                for row in table.rows:
                    row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    if row_text:
                        text_content.append(row_text)
                text_content.append("=== FIN TABLEAU ===\n")
            
            # PDF temporaire avec le texte
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                pdf_path = tmp.name
                
            c = canvas.Canvas(pdf_path, pagesize=letter)
            width, height = letter
            
            # Configuration de police
            c.setFont("Helvetica", 10)
            y_position = height - 50
            margin = 50
            max_width = width - 2 * margin
            
            for paragraph in text_content:
                if not paragraph.strip():
                    continue
                    
                # Gérer les titres
                if paragraph.startswith("***") and paragraph.endswith("***"):
                    if y_position < 100:
                        c.showPage()
                        y_position = height - 50
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(margin, y_position, paragraph.replace("*", "").strip())
                    y_position -= 20
                    c.setFont("Helvetica", 10)
                    continue
                
                # Gérer les tableaux
                if paragraph.startswith("==="):
                    if y_position < 50:
                        c.showPage()
                        y_position = height - 50
                    c.setFont("Helvetica-Bold", 9)
                    c.drawString(margin, y_position, paragraph)
                    y_position -= 15
                    c.setFont("Helvetica", 10)
                    continue
                
                # Découpe du texte automatiquement
                lines = simpleSplit(paragraph, "Helvetica", 10, max_width)
                
                for line in lines:
                    if y_position < 50:
                        c.showPage()
                        y_position = height - 50
                    
                    c.drawString(margin, y_position, line)
                    y_position -= 12
                
                # Espace entre paragraphes
                y_position -= 8
                    
            c.save()
            logger.info("PDF créé à partir du texte DOCX ")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Erreur extraction DOCX: {e}")
            # En dernier recours, créer un PDF minimal
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    pdf_path = tmp.name
                c = canvas.Canvas(pdf_path, pagesize=letter)
                c.setFont("Helvetica", 12)
                c.drawString(50, 750, f"Document: {Path(docx_path).name}")
                c.drawString(50, 730, "Erreur lors de l'extraction du contenu DOCX")
                c.save()
                logger.warning("PDF minimal créé en fallback")
                return pdf_path
            except:
                # Ultime fallback : retourner le fichier original
                return docx_path
    
    async def analyze_page_structure(self, image: Image.Image, page_num: int) -> Dict:
        """Analyse la structure d'une page avec Claude"""
        
        # Conversion de l'image en base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        
        # Prompt spécialisé pour l'analyse de du document médical
        analysis_prompt = """
                        Analyse cette page de recommandations médicales et identifie précisément:

                        1. **STRUCTURE HIERARCHIQUE**:
                        - Titre principal et sous-titres
                        - Sections (A, B, C, D, etc.)
                        - Numérotation et listes

                        2. **ELEMENTS STRUCTURELS**:
                        - Tableaux (posologies, critères, alternatives)
                        - Encadrés/points forts
                        - Listes à puces
                        - Paragraphes de texte continu

                        3. **CONTENU MEDICAL**:
                        - Noms de médicaments et posologies
                        - Critères cliniques (gravité, stabilité)
                        - Cas cliniques spécifiques
                        - Durées de traitement

                        4. **ZONES DE TEXTE** avec coordinates approximatives (x, y, largeur, hauteur en %)

                        Retourne un JSON structuré avec:
                        ```json
                        {
                        "page_type": "guidelines|dosage_table|criteria_list",
                        "main_sections": [
                            {
                            "title": "titre section",
                            "type": "section|table|criteria|dosage|case_study",
                            "bbox_percent": [x, y, width, height],
                            "content_preview": "aperçu du contenu...",
                            "medical_entities": ["amoxicilline", "PAC grave", etc.],
                            "confidence": 0.0-1.0
                            }
                        ],
                        "tables": [
                            {
                            "title": "nom du tableau",
                            "type": "dosage|criteria|alternatives",
                            "bbox_percent": [x, y, width, height],
                            "columns": ["colonne1", "colonne2"],
                            "medical_focus": "antibiotiques|critères cliniques|durées"
                            }
                        ],
                        "key_medical_info": {
                            "medications": ["liste des médicaments"],
                            "dosages": ["posologies identifiées"],
                            "clinical_criteria": ["critères cliniques"],
                            "patient_types": ["PAC grave", "sans comorbidité", etc.]
                        }
                        }
                        ```
                        
                        Sois très précis sur les bounding boxes et identifie tous les éléments médicaux importants.
                        """
        
        try:
            import httpx
            import asyncio
            
            # Utiliser httpx pour un appel asynchrone à Anthropic
            headers = {
                        "Content-Type": "application/json",
                        "x-api-key": self.client.api_key,
                        "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": self.model,
                "max_tokens": 2000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_b64
                                }
                            },
                            {
                                "type": "text",
                                "text": analysis_prompt
                            }
                        ]
                    }
                ]
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=data,
                    headers=headers
                )
            
            # Parser la réponse JSON
            if response.status_code == 200:
                result = response.json()
                response_text = result["content"][0]["text"]
                
                # Extraire le JSON de la réponse
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start != -1 and json_end != -1:
                    json_str = response_text[json_start:json_end]
                    analysis = json.loads(json_str)
                    analysis['page_number'] = page_num
                    return analysis
                else:
                    raise ValueError("No JSON found in response")
            else:
                raise ValueError(f"API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erreur analyse page {page_num}: {e}")
            return self._fallback_analysis(page_num)
    
    def _fallback_analysis(self, page_num: int) -> Dict:
        """Analyse de fallback en cas d'échec"""
        return {
            "page_type": "unknown",
            "page_number": page_num,
            "main_sections": [],
            "tables": [],
            "key_medical_info": {
                "medications": [],
                "dosages": [],
                "clinical_criteria": [],
                "patient_types": []
            }
        }

class IntelligentMedicalProcessor:
    """Processeur intelligent pour documents médicaux"""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.analyzer = VisualDocumentAnalyzer(anthropic_api_key)
        
    async def process_medical_document(self, doc_path: str, progress_callback=None) -> List[LangChainDocument]:
        """Traite un document médical et retourne des chunks enrichis"""
        logger.info(f"Traitement du document: {doc_path}")
        
        # Convertir en images
        if progress_callback:
            await progress_callback(f"Conversion du document en images...", "vision")
        
        images = self.analyzer.convert_doc_to_images(doc_path)
        
        if progress_callback:
            await progress_callback(f"Document converti: {len(images)} pages à analyser", "vision")
        
        # Analyser chaque page avec streaming temps réel
        import asyncio
        analysis_results = []
        
        async def analyze_single_page(i, image):
            if progress_callback:
                await progress_callback(f"Analyse de la page {i+1}/{len(images)} avec Anthropic Claude...", "vision")
            
            analysis = await self.analyzer.analyze_page_structure(image, i)
            
            if progress_callback:
                sections_found = len(analysis.get('main_sections', []))
                tables_found = len(analysis.get('tables', []))
                await progress_callback(
                    f"Page {i+1} analysée: {sections_found} sections, {tables_found} tableaux", 
                    "success",
                    {
                        "page": i+1,
                        "sections": sections_found,
                        "tables": tables_found,
                        "page_type": analysis.get('page_type', 'unknown')
                    }
                )
            return analysis
        
        # Traiter les pages une par une pour le streaming
        for i, image in enumerate(images):
            analysis = await analyze_single_page(i, image)
            analysis_results.append(analysis)
        
        # Conversion en documents LangChain
        if progress_callback:
            total_sections = sum(len(analysis.get('main_sections', [])) for analysis in analysis_results)
            await progress_callback(f"Création de {total_sections} chunks structurés...", "chunking")
        
        documents = []
        for i, analysis in enumerate(analysis_results):
            # Créer un document par section principale
            for section in analysis.get('main_sections', []):
                metadata = {
                    'source': doc_path,
                    'page': i,
                    'section_title': section.get('title', ''),
                    'section_type': section.get('type', 'unknown'),
                    'medical_entities': section.get('medical_entities', []),
                    'confidence': section.get('confidence', 0.0),
                    'bbox': section.get('bbox_percent', []),
                    'key_medical_info': analysis.get('key_medical_info', {})
                }
                
                document = LangChainDocument(
                    page_content=section.get('content_preview', ''),
                    metadata=metadata
                )
                documents.append(document)
        
        logger.info(f"Document traité: {len(documents)} sections extraites")
        return documents

def create_medical_processor(anthropic_api_key: Optional[str] = None) -> IntelligentMedicalProcessor:
    """Factory function pour créer un processeur médical"""
    return IntelligentMedicalProcessor(anthropic_api_key) 