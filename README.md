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

## Estúdio 3D

Abra **Estúdio 3D** para criar seu personagem (corpo, rosto, pele, cabelo), vestir roupas, calçados e acessórios, escolher danças e comemorações, comprar com moedas e salvar combinações. O avatar equipado dança no lobby, aparece na partida e comemora na vitória. Para o modo online, aplique também `supabase/migrations/20261017200000_avatar_creator.sql`. Detalhes, arquitetura e limites em [docs/CHARACTER_STUDIO.md](docs/CHARACTER_STUDIO.md); pipeline de assets e licenças em [scripts/avatar/README.md](scripts/avatar/README.md).

## Testar sem consumir Vercel (GitHub Pages)

O projeto publica uma versão de teste estática pelo workflow `pages-preview.yml`, usando
GitHub Actions e os mesmos modelos GLB do repositório. O Vercel continua independente.

- Site: https://aruanmf446-hub.github.io/Quem-sou-eu/
- Abrir diretamente o Estúdio 3D: https://aruanmf446-hub.github.io/Quem-sou-eu/?studio=1

Na primeira publicação, se Pages ainda não estiver habilitado, entre em
**Settings → Pages → Build and deployment → Source: GitHub Actions** e salve.
Depois confira em **Actions → Publicar teste no GitHub Pages**.

O build de teste não recebe credenciais de Supabase: jogo offline e Estúdio 3D podem
ser avaliados, mas salas online e dados reais exigem configuração própria.
