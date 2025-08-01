# Thermostat Configuration Features

This document describes the advanced thermostat management features with clean brand-agnostic architecture, frequency control, and intelligent alerting system for cost control during guest stays.

## Architecture Overview

The thermostat system uses a **generic coordination layer** that routes device communication to brand-specific modules:

- **Main Module**: `src/thermostat.py` - Generic business logic and coordination
- **Brand Modules**: `src/brands/{brand}/thermostats.py` - Brand-specific device communication
- **Template System**: `src/brands/__template__/thermostats.py` - Pattern for new brands

### Key Benefits

✅ **Brand-Agnostic**: Main logic works with any thermostat brand  
✅ **Cost Control**: Monitors actual device settings to catch expensive guest changes  
✅ **Scalable**: Easy to add new brands using the template pattern  
✅ **Reliable**: Comprehensive error handling and graceful degradation  

## Core Features

### 1. Intelligent Frequency Control

The `frequency` setting optimizes when thermostat changes are applied during reservations to balance comfort and API efficiency.

**Options:**
- `"first_day"` - Apply changes only on check-in day (default, reduces API calls)
- `"daily"` - Apply changes every day during reservation (maximum control)

**Use Cases:**
- **First Day**: Ideal for stable climate periods, reduces API throttling
- **Daily**: Best for variable weather or fine-tuned control during long stays

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

### 2. Advanced Temperature Alert System

The alert system monitors **actual device settings** (not target settings) to catch extreme guest temperature changes that increase energy costs.

**Alert Features:**
- **Real-time Monitoring**: Reads current device state during reservations
- **Cost Control**: Detects expensive temperature settings set by guests  
- **Flexible Thresholds**: Multiple threshold types with nested configuration support
- **Smart Notifications**: Formatted Slack messages with violation details
- **Channel Routing**: Custom Slack channels for different alert types

**Alert Threshold Types:**
- `"cool_below"` - Alert if cooling setpoint drops below threshold (guest making it too cold)
- `"cool_above"` - Alert if cooling setpoint rises above threshold (inefficient cooling)
- `"heat_below"` - Alert if heating setpoint drops below threshold (insufficient heating)
- `"heat_above"` - Alert if heating setpoint rises above threshold (expensive heating)

**Alert Configuration:**
- `"enabled"` - Boolean to enable/disable alerts (default: true if thresholds exist)
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

### 3. Freeze Protection

Automatically overrides thermostat settings during non-reservation periods when freezing conditions are forecast.

**Features:**
- **Pipe Protection**: Prevents water pipe freezing damage
- **Weather Integration**: Uses forecast data for proactive protection
- **Configurable Thresholds**: Custom freeze temperatures and heat settings

**Example:**
```json
{
  "when": "non_reservations",
  "mode": "cool",
  "cool_temp": 85,
  "heat_temp": 50,
  "freeze_protection": {
    "freeze_temp": 32,
    "heat_temp": 55
  }
}
```

## Brand Support

### Current Implementations

#### SmartThings
- **Configuration**: JSON-based with location lookup
- **Authentication**: Personal access token
- **Device Identification**: Location name + device name
- **Features**: Full alert support, frequency control

#### Wyze  
- **Configuration**: Client-based with MAC address
- **Authentication**: API key + credentials with token management
- **Device Identification**: MAC address + model
- **Features**: Full alert support, frequency control

#### Template System
- **Purpose**: Blueprint for implementing new brands
- **Location**: `src/brands/__template__/thermostats.py`
- **Documentation**: Complete implementation guide in `src/brands/README.md`

## Sample Configurations

### Advanced SmartThings Setup

```json
[
  {
    "brand": "smartthings",
    "manufacture": "ecobee",
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
          "heat_above": 75,
          "enabled": true,
          "slack_channel": "#energy-alerts"
        }
      },
      {
        "when": "reservations_only", 
        "mode": "heat",
        "cool_temp": 78,
        "heat_temp": 72,
        "frequency": "daily",
        "alerts": {
          "heat_below": 68,
          "heat_above": 76,
          "enabled": true
        }
      },
      {
        "when": "non_reservations",
        "mode": "auto",
        "cool_temp": 85,
        "heat_temp": 50,
        "freeze_protection": {
          "freeze_temp": 32,
          "heat_temp": 55
        }
      }
    ],
    "rest_times": ["01:00", "06:00"]
  }
]
```

### Comprehensive Wyze Configuration

```json
[
  {
    "brand": "wyze",
    "manufacture": "wyze",
    "name": "Guest Suite Thermostat",
    "mac": "2C:26:17:XX:XX:XX",
    "model": "WLPP1CFP",
    "temperatures": [
      {
        "when": "reservations_only",
        "mode": "auto",
        "cool_temp": 74,
        "heat_temp": 70,
        "frequency": "daily",
        "alerts": {
          "cool_below": 72,
          "cool_above": 79,
          "heat_below": 67,
          "heat_above": 77,
          "enabled": true,
          "slack_channel": "#guest-comfort"
        }
      },
      {
        "when": "non_reservations",
        "mode": "cool", 
        "cool_temp": 85,
        "heat_temp": 50,
        "frequency": "first_day",
        "freeze_protection": {
          "freeze_temp": 28,
          "heat_temp": 60
        }
      }
    ],
    "rest_times": ["02:00", "07:00"]
  }
]
```

## Alert Message Examples

### Successful Alert Notification

When temperature thresholds are violated, the system sends detailed Slack notifications:

```
🌡️ Thermostat Alert - Beach House Paradise
Thermostat: Main Floor Thermostat
Current Mode: cool
Current Settings: Cool 68°F, Heat 70°F
Violations:
• 🔵 Cool setpoint 68°F is below threshold 72°F
• 🔴 Heat setpoint 70°F is below threshold 72°F
```

### Temperature Change Notification

After successful thermostat updates:

```
🌡️ Updated Thermostat 'Guest Suite' at 'Mountain Cabin'
Current Temperature: 73°F
Changes Made:
• Mode: heat → cool
• Cool: 78°F → 74°F
• Heat: 72°F → 70°F
```

## Implementation Details

### Generic Architecture Benefits

- **Clean Separation**: Main coordination logic is completely brand-agnostic
- **Easy Extension**: Add new brands by implementing two simple functions
- **Robust Error Handling**: Graceful degradation when devices are unreachable
- **Performance**: Dynamic imports only load brand modules when needed

### Frequency Processing

- The system checks the `frequency` setting for each thermostat configuration
- For `"first_day"`, changes are only applied on the reservation check-in date
- For `"daily"`, changes are applied every day during the reservation period
- Reduces API calls and prevents throttling while maintaining control

### Alert Processing

- Alerts monitor **actual device settings** (not target settings) during reservations
- Readings happen before any temperature changes to catch guest modifications
- Multiple violations can be reported in a single formatted alert message
- Custom Slack channels allow routing different alert types appropriately
- Alert failures are logged but don't affect thermostat operation

### Error Handling & Reliability

- **Invalid Configuration**: Unknown frequency values default to `"first_day"` behavior
- **Missing Thresholds**: Undefined alert thresholds are gracefully ignored
- **Device Communication**: Network failures fall back to target settings for alerts
- **API Throttling**: Frequency control and delays prevent rate limiting
- **Graceful Degradation**: System continues operating even with partial failures

### Brand Module Architecture

Each brand implements a consistent interface:

```python
# Entry point called from main module
def get_current_device_settings_from_config(thermostat, config_or_client, target_mode, target_cool, target_heat):
    # Handle brand-specific configuration parsing and authentication
    return get_current_device_settings(device_params, api_client, target_mode, target_cool, target_heat)

# Core device communication
def get_current_device_settings(device_params, api_client, target_mode, target_cool, target_heat):
    # Make API calls to read actual device state
    return current_mode, current_cool_temp, current_heat_temp
```

## Backward Compatibility

✅ **Configuration**: Existing configurations without new fields continue working  
✅ **Frequency**: Defaults to `"first_day"` if not specified  
✅ **Alerts**: No alerts sent if configuration is missing  
✅ **API Compatibility**: All existing brand integrations remain functional  

## Adding New Brands

1. **Copy Template**: Use `src/brands/__template__/thermostats.py` as starting point
2. **Implement Functions**: Fill in the two required interface functions
3. **Add Router Case**: Update main `thermostat.py` with new brand case
4. **Test Integration**: Verify device communication and error handling
5. **Update Documentation**: Add brand-specific configuration examples

See `src/brands/README.md` for detailed implementation guide.
