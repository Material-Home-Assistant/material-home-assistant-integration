"""Gestione dello storage persistente per la Secret Key."""
import logging
from homeassistant.helpers.storage import Store
from homeassistant.core import HomeAssistant

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

class MaterialStorage:
    """Classe per gestire lettura/scrittura su file .storage."""

    def __init__(self, hass: HomeAssistant):
        """Inizializza lo Store di HA."""
        # Questo crea un file in /config/.storage/material_home_assistant_auth
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load_secret_key(self):
        """Carica la secret_key dal file persistente."""
        try:
            data = await self._store.async_load()
            if data and "secret_key" in data:
                _LOGGER.debug("Secret key caricata con successo dallo storage.")
                return data["secret_key"]
            _LOGGER.debug("Nessuna secret key trovata nello storage.")
            return None
        except Exception as e:
            _LOGGER.error("Errore durante il caricamento della secret key: %s", e)
            return None

    async def async_save_secret_key(self, secret_key: str):
        """Salva la secret_key nel file persistente."""
        try:
            await self._store.async_save({"secret_key": secret_key})
            _LOGGER.debug("Secret key salvata con successo nello storage.")
        except Exception as e:
            _LOGGER.error("Errore durante il salvataggio della secret key: %s", e)