"""Config Flow per Material Home Assistant."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_EMAIL, CONF_TOKEN, CONF_SECRET_KEY, CONF_STATUS, CONF_PLAN
from .api import MaterialHAApiClient, InvalidLicenseError, ApiConnectionError
from .storage import MaterialStorage

class MaterialHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione iniziale."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Primo step: L'utente inserisce Email e Token."""
        errors = {}

        if user_input is not None:
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

                new_secret_key = response.get("secret_key")
                if new_secret_key:
                    await storage.async_save_secret_key(new_secret_key)
                    final_secret_key = new_secret_key
                else:
                    final_secret_key = stored_secret_key

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_STATUS: response.get("status"),
                        CONF_PLAN: response.get("plan"),
                        CONF_SECRET_KEY: final_secret_key
                    }
                )

            except InvalidLicenseError:
                errors["base"] = "invalid_auth"
            except ApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_TOKEN): str,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Definisce che questa integrazione supporta le Opzioni."""
        return MaterialHAOptionsFlowHandler(config_entry)


class MaterialHAOptionsFlowHandler(config_entries.OptionsFlow):
    """Gestisce la modifica delle opzioni (es. cambio token)."""

    # CORREZIONE: Abbiamo rimosso il metodo __init__ custom.
    # config_entries.OptionsFlow gestisce automaticamente self.config_entry
    # quando viene inizializzato dal framework.

    async def async_step_init(self, user_input=None):
        """Gestisce il form delle opzioni."""
        errors = {}
        
        # Recuperiamo i valori attuali. 
        # Nota: usiamo self.config_entry che è popolato automaticamente.
        current_email = self.config_entry.data.get(CONF_EMAIL)
        current_token = self.config_entry.data.get(CONF_TOKEN)

        if user_input is not None:
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
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_STATUS: response.get("status"),
                        CONF_PLAN: response.get("plan")
                    }
                )
                return self.async_create_entry(title="", data={})

            except InvalidLicenseError:
                errors["base"] = "invalid_auth"
            except ApiConnectionError:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL, default=current_email): str,
            vol.Required(CONF_TOKEN, default=current_token): str,
        })

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )