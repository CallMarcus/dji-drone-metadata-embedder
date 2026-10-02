"""Flight-relevant jurisdiction from the track's coordinates (#413).

Never a user setting: one flight, one jurisdiction, chosen from the data
(maintainer decision on #413). Conservative core/hull boxes per supported
jurisdiction: a track entirely inside a hull AND its core resolves; inside
a hull but outside the core sits too close to a land border to decide from
coordinates alone and gaps honestly; anywhere else is the no-provider gap.
When a track sits inside more than one hull (#499: the GB and IE hulls
overlap over Northern Ireland), cores break the tie — exactly one
jurisdiction's core must contain the track, or it gaps as a border band.
The boxes are deliberately coarse v1 constants — the failure mode they
must exclude is borrowing another jurisdiction's framing, not coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..track import Track

Box = tuple[float, float, float, float]  # lon_min, lat_min, lon_max, lat_max

MEASURE_US = (
    "Where this flight took place, 14 CFR 107.51(b) limits small-UAS "
    "altitude to 400 ft above ground level (AGL), with a structure "
    "exception that telemetry cannot evaluate. This record states "
    "measurements and their datums; it makes no determination."
)
MEASURE_EU = (
    "Where this flight took place, Regulation (EU) 2019/947 "
    "(UAS.OPEN.010(2)) requires staying within 120 m of the closest point "
    "of the surface of the earth, with obstacle exceptions that telemetry "
    "cannot evaluate. This record states measurements and their datums; "
    "it makes no determination."
)
MEASURE_UK = (
    "Where this flight took place, assimilated Regulation (EU) 2019/947 "
    "(UK law, UAS.OPEN.010(2)) requires staying within 120 m of the "
    "closest point of the surface of the earth, with obstacle exceptions "
    "that telemetry cannot evaluate. This record states measurements and "
    "their datums; it makes no determination."
)

_CORE: dict[str, list[Box]] = {
    "US": [
        (
            -124.6,
            33.1,
            -95.0,
            48.7,
        ),  # West + Plains, above the border's northernmost reach (Tijuana 32.7)
        (
            -111.2,
            31.9,
            -108.3,
            33.1,
        ),  # southern Arizona (Tucson); border is the 31.33N line here
        (
            -106.4,
            31.9,
            -103.0,
            33.1,
        ),  # southern New Mexico; border ~31.78N, El Paso itself gaps honestly
        (
            -103.0,
            30.0,
            -100.0,
            33.1,
        ),  # west Texas, north of the Big Bend river bend (~29.2N)
        (
            -100.0,
            28.8,
            -97.4,
            33.1,
        ),  # south-central Texas (San Antonio); Rio Grande well south
        (
            -97.4,
            26.1,
            -95.0,
            33.1,
        ),  # Texas Gulf coast (Houston, Corpus Christi); Matamoros is west of -97.4
        (
            -95.0,
            25.8,
            -84.5,
            46.5,
        ),  # central-east (unchanged; only Gulf water below Florida latitudes)
        (
            -84.5,
            24.4,
            -79.8,
            31.0,
        ),  # Florida; east bound keeps Bimini (-79.3) and Grand Bahama out
        (-84.5, 31.0, -74.0, 40.9),  # Southeast + mid-Atlantic
        (-75.5, 40.0, -69.8, 43.5),  # Northeast (unchanged)
        (-165.0, 55.5, -141.5, 70.5),  # Alaska interior (unchanged)
        (-160.5, 18.5, -154.5, 22.5),  # Hawaii (unchanged)
    ],
    "LU": [
        (
            5.9,
            49.55,
            6.3,
            49.8,
        ),  # south (Luxembourg City, Findel); Moselle border ~6.36E
        (5.95, 49.8, 6.25, 49.88),  # centre; border ~6.28E at Wallendorf (49.877)
        # Bettendorf band; the Our bows west to ~6.226 near Roth/Gentingen
        # just above 49.9N; border verified in (6.230, 6.235) at 49.90, so
        # 6.2 keeps >=2 km margin on the whole edge.
        (5.95, 49.88, 6.2, 49.9),
        (
            5.95,
            49.9,
            6.1,
            50.0,
        ),  # north; Our-river border ~6.13E (Vianden excluded), tip above 50.0 gaps
    ],
    "FI": [
        (22.8, 59.8, 26.5, 64.5),
        (24.5, 64.5, 29.0, 66.8),
        (25.0, 66.8, 27.5, 68.3),
    ],
    # Plateau-focused (#456): Geneva, Basel, Ticino, Valais and Grisons sit
    # against five neighbours and gap honestly as border bands. Every edge
    # and outside-margin point Nominatim-verified CH on 2026-08-05, >=5 km
    # of buffer to the nearest border throughout.
    "CH": [
        (7.05, 46.6, 7.9, 47.05),  # Bern / Fribourg / Thun / Interlaken
        (7.3, 47.0, 8.0, 47.3),  # Biel / Solothurn / Zofingen
        (8.0, 46.8, 8.9, 47.42),  # Lucerne / Zug / Zurich
    ],
    # Island geometry (#452): the only land border is with Northern
    # Ireland, whose southernmost reach is ~54.03 (Carlingford Lough) and
    # westernmost ~-8.18 (Belleek) — every core edge Nominatim-verified IE
    # on 2026-08-14 with >=15 km buffer. Donegal and the border counties
    # sit beyond the cores and gap honestly as border bands.
    "IE": [
        (-10.5, 51.45, -5.99, 53.85),  # south + centre (Cork/Dublin/Galway)
        (-10.2, 53.85, -8.4, 54.4),  # northwest coast (Mayo, Sligo)
    ],
    # An island needs sea margins, not land-border margins (#499): the
    # only land border is the IE/NI one, handled by the NI core edges
    # mirroring the IE cores from the other side (border extremes:
    # Carlingford ~54.03, Belleek ~-8.18). Verified 2026-08-15: Nominatim
    # confirms (54.42,-6.5), (54.45,-6.55) and (55.2,-6.5) as UK, right at
    # the core's south/west edges; Kent's SE corner clears Cap Gris-Nez by
    # ~12 km, the GB hull's south edge clears Alderney by ~14.5 km, and the
    # Hebrides core's south edge clears Malin Head/Inishtrahull by
    # ~30/~30 km — all >=10 km.
    # Deliberate gaps, each an honest border band: Isle of Man, Scilly,
    # Kintyre, the IE border counties from the NI side.
    "GB": [
        (-5.75, 49.93, -2.2, 53.4),  # SW England + Wales (Lizard 49.95 in)
        (-2.2, 50.45, 0.9, 51.6),  # southern England incl. London
        (0.9, 50.88, 1.42, 51.45),  # Kent; Cap Gris-Nez stays >=10 km off
        (-0.2, 51.6, 1.77, 53.3),  # East Anglia (Lowestoft 1.76 in)
        (-3.65, 53.4, -0.2, 55.3),  # N England (IoM stays >=40 km west)
        (-5.0, 55.3, -1.5, 58.7),  # Scotland mainland (Kintyre gaps)
        (-7.6, 55.7, -4.95, 58.55),  # Hebrides; Malin Head >=30 km south
        (-3.5, 58.85, -2.3, 59.45),  # Orkney
        (-1.85, 59.75, -0.65, 60.9),  # Shetland
        (-6.55, 54.42, -5.43, 55.25),  # Northern Ireland (Belfast, Coleraine)
    ],
    # Sea margins on three sides, one land border (Germany, ~54.8-54.95N
    # across Jutland). Every edge point Nominatim-verified 2026-08-15:
    # Kastrup and the Zealand core's Øresund edge both resolve DK (the
    # Swedish coast starts by 12.90 → >=13 km margin), Rønne/Skagen/Læsø
    # DK inside their cores, Helsingborg/Flensburg/Puttgarden foreign and
    # inside the hull only. Deliberate gaps, each an honest border band:
    # the German border strip south of 55.1 (Sønderborg, Ærø), Helsingør
    # (the 4.5 km strait), Gedser, Anholt-to-Sweden seas.
    "DK": [
        (8.0, 55.1, 10.9, 57.73),  # Jutland (Skagen in; Sweden >=35 km E)
        (9.6, 55.0, 10.85, 55.1),  # south Funen (Svendborg)
        (11.05, 54.95, 12.68, 55.9),  # Zealand incl. Copenhagen/Kastrup
        (11.3, 55.9, 12.4, 56.1),  # N Zealand, cut back from the strait
        (11.9, 54.85, 12.56, 54.97),  # Møn (German coast >=40 km)
        (11.0, 54.63, 12.3, 54.95),  # Lolland-Falster (Fehmarn >=11 km)
        (14.67, 54.98, 15.17, 55.32),  # Bornholm (Sweden >=60 km)
        (10.85, 57.1, 11.25, 57.35),  # Læsø
        (11.38, 56.6, 11.78, 56.78),  # Anholt
    ],
    # Long land borders with Norway (west) and Finland (the Torne/Muonio
    # valley, northeast), plus the Öresund narrows against Denmark. All
    # 26 edge probes Nominatim-verified 2026-08-19: Swedish markers
    # (Malmö, Vinga, Grisslehamn, Halmstad, Kalix coast, Kiruna, Fårö…)
    # resolve SE inside the cores, foreign markers (Saltholm/Læsø/Anholt
    # DK, Halden NO, Eckerö and Valsörarna FI) sit outside them. Probes
    # at 12.75–12.9E (61.0–61.7N), near the Trysil-area bulge on the
    # Norwegian side of the border, resolve SE — confirming Norway's
    # easternmost reach there sits west of 12.9E, so the inland 13.4
    # west edge keeps >=27 km of margin. Deliberate gaps, each
    # an honest border band: the Öresund shore north of Malmö (Ven,
    # Landskrona, Helsingborg, Kullen/Bjäre), Strömstad and the
    # Norway-border strip, the Torne valley (Haparanda, Karesuando),
    # and the outer Stockholm archipelago beyond the Åland margin.
    # The mountain municipalities (Sälen, Åre) sit west of the hull
    # entirely, so they get the no-provider message, not the band one.
    "SE": [
        (12.95, 55.33, 16.05, 56.45),  # Skåne + Blekinge (Saltholm DK >=10 km W)
        (12.0, 56.45, 12.95, 57.15),  # Halland coast (Anholt DK >=21 km W)
        (11.55, 57.15, 12.3, 58.55),  # west coast, Gothenburg (Læsø DK >=19 km W)
        (16.3, 56.15, 17.2, 57.4),  # Öland
        (17.9, 56.85, 19.4, 58.0),  # Gotland incl. Fårö
        (12.3, 56.35, 19.2, 58.9),  # Götaland interior + east coast
        (13.4, 58.9, 19.3, 59.7),  # south Svealand (Stockholm, Karlstad)
        (13.4, 59.7, 18.9, 61.5),  # north Svealand (Märket FI >=13 km E)
        (14.5, 61.5, 20.6, 63.6),  # lower Norrland (Kvarken FI >=23 km E)
        (17.5, 63.6, 23.2, 65.95),  # upper Norrland coast (Umeå, Luleå, Boden)
        (18.9, 65.95, 22.4, 67.5),  # Jokkmokk/Gällivare (Torne border >=40 km E)
        (19.6, 67.5, 21.6, 68.0),  # Kiruna
    ],
    # Land borders with Latvia (south) and Russia (east: the Narva river
    # and the lakes), sea north and west. All 20 edge probes
    # Nominatim-verified 2026-08-19: Tallinn/Kunda/Haapsalu/Pärnu/Tartu/
    # Kohtla-Järve/Kuressaare/Sõrve/Kärdla and the interiors resolve EE
    # inside the cores; Ivangorod RU, Valka LV and Cape Kolka LV sit
    # outside them. The Kõpu peninsula (Ristna) and the Lahemaa
    # headlands (Käsmu) recovered via #521, probes 2026-08-20; the N
    # core top stays 0.15° under the FI core floor (Hanko 59.82).
    # The cores are inset rectangles, not a hand-traced border, so the
    # gaps are wider than the border bands that motivate them: alongside
    # the true border bands (Valga, whose Latvian twin Valka is 1.2 km
    # away; Narva and the river strip; Setomaa; the Peipus shore; the
    # southern border strip), Vilsandi (west of the Saaremaa core) and
    # the southern interior (Otepää, Võru) gap too, even though no
    # border sits nearby.
    "EE": [
        (
            23.4,
            58.75,
            26.6,
            59.65,
        ),  # N + NW mainland (Tallinn; Käsmu in, Purekkari cape 59.66 gaps)
        (23.5, 58.2, 25.6, 58.85),  # SW mainland (Pärnu; LV border >=12 km)
        (
            25.6,
            58.2,
            26.9,
            59.3,
        ),  # centre-east (Tartu; edge at the Peipus shore, mid-lake border beyond)
        (26.6, 59.1, 27.75, 59.47),  # NE (Kohtla-Järve; Narva river >=17 km)
        (21.9, 57.9, 23.45, 58.65),  # Saaremaa + Muhu (Kolka LV >=17 km S)
        (22.0, 58.68, 23.1, 59.1),  # Hiiumaa incl. Kõpu/Ristna
    ],
    # Land borders on every side (IT, AT, HU, HR) and a 47 km coast, so the
    # cores are the interior only. All 51 edge probes Nominatim-verified
    # 2026-09-05: Slovenian markers (Tržič, Idrija, Žužemberk, Majšperk,
    # Markovci, Ilirska Bistrica, Divača, Tišina, Moravske Toplice,
    # Beltinci, Slovenj Gradec) resolve SI inside the cores; foreign
    # markers (Trieste, Gorizia, Tarvisio, Villach, Klagenfurt, Bleiburg,
    # Leibnitz, Bad Radkersburg, Lenti, Čakovec, Varaždin, Krapina, Zagreb,
    # Karlovac, Buje, Umag) sit outside them. Deliberate gaps, each an
    # honest border band: Koper and the whole coast (Italy <=5 km), Nova
    # Gorica (Gorizia adjoins), Jesenice/Kranjska Gora, the Drava valley
    # (Dravograd), Šentilj, Gornja Radgona and the Mura, Lendava, Brežice,
    # Metlika and the Kolpa, Kočevje.
    "SI": [
        (
            14.00,
            45.85,
            14.95,
            46.38,
        ),  # Ljubljana basin, Kranj, Kamnik, Bled (Austria >=8 km N, Italy >=30 km W)
        (14.95, 46.05, 15.45, 46.45),  # Celje, Velenje, Zasavje (Austria >=15 km N)
        (
            15.50,
            46.35,
            15.95,
            46.58,
        ),  # Maribor, Ptuj (Šentilj 46.68 N, Rogatec 46.23 S)
        (14.95, 45.75, 15.25, 45.95),  # Novo Mesto (Metlika 45.65 S)
        (
            14.00,
            45.62,
            14.40,
            45.85,
        ),  # Postojna, Notranjska (Italy >=20 km W, Croatia >=15 km S)
        (
            16.08,
            46.58,
            16.28,
            46.70,
        ),  # Murska Sobota (Mura/Austria >=8 km NW, Hungary >=13 km E)
    ],
    # Land borders with FR, LU, DE and NL, the North Sea on the fourth side.
    # Every edge and corner Nominatim-verified BE on 2026-09-16 (the coastal
    # box's NW corner is open sea, safe: no other jurisdiction's zones apply
    # there). Deliberate gaps, each an honest border band: the French strip
    # (Kortrijk, Ieper, Tournai, Chimay), the Campine north of Turnhout, the
    # Meuse below Dinant (the Givet salient reaches 50.15N), Belgian
    # Luxembourg (Arlon, Bastogne), the German-speaking east (Eupen,
    # Verviers) and the Maas at Maasmechelen.
    "BE": [
        (
            2.75,
            50.95,
            3.30,
            51.40,
        ),  # coast + West Flanders (Ostend, Bruges); France >=14 km W, NL >=6 km E at Knokke
        (
            3.35,
            50.80,
            4.15,
            51.12,
        ),  # Ghent, Aalst, Oudenaarde; Sas van Gent (NL, 51.23) >=12 km N
        (
            4.15,
            50.35,
            5.00,
            51.28,
        ),  # Brussels, Antwerp, Leuven, Mechelen, Charleroi; NL border >=9 km N
        (
            4.60,
            50.28,
            5.60,
            50.70,
        ),  # Namur, Ciney, Marche approaches; Givet (FR, 50.15) >=14 km S
        (3.75, 50.40, 4.15, 50.80),  # Mons, La Louvière, Ath; France >=9 km S
        (5.00, 50.80, 5.45, 51.15),  # Hasselt, Sint-Truiden, Genk; NL >=12 km N and E
        (
            5.30,
            50.45,
            5.75,
            50.68,
        ),  # Liège basin; NL (Visé/Maastricht) >=8 km N, DE >=17 km E
    ],
    # Land borders with Estonia (N), Russia (E), Belarus (SE) and Lithuania
    # (S). The Baltic coast is free, but the Gulf of Riga and the Irbe
    # Strait are not: Estonian waters around Ruhnu and the Irbe median line
    # bound them, and territorial airspace follows territorial sea, so the
    # northern edges stay well south of both. Cores stay >=12 km inside
    # every land border and out of Estonian waters. Probed against
    # Nominatim 2026-10-01 in two passes: town markers first, then an
    # edge-and-corner sweep (every perimeter sample about every 0.1 deg,
    # each probed at the edge and 12 km straight outward, corners also
    # diagonally; 432 probes, zero foreign hits, sea allowed).
    # Deliberate gaps, each an honest border band or an Estonian-water
    # margin: Daugavpils (~12 km from Lithuania, ~20 from Belarus),
    # Krāslava, Bauska, Valka/Valga, Ainaži and Salacgrīva, Alūksne, Ludza
    # and Zilupe, Rucava and Pape, and the Irbe Strait coast (Kolka cape,
    # 57.75 N, may gap).
    "LV": [
        (
            20.9,
            56.47,
            21.6,
            57.55,
        ),  # Liepāja + the Kurzeme coast; LT border ~56.07 at the coast, ~56.34 at Skuodas => >=14 km; Irbe Strait kept clear
        (
            21.6,
            56.55,
            23.0,
            57.45,
        ),  # Ventspils, Kuldīga, Saldus, Talsi; south edge pulled 0.03 N inboard: its 12 km probe (56.44 N, 22.07 E) is Latvian, the old edge's was Lithuanian
        (
            22.9,
            56.55,
            24.3,
            57.35,
        ),  # Riga west, Jūrmala, Jelgava, Tukums; LT 56.37 => >=20 km; north edge clear of Estonian waters off Ruhnu
        (
            24.3,
            56.58,
            25.2,
            57.60,
        ),  # Riga east, Ogre, Sigulda, Limbaži; south edge pulled 0.03 N inboard: its 12 km probe (56.47 N, 24.89 E near Biržai) is Latvian, the old edge's was Lithuanian; EE coast 57.87 => >=30 km
        (
            25.0,
            56.75,
            25.9,
            57.60,
        ),  # Cēsis, Valmiera, Smiltene; Valka/Valga 57.78 => >=20 km
        (
            25.9,
            56.75,
            26.3,
            57.45,
        ),  # Madona; capped at 57.45 N because the EE border dips to ~57.55 east of Valga (Mõniste is EE at 57.56 N, 26.53 E)
        (
            26.3,
            56.60,
            27.3,
            57.35,
        ),  # Gulbene, Balvi; EE border dips to ~57.55 past Ape, RU east of 27.7 => ~24 km
        (
            25.8,
            56.25,
            26.9,
            56.75,
        ),  # Jēkabpils, Līvāni, Preiļi; LT border ~56.12 at Aknīste => >=13 km
        (
            26.4,
            55.98,
            27.45,
            56.60,
        ),  # Rēzekne; SE corner pulled 0.03 N / 0.05 E inboard so its 12 km probes stay Latvian (the old corner's were Belarusian); RU east of 27.9 => ~24 km
    ],
    # Land borders with Portugal (west and south-west), France and Andorra
    # (the Pyrenees) and Gibraltar; the sea is free on every other side,
    # but Nominatim counts territorial waters as the coastal state's, so
    # the southern edges also keep out of Algerian and Moroccan waters.
    # Cores stay >=12 km inside every land border. Ceuta and Melilla are
    # outside both hulls on purpose (Moroccan land borders), and the cores
    # stop short of the Strait of Gibraltar, so nothing there resolves.
    # Probed against Nominatim 2026-10-02 in two passes: 60 town markers
    # first (Ceuta, Melilla, Tangier and Tarfaya sit outside every hull
    # by design; Ciudad Rodrigo is a real Spanish town about 25 km from
    # Portugal and was gapped by pulling its edge in), then an
    # edge-and-corner sweep (every perimeter sample about every 0.1 deg,
    # each probed at the edge and 12 km straight outward, corners also
    # diagonally, sea allowed). The first sweep of the candidate boxes
    # found 92 foreign hits (Minho, Arribes del Duero, Algerian coast,
    # Moroccan waters off Fuerteventura); the boxes below are the
    # adjusted set, 1,264 probes, zero foreign hits. The two Canarias boxes
    # were then re-swept after the southern Gran Canaria and El Hierro
    # change: 292 probes, zero foreign hits.
    # Deliberate gaps, each an honest border band: Badajoz, Tui and the
    # Minho valley, Ciudad Rodrigo, Ayamonte, Huelva (about 40 km from
    # Portugal, yet west of the Andalusia core's 6.6 W edge; a future box
    # there needs its own sweep), Irun and San Sebastián, the
    # Campo de Gibraltar (Algeciras, La Línea, Tarifa), Puigcerdà, La Seu
    # d'Urgell, Figueres and Jaca; Ceuta and Melilla; the open sea south
    # of 37.4 N between 1 W and 4.5 E and south-east of Fuerteventura.
    "ES": [
        (
            -9.3,
            42.2,
            -8.4,
            43.8,
        ),  # Galicia west of the Minho bend (Vigo, A Coruña); PT border at the Minho mouth 41.87 N
        (
            -8.4,
            42.3,
            -8.0,
            43.8,
        ),  # the Ribadavia stretch of the Minho valley; south edge 42.3 N because the 12 km probes from 42.2 N at 8.3 W and 8.2 W were Portuguese (Melgaço)
        (
            -8.0,
            42.2,
            -6.0,
            43.8,
        ),  # Galicia east (Ourense, Lugo), Asturias; PT (Verín side, border near 41.93 N) is ~30 km south of the 42.2 N edge
        (
            -6.0,
            41.2,
            -2.05,
            43.8,
        ),  # León, Burgos, Valladolid, Cantabria, Bilbao, Vitoria; PT (Zamora) <= -6.2 => >=14 km, FR (Irun -1.78) => >=20 km
        (
            -6.3,
            40.2,
            -2.05,
            41.2,
        ),  # Salamanca, Ávila, Segovia, Madrid; west edge 6.3 W gaps Ciudad Rodrigo on purpose and keeps clear of the Arribes del Duero (PT reaches 41.3 N at 6.5 W => about 19 km at the north-west corner)
        (
            -2.05,
            41.2,
            -1.2,
            42.85,
        ),  # Navarra south of Pamplona; FR border >= 43.0 => >=16 km
        (
            -1.2,
            40.2,
            0.3,
            42.5,
        ),  # Zaragoza, Huesca, Teruel; FR border >= 42.7 => >=22 km
        (0.3, 40.6, 3.3, 42.2),  # Catalonia; FR/AD border >= 42.4 => >=22 km
        (
            -2.5,
            36.7,
            -1.0,
            40.6,
        ),  # Almería, Murcia, Alicante; sea to the south (Algeria's Cap Falcon, 35.77 N 0.8 W, is ~100 km from the south-east corner)
        (
            -1.0,
            37.4,
            4.5,
            40.6,
        ),  # Valencia coast and the Balearics; south edge 37.4 N because Algerian land and territorial waters reach past 37.04 N near Dellys (3.9 E); the old 36.7 N edge sat inside Algeria
        (
            -6.6,
            36.3,
            -2.5,
            40.2,
        ),  # Andalusia + Cáceres; PT (Huelva/Badajoz) <= -7.0 => >=35 km, Gibraltar 36.15 => >=16 km
        (
            -18.3,
            27.6,
            -14.6,
            29.4,
        ),  # western Canarias (El Hierro, La Palma, La Gomera, Tenerife, Gran Canaria); the nearest foreign territory is Western Sahara/Morocco, over 100 km east, so southern Gran Canaria and El Hierro resolve
        (
            -14.6,
            28.0,
            -13.4,
            29.4,
        ),  # eastern Canarias (Fuerteventura, Lanzarote); south edge 28.0 N and east edge -13.4 keep clear of the Moroccan waters Nominatim places south-east of Fuerteventura; the waters south of Jandia's tip and the sea towards Africa gap
    ],
    # Nine land borders (DK, PL, CZ, AT, CH, FR, LU, BE, NL) and the North
    # Sea and Baltic coast. Cores stay >=12 km inside every land border, and
    # Danish, Dutch and Swiss waters count as foreign too, which is why the
    # coastal edges are cut back from Als, Falster/Møn and Lake Constance.
    # Probed against Nominatim 2026-10-02 in two passes: 87 town markers
    # first (42 German cities that must resolve, 21 German border towns
    # that must gap, 24 foreign towns inside the hull that must stay
    # outside every core; Karlsruhe, which the candidate boxes left in a
    # gap, was swapped for Heidelberg, and Hof for Selb, which the first
    # box set left in a core), then an edge-and-corner sweep (every
    # perimeter sample about every 0.1 deg, each probed at the edge and 12
    # km straight outward, corners also diagonally, sea allowed). The
    # candidate boxes drew 13 foreign hits (Danish waters off Als and
    # Falster, the Czech Aš salient near Selb, Swiss land at Schaffhausen,
    # Austrian land at the Salzach and near Kufstein, French land across
    # the Rhine at Breisach and Strasbourg); the boxes below are the
    # adjusted set, 22 boxes, 800 probes, zero foreign hits.
    # Deliberate gaps, each an honest border band or a coast margin: the 21
    # border towns (Aachen, Trier, Saarbrücken, Konstanz, Passau, Görlitz,
    # Frankfurt (Oder), Flensburg, Emden, Lörrach, Kehl, Garmisch,
    # Berchtesgaden, Lindau, Kleve, Mönchengladbach, Gronau, Zittau, Selb,
    # Pirmasens, Usedom's Ahlbeck), the Saarland, Karlsruhe and the Upper
    # Rhine strip (Offenburg, Baden-Baden), the Vogtland round Hof, Cottbus
    # and Lusatia east of 13.9 E, Rosenheim and the Alpine foothills, the
    # Ems and Emsland strip (Nordhorn), Sylt and the Flensburg fjord coast,
    # and the Fehmarn Belt shore.
    "DE": [
        (7.45, 52.9, 9.7, 54.68),
        (9.7, 52.9, 10.9, 54.4),
        (10.9, 52.9, 11.3, 54.45),
        (11.3, 52.9, 12.6, 54.35),
        (12.6, 52.9, 12.9, 54.4),
        (12.9, 52.9, 13.85, 54.68),
        (10.5, 50.95, 13.9, 52.9),
        (11.9, 50.7, 13.1, 50.95),
        (7.45, 51.6, 9.5, 52.9),
        (6.6, 50.4, 9.5, 51.6),
        (8.0, 51.3, 11.5, 52.9),
        (7.5, 49.3, 10.5, 50.4),
        (8.0, 49.17, 10.5, 49.3),
        (8.6, 49.05, 10.5, 49.17),
        (9.5, 49.05, 12.0, 50.0),
        (9.5, 50.0, 11.85, 50.95),
        (9.0, 47.85, 12.0, 49.05),
        (8.6, 47.95, 9.0, 49.05),
        (12.0, 47.95, 12.5, 48.3),
        (12.0, 48.3, 12.75, 49.05),
        (7.85, 47.95, 8.6, 48.1),
        (8.1, 48.1, 8.6, 48.6),
    ],
}
_HULL: dict[str, list[Box]] = {
    "US": [
        (-125.5, 24.0, -66.5, 49.5),
        (-170.0, 51.0, -129.0, 71.8),
        (-161.0, 18.0, -154.0, 23.0),
    ],
    "LU": [(5.70, 49.44, 6.60, 50.20)],
    "FI": [(19.0, 59.5, 31.6, 70.1)],
    "CH": [(5.9, 45.8, 10.5, 47.85)],
    # Covers the whole island including Northern Ireland on purpose: an NI
    # flight then gaps as a border band instead of "no provider", the same
    # semantics the CH hull gives Konstanz.
    "IE": [(-11.0, 51.3, -5.3, 55.6)],
    # Covers Great Britain, its islands and Northern Ireland; the Isle
    # of Man sits inside deliberately with no core (its own AIP, no
    # Ronaldsway FRZ in the dataset) and the Channel Islands stay
    # outside entirely (zero zones in the dataset). The NI box overlaps
    # the IE hull on purpose: cores break the tie (#499).
    "GB": [
        (-5.9, 49.85, 1.9, 61.0),  # Great Britain + Northern Isles
        (-6.6, 49.75, -5.9, 50.3),  # Scilly approaches
        (-8.0, 55.55, -5.9, 61.0),  # Hebridean seas
        (-8.2, 54.0, -5.35, 55.4),  # Northern Ireland
    ],
    # Flensburg, Helsingborg and Fehmarn's north tip sit inside the hull
    # deliberately (the CH-Konstanz semantics: a border band, not "no
    # provider"); Malmö stays outside entirely.
    "DK": [
        (7.5, 54.68, 11.0, 57.9),  # Jutland + Funen
        (11.0, 54.5, 12.78, 57.4),  # Zealand / Lolland-Falster / Øresund
        (14.6, 54.9, 15.35, 55.38),  # Bornholm
    ],
    # Læsø, Bornholm and the Copenhagen shore sit inside the south hull
    # deliberately and resolve DK via its cores (#499 tie-break); Halden,
    # Åland and the Tornio strip sit inside as honest border bands
    # (Konstanz semantics). Oslo stays outside entirely (west of 10.9).
    "SE": [
        (10.9, 55.05, 19.7, 61.0),  # Götaland + Svealand + approaches
        (13.4, 61.0, 24.3, 66.4),  # Norrland + the Bothnian sea
        (16.3, 66.4, 24.2, 69.3),  # Lapland up to Treriksröset
    ],
    # Valka, Ivangorod and the Latvian coast strip sit inside the hull
    # deliberately (border-band semantics); Riga and Helsinki stay
    # outside. Overlaps the FI hull over the Gulf of Finland on purpose:
    # cores break the tie (#499).
    "EE": [(21.5, 57.45, 28.45, 59.9)],
    # The national bounding box: Trieste, Gorizia, Villach, Klagenfurt,
    # Bad Radkersburg, Zagreb and Istria sit inside it deliberately, so a
    # flight there gaps as a border band (cores decide), never as SI.
    "SI": [(13.35, 45.40, 16.62, 46.88)],
    # The national bounding box with a sea margin north of the coast:
    # Lille, Breda, Maastricht, Aachen and Belgian Luxembourg sit inside it
    # deliberately (border-band semantics). Overlaps the LU hull over the
    # Grand Duchy on purpose: cores break the tie (#499), so Luxembourg City
    # keeps resolving LU.
    "BE": [(2.50, 49.49, 6.42, 51.51)],
    # The national bounding box with a sea margin: Valga, Palanga, the
    # Lithuanian and Belarusian border towns and Sõrve on Saaremaa sit
    # inside it deliberately (border-band semantics; the EE core claims
    # Sõrve). Overlaps the EE hull's southern band on purpose: cores decide.
    "LV": [(20.8, 55.6, 28.3, 58.15)],
    # Mainland + Balearics, with a sea margin; Portugal, the French and
    # Andorran Pyrenees and Gibraltar sit inside it deliberately (cores
    # decide). Ceuta (35.89) and Melilla (35.29) sit south of the floor
    # on purpose: the North African enclaves gap as no-provider rather
    # than borrow a mainland framing across the strait.
    "ES": [(-9.4, 35.95, 4.5, 43.9), (-18.4, 27.5, -13.3, 29.5)],
    # The national bounding box with a sea margin. It overlaps the DK, LU,
    # BE and CH hulls on purpose (Sønderborg, Luxembourg City, Eupen and
    # Verviers, Zurich), and Strasbourg, Basel, Salzburg, Cheb, Szczecin and
    # the Dutch frontier towns sit inside it (border-band semantics). Cores
    # decide (#499): the DE cores keep clear of every neighbouring core, so
    # Luxembourg City still resolves LU and Zurich CH, and no foreign town
    # ever resolves DE.
    "DE": [(5.8, 47.2, 15.1, 55.1)],
}
# CH takes the EU measure: Regulation (EU) 2019/947 applies in Switzerland
# since 2023-01-01 under the CH-EU air transport agreement.
_MEASURE = {
    "US": MEASURE_US,
    "LU": MEASURE_EU,
    "FI": MEASURE_EU,
    "CH": MEASURE_EU,
    "IE": MEASURE_EU,
    "GB": MEASURE_UK,
    "DK": MEASURE_EU,
    "SE": MEASURE_EU,
    "EE": MEASURE_EU,
    "SI": MEASURE_EU,
    "BE": MEASURE_EU,
    "LV": MEASURE_EU,
    "ES": MEASURE_EU,
    "DE": MEASURE_EU,
}


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    measure_note: str


@dataclass(frozen=True)
class Resolution:
    jurisdiction: Jurisdiction | None
    gap_reason: str | None


def _all_inside(track: Track, boxes: list[Box]) -> bool:
    return all(
        any(x1 <= p.lon <= x2 and y1 <= p.lat <= y2 for x1, y1, x2, y2 in boxes)
        for p in track.points
    )


def resolve_jurisdiction(track: Track) -> Resolution:
    if not track.points:
        return Resolution(None, "the track has no GPS points")
    hulls = [code for code, boxes in _HULL.items() if _all_inside(track, boxes)]
    if not hulls:
        return Resolution(
            None,
            "no supported airspace data source for this location "
            "(covered: the US, Luxembourg, Finland, Switzerland, "
            "Ireland, the UK, Denmark, Sweden, Estonia, Slovenia, Belgium, "
            "Latvia, Spain and Germany)",
        )
    cores = [code for code in hulls if _all_inside(track, _CORE[code])]
    if len(cores) != 1:
        return Resolution(
            None,
            "the flight sits too close to a jurisdiction boundary to "
            "choose an airspace source from coordinates alone; airspace "
            "lookup skipped",
        )
    return Resolution(Jurisdiction(cores[0], _MEASURE[cores[0]]), None)
