"""Config Flow per Material Home Assistant."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import translation

from .const import (
    DOMAIN, CONF_EMAIL, CONF_TOKEN, CONF_SECRET_KEY, 
    CONF_STATUS, CONF_PLAN, CONF_HASH_KEY, CONF_RESOURCE_URL, REQUIREMENTS_URL
)
from .api import MaterialHAApiClient, InvalidLicenseError, ApiConnectionError
from .storage import MaterialStorage
from . import async_remove_resource

_LOGGER = logging.getLogger(__name__)

class MaterialHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione iniziale."""

    VERSION = 1

    def __init__(self):
        """Inizializza le variabili temporanee per il flow."""
        self._resource_url = None
        self._config_data = {}
        self._need_to_add_resource_on_finish = False

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
                _LOGGER.debug("Calling validate_license...")
                response = await client.validate_license(
                    email=user_input[CONF_EMAIL],
                    token=user_input[CONF_TOKEN],
                    secret_key=stored_secret_key
                )
                _LOGGER.debug("API response received: %s", response)

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
                    CONF_HASH_KEY: response.get("hash_key"),
                    CONF_SECRET_KEY: final_secret_key,
                    CONF_RESOURCE_URL: self._resource_url
                }

                # VERIFICA E TEST AGGIUNTA RISORSA
                # Controlliamo se esiste già
                resource_exists = await self._async_resource_exists(self._resource_url)

                if resource_exists:
                    # Esiste già, non dobbiamo fare nulla alla fine
                    _LOGGER.debug("La risorsa esiste già, procedo al finish.")
                    self._need_to_add_resource_on_finish = False
                    return await self.async_step_finish()

                # Proviamo ad aggiungerla per vedere se funziona
                added = await self._async_try_add_resource(self._resource_url, "module")

                if added:
                    # Successo! La rimuoviamo subito per non lasciarla appesa se l'utente chiude il flow.
                    # Verrà riaggiunta definitivamente solo alla fine del flow.
                    _LOGGER.debug("Risorsa aggiunta con successo (test). Rimozione temporanea.")
                    await async_remove_resource(self.hass, self._resource_url)
                    self._need_to_add_resource_on_finish = True
                    return await self.async_step_finish()
                else:
                    # Fallito, andiamo al manuale
                    _LOGGER.warning("Impossibile aggiungere automaticamente la risorsa. Richiesto intervento manuale.")
                    self._need_to_add_resource_on_finish = False
                    return await self.async_step_manual_resource()

            except InvalidLicenseError:
                errors["base"] = "invalid_auth"
            except ApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                # Se vedi il log "Errore 400" qui, controlla il payload in api.py
                _LOGGER.error("Errore durante la validazione: %s", e, exc_info=True)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors
        )

    async def async_step_finish(self, user_input=None):
        """Step finale: Controlla dipendenze e avvisa l'utente."""

        font_url = "https://fonts.googleapis.com/css2?family=Figtree:ital,wght@0,300..900;1,300..900&display=swap"

        if user_input is not None:
            # Aggiungiamo la risorsa principale se necessario
            if self._need_to_add_resource_on_finish and self._resource_url:
                _LOGGER.debug("Aggiunta definitiva della risorsa Lovelace.")
                await self._async_try_add_resource(self._resource_url, "module")

            if user_input.get("add_font"):
                _LOGGER.debug("Aggiunta del font Figtree.")
                await self._async_try_add_resource(font_url, "css")

            return self.async_create_entry(
                title=self._config_data[CONF_EMAIL],
                data=self._config_data
            )

        # Controllo Dipendenze
        missing_deps = await self._check_dependencies()
        dependency_warning = ""
        show_font_checkbox = False

        if missing_deps:
            # Recuperiamo le traduzioni per costruire il messaggio
            # Carichiamo anche la categoria "issues"
            # Carica le issues
            issues_trans = await translation.async_get_translations(
                self.hass, self.hass.config.language, "issues", [DOMAIN]
            )
            # Carica la config
            config_trans = await translation.async_get_translations(
                self.hass, self.hass.config.language, "config", [DOMAIN]
            )

            # Chiavi di traduzione (fallback in inglese se non trovate)
            # Nota: async_get_translations restituisce un dizionario piatto con chiavi complete
            # es: "component.material_home_assistant.issues.deps_warnings.title"

            t_title = issues_trans.get(f"component.{DOMAIN}.issues.deps_warnings.title", "")
            t_intro = issues_trans.get(f"component.{DOMAIN}.issues.deps_warnings.description", "")
            t_req = config_trans.get(f"component.{DOMAIN}.config.step.finish.data.required", "")
            t_rec = config_trans.get(f"component.{DOMAIN}.config.step.finish.data.recommended", "")

            # Recuperiamo il template per la documentazione
            t_doc_template = config_trans.get(f"component.{DOMAIN}.config.step.finish.data.documentation", "")

            # Formattiamo il link della documentazione
            t_doc_link = t_doc_template.format(docs_url=REQUIREMENTS_URL)

            dependency_warning = f"\n\n**{t_title}**\n{t_intro}\n\n"

            for dep in missing_deps:
                if dep["name"] == "Figtree Font":
                    show_font_checkbox = True
                    # Il font viene mostrato nella lista come tutti gli altri
                    # Non usiamo 'continue' qui, così appare nella lista testuale

                req_str = f"**{t_req}**" if dep.get('required') else t_rec

                links = f"[Docs]({dep['url']})"
                if hacs_url := dep.get('hacs_url'):
                    links += f" | [HACS]({hacs_url})"

                dependency_warning += f"- {dep['name']} {req_str}: {links}\n"

            # Aggiungiamo il link alla documentazione alla fine
            dependency_warning += f"\n{t_doc_link}"

        data_schema = vol.Schema({})
        if show_font_checkbox:
            # Checkbox per installare il font automaticamente
            # Usiamo una chiave descrittiva se possibile, o un label chiaro
            data_schema = vol.Schema({
                vol.Optional("add_font", default=True): bool
            })
            # Nota: La label della checkbox ("add_font") dovrebbe essere tradotta nel file strings.json/en.json
            # Ma qui usiamo il default o possiamo iniettare una descrizione se supportato,
            # ma ConfigFlow standard usa le traduzioni per i campi schema.

        return self.async_show_form(
            step_id="finish",
            data_schema=data_schema,
            description_placeholders={"dependency_warning": dependency_warning}
        )

    async def _check_dependencies(self):
        """Verifica se le dipendenze richieste sono installate."""
        missing = []

        # Lista delle dipendenze da controllare
        dependencies = [
            {
                "name": "Material You Theme and Utilities",
                "type": "resource",
                "keyword": "material-you-utilities",
                "url": "https://github.com/Nerwyn/material-you-utilities",
                "hacs_url": "https://my.home-assistant.io/redirect/hacs_repository/?repository=material-you-utilities&owner=Nerwyn&category=Plugin",
                "required": False
            },
            {
                "name": "Material Symbols",
                "type": "component",
                "id": "material_symbols",
                "url": "https://github.com/beecho01/material-symbols",
                "hacs_url": "https://my.home-assistant.io/redirect/hacs_repository/?owner=beecho01&repository=material-symbols",  # Esempio: "/hacs/repository/12345678"
                "required": True
            },
            {
                "name": "Swipe Card",
                "type": "resource",
                "keyword": "swipe-card",
                "url": "https://github.com/bramkragten/swipe-card",
                "hacs_url": "https://my.home-assistant.io/redirect/hacs_repository/?repository=swipe-card&owner=bramkragten&category=Plugin",
                "required": True
            },
            {
                "name": "Button Card",
                "type": "resource",
                "keyword": "button-card",
                "url": "https://github.com/custom-cards/button-card",
                "hacs_url": "https://my.home-assistant.io/redirect/hacs_repository/?repository=button-card&owner=custom-cards&category=Plugin",
                "required": True
            },
            {
                "name": "Card Mod",
                "type": "resource",
                "keyword": "card-mod",
                "url": "https://github.com/thomasloven/lovelace-card-mod",
                "hacs_url": "https://my.home-assistant.io/redirect/hacs_repository/?owner=thomasloven&repository=lovelace-card-mod",
                "required": True
            },
            {
                "name": "Auto Entities",
                "type": "resource",
                "keyword": "auto-entities",
                "url": "https://github.com/thomasloven/lovelace-auto-entities",
                "hacs_url": "https://my.home-assistant.io/redirect/hacs_repository/?owner=thomasloven&repository=lovelace-auto-entities",
                "required": True
            },
            {
                "name": "Figtree Font",
                "type": "resource",
                "keyword": "family=Figtree",
                "url": "https://fonts.google.com/specimen/Figtree",
                "hacs_url": None,
                "required": False
            }
        ]

        # 1. Controllo Componenti (Integrazioni)
        installed_components = self.hass.config.components

        # 2. Controllo Risorse Lovelace
        lovelace_resources = []
        try:
            lovelace = self.hass.data.get("lovelace")
            if lovelace:
                resources = getattr(lovelace, "resources", None)
                if resources:
                    if not resources.loaded:
                        await resources.async_load()
                    # Creiamo una lista di URL delle risorse installate
                    lovelace_resources = [res.get("url", "") for res in resources.async_items()]
        except Exception as e:
            _LOGGER.warning("Impossibile verificare le risorse Lovelace: %s", e)

        for dep in dependencies:
            is_installed = False

            if dep["type"] == "component":
                if dep["id"] in installed_components:
                    is_installed = True

            elif dep["type"] == "resource":
                # Controlla se la keyword è presente in almeno uno degli URL delle risorse
                if any(dep["keyword"] in url for url in lovelace_resources):
                    is_installed = True

            if not is_installed:
                missing.append(dep)

        return missing

    async def async_step_manual_resource(self, user_input=None):
        """Step 2: Mostrato solo se l'automazione fallisce."""
        if user_input is not None:
            # L'utente ha confermato di aver letto, andiamo al finish
            return await self.async_step_finish()

        return self.async_show_form(
            step_id="manual_resource",
            description_placeholders={"url": self._resource_url}
        )

    async def _async_try_add_resource(self, url: str, res_type: str) -> bool:
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

            await resources.async_create_item({"res_type": res_type, "url": url})
            return True
        except Exception as e:
            _LOGGER.warning("Registrazione automatica risorsa fallita (%s): %s", url, e)
            return False

    async def _async_resource_exists(self, url: str) -> bool:
        """Verifica se una risorsa esiste già."""
        if not url: return False
        try:
            lovelace = self.hass.data.get("lovelace")
            if not lovelace: return False
            resources = getattr(lovelace, "resources", None)
            if not resources: return False
            if not resources.loaded:
                await resources.async_load()
            return any(res.get("url") == url for res in resources.async_items())
        except Exception:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Ritorna l'handler per le opzioni senza passare argomenti."""
        return MaterialHAOptionsFlowHandler()

class MaterialHAOptionsFlowHandler(config_entries.OptionsFlow):
    """Gestisce la modifica (CONFIGURA) dell'integrazione."""

    async def async_step_init(self, user_input=None):
        """Gestisce il primo (e unico) step delle opzioni."""
        errors = {}

        current_email = self.config_entry.data.get(CONF_EMAIL, "")
        current_token = self.config_entry.data.get(CONF_TOKEN, "")

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = MaterialHAApiClient(session)
            storage = MaterialStorage(self.hass)
            stored_secret_key = await storage.async_load_secret_key()

            try:
                _LOGGER.debug("Calling validate_license in options flow...")
                response = await client.validate_license(
                    email=user_input[CONF_EMAIL],
                    token=user_input[CONF_TOKEN],
                    secret_key=stored_secret_key
                )
                _LOGGER.debug("API response in options flow: %s", response)
                
                updated_data = {
                    **self.config_entry.data,
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_STATUS: response.get("status"),
                    CONF_PLAN: response.get("plan"),
                    CONF_HASH_KEY: response.get("hash_key"),
                    CONF_RESOURCE_URL: response.get("resource_url")
                }
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=updated_data
                )
                
                return self.async_create_entry(title="", data={})

            except InvalidLicenseError:
                errors["base"] = "invalid_auth"
            except ApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error("Errore modifica opzioni: %s", e, exc_info=True)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=current_email): str,
                vol.Required(CONF_TOKEN, default=current_token): str,
            }),
            errors=errors
        )