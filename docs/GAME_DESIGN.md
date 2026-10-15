# Quem Sou Eu? — Documento de design

Jogo web (celular e PC) de cartas por turnos com clima Among Us, menu estilo Fortnite e modo história em plataforma 2D.

## 1. Partida de cartas

| Item | Regra |
|---|---|
| Jogadores | 4 a 10 por sala (humanos online + bots completando as vagas) |
| Deck | Conjunto de personagens (mínimo 12, máximo 60). O deck limita o máximo de jogadores: `cartas ÷ 3` |
| Mão | Cada jogador recebe **3 cartas escondidas**. Cada carta é **uma vida** |
| Mesa | Mostra todos os personagens do deck. As cartas que sobram depois da distribuição ficam como "iscas" |
| Turno | Na sua vez, escolha um personagem da mesa (não pode ser o seu) |
| Acerto | Se algum adversário tiver esse personagem, **a carta dele é descartada** (ele perde uma vida) |
| Erro | Ninguém tinha: **só passa a vez**. O personagem fica marcado como "NINGUÉM" para todos |
| Tempo | 20 segundos por turno; se acabar, passa a vez |
| Eliminação | Ficou sem cartas, está fora |
| Chat | Fica aberto em todas as rodadas, **só para conversar e blefar** (sem votação) |

### Fim de partida

Vence quem:
1. sobrar sozinho com cartas; **ou**
2. tiver **pelo menos tantas cartas quanto todos os outros juntos** e **mais do que cada adversário**.

Exemplos: eu 3 × outros 0 → venço · eu 2 × outros 1 + 1 → venço · eu 2 × outros 2 + 1 → continua.

### Recompensa
10 moedas por partida + 5 por acerto + 50 por vitória.

## 2. Menu (estilo Fortnite)

- **Tela inicial:** "Toque para começar" (libera o áudio no celular).
- **Jogar:** seu personagem num pedestal, nome editável, modo (contra bots / criar sala / entrar com código), escolha do deck e botão amarelo **JOGAR**.
- **Armário:** equipar cor, chapéu e visor.
- **Loja:** destaques do dia (mudam à meia-noite, iguais para todos), decks premium e todos os itens, com cores de raridade (comum, raro, épico, lendário).
- **Decks:** decks oficiais, decks do jogador (criar/editar/apagar/publicar) e decks da comunidade (copiar).
- **História:** seleção de fases.
- **Configurações:** volume de música e efeitos, status do online e dos arquivos.

## 3. Personagens, skins e decks

- **Avatar** (seu tripulante) e **cartas** são coisas separadas.
- Skins compradas com **moedas do jogo** (ganhas em partidas e na história).
- Decks oficiais: 2 grátis (*Tripulação Espacial*, *Profissões*) e 2 premium (*Lendas do Brasil*, *Monstros Fofos*).
- Jogadores criam decks próprios e podem publicá-los para a comunidade.

## 4. Modo história (plataforma 2D)

- 3 fases: A Nave, Sala de Máquinas e Ponte de Comando.
- Andar, pular (segurar = pulo mais alto), pisar nos impostores, blocos "?" dão moedas, espinhos e buracos tiram vida.
- 3 vidas por tentativa. Cada fase tem 3 cartas escondidas (20 moedas cada) e bônus por terminar.
- Concluir uma fase libera a próxima.
- Controles: setas/A-D + espaço no PC; botões na tela no celular.

## 5. Arquitetura

```
src/
  game/        regras puras (engine.ts), bots, tipos e testes
  online/      HostMatch (roda a partida), GuestMatch, Room (Supabase Realtime)
  story/       motor de plataforma + fases (ASCII) + teste de "dá para terminar"
  screens/     telas React (menu, abas, partida, sala, história)
  components/  Crewmate (SVG) e CardView
  lib/         perfil (localStorage), Supabase, economia
  audio/       música do R2 com fallback chiptune
  config/      URLs dos arquivos no R2
supabase/migrations/  tabelas, RLS e funções de compra/recompensa
```

- **Online:** presença da sala e mensagens via Supabase Realtime. O **anfitrião** roda as regras e os bots e transmite o estado público. Cada mão vai numa mensagem própria, endereçada ao jogador.
- **Economia:** compras (`purchase_item`) e recompensas (`award_coins`) são funções no banco. O preço vem da tabela `shop_items` e o cliente não consegue editar as moedas direto.
- **Offline:** sem `.env`, tudo funciona contra bots com salvamento local.

## 6. Limitações conhecidas e próximos passos

- [ ] **Mãos visíveis na rede:** hoje as mãos trafegam no canal da sala, então um jogador com conhecimento técnico consegue ver as cartas dos outros. Para competição séria, mover a autoridade da partida para uma Edge Function/servidor e mandar cada mão por canal privado.
- [ ] Se o anfitrião sair, a sala fecha (falta migrar o anfitrião para outro jogador).
- [ ] As recompensas de moedas têm limite e intervalo mínimo, mas ainda partem do cliente.
- [ ] **Venda de decks com dinheiro real:** hoje os decks premium custam moedas. Para vender com dinheiro (Pix/cartão), integrar Stripe ou Mercado Pago via Edge Function, liberando o deck no webhook de pagamento.
- [ ] Moderação dos decks públicos da comunidade.
- [ ] Mais fases, chefe final com batalha de cartas, conquistas.
