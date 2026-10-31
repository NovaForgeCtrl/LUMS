# Documentation de sécurité LUMS

**LUMS — Linux Update Management Server**

Ce document décrit l'architecture de sécurité actuelle, les contrôles de sécurité implémentés, les résultats de l'audit de sécurité, les limitations opérationnelles et les décisions de conception liées à la sécurité de LUMS.

Le document reflète l'**état actuel du système implémenté**. Les améliorations prévues ou futures sont explicitement identifiées comme telles.

---

# Principes de sécurité

LUMS suit une approche de défense en profondeur pour la gestion des mises à jour Linux.

Le modèle de sécurité sépare l'authentification administrative, l'authentification des clients, l'autorisation, l'exécution contrôlée des mises à jour et la journalisation d'audit.

Les objectifs de sécurité principaux sont :

* accès administratif authentifié
* autorisation basée sur les rôles
* communication client authentifiée
* exécution contrôlée des mises à jour
* protection contre l'exécution concurrente de jobs
* jobs de mise à jour récupérables
* secrets protégés
* exécution contrôlée du conteneur
* opérations sensibles à la sécurité auditables
* gestion prévisible des échecs
* tests de régression de sécurité

LUMS est principalement destiné aux environnements d'infrastructure contrôlée, de laboratoire et de réseau interne.

Il ne doit pas être exposé directement à l'Internet public sans une revue de sécurité supplémentaire et des contrôles réseau appropriés.

---

# Architecture de sécurité

LUMS se compose des composants pertinents pour la sécurité suivants :

* Interface d'administration web
* API REST
* Base de données SQLite
* Agent LUMS sur les clients gérés
* Backends de gestion de paquets APT et pacman
* Mécanismes de job de mise à jour et de récupération
* Proxy inverse HTTPS Nginx
* Conteneur Docker durci

Le flux de gestion de base est :

Navigateur → HTTPS/Nginx → LUMS API → SQLite → Agent LUMS → Gestionnaire de paquets → Résultat → SQLite → UI Web

L'authentification et l'autorisation sont délibérément séparées.

Une session authentifiée valide n'accorde pas automatiquement l'accès à toutes les opérations administratives.

L'autorisation est appliquée côté serveur. L'interface web masque en outre les fonctions qui ne sont pas disponibles pour le rôle actuel, mais la visibilité de l'UI n'est jamais traitée comme une frontière de sécurité.

---

## Authentification administrative

Les utilisateurs administratifs s'authentifient via l'interface web LUMS.

Les mots de passe ne sont jamais stockés en clair. LUMS utilise le hachage de mot de passe basé sur Argon2 pour le stockage des mots de passe.

Les sessions administratives utilisent :

* gestion de session authentifiée côté serveur
* expiration de session
* régénération de session
* protection CSRF pour les requêtes de navigateur modifiant l'état
* limitation du taux de connexion
* invalidation de session lors de la déconnexion
* validation de rôle côté serveur

L'authentification et l'autorisation restent des contrôles de sécurité distincts.

Un utilisateur authentifié avec succès doit toujours posséder la permission requise pour les opérations protégées.

---

# Contrôle d'accès basé sur les rôles

LUMS prend actuellement en charge trois rôles d'utilisateur web :

* `administrator`
* `operator`
* `viewer`

Les modèles de rôles sont stockés dans `users.role` ; les permissions individuelles sont stockées côté serveur dans `user_permissions`.

Le serveur charge les permissions effectives pour chaque compte authentifié. Les informations de permission côté client contrôlent uniquement la présentation et ne remplacent jamais l'autorisation côté serveur.

## Administrator

Les administrateurs disposent d'un accès administratif et opérationnel complet.

Ils peuvent :

* afficher les clients
* créer des clients
* désactiver des clients
* faire tourner les tokens clients
* afficher les paquets installés et les mises à jour disponibles
* créer des jobs de mise à jour
* exécuter les opérations de mise à jour prises en charge
* consulter l'historique des jobs de mise à jour
* utiliser la gestion des paquets
* utiliser les fonctions de maintenance système
* gérer les utilisateurs
* gérer les rôles utilisateur
* accéder aux fonctions administratives

## Operator

Les opérateurs peuvent effectuer des tâches opérationnelles de gestion des mises à jour.

Ils peuvent :

* afficher les clients
* afficher les paquets installés et les mises à jour disponibles
* créer des jobs de mise à jour
* exécuter les opérations de mise à jour prises en charge
* consulter l'historique des jobs de mise à jour
* utiliser la gestion des paquets
* utiliser les fonctions de maintenance système

Les opérateurs ne peuvent pas :

* gérer les utilisateurs
* modifier les rôles utilisateur
* créer des clients
* désactiver des clients
* faire tourner les tokens clients

## Viewer

Les Viewers disposent d'un accès en lecture seule restreint.

Ils peuvent :

* afficher les clients
* afficher les logiciels installés

Les domaines de gestion suivants sont masqués pour les comptes Viewer :

* Mises à jour
* Jobs de mise à jour
* Historique des mises à jour
* Gestion des paquets
* Maintenance système

Les comptes Viewer ne peuvent pas effectuer d'opérations de gestion des mises à jour modifiant l'état.

Le serveur applique ces restrictions indépendamment via l'authentification et les vérifications de permissions par utilisateur.

---

# Authentification des clients

Chaque client LUMS géré utilise un token Bearer individuel.

Le mécanisme d'authentification suit le modèle :

`Authorization: Bearer <CLIENT_TOKEN>`

Le serveur ne stocke pas les tokens clients en tant que valeurs en clair.

Au lieu de cela, LUMS stocke un condensé hexadécimal SHA-256 du token client.

Le flux d'authentification est :

Token client → SHA-256 → Condensé du token → SQLite

L'authentification client vérifie le token authentifié par rapport au client enregistré et vérifie en outre l'état pertinent du client.

Le modèle de sécurité n'utilise pas l'adresse IP source comme seule preuve de l'identité du client.

Cela permet à LUMS de fonctionner dans :

* réseaux de laboratoire privés
* infrastructure isolée
* réseaux basés sur NAT
* environnements hors ligne
* réseaux où les adresses clients peuvent changer

Les tokens clients peuvent être rotés par des administrateurs autorisés.

Une rotation de token génère un token de remplacement, stocke uniquement son condensé, invalide le token précédent, enregistre l'action administrative dans le journal d'audit et présente le token de remplacement une seule fois.

Les valeurs de token client en clair ne sont pas écrites dans les enregistrements d'audit.

---

# Audit de sécurité

L'audit de sécurité est effectué de manière incrémentielle.

Chaque domaine d'audit est examiné par rapport à l'implémentation réelle, suivi de tests automatisés, de vérifications isolées ou de vérifications de production le cas échéant.

Domaines d'audit actuels :

| Audit | Domaine                                | Statut                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | Clés étrangères SQLite                 | RÉUSSI                    |
| #02   | Configuration d'exécution SQLite       | RÉUSSI                    |
| #03   | Gestion des délais de mise à jour      | RÉUSSI                    |
| #04   | Limitation du taux de connexion        | RÉUSSI                    |
| #05   | Validation des entrées de l'API        | RÉUSSI                    |
| #06   | Révocation de session                  | RÉUSSI                    |
| #07   | Rotation des tokens clients            | RÉUSSI                    |
| #08   | Gestion des adresses IP / Réseaux hors ligne | RÉUSSI              |
| #09   | Récupération de job / Checkpointing    | RÉUSSI                    |
| #10   | Robustesse APT                         | RÉUSSI                    |
| #11   | Détection de redémarrage Arch          | RÉUSSI                    |
| #12   | Tests unitaires / Validation des résultats de l'API | RÉUSSI    |
| #13   | Tests de simulation                    | RÉUSSI                    |
| #14   | Intégration continue                   | RÉUSSI                    |
| #15   | Journalisation applicative / d'audit   | RÉUSSI                    |
| #16   | Versionnement / Releases               | Vérifier les releases et tags actuels du dépôt |
| #17   | Contrôle d'accès basé sur les rôles    | RÉUSSI                    |

Ce tableau récapitule le périmètre et les résultats des vérifications antérieures ; il ne constitue ni une certification ni une garantie pour les révisions ultérieures. Relancez les contrôles pertinents sur le code exact à déployer. La disponibilité des releases évolue ; ne déduisez donc pas leur état de ce document, mais consultez la [page Releases](https://github.com/NovaForgeCtrl/LUMS/releases) et les [tags](https://github.com/NovaForgeCtrl/LUMS/tags) du dépôt.

# Audit de sécurité #01

## Clés étrangères SQLite

L'application des clés étrangères SQLite est activée pour les connexions à la base de données applicative.

L'application active explicitement :

`PRAGMA foreign_keys = ON`

Cela garantit que l'intégrité référentielle est appliquée pour les relations entre les enregistrements de base de données liés.

L'audit a vérifié :

* l'application des clés étrangères à l'exécution
* l'intégrité des clés étrangères
* le comportement du cycle de vie des clients
* le comportement de désactivation des clients
* la préservation des informations historiques des jobs
* la préservation des informations d'audit

L'état client est géré de manière conservatrice.

Le cas échéant, les clients sont désactivés plutôt que supprimés d'une manière qui détruirait les informations opérationnelles historiques.

**Statut : RÉUSSI**

---

# Audit de sécurité #02

## Configuration d'exécution SQLite

La base de données SQLite de production a été examinée pour sa configuration d'exécution.

La configuration de production vérifiée est :

* `journal_mode` : `wal`
* `busy_timeout` : `5000`
* `synchronous` : `2`

L'application active explicitement :

`PRAGMA foreign_keys = ON`

La base de données de production utilise actuellement le mode WAL.

La configuration de la base de données a été documentée sur la base de l'état de production réellement vérifié plutôt que de la configuration de développement historique.

Le busy timeout configuré réduit les échecs immédiats de base de données lorsqu'une autre transaction détient temporairement la base de données.

Le paramètre de clé étrangère au niveau de l'application garantit l'intégrité référentielle pour chaque connexion à la base de données.

L'audit comprenait la vérification en production de la configuration SQLite active.

**Statut : RÉUSSI**

---

# Audit de sécurité #03

## Délai de mise à jour et gestion des processus

L'exécution des mises à jour est protégée contre les processus de gestionnaire de paquets bloquants indéfiniment.

Le flux d'exécution est :

Démarrer le processus
↓
Lire la sortie du processus
↓
Surveiller le délai
↓
Délai atteint ?
↓
Terminer le processus
↓
Période de grâce
↓
Le processus est-il toujours en cours ?
↓
Tuer le processus si nécessaire
↓
Terminer le job

L'implémentation utilise une gestion contrôlée des sous-processus afin que les processus silencieux ne puissent pas bloquer indéfiniment en attendant une sortie.

La gestion des délais a été testée contre :

* processus silencieux
* achèvement normal du processus
* conditions de délai
* processus résistants à la terminaison normale
* fallback de kill
* comportement de délai au niveau de l'intégration

Le mécanisme de délai empêche une opération de gestion des paquets de rester indéfiniment dans un état actif.

Les erreurs et conditions de délai sont renvoyées sous forme de résultats de job contrôlés et sont enregistrées dans l'état du job.

La version actuelle documentée de l'agent LUMS est :

`1.7.0`

**Statut : RÉUSSI**

---

# Audit de sécurité #04

## Limitation du taux de connexion

Les tentatives de connexion administrative sont limitées en débit.

La politique d'escalade actuelle est :

* 5 tentatives échouées → 30 secondes
* 6 tentatives échouées → 60 secondes
* 7 tentatives échouées → 120 secondes
* 8 tentatives échouées ou plus → 300 secondes

L'état de limitation du taux est persisté dans SQLite.

Les échecs de connexion concurrents utilisent un verrouillage transactionnel de base de données avec :

`BEGIN IMMEDIATE`

Cela empêche les échecs d'authentification concurrents de contourner l'état de limitation du taux prévu par des conditions de course.

Une authentification réussie efface l'état d'échec applicable.

L'audit a couvert :

* comportement isolé de limitation du taux
* échecs d'authentification concurrents
* rollback de transaction
* gestion du verrou de base de données
* comportement de réinitialisation après connexion réussie
* événements d'audit de limitation du taux
* comportement de connexion en production

Le limiteur de taux fournit donc un contrôle côté serveur contre les tentatives d'authentification répétées plutôt que de s'appuyer sur le comportement côté client.

**Statut : RÉUSSI**

---

# Statut de l'audit après la partie 2

Les quatre premiers domaines d'audit de sécurité sont terminés :

| Audit | Domaine                              | Statut |
| ----- | ------------------------------------ | ------ |
| #01   | Clés étrangères SQLite               | RÉUSSI |
| #02   | Configuration d'exécution SQLite     | RÉUSSI |
| #03   | Délai de mise à jour / Gestion des processus | RÉUSSI |
| #04   | Limitation du taux de connexion      | RÉUSSI |

Les domaines d'audit suivants sont documentés dans les sections suivantes :

* #05 Validation des entrées de l'API
* #06 Révocation de session
* #07 Rotation des tokens clients
* #08 Gestion des adresses IP / Réseaux hors ligne
* #09 Récupération de job / Checkpointing
* #10 Robustesse APT
* #11 Détection de redémarrage Arch
* #12 Tests unitaires / Validation des résultats de l'API
* #13 Tests de simulation
* #14 Intégration continue
* #15 Journalisation applicative / d'audit
* #16 Versionnement / Releases
* #17 Contrôle d'accès basé sur les rôles

Examinez la documentation au regard de l'implémentation lorsque le code ou le comportement du déploiement change. Elle doit décrire le système réel, et non un état de développement antérieur. Traitez cette revue comme une tâche de maintenance continue, et non comme un état d'audit ponctuel.

# Audit de sécurité #05

## Validation des entrées de l'API

LUMS valide les entrées sensibles à la sécurité de l'API côté serveur.

Les valeurs fournies par le client ne sont pas approuvées simplement parce qu'elles proviennent de l'interface web authentifiée ou d'un client enregistré.

La validation est appliquée aux paramètres d'API pertinents, notamment :

* identifiants clients
* noms de paquets
* actions de job de mise à jour
* listes de paquets
* paramètres de recherche
* paramètres de gestion des utilisateurs
* opérations sur les tokens clients
* données de résultat de job

Les noms de paquets sont validés avant d'être transmis aux opérations de gestion des paquets.

L'API de job de mise à jour n'accepte que les actions explicitement prises en charge.

Les actions liées aux paquets actuellement prises en charge sont :

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Les actions inattendues sont rejetées.

Les listes de paquets sont validées avant la création du job.

Pour `UPDATE_PACKAGE`, le paquet demandé doit également être présent dans les informations de mise à jour disponibles du client.

Les requêtes de base de données utilisent du SQL paramétré plutôt que de construire des instructions SQL à partir d'entrées non fiables.

Cela empêche les valeurs contrôlées par l'utilisateur d'être interprétées comme de la syntaxe SQL.

L'audit comprenait des tests d'entrée négatifs et des cas de test orientés injection SQL.

Les contrôles de validation ont également été vérifiés via la suite de tests automatisés.

**Statut : RÉUSSI**

---

# Audit de sécurité #06

## Révocation de session

LUMS protège les sessions administratives authentifiées contre la poursuite de l'utilisation après la déconnexion.

La gestion des sessions comprend :

* sessions authentifiées côté serveur
* expiration de session
* régénération de session
* invalidation lors de la déconnexion
* vérifications d'authentification côté serveur
* validation de rôle côté serveur

La déconnexion invalide la session authentifiée active.

Les points de terminaison d'API protégés nécessitent une session authentifiée et ne s'appuient pas sur l'état côté client pour déterminer si l'utilisateur reste authentifié.

L'état de session est donc évalué par le serveur pour les opérations protégées.

Les requêtes de navigateur modifiant l'état nécessitent en outre une protection CSRF.

L'audit a vérifié que :

* l'accès authentifié fonctionne normalement
* les points de terminaison protégés rejettent les requêtes non authentifiées
* la déconnexion invalide la session active
* une session précédemment authentifiée ne peut pas continuer à utiliser la fonctionnalité protégée après révocation
* les informations de rôle sont évaluées côté serveur

**Statut : RÉUSSI**

---

# Audit de sécurité #07

## Rotation des tokens clients

Chaque client LUMS géré utilise un token d'authentification individuel.

Les tokens clients ne sont pas stockés en tant que valeurs en clair.

Au lieu de cela, LUMS stocke le condensé hexadécimal SHA-256 du token client.

Le modèle d'authentification est :

`Authorization: Bearer <CLIENT_TOKEN>`

Le serveur hache le token fourni et compare le condensé résultant avec le condensé du token client enregistré.

Les administrateurs autorisés peuvent faire tourner le token d'un client.

La rotation de token effectue les opérations suivantes :

1. Générer un token de remplacement.
2. Calculer son condensé SHA-256.
3. Remplacer le condensé du token client stocké.
4. Invalider le token précédent.
5. Enregistrer l'action administrative dans le journal d'audit.
6. Présenter le token de remplacement à l'administrateur.

Le token précédent ne peut plus s'authentifier après la rotation.

Les valeurs de token en clair ne sont pas écrites dans les journaux d'audit.

L'audit a vérifié :

* authentification réussie par token
* stockage du condensé du token
* rotation du token
* invalidation du token précédent
* authentification avec le token de remplacement
* exigences d'autorisation pour la rotation de token
* journalisation d'audit
* protection contre la rotation non autorisée

La rotation des tokens clients est réservée aux administrateurs.

Les opérateurs et les viewers ne peuvent pas faire tourner les tokens clients.

**Statut : RÉUSSI**

---

# Audit de sécurité #08

## Gestion des adresses IP et réseaux hors ligne

LUMS n'utilise pas l'adresse IP source d'un client comme seule preuve de l'identité du client.

L'authentification client est basée sur le token client enregistré.

Cette conception est intentionnelle car les clients gérés peuvent fonctionner dans des environnements où leur adresse réseau change.

Les scénarios de déploiement pris en charge comprennent :

* réseaux de laboratoire privés
* réseaux basés sur NAT
* infrastructure isolée
* clients à adressage dynamique
* environnements hors ligne
* réseaux internes contrôlés

Le serveur sépare donc :

**Emplacement réseau**

de :

**Identité client**

Un token client valide identifie le client enregistré.

L'adresse réseau du client peut toujours être enregistrée à des fins opérationnelles et d'audit, mais elle n'est pas traitée comme un identifiant d'authentification.

L'implémentation évite également les suppositions selon lesquelles un client doit être joignable depuis une adresse fixe.

Ceci est particulièrement important pour les environnements de laboratoire et l'infrastructure où la topologie réseau peut changer sans modifier l'identité logique du système géré.

L'audit a vérifié l'authentification client sans s'appuyer sur une adresse IP source fixe.

**Statut : RÉUSSI**

---

# Statut de l'audit après la partie 3

Les domaines d'audit de sécurité suivants sont terminés :

| Audit | Domaine                                | Statut |
| ----- | -------------------------------------- | ------ |
| #01   | Clés étrangères SQLite                 | RÉUSSI |
| #02   | Configuration d'exécution SQLite       | RÉUSSI |
| #03   | Délai de mise à jour / Gestion des processus | RÉUSSI |
| #04   | Limitation du taux de connexion        | RÉUSSI |
| #05   | Validation des entrées de l'API        | RÉUSSI |
| #06   | Révocation de session                  | RÉUSSI |
| #07   | Rotation des tokens clients            | RÉUSSI |
| #08   | Gestion des adresses IP / Réseaux hors ligne | RÉUSSI |

La section suivante couvre :

* #09 Récupération de job / Checkpointing
* #10 Robustesse APT
* #11 Détection de redémarrage Arch
* #12 Tests unitaires / Validation des résultats de l'API

# Audit de sécurité #09

## Récupération de job et Checkpointing

Les jobs de mise à jour LUMS sont conçus pour récupérer en toute sécurité après une exécution interrompue.

Les jobs de mise à jour maintiennent un état persistant dans la base de données SQLite.

Les opérations individuelles sur les paquets sont suivies séparément de l'état global du job.

Cela permet à l'agent de déterminer quelles opérations sur les paquets ont déjà été terminées avec succès avant qu'un job interrompu ne soit repris.

Lors de la récupération, les opérations sur les paquets terminées avec succès ne sont pas exécutées à nouveau.

La logique de récupération suit donc le principe :

`État persistant du job → Déterminer le travail terminé → Ignorer les éléments terminés → Continuer le travail restant`

Cela réduit le risque d'opérations répétées inutiles sur les paquets après :

* interruption de l'agent
* terminaison du processus
* redémarrage du système
* échec de communication temporaire
* redémarrage du conteneur
* autres interruptions d'exécution

L'audit a vérifié le comportement de récupération et de checkpointing des jobs interrompus.

La récupération a été testée avec des jobs contenant plusieurs opérations sur des paquets et avec des éléments de paquets précédemment réussis.

L'audit a confirmé que le travail terminé est préservé et que le travail restant peut continuer sans répéter inutilement les opérations réussies.

**Statut : RÉUSSI**

---

# Audit de sécurité #10

## Robustesse APT

Les opérations sur les paquets basées sur Debian sont exécutées via la couche de gestion des paquets LUMS.

Les opérations de mise à jour liées à APT ont été examinées pour une détection fiable de l'état du gestionnaire de paquets et des résultats de mise à jour.

L'implémentation tient compte des cas où les commandes de gestion des paquets peuvent retourner avec succès tout en nécessitant une interprétation supplémentaire de leur sortie ou de l'état système résultant.

La détection des mises à jour APT a été durcie pour éviter de s'appuyer sur une seule condition simpliste de sortie de commande.

L'audit comprenait des tests de :

* opérations APT normales
* mises à jour de paquets disponibles
* installation de paquets
* suppression de paquets
* exécution de job de mise à jour
* gestion des résultats APT
* comportement de détection des mises à jour

Le durcissement correspondant a été validé comme :

`c76f331 security: harden apt update detection`

L'objectif est de garantir que LUMS ne signale pas incorrectement l'état de gestion des paquets sur la seule base d'une sortie de commande incomplète ou ambiguë.

**Statut : RÉUSSI**

---

# Audit de sécurité #11

## Détection de redémarrage Arch Linux

Les opérations sur les paquets Arch Linux peuvent entraîner un état système où un redémarrage est requis ou recommandé.

LUMS évalue donc l'état système résultant après les opérations pertinentes de gestion des paquets.

L'agent distingue l'achèvement normal d'une opération sur les paquets des situations où un redémarrage est requis.

L'état de redémarrage est rapporté au serveur LUMS dans le cadre du résultat du job.

Cela permet à l'interface de gestion de distinguer entre :

* opération sur les paquets réussie
* opération réussie avec exigence de redémarrage
* opération échouée

L'audit a vérifié la détection de redémarrage Arch Linux en utilisant le chemin d'exécution réel du gestionnaire de paquets.

L'implémentation a été testée contre des conditions de redémarrage requises et des conditions d'achèvement normal.

**Statut : RÉUSSI**

---

# Audit de sécurité #12

## Tests unitaires et validation des résultats de l'API

Le comportement sensible à la sécurité est couvert par des tests automatisés.

La suite de tests comprend une couverture pour l'authentification, l'autorisation, la validation de l'API, les jobs de mise à jour, la gestion des paquets, l'authentification des clients et la gestion des résultats.

Le chemin de résultat Agent-vers-serveur a été spécifiquement examiné pour garantir que les résultats de job ne peuvent pas modifier arbitrairement un état serveur non lié.

Le traitement des résultats valide les informations soumises avant d'appliquer des changements d'état au job de mise à jour correspondant.

La validation couvre les champs de résultat pertinents et les relations de job attendues.

Cela empêche un client authentifié de sélectionner librement des jobs non liés ou d'injecter un état arbitraire dans la base de données des jobs de mise à jour.

La suite de tests de sécurité couvre également les cas négatifs et non autorisés.

Exécutez la suite de tests automatisés complète depuis la racine du référentiel avec
`./.venv-test/bin/pytest -q`. Le nombre de tests change au fil du temps ; utilisez
le résultat de l'exécution actuelle plutôt qu'un nombre fixe dans ce document.

Les contrôles de sécurité pertinents ont en outre été vérifiés par des exécutions de tests ciblés lors de l'audit.

**Statut : RÉUSSI**

---

# Statut de l'audit après la partie 4

Les domaines d'audit de sécurité suivants sont terminés :

| Audit | Domaine                                | Statut |
| ----- | -------------------------------------- | ------ |
| #01   | Clés étrangères SQLite                 | RÉUSSI |
| #02   | Configuration d'exécution SQLite       | RÉUSSI |
| #03   | Délai de mise à jour / Gestion des processus | RÉUSSI |
| #04   | Limitation du taux de connexion        | RÉUSSI |
| #05   | Validation des entrées de l'API        | RÉUSSI |
| #06   | Révocation de session                  | RÉUSSI |
| #07   | Rotation des tokens clients            | RÉUSSI |
| #08   | Gestion des adresses IP / Réseaux hors ligne | RÉUSSI |
| #09   | Récupération de job / Checkpointing    | RÉUSSI |
| #10   | Robustesse APT                         | RÉUSSI |
| #11   | Détection de redémarrage Arch          | RÉUSSI |
| #12   | Tests unitaires / Validation des résultats de l'API | RÉUSSI |

La section suivante couvre :

* #13 Tests de simulation
* #14 Intégration continue
* #15 Journalisation applicative / d'audit
* #16 Versionnement / Releases

# Audit de sécurité #13

## Tests de simulation

LUMS fournit un mécanisme de simulation pour tester les workflows de gestion des mises à jour sans effectuer l'opération correspondante de gestion des paquets sur le système géré.

La simulation est implémentée au niveau de la couche d'exécution de l'agent.

Lorsque la simulation est activée, les opérations de gestion des paquets sont représentées et traitées sans appliquer le changement de paquet demandé au système d'exploitation.

Cela permet de tester le comportement des jobs de mise à jour sans modifier intentionnellement le système géré.

Les tests de simulation couvrent les chemins pertinents de gestion des mises à jour, notamment :

* installation de paquets
* suppression de paquets
* mises à jour de paquets
* mises à jour système
* exécution de job
* rapport de résultat
* achèvement réussi
* gestion des échecs

Le mécanisme de simulation a été utilisé lors de l'audit de sécurité pour vérifier la création de job, l'exécution de l'agent, la gestion des résultats et les transitions d'état côté serveur indépendamment des modifications réelles des paquets.

Le mode simulation est un mécanisme de test et ne remplace pas les contrôles d'autorisation des opérations de mise à jour normales.

**Statut : RÉUSSI**

---

# Audit de sécurité #14

## Intégration continue

LUMS utilise des tests automatisés pour détecter les régressions de sécurité et fonctionnelles avant que les modifications ne soient considérées comme terminées.

Le processus CI exécute la suite de tests automatisés sur le projet.

L'environnement de test vérifie l'application et la fonctionnalité sensible à la sécurité indépendamment du conteneur de production.

Le processus CI comprend la validation de :

* authentification
* autorisation
* RBAC
* comportement de l'API
* gestion des jobs de mise à jour
* comportement de gestion des paquets
* authentification des clients
* validation des résultats de job
* gestion des erreurs sensibles à la sécurité

L'audit CI a été examiné après les modifications de durcissement de la sécurité.

La suite de tests finale vérifiée s'est terminée avec succès.

Le nombre de tests change au fur et à mesure que le projet évolue. La CI fournit une barrière de régression automatisée pour les modifications applicatives sensibles à la sécurité.

**Statut : RÉUSSI**

---

# Audit de sécurité #15

## Journalisation applicative et d'audit

LUMS enregistre les événements administratifs et opérationnels sensibles à la sécurité via la journalisation d'audit au niveau de l'application.

La journalisation d'audit est conçue pour fournir un historique opérationnel sans stocker d'identifiants sensibles.

Les actions sensibles à la sécurité pertinentes comprennent des événements tels que :

* événements de sécurité liés à l'authentification
* actions administratives
* gestion des clients
* opérations sur les tokens clients
* création de jobs de mise à jour
* exécution de jobs de mise à jour
* échecs sensibles à la sécurité

Le matériel d'identification sensible est exclu des enregistrements d'audit.

En particulier :

* les mots de passe ne sont pas journalisés
* les tokens clients en clair ne sont pas journalisés
* les valeurs secrètes ne sont pas intentionnellement écrites dans les enregistrements d'audit

Les enregistrements d'audit sont associés au contexte administratif ou opérationnel pertinent le cas échéant.

L'implémentation de la journalisation d'audit a été examinée pour :

* couverture des événements sensibles à la sécurité
* exclusion des identifiants
* traçabilité administrative
* gestion des échecs
* persistance des informations d'audit pertinentes

Le système de journalisation est conçu pour prendre en charge à la fois le dépannage opérationnel et l'investigation de sécurité.

**Statut : RÉUSSI**

---

# Audit de sécurité #16

## Versionnement et Releases

Le versionnement et la gestion des releases font partie de la revue de sécurité, car les opérateurs doivent pouvoir identifier précisément le code et les artefacts qu'ils déploient. La disponibilité des releases et les versions des composants évoluent indépendamment de ce guide. Consultez les tags actuels et la [page Releases](https://github.com/NovaForgeCtrl/LUMS/releases) du dépôt, ainsi que les métadonnées de version de la révision exacte du code source à déployer. Ce document n'est pas un catalogue des releases en temps réel.

Les versions actuelles des composants comprennent :

* LUMS Agent : `1.7.0`
* LUMS Watcher : `1.2.1`

Le processus de release prévu est :

1. Terminer le travail d'implémentation.
2. Terminer la revue de sécurité.
3. Examiner et synchroniser la documentation.
4. Terminer la suite de tests automatisés complète.
5. Vérifier la CI.
6. Définir la version de release.
7. Créer l'étiquette Git correspondante.
8. Publier la GitHub Release.
9. Préserver la release comme base documentée.

---

# Statut de l'audit après la partie 5

Les domaines d'audit de sécurité suivants sont terminés :

| Audit | Domaine                                | Statut                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | Clés étrangères SQLite                 | RÉUSSI                    |
| #02   | Configuration d'exécution SQLite       | RÉUSSI                    |
| #03   | Délai de mise à jour / Gestion des processus | RÉUSSI              |
| #04   | Limitation du taux de connexion        | RÉUSSI                    |
| #05   | Validation des entrées de l'API        | RÉUSSI                    |
| #06   | Révocation de session                  | RÉUSSI                    |
| #07   | Rotation des tokens clients            | RÉUSSI                    |
| #08   | Gestion des adresses IP / Réseaux hors ligne | RÉUSSI              |
| #09   | Récupération de job / Checkpointing    | RÉUSSI                    |
| #10   | Robustesse APT                         | RÉUSSI                    |
| #11   | Détection de redémarrage Arch          | RÉUSSI                    |
| #12   | Tests unitaires / Validation des résultats de l'API | RÉUSSI    |
| #13   | Tests de simulation                    | RÉUSSI                    |
| #14   | Intégration continue                   | RÉUSSI                    |
| #15   | Journalisation applicative / d'audit   | RÉUSSI                    |
| #16   | Versionnement / Releases               | Vérifier les releases et tags actuels du dépôt |

Le domaine d'audit technique numéroté restant est :

* #17 Contrôle d'accès basé sur les rôles

La revue de la documentation est un processus continu, mené indépendamment de tout état d'audit numéroté.

# Audit de sécurité #17

## Contrôle d'accès basé sur les rôles

LUMS combine des modèles de rôles avec des permissions attribuées individuellement. Les modèles pris en charge sont `administrator`, `operator` et `viewer` ; choisir un modèle sélectionne ses permissions par défaut, qu'un administrateur peut personnaliser pour chaque compte.

Le rôle reste des métadonnées de compte. Les routes protégées autorisent en fonction de l'ensemble de permissions stocké côté serveur du compte, et non de l'étiquette de rôle. L'interface masque les fonctions non disponibles pour l'ergonomie, tandis que le serveur reste la frontière de sécurité.

---

## Modèle de permissions RBAC

| Permission        | Accès accordé |
| ----------------- | ------------- |
| `clients.view`    | Afficher les clients et les informations système |
| `software.view`   | Afficher les logiciels installés |
| `updates.view`    | Afficher les mises à jour disponibles, les jobs et l'historique |
| `packages.search` | Rechercher dans les référentiels de paquets |
| `jobs.manage`     | Créer des opérations sur les paquets et des jobs de mise à jour |
| `clients.manage`  | Enregistrer/supprimer des clients et faire tourner les tokens clients |
| `users.manage`    | Créer des utilisateurs et gérer les rôles et permissions |

Les modèles de rôles par défaut sont :

| Modèle          | Permissions par défaut |
| --------------- | ---------------------- |
| `administrator` | Toutes les permissions |
| `operator`      | Visibilité clients/logiciels/mises à jour, recherche de paquets et gestion des jobs |
| `viewer`        | Visibilité des clients et des logiciels installés |

Les permissions liées aux clients nécessitent `clients.view`. `jobs.manage` nécessite également `updates.view`. L'UI charge les permissions du compte authentifié et omet les contrôles que l'utilisateur ne peut pas utiliser ; les vérifications côté serveur appliquent indépendamment les mêmes attributions.

---

## Application de l'autorisation

Les opérations protégées utilisent l'authentification et les vérifications de permissions côté serveur.

Le modèle d'autorisation suit le principe :

`Authentifier → Charger les permissions utilisateur → Autoriser l'opération → Exécuter`

L'authentification seule n'est pas suffisante pour accéder aux opérations privilégiées.

Les opérations modifiant l'état nécessitent en outre une protection CSRF le cas échéant.

Les exemples d'opérations administratives protégées comprennent :

* création de job de mise à jour
* installation de paquets
* suppression de paquets
* mises à jour de paquets
* mises à jour système
* opérations de gestion des paquets
* création de clients
* désactivation de clients
* rotation de tokens clients
* création d'utilisateurs
* fonctions de gestion des utilisateurs

Les points de terminaison protégés définissent explicitement la permission requise pour l'opération correspondante.

Une permission manquante est rejetée par le serveur même si l'utilisateur construit manuellement la requête HTTP correspondante.

Cela empêche de contourner le modèle RBAC en appelant directement un point de terminaison d'API qui est masqué dans l'interface web.

---

## Restrictions Viewer

Le modèle Viewer est intentionnellement restreint par son ensemble de permissions par défaut.

Pour les comptes sans les attributions correspondantes, l'interface client n'expose pas :

* Mises à jour
* Jobs de mise à jour
* Historique des mises à jour
* Gestion des paquets
* Maintenance système

Le serveur empêche en outre les comptes sans les attributions correspondantes d'effectuer des opérations protégées.

L'interface JavaScript ne charge pas les données de gestion des mises à jour sans `updates.view`.

Cela réduit l'exposition inutile des informations opérationnelles tout en maintenant l'autorisation côté serveur comme contrôle de sécurité réel.

Les logiciels installés restent disponibles pour les comptes Viewer en tant que fonction d'information en lecture seule.

---

## Gestion administrative des utilisateurs

La gestion des utilisateurs nécessite la permission `users.manage`.

Les utilisateurs disposant de cette permission peuvent créer des comptes sans permissions puis attribuer des permissions individuelles ou appliquer un modèle de rôle dans l'éditeur de permissions. Les modèles de rôles ont des descriptions expliquant leurs attributions par défaut.

Les gestionnaires d'utilisateurs autorisés peuvent enregistrer une note interne par compte. Les notes sont limitées à 2 000 caractères, ne sont pas incluses dans les détails du journal d'audit et ne sont pas visibles pour le propriétaire du compte.

La création d'utilisateur comprend :

* validation du nom d'utilisateur
* validation du rôle
* validation du mot de passe
* hachage de mot de passe Argon2
* détection de doublons d'utilisateurs
* journalisation d'audit
* protection CSRF
* autorisation côté serveur

Les points de terminaison de gestion des utilisateurs ne sont pas accessibles sans `users.manage`.

Le serveur rejette les permissions inconnues et les combinaisons de dépendances invalides. Au moins un compte actif doit conserver `users.manage` ; les modifications qui supprimeraient le dernier gestionnaire d'utilisateurs sont rejetées.

Les mots de passe ne sont jamais stockés en clair.

---

## Migration de base de données RBAC

Les informations de modèle de rôle restent dans l'enregistrement de base de données utilisateur. Les attributions individuelles sont stockées dans la table `user_permissions` avec une clé étrangère vers le compte utilisateur. La migration `003-user-permissions` crée cette table et initialise les comptes existants à partir de leur modèle de rôle actuel, préservant leur accès pendant la transition. La migration `004-user-admin-notes` ajoute le champ privé `users.admin_note` ; les comptes existants reçoivent une note vide. La migration `005-backup-permission` accorde `backups.manage` aux comptes Administrator existants.

La création de sauvegarde de base de données nécessite `backups.manage` ; le modèle Administrator inclut cette permission par défaut. Le serveur écrit les sauvegardes en ligne SQLite uniquement dans le `LUMS_BACKUP_DIR` configuré côté serveur ; il n'accepte pas les chemins de système de fichiers du navigateur. Les fichiers de sauvegarde sont créés avec des permissions réservées au propriétaire et sont vérifiés en intégrité avant publication.

---

## Tests de sécurité RBAC

Le comportement RBAC est couvert par des tests automatisés.

Les tests comprennent :

* autorisation Administrator
* autorisation Operator
* restrictions Viewer
* accès API protégé
* opérations non autorisées
* restrictions de gestion des clients
* restrictions de job de mise à jour
* restrictions de gestion des utilisateurs
* visibilité de la page client
* comportement d'interface spécifique aux permissions

Les tests RBAC couvrent les valeurs par défaut des modèles de rôles, les permissions personnalisées, les dépendances de permissions et l'autorisation côté serveur. La vérification de production doit inclure des comptes avec des permissions personnalisées ainsi que les modèles par défaut Administrator, Operator et Viewer.

---

## Résultat de sécurité RBAC

L'implémentation RBAC fournit une autorisation en couches :

1. L'authentification établit l'identité de l'utilisateur.
2. Le serveur charge les permissions de l'utilisateur.
3. Les routes protégées appliquent la permission requise.
4. La protection CSRF s'applique aux changements d'état pertinents du navigateur.
5. L'interface web masque les fonctionnalités non disponibles.
6. Les tests automatisés vérifient les frontières d'autorisation.

L'interface ne fournit donc pas elle-même le mécanisme d'autorisation.

Le serveur reste la frontière de sécurité faisant autorité.

**Statut : RÉUSSI**

## Revue de documentation

La documentation de sécurité doit être maintenue en fonction du système LUMS actuellement implémenté.

Le but de cette revue est de garantir que la documentation de sécurité décrit l'implémentation réelle plutôt qu'un état de développement antérieur.

La revue couvre :

* authentification
* autorisation
* RBAC
* authentification des clients
* gestion des tokens
* gestion des sessions
* protection CSRF
* limitation du taux
* configuration SQLite
* exécution des mises à jour
* récupération de job
* gestion des paquets
* durcissement du conteneur
* exposition réseau
* gestion des secrets
* sécurité des dépendances et de la construction
* permissions du système de fichiers
* journalisation applicative et d'audit
* versionnement et gestion des releases
* tests de sécurité automatisés

La documentation doit distinguer entre :

* contrôles implémentés
* comportement de production vérifié
* améliorations prévues
* décisions de projet intentionnellement ouvertes

Les détails d'implémentation historiques ne doivent pas être présentés comme une configuration de production actuelle.

En particulier, la documentation reflète la configuration SQLite de production actuellement implémentée.

L'exécution de production actuelle est documentée comme :

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* `PRAGMA foreign_keys = ON` au niveau de l'application

Le comportement RBAC Viewer actuel est également documenté selon l'interface de production implémentée.

Les utilisateurs Viewer ont accès à :

* informations clients
* logiciels installés

Les utilisateurs Viewer n'ont pas accès à :

* Mises à jour
* Jobs de mise à jour
* Historique des mises à jour
* Gestion des paquets
* Maintenance système

Réexaminez la documentation lorsque le code ou le comportement du déploiement change. Supprimez ou remplacez alors les références obsolètes aux nombres de tests antérieurs, aux états de migration, aux configurations de déploiement et au comportement réservé au développement.

---

# Durcissement de sécurité supplémentaire

L'audit de sécurité numéroté couvre les principaux contrôles de sécurité applicative.

Un durcissement supplémentaire a été effectué après la séquence d'audit initiale et fait partie de la base de sécurité actuelle.

Ces contrôles sont documentés ici car ils représentent des propriétés de sécurité importantes du déploiement actuel.

---

## Durcissement du conteneur

Le conteneur LUMS de production s'exécute avec une configuration Docker durcie.

Le conteneur de production utilise :

* utilisateur applicatif non-root
* système de fichiers racine en lecture seule
* capacités Linux abandonnées
* `no-new-privileges`
* systèmes de fichiers temporaires restreints
* montage secret en lecture seule
* volume dédié de données applicatives persistantes
* politique de redémarrage
* publication hôte du port applicatif limitée au loopback

Le système de fichiers racine de l'application n'est donc pas inscriptible pendant le fonctionnement normal.

Les emplacements inscriptibles sont explicitement limités aux emplacements requis par l'application.

Le conteneur de production a été inspecté indépendamment pour vérifier la configuration d'exécution effective.

L'exécution durcie a également été testée en vérifiant que :

* les écritures sur le système de fichiers applicatif échouent
* `/tmp` reste disponible lorsque nécessaire
* `/var/lib/lums` reste inscriptible
* le fichier secret reste en lecture seule
* l'application reste opérationnelle

---

## Exposition réseau

Le port applicatif LUMS n'est pas directement exposé au LAN.

Le port applicatif Docker est lié à l'interface loopback :

`127.0.0.1:5050`

L'accès externe est fourni via Nginx.

L'hôte de production expose les services réseau prévus via le pare-feu et le proxy inverse.

Le déploiement a été vérifié pour empêcher l'accès distant direct au port applicatif Docker interne.

Le pare-feu utilise un modèle de refus par défaut pour le trafic entrant et routé.

Les services prévus accessibles de l'extérieur sont :

* SSH
* HTTP
* HTTPS

Les requêtes HTTP sont redirigées vers HTTPS par le serveur web.

Le site Nginx par défaut a été supprimé afin que le contenu par défaut non lié ne soit pas exposé.

---

## Sécurité du transport

L'accès web administratif est fourni via HTTPS.

HTTP est redirigé vers HTTPS.

Le point de terminaison TLS est géré par Nginx plutôt que par l'application Flask/Gunicorn directement.

Cela maintient la sécurité du transport et la diffusion applicative séparées.

Le port applicatif Gunicorn interne n'est donc pas destiné à être un point de terminaison HTTP public.

Le déploiement actuel est destiné à une infrastructure interne contrôlée.

Un futur déploiement avec exposition directe à l'Internet public nécessiterait une revue de sécurité supplémentaire.

---

## Secrets et configuration

Les secrets de production ne sont pas stockés dans l'arborescence source de l'application.

La clé secrète LUMS est fournie via un fichier secret protégé.

Le conteneur de production reçoit le secret via :

`/run/secrets/lums_secret`

Le fichier secret est monté en lecture seule.

L'application lit le secret via le mécanisme de fichier secret configuré.

La gestion du référentiel et du contexte de construction Docker a été examinée pour empêcher l'inclusion accidentelle de :

* fichiers de base de données
* fichiers de sauvegarde
* fichiers secrets
* clés privées
* certificats
* journaux d'exécution
* artefacts de sauvegarde locaux

Le référentiel ignore également les modèles de sauvegarde temporaire courants utilisés pendant le développement.

---

## Sécurité des dépendances et de la construction

L'image Docker de production utilise un digest d'image de base Python épinglé.

Les dépendances d'exécution de production sont explicitement épinglées en version.

L'ensemble de dépendances de production actuel comprend :

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

Le contexte de construction Docker est restreint via `.dockerignore`.

Les constructions de production répétées ont été comparées lors de l'audit.

Les métadonnées pertinentes des dépendances et des paquets sont restées cohérentes entre les constructions répétées, à l'exception des différences attendues de bytecode Python généré.

Cela fournit une base reproductible pour l'image de production tout en gardant le contexte de construction limité.

---

## Permissions du système de fichiers et d'exécution

L'application de production s'exécute en tant qu'utilisateur dédié `lums` plutôt que root.

Les données applicatives persistantes sont stockées dans le volume de données LUMS dédié.

Le système de fichiers racine de l'application est en lecture seule.

L'accès en écriture à l'exécution est limité aux emplacements explicitement requis.

L'exécution de production a été vérifiée pour rejeter les écritures non autorisées sur le système de fichiers applicatif.

Cela réduit l'impact des modifications de fichiers accidentelles ou malveillantes à l'intérieur du conteneur applicatif.

---

# Conclusion de l'audit de sécurité

L'implémentation actuelle de LUMS a fait l'objet d'une vaste revue de sécurité couvrant :

* authentification
* autorisation
* RBAC
* sécurité des sessions
* protection CSRF
* limitation du taux de connexion
* sécurité des tokens clients
* validation de l'API
* résistance à l'injection SQL
* intégrité SQLite
* exécution des mises à jour
* gestion des délais
* récupération de job
* robustesse de la gestion des paquets
* validation des résultats
* simulation
* intégration continue
* journalisation d'audit
* durcissement du conteneur
* exposition réseau
* sécurité du transport
* gestion des secrets
* permissions du système de fichiers
* sécurité des dépendances et de la construction

Les résultats d'audit numérotés sont :

| Audit | Domaine                                | Statut                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | Clés étrangères SQLite                 | RÉUSSI                    |
| #02   | Configuration d'exécution SQLite       | RÉUSSI                    |
| #03   | Délai de mise à jour / Gestion des processus | RÉUSSI              |
| #04   | Limitation du taux de connexion        | RÉUSSI                    |
| #05   | Validation des entrées de l'API        | RÉUSSI                    |
| #06   | Révocation de session                  | RÉUSSI                    |
| #07   | Rotation des tokens clients            | RÉUSSI                    |
| #08   | Gestion des adresses IP / Réseaux hors ligne | RÉUSSI              |
| #09   | Récupération de job / Checkpointing    | RÉUSSI                    |
| #10   | Robustesse APT                         | RÉUSSI                    |
| #11   | Détection de redémarrage Arch          | RÉUSSI                    |
| #12   | Tests unitaires / Validation des résultats de l'API | RÉUSSI    |
| #13   | Tests de simulation                    | RÉUSSI                    |
| #14   | Intégration continue                   | RÉUSSI                    |
| #15   | Journalisation applicative / d'audit   | RÉUSSI                    |
| #16   | Versionnement / Releases               | Vérifier les releases et tags actuels du dépôt |
| #17   | Contrôle d'accès basé sur les rôles    | RÉUSSI                    |

Les contrôles de sécurité techniques examinés dans les audits #01–#15 et #17 ont réussi.

La disponibilité des releases et des tags peut évoluer ; consultez les [releases](https://github.com/NovaForgeCtrl/LUMS/releases) et les [tags](https://github.com/NovaForgeCtrl/LUMS/tags) actuels du dépôt.

Aucun résultat d'audit de sécurité ne doit être interprété comme une garantie que LUMS est exempt de vulnérabilités.

La sécurité est un processus continu.

Les modifications de l'application, de l'agent, des dépendances, de la configuration du conteneur, de l'exposition réseau, du modèle d'authentification ou de l'architecture de déploiement doivent déclencher une nouvelle revue de sécurité des contrôles affectés.

---

# Base de sécurité

Cette base décrit les contrôles configurés dans le code source et les consignes de déploiement. Elle ne prouve pas qu'une installation particulière les applique ; vérifiez les paramètres effectifs dans l'environnement cible.

La base comprend :

* authentification côté serveur
* RBAC côté serveur
* hachage de mot de passe Argon2
* condensés SHA-256 des tokens clients
* protection CSRF
* limitation du taux de connexion
* SQL paramétré
* entrée API validée
* exécution contrôlée du gestionnaire de paquets
* récupération de job de mise à jour
* journalisation d'audit
* exécution Docker durcie
* HTTPS via Nginx
* exposition du port applicatif limitée au loopback
* restrictions du pare-feu
* secrets de production protégés
* dépendances de production épinglées
* permissions du système de fichiers restreintes
* tests de sécurité automatisés

Les modifications futures devraient préserver ces propriétés, sauf si un changement architectural délibéré les remplace par un contrôle équivalent ou plus fort.

---

# Maintenance de la sécurité

Les contrôles de sécurité devraient être revalidés lorsque des modifications significatives sont introduites.

Les exemples comprennent :

* modifications d'authentification
* nouveaux rôles utilisateur
* nouveaux points de terminaison d'API
* modifications de gestion des paquets
* modifications d'exécution de l'agent
* migrations de base de données
* mises à jour de dépendances
* modifications du Dockerfile
* modifications du runtime du conteneur
* modifications du proxy inverse
* modifications du pare-feu
* modifications de gestion des secrets
* préparation de release

Les tests de sécurité doivent être effectués avant de publier une release officielle.

La documentation de sécurité doit être mise à jour chaque fois que la base de sécurité vérifiée change.

---

# Préparation à la release

La première release officielle de LUMS ne sera créée qu'après :

1. le travail d'implémentation est terminé
2. la revue de sécurité est terminée
3. la revue de documentation est terminée
4. la suite de tests automatisés complète réussit
5. la CI réussit
6. la version finale est définie
7. l'étiquette Git est créée
8. la GitHub Release est publiée

D'ici là, LUMS reste un projet en développement actif.

---

# Déclaration finale

LUMS est conçu comme une plateforme contrôlée de gestion des mises à jour Linux avec la sécurité comme préoccupation architecturale centrale.

Le modèle de sécurité ne repose pas sur un seul mécanisme de protection.

Au lieu de cela, l'authentification, l'autorisation, la validation, l'exécution contrôlée, la persistance, la récupération, la journalisation, l'isolation du conteneur, les restrictions réseau et les tests automatisés fonctionnent ensemble comme des contrôles en couches.

Le projet privilégie délibérément l'application explicite côté serveur plutôt que la sécurité par interface.

La base de sécurité actuelle est documentée selon l'état d'implémentation vérifié plutôt que selon le comportement de développement historique.

---

**LUMS — Gestion des mises à jour Linux sans le bruit.**

`segfault // override`
