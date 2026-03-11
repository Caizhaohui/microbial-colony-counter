
import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../models/count_result.dart';

class ResultScreen extends StatelessWidget {
  final File originalImage;
  final CountResult result;

  const ResultScreen({
    super.key,
    required this.originalImage,
    required this.result,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Count Result")),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // Display Images
            if (result.processedImageBase64 != null)
              Image.memory(
                base64Decode(result.processedImageBase64!),
                fit: BoxFit.contain,
              )
            else
              Image.file(originalImage),
            
            const SizedBox(height: 20),
            
            // Display Count
            Text(
              "Count: ${result.count}",
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            
            if (result.processingMs != null)
              Text("Processing Time: ${result.processingMs!.toStringAsFixed(2)} ms"),
              
            if (result.petriCircle != null)
              Text("Petri Dish Detected: Yes"),
              
            const SizedBox(height: 20),
            
            // Warnings
            if (result.warnings.isNotEmpty)
              ...result.warnings.map((w) => Text(w, style: const TextStyle(color: Colors.red))),
              
            // Buttons
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton(
                  onPressed: () {
                    // TODO: Implement save logic
                  },
                  child: const Text("Save"),
                ),
                ElevatedButton(
                  onPressed: () {
                    Navigator.pop(context);
                  },
                  child: const Text("Retake"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
