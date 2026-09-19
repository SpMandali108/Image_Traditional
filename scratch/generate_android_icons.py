import os
from PIL import Image, ImageDraw

def generate_icons(source_path, res_dir):
    """Generate Android mipmap icons and round icons from source logo."""
    img = Image.open(source_path).convert("RGBA")
    
    densities = {
        'mipmap-mdpi': 48,
        'mipmap-hdpi': 72,
        'mipmap-xhdpi': 96,
        'mipmap-xxhdpi': 144,
        'mipmap-xxxhdpi': 192
    }
    
    for folder, size in densities.items():
        out_dir = os.path.join(res_dir, folder)
        os.makedirs(out_dir, exist_ok=True)
        
        # Standard square/squircle icon
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(out_dir, 'ic_launcher.png'), 'PNG')
        
        # Round icon with circular mask
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        
        round_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        round_img.paste(resized, (0, 0), mask=mask)
        round_img.save(os.path.join(out_dir, 'ic_launcher_round.png'), 'PNG')
        
        print(f"Generated {folder}/ic_launcher.png and ic_launcher_round.png ({size}x{size})")

    # Splash logo (256x256 and 512x512)
    drawable_dir = os.path.join(res_dir, 'drawable')
    os.makedirs(drawable_dir, exist_ok=True)
    splash_logo = img.resize((256, 256), Image.Resampling.LANCZOS)
    splash_logo.save(os.path.join(drawable_dir, 'splash_logo.png'), 'PNG')
    print("Generated drawable/splash_logo.png (256x256)")

if __name__ == '__main__':
    src = os.path.join('website', 'static', 'Icons', 'icon-512x512.png')
    res = os.path.join('android', 'app', 'src', 'main', 'res')
    generate_icons(src, res)
