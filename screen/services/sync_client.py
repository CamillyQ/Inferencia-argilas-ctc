import os
import requests
from services import banco_local as db

WORKER_URL = os.environ["SYNC_WORKER_URL"]
API_KEY = os.environ["SYNC_API_KEY"]

TIMEOUT_SEGUNDOS = 10
TAMANHO_LOTE = 20


def _preparar_payload(ensaio):
    """Remove campos que só fazem sentido localmente (id autoincrement
    do SQLite do Pi, flag de sincronizado) antes de mandar pro Worker."""
    campos_locais = {"id", "sincronizado"}
    return {k: v for k, v in ensaio.items() if k not in campos_locais}


def sincronizar():
    pendentes = db.listar_ensaios_pendentes_sync()
    if not pendentes:
        print("[SYNC] Nada pendente.")
        return

    print(f"[SYNC] {len(pendentes)} ensaio(s) pendente(s).")

    for i in range(0, len(pendentes), TAMANHO_LOTE):
        lote = pendentes[i:i + TAMANHO_LOTE]
        payload = [_preparar_payload(e) for e in lote]

        try:
            resposta = requests.post(
                WORKER_URL,
                json=payload,
                headers={"X-API-Key": API_KEY},
                timeout=TIMEOUT_SEGUNDOS,
            )
            resposta.raise_for_status()
        except requests.RequestException as erro:
            # sem internet no laboratório -- comportamento esperado e
            # não deve derrubar nada; só tenta de novo na próxima
            # execução do systemd timer
            print(f"[SYNC] Falha de conexão, tentando depois: {erro}")
            return

        dados = resposta.json()
        for uuid_sync in dados.get("aceitos", []):
            db.marcar_como_sincronizado(uuid_sync)

        for falha in dados.get("erros", []):
            print(f"[SYNC] Rejeitado pelo servidor: {falha}")

    print("[SYNC] Concluído.")


if __name__ == "__main__":
    sincronizar()