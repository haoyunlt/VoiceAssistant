"""
Document Parser - Parse different document types
"""

import logging
from typing import List, Dict
from io import BytesIO

import PyPDF2
from docx import Document
import markdown
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parse documents and extract text"""
    
    @staticmethod
    def parse_pdf(file_content: bytes) -> str:
        """Parse PDF document"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise
    
    @staticmethod
    def parse_docx(file_content: bytes) -> str:
        """Parse Word document"""
        try:
            doc = Document(BytesIO(file_content))
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            logger.error(f"Error parsing DOCX: {e}")
            raise
    
    @staticmethod
    def parse_markdown(file_content: bytes) -> str:
        """Parse Markdown document"""
        try:
            md_text = file_content.decode('utf-8')
            html = markdown.markdown(md_text)
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text().strip()
        except Exception as e:
            logger.error(f"Error parsing Markdown: {e}")
            raise
    
    @staticmethod
    def parse_txt(file_content: bytes) -> str:
        """Parse plain text"""
        try:
            return file_content.decode('utf-8').strip()
        except Exception as e:
            logger.error(f"Error parsing TXT: {e}")
            raise
    
    @classmethod
    def parse(cls, file_content: bytes, content_type: str) -> str:
        """Parse document based on content type"""
        if 'pdf' in content_type.lower():
            return cls.parse_pdf(file_content)
        elif 'word' in content_type.lower() or 'docx' in content_type.lower():
            return cls.parse_docx(file_content)
        elif 'markdown' in content_type.lower() or 'md' in content_type.lower():
            return cls.parse_markdown(file_content)
        elif 'text' in content_type.lower() or 'txt' in content_type.lower():
            return cls.parse_txt(file_content)
        else:
            raise ValueError(f"Unsupported content type: {content_type}")


class DocumentChunker:
    """Chunk documents into smaller pieces"""
    
    @staticmethod
    def chunk_by_tokens(text: str, chunk_size: int = 512, overlap: int = 50) -> List[Dict]:
        """Chunk text by token count with overlap"""
        # Simple word-based chunking (in production, use tiktoken)
        words = text.split()
        chunks = []
        
        i = 0
        chunk_id = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunks.append({
                'chunk_id': chunk_id,
                'content': chunk_text,
                'start_index': i,
                'end_index': min(i + chunk_size, len(words)),
                'token_count': len(chunk_words)
            })
            
            i += (chunk_size - overlap)
            chunk_id += 1
        
        return chunks
    
    @staticmethod
    def chunk_by_sentences(text: str, max_chunk_size: int = 512) -> List[Dict]:
        """Chunk text by sentences"""
        # Simple sentence splitting
        import re
        sentences = re.split(r'[.!?]+', text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_id = 0
        
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            sent_size = len(sent.split())
            
            if current_size + sent_size > max_chunk_size and current_chunk:
                chunks.append({
                    'chunk_id': chunk_id,
                    'content': ' '.join(current_chunk),
                    'token_count': current_size
                })
                current_chunk = []
                current_size = 0
                chunk_id += 1
            
            current_chunk.append(sent)
            current_size += sent_size
        
        # Add remaining chunk
        if current_chunk:
            chunks.append({
                'chunk_id': chunk_id,
                'content': ' '.join(current_chunk),
                'token_count': current_size
            })
        
        return chunks

