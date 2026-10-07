import { QRCodeSVG } from 'qrcode.react';
import { Users } from 'lucide-react';
import { useGame } from './GameLayout';
import { Button } from '../../components/ui/button';

export default function LobbyPage() {
  const { roomCode, gameTitle, playerCount, emitAdvance, autoAdvance, setAutoAdvance } = useGame();

  const playerJoinUrl = `${window.location.origin}/player/join?code=${roomCode}`;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 gap-8">
      {/* Quiz name */}
      {gameTitle && (
        <h1 className="nb-h1 text-ink text-center">{gameTitle}</h1>
      )}

      {/* Join instructions */}
      <p className="nb-caption">
        Scan QR code or go to <span className="text-ink">{window.location.host}/player</span>
      </p>

      {/* QR code + room code side by side */}
      <div className="flex items-center gap-10">
        {/* Black on white in both themes, for scanning (§4.7). */}
        <div className="border-4 border-line bg-qr-bg p-4 shadow-brutal">
          <QRCodeSVG value={playerJoinUrl} size={200} />
        </div>

        <div className="text-center">
          <p className="nb-caption mb-2">Room Code</p>
          <div className="nb-box px-10 py-5 inline-block">
            <p className="nb-hero text-ink">{roomCode}</p>
          </div>
        </div>
      </div>

      {/* Player count */}
      <div className="nb-body flex items-center gap-3 text-ink">
        <Users className="w-8 h-8" aria-hidden="true" />
        <span>
          {playerCount === 0
            ? 'Waiting for players to join…'
            : `${playerCount} player${playerCount !== 1 ? 's' : ''} joined`}
        </span>
      </div>

      {/* Auto-advance toggle */}
      <button
        role="switch"
        aria-checked={autoAdvance}
        className="flex items-center gap-3"
        onClick={() => setAutoAdvance(!autoAdvance)}
      >
        <div className={`relative h-7 w-14 border-2 border-line transition-colors ${autoAdvance ? 'bg-accent' : 'bg-surface-muted'}`}>
          <div className={`absolute top-0.5 h-5 w-5 border-2 border-line transition-transform ${autoAdvance ? 'translate-x-7 bg-on-fill' : 'translate-x-0.5 bg-surface'}`} />
        </div>
        <span className="text-ink font-semibold select-none">
          Auto-advance — run game hands-free
        </span>
      </button>

      {/* Start button */}
      <Button size="lg" onClick={emitAdvance} disabled={playerCount === 0} className="px-12">
        {playerCount === 0 ? 'Waiting for players…' : 'Start Game'}
      </Button>
    </div>
  );
}
