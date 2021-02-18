"""Adds support for SPZB0001 thermostat units."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)

from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, CoreState, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = "SPZB0001 Thermostat"

CONF_HEATER = "heater"
CONF_SENSOR = "target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_AC_MODE = "ac_mode"
CONF_MIN_DUR = "min_cycle_duration"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_AWAY_TEMP = "away_temp"
CONF_PRECISION = "precision"
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_AC_MODE): cv.boolean,
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_DUR): cv.positive_time_period,
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
        vol.Optional(CONF_KEEP_ALIVE): cv.positive_time_period,
        vol.Optional(CONF_INITIAL_HVAC_MODE): vol.In(
            [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF]
        ),
        vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SPZB0001 thermostat platform."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    sensor_entity_id = config.get(CONF_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_temp = config.get(CONF_TARGET_TEMP)
    ac_mode = config.get(CONF_AC_MODE)
    min_cycle_duration = config.get(CONF_MIN_DUR)
    cold_tolerance = config.get(CONF_COLD_TOLERANCE)
    hot_tolerance = config.get(CONF_HOT_TOLERANCE)
    keep_alive = config.get(CONF_KEEP_ALIVE)
    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
    away_temp = config.get(CONF_AWAY_TEMP)
    precision = config.get(CONF_PRECISION)
    unit = hass.config.units.temperature_unit

    async_add_entities(
        [
            SPZB0001Thermostat(
                name,
                heater_entity_id,
                sensor_entity_id,
                min_temp,
                max_temp,
                target_temp,
                ac_mode,
                min_cycle_duration,
                cold_tolerance,
                hot_tolerance,
                keep_alive,
                initial_hvac_mode,
                away_temp,
                precision,
                unit,
            )
        ]
    )


class SPZB0001Thermostat(ClimateEntity, RestoreEntity):
    """Representation of a SPZB0001 Thermostat device."""

    def __init__(
        self,
        name,
        heater_entity_id,
        sensor_entity_id,
        min_temp,
        max_temp,
        target_temp,
        ac_mode,
        min_cycle_duration,
        cold_tolerance,
        hot_tolerance,
        keep_alive,
        initial_hvac_mode,
        away_temp,
        precision,
        unit,
    ):
        """Initialize the thermostat."""
        self._name = name
        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id
        self.ac_mode = ac_mode
        self.min_cycle_duration = min_cycle_duration
        self._cold_tolerance = cold_tolerance
        self._hot_tolerance = hot_tolerance
        self._keep_alive = keep_alive
        self._hvac_mode = initial_hvac_mode
        self._saved_target_temp = target_temp or away_temp
        self._temp_precision = precision
        if self.ac_mode:
            self._hvac_list = [HVAC_MODE_COOL, HVAC_MODE_OFF]
        else:
            self._hvac_list = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
        self._active = False
        self._cur_temp = None
        self._temp_lock = asyncio.Lock()
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp = target_temp
        self._unit = unit
        self._support_flags = SUPPORT_FLAGS
        if away_temp:
            self._support_flags = SUPPORT_FLAGS | SUPPORT_PRESET_MODE
        self._away_temp = away_temp
        self._is_away = False
        self.startup = True #SPZB: introduced to be able to shutdown EUROTRONIC thermostats after HA restart to avoid inconsistant states

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.sensor_entity_id], self._async_sensor_changed
            )
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.heater_entity_id], self._async_switch_changed
            )
        )

        if self._keep_alive:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass, self._async_control_heating, self._keep_alive
                )
            )

        @callback
        def _async_startup(*_):
            """Init on startup."""
            sensor_state = self.hass.states.get(self.sensor_entity_id)
            if sensor_state and sensor_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self._async_update_temp(sensor_state)
                self.async_write_ha_state()

        if self.hass.state == CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # If we have no initial temperature, restore
            if self._target_temp is None:
                # If we have a previously saved temperature
                if old_state.attributes.get(ATTR_TEMPERATURE) is None:
                    if self.ac_mode:
                        self._target_temp = self.max_temp
                    else:
                        self._target_temp = self.min_temp
                    _LOGGER.warning(
                        "Undefined target temperature, falling back to %s",
                        self._target_temp,
                    )
                else:
                    self._target_temp = float(old_state.attributes[ATTR_TEMPERATURE])
            if old_state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY:
                self._is_away = True
            if not self._hvac_mode and old_state.state:
                self._hvac_mode = old_state.state

        else:
            # No previous state, try and restore defaults
            if self._target_temp is None:
                if self.ac_mode:
                    self._target_temp = self.max_temp
                else:
                    self._target_temp = self.min_temp
            _LOGGER.warning(
                "No previously saved temperature, setting to %s", self._target_temp
            )

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision
        return super().precision

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        # Since this integration does not yet have a step size parameter
        # we have to re-use the precision as the step size for now.
        return self.precision

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._hvac_mode == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF
        if not self._is_device_active:
            return CURRENT_HVAC_IDLE
        if self.ac_mode:
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_HEAT

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_list

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return PRESET_AWAY if self._is_away else PRESET_NONE

    @property
    def preset_modes(self):
        """Return a list of available preset modes or PRESET_NONE if _away_temp is undefined."""
        return [PRESET_NONE, PRESET_AWAY] if self._away_temp else PRESET_NONE

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
            if self._is_device_active:
                await self._async_heater_turn_off()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return
        # Ensure we update the current operation after changing the mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = temperature
        await self._async_control_heating(force=True)
        self.async_write_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp is not None:
            return self._min_temp

        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp is not None:
            return self._max_temp

        # Get default temp from super class
        return super().max_temp

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        #_LOGGER.info("_async_sensor_changed runs for %s with state %s", new_state.name, new_state) #SPZB: log for debugging
        #_LOGGER.info("_async_sensor_changed runs for %s", new_state.name) #SPZB: log for debugging
        self._async_update_temp(new_state)
        await self._async_control_heating()
        self.async_write_ha_state()

    @callback
    #SPZB: made async to be able to call async functions for EUROTRONIC thermostat
    async def _async_switch_changed(self, event):
        """Handle heater switch state changes."""
        #SPZB: also get old state for handling EUROTRONIC thermostat HVAC modes
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        #SPZB: also check if old state is ok
        if new_state is None or old_state is None:
            return
        #SPZB: handle EUROTRONIC SPIRIT ZIGBEE thermostat
        #SPZB: Service set HVAC mode back to auto if set from auto to heat (e.g. manually)
        #if old_state.state != new_state.state: #SPZB: log for debugging (needs this and next line to work properly)
            #_LOGGER.info("Changed state from %s to %s for %s.", old_state.state, new_state.state, new_state.name) #SPZB: log for debugging

        if old_state.state == "auto" and new_state.state == "heat":
            data_auto = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_HVAC_MODE: HVAC_MODE_AUTO}
            await self.hass.services.async_call(
                CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, data_auto, blocking=True,
            )
            #SPZB: Service set temperature to max_temp
            data_temp = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_TEMPERATURE: self.max_temp}
            await self.hass.services.async_call(
                CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, data_temp, blocking=True,
            )
            #_LOGGER.info("Something tried to switch from auto to heat for %s, so we revert HVAC mode to auto", self.heater_entity_id) #SPZB: log for debugging
        #SPZB: Service set HVAC mode back to auto if set from off to heat (e.g. manually)
        elif old_state.state == "off" and new_state.state == "heat":
            data_auto = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_HVAC_MODE: HVAC_MODE_AUTO}
            await self.hass.services.async_call(
                CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, data_auto, blocking=True,
            )
            _LOGGER.info("data_auto: %s", data_auto)
            #SPZB: Service set temperature to max_temp
            data_temp = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_TEMPERATURE: self.max_temp}
            await self.hass.services.async_call(
                CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, data_temp, blocking=True,
            )
            #_LOGGER.info("data_temp: %s", data_temp) #SPZB: log for debugging
            #_LOGGER.info("Something tried to switch from off to heat for %s, so we change HVAC mode to auto", self.heater_entity_id) #SPZB: log for debugging
        self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._cur_temp = float(state.state)
            #_LOGGER.info("_async_update_temp: %s for %s", self._cur_temp, self.heater_entity_id) #SPZB: log for debugging
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    async def _async_control_heating(self, time=None, force=False):
        """Check if we need to turn heating on or off."""
        if self.startup == True: #SPZB: check if HA was freshly initialized
            await self._async_init_shutdown_thermostat() #SPZB: turn of the corresponding EUROTRONIC thermostat on startup
        #_LOGGER.info("_async_control_heating running for %s", self.heater_entity_id) #SPZB: log for debugging
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp, self._target_temp):
                self._active = True
                _LOGGER.info(
                    "Obtained current and target temperature. "
                    "SPZB0001 thermostat active. %s, %s",
                    self._cur_temp,
                    self._target_temp,
                )

            if not self._active or self._hvac_mode == HVAC_MODE_OFF:
                self._async_heater_turn_off()
                return

            if not force and time is None:
                # If the `force` argument is True, we
                # ignore `min_cycle_duration`.
                # If the `time` argument is not none, we were invoked for
                # keep-alive purposes, and `min_cycle_duration` is irrelevant.
                if self.min_cycle_duration:
                    #_LOGGER.info("force/time/self.min_cycle_duration %s/%s/%s for %s", force, time, self.min_cycle_duration, self.heater_entity_id) #SPZB: log for debugging
                    if self._is_device_active:
                        current_state = STATE_ON
                    else:
                        current_state = HVAC_MODE_OFF
                    long_enough = condition.state(
                        self.hass,
                        self.heater_entity_id,
                        current_state,
                        self.min_cycle_duration,
                    )
                    if not long_enough:
                        return

            too_cold = self._target_temp >= self._cur_temp + self._cold_tolerance
            too_hot = self._cur_temp >= self._target_temp + self._hot_tolerance
            #SPZB: log for debugging
            #_LOGGER.info("self._is_device_active: %s and self.ac_mode %s and too_cold: %s and too_hot: %s for %s", self._is_device_active, self.ac_mode, too_cold, too_hot, self.heater_entity_id)
            #SPZB: we need to handle that the EUROTRONIC thermostats could be "active" (auto + 5°C ... which means off) so we need to work around this in "_is_device_active"
            if self._is_device_active:
                if (self.ac_mode and too_cold) or (not self.ac_mode and too_hot):
                    _LOGGER.info("Turning off heater %s", self.heater_entity_id)
                    await self._async_heater_turn_off()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    _LOGGER.info(
                        "Keep-alive - Turning on heater %s", self.heater_entity_id
                    )
                    await self._async_heater_turn_on()
            else:
                if (self.ac_mode and too_hot) or (not self.ac_mode and too_cold):
                    _LOGGER.info("Turning on heater %s", self.heater_entity_id)
                    await self._async_heater_turn_on()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    _LOGGER.info(
                        "Keep-alive - Turning off heater %s", self.heater_entity_id
                    )
                    await self._async_heater_turn_off()

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        #SPZB: check for state == "heat"/"auto" instead of STATE_ON for EUROTRONIC Thermostat ...
        #SPZB: also check set temperature if device is set to "auto", if it is set to 5°C then it's off
        #return self.hass.states.is_state(self.heater_entity_id, "heat")
        state_heat = self.hass.states.is_state(self.heater_entity_id, "heat")
        state_auto = self.hass.states.is_state(self.heater_entity_id, "auto")
        state_temp = self.hass.states.get(self.heater_entity_id)
        #_LOGGER.info("%s.state = %s", self.heater_entity_id, state_temp) #SPZB: log for debugging
        #_LOGGER.info("%s.SetPointTemp = %s", self.heater_entity_id, state_temp.attributes[ATTR_TEMPERATURE]) #SPZB: log for debugging
        if state_auto and state_temp.attributes[ATTR_TEMPERATURE] == 5.0:
            #_LOGGER.info("state_auto: %s and %s.SetPointTemp = %s", state_auto, self.heater_entity_id, state_temp.attributes[ATTR_TEMPERATURE]) #SPZB: log for debugging
            return False 
        elif state_heat:
            #_LOGGER.info("state_heat: %s for %s", state_heat, self.heater_entity_id) #SPZB: log for debugging
            return state_heat
        elif state_auto:
            #_LOGGER.info("state_auto: %s for %s", state_auto, self.heater_entity_id) #SPZB: log for debugging
            return state_auto

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        #SPZB: old code below
        #data = {ATTR_ENTITY_ID: self.heater_entity_id}
        #await self.hass.services.async_call(
        #    HA_DOMAIN, SERVICE_TURN_ON, data, context=self._context
        #)
        #SPZB: handle EUROTRONIC SPIRIT ZIGBEE thermostat
        #SPZB: Service set HVAC mode to auto
        data_auto = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_HVAC_MODE: HVAC_MODE_AUTO}
        await self.hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, data_auto, blocking=True,
        )
        #_LOGGER.info("data_auto: %s for %s", data_auto, self.heater_entity_id) #SPZB: log for debugging
        #SPZB: Service set temperature to max_temp
        data_temp = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_TEMPERATURE: self.max_temp}
        await self.hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, data_temp, blocking=True,
        )
        #_LOGGER.info("data_temp: %s for %s", data_temp, self.heater_entity_id) #SPZB: log for debugging
        #_LOGGER.info("_async_heater_turn_on executed for %s", self.heater_entity_id) #SPZB: log for debugging

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        #SPZB: handle EUROTRONIC SPIRIT ZIGBEE thermostat
        #SPZB: Service set HVAC mode to off
        data_off = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_HVAC_MODE: HVAC_MODE_OFF}
        await self.hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, data_off, blocking=True,
        )
        #SPZB: Service set temperature to min_temp
        data_temp = {ATTR_ENTITY_ID: self.heater_entity_id, ATTR_TEMPERATURE: self.min_temp}
        await self.hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, data_temp, blocking=True,
        )
        #_LOGGER.info("_async_heater_turn_off executed for %s", self.heater_entity_id) #SPZB: log for debugging

        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_OFF, data, context=self._context
        )

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        if preset_mode == PRESET_AWAY and not self._is_away:
            self._is_away = True
            self._saved_target_temp = self._target_temp
            self._target_temp = self._away_temp
            await self._async_control_heating(force=True)
        elif preset_mode == PRESET_NONE and self._is_away:
            self._is_away = False
            self._target_temp = self._saved_target_temp
            await self._async_control_heating(force=True)

        self.async_write_ha_state()

    async def _async_init_shutdown_thermostat(self): #SPZB: new function for avoiding inconsistency on startup
        """Shutdown the connected SPZB0001 thermostat after restart of HA to prevent wrong state"""
        await self._async_heater_turn_off() # turn of the corresponding EUROTRONIC thermostat on startup
        self.startup = False
        #_LOGGER.info("_async_init_shutdown_thermostat running for %s", self.heater_entity_id) #SPZB: log for debugging