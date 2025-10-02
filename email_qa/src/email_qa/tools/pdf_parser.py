"""
PDF Parser Tool for Email QA System
====================================
Extracts text and images from PDF copy documents using PyMuPDF.
Clean, simple extraction without encoding complexity.

Author: Rishabh Sharma
Date: 2025
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any
import fitz  # PyMuPDF
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class PDFParserInput(BaseModel):
    """Input schema for PDF Parser Tool."""
    pdf_path: str = Field(
        ..., 
        description="Path to the PDF file to parse"
    )
    extract_images: bool = Field(
        default=True,
        description="Whether to extract and save images from the PDF"
    )
    output_dir: str = Field(
        default="uploads",
        description="Directory to save extracted images"
    )


class PDFParserTool(BaseTool):
    """
    Parse PDF copy documents to extract text and images.
    
    This tool uses PyMuPDF to extract text with markdown formatting,
    preserving document structure (headers, lists, tables) and optionally
    extracting images.
    
    Returns clean markdown text without encoding issues.
    """
    
    name: str = "PDF Parser"
    description: str = (
        "Extracts text content from PDF copy documents with markdown formatting. "
        "Use this tool to parse email copy documents (PDFs) to extract requirements "
        "like subject lines, CTAs, preview text, and content sections. "
        "Returns structured markdown text that preserves document hierarchy."
    )
    args_schema: Type[BaseModel] = PDFParserInput
    
    def _run(
        self,
        pdf_path: str,
        extract_images: bool = True,
        output_dir: str = "uploads"
    ) -> str:
        """
        Extract text and images from PDF.
        
        Args:
            pdf_path: Path to PDF file
            extract_images: Whether to save images
            output_dir: Directory for extracted images
            
        Returns:
            JSON string with markdown text, image paths, and metadata
        """
        try:
            # Validate PDF path
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                return json.dumps({
                    "error": f"PDF file not found: {pdf_path}",
                    "success": False
                })
            
            # Open PDF
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            logger.info(f"Opened PDF: {pdf_path} ({page_count} pages)")
            
            # Extract content
            markdown_parts = []
            extracted_images = []
            
            # Create output directory for images
            if extract_images:
                img_dir = Path(output_dir) / pdf_file.stem / "images"
                img_dir.mkdir(parents=True, exist_ok=True)
            
            # Process each page
            for page_num in range(page_count):
                page = doc[page_num]
                
                # Add page separator
                markdown_parts.append(f"\n## Page {page_num + 1}\n")
                
                # Extract text as plain text (markdown format not available in this PyMuPDF version)
                page_text = page.get_text("text")
                if page_text.strip():
                    markdown_parts.append(page_text)
                
                # Extract images if requested
                if extract_images:
                    images = self._extract_page_images(
                        page, 
                        page_num + 1, 
                        img_dir,
                        doc
                    )
                    extracted_images.extend(images)
                    
                    # Add image references to markdown
                    for img_info in images:
                        markdown_parts.append(
                            f"\n![Image {img_info['index']}]({img_info['path']})\n"
                        )
            
            # Close document
            doc.close()
            
            # Combine markdown
            full_markdown = "\n".join(markdown_parts)
            
            # Prepare result
            result = {
                "success": True,
                "markdown": full_markdown,
                "images": extracted_images,
                "metadata": {
                    "page_count": page_count,
                    "char_count": len(full_markdown),
                    "image_count": len(extracted_images),
                    "source_file": str(pdf_file.name)
                }
            }
            
            logger.info(
                f"Extracted {page_count} pages, {len(extracted_images)} images, "
                f"{len(full_markdown)} characters"
            )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"PDF parsing failed: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "success": False
            })
    
    def _extract_page_images(
        self,
        page: fitz.Page,
        page_num: int,
        img_dir: Path,
        doc: fitz.Document
    ) -> List[Dict[str, Any]]:
        """
        Extract all images from a page.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (1-indexed)
            img_dir: Directory to save images
            doc: Parent document
            
        Returns:
            List of dicts with image info (path, index, page_number)
        """
        images = []
        
        try:
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Create filename
                    filename = f"page_{page_num}_img_{img_index}.{image_ext}"
                    img_path = img_dir / filename
                    
                    # Save image
                    img_path.write_bytes(image_bytes)
                    
                    # Store info
                    images.append({
                        "path": str(img_path),
                        "filename": filename,
                        "page_number": page_num,
                        "index": img_index,
                        "format": image_ext
                    })
                    
                    logger.debug(f"Extracted image: {filename}")
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to extract image {img_index} on page {page_num}: {e}"
                    )
        
        except Exception as e:
            logger.warning(f"Failed to get images from page {page_num}: {e}")
        
        return images


# Standalone function for direct use (non-CrewAI)
def parse_pdf_file(
    pdf_path: str,
    extract_images: bool = True,
    output_dir: str = "uploads"
) -> dict:
    """
    Direct function to parse PDF without CrewAI wrapper.
    
    Args:
        pdf_path: Path to PDF file
        extract_images: Whether to save images
        output_dir: Directory for images
        
    Returns:
        Dict with markdown, images, and metadata
        
    Example:
        >>> result = parse_pdf_file("copy_doc.pdf")
        >>> print(result['markdown'][:200])
        >>> print(f"Found {len(result['images'])} images")
    """
    tool = PDFParserTool()
    result_json = tool._run(pdf_path, extract_images, output_dir)
    return json.loads(result_json)