"""CRLV digital — Detran-MT.

Preencha só os três campos obrigatórios e execute.
Proxy/cookies vêm do ambiente (nunca no código).
"""
from __future__ import annotations

import base64
import json
import os

from crlve_mt import consultar_crlv_mt, salvar_documento

# ===================== OBRIGATÓRIOS =====================
placa = "ABC1D23"
renavam = "00000000000"
documento = "00000000000"  # CPF ou CNPJ do proprietário
# ========================================================

# Opcional (ambiente)
proxy = os.getenv("DETRAN_PROXY", "")
cookies = os.getenv("MT_COOKIES", "")

arquivo_pdf = "crlv_mt.pdf"
arquivo_json = "resultado_mt.json"


def main() -> int:
    print(f"Consultando CRLV-MT — placa {placa.strip().upper()} …")
    try:
        retorno = consultar_crlv_mt(
            placa=placa,
            renavam=renavam,
            documento_proprietario=documento,
            cookies=cookies or None,
            proxy=proxy or None,
        )
    except Exception as exc:
        print(f"Erro: {type(exc).__name__}: {exc}")
        return 1

    pdf_bytes = retorno.get("bytes")
    disponivel = (
        retorno.get("kind") in {"pdf", "pdf_base64"}
        and isinstance(pdf_bytes, (bytes, bytearray))
        and bytes(pdf_bytes).startswith(b"%PDF")
    )

    caminho = None
    if disponivel:
        caminho = salvar_documento(retorno, arquivo_pdf)
        print(f"PDF salvo: {caminho} ({retorno.get('size', 0)} bytes)")
    else:
        print("CRLV não disponível.")
        print(f"  kind={retorno.get('kind')!r}")
        for m in retorno.get("mensagens") or []:
            print(f"  - [{m.get('tipo')}] {m.get('texto')}")

    resposta = {
        "uf": "MT",
        "placa": placa.strip().upper(),
        "renavam": renavam.strip(),
        "crlve": {
            "disponivel": disponivel,
            "arquivo": caminho,
            "tamanho_bytes": retorno.get("size") if disponivel else None,
            "base64": (
                base64.b64encode(bytes(pdf_bytes)).decode("ascii")
                if disponivel
                else None
            ),
        },
    }
    if retorno.get("mensagens"):
        resposta["crlve"]["mensagens"] = retorno["mensagens"]
    if retorno.get("dados") is not None:
        resposta["crlve"]["dados"] = retorno["dados"]

    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(resposta, f, ensure_ascii=False, indent=2)
    print(f"JSON salvo: {arquivo_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
