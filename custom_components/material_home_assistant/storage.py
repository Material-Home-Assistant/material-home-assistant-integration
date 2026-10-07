"""Gestione dello storage persistente per la Secret Key e i metadati."""
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

    async def async_load_data(self) -> dict:
        """Carica l'intero dizionario dallo storage."""
        try:
            data = await self._store.async_load()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            _LOGGER.error("Errore durante il caricamento dello storage: %s", e)
            return {}

    async def async_load_secret_key(self):
        """Carica la secret_key dal file persistente."""
        data = await self.async_load_data()
        return data.get("secret_key")

    async def async_save_secret_key(self, secret_key: str):
        """Salva la secret_key nel file persistente."""
        try:
            data = await self.async_load_data()
            data["secret_key"] = secret_key
            await self._store.async_save(data)
            _LOGGER.debug("Secret key salvata con successo nello storage.")
        except Exception as e:
            _LOGGER.error("Errore durante il salvataggio della secret key: %s", e)

    async def async_load_card_version(self):
        """Carica la versione della card dal file persistente."""
        data = await self.async_load_data()
        return data.get("card_version")

    async def async_save_card_version(self, card_version: str):
        """Salva la versione della card nel file persistente."""
        try:
            data = await self.async_load_data()
            data["card_version"] = card_version
            await self._store.async_save(data)
            _LOGGER.debug("Versione card salvata con successo nello storage: %s", card_version)
        except Exception as e:
            _LOGGER.error("Errore durante il salvataggio della versione card: %s", e)