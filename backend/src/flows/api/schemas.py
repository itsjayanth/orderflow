from pydantic import BaseModel


class FlowDataExchangeRequest(BaseModel):
    """The three base64 fields WhatsApp POSTs for every Flow data-exchange
    request (data_api_version 3.0) -- see flows/domain/encryption.py for
    what's actually inside encrypted_flow_data."""

    encrypted_flow_data: str
    encrypted_aes_key: str
    initial_vector: str
