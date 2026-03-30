#!/usr/bin/env python3
"""
Verify SEO setup for Your Life Pathways
Checks that all SEO components are properly configured
"""

import os
import sys
from bs4 import BeautifulSoup

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description} MISSING: {filepath}")
        return False

def check_html_content(filepath, search_terms, description):
    """Check if HTML file contains specific terms"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            soup = BeautifulSoup(content, 'html.parser')
            
        found_terms = []
        missing_terms = []
        
        for term in search_terms:
            if term.lower() in content.lower():
                found_terms.append(term)
            else:
                missing_terms.append(term)
        
        if missing_terms:
            print(f"⚠ {description}: Missing terms: {', '.join(missing_terms)}")
            return False
        else:
            print(f"✓ {description}: All terms found ({', '.join(found_terms)})")
            return True
            
    except Exception as e:
        print(f"✗ Error checking {description}: {str(e)}")
        return False

def check_structured_data(filepath):
    """Check for JSON-LD structured data"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_person_schema = '"@type": "Person"' in content
        has_service_schema = '"@type": "ProfessionalService"' in content
        has_erez_asif = '"name": "Erez Asif"' in content
        
        if has_person_schema and has_service_schema and has_erez_asif:
            print(f"✓ Structured Data: Person and ProfessionalService schemas found")
            return True
        else:
            print(f"⚠ Structured Data: Some schemas missing")
            print(f"  - Person schema: {'✓' if has_person_schema else '✗'}")
            print(f"  - Service schema: {'✓' if has_service_schema else '✗'}")
            print(f"  - Erez Asif name: {'✓' if has_erez_asif else '✗'}")
            return False
            
    except Exception as e:
        print(f"✗ Error checking structured data: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("SEO Setup Verification for Your Life Pathways")
    print("=" * 60)
    print()
    
    all_checks_passed = True
    
    # Check robots.txt
    print("1. Checking robots.txt...")
    if not check_file_exists('robots.txt', 'robots.txt file'):
        all_checks_passed = False
    print()
    
    # Check base.html for key SEO elements
    print("2. Checking base.html meta tags...")
    if not check_html_content(
        'templates/base.html',
        ['Erez Asif', 'ICF ACC', 'meta name="author"'],
        'Base template SEO tags'
    ):
        all_checks_passed = False
    print()
    
    # Check for structured data
    print("3. Checking structured data (JSON-LD)...")
    if not check_structured_data('templates/base.html'):
        all_checks_passed = False
    print()
    
    # Check index.html for Erez Asif mentions
    print("4. Checking homepage content...")
    if not check_html_content(
        'templates/index.html',
        ['Erez Asif', '<h1>', 'ICF ACC certified'],
        'Homepage Erez Asif presence'
    ):
        all_checks_passed = False
    print()
    
    # Check routes_main.py for new endpoints
    print("5. Checking routes for SEO endpoints...")
    if not check_html_content(
        'routes_main.py',
        ['/robots.txt', '/sitemap.xml', 'def robots_txt', 'def sitemap_xml'],
        'SEO routes'
    ):
        all_checks_passed = False
    print()
    
    print("=" * 60)
    if all_checks_passed:
        print("✓ ALL CHECKS PASSED!")
        print()
        print("Next steps:")
        print("1. Deploy to production")
        print("2. Verify URLs work:")
        print("   - https://www.yourlifepathways.com/robots.txt")
        print("   - https://www.yourlifepathways.com/sitemap.xml")
        print("3. Submit to Google Search Console")
        print("4. Request indexing")
    else:
        print("⚠ SOME CHECKS FAILED - Review above output")
        return 1
    print("=" * 60)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())