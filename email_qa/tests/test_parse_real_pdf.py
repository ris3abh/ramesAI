#!/usr/bin/env python3
"""Quick test of PDF parser with a real file."""

import json
from pathlib import Path
from email_qa.tools.pdf_parser import parse_pdf_file

# Update this path to your actual PDF
PDF_PATH = "../uploads/Internal - Welltower - Brandywine New Lead Nurture.pdf"

if __name__ == "__main__":
    print(f"Parsing PDF: {PDF_PATH}")
    print("-" * 60)
    
    result = parse_pdf_file(
        pdf_path=PDF_PATH,
        extract_images=True,
        output_dir="uploads"
    )
    
    if result["success"]:
        print("✅ SUCCESS!")
        print(f"\nMetadata:")
        print(f"  Pages: {result['metadata']['page_count']}")
        print(f"  Characters: {result['metadata']['char_count']}")
        print(f"  Images: {result['metadata']['image_count']}")
        
        print(f"\n📄 First 500 characters of extracted text:")
        print(result['markdown'][:500])
        
        if result['images']:
            print(f"\n🖼️  Extracted {len(result['images'])} images:")
            for img in result['images']:
                print(f"  - {img['filename']}")
    else:
        print("❌ FAILED!")
        print(f"Error: {result.get('error', 'Unknown error')}")
