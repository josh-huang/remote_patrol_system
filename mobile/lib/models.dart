/// Plain data classes for the parts of the API the duty phone uses.
library;

double _d(dynamic v) => v == null ? 0 : (v as num).toDouble();

class Vehicle {
  Vehicle({
    required this.id,
    required this.plateNumber,
    this.modelName = '',
    this.driverName,
    this.maintenanceStatus = 'healthy',
  });

  final int id;
  final String plateNumber;
  final String modelName;
  final String? driverName;
  final String maintenanceStatus;

  factory Vehicle.fromJson(Map<String, dynamic> j) => Vehicle(
        id: j['id'] as int,
        plateNumber: j['plate_number'] as String,
        modelName: (j['model_name'] ?? '') as String,
        driverName: j['driver_name'] as String?,
        maintenanceStatus: (j['maintenance_status'] ?? 'healthy') as String,
      );
}

class Stop {
  Stop({
    required this.id,
    required this.order,
    required this.locationId,
    required this.locationName,
    required this.latitude,
    required this.longitude,
    this.address = '',
    this.priority = 1,
    this.legDistanceKm = 0,
    this.source = 'planned',
    this.isVisited = false,
    this.visitedAt,
  });

  final int id;
  final int order;
  final int locationId;
  final String locationName;
  final String address;
  final double latitude;
  final double longitude;
  final int priority;
  final double legDistanceKm;
  final String source;
  final bool isVisited;
  final DateTime? visitedAt;

  bool get isEmergency => source == 'emergency';

  factory Stop.fromJson(Map<String, dynamic> j) => Stop(
        id: j['id'] as int,
        order: j['order'] as int,
        locationId: j['location'] as int,
        locationName: j['location_name'] as String,
        address: (j['address'] ?? '') as String,
        latitude: _d(j['latitude']),
        longitude: _d(j['longitude']),
        priority: (j['priority'] ?? 1) as int,
        legDistanceKm: _d(j['leg_distance_km']),
        source: (j['source'] ?? 'planned') as String,
        isVisited: (j['is_visited'] ?? false) as bool,
        visitedAt: j['visited_at'] == null ? null : DateTime.parse(j['visited_at'] as String),
      );
}

/// Response of `GET /mobile/route/`.
class RouteInfo {
  RouteInfo({
    required this.vehicle,
    required this.stops,
    this.planName,
    this.nextStop,
    this.visited = 0,
    this.total = 0,
    this.remainingKm = 0,
    this.commandCentrePhone = '',
    this.unreadMessages = 0,
  });

  final Vehicle vehicle;
  final String? planName;
  final List<Stop> stops;
  final Stop? nextStop;
  final int visited;
  final int total;
  final double remainingKm;
  final String commandCentrePhone;
  final int unreadMessages;

  factory RouteInfo.fromJson(Map<String, dynamic> j) {
    final progress = (j['progress'] ?? {}) as Map<String, dynamic>;
    final plan = j['plan'] as Map<String, dynamic>?;
    return RouteInfo(
      vehicle: Vehicle.fromJson(j['vehicle'] as Map<String, dynamic>),
      planName: plan?['name'] as String?,
      stops: ((j['stops'] ?? []) as List).map((s) => Stop.fromJson(s as Map<String, dynamic>)).toList(),
      nextStop: j['next_stop'] == null ? null : Stop.fromJson(j['next_stop'] as Map<String, dynamic>),
      visited: (progress['visited'] ?? 0) as int,
      total: (progress['total'] ?? 0) as int,
      remainingKm: _d(j['remaining_km']),
      commandCentrePhone: (j['command_centre_phone'] ?? '') as String,
      unreadMessages: (j['unread_messages'] ?? 0) as int,
    );
  }
}

class ChatMessage {
  ChatMessage({
    required this.id,
    required this.body,
    required this.fromCommandCentre,
    required this.createdAt,
    this.senderName,
  });

  final int id;
  final String body;
  final bool fromCommandCentre;
  final DateTime createdAt;
  final String? senderName;

  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
        id: j['id'] as int,
        body: j['body'] as String,
        fromCommandCentre: (j['from_command_centre'] ?? false) as bool,
        createdAt: DateTime.parse(j['created_at'] as String),
        senderName: j['sender_name'] as String?,
      );
}

/// AI triage returned after submitting an incident.
class IncidentResult {
  IncidentResult({
    required this.id,
    required this.severity,
    required this.category,
    required this.summary,
    required this.recommendedAction,
  });

  final int id;
  final String severity;
  final String category;
  final String summary;
  final String recommendedAction;

  factory IncidentResult.fromJson(Map<String, dynamic> j) => IncidentResult(
        id: j['id'] as int,
        severity: (j['ai_severity'] ?? '') as String,
        category: (j['ai_category'] ?? '') as String,
        summary: (j['ai_summary'] ?? '') as String,
        recommendedAction: (j['ai_recommended_action'] ?? '') as String,
      );
}
