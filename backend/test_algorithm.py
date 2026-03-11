
import cv2
import os
import sys

# Add the parent directory to sys.path to allow importing from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.algorithm import process_image

def test_image(image_path):
    print(f"Testing image: {image_path}")
    if not os.path.exists(image_path):
        print("Image not found.")
        return

    image = cv2.imread(image_path)
    if image is None:
        print("Failed to read image.")
        return

    # Test 1: Default parameters
    print("Test 1: Default parameters")
    result = process_image(image)
    if result["error"]:
        print(f"Error: {result['error']}")
    else:
        print(f"Count: {result['count']}")
        # Save output for visual inspection
        output_path = f"test_result_{os.path.basename(image_path)}"
        cv2.imwrite(output_path, result["processed_image"])
        print(f"Saved processed image to {output_path}")

    # Test 2: With Petri Dish Detection
    print("Test 2: With Petri Dish Detection")
    result = process_image(image, detect_petri_dish=True)
    if result["error"]:
        print(f"Error: {result['error']}")
    else:
        print(f"Count: {result['count']}")
        if result["petri_circle"]:
            print(f"Petri Dish Detected: {result['petri_circle']}")
        
        output_path = f"test_result_petri_{os.path.basename(image_path)}"
        cv2.imwrite(output_path, result["processed_image"])
        print(f"Saved processed image to {output_path}")

if __name__ == "__main__":
    # Assuming the script is run from the project root or backend directory
    # Adjust paths as necessary
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test1 = os.path.join(base_dir, "test1.jpg")
    test2 = os.path.join(base_dir, "test2.jpg")

    test_image(test1)
    print("-" * 20)
    test_image(test2)
