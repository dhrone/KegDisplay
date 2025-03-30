import os
import shutil
from pathlib import Path
import unittest
from PIL import Image, ImageDraw
from tests.test_renderer_exact_match import TestRendererExactMatch

def extract_exact_match_images():
    """Run the exact match test and save all images to a permanent location."""
    # Create output directory
    output_dir = Path("exact_match_images")
    output_dir.mkdir(exist_ok=True)
    
    # Create and run the test
    test = TestRendererExactMatch('test_exact_visual_match')
    
    # Run setup to create directories and files
    test.setUp()
    
    try:
        # Record the test directory before running the test
        test_dir = test.test_dir
        print(f"Test directory: {test_dir}")
        
        # Check template content
        print("\nTemplate content (checking for proper text positioning):")
        with open(test.template_path, 'r') as f:
            template_content = f.read()
            print(template_content)
        
        # Run the test (but catch any assertion errors)
        try:
            test.test_exact_visual_match()
            print("Test passed")
        except Exception as e:
            print(f"Test error (expected): {e}")
        
        # Create debug versions of the images to visualize placement
        create_debug_images(test, output_dir)
        
        # Copy reference image
        ref_img_path = test_dir / "reference" / "exact_beer_info.png"
        if ref_img_path.exists():
            dest = output_dir / "reference_image.png"
            shutil.copy(ref_img_path, dest)
            print(f"Copied reference image to: {dest}")
            
            # Create a larger version for better visibility
            img = Image.open(ref_img_path)
            img_large = img.resize((400, 64), Image.NEAREST)
            img_large.save(output_dir / "reference_image_large.png")
            print(f"Created enlarged reference image")
        
        # Copy actual rendered image
        actual_img_path = test_dir / "output" / "actual_exact_match.png"
        if actual_img_path.exists():
            dest = output_dir / "rendered_image.png"
            shutil.copy(actual_img_path, dest)
            print(f"Copied rendered image to: {dest}")
            
            # Create a larger version for better visibility
            img = Image.open(actual_img_path)
            img_large = img.resize((400, 64), Image.NEAREST)
            img_large.save(output_dir / "rendered_image_large.png")
            print(f"Created enlarged rendered image")
        
        # Copy difference image
        diff_img_path = test_dir / "output" / "exact_diff.png"
        if diff_img_path.exists():
            dest = output_dir / "difference_image.png"
            shutil.copy(diff_img_path, dest)
            print(f"Copied difference image to: {dest}")
            
            # Create a larger version for better visibility
            img = Image.open(diff_img_path)
            img_large = img.resize((400, 64), Image.NEAREST)
            img_large.save(output_dir / "difference_image_large.png")
            print(f"Created enlarged difference image")
        
        # Copy baseline image
        baseline_path = test.baseline_dir / "beer_info_baseline.png"
        if baseline_path.exists():
            dest = output_dir / "baseline_image.png"
            shutil.copy(baseline_path, dest)
            print(f"Copied baseline image to: {dest}")
            
            # Create a larger version for better visibility
            img = Image.open(baseline_path)
            img_large = img.resize((400, 64), Image.NEAREST)
            img_large.save(output_dir / "baseline_image_large.png")
            print(f"Created enlarged baseline image")
        
        # Create an HTML file to view all images
        create_comparison_html(output_dir)
    
    finally:
        # Clean up
        test.tearDown()
    
    return output_dir

def create_debug_images(test, output_dir):
    """Create debug versions of the images with colored outlines to show placement."""
    # Create a debug image to understand what's being rendered
    debug_img = Image.new('RGB', (100, 16), color=(0, 0, 0))
    draw = ImageDraw.Draw(debug_img)
    
    # Draw boxes where text should be
    # Top left - Beer name at [0, 0, lt] - Origin at left-top corner, no offset
    draw.rectangle([(0, 0), (50, 8)], outline=(255, 0, 0))
    draw.text((2, 1), "Test IPA", fill=(255, 255, 255))
    
    # Top right - ABV at [-5, 0, rt] - Origin at right-top corner, offset 5px left
    draw.rectangle([(50, 0), (99, 8)], outline=(0, 255, 0))
    draw.text((75, 1), "6.5%", fill=(255, 255, 255))
    
    # Bottom left - Description at [0, 0, lb] - Origin at left-bottom corner, no offset
    draw.rectangle([(0, 8), (99, 15)], outline=(0, 0, 255))
    draw.text((2, 9), "A hoppy beer", fill=(255, 255, 255))
    
    # Save the debug image
    debug_path = output_dir / "debug_expected_layout.png"
    debug_img.save(debug_path)
    debug_large = debug_img.resize((400, 64), Image.NEAREST)
    debug_large.save(output_dir / "debug_expected_layout_large.png")
    print(f"Created debug layout image at: {debug_path}")
    
    # Also create a version of the reference image with a black background for clarity
    try:
        ref_img = Image.open(test.reference_dir / "exact_beer_info.png")
        ref_debug = Image.new('RGB', ref_img.size, color=(0, 0, 0))
        ref_debug.paste(ref_img, (0, 0), ref_img)
        ref_debug.save(output_dir / "reference_with_bg.png")
        ref_debug_large = ref_debug.resize((400, 64), Image.NEAREST)
        ref_debug_large.save(output_dir / "reference_with_bg_large.png")
        print("Created reference image with background")
    except Exception as e:
        print(f"Error creating reference debug image: {e}")

def create_comparison_html(output_dir):
    """Create an HTML file to display all images side by side."""
    html_path = output_dir / "exact_match_comparison.html"
    
    with open(html_path, 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exact Visual Match Comparison</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1, h2, h3 {
            color: #333;
        }
        .comparison {
            display: flex;
            flex-direction: column;
            gap: 30px;
            margin: 20px 0;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .image-container {
            display: flex;
            gap: 20px;
            align-items: center;
            justify-content: center;
            flex-wrap: wrap;
        }
        .image-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 20px;
        }
        .image-wrapper {
            background-color: #222;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
            margin-bottom: 10px;
        }
        .image-box img {
            image-rendering: pixelated;
            display: block;
        }
        p {
            max-width: 800px;
            line-height: 1.5;
        }
        .color-key {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }
        .color-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .color-box {
            width: 20px;
            height: 20px;
            border: 1px solid #333;
        }
        .white {
            background-color: white;
        }
        .transparent {
            background-color: transparent;
            position: relative;
        }
        .transparent:before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: repeating-linear-gradient(
                45deg,
                rgba(255, 255, 255, 0.2),
                rgba(255, 255, 255, 0.2) 5px,
                rgba(255, 255, 255, 0.4) 5px,
                rgba(255, 255, 255, 0.4) 10px
            );
        }
    </style>
</head>
<body>
    <h1>Exact Visual Match Comparison</h1>
    
    <div class="comparison">
        <h2>Color Key</h2>
        <div class="color-key">
            <div class="color-item">
                <div class="color-box white"></div>
                <span>White pixels (text)</span>
            </div>
            <div class="color-item">
                <div class="color-box transparent"></div>
                <span>Transparent background (appears black in the images below)</span>
            </div>
        </div>
        <p><strong>Note:</strong> The test images use white text on a transparent background. To make them visible, we're displaying them on a dark background in this comparison.</p>
    </div>
    
    <div class="comparison">
        <h2>Debug Layout</h2>
        <p>This shows the expected layout with colored boxes indicating where text should appear:</p>
        <div class="image-container">
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="debug_expected_layout.png" alt="Debug Layout">
                </div>
                <span>Expected Layout</span>
            </div>
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="debug_expected_layout_large.png" alt="Debug Layout (Enlarged)">
                </div>
                <span>Expected Layout (Enlarged)</span>
            </div>
        </div>
        <div class="image-container">
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="reference_with_bg.png" alt="Reference with Background">
                </div>
                <span>Reference with Background</span>
            </div>
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="reference_with_bg_large.png" alt="Reference with Background (Enlarged)">
                </div>
                <span>Reference with Background (Enlarged)</span>
            </div>
        </div>
    </div>
    
    <div class="comparison">
        <h2>Original Size (100x16 pixels)</h2>
        <div class="image-container">
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="reference_image.png" alt="Reference Image">
                </div>
                <span>Reference Image</span>
            </div>
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="rendered_image.png" alt="Rendered Image">
                </div>
                <span>Rendered Image</span>
            </div>
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="difference_image.png" alt="Difference Image">
                </div>
                <span>Difference Image</span>
            </div>
        </div>
        
        <h2>Enlarged (4x) for Better Visibility</h2>
        <div class="image-container">
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="reference_image_large.png" alt="Reference Image (Enlarged)">
                </div>
                <span>Reference Image</span>
            </div>
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="rendered_image_large.png" alt="Rendered Image (Enlarged)">
                </div>
                <span>Rendered Image</span>
            </div>
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="difference_image_large.png" alt="Difference Image (Enlarged)">
                </div>
                <span>Difference Image</span>
            </div>
        </div>
    </div>
    
    <div class="comparison">
        <h2>Baseline Image</h2>
        <p>The baseline image is saved in the repository for future tests.</p>
        <div class="image-container">
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="baseline_image.png" alt="Baseline Image">
                </div>
                <span>Baseline Image (Original Size)</span>
            </div>
            <div class="image-box">
                <div class="image-wrapper">
                    <img src="baseline_image_large.png" alt="Baseline Image (Enlarged)">
                </div>
                <span>Baseline Image (Enlarged)</span>
            </div>
        </div>
    </div>
    
    <div class="comparison">
        <h2>Key Points</h2>
        <ul>
            <li>The reference and rendered images should be 100% identical, showing white text on a transparent background</li>
            <li>The difference image should be completely transparent (appears as black with our dark background) because there are no differences</li>
            <li>The baseline image is saved in the repository for comparing against future renders</li>
            <li>All these images use a deterministic template with fixed text values to ensure reproducibility</li>
        </ul>
        
        <h3>Image Details</h3>
        <ul>
            <li>Size: 100x16 pixels</li>
            <li>Format: RGBA (includes transparency channel)</li>
            <li>Content: "Test IPA" (top left), "6.5%" (top right), "A hoppy test beer" (bottom)</li>
        </ul>
    </div>
</body>
</html>""")
    
    print(f"Created comparison HTML at: {html_path}")

if __name__ == "__main__":
    output_path = extract_exact_match_images()
    print(f"\nImages extracted to: {output_path}")
    print("The following files were created:")
    
    for file in os.listdir(output_path):
        print(f"  - {file}")
    
    print(f"\nOpen {output_path}/exact_match_comparison.html to view the images") 