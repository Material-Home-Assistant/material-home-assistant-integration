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
            # Questo significa che il metodo _async_update_data verrà chiamato ogni 24 ore.
            update_interval=timedelta(hours=24),
        )
        self.entry = entry
        # Inizializza il client API con la sessione aiohttp di Home Assistant.
        self.api = MaterialHAApiClient(async_get_clientsession(hass))
        _LOGGER.debug("MaterialHALicenseCoordinator inizializzato.")

    async def _async_update_data(self):
        """
        Questo metodo viene chiamato dal DataUpdateCoordinator:
        1. All'avvio dell'integrazione (tramite async_config_entry_first_refresh).
        2. Periodicamente, in base a `update_interval`.
        3. Quando viene richiesto un aggiornamento manuale.

        Si occupa di contattare l'API per verificare lo stato della licenza.
        Gestisce gli errori in modo che l'integrazione non vada in crash
        o richieda un riavvio, ma gestisca lo stato (attivo/inattivo) dinamicamente.

        Returns:
            dict: Un dizionario contenente i dati della licenza, incluso lo stato.

        Raises:
            UpdateFailed: Se si verifica un errore di connessione all'API.
        """
        _LOGGER.info("Avvio _async_update_data per verificare lo stato della licenza.")

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
            _LOGGER.info("Verifica licenza completata. Stato API: %s", data.get("status"))

            # Aggiungiamo il timestamp dell'ultima verifica ai dati
            data["last_check"] = last_check
            return data

        except InvalidLicenseError as err:
            # Questo errore indica che la licenza non è valida (es. scaduta, non pagata).
            # Invece di far fallire l'integrazione con ConfigEntryAuthFailed (che richiederebbe un riavvio),
            # ritorniamo un payload che indica lo stato di fallimento.
            # Il listener in __init__.py userà questo stato per rimuovere la risorsa Lovelace.
            _LOGGER.warning(
                "Licenza non valida o scaduta: %s. La risorsa Lovelace verrà disattivata.",
                err
            )
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
