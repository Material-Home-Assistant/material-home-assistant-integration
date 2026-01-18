"""Coordinatore per aggiornamento dati e check licenza."""
from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_EMAIL, CONF_TOKEN, CONF_SECRET_KEY
from .api import MaterialHAApiClient, InvalidLicenseError, ApiConnectionError

_LOGGER = logging.getLogger(__name__)

class MaterialHALicenseCoordinator(DataUpdateCoordinator):
    """Coordinatore che verifica la licenza periodicamente."""

    def __init__(self, hass, entry):
        """Inizializza il coordinatore."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Frequenza di aggiornamento: 24 ore
            update_interval=timedelta(hours=24),
        )
        self.entry = entry
        self.api = MaterialHAApiClient(async_get_clientsession(hass))

    async def _async_update_data(self):
        """Questo metodo viene chiamato ogni 24h o all'avvio."""
        
        email = self.entry.data.get(CONF_EMAIL)
        token = self.entry.data.get(CONF_TOKEN)
        secret_key = self.entry.data.get(CONF_SECRET_KEY)

        try:
            # Chiamata di verifica
            data = await self.api.validate_license(email, token, secret_key)
            
            # Se ha successo, ritorniamo i dati.
            # Questi dati saranno disponibili in coordinator.data
            return data

        except InvalidLicenseError as err:
            # Caso 403/401: Licenza scaduta o non valida
            # ConfigEntryAuthFailed fa apparire una notifica "Riconfigurare" all'utente
            # e segna l'integrazione come "Errore Auth".
            # Cattureremo questo stato in __init__.py per rimuovere le risorse.
            raise ConfigEntryAuthFailed(f"Licenza non valida: {err}") from err

        except ApiConnectionError as err:
            # Caso 500/Connection Error
            # UpdateFailed dice a HA che l'aggiornamento è fallito TEMPORANEAMENTE.
            # HA riproverà automaticamente con backoff (tra 30s, 1min, etc.)
            raise UpdateFailed(f"Errore connessione API: {err}") from err