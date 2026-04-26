from temporalio.client import Client


async def build_temporal_client(address: str, namespace: str = "default") -> Client:
    return await Client.connect(address, namespace=namespace)
