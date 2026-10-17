# Estúdio 3D

No menu, abra **Estúdio 3D**. Tudo acontece dentro do jogo: criar o personagem, vestir, experimentar danças e comemorações, comprar com moedas, salvar combinações e equipar. Não há editor externo, upload de arquivo, Blender ou geração individual por IA.

## O que o jogador faz

1. **Visuais** — aplica um personagem original (Nova, Camisa 10, Riso da Meia-Noite) como ponto de partida e gerencia **Meus visuais** (até 12 combinações salvas).
2. **Corpo** — estrutura masculina ↔ feminina, altura, musculatura, massa, ombros, tronco, quadril, pernas e cabeça.
3. **Rosto** — formato (oval, redondo, quadrado, triangular), mandíbula, queixo, maçãs, olhos (tamanho, distância, inclinação, cor), sobrancelhas, nariz, lábios, boca e orelhas.
4. **Pele e cabelo** — 11 tons de pele + cor livre, estilos de cabelo, cor e pontas descoloridas, sobrancelhas e barba.
5. **Roupas, Calçados, Acessórios** — peças gratuitas e premium, várias recoloríveis, com prévia 3D imediata.
6. **Danças** — 4 danças e 5 comemorações, com prévia, pausa e velocidade.

O palco tem giro 360° (arraste ou botão), zoom (roda, pinça ou botões), vistas de corpo, rosto, tronco, pernas, pés e costas, câmera que acompanha a cabeça durante a dança e três cenários de luz.

O rodapé mostra o que falta comprar. **Comprar e equipar** abre a confirmação com o total; quando várias peças pertencem a um personagem original, o carrinho oferece o personagem completo se sair mais barato. **Salvar e equipar** grava o visual quando tudo já é do jogador. O avatar equipado dança no lobby (**Comemorar** toca a comemoração), aparece como retrato na partida e comemora em 3D na tela de vitória.

## Arquitetura

- **Base compartilhada** (`public/avatar/base.glb`): malha anatômica CC0 do MakeHuman com 67 morphs nomeados (corpo, rosto e expressões faciais), olhos, cílios, dentes e esqueleto padrão Mixamo (52 ossos + olhos). Proporções que movem juntas guardam o deslocamento de cada junta; o runtime reposiciona o esqueleto e recalcula o bind, sem rig manual.
- **Peças modulares** (`public/avatar/items/*.glb`): cada roupa, calçado, cabelo ou acessório traz os mesmos nomes de ossos e de morphs. Ao vestir, a peça é religada ao esqueleto do avatar e acompanha qualquer corpo e rosto criados. Peças declaram as regiões do corpo que cobrem (`hides`), evitando que a pele atravesse o tecido.
- **Animações** (`src/avatar/animation.ts`, `src/avatar/dances.ts`): coreografias originais descritas por poses-chave anatômicas, com IK das pernas (pés plantados), dedos e expressões faciais; compiladas uma vez em `AnimationClip`s por nome de osso. A mesma dança produz o mesmo movimento em todos os avatares.
- **Runtime** (`src/avatar/Avatar.ts`, `AvatarView.tsx`, `stage.ts`): materiais PBR do three.js, pele com espalhamento subsuperficial aproximado, tecido com sheen, cabelo com pontas descoloridas, sombras suaves, piscar e olhar.
- **Interface**: `src/screens/AvatarStudio.tsx` e `avatarStudio.css` (desktop e celular).
- **Catálogo e posse**: `src/avatar/catalog.ts` e `src/avatar/ownership.ts`.

Pipeline de geração, licenças e como adicionar peças: [scripts/avatar/README.md](../scripts/avatar/README.md).

## Compras e persistência

- Moedas do jogo. Offline, perfil e compras ficam no navegador. Online, compras passam pela RPC `purchase_item` com preços do banco.
- Perfis antigos são preservados: IDs `street`, `striker`, `night-clown` e as danças continuam valendo. Quem já tinha o Camisa 10 ou o Riso da Meia-Noite recebe automaticamente todas as peças daquele visual. Um perfil sem avatar criado abre com o visual do personagem equipado.
- O avatar criado fica em `profiles.avatar.creator`. Peças avulsas em `profiles.owned_items`, comemorações em `owned_dances`, visuais salvos em `profiles.outfits`.
- Aplique `supabase/migrations/20261017200000_avatar_creator.sql` depois das migrações anteriores. Ela adiciona as colunas, os preços, a relação peça ↔ personagem e estende o gatilho que impede equipar o que não foi comprado (inclusive requisições forjadas). A migração foi verificada em Postgres embarcado (PGlite); **não foi aplicada automaticamente ao banco de produção**. Sem ela, o jogo funciona, mas no modo online os visuais salvos ficam só no aparelho e o servidor recusa equipar peças novas.

## Limites conhecidos

- Os modelos são gerados proceduralmente sobre a base CC0 do MakeHuman. A qualidade é de personagem de jogo estilizado-realista, mas **não alcança o nível da arte conceitual de `art-direction/camisa10/reference-front.png`** (rosto esculpido, tecidos com simulação e detalhe de pintura à mão). Chegar lá exige um artista 3D (ou geração por imagem-para-3D com revisão) produzindo cabeça, cabelo e roupas sobre esta mesma base — o sistema de peças, rig e animações já está pronto para recebê-los.
- Tecidos acompanham o corpo por skinning (sem simulação física); em poses extremas os ombros podem esticar.
- Em partidas online, os adversários continuam aparecendo com o boneco 2D: o avatar 3D ainda não é transmitido aos outros jogadores.
- Pagamentos em reais, compra de moedas, itens criados por jogadores e importação de modelos não estão implementados.

## Manutenção

`npm test` cobre: esqueleto e morphs da base, compatibilidade de todas as peças com o esqueleto, montagem do Camisa 10, proporções com pés no chão, as 9 animações em corpos diferentes, conversão de sliders, sanitização, posse, carrinho e compras. `node scripts/avatar/preview/e2e.mjs` (com `npm run dev` rodando) executa o fluxo completo no navegador em desktop e celular.
