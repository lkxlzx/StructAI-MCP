import pytest

from midas_nx.client import MidasClient, Product


@pytest.fixture
def gen_client() -> MidasClient:
    return MidasClient(mapi_key="test-key", base_url="https://x.test:443/gen", product=Product.GEN)


@pytest.fixture
def civil_client() -> MidasClient:
    return MidasClient(mapi_key="test-key", base_url="https://x.test:443/civil", product=Product.CIVIL)
