"""Sensore per Material Home Assistant."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.loader import async_get_integration

from .const import DOMAIN, CONF_PLAN, CONF_STATUS
from .coordinator import MaterialHALicenseCoordinator

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

    async_add_entities([MaterialHALicenseSensor(coordinator, entry, version)])

class MaterialHALicenseSensor(CoordinatorEntity, SensorEntity):
    """Rappresenta lo stato della licenza Material Home Assistant."""

    _attr_has_entity_name = True
    _attr_name = "License Status"
    _attr_icon = "mdi:license"

    def __init__(self, coordinator: MaterialHALicenseCoordinator, entry: ConfigEntry, version: str) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)
        self._entry = entry
        self._version = version
        self._attr_unique_id = f"{entry.entry_id}_license_status"

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
    def native_value(self) -> str:
        """Ritorna lo stato principale (es. ACTIVE, EXPIRED)."""
        return self.coordinator.data.get("status", "UNKNOWN")

    @property
    def extra_state_attributes(self) -> dict:
        """Ritorna attributi aggiuntivi (status, plan, last_check)."""
        return {
            "status": self.coordinator.data.get("status", "UNKNOWN"),
            "plan": self.coordinator.data.get("plan", "UNKNOWN"),
            "last_check": self.coordinator.data.get("last_check", "UNKNOWN"),
            "message": self.coordinator.data.get("message", "")
        }
