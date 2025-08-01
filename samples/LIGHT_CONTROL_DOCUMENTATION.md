# Light Control System Documentation

## Overview

The light control system manages SmartThings lights based on various time-based conditions, reservation status, and sunrise/sunset calculations with configurable offsets.

## Light Configuration

### Basic Structure
```json
{
  "brand": "smartthings",
  "name": "String Lights", 
  "when": "reservations_only",
  "minutes_before_sunset": 30,
  "minutes_after_sunrise": 30,
  "start_time": null,
  "stop_time": "23:00"
}
```

### Configuration Parameters

#### Required Fields
- **brand**: Always "smartthings" for SmartThings lights
- **name**: The exact device name as it appears in SmartThings
- **when**: When the light should operate
  - `"reservations_only"`: Only during active reservations
  - `"non_reservations"`: Only when property is vacant

#### Time Control Fields (all optional)
- **minutes_before_sunset**: Turn light ON X minutes before actual sunset
- **minutes_after_sunrise**: Turn light OFF X minutes after actual sunrise  
- **start_time**: Fixed time to turn light ON (format: "HH:MM", 24-hour)
- **stop_time**: Fixed time to turn light OFF (format: "HH:MM", 24-hour)

## Logic Priority

The system uses the following priority order to determine light state:

### 1. Stop Time Check (Highest Priority)
If `stop_time` is set and current time >= stop_time, light will be OFF regardless of other conditions.

### 2. Explicit Time Window
If `start_time` and/or `stop_time` are defined, the light follows this schedule:
- Both defined: ON between start_time and stop_time
- Only start_time: ON after start_time (until stop_time if defined)
- Only stop_time: ON until stop_time

### 3. Sunrise/Sunset with Offsets
If sunrise/sunset offsets are defined and no explicit times apply:
- Light turns ON at: (sunset - minutes_before_sunset)
- Light turns OFF at: (sunrise + minutes_after_sunrise)

### 4. Default
Light remains OFF if no conditions are met.

## Example Configurations

### 1. Sunset to 11 PM During Reservations
```json
{
  "brand": "smartthings", 
  "name": "String Lights",
  "when": "reservations_only",
  "minutes_before_sunset": 30,
  "minutes_after_sunrise": 0,
  "start_time": null,
  "stop_time": "23:00"
}
```
**Behavior**: During reservations, turns ON 30 minutes before sunset, turns OFF at 11 PM.

### 2. Fixed Evening Hours
```json
{
  "brand": "smartthings",
  "name": "Porch Light", 
  "when": "reservations_only",
  "start_time": "18:00",
  "stop_time": "22:00"
}
```
**Behavior**: During reservations, ON from 6 PM to 10 PM daily.

### 3. Natural Light Cycle
```json
{
  "brand": "smartthings",
  "name": "Garden Lights",
  "when": "non_reservations", 
  "minutes_before_sunset": 15,
  "minutes_after_sunrise": 15
}
```
**Behavior**: When property is vacant, ON from 15 minutes before sunset until 15 minutes after sunrise.

## Retry Logic

The system includes robust retry logic for light state changes:

- **Maximum Attempts**: Configurable via `LIGHT_VERIFY_MAX_ATTEMPTS` (default: 3)
- **Verification**: After each API call, the system verifies the light actually changed state
- **Delays**: Configurable delays between attempts via `SMARTTHINGS_API_DELAY_SECONDS`
- **Slack Notifications**: Success/failure messages include attempt count when > 1

## Slack Notifications

### Successful Change
```
💡 Updated Lights 'String Lights' at 'Paradise Cove': OFF → ON
```

### Successful Change with Retries
```
💡 Updated Lights 'String Lights' at 'Paradise Cove': OFF → ON (verified on attempt 2)
```

### Failed Change
```
⚠️ Failed to update Lights 'String Lights' at 'Paradise Cove' to ON after 3 attempts
```

### Device Not Found
```
❓ Device Not Found: Unable to fetch Lights 'String Lights' at 'Paradise Cove'. Please verify the device is online and correctly named.
```

## Environment Variables

### Required
- `TIMEZONE`: Timezone for time calculations (e.g., "America/Chicago")
- `SMARTTHINGS_TOKEN`: SmartThings API token

### Optional (with defaults)
- `SMARTTHINGS_API_DELAY_SECONDS`: Delay between API calls (default: 2)
- `LIGHT_VERIFY_MAX_ATTEMPTS`: Maximum retry attempts (default: 3)

## Location Requirements

The property configuration must include latitude and longitude for sunrise/sunset calculations:

```json
{
  "Location": {
    "latitude": "42.3554334", 
    "longitude": "-71.060511"
  }
}
```

## Troubleshooting

### Light Not Responding
1. Check device name matches exactly in SmartThings
2. Verify device is online and responsive in SmartThings app
3. Check Slack messages for specific error details

### Unexpected Timing
1. Verify timezone configuration matches property location
2. Check latitude/longitude accuracy for sunrise/sunset calculations
3. Review time field formats (24-hour HH:MM)

### State Verification Issues
1. Increase `SMARTTHINGS_API_DELAY_SECONDS` if network is slow
2. Increase `LIGHT_VERIFY_MAX_ATTEMPTS` for unreliable devices
3. Check SmartThings API status if multiple devices fail
