"""Sensore per Material Home Assistant."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_PLAN, CONF_STATUS
from .coordinator import MaterialHALicenseCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status",
        name="License Status",
        icon="mdi:license",
    ),
    SensorEntityDescription(
        key="plan",
        name="Plan",
        icon="mdi:star-circle",
    ),
    SensorEntityDescription(
        key="last_check",
        name="Last Check License",
        icon="mdi:clock-check",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura il sensore Material Home Assistant."""
    coordinator: MaterialHALicenseCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Recuperiamo la versione dell'integrazione in modo asincrono
    integration = await async_get_integration(hass, DOMAIN)
    version = integration.version

    async_add_entities(
        MaterialHASensor(coordinator, entry, version, description)
        for description in SENSOR_TYPES
    )

class MaterialHASensor(CoordinatorEntity, SensorEntity):
    """Rappresenta un sensore per Material Home Assistant."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaterialHALicenseCoordinator,
        entry: ConfigEntry,
        version: str,
        description: SensorEntityDescription
    ) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)
        self._entry = entry
        self._version = version
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Restituisce le informazioni sul dispositivo."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Material Home Assistant",
            manufacturer="Material Home Assistant",
            model="License Manager",
            sw_version=self._version,
            configuration_url="https://material-home-assistant.com",
        )

    @property
    def native_value(self):
        """Ritorna il valore del sensore."""
        value = self.coordinator.data.get(self.entity_description.key)

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if value and value != "UNKNOWN":
                return dt_util.parse_datetime(value)
            return None

        return value

    @property
    def extra_state_attributes(self) -> dict:
        """Ritorna attributi aggiuntivi."""
        # Manteniamo gli attributi extra solo per il sensore principale di stato,
        # rimuovendo 'message' come richiesto.
        if self.entity_description.key == "status":
            return {
                "status": self.coordinator.data.get("status", "UNKNOWN"),
                "plan": self.coordinator.data.get("plan", "UNKNOWN"),
                "last_check": self.coordinator.data.get("last_check", "UNKNOWN"),
            }
        return {}
