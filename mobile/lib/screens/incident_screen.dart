import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../app_scope.dart';
import '../models.dart';
import '../widgets/photo_picker.dart';

/// Submit an incident report (text + photos); shows the AI triage result.
class IncidentScreen extends StatefulWidget {
  const IncidentScreen({super.key});

  @override
  State<IncidentScreen> createState() => _IncidentScreenState();
}

class _IncidentScreenState extends State<IncidentScreen> {
  final _description = TextEditingController();
  final _pickerKey = GlobalKey<PhotoPickerState>();
  List<String> _photos = const [];
  List<Stop> _sites = const [];
  int? _locationId;
  bool _busy = false;
  IncidentResult? _result;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_sites.isEmpty) _loadSites();
  }

  Future<void> _loadSites() async {
    try {
      final route = await AppScope.of(context).api.myRoute();
      if (!mounted) return;
      setState(() {
        _sites = route.stops;
        _locationId ??= route.nextStop?.locationId;
      });
    } catch (_) {
      // The report can still be sent without a site.
    }
  }

  Future<void> _submit() async {
    if (_description.text.trim().isEmpty) return;
    setState(() => _busy = true);
    try {
      final result = await AppScope.of(context).api.reportIncident(
            description: _description.text.trim(),
            locationId: _locationId,
            photos: _photos,
          );
      if (!mounted) return;
      _description.clear();
      _pickerKey.currentState?.clear();
      setState(() => _result = result);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not submit. Try again.')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final seen = <int>{};
    final sites = _sites.where((s) => seen.add(s.locationId)).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Report an incident')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          DropdownButtonFormField<int?>(
            initialValue: _locationId,
            decoration: const InputDecoration(labelText: 'Site', border: OutlineInputBorder()),
            items: [
              const DropdownMenuItem<int?>(value: null, child: Text('Not at a patrol site')),
              ...sites.map((s) => DropdownMenuItem<int?>(value: s.locationId, child: Text(s.locationName))),
            ],
            onChanged: (v) => setState(() => _locationId = v),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _description,
            maxLines: 5,
            decoration: const InputDecoration(
              labelText: 'What happened?',
              hintText: 'Describe what you observed…',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          PhotoPicker(key: _pickerKey, onChanged: (p) => _photos = p),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _busy ? null : _submit,
            icon: const Icon(Icons.send),
            label: Text(_busy ? 'Submitting…' : 'Submit report'),
          ),
          if (_result != null) ...[
            const SizedBox(height: 24),
            Card(
              color: _result!.severity == 'critical' || _result!.severity == 'high'
                  ? theme.colorScheme.errorContainer
                  : theme.colorScheme.secondaryContainer,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Report #${_result!.id} received', style: theme.textTheme.titleMedium),
                    Text('AI assessment: ${_result!.severity.toUpperCase()} · ${_result!.category}'),
                    const SizedBox(height: 8),
                    Text(_result!.recommendedAction),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
