"""Setup dell'integrazione Material Home Assistant."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, CoreState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from .const import DOMAIN
from .coordinator import MaterialHALicenseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [] 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura l'integrazione."""
    _LOGGER.warning(f"Avvio setup entry per {DOMAIN}")
    
    # Inizializzazione Coordinatore
    coordinator = MaterialHALicenseCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async def _update_resources_when_ready(event=None):
        """Funzione lanciata quando HA è pronto."""
        if coordinator.data and "resource_url" in coordinator.data:
            url = coordinator.data["resource_url"]
            _LOGGER.warning(f"DIAGNOSTICA MATERIAL HA: Gestione risorsa per: {url}")
            try:
                await async_add_resource_if_missing(hass, url)
            except Exception as e:
                _LOGGER.warning("Errore gestione risorse Lovelace: %s", e)
        else:
            _LOGGER.error("DIAGNOSTICA MATERIAL HA: resource_url non trovato!")

    # Registrazione risorsa Lovelace all'avvio
    if hass.state == CoreState.running:
        await _update_resources_when_ready()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_resources_when_ready)
    
    # Listener per aggiornamenti dal coordinatore
    entry.async_on_unload(coordinator.async_add_listener(lambda: _handle_coordinator_update(hass, coordinator)))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Rimozione dell'integrazione."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True

async def _handle_coordinator_update(hass: HomeAssistant, coordinator):
    """Gestisce gli aggiornamenti dinamici dal coordinatore."""
    if coordinator.last_update_success and hass.state == CoreState.running:
        if coordinator.data and "resource_url" in coordinator.data:
            _LOGGER.warning("MATERIAL HA: Aggiornamento risorsa rilevato.")
            try:
                await async_add_resource_if_missing(hass, coordinator.data["resource_url"])
            except Exception as e:
                _LOGGER.warning("Errore aggiornamento risorsa Lovelace: %s", e)

async def async_add_resource_if_missing(hass: HomeAssistant, url: str):
    """Aggiunge la risorsa al registro Lovelace se non presente."""
    # Accediamo al componente lovelace
    lovelace = hass.data.get("lovelace")
    if not lovelace:
        _LOGGER.debug("Lovelace non trovato in hass.data")
        return

    # Recuperiamo la collezione delle risorse
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        _LOGGER.debug("Risorse Lovelace non disponibili")
        return

    # Carica le risorse se non sono ancora pronte
    if not resources.loaded:
        await resources.async_load()

    # Controlla se l'URL esiste già per evitare duplicati
    if any(res.get("url") == url for res in resources.async_items()):
        _LOGGER.debug("Risorsa già presente: %s", url)
        return

    # Creazione effettiva della risorsa
    await resources.async_create_item({
        "res_type": "module",
        "url": url
    })
    _LOGGER.warning("DIAGNOSTICA MATERIAL HA: Nuova risorsa aggiunta correttamente: %s", url)