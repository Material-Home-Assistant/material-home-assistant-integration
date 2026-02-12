"""
Setup dell'integrazione Material Home Assistant.
Questo file è il punto di ingresso principale per l'integrazione.
Gestisce il caricamento, lo scaricamento e il ricaricamento dell'integrazione.
"""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_RESOURCE_URL
from .coordinator import MaterialHALicenseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Questa funzione viene chiamata da Home Assistant quando l'integrazione viene caricata.
    """
    _LOGGER.info("Avvio di async_setup_entry per Material Home Assistant (entry_id: %s)", entry.entry_id)

    coordinator = MaterialHALicenseCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Carica le piattaforme (es. sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _handle_coordinator_update(hass, entry, coordinator)
        )
    )

    # Esegue la prima gestione della risorsa basandosi sui dati appena ottenuti.
    _handle_coordinator_update(hass, entry, coordinator)

    # Abilita il ricaricamento dell'integrazione.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Setup dell'integrazione Material Home Assistant completato con successo.")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Questa funzione viene chiamata quando l'integrazione viene scaricata (es. ricaricamento o stop di HA).
    NOTA: Non rimuoviamo la risorsa qui per evitare che debba essere ricaricata dal browser inutilmente.
    """
    _LOGGER.info("Avvio di async_unload_entry per Material Home Assistant (entry_id: %s)", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(entry.entry_id, None)

    _LOGGER.info("Unload dell'integrazione Material Home Assistant completato.")
    return unload_ok

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Questa funzione viene chiamata SOLO quando l'integrazione viene rimossa definitivamente dall'utente.
    Qui è dove dobbiamo pulire la risorsa Lovelace.
    """
    _LOGGER.info("Rimozione definitiva dell'integrazione Material Home Assistant (entry_id: %s)", entry.entry_id)

    resource_url = entry.data.get(CONF_RESOURCE_URL)
    if resource_url:
        await async_remove_resource(hass, resource_url)

    _LOGGER.info("Pulizia completata.")

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Gestisce il ricaricamento dell'integrazione."""
    await hass.config_entries.async_reload(entry.entry_id)


def _handle_coordinator_update(hass: HomeAssistant, entry: ConfigEntry, coordinator: MaterialHALicenseCoordinator):
    """Gestisce i dati ricevuti dal coordinatore e agisce di conseguenza."""
    if not coordinator.last_update_success:
        return

    status = coordinator.data.get("status")
    resource_url = coordinator.data.get("resource_url")
    notification_id = f"{DOMAIN}_payment_warning"

    # Salviamo l'URL nell'entry per coerenza
    if resource_url and entry.data.get(CONF_RESOURCE_URL) != resource_url:
        new_data = entry.data.copy()
        new_data[CONF_RESOURCE_URL] = resource_url
        hass.config_entries.async_update_entry(entry, data=new_data)

    if status == "ACTIVE":
        hass.async_create_task(async_dismiss_payment_notification(hass, notification_id))
        if resource_url:
            hass.async_create_task(async_add_or_update_resource(hass, resource_url))

    elif status == "PAST_DUE":
        hass.async_create_task(async_create_payment_notification(hass, notification_id))
        if resource_url:
            hass.async_create_task(async_add_or_update_resource(hass, resource_url))

    elif status in ["UNPAID", "EXPIRED", "INVALID"]:
        hass.async_create_task(async_dismiss_payment_notification(hass, notification_id))
        url_to_remove = resource_url or entry.data.get(CONF_RESOURCE_URL)
        if url_to_remove:
            hass.async_create_task(async_remove_resource(hass, url_to_remove))

    else:
        url_to_remove = resource_url or entry.data.get(CONF_RESOURCE_URL)
        if url_to_remove:
            hass.async_create_task(async_remove_resource(hass, url_to_remove))

async def async_add_or_update_resource(hass: HomeAssistant, url: str):
    """Aggiunge una risorsa al registro Lovelace."""
    try:
        lovelace = hass.data.get("lovelace")
        if not lovelace or not hasattr(lovelace, "resources"):
            _LOGGER.warning("Componente Lovelace non pronto, impossibile aggiungere risorsa.")
            return

        resources = lovelace.resources
        if not resources.loaded:
            await resources.async_load()

        # Cerca se esiste già una risorsa con questo URL
        existing_res = next((res for res in resources.async_items() if res.get("url") == url), None)

        if not existing_res:
            _LOGGER.info("Aggiunta nuova risorsa Lovelace al registro: %s", url)
            await resources.async_create_item({"res_type": "module", "url": url})
        else:
            _LOGGER.debug("La risorsa Lovelace esiste già: %s", url)

    except Exception as e:
        _LOGGER.error("Errore durante l'aggiunta della risorsa Lovelace: %s", e, exc_info=True)

async def async_remove_resource(hass: HomeAssistant, url: str):
    """Rimuove una risorsa dal registro Lovelace."""
    try:
        lovelace = hass.data.get("lovelace")
        if not lovelace or not hasattr(lovelace, "resources"):
            _LOGGER.warning("Componente Lovelace non pronto, impossibile rimuovere risorsa.")
            return

        resources = lovelace.resources
        if not resources.loaded:
            await resources.async_load()

        # Cerca la risorsa da rimuovere
        resource_id = next((res.get("id") for res in resources.async_items() if res.get("url") == url), None)

        if resource_id:
            _LOGGER.info("Rimozione della risorsa Lovelace dal registro: %s", url)
            await resources.async_delete_item(resource_id)
    except Exception as e:
        _LOGGER.error("Errore durante la rimozione della risorsa Lovelace: %s", e, exc_info=True)

async def async_create_payment_notification(hass: HomeAssistant, notification_id: str):
    """Crea una notifica persistente per problemi di pagamento."""
    await hass.services.async_call(
        "persistent_notification", "create",
        {
            "notification_id": notification_id,
            "title": "Material Home Assistant - Avviso di Pagamento",
            "message": "Il tuo ultimo tentativo di rinnovo della licenza non è andato a buon fine. Per favore, controlla i tuoi dati di pagamento per evitare la disattivazione dei componenti.",
        },
    )

async def async_dismiss_payment_notification(hass: HomeAssistant, notification_id: str):
    """Rimuove la notifica persistente di pagamento."""
    await hass.services.async_call(
        "persistent_notification", "dismiss",
        {"notification_id": notification_id},
    )
