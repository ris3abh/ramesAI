#!/usr/bin/env python3
"""Quick test of Email parser with a real .eml file."""

import json
from pathlib import Path
from email_qa.tools.email_parser import parse_email_file

# Update this path to your actual .eml file
EMAIL_PATH = "../uploads/[Test]_Explore What Yanmar Can Do (1).eml"

if __name__ == "__main__":
    print(f"Parsing Email: {EMAIL_PATH}")
    print("-" * 60)
    
    result = parse_email_file(email_path=EMAIL_PATH)
    
    if result["success"]:
        print("✅ SUCCESS!")
        
        print(f"\n📧 Email Headers:")
        print(f"  Subject: {result['subject']}")
        print(f"  From: {result['from_name']} <{result['from_email']}>")
        print(f"  To: {result['to']}")
        
        print(f"\n👁️  Preview Text:")
        print(f"  {result['preview_text'][:100]}...")
        
        print(f"\n🔗 Links Found: {len(result['links'])}")
        for i, link in enumerate(result['links'][:5], 1):
            print(f"  {i}. {link['text'][:50]} → {link['url'][:60]}")
            if link['utm_params']:
                print(f"     UTM: {link['utm_params']}")
        
        print(f"\n🎯 CTAs Found: {len(result['ctas'])}")
        for i, cta in enumerate(result['ctas'], 1):
            print(f"  {i}. [{cta['text']}] → {cta['url'][:60]}")
        
        print(f"\n🖼️  Images: {len(result['images'])}")
        for i, img in enumerate(result['images'][:5], 1):
            alt = img['alt'] or '(no alt text)'
            print(f"  {i}. {alt[:50]} - {img['src'][:60]}")
        
        print(f"\n✉️  Compliance:")
        print(f"  Has Unsubscribe: {'✅' if result['has_unsubscribe'] else '❌'}")
        
        print(f"\n📄 HTML Body Length: {len(result['html_body'])} characters")
        
    else:
        print("❌ FAILED!")
        print(f"Error: {result.get('error', 'Unknown error')}")
