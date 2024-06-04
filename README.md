# Syncing Rental Wyze Devices

This is to synchronize Wyze devices for rental use. This azure function wil look 1 week in advance from your Hospitable calendar. It will add, update, or delete codes into Wyze locks.

## Setup

### First Time

For first time run of any scripts use

```
chmod +x ./scripts/<filename>.sh
```

### Setup Enviorment

```
python3 -m venv .venv
. .venv/bin/activate
```