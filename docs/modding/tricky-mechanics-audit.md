# Audit des mécaniques Tricky — 3 novembre 2026

État examiné : `57008fc`, les onze mondes du disque USA et les dix-neuf
variantes préparées. Analyse des données et du code d'import ; aucune nouvelle
partie, aucun test automatisé et aucun replay pour cet audit.

## Conclusion

Suivi : le [plan d'implémentation](../plans/tricky-mechanics-implementation.md)
consigne les corrections postérieures à cet état de référence. Le Freestyle
solo, les temps initiaux extraits de l'exécutable et les événements de temps
SOP sont maintenant implémentés. Les huit murs de Pipedream et le téléporteur
de Merqury disposent de scripts natifs ; un mur et la traversée du portail ont
été observés en jeu. Les courbes des objets et les effets de texture persistants
sont aussi importés, avec une observation partielle de leurs acteurs natifs.
Les lignes ci-dessous restent l'inventaire de départ, pas le statut actuel
de chaque correction. Les séquences différées/conditionnelles, les vitres
fissurables, les movers et plusieurs familles de décors restent à traiter.

Oui, plusieurs mécaniques restent absentes. Les plus importantes pour le
parcours sont les murs destructibles de Pipedream, le téléporteur de Merqury,
les objets mobiles qui modifient les passages et les portes de temps Freestyle.
Les zones de retour en piste pilotées par les scripts SSF manquent aussi.

Les poussées déjà ajoutées couvrent tous les volumes de la famille boost
connue trouvés par l'inventaire : 42 à Tokyo, 18 à Merqury et 7 en Alaska,
dans chacun des deux modes. Aucun volume supplémentaire de cette famille
n'a été trouvé sur les autres maps. Cela ne démontre pas l'équivalence de
toutes les interactions physiques avec les objets.

## Mécaniques par map

| Map | Comportements source manquants ou partiels | Preuves dans les données source |
| --- | --- | --- |
| **Merqury City Meltdown** | Téléporteur ; ouverture des portes d'égout ; train suivant son trajet ; autres objets cassables. Les 18 poussées sont déjà importées. | `2308 Mdl_TeleportStart_0` : chaîne 905, son 122 puis MainType 24 vers `3332 Mdl_TeleportExit_0`. Portes `3623/3624/3967/3968` : animations delta 257 via d'autres instances. Train `344` : mover 2/1, spline 38. |
| **Pipedream** | **Huit murs destructibles** restent privés de leur logique d'ouverture et de fragments. Ils ne font pas partie des panneaux LCD remplacés auparavant. | Triggers `546/550/469/473/423/427/508/512`, appels des fonctions `BreakWall_1001` à `BreakWall_1008`. Exemple : mur `543 Mdl_Wall_Peeps_1001`, chaîne 131, DeadNode mode 4 ; fragments `544` activés séparément. |
| **Elysium Alps** | Trois tremplins mobiles ; une porte animée ; animations de branches et d'objets cassés. | `153/154/179 Mdl_DynKicker_Event1_*` : subtype 257. `3851 Mdl_Elys_Door_5000` reçoit une animation 256 par un lien vers une autre instance. |
| **Mesablanca** | Séquence d'arbres qui tombent et d'activation de rails ; pont mobile et sa surface de collision ; wagonnet animé. | Trigger `2168`, chaîne 221 : arbres `2236–2239`, puis commandes MainType 25 sur rails **87 et 88**. Pont `1443` et surface `1444` : animations synchronisées 256. Wagonnet `771`, animé par une autre instance. |
| **Aloha Ice Jam** | Cinq barrières mobiles et un tremplin déclenché par proximité. Les formes de collision sont conservées, mais pas leur mouvement source. | Barrières `686/1788/1799/1816/1817` : animation combo 258 et commande au contact. Trigger `679` → tremplin `662`, chaîne 235, animation 256. |
| **Tokyo Megaplex** | Flippers, portes tournantes et autres obstacles animés ; **20 vitres à fissuration/destruction**, distinctes des panneaux LCD de raccourci. | Flippers et portes : animations 256, souvent déclenchées indirectement. Vitres `Mdl_Glass_Pane_*` : subtype 14, puis canal de déclenchement activant disparition et fragments. Exemple : `7`, chaînes 587/589. Le tube, les ventilations et convoyeurs de la famille boost sont déjà couverts. |
| **Alaska** | Animations des deux ventilateurs ; destruction/animation des stalactites et de leurs fragments ; resets dans les rivières. Les **7 volumes ForceWind** sont déjà importés. | Ventilateurs `785/786`, animation 256. `Mdl_IcicleBigA_*` et morceaux : subtype 20. `Mdl_Water_River_*` : MainType 13. |
| **Snowdream** | Clôtures en bois et lanternes cassables ; animations de souffleurs et d'autres décors. Pas de poussée de soufflerie supplémentaire établie dans les chaînes boost. | `1466 Mdl_FenceWooden_Break5_3000`, autres clôtures et lanternes : subtype 20. `Mdl_SnowBlower_Top_*` : animations 256. Une animation de souffleur ne prouve pas une force appliquée au rider. |
| **Garibaldi** | Animations de marqueurs/objets cassés et resets d'objets. Les panneaux LCD de raccourci, pickups et multiplicateurs disposent déjà de leurs remplacements SSX3. | Exemple `147 Mdl_Obstacle_PathMarker_2` : subtype 20. Les nœuds Roller des sacs et panneaux ne sont pas traduits ; l'équivalence de leur réaction physique native reste à examiner. |
| **Untracked** | Branches cassables/animées ; hélicoptères animés ; un reset scripté. Aucun autre mécanisme de poussée ou de tours repéré. | `Mdl_Branch_Broken*` : subtype 20. `6 Mdl_Proxy_ResetThing_1000` : MainType 13. |
| **Trick Tutorial** | Pas de nouveau mécanisme de la famille boost/téléporteur/murs mobiles repéré. Réactions des sacs de collision à examiner. | Dix objets `Mdl_CrashBag_Event_*` portent un nœud Roller. Les objectifs et instructions du tutoriel ne sont pas couverts par cet audit des objets SSF. |

Les collisions et le rebond natif ne sont pas globalement absents : l'import
conserve les proxies, masses/restitutions et le drapeau `PlayerBounce`.
Les nœuds **Roller** source ne sont cependant pas exécutés. Une réaction
physique native possible ne suffit donc pas à affirmer que l'effet original
est reproduit. De même, un bumper de Tokyo peut déjà rebondir sans que ses
animations ni les mouvements des flippers soient présents.

## Deux manques transversaux

**Portes de temps Freestyle : 22 stations logiques.** Les `.SOP` contiennent
des événements 11 dont la valeur est un bonus de secondes. Les copies sur
les routes alternatives sont regroupées ici par distance restante, à 2 m
près. Tokyo offre des bonus différents selon la route à une même station.

| Map Freestyle | Stations | Bonus source en secondes |
| --- | ---: | --- |
| Garibaldi | 3 | 45, 75, 75 |
| Snowdream | 2 | 60, 90 |
| Elysium Alps | 3 | 90, 100, 110 |
| Mesablanca | 3 | 60, 90, 90 |
| Merqury City | 3 | 75, 90, 150 |
| Tokyo Megaplex | 1 | 120 ou 150 selon la route |
| Aloha Ice Jam | 2 | 45, 120 |
| Alaska | 3 | 30, 110, 150 |
| Pipedream | 2 | 90, 90 |

La liste des bonus est présentée sans ordre de passage. Les variantes
actuelles utilisent toujours le `.AIP` de Race dans `build_tricky_world.py`.
`ssx3_aip.py` transforme ses checkpoints en indices natifs ; il ne reprend
pas les valeurs de temps du `.SOP`. Un panneau visible n'implique donc pas
qu'un bonus de chrono soit attribué. Le temps de départ original n'a pas
été déterminé dans cet audit.

**Retours en piste scriptés : 985 instances liées à MainType 13.** Cela
comprend volumes invisibles, eau, murs et certains décors. Leurs callbacks
ne sont pas repris par `ssx3_worldscript.py`. Les resets des patches de
terrain, déjà traduits via le type de surface, sont un système distinct
et restent présents. Il ne faut pas remplacer tous ces callbacks par des
boîtes : certains sont des contacts avec une géométrie comportant un passage,
comme le bâtiment du Parlement de Merqury ; une boîte fermerait son tunnel.

## Cause et ordre de correction proposé

Le convertisseur importe la géométrie, les colliders et les propriétés
statiques. Les scripts Tricky ne s'exécutent pas. Les exceptions actuelles
sont les objets SSX3 substitués et l'adaptateur des volumes de poussée/tours.
Les animations de prefab ne sont pas transposées au runtime SSX3.

1. Murs Pipedream et téléporteur Merqury : passages et raccourcis fonctionnels.
2. Portes de temps `.SOP` : déroulement du Freestyle sur les neuf maps concernées.
3. Animations avec collision : Aloha, Elysium, portes d'égout, arbres/rails de Mesa.
4. Vitres Tokyo et autres objets destructibles ; resets scriptés.
5. Trains, hélices, particules, feux d'artifice et autres animations décoratives.

Pour les rails de Mesa, le problème dépasse l'animation : les splines 87/88
ont le style source **NonGrind = 1** et sont commutées par un effet. L'import
actuel traite cette valeur comme une surface de neige, avec des flags actifs,
et perd cette transition. Il faut conserver la distinction entre style de
rail et type de surface.

## Inventaire reproductible et limites

Depuis le dépôt :

```powershell
python tools/audit_tricky_mechanics.py
```

Le résultat détaillé reste ignoré sous `.cache/tricky-mechanics-audit.json`.
Chaque entrée conserve map, mode, instance, type de mécanique, chaîne et
instance porteuse. L'outil suit les liens **ActOnInstance** et les appels de
fonction : une inspection des seuls effets directement attachés manquerait
notamment les portes d'égout, les arbres de Mesa et les fragments des murs.

Tous les canaux attachés sont inventoriés. Une liaison est un comportement
source potentiel, pas une preuve d'activation observée dans une partie.
Les comptes de l'outil sont des couples objet/mécanique, pas un nombre de
fonctionnalités indépendantes. La couverture `native_replacement`/`native_volume`
indique une liaison à l'import existant, pas une nouvelle validation en jeu.
Les sons, caméras, objectifs et scripts internes propres au moteur Tricky
ne constituent pas un audit exhaustif dans ce document.

Références : [lecteur SSF et énumérations SSX-Library](https://github.com/GlitcherOG/SSX-Library/blob/main/SSX-Library/FileHandlers/LevelFiles/Tricky/TrickyEnums.cs),
[résolution des volumes, téléporteurs et movers OpenSlope](https://github.com/swax/OpenSlope/blob/main/Snowknife/Snowknife/Bundle/ParticleBundle.cs),
[portes Showoff et `.SOP`](https://github.com/swax/OpenSlope/blob/main/Unity/docs/050-leaderboard.md).
Les noms, nombres et liens par map ci-dessus proviennent directement du disque
USA fourni ; les implémentations OpenSlope servent d'aide à l'interprétation.
