# Sound: what is missing, and what is chosen and not yet played

Written on 4 October 2026, after three rounds of listening (575 of 623 candidates rated).
The table of what was chosen is `Scripts/Sound/sound_candidates/selection.py`; the audition
page's **Selected** tab (`python3 Scripts/Sound/build_sound_audition.py --open`) plays it.
This file is the other half: what that table does not have, or has and the game does not
play.

## 1. No usable sound

Nothing rated ok or better exists for these. Each needs a new source.

| sound | what was tried | where to look next |
|---|---|---|
| The menu opening, closing, scrolling, a toggle | Kenney's interface sounds, Sonniss's dark and mechanical sets: all rated bad or very bad. Electronic sounds do not suit the game | Soft, physical sounds: paper, leather, wood. Two page turns were rated ok (below), nothing better |
| A tension bed for ordinary play, and for a wendigo's hunt | 11 Sonniss drones and 15 Freesound ones: all bad, but three kept for ghosts and a boss, and one rated ok | Quiet, mostly wind and low tone. The Sonniss 2020 and 2021-23 bundles have horror ambience libraries not yet looked at (they are only on Sonniss's own server: download by hand) |
| Eating forage (a mushroom) | Only an apple and crackers were liked, each for an item the game does not have | A soft, wet bite: Freesound has three eating previews not yet rated |
| The forest's night one-shots: an owl, a branch snapping, a tree creaking | One owl was rated bad. Four more owls, six owl screeches, five branch snaps and one tree creak are cut and **not yet rated** | Rate those first. The four tree creaks that were liked are for a creaky house, not the forest |
| A wanderer's footsteps as its own sound | None sought | The wanderers share the player's footsteps today |

## 2. Thin: one or two takes

A sound played often needs three takes or more, or it is heard to repeat.

| sound | takes | note |
|---|---|---|
| The wendigo's growl | 1 (`troll2_growl_01`, ok) | It growls every 4-9 s once it has seen the player: today that is one of its roars |
| The wendigo hurt | 2 (`troll2_hurt_01`, ok; Freesound 784771, a preview) | |
| The wendigo dying | 1 (`troll2_death_01`, ok) | |
| The zombie hurt | 2 (`creature_pain_01`, ok; Freesound 506514, a preview) | |
| The zombie dying | 2 (`pain_death_01`, ok; Freesound 754441, great, a preview) | |
| The player dying | 1 (`pain_shout_01`) | Played once a life, so one is enough |
| Drinking | 1 (Freesound 674543, ok, a preview, 9 s) | The Sonniss sip was "just a sip, need glug glug" |
| Landing from a jump | 1 great of 3 | |
| A bullet into a body, and into the ground | 1 each, ok | Fifteen more impact takes are cut and not yet rated |
| Menu click, select, back, rollover, confirm | 1 each, ok | Enough for a menu, none of them liked much |

## 3. Chosen, but only as a Freesound preview

A preview is a 128 kbps MP3. It was good enough to judge by and is not good enough to
ship: download the original from its page (a free account) into
`assets/cache/sounds/freesound/`, and point the row of `manifest_archive.py` at it.

| for | Freesound | page |
|---|---|---|
| The zombie dying (great) | 754441, OwNathan, "Zombie Groan 3" | <https://freesound.org/people/OwNathan/sounds/754441/> |
| The axe on a tree (great) | 536736, egomassive, "Chop" | <https://freesound.org/people/egomassive/sounds/536736/> |
| The zombie hurt | 506514, LilMati, "Monster AAH!" | <https://freesound.org/people/LilMati/sounds/506514/> |
| The wendigo hurt | 784771, pdfpxf520, "Hit02" | <https://freesound.org/people/pdfpxf520/sounds/784771/> |
| Drinking | 674543, laboratoriosonoridades2022 | <https://freesound.org/people/laboratoriosonoridades2022/sounds/674543/> |
| A match | 398448, brachern, "Match Ignite" | <https://freesound.org/people/brachern/sounds/398448/> |
| A menu click | 477640, Joao_Janz | <https://freesound.org/people/Joao_Janz/sounds/477640/> |
| The menu opening and closing | 437121, mosaichorse; 667180, MBPL | <https://freesound.org/people/mosaichorse/sounds/437121/>, <https://freesound.org/people/MBPL/sounds/667180/> |
| A bed under a hunt | 560618, szegvari, "Dark Ghost House" | <https://freesound.org/people/szegvari/sounds/560618/> |

None of the sounds the game plays today is a preview.

## 4. Chosen, and not played yet

These rows of the selection are `ready, not wired`: the takes are picked, and no graph
plays them. What each needs:

| sound | where it would be played | what is in the way |
|---|---|---|
| The zombie's bite and swing, hurt and death; the wendigo's growl, hurt and death | The wanderers' controller (`npc/`), and the health component, whose voice is the player's only (`combat/voice.py` gates on `DespawnOnDeath`) | Per-creature takes have to reach the pawn's health component at possession, as its flinch clips do |
| A blade into a body; a thrown blade sticking | `weapon_component/punch.py`'s blow, on a Melee item; `throw_strike.py` | Nothing: a play node each |
| A bullet into wood, a body, the ground | `BP_BulletImpact` and `BP_BloodSplash` (`combat/bullet_impact.py`, `blood.py`) | The impact does not know its surface: wood and ground are one burst |
| An item picked up and set down; a garment worn; a weapon brought to hand | `weapon_component/pickup.py`, `wear.py`, `slot_sync.py` | Nothing |
| The player's effort on a swing and a throw; out of breath; a grunt on landing | `punch.py`, `throw_windup.py`, `sprint.py` | Nothing |
| Low health: a heartbeat | The health component, or the HUD | The take is 56 s and speeds up: it has to be trimmed to a steady loop and turned down (the note on it says so) |
| Drinking; eating | `weapon_component/consume.py` | Drinking is a preview; eating has no take |
| Running, grass and bare-ground footsteps, landing, grass rustle | `combat/footsteps.py` | The component has one sound for every speed and surface, and does not know what is underfoot |
| The menu's sounds | The HUD (`graphics_menu/`) | The HUD polls keys in `DrawHUD`; every row change, take and back needs a play node, and they would be the game's first 2D sounds played from a graph |
| The title screen's boom; a scare when a wendigo sees you | The HUD's first Tick; `npc/roar.py` | Nothing |
| A bed under a hunt | `world/ambience.py`, a fourth bed, raised while a wendigo hunts | Something has to tell the cycle that one is hunting |
| Each gun from far off | Nowhere yet | Only the player fires, 1.5 m from the listener. For the day something else shoots |

## 5. To listen to in the game

Built and verified, and nobody has heard them yet:

- **The three reloads** are put together from separate takes (shells and the action; a
  magazine out, a magazine in, a bolt), laid out by each take's length. Which take is the
  magazine going in and which is it coming out was a guess.
- **The beds' levels** against everything else: day birds 0.7, night 0.7, wind 0.5 (the
  SOUND SETTINGS tab), and whether dusk's cross-fade reads.
- **The footsteps at 0.4**: that number was set for the synthesised steps.
- **The gunshots' tails**: the shotgun's is 2.2 s where it was 1.3 s.
- **The player's grunt**, on every blow a wanderer lands.
- **The zombie's growl**: eleven takes from three libraries, which may not sound like one
  creature.

## 6. Kept for later

Good sounds for things the game does not have. They are in the selection (`future`), with
the notes written while listening: a growling, dog-like monster; ghosts and a ghost boss;
a tribe; finishing moves and a mace; bandages, skinning a rabbit, building; walking on
blood; an apple, crackers, a sip; a creaky house.
