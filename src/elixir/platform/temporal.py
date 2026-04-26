from temporalio.client import Client, TLSConfig


async def build_temporal_client(
    address: str,
    namespace: str = "default",
    tls: bool = False,
) -> Client:
    tls_config = TLSConfig() if tls else None
    return await Client.connect(address, namespace=namespace, tls=tls_config)
