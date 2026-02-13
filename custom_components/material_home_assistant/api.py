"""Client API per Material Home Assistant."""
import aiohttp
import logging
from typing import Optional, Dict, Any

from .const import API_BASE_URL, API_ENDPOINT_HANDSHAKE

_LOGGER = logging.getLogger(__name__)

class MaterialHAApiClient:
    """Classe per interagire con il backend API."""

    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    async def validate_license(
        self, 
        email: str, 
        token: str, 
        secret_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Esegue l'handshake per validare la licenza."""
        
        url = f"{API_BASE_URL}{API_ENDPOINT_HANDSHAKE}"
        
        # Costruzione del payload come da specifica
        payload = {
            "email": email,
            "token": token
        }
        
        # Se abbiamo già una secret_key (verifica ricorrente o reinstallazione), la aggiungiamo
        if secret_key:
            payload["secret_key"] = secret_key

        try:
            _LOGGER.debug(f"Chiamata API a {url} con payload parziale: email={email}")
            
            async with self._session.post(url, json=payload) as response:
                
                # Leggiamo il JSON di risposta
                data = await response.json()
                
                # Gestione specifica degli errori HTTP in base alla tua logica
                if response.status == 403 or response.status == 401:
                    # Licenza non valida o scaduta
                    _LOGGER.error(f"Errore Licenza {response.status}: {data.get('message', 'Sconosciuto')}")
                    raise InvalidLicenseError(data.get("message", "Licenza non valida"))
                
                if response.status >= 400:
                    # Altri errori (400 Bad Request, 500 Server Error)
                    _LOGGER.error(f"Errore API {response.status}: {data.get('message')}")
                    raise ApiConnectionError(f"Errore Backend: {response.status}")

                # Se tutto ok (200), restituiamo i dati (status, plan, resource_url, evt secret_key)
                return data

        except aiohttp.ClientError as err:
            # Errore di connessione puro (server giù, dns, etc)
            raise ApiConnectionError(f"Errore di connessione: {err}")

class InvalidLicenseError(Exception):
    """Eccezione per licenza non valida (401/403)."""
    pass

class ApiConnectionError(Exception):
    """Eccezione per problemi di connessione (400, 500, Network)."""
    pass