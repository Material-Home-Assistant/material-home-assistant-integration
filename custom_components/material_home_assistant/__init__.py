"""Setup dell'integrazione Material Home Assistant."""
import logging
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, CoreState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.components.http import StaticPathConfig, HomeAssistantView # Import aggiunti

from .const import DOMAIN, CONF_RESOURCE_URL
from .coordinator import MaterialHALicenseCoordinator

_LOGGER = logging.getLogger(__name__)

# URL stabile del loader locale
LOCAL_LOADER_URL = f"/local/{DOMAIN}/material-home-assistant.js"

PLATFORMS = [] 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura l'integrazione."""
    _LOGGER.warning(f"Avvio setup entry per {DOMAIN}")

    # 1. Registrazione Percorso Statico per il loader.js
    path_www = hass.config.path(f"custom_components/{DOMAIN}/www")
    if os.path.exists(path_www):
        static_config = StaticPathConfig(
            url_path=f"/local/{DOMAIN}",
            path=path_www,
            cache_headers=False
        )
        await hass.http.async_register_static_paths([static_config])
    else:
        _LOGGER.error("Cartella www non trovata in %s", path_www)

    # 2. Registrazione dell'API View per il loader
    hass.http.register_view(MaterialHALoaderView(hass))
    
    # Inizializzazione Coordinatore
    coordinator = MaterialHALicenseCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async def _update_resources_when_ready(event=None):
        """Gestisce la risorsa Lovelace puntando al LOADER locale."""
        # Puntiamo sempre al loader locale, è lui che poi caricherà il resto
        _LOGGER.warning(f"DIAGNOSTICA MATERIAL HA: Gestione risorsa loader: {LOCAL_LOADER_URL}")
        try:
            await async_add_resource_if_missing(hass, LOCAL_LOADER_URL)
        except Exception as e:
            _LOGGER.warning("Errore gestione risorse Lovelace: %s", e)

    # Registrazione risorsa Lovelace all'avvio
    if hass.state == CoreState.running:
        await _update_resources_when_ready()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_resources_when_ready)
    
    entry.async_on_unload(coordinator.async_add_listener(lambda: _handle_coordinator_update(hass, coordinator)))
    
    return True

class MaterialHALoaderView(HomeAssistantView):
    """API che restituisce l'URL dinamico al loader.js."""
    url = f"/api/{DOMAIN}/get_url"
    name = f"api:{DOMAIN}:get_url"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        """Restituisce l'URL salvato nel coordinatore."""
        try:
            # 1. Verifica se il dominio esiste nei dati
            if DOMAIN not in self.hass.data or not self.hass.data[DOMAIN]:
                _LOGGER.warning("API chiamata ma l'integrazione non è ancora pronta")
                return self.json({"error": "Integration not ready"}, status_code=503)

            # 2. Recupera il coordinatore in modo sicuro
            # Usiamo next(iter(...)) per prendere la prima istanza disponibile
            entry_id = next(iter(self.hass.data[DOMAIN]))
            coordinator = self.hass.data[DOMAIN][entry_id]

            # 3. Verifica se il coordinatore ha dati
            if coordinator is None or coordinator.data is None:
                _LOGGER.warning("Coordinatore presente ma dati non ancora scaricati")
                return self.json({"error": "Data not available yet"}, status_code=503)

            # 4. Verifica la presenza dell'URL
            resource_url = coordinator.data.get("resource_url")
            if not resource_url:
                _LOGGER.error("Resource URL non trovato nei dati del coordinatore")
                return self.json({"error": "URL not found"}, status_code=404)

            # Tutto ok!
            return self.json({
                "url": resource_url,
                "version": coordinator.data.get("version", "1.0.0"),
                "status": "active"
            })

        except Exception as e:
            # Questo log ti dirà esattamente cosa sta causando l'errore 500
            _LOGGER.error("Errore critico nella View API: %s", e, exc_info=True)
            return self.json({"error": "Internal Server Error"}, status_code=500)

#class MaterialHALoaderView(HomeAssistantView):
#    """API che restituisce l'URL dinamico al loader.js."""
#    url = f"/api/{DOMAIN}/get_url"
#    name = f"api:{DOMAIN}:get_url"
#    requires_auth = True
#
#    def __init__(self, hass):
#        self.hass = hass
#
#    async def get(self, request):
#        """Restituisce l'URL salvato nel coordinatore o nel registro."""
#        # Recuperiamo il coordinatore dai dati
#        # Nota: assumiamo che ci sia una sola istanza dell'integrazione
#        entry_id = list(self.hass.data[DOMAIN].keys())[0]
#        coordinator = self.hass.data[DOMAIN][entry_id]
#        
#        if coordinator.data and "resource_url" in coordinator.data:
#            return self.json({
#                "url": coordinator.data["resource_url"],
#                "version": coordinator.data.get("version", "1.0.0")
#            })
#        
#        return self.json({"error": "No URL available"}, status_code=404)

    #async def _update_resources_when_ready(event=None):
    #    """Funzione lanciata quando HA è pronto."""
    #    if coordinator.data and "resource_url" in coordinator.data:
    #        url = coordinator.data["resource_url"]
    #        _LOGGER.warning(f"DIAGNOSTICA MATERIAL HA: Gestione risorsa per: {url}")
    #        try:
    #            await async_add_resource_if_missing(hass, url)
    #        except Exception as e:
    #            _LOGGER.warning("Errore gestione risorse Lovelace: %s", e)
    #    else:
    #        _LOGGER.error("DIAGNOSTICA MATERIAL HA: resource_url non trovato!")
#
    ## Registrazione risorsa Lovelace all'avvio
    #if hass.state == CoreState.running:
    #    await _update_resources_when_ready()
    #else:
    #    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_resources_when_ready)
    #
    ## Listener per aggiornamenti dal coordinatore
    #entry.async_on_unload(coordinator.async_add_listener(lambda: _handle_coordinator_update(hass, coordinator)))
    #
    #return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Gestisce la rimozione completa dell'integrazione e della risorsa."""
    
    # 1. Recuperiamo l'URL della risorsa dai dati salvati nell'entry
    resource_url = entry.data.get(CONF_RESOURCE_URL)

    if resource_url:
        _LOGGER.debug("Rimozione risorsa Lovelace: %s", resource_url)
        try:
            lovelace = hass.data.get("lovelace")
            # Accediamo alle risorse della Dashboard
            if lovelace and hasattr(lovelace, "resources"):
                resources = lovelace.resources
                if not resources.loaded:
                    await resources.async_load()

                # Cerchiamo l'ID della risorsa che corrisponde all'URL
                resource_id = next(
                    (res.get("id") for res in resources.async_items() 
                     if res.get("url") == resource_url),
                    None
                )

                if resource_id:
                    await resources.async_delete_item(resource_id)
                    _LOGGER.info("Risorsa Lovelace rimossa correttamente")
        except Exception as e:
            _LOGGER.error("Errore durante la pulizia della risorsa: %s", e)

    # 2. Rimuoviamo i dati dell'integrazione dalla memoria (il tuo codice originale)
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    # 3. Se hai piattaforme (sensor, binary_sensor, ecc.), scaricale
    # Se non ne hai, puoi omettere questa riga
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    
    return unload_ok

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