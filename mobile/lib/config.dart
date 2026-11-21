/// App configuration. Override at build/run time, e.g.
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000/api/v1
///
/// The default points at the host machine from the Android emulator.
const String apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000/api/v1',
);

/// How often the duty phone reports its GPS position while on duty.
const Duration pingInterval = Duration(seconds: 15);

/// How often the route screen refreshes (to pick up emergency re-routes).
const Duration routeRefreshInterval = Duration(seconds: 30);
