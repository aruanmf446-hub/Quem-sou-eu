# Estúdio de personagens 3D

No menu, abra **Estúdio 3D**. Experimente uma skin e uma dança, escolha cor, proporção e iluminação, e clique em **Salvar e equipar**. Para itens bloqueados, **Desbloquear e equipar** informa o total em moedas antes da compra. O personagem equipado dança no menu **Jogar**.

## Modelos e apresentação

- Três personagens originais: Nova, Camisa 10 e Riso da Meia-Noite.
- Modelos GLB feitos no Blender sobre a malha anatômica CC0 do MakeHuman, com mãos e rosto contínuos, olhos, sobrancelhas, cabelo, roupas e acessórios.
- Esqueleto comum de 17 ossos e pesos de deformação. Os modelos usam `SkinnedMesh`, com compressão Meshopt e decodificador empacotado no aplicativo.
- Cada GLB pesa aproximadamente 375–441 KB. As prévias WebP dos próprios modelos pesam cerca de 27–29 KB.
- Danças procedurais: groove, samba, robô e baile de terror, com contramovimento do tronco, membros articulados, apoio dos pés e transição suave entre emotes.
- Câmera de corpo inteiro, rosto e costas, zoom, órbita, giro automático e visualização de esqueleto.
- Iluminação de estúdio com materiais físicos, reflexos de ambiente e sombras. Três ambientes: Estúdio, Arena e Meia-noite.
- Pausa, controle de velocidade e respeito à preferência por movimento reduzido.

## Compras e persistência

As skins e danças usam moedas do jogo. Offline, o progresso fica no navegador. Online, compras passam pela RPC e preços oficiais do banco; um trigger impede equipar itens não adquiridos.

Aplique `supabase/migrations/20261017130458_character_studio.sql` depois da migração inicial para ativar o catálogo online. A atualização visual não exige outra migração e preserva os IDs e itens já adquiridos. A migração foi verificada em Postgres embarcado (PGlite); não foi aplicada automaticamente a um banco de produção.

Pagamentos em reais, compra de moedas, repasses para criadores, publicação de itens por terceiros, importação/exportação pelo usuário e autorig de modelos enviados não estão implementados.

## Manutenção

- Catálogo e IDs: `src/data/characters.ts`.
- Renderer e carregamento: `src/components/CharacterStage.tsx`.
- Coreografias: `src/three/choreography.ts`.
- Interface: `src/screens/CharacterStudio.tsx`.
- Fonte/licenças e regeneração dos assets: `scripts/assets/README.md`.

`npm run assets:build` reconstrói os personagens (Blender 4.3+ e Pillow necessários). `npm run build` usa os assets já versionados. Os testes carregam os GLBs comprimidos com o mesmo decodificador do app e verificam pesos, rig, movimento real dos membros, poses válidas e ausência de acúmulo de transformações.
