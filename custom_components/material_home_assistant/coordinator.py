"""Coordinatore per aggiornamento dati e check licenza."""
from datetime import timedelta
import logging
from homeassistant.util import dt as dt_util

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_EMAIL, CONF_TOKEN, CONF_SECRET_KEY
from .api import MaterialHAApiClient, InvalidLicenseError, ApiConnectionError

_LOGGER = logging.getLogger(__name__)

class MaterialHALicenseCoordinator(DataUpdateCoordinator):
    """
    Coordinatore per l'integrazione Material Home Assistant.
    Si occupa di verificare periodicamente lo stato della licenza
    contattando l'API esterna.
    """

    def __init__(self, hass, entry):
        """
        Inizializza il coordinatore.

        Args:
            hass (HomeAssistant): L'istanza di Home Assistant.
            entry (ConfigEntry): L'entry di configurazione dell'integrazione.
        """
        _LOGGER.debug("Inizializzazione MaterialHALicenseCoordinator per entry_id: %s", entry.entry_id)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Frequenza di aggiornamento: 24 ore.
            update_interval=timedelta(hours=24),
        )
        self.entry = entry
        # Inizializza il client API con la sessione aiohttp di Home Assistant.
        self.api = MaterialHAApiClient(async_get_clientsession(hass))
        _LOGGER.debug("MaterialHALicenseCoordinator inizializzato.")

    async def _async_update_data(self):
        """
        Contatta l'API per verificare lo stato della licenza.
        """
        _LOGGER.debug("Avvio _async_update_data per verificare lo stato della licenza.")

        email = self.entry.data.get(CONF_EMAIL)
        token = self.entry.data.get(CONF_TOKEN)
        secret_key = self.entry.data.get(CONF_SECRET_KEY)

        # Data e ora corrente per il timestamp dell'ultima verifica
        last_check = dt_util.now().isoformat()

        if not all([email, token, secret_key]):
            _LOGGER.error("Credenziali API mancanti. Impossibile validare la licenza.")
            # Ritorna uno stato INVALID se le credenziali non sono complete
            return {
                "status": "INVALID",
                "resource_url": None,
                "message": "Credenziali mancanti",
                "last_check": last_check
            }

        try:
            # Chiamata all'API per validare la licenza.
            # Il risultato atteso è un dizionario con "status" e "resource_url".
            data = await self.api.validate_license(email, token, secret_key)
            _LOGGER.debug("Verifica licenza completata. Stato API: %s", data.get("status"))

            # Aggiungiamo il timestamp dell'ultima verifica ai dati
            data["last_check"] = last_check
            return data

        except InvalidLicenseError as err:
            _LOGGER.warning("Licenza non valida o scaduta: %s", err)
            return {
                "status": "INVALID",
                "resource_url": None,
                "message": str(err),
                "last_check": last_check
            }

        except ApiConnectionError as err:
            # Questo errore indica un problema di connessione temporaneo all'API.
            # UpdateFailed notifica Home Assistant di riprovare più tardi con un backoff.
            # Lo stato precedente (e la risorsa Lovelace) rimarranno attivi fino al prossimo
            # aggiornamento andato a buon fine.
            _LOGGER.error("Errore di connessione all'API durante la verifica licenza: %s", err)
            raise UpdateFailed(f"Errore di connessione all'API: {err}") from err

        except Exception as err:
            # Cattura qualsiasi altro errore inaspettato durante l'aggiornamento.
            _LOGGER.exception("Errore inatteso durante l'aggiornamento del coordinatore: %s", err)
            raise UpdateFailed(f"Errore inatteso: {err}") from err