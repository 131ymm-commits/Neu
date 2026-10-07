import time, sys, pyspiel
from open_spiel.python import policy as P
from open_spiel.python.algorithms import exploitability
def up(rounds, ranks, suits, raise_sizes, max_raises, hole=1, board="0 1"):
    return ("universal_poker(betting=limit,numPlayers=2,numRounds=%d,blind=1 1,firstPlayer=1 1,numSuits=%d,numRanks=%d,numHoleCards=%d,numBoardCards=%s,raiseSize=%s,maxRaises=%s,stack=100 100)"
            % (rounds, suits, ranks, hole, board, raise_sizes, max_raises))
for name in [up(2, 3, 2, "2 4", "2 2"), up(2, 4, 2, "2 4", "2 2"), up(2, 5, 2, "1 3", "3 2"), up(2, 4, 3, "2 4", "2 2"), "liars_dice(numdice=2,dice_sides=3)", "liars_dice(numdice=2,dice_sides=4)"]:
    try:
        g = pyspiel.load_game(name); t = time.time(); nu = exploitability.nash_conv(g, P.UniformRandomPolicy(g)); tu = time.time() - t
        print(f'{name[:110]:110s} infosets {len(P.TabularPolicy(g).state_lookup):7d} uni {nu:.3f} t_truth {tu:.1f}s', flush=True)
    except Exception as e: print(name, 'ERR', str(e)[:200], flush=True)
