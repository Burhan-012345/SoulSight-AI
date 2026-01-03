#!/usr/bin/env python3
"""
Generate OG (Open Graph) image for SoulSight AI
Creates a 1200x630 PNG image for social media sharing
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_og_image():
    """Create OG image for social media sharing"""
    
    # Create directory if it doesn't exist
    os.makedirs('static/images', exist_ok=True)
    
    # Image dimensions for OG image (Facebook/Twitter)
    width = 1200
    height = 630
    
    # Create new image with gradient background
    image = Image.new('RGB', (width, height), color='#FFFFFF')
    draw = ImageDraw.Draw(image)
    
    # Create gradient background
    for y in range(height):
        # Interpolate between two colors
        r1, g1, b1 = 102, 126, 234  # #667eea
        r2, g2, b2 = 118, 75, 162   # #764ba2
        
        ratio = y / height
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Add decorative elements
    # Circles
    for i in range(5):
        x = 150 + i * 200
        y = 200 + i * 30
        size = 80 + i * 20
        draw.ellipse(
            [(x - size//2, y - size//2), (x + size//2, y + size//2)],
            fill=(255, 255, 255, 30),
            outline=(255, 255, 255, 60)
        )
    
    # Logo/eye icon
    eye_center_x = width // 2
    eye_center_y = height // 2 - 50
    eye_radius = 80
    
    # Outer eye circle
    draw.ellipse(
        [(eye_center_x - eye_radius, eye_center_y - eye_radius),
         (eye_center_x + eye_radius, eye_center_y + eye_radius)],
        fill=(255, 255, 255, 180),
        outline=(255, 255, 255, 220)
    )
    
    # Inner eye circle
    draw.ellipse(
        [(eye_center_x - eye_radius//2, eye_center_y - eye_radius//2),
         (eye_center_x + eye_radius//2, eye_center_y + eye_radius//2)],
        fill=(102, 126, 234),
        outline=(255, 255, 255, 220)
    )
    
    # Pupil
    draw.ellipse(
        [(eye_center_x - eye_radius//4, eye_center_y - eye_radius//4),
         (eye_center_x + eye_radius//4, eye_center_y + eye_radius//4)],
        fill=(246, 135, 179),  # Accent color
        outline=(255, 255, 255, 220)
    )
    
    # Try to use system fonts, fallback to default
    try:
        title_font = ImageFont.truetype("arial.ttf", 72)
        subtitle_font = ImageFont.truetype("arial.ttf", 36)
        tagline_font = ImageFont.truetype("arial.ttf", 28)
    except:
        # Fallback to default font
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        tagline_font = ImageFont.load_default()
    
    # Add title
    title = "SoulSight AI"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    title_y = eye_center_y + eye_radius + 50
    
    # Draw text with shadow
    draw.text((title_x + 3, title_y + 3), title, fill=(0, 0, 0, 100), font=title_font)
    draw.text((title_x, title_y), title, fill=(255, 255, 255), font=title_font)
    
    # Add subtitle
    subtitle = "See the Soul in Every Image"
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = (width - subtitle_width) // 2
    subtitle_y = title_y + 80
    
    draw.text((subtitle_x + 2, subtitle_y + 2), subtitle, fill=(0, 0, 0, 100), font=subtitle_font)
    draw.text((subtitle_x, subtitle_y), subtitle, fill=(255, 255, 255, 220), font=subtitle_font)
    
    # Add tagline
    tagline = "AI-powered image analysis with emotional intelligence"
    tagline_bbox = draw.textbbox((0, 0), tagline, font=tagline_font)
    tagline_width = tagline_bbox[2] - tagline_bbox[0]
    tagline_x = (width - tagline_width) // 2
    tagline_y = subtitle_y + 60
    
    draw.text((tagline_x + 1, tagline_y + 1), tagline, fill=(0, 0, 0, 80), font=tagline_font)
    draw.text((tagline_x, tagline_y), tagline, fill=(255, 255, 255, 180), font=tagline_font)
    
    # Add URL at bottom
    url = "soulsight.ai"
    url_bbox = draw.textbbox((0, 0), url, font=tagline_font)
    url_width = url_bbox[2] - url_bbox[0]
    url_x = (width - url_width) // 2
    url_y = height - 60
    
    draw.text((url_x + 1, url_y + 1), url, fill=(0, 0, 0, 80), font=tagline_font)
    draw.text((url_x, url_y), url, fill=(255, 255, 255), font=tagline_font)
    
    # Add decorative line under URL
    line_y = url_y + 35
    line_width = 200
    line_x = (width - line_width) // 2
    
    draw.line(
        [(line_x, line_y), (line_x + line_width, line_y)],
        fill=(246, 135, 179),  # Accent color
        width=3
    )
    
    # Save the image
    output_path = 'static/images/og-image.png'
    image.save(output_path, 'PNG', quality=95)
    print(f"OG image created successfully: {output_path}")
    print(f"Dimensions: {width}x{height} pixels")
    
    # Show image info
    from pathlib import Path
    file_size = Path(output_path).stat().st_size / 1024  # KB
    print(f"File size: {file_size:.1f} KB")
    
    return output_path

def create_favicon():
    """Create favicon and related icons"""
    
    # Create 32x32 favicon
    favicon = Image.new('RGBA', (32, 32), (102, 126, 234, 255))
    draw = ImageDraw.Draw(favicon)
    
    # Draw simple eye icon
    draw.ellipse([(6, 6), (26, 26)], fill=(255, 255, 255, 255))
    draw.ellipse([(12, 12), (20, 20)], fill=(102, 126, 234, 255))
    draw.ellipse([(15, 15), (17, 17)], fill=(246, 135, 179, 255))
    
    favicon.save('static/images/favicon-32x32.png')
    
    # Create 16x16 favicon
    favicon16 = Image.new('RGBA', (16, 16), (102, 126, 234, 255))
    draw16 = ImageDraw.Draw(favicon16)
    draw16.ellipse([(3, 3), (13, 13)], fill=(255, 255, 255, 255))
    
    favicon16.save('static/images/favicon-16x16.png')
    
    # Create apple touch icon (180x180)
    apple_icon = Image.new('RGBA', (180, 180), (102, 126, 234, 255))
    draw_apple = ImageDraw.Draw(apple_icon)
    
    # Draw eye icon
    draw_apple.ellipse([(30, 30), (150, 150)], fill=(255, 255, 255, 255))
    draw_apple.ellipse([(60, 60), (120, 120)], fill=(102, 126, 234, 255))
    draw_apple.ellipse([(85, 85), (95, 95)], fill=(246, 135, 179, 255))
    
    # Add text
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        draw_apple.text((45, 155), "SS", fill=(255, 255, 255), font=font)
    except:
        pass
    
    apple_icon.save('static/images/apple-touch-icon.png')
    
    print("Favicon images created successfully!")

def create_simple_favicon_ico():
    """Create a simple .ico file"""
    # Create 32x32 icon
    img = Image.new('RGBA', (32, 32), (102, 126, 234, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([(6, 6), (26, 26)], fill=(255, 255, 255, 255))
    
    # Save as .ico
    img.save('static/images/favicon.ico', format='ICO', sizes=[(32, 32)])
    print("ICO favicon created successfully!")

def create_web_manifest():
    """Create web app manifest"""
    import json
    
    manifest = {
        "name": "SoulSight AI",
        "short_name": "SoulSight",
        "description": "See the soul in every image through AI",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#667eea",
        "theme_color": "#667eea",
        "icons": [
            {
                "src": "/static/images/favicon-32x32.png",
                "sizes": "32x32",
                "type": "image/png"
            },
            {
                "src": "/static/images/favicon-16x16.png",
                "sizes": "16x16",
                "type": "image/png"
            },
            {
                "src": "/static/images/apple-touch-icon.png",
                "sizes": "180x180",
                "type": "image/png"
            }
        ]
    }
    
    with open('static/images/site.webmanifest', 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print("Web manifest created successfully!")

def create_all_assets():
    """Create all necessary assets"""
    print("Creating all assets for SoulSight AI...")
    print("-" * 50)
    
    # Create images directory
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('static/uploads', exist_ok=True)
    
    # Create OG image
    create_og_image()
    print("-" * 50)
    
    # Create favicon and related icons
    create_favicon()
    create_simple_favicon_ico()
    print("-" * 50)
    
    # Create web manifest
    create_web_manifest()
    print("-" * 50)
    
    print("\n✅ All assets created successfully!")
    print("\nAssets created:")
    print("  • static/images/og-image.png (1200x630)")
    print("  • static/images/favicon.ico")
    print("  • static/images/favicon-16x16.png")
    print("  • static/images/favicon-32x32.png")
    print("  • static/images/apple-touch-icon.png")
    print("  • static/images/site.webmanifest")
    
    # Verify files exist
    import glob
    files = glob.glob('static/images/*')
    print(f"\nTotal files in static/images/: {len(files)}")

if __name__ == '__main__':
    create_all_assets()