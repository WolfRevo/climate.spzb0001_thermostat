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
    min_temp: 05
    max_temp: 30
    ac_mode: false
    target_temp: 18    
    cold_tolerance: 0.0
    hot_tolerance: 0.0
    initial_hvac_mode: "heat"
    away_temp: 15
    precision: 0.5
```

Field | Value | Necessity | Comments
--- | --- | --- | ---
platform | `spzb0001_thermostat` | *Required* |
name| SPZB0001 Thermostat | *Conditional* | Used to distinguish the virtual thermostats
heater |  | *Conditional* | Switch that will activate/deactivate the heating system. This can be only a single EUROTRONIC SPZB0001 Zigbee entity.
target_sensor |  | *Required* | Sensor that is used for the actual temperature input of the thermostat.
min_temp | 5 | Optional | Minimum temperature manually selectable. I recommend to use 5 as this is the lower limit of the EUROTRONIC SPZB0001 Zigbee thermostat.
max_temp | 30 | Optional | Maximum temperature manually selectable. I recommend to use 30 as this is the upper limit of the EUROTRONIC SPZB0001 Zigbee thermostat.
ac_mode | false | *Conditional* | Necessary as the EUROTRONIC SPZB0001 Zigbee thermostat does not support cooling and this is only slightly modified custom code.
target_temp | 18 | Temperature used for initialization after Home Assistant has started.
cold_tolerance | 0.0 | Optional | Tolerance for turn on and off the switches mode. I recommend to use 0.0 as you already have a tolerance due to the sensor.
hot_tolerance | 0.0 | Optional | Tolerance for turn on and off the switches mode. I recommend to use 0.0 as you already have a tolerance due to the sensor.
initial_hvac_mode | "heat" | *Conditional* | "heat" or "off", what you prefer as the initial startup value of the thermostat.
away_temp | 15 | Optional | Temperature used if the tag away is set.
precision | 0.5 | *Conditional* | This is the precision of the EUROTRONIC SPZB0001 Zigbee thermostat itself so I recommend to not change it.

## ADDITIONAL INFO
This custom component replicates the original generic_thermostat component from Home Assistant to integrate the EUROTRONIC SPZB0001 Zigbee thermostat while using an external temperature sensor for the room temperature.

You still need the original EUROTRONIC SPZB0001 Zigbee thermostat as an identy in Home Assistant (best used with the official deCONZ Add-On). The new spzb0001_thermostat just controls this device in the following matter:

The EUROTRONIC SPZB0001 Zigbee thermostat can't be used as a normal heater switch as it automatically changes from `HVAC_MODE_HEAT` to `HVAC_MODE_AUTO` after some time. This behaviour can't actually be changed. So the spzb0001_thermostat uses the `HVAC_MODE_AUTO` and the `ATTR_TEMPERATURE=max_temp` (the 30°C as stated in the config example) to control the EUROTRONIC SPZB0001 Zigbee thermostat and cause it to fully open the valve.
To switch off the EUROTRONIC SPZB0001 Zigbee thermostat the spzb0001_thermostat uses the `HVAC_MODE_OFF`, the `ATTR_TEMPERATURE=min_temp` (the 5°C as stated in the config example) and also sends a manual switch off to the corresponding service. This is needed as the EUROTRONIC SPZB0001 Zigbee thermostat sometimes also switches automatically from `HVAC_MODE_OFF` to `HVAC_MODE_AUTO`.

For controlling purposes you can visually add the original EUROTRONIC SPZB0001 Zigbee thermostats to another lovelace view to compare the states of the virtual spzb0001_thermostat and the corresponding EUROTRONIC SPZB0001 Zigbee thermostat.
