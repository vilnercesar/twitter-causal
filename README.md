# 🐦 Twitter Distribuído - Consistência Eventual

Este projeto é uma implementação acadêmica de um sistema distribuído simplificado (semelhante ao Twitter) para demonstrar o conceito de **Consistência Eventual**.

O sistema é composto por múltiplas réplicas (processos) que se comunicam via HTTP. O objetivo principal é simular atrasos de rede (*Chaos Engineering*) para provocar inconsistências temporárias — especificamente **"Respostas Órfãs"** (quando uma resposta chega antes do post original) — e observar como o sistema converge para um estado consistente automaticamente após o fim do atraso.

**Tecnologias:** Python, FastAPI, Uvicorn, Requests.

---

## 🔌 Principais Endpoints

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `POST` | `/post` | Cria um novo post ou resposta na réplica local. Incrementa o relógio lógico (Lamport), salva localmente e difunde (*broadcast*) para as outras réplicas. |
| `POST` | `/share` | Endpoint passivo usado para receber mensagens de outras réplicas ("fofoca"). Apenas armazena e atualiza o relógio lógico, sem alterar o timestamp original do evento. |

---

## 🛠️ Pré-requisitos

* Python 3.8+ instalado.
* Virtualenv (recomendado).
* Bibliotecas listadas em `requirements.txt`:
    * `fastapi`
    * `uvicorn`
    * `requests`
    * `pydantic`

---

## 🚀 Instalação e Execução

### 1. Clonar e Instalar

```bash
# 1. Clone o repositório
git clone [https://github.com/seu-usuario/seu-repo.git](https://github.com/seu-usuario/seu-repo.git)
cd seu-repo

# 2. Crie e ative um ambiente virtual (Opcional, mas recomendado)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
# .venv\\Scripts\\activate     # Windows

# 3. Instale as dependências
pip install -r requirements.txt
```

### 2. Como Rodar (Topologia de 3 Nós)

Você precisará de **3 terminais abertos**, um para cada processo:

* **Terminal 1 (Processo 0):**
  ```bash
  python twitter_eventual.py 0
  ```
  *(Roda na porta 8080)*

* **Terminal 2 (Processo 1):**
  ```bash
  python twitter_eventual.py 1
  ```
  *(Roda na porta 8081)*

* **Terminal 3 (Processo 2):**
  ```bash
  python twitter_eventual.py 2
  ```
  *(Roda na porta 8082)*

---

## 🧪 Roteiro de Teste (Cenário de Divergência)

Este roteiro demonstra o **"Efeito Viagem no Tempo"**, onde uma resposta chega antes da pergunta devido a um atraso simulado de rede.

**Cenário:**
1. **Alice (P0)** posta algo. O sistema simula um atraso de 10s no envio para o **Carlos (P2)**.
2. **Bob (P1)** recebe o post imediatamente e responde.
3. **Carlos (P2)** recebe a resposta do Bob *antes* do post da Alice.

### Passo 1: O Post Original (Alice - P0)
Execute em um terminal separado:

```bash
curl -X POST http://localhost:8080/post \\
  -H "Content-Type: application/json" \\
  -d '{"evtId": "post_alice", "author": "Alice", "text": "Alguém gosta de Pizza?", "processId": 0}'
```

### Passo 2: A Resposta Rápida (Bob - P1)
Execute **imediatamente** após o passo 1 (dentro da janela de 10 segundos):

```bash
curl -X POST http://localhost:8081/post \\
  -H "Content-Type: application/json" \\
  -d '{"evtId": "reply_bob", "parentEvtId": "post_alice", "author": "Bob", "text": "Eu amo pizza!", "processId": 1}'
```

### 📊 Resultados Esperados

Observe o **Terminal do Processo 2 (Carlos)**.

**1. Imediatamente (Inconsistência Temporária):**
Você verá um alerta de que a resposta chegou sem o pai.

```text
[!] ALERTA: RESPOSTAS ÓRFÃS (Pai 'post_alice' desconhecido):
└── ? [reply_bob] @Bob (T:2): Eu amo pizza!
```

**2. Após 10 Segundos (Convergência):**
O post original finalmente chega. O sistema se autocorrige e exibe a árvore correta.

```text
POST [post_alice] | @Alice (T:1): Alguém gosta de Pizza?
└── REPLY [reply_bob] @Bob (T:2): Eu amo pizza!
```
