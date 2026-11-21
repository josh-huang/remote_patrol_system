import 'dart:async';

import 'package:geolocator/geolocator.dart';

import '../api/api_client.dart';
import '../config.dart';

/// Reports the vehicle's GPS position to the command centre while on duty.
class LocationService {
  LocationService(this._api);

  final ApiClient _api;
  Timer? _timer;
  String? lastError;

  bool get isRunning => _timer != null;

  /// Asks for permission and starts periodic pings. Returns false if location
  /// is unavailable or permission was denied.
  Future<bool> start() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      lastError = 'Location services are turned off.';
      return false;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      lastError = 'Location permission denied.';
      return false;
    }
    lastError = null;
    await _sendPing();
    _timer = Timer.periodic(pingInterval, (_) => _sendPing());
    return true;
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> _sendPing() async {
    try {
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
      );
      await _api.ping(pos.latitude, pos.longitude, pos.speed < 0 ? 0 : pos.speed * 3.6);
      lastError = null;
    } catch (e) {
      lastError = e.toString();
    }
  }
}
