import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

/// Lets the guard take or choose photos; reports the selected file paths.
class PhotoPicker extends StatefulWidget {
  const PhotoPicker({super.key, required this.onChanged, this.maxPhotos = 6});

  final ValueChanged<List<String>> onChanged;
  final int maxPhotos;

  @override
  State<PhotoPicker> createState() => PhotoPickerState();
}

class PhotoPickerState extends State<PhotoPicker> {
  final _picker = ImagePicker();
  final List<String> _paths = [];

  void clear() {
    setState(_paths.clear);
    widget.onChanged(const []);
  }

  Future<void> _add(ImageSource source) async {
    final file = await _picker.pickImage(source: source, maxWidth: 1920, imageQuality: 80);
    if (file == null) return;
    setState(() => _paths.add(file.path));
    widget.onChanged(List.unmodifiable(_paths));
  }

  @override
  Widget build(BuildContext context) {
    final canAdd = _paths.length < widget.maxPhotos;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            OutlinedButton.icon(
              onPressed: canAdd ? () => _add(ImageSource.camera) : null,
              icon: const Icon(Icons.photo_camera_outlined),
              label: const Text('Take photo'),
            ),
            const SizedBox(width: 8),
            TextButton.icon(
              onPressed: canAdd ? () => _add(ImageSource.gallery) : null,
              icon: const Icon(Icons.photo_library_outlined),
              label: const Text('Gallery'),
            ),
          ],
        ),
        if (_paths.isNotEmpty)
          SizedBox(
            height: 92,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _paths.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, i) => Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.file(File(_paths[i]), width: 92, height: 92, fit: BoxFit.cover),
                  ),
                  Positioned(
                    right: 0,
                    top: 0,
                    child: IconButton.filledTonal(
                      visualDensity: VisualDensity.compact,
                      iconSize: 16,
                      icon: const Icon(Icons.close),
                      onPressed: () {
                        setState(() => _paths.removeAt(i));
                        widget.onChanged(List.unmodifiable(_paths));
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
