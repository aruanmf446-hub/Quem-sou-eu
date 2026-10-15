# Quem Sou Eu?

Jogo de cartas por turnos para a web: cada carta é uma vida. Chute os personagens dos adversários, blefe no chat e seja quem fica com mais cartas no final.
Tem menu estilo Fortnite, skins, decks criados pelos jogadores e um modo história em plataforma 2D.

As regras completas estão em [docs/GAME_DESIGN.md](docs/GAME_DESIGN.md).

## Rodar

```bash
npm install
npm run dev        # http://localhost:5173
npm test           # regras do jogo e fases
npm run build      # gera dist/ para publicar
```

Sem configurar nada, o jogo roda **offline contra bots**, com progresso salvo no navegador.

## Online (Supabase)

1. Crie um projeto em supabase.com.
2. Rode `supabase/migrations/0001_init.sql` (SQL Editor ou `supabase db push`).
3. Em **Authentication → Providers**, ative **Anonymous sign-ins**.
4. Copie `.env.example` para `.env` e preencha `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY`.

Isso libera salas online com código, perfil e moedas salvos, compras validadas no servidor e decks da comunidade.

## Arte e música (Cloudflare R2)

Defina `VITE_ASSETS_BASE_URL` e suba os arquivos seguindo [docs/ASSETS.md](docs/ASSETS.md).

## Publicar

É um site estático (`dist/`): funciona no Vercel, no Cloudflare Pages ou no Netlify. Configure as mesmas variáveis `VITE_*` no painel da hospedagem.
