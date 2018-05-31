# Dumbstone

**NB** I have tested this only on Windows 10 with Sabaki as a client. If you run into problems in different setup, let me know.

## Description

Dumbstone is a Python wrapper around excellent [Leela Zero](https://github.com/gcp/leela-zero) go-playing program. It "dumbs down" Leela by trying to choose the move which gives it the closest probablity to win to some pre-defined number.

This means that it is "adjusting" own strength with respect to the strength of the opponent and the current statate of the game. For example, if desired win probability is 50%, Dumbstone will choose the best move if it is behind, and worse move if it is winning.

Please notice that in any case Dumbstone chooses one of the moves considered by Leela Zero, which means that they are still tend to be very good. Even if desired win probability is set to low number, it is entirely possible to get yourself into the position where even the worst move considered by Leela Zero has high win probability.

## How to run

### Requirements

Dumbstone requires:

- Working Leela Zero installation (including weights file)
- Python 3 (get yours at https://www.python.org)
- GTP-capable client ([Sabaki](https://sabaki.yichuanshen.de/) works very well)

### Installation

Download `dumbstone.py` and `dumbstone.ini` files and put them in the same directory somewhere.

Edit `dumbstone.ini`:

1. In `[leelaz]` section set `leelaz` to the full path to Leela Zero binary.
2. In `[leelaz]` section set `weights` to the full path to Leela Zero weights.
3. In `[stupidity]` section set `win_percent` to the winning probability (in percents) Dumbstone will try to maintain.
4. In `[stupidity]` section set `max_drop_percent` to some value. Dumbstone will not consider moves which cause bigger drop in winning probability than this value, comparing with the move chosen by Leela Zero. If you want to disable this feature, just set it to some huge number. Having this value set helps against Dumbstone making really horrible moves in yose just to prevent itself from winning.
5. In `[stupidity]` section set `pass_terminates` either to 1 or to 0. If it is set to 1, and Leela Zero considered pass as a move, Dumbstone will not play moves worse than pass.
6. In `[stupidity]` section set `min_visits` to some number to prevent Dumbstone from considering moves with small number of visits. *Warning*: this should be much, much smaller than `visits` setting in `[leelaz]` section.

If you want, you can change `visits` in `[leelaz]` section. Unlike with Leela Zero, this number will not change the playing strength; instead, higher number of visits will produce more variations for Dumbstone to choose from, so it (maybe) will be able to maintain winning probability better. In my experience, 1000 works quite well. Set to lower number if Dumbstone is too slow.

### Usage

**If you know what you are doing**: `python dumbstone.py` should behave as a standard GTP client.

To set up in Sabaki, add engine in `Engines->Manage Engines...`, then configure as ollowing:
* Name: `Dumbstone`
* Path: full path to your Python 3 binary, including `python.exe` in the end;
* Arguments: full path to `dumbstone.py` file, including `dumbstone.py` in the end;
* Initial commands: none.


## Meta

Version: 0.3

Author: Alexey Vyskubov <alexey@hotmail.fi>

License: BSD 2-clause
