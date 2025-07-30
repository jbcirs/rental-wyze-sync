# Thermostat Configuration Updates

This document describes the new frequency and alerting features added to the thermostat configuration system.

## New Features

### 1. Frequency Control

The `frequency` setting controls when thermostat changes are applied during reservations.

**Options:**
- `"first_day"` - Only apply changes on the check-in day (default if not specified)
- `"daily"` - Apply changes every day during the reservation

**Example:**
```json
{
  "when": "reservations_only",
  "mode": "cool",
  "cool_temp": 72,
  "heat_temp": 68,
  "frequency": "daily"
}
```

### 2. Temperature Alerts

The `alerts` configuration enables Slack notifications when thermostat setpoints violate defined thresholds.

**Alert Options:**
- `"cool_below"` - Alert if cooling setpoint is below this temperature
- `"cool_above"` - Alert if cooling setpoint is above this temperature  
- `"heat_below"` - Alert if heating setpoint is below this temperature
- `"heat_above"` - Alert if heating setpoint is above this temperature
- `"enabled"` - Boolean to enable/disable alerts (default: true)
- `"slack_channel"` - Optional custom Slack channel for alerts

**Example:**
```json
{
  "when": "reservations_only",
  "mode": "auto",
  "cool_temp": 74,
  "heat_temp": 70,
  "frequency": "daily",
  "alerts": {
    "cool_below": 72,
    "cool_above": 78,
    "heat_below": 67,
    "heat_above": 76,
    "enabled": true,
    "slack_channel": "#thermostat-alerts"
  }
}
```

## Sample Configurations

### Basic SmartThings Configuration

```json
[
  {
    "brand": "smartthings",
    "manufacture": "ecobee",
    "name": "Upstairs",
    "temperatures": [
      {
        "when": "reservations_only",
        "mode": "cool",
        "cool_temp": 72,
        "heat_temp": 68,
        "frequency": "first_day",
        "alerts": {
          "cool_below": 70,
          "heat_above": 75,
          "enabled": true
        }
      },
      {
        "when": "reservations_only",
        "mode": "heat",
        "cool_temp": 78,
        "heat_temp": 72,
        "frequency": "daily",
        "alerts": {
          "cool_below": 75,
          "heat_above": 75,
          "enabled": true
        }
      },
      {
        "when": "non_reservations",
        "mode": "cool",
        "cool_temp": 85,
        "heat_temp": 50,
        "freeze_protection": {
          "freeze_temp": 32,
          "heat_temp": 70
        }
      }
    ],
    "rest_times": ["01:00", "06:00"]
  }
]
```

### Advanced Wyze Configuration

```json
[
  {
    "brand": "wyze",
    "manufacture": "wyze",
    "name": "Main Floor Thermostat",
    "temperatures": [
      {
        "when": "reservations_only",
        "mode": "cool",
        "cool_temp": 73,
        "heat_temp": 69,
        "frequency": "first_day",
        "alerts": {
          "cool_below": 71,
          "cool_above": 78,
          "heat_below": 66,
          "heat_above": 76,
          "enabled": true
        }
      },
      {
        "when": "reservations_only",
        "mode": "auto",
        "cool_temp": 75,
        "heat_temp": 71,
        "frequency": "daily",
        "alerts": {
          "cool_below": 73,
          "cool_above": 79,
          "heat_below": 68,
          "heat_above": 77,
          "enabled": false
        }
      }
    ],
    "rest_times": ["02:00", "07:00"]
  }
]
```

## Alert Message Format

When temperature thresholds are violated, the system sends Slack notifications with the following format:

```
🌡️ Thermostat Alert - Property Name
Thermostat: Device Name
Current Mode: cool
Current Settings: Cool 68°F, Heat 70°F
Violations:
• 🔵 Cool setpoint 68°F is below threshold 70°F
```

## Backward Compatibility

- If `frequency` is not specified, it defaults to `"first_day"`
- If `alerts` section is not present, no alerts will be sent
- Existing configurations without these new fields will continue to work as before

## Implementation Details

### Frequency Processing
- The system checks the `frequency` setting for each thermostat configuration
- For `"first_day"`, changes are only applied on the reservation check-in date
- For `"daily"`, changes are applied every day during the reservation period

### Alert Processing
- Alerts are checked after successful thermostat synchronization
- Only active during reservations and when alerts are enabled
- Alerts can be sent to custom Slack channels if specified
- Multiple violations can be reported in a single alert message

### Error Handling
- Invalid frequency values default to `"first_day"` behavior
- Missing alert thresholds are ignored (no alerts for that threshold)
- Alert failures are logged but don't affect thermostat operation
