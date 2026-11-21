import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../app_scope.dart';
import '../models.dart';
import '../widgets/photo_picker.dart';

/// Confirms a site visit with photos — replaces sending pictures on WhatsApp.
class CheckInScreen extends StatefulWidget {
  const CheckInScreen({super.key, required this.stop});

  final Stop stop;

  @override
  State<CheckInScreen> createState() => _CheckInScreenState();
}

class _CheckInScreenState extends State<CheckInScreen> {
  final _notes = TextEditingController(text: 'All clear.');
  List<String> _photos = const [];
  bool _busy = false;

  Future<void> _submit() async {
    setState(() => _busy = true);
    try {
      await AppScope.of(context).api.checkIn(widget.stop.id, notes: _notes.text, photos: _photos);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Checked in at ${widget.stop.locationName}')));
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Upload failed. Try again.')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Check in · ${widget.stop.locationName}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Take photos of the premises as proof of visit. They are stored centrally for the command centre.'),
          const SizedBox(height: 16),
          PhotoPicker(onChanged: (p) => _photos = p),
          const SizedBox(height: 16),
          TextField(
            controller: _notes,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Notes', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _busy ? null : _submit,
            icon: const Icon(Icons.task_alt),
            label: Text(_busy ? 'Uploading…' : 'Confirm visit'),
          ),
        ],
      ),
    );
  }
}
