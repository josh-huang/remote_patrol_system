import 'package:flutter_test/flutter_test.dart';
import 'package:patrol_duty_phone/api/api_client.dart';
import 'package:patrol_duty_phone/main.dart';
import 'package:patrol_duty_phone/models.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('shows the sign-in screen when logged out', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(DutyPhoneApp(api: ApiClient(baseUrl: 'http://localhost')));
    await tester.pumpAndSettle();
    expect(find.text('Patrol Duty Phone'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
  });

  test('parses the mobile route payload', () {
    final route = RouteInfo.fromJson({
      'vehicle': {'id': 1, 'plate_number': 'SPT 1001 A', 'model_name': 'Corolla', 'driver_name': 'Ahmad'},
      'plan': {'id': 3, 'name': "Tonight's patrol", 'date': '2026-10-09', 'status': 'active'},
      'stops': [
        {'id': 10, 'order': 0, 'location': 5, 'location_name': 'Marina Bay Sands', 'latitude': 1.28, 'longitude': 103.86,
         'leg_distance_km': 0.0, 'is_visited': true, 'visited_at': '2026-10-09T22:00:00Z', 'priority': 3},
        {'id': 11, 'order': 1, 'location': 6, 'location_name': 'Tuas', 'latitude': 1.32, 'longitude': 103.65,
         'leg_distance_km': 25.4, 'is_visited': false, 'source': 'emergency', 'priority': 1},
      ],
      'next_stop': {'id': 11, 'order': 1, 'location': 6, 'location_name': 'Tuas', 'latitude': 1.32, 'longitude': 103.65,
                    'leg_distance_km': 25.4, 'is_visited': false, 'source': 'emergency'},
      'progress': {'visited': 1, 'total': 2},
      'remaining_km': 25.4,
      'command_centre_phone': '+65 6000 0000',
      'unread_messages': 2,
    });
    expect(route.vehicle.plateNumber, 'SPT 1001 A');
    expect(route.stops, hasLength(2));
    expect(route.stops.first.isVisited, isTrue);
    expect(route.nextStop!.isEmergency, isTrue);
    expect(route.remainingKm, 25.4);
    expect(route.unreadMessages, 2);
  });
}
