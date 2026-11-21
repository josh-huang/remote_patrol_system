import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'app_scope.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'services/location_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(DutyPhoneApp(api: ApiClient()));
}

class DutyPhoneApp extends StatefulWidget {
  const DutyPhoneApp({super.key, required this.api});

  final ApiClient api;

  @override
  State<DutyPhoneApp> createState() => _DutyPhoneAppState();
}

class _DutyPhoneAppState extends State<DutyPhoneApp> {
  late final LocationService _location = LocationService(widget.api);
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    widget.api.restoreSession().then((_) => setState(() => _ready = true));
  }

  Future<void> _signOut() async {
    _location.stop();
    await widget.api.logout();
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final theme = ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF3DA58A), brightness: Brightness.dark),
      useMaterial3: true,
    );
    Widget home;
    if (!_ready) {
      home = const Scaffold(body: Center(child: CircularProgressIndicator()));
    } else if (!widget.api.isAuthenticated) {
      home = LoginScreen(api: widget.api, onSignedIn: () => setState(() {}));
    } else {
      home = const HomeShell();
    }
    return AppScope(
      api: widget.api,
      location: _location,
      onSignedOut: _signOut,
      child: MaterialApp(
        title: 'Patrol Duty Phone',
        debugShowCheckedModeBanner: false,
        theme: theme,
        home: home,
      ),
    );
  }
}
