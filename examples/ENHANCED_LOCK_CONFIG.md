# Example Enhanced Lock Configuration

## Updated Configuration E### Daily Report Example

When Front Door Lock battery drops to 28% and Back Door Lock is at 42%, you'll see this in the daily 8 AM report:

```
🚨 **LOW BATTERY ALERTS for Beach House Main** 🚨
⚠️ SmartThings lock `Front Door Lock`: **28%** (threshold: 30%)

⚠️ **BATTERY WARNINGS for Beach House Main** ⚠️
🟡 SmartThings lock `Back Door Lock`: **42%** (warning at: 45%)

🔋 **Battery Status Report for Beach House Main**
Report generated: 2025-08-01 08:00:15

🔴 SmartThings `Front Door Lock`: 28% (LOW)
🟡 SmartThings `Back Door Lock`: 42% (WARNING)
🟢 SmartThings `Pool Gate Lock`: 65% (OK)

Summary: 3 locks total, 1 with low battery, 1 with warnings
```on your current lock configuration, here's how to enhance it with battery monitoring:

### Current Configuration
```json
[
  { 
    "brand": "smartthings", 
    "name": "Front Door Lock" 
  },
  { 
    "brand": "smartthings", 
    "name": "Back Door Lock" 
  }
]
```

### Enhanced Configuration with Battery Monitoring
```json
[
  { 
    "brand": "smartthings", 
    "name": "Front Door Lock",
    "location": "Main House",
    "battery_threshold": 30,
    "battery_warning_offset": 15
  },
  { 
    "brand": "smartthings", 
    "name": "Back Door Lock",
    "location": "Main House", 
    "battery_threshold": 25,
    "battery_warning_offset": 20
  }
]
```

### Key Changes Required

1. **Location Field**: Added required `location` field for SmartThings locks
   - This should match exactly with your SmartThings location name
   - Find this in your SmartThings app under "Locations"

2. **Battery Threshold**: Set the percentage that triggers critical alerts
   - Front Door: 30% (standard alert level)
   - Back Door: 25% (slightly more aggressive for security)

3. **Battery Warning Offset**: Set how many percentage points above threshold to show warnings
   - Front Door: 15% above threshold = warning at 45% (30% + 15%)
   - Back Door: 20% above threshold = warning at 45% (25% + 20%)
   - Default: 15% if not specified

### Testing Your Configuration

1. **Verify Lock Names**: Ensure lock names match exactly in SmartThings
2. **Check Location**: Confirm location name in SmartThings app
3. **Test Battery Reading**: Manually run battery check to verify connection
4. **Lower Threshold Temporarily**: Set threshold to 95% to test alerts

### API Endpoints for Testing

- **Manual Check**: `GET /api/battery_monitor`
- **View Results**: Check response JSON for battery levels and any errors

### Daily Report Example

When Front Door Lock battery drops to 28%, you'll see it in the daily 8 AM report:

```
� **LOW BATTERY ALERTS for Beach House Main** 🚨
⚠️ SmartThings lock `Front Door Lock`: **28%** (threshold: 30%)

🔋 **Battery Status Report for Beach House Main**
Report generated: 2025-08-01 08:00:15

🔴 SmartThings `Front Door Lock`: 28% (LOW)
🟢 SmartThings `Back Door Lock`: 65% (OK)

Summary: 2 locks total, 1 with low battery
```

### Gradual Rollout Approach

1. **Phase 1**: Add location fields to existing config (no battery monitoring yet)
2. **Phase 2**: Add battery monitoring with high thresholds (50%) for testing
3. **Phase 3**: Adjust thresholds to production values (20-30%)
4. **Phase 4**: Add custom Slack channels as needed
