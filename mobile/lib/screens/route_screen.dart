import 'dart:async';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/api_client.dart';
import '../app_scope.dart';
import '../config.dart';
import '../models.dart';
import 'check_in_screen.dart';

/// Tonight's route plan and the next location to go to.
class RouteScreen extends StatefulWidget {
  const RouteScreen({super.key});

  @override
  State<RouteScreen> createState() => _RouteScreenState();
}

class _RouteScreenState extends State<RouteScreen> {
  RouteInfo? _route;
  String? _error;
  Timer? _timer;
  int? _lastNextStopId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_timer == null) {
      _load();
      _timer = Timer.periodic(routeRefreshInterval, (_) => _load());
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final route = await AppScope.of(context).api.myRoute();
      if (!mounted) return;
      final next = route.nextStop;
      // Tell the driver when the command centre re-routes them.
      if (_lastNextStopId != null && next != null && next.id != _lastNextStopId && next.isEmergency) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: Theme.of(context).colorScheme.error,
            content: Text('EMERGENCY: proceed to ${next.locationName}. Your route has been re-planned.'),
          ),
        );
      }
      _lastNextStopId = next?.id;
      setState(() {
        _route = route;
        _error = null;
      });
    } on ApiException catch (e) {
      if (e.statusCode == 401 && mounted) AppScope.of(context).onSignedOut();
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Cannot reach the command centre.');
    }
  }

  Future<void> _navigate(Stop stop) async {
    final uri = Uri.parse(
      'https://www.google.com/maps/dir/?api=1&destination=${stop.latitude},${stop.longitude}&travelmode=driving',
    );
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  Future<void> _checkIn(Stop stop) async {
    final done = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => CheckInScreen(stop: stop)),
    );
    if (done == true) _load();
  }

  Future<void> _toggleDuty(bool on) async {
    final location = AppScope.of(context).location;
    if (on) {
      final ok = await location.start();
      if (!ok && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(location.lastError ?? 'GPS unavailable')));
      }
    } else {
      location.stop();
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final scope = AppScope.of(context);
    final route = _route;
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(route?.vehicle.plateNumber ?? 'Patrol route'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load, tooltip: 'Refresh'),
          IconButton(icon: const Icon(Icons.logout), onPressed: scope.onSignedOut, tooltip: 'Sign out'),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('On duty — share live location'),
              subtitle: Text(scope.location.isRunning ? 'Reporting GPS to the command centre' : 'Location sharing is off'),
              value: scope.location.isRunning,
              onChanged: _toggleDuty,
            ),
            if (_error != null)
              Card(
                color: theme.colorScheme.errorContainer,
                child: ListTile(leading: const Icon(Icons.wifi_off), title: Text(_error!)),
              ),
            if (route == null && _error == null) const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
            if (route != null) ...[
              Text(route.planName ?? 'No active patrol plan', style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              LinearProgressIndicator(value: route.total == 0 ? 0 : route.visited / route.total, minHeight: 8),
              const SizedBox(height: 4),
              Text('${route.visited}/${route.total} sites · ${route.remainingKm.toStringAsFixed(1)} km to go'),
              const SizedBox(height: 16),
              if (route.nextStop != null) _NextStopCard(stop: route.nextStop!, onNavigate: _navigate, onCheckIn: _checkIn),
              if (route.nextStop == null && route.total > 0)
                const Card(child: ListTile(leading: Icon(Icons.check_circle), title: Text('All sites patrolled. Good work!'))),
              const SizedBox(height: 16),
              Text('Route plan', style: theme.textTheme.titleMedium),
              ...route.stops.map((s) => _StopTile(stop: s, isNext: s.id == route.nextStop?.id)),
            ],
          ],
        ),
      ),
    );
  }
}

class _NextStopCard extends StatelessWidget {
  const _NextStopCard({required this.stop, required this.onNavigate, required this.onCheckIn});

  final Stop stop;
  final ValueChanged<Stop> onNavigate;
  final ValueChanged<Stop> onCheckIn;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final urgent = stop.isEmergency;
    return Card(
      color: urgent ? theme.colorScheme.errorContainer : theme.colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(urgent ? 'EMERGENCY — GO NOW' : 'NEXT LOCATION', style: theme.textTheme.labelLarge),
            const SizedBox(height: 4),
            Text(stop.locationName, style: theme.textTheme.headlineSmall),
            if (stop.address.isNotEmpty) Text(stop.address),
            Text('${stop.legDistanceKm.toStringAsFixed(1)} km · priority ${stop.priority}'),
            const SizedBox(height: 12),
            Row(
              children: [
                FilledButton.icon(
                  onPressed: () => onNavigate(stop),
                  icon: const Icon(Icons.navigation_outlined),
                  label: const Text('Navigate'),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () => onCheckIn(stop),
                  icon: const Icon(Icons.task_alt),
                  label: const Text('Check in'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StopTile extends StatelessWidget {
  const _StopTile({required this.stop, required this.isNext});

  final Stop stop;
  final bool isNext;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
        backgroundColor: stop.isVisited
            ? theme.colorScheme.surfaceContainerHighest
            : stop.isEmergency
                ? theme.colorScheme.error
                : isNext
                    ? theme.colorScheme.primary
                    : theme.colorScheme.secondaryContainer,
        child: stop.isVisited ? const Icon(Icons.check, size: 18) : Text('${stop.order + 1}'),
      ),
      title: Text(
        stop.locationName,
        style: stop.isVisited ? const TextStyle(decoration: TextDecoration.lineThrough) : null,
      ),
      subtitle: Text([
        '${stop.legDistanceKm.toStringAsFixed(1)} km',
        'P${stop.priority}',
        if (stop.isEmergency) 'emergency',
        if (stop.visitedAt != null) 'visited ${TimeOfDay.fromDateTime(stop.visitedAt!.toLocal()).format(context)}',
      ].join(' · ')),
    );
  }
}
