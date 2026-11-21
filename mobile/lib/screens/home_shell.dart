import 'package:flutter/material.dart';

import 'incident_screen.dart';
import 'messages_screen.dart';
import 'route_screen.dart';

/// Bottom navigation: tonight's route, incident report, command-centre chat.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: const [RouteScreen(), IncidentScreen(), MessagesScreen()],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.route_outlined), selectedIcon: Icon(Icons.route), label: 'Route'),
          NavigationDestination(icon: Icon(Icons.report_outlined), selectedIcon: Icon(Icons.report), label: 'Incident'),
          NavigationDestination(
            icon: Icon(Icons.support_agent_outlined),
            selectedIcon: Icon(Icons.support_agent),
            label: 'Command',
          ),
        ],
      ),
    );
  }
}
