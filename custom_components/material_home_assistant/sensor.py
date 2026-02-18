"""Sensore per Material Home Assistant."""
import logging
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
from homeassistant.util import dt as dt_util

from .const import DOMAIN, VERSION, DEVICE_NAME, DEVICE_MODEL, WEBSITE_URL
from .coordinator import MaterialHALicenseCoordinator

_LOGGER = logging.getLogger(__name__)

# Definiamo i sensori con chiavi semplici
SENSOR_TYPES: tuple[tuple[SensorEntityDescription, str], ...] = (
    (
        SensorEntityDescription(
            key=f"{DOMAIN}_license_status",
            name="License Status",
            icon="mdi:license",
        ),
        "status",
    ),
    (
        SensorEntityDescription(
            key=f"{DOMAIN}_plan",
            name="Plan",
            icon="mdi:star-circle",
        ),
        "plan",
    ),
    (
        SensorEntityDescription(
            key=f"{DOMAIN}_last_check_license",
            name="Last Check License",
            icon="mdi:clock-check",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        "last_check",
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura il sensore Material Home Assistant."""
    _LOGGER.debug("Setting up sensor platform for Material Home Assistant.")
    coordinator: MaterialHALicenseCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Usiamo una versione fissa per evitare problemi di caricamento
    version = VERSION

    entities = []
    for description, data_key in SENSOR_TYPES:
        entities.append(
            MaterialHASensor(coordinator, entry, version, description, data_key)
        )

    _LOGGER.debug("Sensor entities created, adding to Home Assistant.")
    async_add_entities(entities)
    _LOGGER.debug("Sensor entities added successfully.")

class MaterialHASensor(CoordinatorEntity, SensorEntity):
    """Rappresenta un sensore per Material Home Assistant."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaterialHALicenseCoordinator,
        entry: ConfigEntry,
        version: str,
        description: SensorEntityDescription,
        data_key: str
    ) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)
        self._entry = entry
        self._version = version
        self.entity_description = description
        self._data_key = data_key

        # Unique ID basato sull'entry_id.
        # Se l'integrazione viene rimossa e riaggiunta, entry_id cambia,
        # quindi avremo sempre entità nuove e pulite.
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Restituisce le informazioni sul dispositivo."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_NAME,
            model=DEVICE_MODEL,
            sw_version=self._version,
            hw_version="Software",
            configuration_url=WEBSITE_URL,
        )

    @property
    def native_value(self):
        """Ritorna il valore del sensore."""
        value = self.coordinator.data.get(self._data_key)

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if value and value != "UNKNOWN":
                try:
                    return dt_util.parse_datetime(value)
                except (ValueError, TypeError):
                    _LOGGER.warning("Impossibile parsare la data: %s", value)
                    return None
            return None

        return value

    @property
    def extra_state_attributes(self) -> dict:
        """Ritorna attributi aggiuntivi."""
        if self.entity_description.key == f"{DOMAIN}_license_status":
            return {
                "status": self.coordinator.data.get("status", "UNKNOWN"),
                "plan": self.coordinator.data.get("plan", "UNKNOWN"),
                "last_check": self.coordinator.data.get("last_check", "UNKNOWN"),
                "hash_key": self.coordinator.data.get("hash_key", "UNKNOWN"),
            }
        return {}
