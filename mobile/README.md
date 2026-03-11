
# Mobile App for Microbial Colony Counter

This is a Flutter application that communicates with the Python backend to count colonies.

## Prerequisites

- [Flutter SDK](https://flutter.dev/docs/get-started/install) installed.
- Android Studio or VS Code with Flutter extensions.
- An Android device or emulator.

## Setup

1.  Navigate to this directory:
    ```bash
    cd mobile
    ```

2.  Add dependencies to `pubspec.yaml` (if not already there, create one):
    ```yaml
    name: colony_counter_mobile
    description: A new Flutter project.
    version: 1.0.0+1
    environment:
      sdk: '>=3.0.0 <4.0.0'
    dependencies:
      flutter:
        sdk: flutter
      dio: ^5.0.0
      image_picker: ^1.0.0
      camera: ^0.10.0
      permission_handler: ^11.0.0
      path_provider: ^2.0.0
    ```

3.  Install dependencies:
    ```bash
    flutter pub get
    ```

4.  **Configure Backend URL**:
    Open `lib/services/api_service.dart` and update `baseUrl` to your computer's IP address (e.g., `http://192.168.1.X:8000`).
    - If running on Android Emulator, use `http://10.0.2.2:8000`.
    - If running on physical device, ensure both phone and computer are on the same Wi-Fi network.

5.  **Run the App**:
    ```bash
    flutter run
    ```

## Features

- **Take Photo**: Use the camera to capture a Petri dish image.
- **Pick from Gallery**: Select an existing image.
- **Automatic Counting**: Uploads the image to the backend and displays the count.
- **Result Visualization**: Shows the processed image with contours and the total count.

## Notes

- Ensure the backend server is running (`uvicorn backend.main:app --host 0.0.0.0 --port 8000`).
- Check Android permissions (Camera, Storage) in `AndroidManifest.xml`.
