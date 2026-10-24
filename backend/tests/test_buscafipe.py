import httpx
import pytest

from app.integrations.buscafipe import BuscaFipeClient, BuscaFipeError


def make_client(handler):
    return BuscaFipeClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_fipe_passes_action_and_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/fipe.php"
        assert request.url.params["action"] == "valor"
        assert request.url.params["marca"] == "21"
        return httpx.Response(200, json={"valor": "R$ 50.000,00"})

    result = await make_client(handler).fipe("valor", marca="21")
    assert result["valor"] == "R$ 50.000,00"


@pytest.mark.asyncio
async def test_plate_is_normalized_and_posted_as_form():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/placa.php"
        assert request.content.decode() == "placa=ABC1D23"
        return httpx.Response(200, json={"marca": "FIAT"})

    result = await make_client(handler).plate("abc-1d23")
    assert result["marca"] == "FIAT"


@pytest.mark.asyncio
async def test_rejects_invalid_plate_before_network():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Request must not be sent")

    with pytest.raises(ValueError):
        await make_client(handler).plate("NOTAPLATE")


@pytest.mark.asyncio
async def test_cnpj_sends_digits_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content.decode() == "cnpj=00000000000100"
        return httpx.Response(200, json={"situacao": "ATIVA"})

    result = await make_client(handler).cnpj("00.000.000/0001-00")
    assert result["situacao"] == "ATIVA"


@pytest.mark.asyncio
async def test_rate_limit_is_reported_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "limit"})

    with pytest.raises(BuscaFipeError, match="Limite"):
        await make_client(handler).ipva("SP")
