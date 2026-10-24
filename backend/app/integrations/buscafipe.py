from __future__ import annotations

import re
from typing import Any

import httpx


BASE_URL = "https://buscafipe.com/api"
_PLATE_RE = re.compile(r"^(?:[A-Z]{3}\d{4}|[A-Z]{3}\d[A-Z]\d{2})$")
_CNPJ_RE = re.compile(r"^\d{14}$")
_VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
    "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
    "RR", "SC", "SP", "SE", "TO",
}


class BuscaFipeError(RuntimeError):
    """Falha segura na integração BuscaFIPE."""


class BuscaFipeClient:
    """Cliente server-side para os endpoints documentados do BuscaFIPE.

    A documentação informada apresenta FIPE/IPVA sem autenticação no plano gratuito.
    Não presumimos formato de chave para endpoints de parceiro enquanto o fornecedor
    não documentar explicitamente o mecanismo de autenticação.
    """

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        timeout_seconds: float = 8.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not 0.5 <= timeout_seconds <= 60:
            raise ValueError("timeout_seconds deve estar entre 0,5 e 60 segundos")
        # Evita que configuração externa transforme este cliente em proxy arbitrário.
        if base_url.rstrip("/") != BASE_URL:
            raise ValueError("A URL base do BuscaFIPE não pode ser alterada")
        self._base_url = BASE_URL
        self._timeout = timeout_seconds
        self._transport = transport

    async def _request(
        self, method: str, endpoint: str, *, params: dict[str, str] | None = None,
        data: dict[str, str] | None = None
    ) -> Any:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}/{endpoint}",
                    params=params,
                    data=data,
                    headers={"Accept": "application/json"},
                )
        except httpx.TimeoutException as exc:
            raise BuscaFipeError("BuscaFIPE excedeu o tempo limite") from exc
        except httpx.RequestError as exc:
            raise BuscaFipeError("BuscaFIPE está temporariamente indisponível") from exc

        if response.status_code == 429:
            raise BuscaFipeError("Limite de consultas da BuscaFIPE atingido")
        if response.status_code in (401, 403):
            raise BuscaFipeError("A BuscaFIPE exige credenciais ou autorização para este endpoint")
        if response.status_code >= 500:
            raise BuscaFipeError("BuscaFIPE retornou erro temporário")
        if response.status_code >= 400:
            raise BuscaFipeError(f"BuscaFIPE rejeitou a solicitação (HTTP {response.status_code})")
        try:
            return response.json()
        except ValueError as exc:
            raise BuscaFipeError("BuscaFIPE retornou uma resposta inválida") from exc

    async def fipe(self, action: str, **params: str) -> Any:
        if action not in {"marcas", "modelos", "anos", "valor"}:
            raise ValueError("action deve ser marcas, modelos, anos ou valor")
        allowed_params = {"tipo", "marca", "modelo", "ano", "codigo"}
        if set(params) - allowed_params:
            raise ValueError("Parâmetros FIPE não reconhecidos")
        query = {"action": action, **{k: v for k, v in params.items() if v != ""}}
        return await self._request("GET", "fipe.php", params=query)

    async def plate(self, plate: str) -> Any:
        normalized = re.sub(r"[\s-]", "", plate.upper())
        if not _PLATE_RE.fullmatch(normalized):
            raise ValueError("Placa inválida. Informe padrão ABC1234 ou Mercosul ABC1D23")
        return await self._request("POST", "placa.php", data={"placa": normalized})

    async def cnpj(self, cnpj: str) -> Any:
        digits = re.sub(r"\D", "", cnpj)
        if not _CNPJ_RE.fullmatch(digits):
            raise ValueError("CNPJ deve conter 14 dígitos")
        return await self._request("POST", "cnpj.php", data={"cnpj": digits})

    async def ipva(self, uf: str) -> Any:
        normalized = uf.strip().upper()
        if normalized not in _VALID_UFS:
            raise ValueError("UF brasileira inválida")
        return await self._request("GET", "ipva.php", params={"uf": normalized})
