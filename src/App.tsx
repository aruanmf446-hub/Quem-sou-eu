import { useEffect, useState } from 'react';
import { audio } from './audio/music';
import { MainMenu, type MenuTab } from './screens/MainMenu';
import { MatchScreen } from './screens/MatchScreen';
import { RoomScreen } from './screens/RoomScreen';
import { StoryScreen } from './screens/StoryScreen';
import { Splash } from './screens/Splash';
import { HostMatch, type MatchController } from './online/match';
import type { Room } from './online/room';
import { makeBots } from './game/bots';
import type { Deck } from './game/types';
import { getProfile, useProfile } from './lib/profile';
import { initOnline } from './lib/supabase';

type Screen =
  | { name: 'splash' }
  | { name: 'menu'; tab: MenuTab }
  | { name: 'match'; controller: MatchController; room?: Room }
  | { name: 'room'; room: Room }
  | { name: 'story'; level: number };

export function App() {
  const profile = useProfile();
  const [screen, setScreen] = useState<Screen>({ name: 'splash' });

  useEffect(() => {
    audio.setMusicVolume(profile.settings.music);
    audio.setSfxVolume(profile.settings.sfx);
  }, [profile.settings.music, profile.settings.sfx]);

  useEffect(() => {
    void initOnline();
  }, []);

  useEffect(() => {
    if (screen.name === 'menu' || screen.name === 'room') audio.play('menu');
    if (screen.name === 'match') audio.play('match');
    if (screen.name === 'story') audio.play('story');
  }, [screen.name]);

  const toMenu = (tab: MenuTab = 'jogar') => setScreen({ name: 'menu', tab });

  const startOffline = (deck: Deck, totalPlayers: number) => {
    const p = getProfile();
    const me = { id: p.id, name: p.name, isBot: false, skin: p.skin };
    const bots = makeBots(totalPlayers - 1, [p.name]);
    const controller = new HostMatch(deck, [me, ...bots], p.id);
    setScreen({ name: 'match', controller });
  };

  switch (screen.name) {
    case 'splash':
      return <Splash onStart={() => toMenu()} />;
    case 'menu':
      return (
        <MainMenu
          tab={screen.tab}
          onTab={(tab) => setScreen({ name: 'menu', tab })}
          onQuickMatch={startOffline}
          onRoom={(room) => setScreen({ name: 'room', room })}
          onStory={(level) => setScreen({ name: 'story', level })}
        />
      );
    case 'room':
      return (
        <RoomScreen
          room={screen.room}
          onMatch={(controller) => setScreen({ name: 'match', controller, room: screen.room })}
          onExit={() => {
            screen.room.close();
            toMenu();
          }}
        />
      );
    case 'match':
      return (
        <MatchScreen
          controller={screen.controller}
          online={!!screen.room}
          onExit={() => {
            screen.controller.leave();
            screen.room?.close();
            toMenu();
          }}
        />
      );
    case 'story':
      return <StoryScreen key={screen.level} level={screen.level} onExit={() => toMenu('historia')} onNext={(level) => setScreen({ name: 'story', level })} />;
  }
}
