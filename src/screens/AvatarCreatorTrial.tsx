import './avatarCreatorTrial.css';

interface Props {
  onClose: () => void;
}

const TOOLS = [
  {
    name: 'Character Studio',
    subtitle: 'Código aberto · MIT',
    url: 'https://studio.m3org.com/',
    source: 'https://github.com/M3-org/CharacterStudio',
    description: 'Editor original de avatares 3D com corpo, cabelo, roupas, cores e acessórios. É a opção mais adequada para estudar a incorporação no próprio jogo.',
    note: 'Teste os controles e a qualidade dos modelos. Os itens e bibliotecas de assets precisam ter licenças comerciais conferidas separadamente.',
    recommended: true,
  },
  {
    name: 'three.ws Avatar Studio',
    subtitle: 'Serviço externo · confira termos comerciais',
    url: 'https://three.ws/create/studio',
    source: 'https://github.com/nirholas/three.ws',
    description: 'Editor alternativo com personalização visual. A página do serviço impede que o nosso jogo a incorpore diretamente por iframe.',
    note: 'Experimente em outra aba. Não está conectado às moedas ou ao perfil do Quem Sou Eu?.',
    recommended: false,
  },
] as const;

/**
 * Avaliação de editores reais. Evita o iframe remoto bloqueado por CSP
 * e não simula exportação, compras, rigging ou persistência que não existem.
 */
export function AvatarCreatorTrial({ onClose }: Props) {
  return <main className="avatar-trial">
    <header className="avatar-trial-header">
      <div>
        <span className="avatar-trial-eyebrow">LAB / TESTE DE CRIADORES PRONTOS</span>
        <h1>Escolha o gerador de personagens</h1>
        <p>Vamos avaliar editores existentes antes de integrar um no jogo. Nada de Blender ou gerar modelos manualmente.</p>
      </div>
      <button className="avatar-trial-close" type="button" onClick={onClose}>← Voltar ao estúdio</button>
    </header>
    <div className="avatar-trial-explain" role="status">
      <strong>Corrigimos o painel em branco</strong>
      <p>O three.ws bloqueia a abertura do editor dentro de outros sites. Agora o teste abre o editor verdadeiro em uma nova aba — sem exigir que você procure ou importe um arquivo GLB. Ainda é um teste de qualidade, não a integração final.</p>
    </div>
    <div className="avatar-trial-options">
      {TOOLS.map((tool, index) => <section className={tool.recommended ? 'avatar-trial-option recommended' : 'avatar-trial-option'} key={tool.name}>
        <div className="avatar-trial-option-top">
          <span className="avatar-trial-num">0{index + 1}</span>
          {tool.recommended && <span className="avatar-trial-tag">PRIMEIRO TESTE</span>}
        </div>
        <div>
          <small>{tool.subtitle}</small>
          <h2>{tool.name}</h2>
          <p>{tool.description}</p>
        </div>
        <div className="avatar-trial-option-bottom">
          <a href={tool.url} className="avatar-trial-open" target="_blank" rel="noopener noreferrer" aria-label={`Abrir ${tool.name} em nova aba`}>TESTAR GERADOR REAL ↗</a>
          <a href={tool.source} target="_blank" rel="noopener noreferrer" className="avatar-trial-source">Ver código-fonte ↗</a>
          <small>{tool.note}</small>
        </div>
      </section>)}
    </div>
    <div className="avatar-trial-next"><strong>O que acontece depois do teste?</strong><p>Se a qualidade do Character Studio servir para o seu jogo, o caminho correto será hospedar o editor open source dentro do Quem Sou Eu?, conectar o avatar ao perfil e às skins comerciais e reutilizar animações. Não vamos anunciar esses recursos como prontos antes de funcionarem.</p></div>
    <footer className="avatar-trial-footer">Seu estúdio original, personagens, moedas e compras continuam como estavam. Nenhuma compra, upload ou alteração de dados acontece nesta tela.</footer>
  </main>;
}
