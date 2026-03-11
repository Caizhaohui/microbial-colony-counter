
import 'dart:io';
import 'package:dio/dio.dart';
import '../models/count_result.dart';

class ApiService {
  // Replace with your computer's IP address when running on physical device
  // e.g., "http://192.168.1.100:8000"
  // Local WLAN IP: 172.16.103.193
  final String baseUrl = "http://172.16.103.193:8000"; 
  final Dio _dio = Dio();

  Future<CountResult> countColonies(
    File imageFile, {
    bool detectPetriDish = true,
    String threshMethod = "adaptive",
    int minArea = 50,
    int maxArea = 5000,
  }) async {
    try {
      String fileName = imageFile.path.split('/').last;
      FormData formData = FormData.fromMap({
        "image": await MultipartFile.fromFile(imageFile.path, filename: fileName),
        "detect_petri_dish": detectPetriDish,
        "thresh_method": threshMethod,
        "min_area": minArea,
        "max_area": maxArea,
        "blur_ksize": 7,
        "adaptive_block_size": 11,
        "adaptive_c": 2,
        "min_distance_from_edge": 20,
      });

      Response response = await _dio.post(
        "$baseUrl/api/v1/count",
        data: formData,
        options: Options(
          sendTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
        ),
      );

      if (response.statusCode == 200) {
        return CountResult.fromJson(response.data);
      } else {
        throw Exception("Server error: ${response.statusCode}");
      }
    } catch (e) {
      throw Exception("Failed to count colonies: $e");
    }
  }
}
