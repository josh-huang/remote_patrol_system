import 'package:flutter/widgets.dart';

import 'api/api_client.dart';
import 'services/location_service.dart';

/// Makes the API client and location service available to every screen.
class AppScope extends InheritedWidget {
  const AppScope({
    super.key,
    required this.api,
    required this.location,
    required this.onSignedOut,
    required super.child,
  });

  final ApiClient api;
  final LocationService location;
  final VoidCallback onSignedOut;

  static AppScope of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope not found in widget tree');
    return scope!;
  }

  @override
  bool updateShouldNotify(AppScope oldWidget) => api != oldWidget.api;
}
