from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from collections import defaultdict
import threading
import time
import sys
import uvicorn
import requests

app = FastAPI()


# ------------------------------------------------------------
# Estado global (instâncias e estruturas compartilhadas)
# ------------------------------------------------------------
myProcessId = 0          # id da réplica atual (definido via argv na inicialização)
timestamp = 0            # relógio lógico simples (Lamport-style) usado para ordenação
posts = defaultdict(list)
replies = defaultdict(list)


processes = [
    "localhost:8080",
    "localhost:8081",
    "localhost:8082",
]


# ------------------------------------------------------------
# Modelo de evento
# ------------------------------------------------------------
class Event(BaseModel):
    processId: int
    evtId: str
    parentEvtId: Optional[str] = None
    author: str
    text: str
    timestamp: Optional[int] = None




# ------------------------------------------------------------
# Endpoints HTTP
# ------------------------------------------------------------

@app.post("/post")
def post(msg: Event):
    """
    Endpoint usado para criar um novo post localmente.
    Deve:
      - Se o evento foi gerado localmente (msg.processId == myProcessId):
          * incrementar o relógio lógico (timestamp).
          * atribuir msg.timestamp = timestamp.
      - Processar/aplicar o evento localmente (chamar processMsg).
      - Reencaminhar o evento para as demais réplicas (async_send para cada processo != myProcessId).
      - Retornar confirmação ao cliente.
    """
    global timestamp
    
    timestamp += 1
    msg.timestamp = timestamp
    msg.processId = myProcessId
    
    processMsg(msg)
    payload = msg.dict()
    
    for i, node_address in enumerate(processes):
        if i != myProcessId:
            url = f"http://{node_address}/share"
            async_send(url, payload)
            
    return {"status": "posted", "timestamp": timestamp}



@app.post("/share")
def share(msg: Event):
    """
    Endpoint usado para receber eventos enviados por outras réplicas.
    Deve:
      - Processar/aplicar o evento recebido (chamar processMsg).
      - Retornar confirmação HTTP à réplica remetente.
      - Nota: este endpoint não deve alterar timestamps gerados pelo autor do evento.
    """

    print(f"\n[Recebido via Rede] De Processo {msg.processId}: {msg.evtId}")
    
    processMsg(msg)

    return {"status": "ack"}



# ------------------------------------------------------------
# Funções auxiliares de rede e aplicação
# ------------------------------------------------------------


def async_send(url: str, payload: dict):
    """
    Envia um payload JSON para outra réplica de forma assíncrona.
    Deve:
      - Criar uma thread/worker para enviar a requisição sem bloquear o servidor.
      - Implementar mecanismo básico de timeout e tratamento de exceções de rede.
- (Opcional) incluir delays simulados para testes (por exemplo, condicional para myProcessId == 0).
    """
    def send_task():
        try:

            if 'myProcessId' in globals() and myProcessId == 0 and "8082" in url:
                print(f"[Network] Simulando delay de 10s para {url}...")
                time.sleep(30)
            
            requests.post(url, json=payload, timeout=5)
            
        except requests.exceptions.Timeout:
            print(f"[Timeout] Falha ao enviar para {url}: Tempo limite excedido.")
        except requests.exceptions.ConnectionError:
            print(f"[Erro Conexão] Falha ao enviar para {url}: Destino inacessível.")
        except Exception as e:
            print(f"[Erro Genérico] Falha no envio para {url}: {e}")

    t = threading.Thread(target=send_task, daemon=True)
    t.start()


def processMsg(msg: Event):
    """
    Aplica um evento ao estado local (feed).
    Deve:
      - Se msg.parentEvtId for None: armazenar em posts[msg.evtId].
      - Caso contrário: anexar em replies[msg.parentEvtId].
      - Atualizar qualquer índice/estrutura auxiliar necessária.
      - Exibir/registro do feed (chamar showFeed).
      - Observação: em consistência eventual não há checagem de dependências; aceita-se a chegada em qualquer ordem.
    """

    global timestamp
    

    if msg.timestamp and msg.timestamp > timestamp:
        timestamp = msg.timestamp

    if msg.parentEvtId is None:

        current_list = posts[msg.evtId]
        
        already_exists = False
        for p in current_list:
            if p.evtId == msg.evtId:
                already_exists = True
                break
        
        if not already_exists:
            posts[msg.evtId].append(msg)

    else:

        current_list = replies[msg.parentEvtId]
        
        # Verifica duplicidade
        already_exists = False
        for r in current_list:
            if r.evtId == msg.evtId:
                already_exists = True
                break
        
        if not already_exists:
            replies[msg.parentEvtId].append(msg)


    showFeed()


# ------------------------------------------------------------
# Apresentação / debug
# ------------------------------------------------------------


def showFeed():
    """
    Exibe no console o estado atual do feed local (útil para debugging).
    Deve imprimir:
      - Todos os posts conhecidos e seus timestamps.
      - As replies associadas a cada post (mesmo que tenham chegado antes/ depois).
      - Replies órfãs (replies cujo post pai ainda não foi recebido) para evidenciar divergência.
    """
    print("\n" + "="*60)
    print(f"--- FEED DO PROCESSO {myProcessId} (Relógio Lógico: {timestamp}) ---")

    has_content = False

    for evt_id, post_list in posts.items():
        for post in post_list:
            has_content = True
            # Imprime o Post Principal
            t_str = f"T:{post.timestamp}" if post.timestamp else "T:?"
            print(f"POST [{post.evtId}] | @{post.author} ({t_str}): {post.text}")

            # Verifica se existem respostas para este Post específico
            if evt_id in replies:
                sorted_replies = sorted(replies[evt_id], key=lambda x: x.timestamp or 0)
                
                for r in sorted_replies:
                    tr_str = f"T:{r.timestamp}" if r.timestamp else "T:?"
                    print(f"   └── REPLY [{r.evtId}] @{r.author} ({tr_str}): {r.text}")


    
    orphans_found = False
    for parent_id, reply_list in replies.items():
        if parent_id not in posts:
            orphans_found = True
            has_content = True
            print(f"\n[!] ALERTA: RESPOSTAS ÓRFÃS DETECTADAS (Pai '{parent_id}' desconhecido):")
            
            for r in reply_list:
                tr_str = f"T:{r.timestamp}" if r.timestamp else "T:?"
                print(f"   └── ? [{r.evtId}] @{r.author} ({tr_str}): {r.text}")

    if not has_content:
        print("(Feed Vazio)")
        
    print("="*60 + "\n")


### O que acontece nessa função?
"""
1.  **Iteração dos Posts (`posts.items()`):**
    * Mostramos tudo o que é "normal": posts que conhecemos.
    * Imediatamente abaixo de cada post, procuramos no dicionário `replies` se há respostas para aquele ID. Se houver, imprimimos com um recuo (`└──`) para indicar a hierarquia.

2.  **A Caça aos Órfãos (`replies.items()`):**
    * Aqui está a lógica da Consistência Eventual.
    * Perguntamos: *"Tenho uma lista de respostas para o ID 'X'. Eu conheço o post 'X'?"*
    * `if parent_id not in posts`: Se a resposta é **Não**, significa que a mensagem de resposta chegou mais rápido pela rede do que a mensagem original.
    * Imprimimos isso em uma seção separada com um alerta `[!]`, mostrando que o estado está temporariamente inconsistente.

### Visualizando no Console

Quando você rodar o cenário de atraso que discutimos antes, o console do **Processo 2** mostrará algo assim:

```text
============================================================
--- FEED DO PROCESSO 2 (Relógio Lógico: 5) ---

[!] ALERTA: RESPOSTAS ÓRFÃS DETECTADAS (Pai 'Post_1' desconhecido):
   └── ? [Reply_1] @Bob (T:4): Eu concordo!
============================================================
```

E depois de 10 segundos (quando o atraso passar), o próximo `showFeed` corrigirá para:

```text
============================================================
--- FEED DO PROCESSO 2 (Relógio Lógico: 6) ---
POST [Post_1] | @Alice (T:3): Gosto de Pizza
   └── REPLY [Reply_1] @Bob (T:4): Eu concordo!
============================================================

"""

# ------------------------------------------------------------
# Inicialização do nó
# ------------------------------------------------------------


if __name__ == "__main__":
    """
    Inicializa a réplica:
      - Ler myProcessId de sys.argv.
      - Configurar host/port com base em `processes`.
      - Subir o servidor FastAPI/uvicorn.
      - (Opcional) iniciar threads auxiliares de teste ou temporizadores se necessário.
    """

    if len(sys.argv) < 2:
        print(f"USO: python {sys.argv[0]} <ProcessId (0, 1 ou 2)>")
        sys.exit(1)

    try:
        myProcessId = int(sys.argv[1])
        
        if myProcessId < 0 or myProcessId >= len(processes):
            print(f"Erro: ProcessId deve ser entre 0 e {len(processes)-1}")
            sys.exit(1)
            
    except ValueError:
        print("Erro: ProcessId deve ser um número inteiro.")
        sys.exit(1)


    address = processes[myProcessId]
    host, port_str = address.split(":")
    port = int(port_str)

    print(f"--> Iniciando TWITTER (Consistência Eventual) - Nó {myProcessId}")
    print(f"--> Endereço: http://{host}:{port}")
    print(f"--> PID: {myProcessId}")
    
    uvicorn.run(app, host=host, port=port)


