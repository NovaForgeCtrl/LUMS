# Tableau de bord de santé du système LUMS

## Objectif et portée

Le tableau de bord authentifié à l’adresse `/health` donne à l’opérateur un
aperçu rapide de certains états de LUMS et du parc :

- état de la base de données tel qu’évalué par l’application ;
- nombre total de clients et nombres de clients en ligne, inconnus et hors ligne ;
- télémétrie récente du processeur, de la mémoire et du réseau pour un client
  activé, lorsque la télémétrie est installée et que des échantillons existent ;
- télémétrie récente du processeur, de la mémoire et du réseau pour les clients
  activés, lorsque la télémétrie est installée et que des échantillons existent ;
- historique des alertes et interruptions de télémétrie détectées ;
- possibilité d’inspecter le répertoire de sauvegarde configuré, fichier de
  sauvegarde le plus récent reconnu par l’application et dernière sauvegarde
  créée avec succès selon le journal d’audit.
- lignes d’état facultatives des services systemd Wazuh et Suricata lorsqu’ils
  sont configurés.

Les mesures détaillées de l’hôte et du réseau par client, les températures,
les états des services et conteneurs ainsi que les résumés d’événements de
sécurité se trouvent sur la page distincte `/monitoring`. L’unité de
télémétrie dispose d’un accès en lecture seule au journal système pour résumer
les événements ; elle n’envoie pas les messages bruts du journal, les noms
d’utilisateur ni les adresses source. Les détails des conteneurs sont
indisponibles sauf si le compte de service de télémétrie peut inspecter
l’environnement d’exécution sans privilèges supplémentaires. Ces pages ne
prouvent pas que l’hôte, le démon Docker, le proxy inverse, le réseau ou chaque
client géré est en bon état. La présence d’une sauvegarde dans la liste ne
prouve pas qu’elle est restaurable ; effectuez périodiquement un test de
restauration contrôlé.

## Contrôle d’accès

La page `/health` exige un utilisateur connecté disposant de l’autorisation
`clients.view`. L’accès est soumis aux vérifications normales
d’authentification et d’autorisation de l’application. Ne rendez pas le tableau
de bord public en contournant la connexion ou les contrôles du proxy inverse.

Le point de terminaison distinct `GET /api/health` fournit une réponse légère
de disponibilité. Une réponse réussie signifie que la route peut répondre ;
elle ne constitue pas une évaluation complète de la base de données, des
sauvegardes ou de l’état des clients.

## Interprétation de l’état des clients

Le tableau de bord classe les clients d’après l’ancienneté de leur dernier
horodatage signalé :

| État | Ancienneté de l’horodatage |
| --- | --- |
| En ligne | 120 secondes ou moins |
| Inconnu | Plus de 120 secondes et jusqu’à 600 secondes, horodatage manquant/invalide ou horodatage futur |
| Hors ligne | Plus de 600 secondes |

Ces seuils décrivent la récence des rapports, et non le fait qu’une machine
soit allumée ou que tous ses services fonctionnent. Les retards réseau, les
machines en veille, un agent arrêté ou des défaillances de signalement peuvent
tous affecter le résultat. Considérez `unknown` comme une information
insuffisante plutôt que comme une preuve de défaillance.

## Télémétrie du processeur et de la mémoire

La télémétrie est facultative et distincte de l’Agent de rapport et du Watcher
d’exécution. Lorsque son minuteur systemd est activé et que le client peut
joindre le serveur, le service de télémétrie envoie un échantillon environ
toutes les cinq secondes.

Le tableau de bord propose des plages d’historique de 1 heure, 24 heures et
7 jours et actualise les données de télémétrie du parc toutes les cinq
secondes. Les détails de l’hôte sur `/monitoring` correspondent au dernier
instantané signalé ; la bande passante par interface est calculée à partir
d’instantanés consécutifs. Les requêtes d’historique sont limitées à 1–168
heures et peuvent être réduites à 1 000 points maximum. Les échantillons datant
de plus de sept jours sont supprimés lors du traitement de nouvelles
soumissions de télémétrie ; si toutes les soumissions cessent, ne supposez pas
que le nettoyage de conservation s’exécute indépendamment.

Chaque requête du journal sur la page de surveillance est limitée à
500 enregistrements correspondants ; un nombre affiché comme `500+` peut être
supérieur. L’historique des connexions/déconnexions est limité à 20 événements
et l’historique des démarrages à 10 entrées. Le tableau de bord de santé a une
mise en page fixe et utilise les seuils existants par utilisateur pour le
processeur/la RAM/le disque (90 % par défaut). Les dépassements de seuil et les
interruptions de télémétrie sont calculés à partir de l’historique des
échantillons conservés ; les changements d’état des services et les nouveaux
échecs SSH signalés sont consignés sous forme d’événements horodatés pendant
jusqu’à sept jours. Les exportations CSV/JSON fournissent tous les échantillons
de la plage sélectionnée ; les graphiques interactifs sont limités à
1 000 points.

Les lignes Wazuh et Suricata sont facultatives et signalent uniquement les
états des services systemd. Elles exigent que l’unité correspondante soit
incluse dans `LUMS_MONITORED_SERVICES` ; elles ne se connectent pas aux API
Wazuh ou Suricata et n’importent pas leurs alertes. L’horodatage d’exécution de
la sauvegarde provient du journal d’audit et ne constitue pas une vérification
indépendante de restauration.

La télémétrie exige l’authentification du client. Les connexions distantes de
l’agent exigent HTTPS ; le protocole HTTP non chiffré n’est accepté que pour
les adresses loopback. Configurez un fichier CA si le serveur utilise une
autorité de certification privée. Consultez [Télémétrie](telemetrie.md) et
[Installation et mises à niveau](Installation%20et%20mises%20à%20niveau.md)
pour les détails de configuration. [Documentation source en anglais](../../../LUMS_Health_Dashboard.md).

## État du stockage des sauvegardes

La section des sauvegardes indique ce que l’application peut inspecter dans le
répertoire de sauvegarde configuré et le fichier de sauvegarde le plus récent
qu’elle reconnaît. Elle ne vérifie pas indépendamment le contenu de chaque
sauvegarde, ne confirme pas la réplication hors hôte et ne prouve pas qu’une
restauration de la base de données réussira.

Une bonne routine opérationnelle consiste à :

1. vérifier que la date de sauvegarde affichée est assez récente pour votre
   objectif de récupération ;
2. examiner la tâche de sauvegarde et les journaux de l’application pour y
   repérer des erreurs ;
3. vérifier que la sauvegarde est copiée vers une destination protégée adaptée ;
4. tester périodiquement la restauration dans un emplacement distinct et
   contrôlé.

Ne supprimez et ne remplacez pas la base de données active ou les fichiers de
sauvegarde pour simplifier le dépannage.

## Vérifications recommandées en cas d’état suspect

1. Vérifiez le conteneur LUMS et les journaux récents.
2. Si la page ou l’API est inaccessible, vérifiez la configuration du proxy
   inverse et de TLS.
3. Pour un client marqué comme inconnu/hors ligne, inspectez les minuteurs de
   l’Agent de rapport et du Watcher ainsi que les entrées récentes du journal.
4. En cas d’absence de télémétrie, inspectez `lums-telemetry.timer`,
   `lums-telemetry.service` et la configuration du client/serveur.
5. En cas d’avertissement de sauvegarde, vérifiez le chemin configuré, les
   permissions du système de fichiers, l’espace disponible et les journaux de
   sauvegarde récents.
6. Notez l’état observé et les horodatages avant toute modification.

Consultez [Dépannage](Dépannage.md) pour les commandes de diagnostic et
[Administration et sauvegardes](Administration%20et%20sauvegardes.md) pour
les procédures d’entretien courant et de sauvegarde.
