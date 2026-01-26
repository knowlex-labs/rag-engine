#!/usr/bin/env python3
"""
Parse Constitution PDF using the premium LlamaParse parser.
Saves structured JSON for ingestion.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add paths - go up one level to project root, then add src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from parsers.constitution_parser import ConstitutionParser

async def main():
    pdf_path = Path(__file__).parent / "pdfs" / "the_constitution_of_india.pdf"
    output_path = Path(__file__).parent / "output" / "constitution_parsed.json"
    
    print(f"📄 Parsing Constitution PDF...")
    print(f"   Input: {pdf_path}")
    print(f"   Output: {output_path}")
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return 1
    
    # Create output directory
    output_path.parent.mkdir(exist_ok=True)
    
    # Parse with LlamaParse
    parser = ConstitutionParser()
    parsed_content = await parser.parse_async(str(pdf_path))
    
    # Convert to dict for JSON
    output_data = {
        "legal_document": {
            "name": parsed_content.legal_document.name,
            "document_type": parsed_content.legal_document.document_type,
            "year": parsed_content.legal_document.year,
            "total_provisions": parsed_content.legal_document.total_provisions,
            "parsing_method": parsed_content.legal_document.parsing_method,
            "hierarchy": {
                "parts": parsed_content.legal_document.hierarchy.parts,
                "provisions": [
                    {
                        "id": p.id,
                        "number": p.number,
                        "title": p.title,
                        "text": p.text,
                        "part_number": p.part_number,
                        "statute_name": p.statute_name,
                        "provision_type": p.provision_type,
                        "references": p.references
                    }
                    for p in parsed_content.legal_document.hierarchy.provisions
                ],
                "schedules": [
                    {
                        "id": s.id,
                        "number": s.number,
                        "title": s.title,
                        "text": s.text,
                        "part_number": s.part_number,
                        "statute_name": s.statute_name,
                        "provision_type": s.provision_type,
                        "references": s.references
                    }
                    for s in parsed_content.legal_document.hierarchy.schedules
                ]
            },
            "internal_references": parsed_content.legal_document.internal_references
        },
        "parsing_metadata": {
            "title": parsed_content.metadata.title,
            "page_count": parsed_content.metadata.page_count,
            "extracted_at": str(parsed_content.metadata.extracted_at)
        }
    }
    
    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Parsing complete!")
    print(f"   Articles: {len([p for p in output_data['legal_document']['hierarchy']['provisions'] if p['provision_type'] == 'ARTICLE'])}")
    print(f"   Schedules: {len([p for p in output_data['legal_document']['hierarchy']['provisions'] if p['provision_type'] == 'SCHEDULE'])}")
    print(f"   Parts: {len(output_data['legal_document']['hierarchy']['parts'])}")
    print(f"\n📁 Saved to: {output_path}")
    print(f"\n▶️  Next: python ingestion-tools/ingest_constitution.py")
    
    return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))
