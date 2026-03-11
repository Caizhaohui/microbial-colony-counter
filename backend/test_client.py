
import requests
import os
import sys

def test_api(image_path):
    url = "http://127.0.0.1:8000/api/v1/count"
    print(f"Testing image: {image_path}")
    if not os.path.exists(image_path):
        print("Image not found.")
        return

    # Prepare data
    files = {'image': open(image_path, 'rb')}
    data = {
        'detect_petri_dish': 'true',
        'thresh_method': 'adaptive',
        'adaptive_block_size': 11,
        'adaptive_c': 2,
        'blur_ksize': 7,
        'min_area': 50,
        'max_area': 5000,
        'min_distance_from_edge': 20
    }

    try:
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            result = response.json()
            print(f"Status Code: {response.status_code}")
            print(f"Count: {result['count']}")
            print(f"Processing Time: {result['processing_ms']} ms")
            if result.get('petri_circle'):
                print(f"Petri Dish: {result['petri_circle']}")
            else:
                print("No Petri Dish Detected")
            
            # Save processed image if available
            # Note: We are not decoding base64 here for brevity, but could if needed.
            if result.get('processed_image_base64'):
                print("Received processed image (base64)")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Request failed: {e}")
    finally:
        files['image'].close()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test1 = os.path.join(base_dir, "test1.jpg")
    test2 = os.path.join(base_dir, "test2.jpg")

    print("Test 1:")
    test_api(test1)
    print("-" * 20)
    print("Test 2:")
    test_api(test2)
