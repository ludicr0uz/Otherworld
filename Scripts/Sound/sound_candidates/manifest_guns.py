"""The third table: gunshots, for the five guns.

The shots the game plays are the first, synthesised ones, and the Free
Firearm Sound Library's takes were not liked in the hand. These are the
options to replace them: recordings of real guns from the Sonniss GDC 2016
bundle (Pole Position Production, each gun close and again from tens of
metres off; Audiobeast's warehouse; TS Sound) and a few designed game shots
(Gamemaster Audio).

A row is one recording of one gun from one place, and its op is `shots`:
the recording holds several, and the cleanest are cut out (dsp.single_shots).
`near` rows are for the gun in the hand; `far` rows are the same gun from
25 to 75 m, for gunfire heard at a distance. Every cut is levelled to the
same peak, so that two guns are compared and not two volumes.

The page shows them as `gunshots / <gun>`.
"""

A = "sonniss_archive"
PP = f"{A}/2016/Pole Position Production"
PEAK = 0.9

# How long a shot is kept, near and far, by gun. The automatics' are short:
# a held trigger stacks them (combat/verify/audio.py holds that to 12).
SECONDS = {"shotgun": (1.5, 2.0), "pistol": (1.0, 1.5), "smg": (0.6, 1.0),
           "rifle": (0.9, 1.4), "sniper": (1.8, 2.4)}

# (gun, name, where, the file under assets/cache/sounds, takes)
RECORDINGS = (
    ("shotgun", "spas12", "near", f"{PP} - SPAS-12*/*1m_right*.wav", 2),
    ("shotgun", "spas12", "far", f"{PP} - SPAS-12*/*50m*.wav", 1),
    ("shotgun", "saiga12", "near", f"{PP} - Saiga-12*/*1m_left*.wav", 2),
    ("shotgun", "saiga12", "far", f"{PP} - Saiga-12*/*55m*.wav", 2),
    ("shotgun", "usas12", "near", f"{PP} - USAS-12*/*1m_right*.wav", 2),
    ("shotgun", "usas12", "far", f"{PP} - USAS-12*/*55m*.wav", 1),
    ("shotgun", "remington870_warehouse", "near", f"{A}/2016/Audiobeast*/*Remington_870*.wav", 2),
    ("shotgun", "ts_slug", "near", f"{A}/2016/TS Sound*/Shotgun_Fire_Slug*.wav", 1),
    ("shotgun", "ts_round", "near", f"{A}/2016/TS Sound*/Shotgun_Fire_Round*.wav", 1),
    ("pistol", "sig_p229", "near", f"{PP} - Sig P229*/*1m_left*.wav", 2),
    ("pistol", "sig_p229", "far", f"{PP} - Sig P229*/*50m*.wav", 1),
    ("pistol", "glock18", "near", f"{PP} - Glock 18c/*1m_left*.wav", 2),
    ("pistol", "glock18", "far", f"{PP} - Glock 18c/*75m*.wav", 1),
    ("pistol", "beretta93r", "near", f"{PP} - Beretta 93R*/*1m_left*.wav", 2),
    ("pistol", "beretta93r", "far", f"{PP} - Beretta 93R*/*25m*.wav", 1),
    ("pistol", "hk_vp70", "near", f"{PP} -  Heckler & Koch VP70*/*1m_in_front*.wav", 2),
    ("pistol", "colt1911_warehouse", "near", f"{A}/2016/Audiobeast*/*Colt_M1911*.wav", 2),
    ("pistol", "magnum44", "near", f"{PP} - Smith & Wesson M29*/*2m_behind_right_PZM*.wav", 2),
    ("pistol", "designed_revolver", "near", f"{A}/2017/Gamemaster Audio -  Gun Sound Pack/gun_revolver*.wav", 1),
    ("smg", "ingram_m10", "near", f"{PP} - Ingram M10*/*1m_right*.wav", 2),
    ("smg", "ingram_m10", "far", f"{PP} - Ingram M10*/*50m*.wav", 1),
    ("smg", "mini_uzi", "near", f"{PP} - Mini Uzi*/*1m_left*.wav", 2),
    ("smg", "mini_uzi", "far", f"{PP} - Mini Uzi*/*30m*.wav", 1),
    ("smg", "uzi", "near", f"{PP} - Uzi 9mm/*1m_right*.wav", 2),
    ("smg", "uzi", "far", f"{PP} - Uzi 9mm/*75m*.wav", 1),
    ("smg", "mp5", "near", f"{PP} -  Heckler & Koch MP5*/*2m_behind*.wav", 2),
    ("smg", "mp5", "far", f"{PP} -  Heckler & Koch MP5*/*75m*.wav", 1),
    ("smg", "mp5_forest", "near", f"{A}/2018/*Outdoor Gun Acoustics*/MP5_forest*.wav", 2),
    ("smg", "designed_smg", "near", f"{A}/2017/Gamemaster Audio -  Gun Sound Pack/gun_submachine*.wav", 1),
    ("rifle", "akm", "near", f"{PP} - AKM*/*1m_left*.wav", 2),
    ("rifle", "akm", "far", f"{PP} - AKM*/*55m*.wav", 1),
    ("rifle", "ak47_open_area", "near", f"{A}/2018/*Outdoor Gun Acoustics*/AK47_big_open*.wav", 2),
    ("rifle", "g36c", "near", f"{PP} - Heckler & Koch G36C 5.56mm/*1m_left*.wav", 2),
    ("rifle", "g36c", "far", f"{PP} - Heckler & Koch G36C 5.56mm/*50m*.wav", 1),
    ("rifle", "hk416", "near", f"{PP} -  Heckler & Koch HK416*/*1m_left*.wav", 2),
    ("rifle", "hk416_small_room", "near", f"{A}/2016/Audiobeast*/*H&K_416*.wav", 1),
    ("sniper", "remington700", "near", f"{PP} - Remington 700*/*1m_right*.wav", 2),
    ("sniper", "remington700", "far", f"{PP} - Remington 700*/*50m*.wav", 2),
    ("sniper", "delisle_suppressed", "near", f"{PP} - De Lisle*/*1m_right*.wav", 2),
    ("sniper", "delisle_suppressed", "far", f"{PP} - De Lisle*/*55m*.wav", 1),
    ("sniper", "designed_sniper", "near", f"{A}/2017/Gamemaster Audio -  Gun Sound Pack/gun_rifle_sniper*.wav", 1),
    ("sniper", "designed_silenced", "near", f"{A}/2018/*Silenced Gun Sounds/gun_silenced_sniper*.wav", 1),
)

ROWS = tuple(
    ("shots", f"gunshots/{gun}/{name}_{where}", source,
     dict(seconds=SECONDS[gun][where == "far"], peak=PEAK, limit=takes))
    for gun, name, where, source, takes in RECORDINGS
)
