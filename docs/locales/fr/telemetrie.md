# Télémétrie CPU, mémoire et réseau de LUMS

## Présentation

L’agent de télémétrie facultatif de LUMS collecte l’utilisation du processeur,
de la mémoire, les compteurs réseau et un instantané limité d’un hôte Linux
géré, puis transmet les mesures au serveur LUMS.

Le serveur stocke les échantillons de télémétrie et expose une API d’historique
authentifiée utilisée par le tableau de bord de télémétrie du client.

La télémétrie est distincte de l’Agent de rapport et du Watcher LUMS existants.
Elle ne remplace aucun de ces composants et n’effectue pas de mises à jour de
paquets.

## Composants

| Composant | Responsabilité |
| --- | --- |
| `agent/telemetry.py` | Collecte les métriques du processeur, de la mémoire, de l’hôte, du réseau, des capteurs, des services et des conteneurs |
| `agent/lums-telemetry.service` | Exécute l’agent de télémétrie en tant que service systemd restreint |
| `agent/lums-telemetry.timer` | Planifie les collectes récurrentes de télémétrie |
| `server/app.py` | Authentifie les soumissions, valide les métriques et stocke les échantillons |
| `server/static/telemetry.js` | Affiche la vue d’ensemble du parc, les graphiques d’historique et les jauges circulaires |

## Mesures

Chaque échantillon contient les champs obligatoires suivants :

- `cpu_percent` : utilisation du processeur de 0 à 100.
- `memory_percent` : utilisation de la mémoire de 0 à 100.
- `memory_total_bytes` : mémoire totale détectée, en octets.
- `memory_available_bytes` : mémoire disponible, en octets.

La version 1.1.0 de l’agent et les versions ultérieures envoient également deux
compteurs cumulatifs facultatifs :

- `network_rx_bytes` : octets reçus depuis le démarrage, cumulés sur toutes les
  interfaces autres que loopback.
- `network_tx_bytes` : octets envoyés depuis le démarrage, cumulés sur toutes
  les interfaces autres que loopback.

Les deux compteurs doivent être envoyés ensemble sous forme d’entiers positifs
ou nuls. Les anciennes versions de l’agent qui les omettent continuent de
fonctionner ; le tableau de bord n’affiche alors aucune donnée réseau pour ce
client. Le serveur stocke les compteurs bruts et calcule les octets par seconde
à partir d’échantillons consécutifs lors de la consultation des données. Aucun
débit n’est affiché pour le premier échantillon, après la réinitialisation d’un
compteur (par exemple, lors d’un redémarrage) ou si l’intervalle entre deux
échantillons dépasse cinq minutes.

La version 1.2.0 de l’agent et les versions ultérieures signalent également un
instantané système limité :

- charge moyenne, durée de fonctionnement, système d’exploitation, noyau et
  utilisation du système de fichiers racine ;
- état de liaison, compteurs d’octets, erreurs et paquets abandonnés pour
  chaque interface réseau ;
- serveurs DNS configurés et vérifications au mieux de l’accessibilité de la
  passerelle, du DNS et d’Internet ;
- mesures thermiques et de ventilateur lorsque le noyau les expose ;
- états et durées d’exécution de certains services systemd, compteurs de
  redémarrages, ainsi que noms et états normalisés des conteneurs Docker et
  Podman lorsque les outils locaux et les autorisations permettent une
  inspection en lecture seule ;
- pourcentage d’utilisation du disque à chaque échantillon de télémétrie, pour
  les graphiques historiques et l’évaluation des événements de seuil.

La version 1.3.0 de l’agent et les versions ultérieures signalent également
des résumés limités des événements opérationnels : nombre et horodatage des
échecs de connexion SSH, nombre récent d’avertissements et d’erreurs du
journal, horodatages des connexions et déconnexions, ainsi que premiers et
derniers horodatages du journal pour les démarrages récents. Les messages bruts
du journal, les noms d’utilisateur et les adresses source ne sont pas envoyés.
Chaque requête du journal est limitée à 500 enregistrements correspondants ;
le tableau de bord affiche `500+` lorsque le nombre atteint 500. L’historique
des démarrages est limité à 10 et celui des connexions/déconnexions à 20
événements.

Le serveur calcule le débit de chaque interface à partir d’échantillons
consécutifs. Les détails des services, conteneurs, températures, ventilateurs
et événements sont stockés uniquement dans l’instantané le plus récent et ne
sont pas dupliqués dans chaque échantillon historique. Les métriques
facultatives que le système d’exploitation n’expose pas ou dont il n’autorise
pas la consultation sont indiquées comme indisponibles. L’agent ne démarre,
n’arrête ni ne modifie aucun service ou conteneur. Le service de l’agent n’a
pas accès au socket Docker ; les détails des conteneurs restent indisponibles,
sauf si l’environnement d’exécution autorise déjà le compte de service à les
inspecter.

L’unité systemd de télémétrie appartient au groupe `systemd-journal` afin
d’obtenir un accès en lecture seule au journal. Cela donne accès aux journaux
système, mais l’agent n’envoie que les résumés limités décrits ci-dessus. La
liste d’autorisation des services par défaut comprend les unités LUMS, Docker
et SSH. Remplacez-la par une valeur séparée par des virgules pour
`LUMS_MONITORED_SERVICES` dans le fichier d’environnement de l’agent ; seuls
les noms d’unités `.service` valides sont acceptés.

L’accessibilité de la passerelle est vérifiée par un seul ping lorsqu’il est
disponible, celle du DNS par une courte requête `getent`, et celle d’Internet
par une brève tentative de connexion TCP vers `1.1.1.1:443`. Ces vérifications
ne sont que des indicateurs et peuvent refléter la politique du pare-feu
plutôt qu’une panne.

Le serveur attribue l’horodatage de l’échantillon et rejette les charges utiles
non valides.

Après la mise à jour du serveur, exécutez une fois la migration de la base de
données (`python3 server/security_migration.py`) afin de créer les colonnes
réseau, la table du dernier état système et l’historique des événements.
Mettez à jour l’agent sur chaque client pour qu’il commence à signaler les
nouvelles métriques. Pour surveiller le serveur LUMS lui-même, enregistrez-le
comme client et installez/configurez également l’agent de télémétrie sur cet
hôte.

## Sécurité et confidentialité

Le point de terminaison de télémétrie exige l’authentification du client à
l’aide du jeton client LUMS configuré.

L’agent envoie ses requêtes en HTTPS lorsqu’il se connecte à un serveur distant.
Le protocole HTTP non chiffré est autorisé uniquement pour `localhost`,
`127.0.0.1` et `::1`. Les connexions aux serveurs distants exigent HTTPS. Un
fichier CA facultatif peut être configuré pour la vérification des certificats.

L’agent n’inclut pas le jeton client dans la charge JSON et ne le consigne pas.
Le service systemd utilise un environnement d’exécution restreint et n’a pas
besoin des privilèges root pour collecter les métriques documentées.

La télémétrie contient des ressources système et des métadonnées
opérationnelles, mais ni mises à jour de paquets ni sorties arbitraires de
commandes. Les adresses d’interfaces, les serveurs DNS, les noms de services
et les noms de conteneurs peuvent révéler des détails sensibles de
l’infrastructure ; l’accès au tableau de bord et à l’API reste protégé par
l’autorisation `clients.view`.

## Conservation des données

Le serveur supprime les échantillons de télémétrie datant de plus de sept jours
lors du traitement de nouvelles soumissions de télémétrie.

Le point de terminaison d’historique authentifié accepte une plage de 1 à 168
heures. L’accès exige l’autorisation appropriée de consultation des clients.
Les grands ensembles de résultats peuvent être réduits à 1 000 échantillons
maximum.

Le tableau de bord `/health` propose des plages d’historique de 1 heure,
24 heures et 7 jours, et actualise les données affichées toutes les cinq
secondes. Il affiche l’historique du processeur, de la mémoire, du disque et du
réseau agrégé, ainsi que les détails en direct du disque, de la charge, de la
durée de fonctionnement, du noyau, du système d’exploitation, des interfaces,
de la connectivité, des capteurs, des services et des conteneurs pour le client
sélectionné. Il présente aussi une vue d’ensemble du parc filtrable par état,
télémétrie obsolète ou charge élevée, consultable et triable, ainsi que les
détails de chaque client. Le processeur et la mémoire peuvent s’afficher sous
forme de graphique linéaire, de graphique en aires ou de jauge circulaire
indiquant la valeur actuelle ; la vue choisie est mémorisée dans le navigateur.
Le trafic réseau est présenté sous forme de débits de téléchargement et
d’envoi. Les données de télémétrie datant de plus de deux minutes sont
signalées comme obsolètes. La vue d’ensemble du parc utilise le point de
terminaison `/api/telemetry/overview`, qui exige l’autorisation de consultation
des clients. Les requêtes d’historique sont limitées à 1–168 heures et peuvent
être réduites à 1 000 échantillons maximum. Le minuteur systemd est configuré
pour lancer l’agent ponctuel toutes les cinq secondes ; la fréquence réelle
des échantillons dépend de la durée d’exécution du service et de la
disponibilité du réseau. Le tableau de bord affiche également les échecs SSH
récents, les nombres d’avertissements et d’erreurs du journal, ainsi que
l’historique des connexions/déconnexions et des démarrages. Les alertes de
seuil utilisent les limites configurables du processeur, de la RAM et du
disque de l’utilisateur connecté. Chaque requête du journal porte sur
500 enregistrements correspondants au maximum. La date de la dernière
sauvegarde créée avec succès provient du journal d’audit du serveur ; elle ne
constitue pas un test de restauration.

Les dépassements de seuil et les interruptions de télémétrie de plus de deux
minutes apparaissent dans l’historique des événements. Les alertes de seuil
sont calculées à partir des échantillons conservés et des seuils de
l’utilisateur connecté ; les changements d’état des services et les nouveaux
horodatages d’échecs SSH sont consignés lors de l’ingestion. Les événements
sont conservés jusqu’à sept jours et le point de terminaison des événements
renvoie 500 entrées maximum.

Des exportations CSV et JSON sont disponibles pour le client et la plage
sélectionnés. Les téléchargements d’historique comprennent tous les
échantillons conservés pour cette plage ; les graphiques restent limités à
1 000 points maximum. Les exportations exigent `clients.view` et ne sont pas
mises en cache par le navigateur.

Wazuh et Suricata peuvent être activés comme lignes d’état facultatives dans le
tableau de bord. Ces lignes affichent uniquement l’état du service systemd
configuré ; LUMS ne se connecte pas à leurs API et ne collecte pas leurs
alertes. Pour signaler un service, ajoutez son unité installée (par exemple
`wazuh-agent.service`, `wazuh-manager.service` ou `suricata.service`) à la
liste d’autorisation `LUMS_MONITORED_SERVICES` de l’agent. Aucune information
d’identification d’intégration n’est requise ni stockée par LUMS.

## Configuration

L’agent de télémétrie utilise les variables d’environnement `LUMS_BASE`,
`LUMS_TOKEN` et, facultativement, `LUMS_CA_FILE`. Les connexions aux serveurs
distants exigent HTTPS. Consultez [Installation et mises à niveau](Installation%20et%20mises%20à%20niveau.md)
pour les instructions d’installation et de configuration.
[Documentation source en anglais](../../../telemetry.md).

## Installation et fonctionnement

Le service de télémétrie est distinct du client LUMS habituel. Sous Debian,
mettez d’abord à jour la copie du dépôt LUMS sur le client, puis exécutez
`sudo bash scripts/install-telemetry-agent.sh` depuis sa racine. Le programme
d’installation vérifie que `/etc/default/lums-agent` définit `LUMS_BASE` et
`LUMS_TOKEN`, installe le collecteur et les unités systemd actuels, active le
minuteur et envoie un échantillon de test. Il n’affiche jamais le jeton.

Inspectez le minuteur et le service avec `systemctl status lums-telemetry.timer`
et `systemctl status lums-telemetry.service`. Consultez les journaux récents du
service avec `journalctl -u lums-telemetry.service -n 30 --no-pager`. Un
service ponctuel inactif entre deux exécutions planifiées n’indique pas
nécessairement une erreur ; vérifiez également le minuteur et les journaux
récents.

La page `/monitoring` distingue l’absence d’échantillons, la télémétrie de base
sans instantanés détaillés et un instantané obsolète, et affiche ces
vérifications côté client. Ne collez pas et ne partagez pas le jeton lors du
dépannage.

## Dépannage

- **Aucun échantillon n’apparaît :** vérifiez l’URL du serveur, le jeton client
  et l’authentification.
- **Erreurs TLS :** vérifiez le certificat du serveur et le fichier CA configuré.
- **Défaillances du service :** consultez le journal du service.
- **Historique manquant :** vérifiez l’autorisation de consultation des clients
  et la plage demandée (1–168 heures).

Pour connaître les seuils d’état du tableau de bord et les limites de son
indicateur de stockage des sauvegardes, consultez le [Tableau de bord de santé
du système](tableau-de-bord-sante.md). Pour des conseils généraux, consultez
[Installation et mises à niveau](Installation%20et%20mises%20à%20niveau.md) et
[Dépannage](Dépannage.md).
