# Topologie de l’infrastructure LUMS

## Objectif

La page authentifiée `/infrastructure` rassemble les clients LUMS enregistrés
et l’infrastructure tenue à jour manuellement dans une vue des dépendances.
Il s’agit d’un inventaire et d’une carte des relations, et non d’un système
automatique de découverte réseau ou de gestion de configuration.

## Sources de données et responsabilités

- Les clients LUMS enregistrés sont lus depuis le registre de clients existant
  et apparaissent automatiquement, avec leur nom d’hôte, adresse IP, système
  d’exploitation et état activé/de signalement. Les clients désactivés restent
  visibles afin que les relations existantes restent compréhensibles. Ces
  entrées sont en lecture seule sur la page de topologie ; gérez les clients
  via le processus normal de gestion des clients.
- Les serveurs, machines virtuelles, conteneurs, périphériques réseau,
  services et espaces de stockage peuvent être saisis manuellement avec un nom
  d’hôte, une adresse IP, un rôle, un emplacement et des notes.
- Les relations sont gérées manuellement. Les types pris en charge sont
  `depends on`, `hosts`, `connects to` et `runs on`.
- La page n’analyse pas les sous-réseaux, n’interroge pas les API cloud et ne
  déduit pas les dépendances à partir de la configuration des services ou des
  conteneurs. Maintenez à jour l’inventaire et les relations saisis
  manuellement.

## Contrôle d’accès et audit

Les utilisateurs disposant de `clients.view` peuvent consulter la topologie.
La création, la modification et la suppression d’entrées ou de relations
manuelles sont réservées aux administrateurs disposant de l’autorisation
`infrastructure.manage`. L’application exige une session authentifiée normale,
une protection CSRF et une journalisation d’audit pour les modifications.

`infrastructure.manage` dépend de `users.manage` et `clients.view` et est
accordée aux administrateurs par la migration de base de données
`016-infrastructure-topology`. La suppression d’un nœud géré manuellement
supprime également ses enregistrements de relations. La suppression d’un
client supprime les relations qui le référencent.

## Lecture de la carte

La carte organise les nœuds par catégorie et dessine une arête directionnelle
pour chaque relation enregistrée. Une **dépendance partagée** est un nœud vers
lequel pointent au moins deux autres nœuds via `depends on`. Il s’agit d’un
indice utile pour repérer un éventuel point central de défaillance, et non
d’une analyse complète de disponibilité ou d’impact. La carte ne tient pas
compte de la redondance, du basculement, de la capacité, de la segmentation
réseau ni des dépendances non enregistrées.

Utilisez les tableaux d’inventaire et de relations pour connaître précisément
les noms d’hôte, adresses IP, rôles, emplacements et détails des relations. La
topologie utilise le thème LUMS actuellement sélectionné et fonctionne avec la
barre latérale rétractable partagée. [Documentation source en anglais](../../../LUMS_Infrastructure_Topology.md).
