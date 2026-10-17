# Estúdio de personagens 3D

No menu, abra **Estúdio 3D**. Escolha uma skin e uma dança para experimentar, personalize cor e altura e clique em **Equipar personagem e dança**. O avatar equipado aparece dançando no menu **Jogar**. As cartas e o avatar 2D das partidas continuam disponíveis.

## O que está implementado

- Três personagens originais estilizados: Original, Camisa 10 e Riso da Meia-Noite.
- Rig comum com 12 ossos (`THREE.Bone`) e malhas rígidas anexadas às articulações. Não são modelos realistas gerados por IA nem arquivos de personagens licenciados.
- Quatro animações procedurais compartilhadas: groove, samba, robô e baile de terror.
- Órbita, zoom, pausa, velocidade, visualização do rig, cor da roupa e altura.
- Compra de skins e danças usando moedas do jogo; inventário e aparência no perfil.
- Offline: armazenamento local. Online: RPC existente de compras, catálogo de preços no banco e validação de posse ao equipar.

## Banco online

Aplique `supabase/migrations/20261017130458_character_studio.sql` depois da migração inicial, pelo fluxo habitual de migrations ou SQL Editor. A migração adiciona inventários e aparência, amplia os tipos do catálogo, substitui a compra por um wrapper invoker que chama uma função privada, e rejeita avatares com itens não adquiridos. Preços e moedas são determinados no servidor. Não há necessidade de mudar as variáveis de ambiente existentes.

O frontend funciona offline sem banco. Sem a nova migração, as compras 3D online não funcionam. A migração foi verificada em Postgres embarcado (PGlite), mas não foi aplicada a um banco de produção.

## Adicionar conteúdo

O catálogo fica em `src/data/characters.ts`; mantenha os preços e IDs sincronizados com uma nova migração de `shop_items`. A montagem do rig e as animações ficam em `src/components/CharacterStage.tsx`.

Esta versão é um criador de personagens a partir de presets, com formas geométricas. Importação/exportação GLB, autorig de modelos enviados e criação de novas coreografias não estão implementadas. Para modelos detalhados, uma próxima etapa é produzir modelos GLB em Blender e importar animações compatíveis com o rig.

As vendas atuais usam moedas ganhas no jogo. Pagamento em reais, compra de moedas, repasses para criadores e publicação de itens por terceiros precisam de uma integração de pagamentos e validação de transações no servidor.

Para comercializar o nome/imagem de Neymar ou uma reprodução de Pennywise, providencie os direitos correspondentes. Os presets incluídos são personagens originais genéricos de futebol e terror.
