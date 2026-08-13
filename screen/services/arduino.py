import serial
import time
import re
from serial.tools import list_ports

VIDS_CONHECIDOS = {
    0x1A86: "CH340 / CH341 (QinHeng Electronics -- clones Arduino Nano)",
    0x2341: "Arduino LLC (placas oficiais)",
    0x2A03: "Arduino SA (placas oficiais, versão antiga)",
    0x0403: "FTDI FT232 (alguns clones e placas antigas)",
    0x10C4: "Silicon Labs CP210x (outro chip comum em clones)",
}


def detectar_arduino(verbose=True):
    """
    Procura a porta serial do Arduino.

    Estratégia (nessa ordem):
      1. VID conhecido (mais confiável -- é o ID do chip, fixo no
         hardware, funciona igual em qualquer sistema operacional).
      2. Texto da descrição/fabricante (fallback -- útil quando o VID
         não está na lista acima, mas é frágil porque o texto muda
         de formato entre Windows e Linux para o MESMO dispositivo).
    """
    portas = list(list_ports.comports())

    if verbose:
        print(f"[ARDUINO] {len(portas)} porta(s) serial encontrada(s):")
        for p in portas:
            vid_hex = f"0x{p.vid:04X}" if p.vid is not None else "None"
            pid_hex = f"0x{p.pid:04X}" if p.pid is not None else "None"
            print(
                f"  {p.device} | desc={p.description!r} | "
                f"manuf={p.manufacturer!r} | vid={vid_hex} | pid={pid_hex}"
            )

    # 1) Tenta por VID conhecido primeiro (mais confiável)
    for porta in portas:
        if porta.vid in VIDS_CONHECIDOS:
            if verbose:
                print(
                    f"[ARDUINO] Encontrado por VID: {porta.device} "
                    f"({VIDS_CONHECIDOS[porta.vid]})"
                )
            return porta.device

    # 2) Fallback: texto (mantém compatibilidade com o comportamento
    #    original no Windows, e cobre chips fora da lista de VIDs)
    for porta in portas:
        descricao = (porta.description or "").lower()
        fabricante = (porta.manufacturer or "").lower()

        if any(termo in descricao for termo in ("arduino", "ch340", "ch341", "usb serial", "usb-serial")):
            if verbose:
                print(f"[ARDUINO] Encontrado por descrição: {porta.device}")
            return porta.device

        if "arduino" in fabricante:
            if verbose:
                print(f"[ARDUINO] Encontrado por fabricante: {porta.device}")
            return porta.device

    if verbose:
        print("[ARDUINO] Nenhuma porta correspondente encontrada.")
    return None


if __name__ == "__main__":
    print("Porta detectada:", detectar_arduino())


class ArduinoService:

    def __init__(self, porta=None, baudrate=9600):
        self.conexao = None
        self.conectado = False
        self.ppm = None
        self.condutividade = None
        self.tem_ppm = False
        self.tem_condutividade = False
        self.regex = re.compile(r"([0-9.]+)\s*(ppm|uS/cm)")

        if porta is None:
            porta = detectar_arduino()

        if porta is None:
            print("[AVISO] Nenhum Arduino encontrado. A aplicação iniciará offline.")
            return

        try:
            self.conexao = serial.Serial(
                port=porta,
                baudrate=baudrate,
                timeout=0.1
            )
            time.sleep(2)
            self.conectado = True
            print(f"Arduino conectado em {porta}")
        except Exception as e:
            print(f"[ERRO] Falha ao abrir porta serial {porta}: {e}")
            self.conexao = None
            self.conectado = False

        def enviar(self, comando):
            if not self.conectado or not self.conexao:
                print("[SERIAL] Comando ignorado: Arduino desconectado.")
                return

            comando = comando.strip() + "\n"
            self.conexao.write(comando.encode("utf-8"))

        def ler(self):
            if not self.conectado or not self.conexao:
                return None

            while self.conexao.in_waiting:
                linha = (
                    self.conexao
                    .readline()
                    .decode("utf-8", errors="ignore")
                    .strip()
                )

                if linha == "":
                    continue

                match = self.regex.search(linha)

                if match is None:
                    continue

                valor = float(match.group(1))
                unidade = match.group(2)

                if unidade == "ppm":
                    self.ppm = valor
                    self.tem_ppm = True

                elif unidade == "uS/cm":
                    self.condutividade = valor
                    self.tem_condutividade = True

                if self.tem_ppm and self.tem_condutividade:
                    leitura = (self.ppm, self.condutividade)
                    self.tem_ppm = False
                    self.tem_condutividade = False
                    return leitura

        return None

    def limpar_buffer(self):

        self.conexao.reset_input_buffer()


    def fechar(self):

        if self.conexao.is_open:
            self.conexao.close()
            
    def enviar_comando_calibracao(self, comando):
        """
        comando: 'ENTER', 'CAL:707', 'EXIT'
        """
        if not self.conexao or not self.conexao.is_open:
            return False
        
        try:
            self.conexao.reset_input_buffer()

            self.conexao.write(f"{comando.upper()}\n".encode('utf-8'))
            
            # Pausa necessária para o Arduino processar e atualizar a EEPROM
            time.sleep(0.5) 
            
            print(f"[SERIAL] Comando enviado: {comando.upper()}")
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao enviar: {e}")
            return False