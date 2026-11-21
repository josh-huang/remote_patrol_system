import 'dart:async';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../app_scope.dart';
import '../models.dart';

/// Contact the command centre: message thread + one-tap phone call.
class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  final _text = TextEditingController();
  final _scroll = ScrollController();
  List<ChatMessage> _messages = const [];
  String _phone = '';
  Timer? _timer;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_timer == null) {
      _load();
      _timer = Timer.periodic(const Duration(seconds: 10), (_) => _load());
      AppScope.of(context).api.get('/messages/contact/').then((data) {
        if (mounted) setState(() => _phone = (data as Map)['command_centre_phone'] as String? ?? '');
      }).catchError((_) {});
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    final api = AppScope.of(context).api;
    try {
      final messages = await api.messages();
      if (!mounted) return;
      final grew = messages.length != _messages.length;
      setState(() => _messages = messages);
      await api.markMessagesRead();
      if (grew) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
        });
      }
    } catch (_) {
      // Keep showing the last messages while offline.
    }
  }

  Future<void> _send() async {
    final body = _text.text.trim();
    if (body.isEmpty) return;
    _text.clear();
    await AppScope.of(context).api.sendMessage(body);
    _load();
  }

  Future<void> _call() async {
    if (_phone.isEmpty) return;
    await launchUrl(Uri(scheme: 'tel', path: _phone.replaceAll(' ', '')));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Command centre'),
        actions: [
          TextButton.icon(
            onPressed: _phone.isEmpty ? null : _call,
            icon: const Icon(Icons.call),
            label: const Text('Call'),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (context, i) {
                final m = _messages[i];
                final mine = !m.fromCommandCentre;
                return Align(
                  alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                    decoration: BoxDecoration(
                      color: mine ? theme.colorScheme.primaryContainer : theme.colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(m.body),
                        Text(
                          '${m.senderName ?? (m.fromCommandCentre ? 'Command Centre' : 'You')} · '
                          '${TimeOfDay.fromDateTime(m.createdAt.toLocal()).format(context)}',
                          style: theme.textTheme.labelSmall,
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _text,
                      decoration: const InputDecoration(hintText: 'Message the command centre…', border: OutlineInputBorder()),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(onPressed: _send, icon: const Icon(Icons.send)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
