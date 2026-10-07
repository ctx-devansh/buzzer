import { useGame } from './GameLayout';

export default function LobbyPage() {
  const { roomCode, playerCount, gameStatus } = useGame();

  const statusText = gameStatus === 'IN_PROGRESS'
    ? 'Waiting for next question…'
    : 'Waiting for host to start…';

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6 gap-6 text-center">
      <div className="space-y-2">
        <p className="nb-caption">Room</p>
        <p className="nb-hero text-ink">{roomCode}</p>
      </div>

      <div className="mt-4 space-y-2">
        <div className="flex justify-center">
          <div className="w-12 h-12 border-4 border-shadow border-t-accent rounded-full animate-spin" />
        </div>
        <p className="nb-h3 text-ink">{statusText}</p>
        <p className="text-ink-muted text-sm">
          {playerCount} player{playerCount !== 1 ? 's' : ''} in room
        </p>
      </div>
    </div>
  );
}
