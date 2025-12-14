#!/bin/bash

echo "--- 1. Enviando Post da Alice (P0) [Vai demorar 10s para chegar no P2] ---"
curl -s -X POST http://localhost:8080/post \
     -H "Content-Type: application/json" \
     -d '{"evtId": "P1", "author": "Alice", "text": "Post Original", "processId": 0}' > /dev/null

echo "--- 2. Aguardando 2 segundos (para garantir que P1 recebeu) ---"
sleep 2

echo "--- 3. Enviando Resposta do Bob (P1) [Vai chegar no P2 antes do Post] ---"
curl -s -X POST http://localhost:8081/post \
     -H "Content-Type: application/json" \
     -d '{"evtId": "R1", "parentEvtId": "P1", "author": "Bob", "text": "Resposta Rapida", "processId": 1}' > /dev/null

echo "--- TESTE ENVIADO! ---"
echo "Olhe o terminal do Processo 2 AGORA. Você deve ver o 'ALERTA DE ÓRFÃO'."
echo "Espere ~8 segundos e veja a mágica da consistência eventual acontecer."