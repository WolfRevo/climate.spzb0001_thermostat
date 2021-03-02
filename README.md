# SPZB0001 THERMOSTAT
A clone created from the Home Assistant generic_thermostat to use EUROTRONIC Zigbee SPZB0001 thermostats with external temperature sensors.

# HOW TO INSTALL
Just copy paste the content of the climate.spzb_thermostat/custom_components folder in your config/custom_components directory.

As example you will get the '.py' file in the following path: /config/custom_components/spzb0001_thermostat/climate.py.

## EXAMPLE OF SETUP
You need to configure one virtual spzb0001_thermostat for every used EUROTRONIC Zigbee SPZB0001 thermostat in the `configuration.yaml` file.

Here below the example of manual setup of sensor and parameters to configure.
```yaml
climate:
  - platform: spzb0001_thermostat
    name: room
    heater: switch.heater
    target_sensor: sensor.temperature
    target_temp: 18    
    initial_hvac_mode: "heat"
    away_temp: 15
```

Field | Value | Necessity | Comments
--- | --- | --- | ---
platform | `spzb0001_thermostat` | *Required* |
name| SPZB0001 Thermostat | *Conditional* | Used to distinguish the virtual thermostats
heater |  | *Conditional* | Switch that will activate/deactivate the heating system. This can be only a single EUROTRONIC SPZB0001 Zigbee entity.
target_sensor |  | *Required* | Sensor that is used for the actual temperature input of the thermostat.
target_temp | 18 | Optional |Temperature used for initialization after Home Assistant has started.
initial_hvac_mode | "heat" | *Conditional* | "heat" or "off", what you prefer as the initial startup value of the thermostat.
away_temp | 15 | Optional | Temperature used if the tag away is set.

## ADDITIONAL INFO
This custom component replicates the original generic_thermostat component from Home Assistant to integrate the EUROTRONIC SPZB0001 Zigbee thermostat while using an external temperature sensor for the room temperature. It is stripped down to the necessary only and working configuration options (see above). Lower and upper temperature are hardcoded to reflect the deCONZ integration.

You still need the original EUROTRONIC SPZB0001 Zigbee thermostat as an identy in Home Assistant (best used with the official deCONZ Add-On). The new spzb0001_thermostat just controls this device in the following matter:

The EUROTRONIC SPZB0001 Zigbee thermostat can't be used as a normal heater switch (`STATE_ON`, `STATE_OFF`) as it only knows `HVAC_MODE_OFF`, `HVAC_MODE_AUTO`, `HVAC_MODE_HEAT` and automatically changes from `HVAC_MODE_HEAT` to `HVAC_MODE_AUTO` after some time. This behaviour can't actually be changed. So the spzb0001_thermostat uses the `HVAC_MODE_AUTO` and the `ATTR_TEMPERATURE=max_temp` (30°C per deCONZ integration) to control the EUROTRONIC SPZB0001 Zigbee thermostat and cause it to fully open the valve.
To switch off the EUROTRONIC SPZB0001 Zigbee thermostat the spzb0001_thermostat uses the `ATTR_TEMPERATURE=min_temp` (5°C per deCONZ integration) and the `HVAC_MODE_OFF` with tested delays to prevent inconsistent states.

For controlling purposes you can visually add the original EUROTRONIC SPZB0001 Zigbee thermostats to another lovelace view to compare the states of the virtual spzb0001_thermostat and the corresponding EUROTRONIC SPZB0001 Zigbee thermostat.
