# Arquivos no Cloudflare R2

O jogo carrega imagens e músicas de `VITE_ASSETS_BASE_URL` (a URL pública do bucket).
Se um arquivo não existir, ele usa o placeholder (emoji, desenho em código ou chiptune), então você pode subir aos poucos.

## Configurar o bucket

1. Cloudflare → R2 → crie o bucket (ex.: `quem-sou-eu-assets`).
2. Em **Settings → Public access**, ligue um domínio próprio (recomendado) ou o `r2.dev`.
3. Em **CORS policy**, libere o domínio do jogo:
   ```json
   [{ "AllowedOrigins": ["https://seu-jogo.com", "http://localhost:5173"], "AllowedMethods": ["GET"], "AllowedHeaders": ["*"] }]
   ```
4. No `.env`: `VITE_ASSETS_BASE_URL=https://assets.seu-jogo.com`

## Estrutura de pastas

```
music/
  menu.mp3       música do menu (loop)
  match.mp3      música da partida (loop)
  story.mp3      música do modo história (loop)
  victory.mp3    vitória (toca uma vez)
sfx/
  click.mp3  hit.mp3  miss.mp3  coin.mp3  jump.mp3
decks/
  espaco/cover.png
  espaco/astronauta.png
  espaco/alien.png
  ...
  profissoes/...
  folclore/...
  monstros/...
```

### Nome das imagens das cartas
O nome do personagem em minúsculas, sem acento, com espaços trocados por `-`:

| Personagem | Arquivo |
|---|---|
| Astronauta | `decks/espaco/astronauta.png` |
| Cachorro Astronauta | `decks/espaco/cachorro-astronauta.png` |
| Boto Cor-de-Rosa | `decks/folclore/boto-cor-de-rosa.png` |
| Mula sem Cabeça | `decks/folclore/mula-sem-cabeca.png` |

A lista completa está em `src/data/decks.ts`.
Recomendado: PNG ou WebP quadrado de 256×256 a 512×512, com fundo transparente.

### Decks criados por jogadores
No editor, o campo "Imagem" aceita um caminho do R2 (`decks/meu-deck/heroi.png`) ou uma URL completa.
