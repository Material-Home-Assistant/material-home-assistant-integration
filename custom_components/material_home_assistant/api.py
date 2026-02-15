"""Client API per Material Home Assistant."""
import logging
import aiohttp
from typing import Optional, Dict, Any

from .const import API_BASE_URL, API_ENDPOINT_HANDSHAKE

_LOGGER = logging.getLogger(__name__)

class MaterialHAApiClient:
    """Classe per interagire con il backend API."""

    def __init__(self, session: aiohttp.ClientSession):
        """Inizializza il client API con una sessione aiohttp."""
        self._session = session

    async def validate_license(
        self, 
        email: str, 
        token: str, 
        secret_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Esegue l'handshake per validare la licenza.

        Args:
            email: L'indirizzo email dell'utente.
            token: Il token di licenza fornito.
            secret_key: La chiave segreta opzionale (se già presente).

        Returns:
            Un dizionario contenente i dati della risposta (status, plan, resource_url, ecc.).

        Raises:
            InvalidLicenseError: Se la licenza non è valida o è scaduta (401/403).
            ApiConnectionError: Se c'è un errore di connessione o un errore server (400/500).
        """
        
        url = f"{API_BASE_URL}{API_ENDPOINT_HANDSHAKE}"
        
        # Costruzione del payload come da specifica
        payload = {
            "email": email,
            "token": token
        }
        
        # Se abbiamo già una secret_key (verifica ricorrente o reinstallazione), la aggiungiamo al payload
        if secret_key:
            payload["secret_key"] = secret_key

        try:
            _LOGGER.debug("Invio richiesta di validazione licenza a %s per email: %s", url, email)
            
            async with self._session.post(url, json=payload) as response:
                # Leggiamo il JSON di risposta
                try:
                    data = await response.json()
                except aiohttp.ContentTypeError:
                    _LOGGER.error("Risposta non valida dal server (non JSON). Status: %s", response.status)
                    raise ApiConnectionError(f"Risposta non valida dal server. Status: {response.status}")
                
                # Gestione specifica degli errori HTTP
                if response.status in (401, 403):
                    # Licenza non valida o scaduta
                    _LOGGER.warning("Licenza non valida o scaduta (Status %s): %s", response.status, data.get('message', 'Nessun messaggio'))
                    raise InvalidLicenseError(data.get("message", "Licenza non valida"))
                
                if response.status >= 400:
                    # Altri errori (400 Bad Request, 500 Server Error)
                    _LOGGER.error("Errore API (Status %s): %s", response.status, data.get('message', 'Nessun messaggio'))
                    raise ApiConnectionError(f"Errore Backend: {response.status}")

                # Se tutto ok (200), restituiamo i dati
                _LOGGER.debug("Validazione licenza completata con successo.")
                return data

        except aiohttp.ClientError as err:
            # Errore di connessione puro (server giù, dns, timeout)
            _LOGGER.error("Errore di connessione durante la validazione della licenza: %s", err)
            raise ApiConnectionError(f"Errore di connessione: {err}")

class InvalidLicenseError(Exception):
    """Eccezione per licenza non valida (401/403)."""
    pass

class ApiConnectionError(Exception):
    """Eccezione per problemi di connessione (400, 500, Network)."""
    pass