# Battery Monitoring System

## Overview

The battery monitoring system provides comprehensive battery level tracking and alerting for SmartThings and Wyze locks across all properties. The system runs daily at 8 AM via a timer trigger and can also be invoked manually via HTTP request.

## Key Features

- **Daily Automated Reports**: Timer-triggered execution every morning at 8 AM
- **Comprehensive Battery Status**: Shows battery levels for all locks across all properties
- **Smart Alert System**: Low battery alerts prominently displayed at the top of reports
- **Multi-Brand Support**: Works with both SmartThings and Wyze locks
- **Slack Integration**: Rich formatted reports sent directly to Slack
- **HTTP API**: Manual triggering and monitoring via REST endpoints

## Configuration Structure

Battery monitoring is configured as part of your lock configuration in the property settings. Each lock can have its own battery monitoring settings.

## Three-Tier Alert System

The battery monitoring system uses a three-tier alert approach:

### Status Levels

1. **🟢 OK Status**: Battery level is above the warning threshold
2. **🟡 WARNING Status**: Battery level is between the warning and critical thresholds
3. **🔴 LOW Status**: Battery level is at or below the critical threshold

### Threshold Calculation

- **Critical Threshold**: Set by `battery_threshold` parameter (default: 20%)
- **Warning Threshold**: Calculated as `battery_threshold + battery_warning_offset`
- **Default Warning Offset**: 15% (configurable per lock)

### Example Thresholds

For a lock with `battery_threshold: 25` and `battery_warning_offset: 15`:
- 🟢 **OK**: Battery ≥ 40% (25% + 15%)
- 🟡 **WARNING**: Battery 26-39% (between thresholds)
- 🔴 **LOW**: Battery ≤ 25% (critical threshold)

### Basic Lock Configuration (Current)
```json
{
  "locks": [
    {
      "brand": "smartthings",
      "name": "Front Door Lock"
    },
    {
      "brand": "smartthings", 
      "name": "Back Door Lock"
    }
  ],
  "BrandSettings": [
    {
      "brand": "smartthings",
      "location": "Main House"
    }
  ]
}
```

### Enhanced Lock Configuration with Battery Monitoring
```json
{
  "locks": [
    {
      "brand": "smartthings",
      "name": "Front Door Lock",
      "battery_threshold": 25,
      "battery_warning_offset": 15
    },
    {
      "brand": "smartthings",
      "name": "Back Door Lock", 
      "battery_threshold": 30,
      "battery_warning_offset": 20
    },
    {
      "brand": "wyze",
      "name": "Side Gate Lock",
      "battery_threshold": 20,
      "battery_warning_offset": 15
    }
  ],
  "BrandSettings": [
    {
      "brand": "smartthings",
      "location": "Main House"
    },
    {
      "brand": "wyze"
    }
  ]
}
```

## Configuration Parameters

### Required Parameters
- **`brand`** (string): Lock brand - either "smartthings" or "wyze"
- **`name`** (string): The exact name of the lock device as configured in SmartThings or Wyze

### SmartThings Specific
- **`location`** (string): Required for SmartThings - specified in BrandSettings, not individual lock configurations. This is the location/hub name where all SmartThings locks for this property are configured.

### Battery Monitoring Parameters (Optional)
- **`battery_threshold`** (integer): Battery percentage threshold that triggers alerts
  - Default: 30
  - Range: 1-99
  - Example: 25 means alert when battery drops to 25% or below

## Report Format

### Daily Battery Report Structure

The system generates comprehensive daily reports at 8 AM with the following format:

```
� **LOW BATTERY ALERTS for Property Name** 🚨
⚠️ SmartThings lock `Front Door Lock`: **15%** (threshold: 25%)
⚠️ Wyze lock `Side Gate Lock`: **18%** (threshold: 20%)

🔋 **Battery Status Report for Property Name**
Report generated: 2025-08-01 08:00:15

🔴 SmartThings `Front Door Lock`: 15% (LOW)
🟢 SmartThings `Back Door Lock`: 65% (OK)
🔴 Wyze `Side Gate Lock`: 18% (LOW)
🟢 Wyze `Pool Gate Lock`: 78% (OK)

Summary: 4 locks total, 2 with low battery
```

### Report Behavior
- Reports are sent daily at 8:00 AM regardless of battery levels
- Low battery alerts are prominently displayed at the top when present
- Complete status overview shows all locks with current battery percentages
- Color-coded emojis indicate status: 🔴 (low), 🟢 (ok), ❌ (error)

## Implementation Details

### Azure Function Triggers
1. **HTTP Trigger**: Manual battery check via API call to `/api/battery_monitor`
2. **Timer Trigger**: Automatic daily check at 8:00 AM

### Battery Check Process
1. Retrieves all property configurations from Hospitable
2. For each property with lock configurations:
   - Connects to SmartThings/Wyze API
   - Retrieves current battery level for each lock
   - Compares against configured threshold
   - Generates comprehensive battery report for the property
   - Sends report to Slack with alerts prominently displayed

### Error Handling
- Invalid configurations are logged and skipped
- Network/API errors are reported but don't stop other checks
- Failed battery retrievals are logged with detailed error messages

## Environment Variables

No additional environment variables are required. The system uses existing SmartThings and Wyze API credentials.

## Monitoring and Logs

### Log Messages
- Info: Successful battery checks with current levels
- Warning: Battery levels approaching threshold
- Error: Configuration issues, API failures, or connectivity problems

### Azure Function Response
The battery monitoring function returns a detailed JSON response:
```json
{
  "timestamp": "2025-08-01T08:00:15.123456-05:00",
  "summary": {
    "total_properties_processed": 3,
    "total_locks_monitored": 8,
    "total_low_battery_alerts": 2,
    "total_reports_sent": 3,
    "total_errors": 0
  },
  "property_results": {
    "Beach House Main": {
      "total_locks": 4,
      "low_battery_count": 1,
      "errors": 0,
      "locks": [
        {
          "name": "Front Door Lock",
          "brand": "smartthings",
          "battery_level": 23,
          "battery_threshold": 25,
          "is_low_battery": true,
          "property_name": "Beach House Main"
        }
      ],
      "error_details": []
    }
  }
}
```

## Best Practices

1. **Threshold Settings**: 
   - Set thresholds between 20-30% for most locks
   - Lower thresholds (15-20%) for frequently accessed locks
   - Higher thresholds (30-40%) for critical security locks

2. **Daily Monitoring**:
   - Review daily 8 AM battery reports in Slack
   - Plan battery replacements when levels approach thresholds
   - Keep spare batteries available for immediate replacement

3. **Testing**:
   - Test battery monitoring by temporarily lowering thresholds
   - Verify Slack notifications are received correctly
   - Confirm lock names match exactly between config and devices
   - Use manual HTTP endpoint for immediate battery checks
