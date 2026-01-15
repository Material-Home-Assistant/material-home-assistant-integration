import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

# Configurazione del logger per vedere i messaggi nel log di HA
_LOGGER = logging.getLogger(__name__)

DOMAIN = "material_home_assistant"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Configura l'integrazione Material Home Assistant."""
    
    _LOGGER.info("Ciao! L'integrazione Material Home Assistant è stata caricata correttamente.")

    # Creiamo un'entità fittizia per vedere che funziona nella dashboard
    hass.states.async_set(f"{DOMAIN}.status", "Attivo", {
        "friendly_name": "Stato Material Home Assistant",
        "icon": "mdi:emoticon-happy"
    })

    # Restituiamo True per indicare che l'inizializzazione è riuscita
    return True