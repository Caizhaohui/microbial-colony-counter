
class CountResult {
  final int count;
  final double? qualityScore;
  final List<String> warnings;
  final String? binaryImageBase64;
  final String? processedImageBase64;
  final List<int>? petriCircle;
  final double? processingMs;

  CountResult({
    required this.count,
    this.qualityScore,
    this.warnings = const [],
    this.binaryImageBase64,
    this.processedImageBase64,
    this.petriCircle,
    this.processingMs,
  });

  factory CountResult.fromJson(Map<String, dynamic> json) {
    return CountResult(
      count: json['count'],
      qualityScore: json['quality_score'],
      warnings: List<String>.from(json['warnings'] ?? []),
      binaryImageBase64: json['binary_image_base64'],
      processedImageBase64: json['processed_image_base64'],
      petriCircle: json['petri_circle'] != null
          ? List<int>.from(json['petri_circle'])
          : null,
      processingMs: json['processing_ms'],
    );
  }
}
