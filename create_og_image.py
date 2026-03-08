#!/usr/bin/env python3
"""
Script to create an optimized Open Graph image (1200x630px) from the horizontal logo.
Minimizes whitespace by using maximum space available.
"""

from PIL import Image
import sys

def create_og_image():
    try:
        # Open the horizontal logo
        logo_path = 'static/images/logo_yourlifepathways_coaching_horizontal.png'
        print(f"Loading logo from: {logo_path}")
        logo = Image.open(logo_path)
        print(f"Logo loaded successfully: {logo.size}, mode: {logo.mode}")
        
        # Convert to RGBA if needed
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        # Get the bounding box to crop whitespace from the original logo
        # We need to find the actual content boundaries
        pixels = logo.load()
        
        # Find bounds of non-white/non-transparent pixels
        min_x, min_y = logo.size
        max_x = max_y = 0
        
        for y in range(logo.size[1]):
            for x in range(logo.size[0]):
                pixel = pixels[x, y]
                # Check if pixel is not white and not fully transparent
                if logo.mode == 'RGBA':
                    if pixel[3] > 0 and (pixel[0] < 250 or pixel[1] < 250 or pixel[2] < 250):
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
                else:
                    if pixel[0] < 250 or pixel[1] < 250 or pixel[2] < 250:
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
        
        # Crop to content with minimal padding
        padding = 5
        bbox = (max(0, min_x - padding), max(0, min_y - padding), 
                min(logo.size[0], max_x + padding + 1), min(logo.size[1], max_y + padding + 1))
        logo_cropped = logo.crop(bbox)
        
        print(f"Original logo size: {logo.size}")
        print(f"Cropped to: {logo_cropped.size}")
        
        # Create the OG image canvas (1200x630px) with white background
        og_width, og_height = 1200, 630
        og_image = Image.new('RGB', (og_width, og_height), (255, 255, 255))
        
        # Calculate scaling to maximize logo size (use 98% of canvas to minimize whitespace)
        target_width = int(og_width * 0.98)
        target_height = int(og_height * 0.98)
        
        # Calculate scale factor maintaining aspect ratio
        logo_aspect = logo_cropped.width / logo_cropped.height
        target_aspect = target_width / target_height
        
        if logo_aspect > target_aspect:
            # Logo is wider - fit to width
            new_width = target_width
            new_height = int(new_width / logo_aspect)
        else:
            # Logo is taller - fit to height
            new_height = target_height
            new_width = int(new_height * logo_aspect)
        
        print(f"Resizing to: {new_width}x{new_height}px")
        
        # Resize the logo
        logo_resized = logo_cropped.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Calculate position to center the logo
        x = (og_width - new_width) // 2
        y = (og_height - new_height) // 2
        
        print(f"Positioning at: ({x}, {y})")
        
        # Paste the logo onto the canvas
        if logo_resized.mode == 'RGBA':
            og_image.paste(logo_resized, (x, y), logo_resized)
        else:
            og_image.paste(logo_resized, (x, y))
        
        # Save the result
        output_path = 'static/images/og_image.png'
        og_image.save(output_path, 'PNG', optimize=True)
        print(f"\n✓ Created optimized OG image: {output_path}")
        print(f"  Canvas size: {og_width}x{og_height}px")
        print(f"  Logo size in image: {new_width}x{new_height}px (98% of canvas)")
        print(f"  Whitespace minimized!")
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    create_og_image()