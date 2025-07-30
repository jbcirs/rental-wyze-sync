# Thermostat Slack Message Examples

This document shows examples of the enhanced Slack messages that are sent when thermostats are updated, providing detailed before/after information for both SmartThings and Wyze devices.

## Successful Update Messages

Both SmartThings and Wyze devices now send consistent, detailed messages when thermostat settings are changed:

### Example 1: Mode and Temperature Change
```
🌡️ Updated Thermostat 'Living Room' at 'Mountain View Cabin'
Current Temperature: 72°F
Changes Made:
• Mode: heat → auto
• Cool: 76°F → 74°F
• Heat: 68°F → 70°F
```

### Example 2: Temperature Only Change
```
🌡️ Updated Thermostat 'Master Bedroom' at 'Lakeshore Property'
Current Temperature: 69°F
Changes Made:
• Cool: 78°F → 75°F
• Heat: 65°F → 68°F
```

### Example 3: Mode Change Only
```
🌡️ Updated Thermostat 'Main Floor' at 'Downtown Condo'
Current Temperature: 71°F
Changes Made:
• Mode: cool → auto
```

### Example 4: Wyze Scenario Change (Wyze Only)
```
🌡️ Updated Thermostat 'Guest Room' at 'Beach House'
Current Temperature: 73°F
Changes Made:
• Scenario: away → home
• Mode: heat → auto
• Heat: 65°F → 70°F
```

### Example 5: Fan Mode Change
```
🌡️ Updated Thermostat 'Office' at 'City Apartment'
Current Temperature: 70°F
Changes Made:
• Fan: on → auto
• Cool: 77°F → 75°F
```

## Error Messages

### Device Not Found
```
❓ Device Not Found: Unable to fetch Thermostat 'Living Room' at 'Mountain View Cabin'. Please verify the device is online and correctly named.
```

### Status Retrieval Error
```
🌡️ Thermostat Status Error: Unable to retrieve current status for 'Master Bedroom' at 'Lakeshore Property'. The device may be offline or experiencing connectivity issues.
```

### Partial Update Failure (Wyze Only)
```
⚠️ Partial update failure for Thermostat Living Room at Mountain View Cabin:
Mode update: ✅
Temp update: ❌
Fan update: ✅
Scenario update: ✅
```

### Complete Update Failure
```
⚠️ Failed to update Thermostat 'Main Floor' at 'Downtown Condo'
```

### Missing Configuration
```
🔍 Missing Data: Thermostat configuration is missing or invalid for 'Beach House'.
```

### Location Not Found (SmartThings Only)
```
❓ Location Not Found: Unable to fetch location ID for 'SmartThings Location' when configuring thermostat at 'City Apartment'.
```

### Unexpected Error
```
❌ Unexpected Error in SmartThings Thermostat function for 'Downtown Condo': Connection timeout after 30 seconds
```

## Message Format Consistency

Both SmartThings and Wyze implementations now follow the same message format:
- 🌡️ emoji for successful updates
- Device type and name clearly identified
- Property name for context
- Current temperature always displayed
- Changes listed with clear before → after format
- Consistent error message structure with appropriate emojis (❓ ⚠️ 🔍 ❌)

This provides users with clear, consistent information about thermostat changes regardless of the device brand.
