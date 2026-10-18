# Estúdio 3D

No menu, abra **Estúdio 3D**. Tudo acontece dentro do jogo: criar o personagem, vestir, experimentar danças e comemorações, comprar com moedas, salvar combinações e equipar. Não há editor externo, upload de arquivo, Blender ou geração individual por IA.

## O que o jogador faz

1. **Visuais** — aplica um personagem original (Nova, Camisa 10, Riso da Meia-Noite e as cinco coleções estilizadas abaixo) como ponto de partida e gerencia **Meus visuais** (até 12 combinações salvas).
2. **Corpo** — estilo (realista ↔ animação: cabeça e olhos maiores), estrutura masculina ↔ feminina, idade do corpo (adulto ↔ criança, cerca de 1,35–1,42 m antes do ajuste de altura), altura, musculatura, massa, barriga (chapada ↔ redonda), ombros, tronco, quadril, pernas e cabeça. Roupas, cabelos e acessórios acompanham todos esses corpos.
3. **Rosto** — formato (oval, redondo, quadrado, triangular), comprimento, bochechas, idade aparente, mandíbula, queixo, maçãs, olhos (formato, tamanho, distância, inclinação, cor), sobrancelhas, nariz (inclusive perfil), lábios, boca (inclusive cantos) e orelhas, além da **expressão de repouso** (sorriso, olhar semicerrado, sobrancelhas erguidas ou franzidas), que se soma às expressões das danças.
4. **Pele e cabelo** — 11 tons de pele + cor livre, estilos de cabelo, cor e pontas descoloridas, sobrancelhas e barba.
5. **Roupas, Calçados, Acessórios** — peças gratuitas e premium, várias recoloríveis, com prévia 3D imediata.
6. **Danças** — 4 danças e 5 comemorações, com prévia, pausa e velocidade.

O palco tem giro 360° (arraste ou botão), zoom (roda, pinça ou botões), vistas de corpo, rosto, tronco, pernas, pés e costas, câmera que acompanha a cabeça durante a dança e três cenários de luz.

O rodapé mostra o que falta comprar. **Comprar e equipar** abre a confirmação com o total; quando várias peças pertencem a um personagem original, o carrinho oferece o personagem completo se sair mais barato. **Salvar e equipar** grava o visual quando tudo já é do jogador. O avatar equipado dança no lobby (**Comemorar** toca a comemoração), aparece como retrato na partida e comemora em 3D na tela de vitória.

## Coleções estilizadas

Cinco personagens em estilo animação (cabeça e olhos maiores pelo morph `style_toon`, roupas em camadas, couro, latão e ouro, cores saturadas), inspirados em artes de referência. Cada peça é vendida avulsa ou no pacote do personagem (preços em `src/avatar/catalog.ts`). O código de cada coleção fica em `scripts/avatar/collection_*.py`.

| Pacote | Peças |
| --- | --- |
| **Mecânica dos Céus** (`sky-mechanic`) | rabo de cavalo rebelde, óculos de aviador de latão, jaqueta coral cropped sobre camisa creme, calça cargo azul-marinho, botas de cano alto com engrenagens, luvas sem dedos, cinturão duplo com bolsas, bússola e cristal, lenço ao vento (recolorível), chave inglesa |
| **Astrônoma** (`astronomer`) | cabelo longo ondulado, tiara de engrenagens com gema, túnica creme com tabardo e colete, capa curta com capuz e estrelas douradas, calça bufante estrelada, botas com frisos dourados, cinto com fivela-bússola, braçadeiras de couro com cordão, cajado com esfera armilar |
| **Arlequina** (`harlequin`) | maria-chiquinha em cachos espirais rosa com pontas turquesa, chapéu de guizos, blusa de losangos com gola franzida, short bufante, meias 7/8 desencontradas, botinhas de bico enrolado, luvas com babado, bomba sorridente, losango no rosto |
| **Guardião Anúbis** (`anubis`) | máscara de chacal com nemes azul e dourado (esconde rosto e cabelo), colar usekh, faixas cruzadas com medalhão, saiote de linho pregueado com avental listrado, manto azul-noite (recolorível), braceletes, grevas douradas com sandálias, cetro solar |
| **Cientista Voltaico** (`volt`) | cabelo azul espetado, jaleco longo com frisos dourados e dragona, calça de laboratório, botas de fivela, braço mecânico com tubos emissivos e dedos presos aos ossos, cinto do raio e os óculos de aviador da Mecânica |

Cada personagem tem rosto e corpo próprios: a Mecânica tem rosto redondo, bochechas cheias, nariz arrebitado e sorrisão; a Astrônoma, rosto oval comprido, olhos amendoados e caídos e lábios cheios; a Arlequina, rosto de coração, olhos redondos enormes inclinados e sorriso travesso; o Voltaico, rosto comprido e magro, queixo forte, nariz aquilino e sobrancelhas de cientista maluco. Cor de pele, olhos, altura, massa e tamanho da cabeça também variam.

Objetos de mão (chave inglesa, cajado, bomba, cetro) usam a pegada do runtime (`grip`: `fist`, `staff` ou `open`) e foram conferidos parados e nas danças. Os chapéus, a máscara e o cabelo longo foram posicionados sobre os penteados das próprias coleções.

## Arquitetura

- **Base compartilhada** (`public/avatar/base.glb`): malha anatômica CC0 do MakeHuman com 84 morphs nomeados (corpo, rosto, traços de personagem e expressões faciais), olhos, cílios, dentes e esqueleto padrão Mixamo (52 ossos + olhos). Proporções que movem juntas guardam o deslocamento de cada junta; o runtime reposiciona o esqueleto e recalcula o bind, sem rig manual.
- **Peças modulares** (`public/avatar/items/*.glb`): cada roupa, calçado, cabelo ou acessório traz os mesmos nomes de ossos e de morphs. Ao vestir, a peça é religada ao esqueleto do avatar e acompanha qualquer corpo e rosto criados. Peças declaram as regiões do corpo que cobrem (`hides`), evitando que a pele atravesse o tecido.
- **Animações** (`src/avatar/animation.ts`, `src/avatar/dances.ts`): coreografias originais descritas por poses-chave anatômicas, com IK das pernas (pés plantados), dedos e expressões faciais; compiladas em `AnimationClip`s por nome de osso. A mesma coreografia vale para todos os avatares e é resolvida nas proporções de cada um (pernas curtas ou longas, quadril largo ou estreito): joelhos sempre dobram para a frente e os pés ficam plantados. Corpos com as mesmas proporções compartilham o clip compilado.
- **Runtime** (`src/avatar/Avatar.ts`, `AvatarView.tsx`, `stage.ts`): materiais PBR do three.js, pele com espalhamento subsuperficial aproximado, tecido com sheen, cabelo com pontas descoloridas, sombras suaves, piscar e olhar. Ao trocar de visual, o avatar atual continua na tela com uma tela de carregamento (progresso por peça) até todas as peças novas chegarem; corpo, cores e roupas trocam juntos no mesmo quadro, e a câmera se reenquadra para cabelos altos e chapéus.
- **Interface**: `src/screens/AvatarStudio.tsx` e `avatarStudio.css` (desktop e celular).
- **Catálogo e posse**: `src/avatar/catalog.ts` e `src/avatar/ownership.ts`.

Pipeline de geração, licenças e como adicionar peças: [scripts/avatar/README.md](../scripts/avatar/README.md).

## Compras e persistência

- Moedas do jogo. Offline, perfil e compras ficam no navegador. Online, compras passam pela RPC `purchase_item` com preços do banco.
- Perfis antigos são preservados: IDs `street`, `striker`, `night-clown` e as danças continuam valendo. Quem já tinha o Camisa 10 ou o Riso da Meia-Noite recebe automaticamente todas as peças daquele visual. Um perfil sem avatar criado abre com o visual do personagem equipado.
- O avatar criado fica em `profiles.avatar.creator`. Peças avulsas em `profiles.owned_items`, comemorações em `owned_dances`, visuais salvos em `profiles.outfits`.
- Aplique `supabase/migrations/20261017200000_avatar_creator.sql` depois das migrações anteriores e, em seguida, `20261018090000_avatar_collections.sql` (preços e pacotes das coleções estilizadas; regere com `python3 scripts/avatar/catalog_sql.py` quando o catálogo mudar). A primeira adiciona as colunas, os preços, a relação peça ↔ personagem e estende o gatilho que impede equipar o que não foi comprado (inclusive requisições forjadas); ela foi verificada em Postgres embarcado (PGlite). **Nenhuma das duas foi aplicada ao banco de produção**. Sem ela, o jogo funciona, mas no modo online os visuais salvos ficam só no aparelho e o servidor recusa equipar peças novas.

## Limites conhecidos

- Os modelos são gerados proceduralmente sobre a base CC0 do MakeHuman. A qualidade é de personagem de jogo estilizado-realista, mas **não alcança o nível da arte conceitual de `art-direction/camisa10/reference-front.png`** (rosto esculpido, tecidos com simulação e detalhe de pintura à mão). Chegar lá exige um artista 3D (ou geração por imagem-para-3D com revisão) produzindo cabeça, cabelo e roupas sobre esta mesma base — o sistema de peças, rig e animações já está pronto para recebê-los.
- As danças são resolvidas uma vez no esqueleto-padrão; o deslocamento do quadril é escalado pelo comprimento da perna de cada avatar, para que baixinhos e crianças não dobrem o joelho além do previsto. Corpos muito diferentes do padrão ainda podem mostrar pequenas diferenças no contato dos pés.
- Tecidos acompanham o corpo por skinning (sem simulação física); em poses extremas os ombros podem esticar.
- **As coleções estilizadas aproximam as artes de referência, mas não as igualam.** O caminho é procedural (sem escultura nem pintura à mão), então ficam lacunas visíveis: o rosto é a base do MakeHuman com o morph de animação, não um rosto esculpido no estilo das artes; tecidos não têm simulação (capas, lenço, saiote e cabelo longo seguem a coluna e o quadril por pesos, sem balanço próprio, e podem atravessar braços ou pernas em movimentos amplos); dobras, costuras e brilhos vêm de texturas procedurais, não de acabamento pintado à mão. Mechas de cabelo são tubos achatados, sem a leveza de cabelo pintado.
- Pequenos defeitos conhecidos por peça: cajados atravessam o antebraço oposto em comemorações com as duas mãos juntas (ex.: coração); a ponta do lenço da Mecânica é rígida; as miniaturas de luvas e braçadeiras mostram as peças no corpo inteiro (pequenas no quadro); o cabelo longo da Astrônoma cai um pouco mais para um lado; a dobra na ponta do `shoes_clown`, a sombra translúcida na aba do `cap_snapback`, o artefato na gola de trás do `top_tee`, o interior da manga visível com o braço levantado, a borda manchada do `facepaint_midnight` e a colisão de chapéus com cabelos volumosos continuam.
- Em partidas online, os adversários continuam aparecendo com o boneco 2D: o avatar 3D ainda não é transmitido aos outros jogadores.
- Pagamentos em reais, compra de moedas, itens criados por jogadores e importação de modelos não estão implementados.

## Manutenção

`npm test` cobre: esqueleto e morphs da base, compatibilidade de todas as peças com o esqueleto, montagem do Camisa 10, proporções com pés no chão, as 9 animações em corpos diferentes, conversão de sliders, sanitização, posse, carrinho e compras. `node scripts/avatar/preview/e2e.mjs` (com `npm run dev` rodando) executa o fluxo completo no navegador em desktop e celular.
