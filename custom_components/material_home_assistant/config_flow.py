"""Config Flow per Material Home Assistant."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN, CONF_EMAIL, CONF_TOKEN, CONF_SECRET_KEY, 
    CONF_STATUS, CONF_PLAN, CONF_RESOURCE_URL
)
from .api import MaterialHAApiClient, InvalidLicenseError, ApiConnectionError
from .storage import MaterialStorage

_LOGGER = logging.getLogger(__name__)

class MaterialHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione iniziale."""

    VERSION = 1

    def __init__(self):
        """Inizializza le variabili temporanee per il flow."""
        self._resource_url = None
        self._config_data = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Inserimento credenziali e validazione."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = MaterialHAApiClient(session)
            storage = MaterialStorage(self.hass)
            
            # Carichiamo la secret_key se esiste già (es. reinstallazione)
            stored_secret_key = await storage.async_load_secret_key()

            try:
                # Chiamata al backend (Qui potrebbe avvenire l'errore 400 se i dati sono errati)
                response = await client.validate_license(
                    email=user_input[CONF_EMAIL],
                    token=user_input[CONF_TOKEN],
                    secret_key=stored_secret_key
                )

                # Prepariamo i dati da salvare
                new_secret_key = response.get("secret_key")
                final_secret_key = new_secret_key if new_secret_key else stored_secret_key
                
                if new_secret_key:
                    await storage.async_save_secret_key(new_secret_key)

                self._resource_url = response.get("resource_url")
                
                # Salviamo i dati temporaneamente per usarli nello step manuale se serve
                self._config_data = {
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_STATUS: response.get("status"),
                    CONF_PLAN: response.get("plan"),
                    CONF_SECRET_KEY: final_secret_key,
                    CONF_RESOURCE_URL: self._resource_url
                }

                # TENTATIVO REGISTRAZIONE AUTOMATICA
                resource_added = await self._async_try_add_resource(self._resource_url)

                if not resource_added and self._resource_url:
                    # Se fallisce la registrazione automatica, andiamo allo step informativo
                    return await self.async_step_manual_resource()

                # Se tutto è ok, creiamo l'integrazione
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=self._config_data
                )

            except InvalidLicenseError:
                errors["base"] = "invalid_auth"
            except ApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                # Se vedi il log "Errore 400" qui, controlla il payload in api.py
                _LOGGER.error(f"Errore durante la validazione: {e}")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors
        )

    async def async_step_manual_resource(self, user_input=None):
        """Step 2: Mostrato solo se l'automazione fallisce."""
        if user_input is not None:
            # L'utente ha confermato di aver letto, creiamo l'entry
            return self.async_create_entry(
                title=self._config_data[CONF_EMAIL],
                data=self._config_data
            )

        return self.async_show_form(
            step_id="manual_resource",
            description_placeholders={"url": self._resource_url}
        )

    #async def _async_try_add_resource(self, url: str) -> bool:
    #    """TEST: Forziamo il fallimento per vedere lo step manuale."""
    #    _LOGGER.warning("SIMULAZIONE: Fallimento registrazione risorsa per test")
    #    return False # <--- Cambia temporaneamente in False

    async def _async_try_add_resource(self, url: str) -> bool:
        """Helper per aggiungere la risorsa Lovelace."""
        if not url:
            return False
        try:
            lovelace = self.hass.data.get("lovelace")
            if not lovelace: return False
            resources = getattr(lovelace, "resources", None)
            if not resources: return False

            if not resources.loaded:
                await resources.async_load()

            # Evitiamo duplicati
            if any(res.get("url") == url for res in resources.async_items()):
                return True

            await resources.async_create_item({"res_type": "module", "url": url})
            return True
        except Exception as e:
            _LOGGER.warning(f"Registrazione automatica risorsa fallita: {e}")
            return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Ritorna l'handler per le opzioni senza passare argomenti."""
        return MaterialHAOptionsFlowHandler() # CORRETTO: Nessun argomento qui

class MaterialHAOptionsFlowHandler(config_entries.OptionsFlow):
    """Gestisce la modifica (CONFIGURA) dell'integrazione."""

    async def async_step_init(self, user_input=None):
        """Gestisce il primo (e unico) step delle opzioni."""
        errors = {}
        
        # Recuperiamo i dati correnti per pre-popolare il form
        # self.config_entry.data contiene le info salvate al momento dell'installazione
        current_email = self.config_entry.data.get(CONF_EMAIL, "")
        current_token = self.config_entry.data.get(CONF_TOKEN, "")

        if user_input is not None:
            # Qui eseguiamo di nuovo la validazione se cambiano i dati
            session = async_get_clientsession(self.hass)
            client = MaterialHAApiClient(session)
            storage = MaterialStorage(self.hass)
            stored_secret_key = await storage.async_load_secret_key()

            try:
                response = await client.validate_license(
                    email=user_input[CONF_EMAIL],
                    token=user_input[CONF_TOKEN],
                    secret_key=stored_secret_key
                )
                
                # Prepariamo il dizionario aggiornato
                updated_data = {
                    **self.config_entry.data,
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_STATUS: response.get("status"),
                    CONF_PLAN: response.get("plan"),
                    CONF_RESOURCE_URL: response.get("resource_url")
                }
                
                # Aggiorniamo l'entry originale
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=updated_data
                )
                
                # Notifica di successo (chiude il form)
                return self.async_create_entry(title="", data={})

            except InvalidLicenseError:
                errors["base"] = "invalid_auth"
            except ApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Errore modifica opzioni: {e}")
                errors["base"] = "unknown"

        # IMPORTANTE: Lo schema deve contenere esattamente i campi definiti in strings.json
        # strings.json -> options -> step -> init -> data -> email e token
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=current_email): str,
                vol.Required(CONF_TOKEN, default=current_token): str,
            }),
            errors=errors
        )