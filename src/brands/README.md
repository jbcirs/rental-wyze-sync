# Brand-Specific Thermostat Integration

This document explains how the thermostat alert system is organized and how to add support for new brands.

## Architecture

The thermostat system uses a **generic coordination layer** approach where the main module handles business logic and routes device communication to brand-specific implementations:

```
src/
├── thermostat.py                    # Generic coordination logic (brand-agnostic)
├── sync.py                         # Uses thermostat.py functions
└── brands/
    ├── smartthings/
    │   └── thermostats.py          # SmartThings-specific implementation
    ├── wyze/
    │   └── thermostats.py          # Wyze-specific implementation
    └── __template__/
        └── thermostats.py          # Template for new brands
```

## How It Works

### 1. Alert Flow
1. **sync.py** calls `check_temperature_alerts_with_current_device()`
2. **thermostat.py** calls `get_current_device_settings()` to route to brand
3. **Brand module** (e.g., `smartthings/thermostats.py`) handles config parsing and device communication
4. **thermostat.py** checks current settings against alert thresholds
5. **Alert sent** if thresholds are violated

### 2. Generic Brand Routing
The main `get_current_device_settings()` function in `thermostat.py` routes to brand-specific implementations with minimal brand-specific logic:

```python
# Routes to brands/smartthings/thermostats.py
if brand == 'smartthings':
    import brands.smartthings.thermostats as smartthings_thermostats
    return smartthings_thermostats.get_current_device_settings_from_config(...)

# Routes to brands/wyze/thermostats.py  
elif brand == 'wyze':
    import brands.wyze.thermostats as wyze_thermostats
    return wyze_thermostats.get_current_device_settings_from_config(...)
```

### 3. Brand Module Interface
Each brand module implements two key functions:

- **`get_current_device_settings_from_config()`**: Entry point that handles configuration parsing
- **`get_current_device_settings()`**: Core device communication function

## Adding a New Brand

To add support for a new thermostat brand:

### 1. Create Brand Folder
```bash
mkdir src/brands/newbrand
```
```

### 2. Copy Template
```bash
cp src/brands/__template__/thermostats.py src/brands/newbrand/thermostats.py
```

### 3. Implement Required Functions

**Required Function 1: `get_current_device_settings()`**
```python
def get_current_device_settings(thermostat, api_client, target_mode, target_cool, target_heat):
    """Read current settings from physical device"""
    try:
        # Your brand-specific API calls here
        device = api_client.get_device(thermostat['device_id'])
        current_mode = device.mode
        current_cool = device.cooling_setpoint
        current_heat = device.heating_setpoint
        
        logger.info(f"Read {thermostat['name']}: Mode={current_mode}, Cool={current_cool}°F, Heat={current_heat}°F")
        return current_mode, current_cool, current_heat
        
    except Exception as e:
        logger.warning(f"Error reading device: {str(e)}")
        return target_mode, target_cool, target_heat  # Fallback
```

**Required Function 2: `sync()` (if not already implemented)**
```python
def sync(api_client, thermostat, mode, cool_temp, heat_temp, scenario, property_name):
    """Synchronize thermostat with desired settings"""
    # Implementation for updating device settings
    pass
```

### 4. Add Brand to Router
Update `thermostat.py` to include your new brand:

```python
elif brand == 'newbrand':
    import brands.newbrand.thermostats as newbrand_thermostats
    return newbrand_thermostats.get_current_device_settings(
        thermostat, some_client, target_mode, target_cool, target_heat
    )
```

### 5. Update sync.py (if needed)
Add any brand-specific client initialization in `sync.py`.

## Benefits of This Approach

✅ **Separation of Concerns**: Each brand handles its own API communication  
✅ **Easy Testing**: Brand modules can be tested independently  
✅ **Clean Code**: No brand-specific logic cluttering the main coordination files  
✅ **Scalable**: Adding new brands requires minimal changes to core files  
✅ **Maintainable**: Brand teams can own their specific implementation  

## Alert System

The alert system now properly checks **current device settings** (not target settings) by:

1. Reading actual temperatures from physical devices via brand modules
2. Comparing current settings against configured thresholds  
3. Sending Slack alerts when violations are detected

Example violation that would now be caught:
- **Current Device**: Cool setpoint 91°F (set by guest)
- **Alert Threshold**: cool_above = 85°F  
- **Result**: Alert sent! 🔵 Cool setpoint 91°F is above threshold 85°F

This helps property managers catch guests setting extreme temperatures that could increase energy costs.
