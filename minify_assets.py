#!/usr/bin/env python3
"""
Minify CSS and JS files for production deployment.
Run this before deploying to production to reduce file sizes.
"""

import os
import csscompressor
from jsmin import jsmin

# Directories
STATIC_DIR = 'static'
CSS_DIR = os.path.join(STATIC_DIR, 'css')
JS_DIR = os.path.join(STATIC_DIR, 'js')

def minify_css_file(input_path, output_path):
    """Minify a single CSS file."""
    with open(input_path, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    minified = csscompressor.compress(css_content)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(minified)
    
    original_size = os.path.getsize(input_path)
    minified_size = os.path.getsize(output_path)
    savings = ((original_size - minified_size) / original_size) * 100
    
    print(f"✓ {os.path.basename(input_path)}: {original_size:,} → {minified_size:,} bytes ({savings:.1f}% reduction)")

def minify_js_file(input_path, output_path):
    """Minify a single JS file."""
    with open(input_path, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    minified = jsmin(js_content)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(minified)
    
    original_size = os.path.getsize(input_path)
    minified_size = os.path.getsize(output_path)
    savings = ((original_size - minified_size) / original_size) * 100
    
    print(f"✓ {os.path.basename(input_path)}: {original_size:,} → {minified_size:,} bytes ({savings:.1f}% reduction)")

def main():
    print("🔧 Minifying CSS files...")
    css_files = ['main.css', 'blog.css', 'admin.css']
    for filename in css_files:
        input_path = os.path.join(CSS_DIR, filename)
        output_path = os.path.join(CSS_DIR, filename.replace('.css', '.min.css'))
        
        if os.path.exists(input_path):
            minify_css_file(input_path, output_path)
        else:
            print(f"⚠ Skipping {filename} (not found)")
    
    print("\n🔧 Minifying JS files...")
    js_files = ['main.js', 'blog.js', 'admin.js', 'modal.js', 'util.js']
    for filename in js_files:
        input_path = os.path.join(JS_DIR, filename)
        output_path = os.path.join(JS_DIR, filename.replace('.js', '.min.js'))
        
        if os.path.exists(input_path):
            minify_js_file(input_path, output_path)
        else:
            print(f"⚠ Skipping {filename} (not found)")
    
    print("\n✅ Minification complete!")
    print("💡 Update your templates to use .min.css and .min.js files in production")

if __name__ == '__main__':
    main()
