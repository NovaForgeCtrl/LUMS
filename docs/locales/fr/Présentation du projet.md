# LUMS

**Gestion des mises à jour Linux sans le bruit.**

## Pour commencer

LUMS gère centralement les mises à jour Linux. Un serveur affiche les clients, les logiciels installés et les mises à jour disponibles. Un agent sur chaque système Linux géré effectue les actions de paquets approuvées en utilisant le gestionnaire de paquets de ce système. LUMS ne remplace pas APT sur Debian/Ubuntu ni pacman sur Arch Linux.

**Vous utilisez uniquement une installation LUMS existante ?** Ouvrez l'adresse fournie par votre administrateur et connectez-vous avec votre propre compte. Si une fonctionnalité est manquante, votre compte n'a peut-être pas la permission de l'utiliser. Demandez de l'aide à votre administrateur ; ne partagez pas de comptes et n'utilisez pas un token client comme mot de passe web.

**Vous installez ou exploitez LUMS ?** Commencez par le [guide d'installation](<Installation et mises à niveau.md>), puis lisez le [guide d'administration](<Administration et sauvegardes.md>). Si quelque chose ne va pas, utilisez le [guide de dépannage](Dépannage.md). Des guides traduits sont également disponibles, mais leur couverture peut différer des références techniques en anglais. L'[index de la documentation](../../README.md) répertorie les versions linguistiques disponibles.

Un test réussi ou une image Docker construite avec succès n'est **pas** une installation de production. Un déploiement en production nécessite également HTTPS, un secret applicatif protégé, des données persistantes, des sauvegardes vérifiées et un conteneur durci. Ne copiez pas les commandes de production avant d'avoir vérifié leurs espaces réservés et chemins de stockage par rapport à votre propre installation.

### Langues de l'interface web

L'interface web propose l'allemand, l'anglais (US et UK), le français, l'espagnol, le chinois simplifié, le japonais, le polonais, le suédois, le norvégien bokmål et le finnois. Choisissez une langue dans le coin supérieur droit de la page de connexion. Si vous n'en choisissez aucune, LUMS essaie d'utiliser la langue du navigateur ; après la connexion, une langue enregistrée dans votre compte a la priorité. Certains textes techniques ou dynamiques peuvent rester dans leur langue d'origine lorsqu'une traduction n'est pas disponible. Les guides Markdown sont séparés de l'interface web et ne sont pas traduits automatiquement.

---

LUMS est un serveur de gestion des mises à jour Linux conçu pour fournir une gestion des logiciels et des mises à jour contrôlée, auditable et sécurisée pour les clients Linux.

Au lieu de s'appuyer sur une activité de mise à jour non contrôlée côté client, LUMS fournit une couche de gestion centrale pour l'inventaire logiciel, la détection des mises à jour, les opérations sur les paquets, les jobs de mise à jour, la surveillance de l'exécution et la remontée des résultats.

LUMS est conçu pour les environnements où les mises à jour doivent être **visibles, contrôlées, traçables et récupérables**.

---

## Qu'est-ce que LUMS ?

LUMS (**Linux Update Management Server**) se compose d'un serveur central et de clients Linux légers.

Le serveur fournit l'interface de gestion, l'API, l'authentification, l'autorisation, la gestion des jobs, la journalisation d'audit et l'état persistant.

L'agent côté client effectue les opérations locales sur le gestionnaire de paquets et rapporte les résultats au serveur.

L'architecture de base est :

```text
                    ┌──────────────────────┐
                    │      Web Browser      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     LUMS Server      │
                    │                      │
                    │ Web UI / API         │
                    │ Authentication       │
                    │ RBAC                 │
                    │ Job Management       │
                    │ Audit Logging        │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         HTTPS / API
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────────┐             ┌─────────────────┐
      │   Linux Client  │             │   Linux Client  │
      │                 │             │                 │
      │ LUMS Agent      │             │ LUMS Agent      │
      │ Package Manager │             │ Package Manager │
      │ Watcher         │             │ Watcher         │
      └─────────────────┘             └─────────────────┘
```

---

## Pourquoi LUMS ?

Les systèmes Linux fournissent déjà d'excellents outils de gestion de paquets.

LUMS ne cherche pas à les remplacer.

Au lieu de cela, LUMS fournit une couche de gestion autour de ces outils afin que les administrateurs puissent répondre centralement à des questions telles que :

* Quels clients existent ?
* Quels logiciels sont installés ?
* Quelles mises à jour sont disponibles ?
* Quels paquets doivent être installés ou supprimés ?
* Quels jobs de mise à jour sont en cours ?
* Que s'est-il passé lors d'une mise à jour ?
* Le client a-t-il rapporté le résultat avec succès ?
* Un redémarrage a-t-il été nécessaire ?
* Un job interrompu peut-il récupérer en toute sécurité ?
* Qui a initié une action administrative ?

L'objectif n'est pas de masquer le gestionnaire de paquets Linux sous-jacent.

L'objectif est de rendre son fonctionnement **gérable et auditable**.

---

## Fonctionnalités principales

### Gestion des clients

LUMS maintient des clients Linux enregistrés et leur état d'authentification.

Chaque client reçoit un token d'authentification individuel.

Les tokens clients ne sont pas stockés en tant qu'identifiants en clair. Le serveur stocke un condensé SHA-256 et valide l'authentification entrante du client par rapport à ce condensé.

Les administrateurs peuvent :

* enregistrer des clients
* désactiver des clients
* faire tourner les tokens clients
* inspecter l'état des clients
* surveiller la remontée des clients

---

### Inventaire logiciel

Les clients rapportent leurs logiciels installés au serveur LUMS.

Le serveur stocke l'inventaire et l'expose via l'interface de gestion.

La vue des logiciels installés est intentionnellement séparée de la recherche de gestion des paquets.

Cela permet aux administrateurs et aux utilisateurs en lecture seule d'inspecter les logiciels installés sans exposer automatiquement les opérations de gestion des paquets.

---

### Inventaire des mises à jour

Les clients déterminent périodiquement si des mises à jour de paquets sont disponibles.

Le serveur stocke les informations de mise à jour rapportées et les rend disponibles aux utilisateurs autorisés.

Les informations de mise à jour peuvent servir de base à des jobs de mise à jour contrôlés.

---

### Gestion des paquets

LUMS fournit des opérations de gestion des paquets via l'agent client.

Les opérations sur les paquets prises en charge comprennent :

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

La couche de gestion des paquets abstrait le gestionnaire de paquets sous-jacent.

Les familles de gestionnaires de paquets actuellement prises en charge sont :

* **Debian / Ubuntu :** APT / dpkg
* **Arch Linux :** pacman

La recherche de paquets est également disponible via LUMS.

Les demandes de recherche sont envoyées au client cible, exécutées à l'aide du gestionnaire de paquets local, et renvoyées au serveur pour affichage.

---

### Jobs de mise à jour

Les opérations de mise à jour sont représentées sous forme de jobs persistants.

Un job peut contenir une ou plusieurs opérations sur les paquets et maintient un état d'exécution côté serveur.

Le cycle de vie général est :

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► SUCCESS
   │
   └──────────────► FAILED
```

Les résultats au niveau des paquets sont suivis indépendamment afin que les jobs interrompus puissent être récupérés sans répéter inutilement les opérations déjà terminées avec succès.

---

### Exécution contrôlée

LUMS n'exécute pas de commandes shell arbitraires fournies par l'interface web.

Le serveur crée des jobs structurés à l'aide d'actions et de noms de paquets validés.

L'agent client mappe ces actions à l'opération appropriée du gestionnaire de paquets local.

Cela crée une frontière délibérée entre :

```text
Web UI
   ↓
API
   ↓
Validated Job
   ↓
Agent
   ↓
Package Manager
```

---

### Exécution consciente de l'inactivité

LUMS peut différer l'exécution d'une mise à jour tant qu'un client est considéré actif.

Le seuil d'inactivité actuel est de **300 secondes**.

Lorsque cela est pris en charge, l'agent utilise les informations de session/inactivité du système local via `loginctl`.

Si la détection d'inactivité n'est pas disponible, LUMS ne prétend pas que le client est inactif.

Cette distinction est importante car **un état d'inactivité inconnu n'est pas la même chose qu'un état d'inactivité confirmé**.

---

### Récupération des jobs

Les jobs de mise à jour sont conçus pour survivre aux interruptions.

Le serveur maintient un état persistant des jobs et des éléments de paquets.

Lors de la récupération, les éléments de paquets déjà réussis ne sont pas exécutés à nouveau inutilement.

Cela fournit un modèle d'exécution de type point de contrôle pour les opérations multi-paquets.

L'objectif est :

> **Récupérer le job, pas redémarrer aveuglément tout le job.**

---

### Détection de redémarrage

Certaines opérations sur les paquets peuvent nécessiter un redémarrage du système.

LUMS traite donc la détection de redémarrage comme faisant partie du traitement du résultat de mise à jour, plutôt que de supposer qu'une sortie réussie du gestionnaire de paquets signifie toujours que le système est pleinement opérationnel.

Le client rapporte l'exigence de redémarrage détectée au serveur.

---

### Authentification des clients

La communication client est authentifiée à l'aide de tokens par client.

Les tokens sont :

* attribués individuellement
* rotatifs
* stockés côté serveur uniquement sous forme de condensés SHA-256
* validés avant d'accepter les rapports des clients

La rotation des tokens permet à un administrateur d'invalider un identifiant client précédemment émis sans recréer le client.

---

### Auditabilité

Les actions administratives et relatives à la sécurité sont enregistrées via le système de journalisation d'audit de LUMS.

La piste d'audit vise à répondre :

```text
Qui ?
Quoi ?
Quand ?
Sur quel objet ?
Avec quel résultat ?
```

Cela inclut les opérations sensibles à la sécurité telles que les actions liées à l'authentification, la gestion des clients, la gestion des utilisateurs et la création de jobs de mise à jour.

---

## Principe de conception

LUMS suit un principe simple :

> **Rendre la gestion des mises à jour Linux visible, contrôlée, récupérable et auditable — sans masquer les outils Linux sous-jacents.**

## Architecture

LUMS sépare la gestion, l'exécution et la persistance en composants clairement définis.

Le serveur est responsable de l'orchestration et des politiques.

Le client est responsable de l'interaction avec le système local.

Le gestionnaire de paquets reste responsable de l'installation, de la suppression ou de la mise à jour réelle des logiciels.

Cette séparation est intentionnelle.

```text
Browser
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│                LUMS Server                │
│                                          │
│  Web UI                                  │
│  Authentication / Sessions               │
│  RBAC                                    │
│  API                                     │
│  Client Management                       │
│  Package Search                          │
│  Update Job Management                   │
│  Audit Logging                            │
│  SQLite Persistence                       │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Client API
                    ▼
┌──────────────────────────────────────────┐
│               LUMS Agent                  │
│                                          │
│  Authentication                          │
│  Inventory Reporting                     │
│  Update Detection                        │
│  Package Search                          │
│  Job Execution                           │
│  Result Reporting                        │
│  Reboot Detection                        │
│  Idle Detection                          │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Package Manager    │
          │                    │
          │ APT / dpkg         │
          │ pacman             │
          └────────────────────┘
```

---

## Composants du serveur

Le serveur LUMS fournit la couche de gestion centrale.

### Application web

L'application web fournit l'interface administrative pour :

* la gestion des clients
* l'inventaire logiciel
* les informations de mise à jour
* les jobs de mise à jour
* la gestion des paquets
* l'historique des mises à jour
* la gestion des utilisateurs
* la maintenance système

L'interface respecte le rôle RBAC de l'utilisateur actuel.

La visibilité frontend est donc adaptée aux permissions de l'utilisateur, mais l'autorisation est toujours appliquée côté serveur également.

---

### API

L'API connecte l'interface web et les clients Linux à la logique applicative côté serveur.

Elle gère des opérations telles que :

* l'enregistrement et la gestion des clients
* les rapports des clients
* les recherches de paquets
* les résultats de recherche de paquets
* les jobs de mise à jour
* les résultats des jobs
* la gestion des utilisateurs
* les événements d'audit

Les points de terminaison de l'API valident leurs entrées avant d'effectuer des opérations modifiant l'état.

---

### Authentification et sessions

Les utilisateurs administratifs s'authentifient via l'application web LUMS.

Les sessions sont contrôlées par le serveur et prennent en charge la révocation explicite des sessions.

La sécurité de l'authentification comprend :

* hachage des mots de passe à l'aide d'Argon2
* gestion des sessions
* révocation des sessions
* limitation du taux de connexion
* protection CSRF
* autorisation basée sur les rôles

L'authentification des clients est séparée de l'authentification administrative.

---

### RBAC

LUMS combine des modèles de rôles avec des permissions par utilisateur. Les modèles Administrator, Operator et Viewer fournissent des ensembles de permissions de départ qui peuvent être personnalisés pour chaque compte.

L'autorisation est appliquée sur le serveur en utilisant les permissions stockées du compte.

Le frontend masque en outre les fonctionnalités que les permissions de l'utilisateur n'autorisent pas.

Cela signifie que masquer un bouton n'est jamais considéré comme une frontière de sécurité.

---

### Persistance SQLite

LUMS utilise SQLite pour l'état persistant de l'application.

La base de données stocke des informations telles que :

* utilisateurs
* sessions
* clients
* état d'authentification des clients
* inventaire logiciel
* mises à jour disponibles
* jobs de mise à jour
* résultats des jobs au niveau des paquets
* demandes et résultats de recherche de paquets
* informations d'audit

L'application active explicitement l'application des clés étrangères SQLite pour les connexions à la base de données.

La base SQLite de production actuelle est :

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS utilise le mode WAL de SQLite dans la configuration de production actuelle.

---

## Architecture des conteneurs

Le serveur LUMS est déployé en tant que conteneur Docker durci.

Le conteneur applicatif est intentionnellement traité comme jetable.

L'état persistant de l'application est stocké dans le volume Docker dédié :

```text
lums-data
```

Le conteneur de production utilise un système de fichiers racine en lecture seule.

Les emplacements inscriptibles sont délibérément limités aux chemins d'exécution et de stockage persistant requis.

La base de sécurité de production comprend :

```text
read-only root filesystem
all Linux capabilities dropped
no-new-privileges
restricted /tmp
restricted /run
read-only secret mount
dedicated persistent data volume
non-root application user
```

L'application est exposée en interne via :

```text
127.0.0.1:5050
```

L'accès HTTPS externe est fourni via le proxy inverse.

---

## Composants persistants et jetables

LUMS sépare l'état persistant des composants d'exécution remplaçables.

```text
Persistent
├── SQLite database
├── client state
├── user state
├── job state
└── audit state

Disposable
├── Docker container
├── application process
└── generated runtime state
```

Le remplacement du conteneur applicatif ne supprime donc pas intrinsèquement la base de données LUMS.

Cette séparation est importante pour les mises à niveau et la récupération.

---

## Architecture client

Le client Linux se compose de plusieurs composants coopérants.

### LUMS Agent

L'agent est responsable de l'interaction avec le serveur LUMS et le système Linux local.

Version actuelle de l'agent :

```text
1.7.0
```

L'agent gère :

* l'authentification
* la collecte d'inventaire
* la détection des mises à jour
* la recherche de paquets
* les opérations sur les paquets
* l'exécution des jobs de mise à jour
* la remontée des résultats
* la détection de redémarrage
* la gestion de l'état d'inactivité

---

### Couche gestionnaire de paquets

La couche gestionnaire de paquets fournit une abstraction contrôlée autour du gestionnaire de paquets Linux natif.

L'agent n'exige pas que LUMS remplace le gestionnaire de paquets.

Au lieu de cela :

```text
LUMS Action
     │
     ▼
Package Manager Abstraction
     │
     ├── Debian / Ubuntu → APT / dpkg
     │
     └── Arch Linux      → pacman
```

Cela maintient la gestion spécifique à la distribution à l'intérieur du client.

---

### Execution Watcher

Le watcher surveille l'exécution des jobs de mise à jour sur le client.

Version actuelle du watcher :

```text
1.2.1
```

Le watcher fonctionne avec l'agent et l'état des jobs côté serveur.

Son but est de s'assurer que les jobs qui doivent s'exécuter ne restent pas indéfiniment non traités.

---

## Chemin de rapport

La remontée normale des clients suit cette direction :

```text
Linux Client
    │
    │ inventory / update information
    ▼
LUMS API
    │
    ▼
SQLite
    │
    ▼
Web UI
```

Par exemple, une vérification de mise à jour effectuée par le client produit des informations qui sont rapportées au serveur et stockées comme état de mise à jour actuel du client.

Le navigateur n'interroge pas directement le gestionnaire de paquets du client.

---

## Chemin de recherche de paquets

La recherche de paquets suit un flux de requête/réponse différent :

```text
Browser
   │
   │ search request
   ▼
LUMS Server
   │
   │ package-search request
   ▼
Linux Client
   │
   │ APT / pacman search
   ▼
Linux Client
   │
   │ search result
   ▼
LUMS Server
   │
   ▼
Browser
```

Le serveur n'a donc pas besoin de maintenir un index complet de référentiel de paquets distant pour chaque client.

La recherche est effectuée à l'aide de l'environnement de gestion des paquets du client.

---

## Chemin d'exécution des mises à jour

Un job de mise à jour suit l'architecture générale :

```text
Browser
   │
   │ create job
   ▼
LUMS API
   │
   │ validate request
   ▼
SQLite
   │
   │ persistent job
   ▼
Linux Client
   │
   │ execute action
   ▼
APT / dpkg / pacman
   │
   │ result
   ▼
Linux Client
   │
   │ validated result
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Browser
```

Cela crée la chaîne d'exécution centrale de LUMS :

> **Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI**

---

## Revendication atomique des jobs

Les jobs de mise à jour sont des objets persistants côté serveur.

Avant l'exécution, l'agent doit obtenir un job éligible à l'exécution.

La revendication des jobs est effectuée de manière atomique afin que le même job en attente ne soit pas involontairement revendiqué par plusieurs chemins d'exécution.

Ceci est particulièrement important lorsque des timers, des nouvelles tentatives, une récupération ou plusieurs processus côté client sont impliqués.

---

## Exécution des jobs

Le serveur crée des jobs structurés.

L'agent client interprète les actions de job prises en charge et exécute l'opération locale correspondante.

Les actions de paquet prises en charge sont :

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Les noms de paquets sont validés avant la création d'un job de paquet.

L'agent ne traite pas les noms de paquets comme des fragments shell arbitraires.

---

## Abstraction du gestionnaire de paquets

Les opérations sur les paquets sont délibérément implémentées derrière une abstraction du gestionnaire de paquets.

Cela maintient le modèle de job LUMS de niveau supérieur indépendant des commandes spécifiques à la distribution.

Par exemple :

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

Le même principe s'applique à la suppression et aux mises à jour de paquets.

---

## Debian / Ubuntu

Sur les systèmes de la famille Debian, LUMS utilise les outils natifs APT/dpkg.

Les responsabilités typiques comprennent :

* recherche de paquets
* recherche de métadonnées de paquets
* installation de paquets
* suppression de paquets
* mises à jour de paquets
* mises à jour système
* détection des mises à jour

L'agent LUMS ne remplace pas APT.

Il fournit une orchestration contrôlée autour de celui-ci.

---

## Arch Linux

Sur les systèmes Arch Linux, LUMS utilise le gestionnaire de paquets natif pacman.

Les responsabilités typiques comprennent :

* recherche de paquets
* recherche de métadonnées de paquets
* installation de paquets
* suppression de paquets
* mises à jour de paquets
* mises à jour système
* détection des mises à jour

Le comportement spécifique à la distribution reste à l'intérieur de la couche gestionnaire de paquets.

---

## Recherche de paquets

La recherche de paquets est séparée de l'inventaire des logiciels installés.

Cette distinction est importante :

```text
Installed Software
        │
        └── What is already installed?

Package Management Search
        │
        └── What package can the client currently find?
```

Les résultats de recherche peuvent contenir des informations sur les paquets telles que :

* nom du paquet
* version
* description
* informations de référentiel lorsque disponibles

Les résultats de recherche sont renvoyés au serveur LUMS et affichés dans l'interface de gestion des paquets.

---

## Permissions de gestion des paquets

La gestion des paquets est une opération privilégiée.

Le modèle de permissions actuel est :

```text
Administrator → allowed
Operator      → allowed
Viewer        → not allowed
```

Un Viewer peut toujours inspecter les logiciels installés.

L'interface de gestion des paquets elle-même est masquée pour les Viewers, et les points de terminaison de mutation côté serveur correspondants appliquent l'autorisation indépendamment.

---

## Traitement des résultats de mise à jour

LUMS traite le résultat d'une opération de mise à jour comme un état structuré plutôt que de simplement afficher la sortie de commande brute.

Les informations pertinentes peuvent inclure :

* succès ou échec
* résultat au niveau du paquet
* état d'exécution
* informations d'erreur
* exigence de redémarrage
* horodatages d'achèvement

Cela permet au serveur de maintenir un historique de mise à jour significatif.

---

## Détection de redémarrage

Après les opérations sur les paquets, le client vérifie si l'opération indique qu'un redémarrage est nécessaire.

Le résultat est rapporté au serveur dans le cadre du résultat du job.

Une exigence de redémarrage reste donc associée à l'opération de mise à jour au lieu d'être perdue dans une session de terminal côté client.

---

## Frontière d'authentification des clients

L'API client utilise un mécanisme d'authentification distinct des sessions web administratives.

```text
Administrative User
        │
        ▼
 Web Authentication
        │
        ▼
    LUMS Server

Linux Client
        │
        ▼
 Client Token
        │
        ▼
    LUMS Server
```

Cette séparation empêche les sessions de navigateur administratives et les identifiants clients de devenir des mécanismes d'authentification interchangeables.

---

## Piste d'audit

Les actions relatives à la sécurité et administratives sont enregistrées par le système d'audit côté serveur.

La piste d'audit complète la journalisation applicative normale.

La journalisation répond aux questions sur le comportement de l'application.

La journalisation d'audit enregistre en outre les actions administratives importantes et leur contexte.

Cette distinction est utile lors de l'investigation des modifications apportées aux clients, aux utilisateurs, à l'état d'authentification ou aux jobs de mise à jour.

---

## Principe opérationnel

LUMS sépare délibérément :

```text
Management
     │
     ▼
Policy / Authorization
     │
     ▼
Job
     │
     ▼
Client Execution
     │
     ▼
Native Package Manager
```

Chaque couche a une responsabilité définie.

Le serveur gère.

L'agent exécute.

Le gestionnaire de paquets effectue le changement système réel.

Le résultat revient par la même chaîne contrôlée.

## Contrôle d'accès basé sur les rôles

LUMS utilise trois rôles administratifs :

```text
Administrator
Operator
Viewer
```

L'autorisation est appliquée côté serveur.

Le frontend adapte en outre l'interface visible aux permissions de l'utilisateur, mais la visibilité frontend n'est jamais considérée comme une frontière de sécurité.

### Administrator

Les administrateurs ont accès à :

* afficher les clients
* afficher les logiciels installés
* afficher les mises à jour disponibles
* créer et exécuter des jobs de mise à jour
* afficher l'historique des mises à jour
* utiliser la gestion des paquets
* effectuer la maintenance système
* créer et désactiver des clients
* faire tourner les tokens clients
* créer et gérer des utilisateurs
* gérer les rôles et l'accès des utilisateurs

### Operator

Les opérateurs ont accès à :

* afficher les clients
* afficher les logiciels installés
* afficher les mises à jour disponibles
* créer et exécuter des jobs de mise à jour
* afficher l'historique des mises à jour
* utiliser la gestion des paquets
* effectuer la maintenance système

Les opérateurs n'ont pas accès à :

* la gestion des utilisateurs
* l'administration des rôles
* la création ou la désactivation des clients
* la rotation des tokens clients

### Viewer

Les Viewers ont un accès en lecture seule à :

* clients
* logiciels installés

Les fonctionnalités suivantes ne sont pas disponibles pour les Viewers :

* gestion des mises à jour disponibles
* jobs de mise à jour
* historique des mises à jour
* gestion des paquets
* maintenance système
* autres opérations administratives modifiant l'état

Le serveur applique ces restrictions indépendamment.

---

## Gestion des utilisateurs

LUMS fournit la gestion des utilisateurs aux comptes disposant de la permission `users.manage`.

Les utilisateurs disposant de cette permission peuvent créer des comptes à l'aide d'un modèle de rôle, puis attribuer des permissions individuellement ou appliquer explicitement ce modèle. Les nouveaux comptes commencent sans permissions ; l'éditeur de permissions s'ouvre après la création. Les gestionnaires d'utilisateurs peuvent également enregistrer des notes administratives privées qui ne sont pas visibles pour le propriétaire du compte.

Les administrateurs disposant de `backups.manage` peuvent créer des sauvegardes de base de données `.db` ou `.db.gz` validées dans un répertoire configuré sur le serveur et choisir un sous-dossier sûr dans cet emplacement monté. Voir [`administration.md`](<Administration et sauvegardes.md>) et le guide de restauration Markdown intégré à l'application pour la configuration du stockage Docker et la récupération.

Les mots de passe utilisateur sont stockés à l'aide du hachage de mot de passe Argon2 plutôt qu'en clair ou avec un chiffrement réversible.

Les opérations de gestion des utilisateurs sont protégées par :

* l'authentification
* l'autorisation basée sur les permissions
* la protection CSRF
* la validation des entrées
* les vérifications de doublons d'utilisateurs
* la journalisation d'audit

L'interface de gestion des utilisateurs n'est pas exposée sans `users.manage`.

---

## Sécurité des sessions

L'authentification administrative utilise la gestion de session côté serveur.

La sécurité des sessions comprend :

* l'état de session authentifié
* la révocation des sessions
* la protection CSRF pour les demandes modifiant l'état
* la limitation du taux de connexion
* l'application des comptes désactivés
* les vérifications de rôle

La révocation d'une session invalide l'état authentifié correspondant plutôt que de simplement masquer l'interface utilisateur.

---

## Limitation du taux de connexion

Les tentatives de connexion échouées répétées sont soumises à une limitation progressive du taux.

Les seuils actuels sont :

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

L'état pertinent est persisté dans SQLite.

Une authentification réussie efface l'état d'échec applicable.

Cela empêche qu'un simple redémarrage de l'application soit utilisé pour contourner la protection de connexion.

---

## Sécurité des tokens clients

Chaque client enregistré possède son propre token d'authentification.

Le serveur stocke le token sous forme de condensé SHA-256.

Le token d'origine n'est pas requis pour la validation normale côté serveur.

La rotation des tokens permet aux administrateurs d'invalider un identifiant existant et d'en émettre un remplaçant.

Cela crée un cycle de vie clair :

```text
Create
  │
  ▼
Use
  │
  ▼
Rotate
  │
  ▼
Old token invalid
```

---

## Sécurité de l'API

LUMS valide les entrées de l'API avant d'effectuer des opérations modifiant l'état.

Les contrôles de sécurité comprennent :

* l'authentification
* l'autorisation par permission utilisateur
* la protection CSRF le cas échéant
* la validation des entrées
* la validation des noms de paquets
* les actions de job structurées
* les requêtes de base de données paramétrées
* la gestion contrôlée des erreurs

L'application n'utilise pas les noms de paquets fournis par l'utilisateur comme commandes shell non restreintes.

---

## Protection contre l'injection SQL

Les opérations de base de données utilisent des instructions SQL paramétrées.

Les valeurs contrôlées par l'utilisateur ne sont pas directement concaténées dans les requêtes SQL.

Cela s'applique à des domaines tels que :

* l'authentification
* la gestion des clients
* la gestion des utilisateurs
* les recherches de paquets
* les jobs de mise à jour
* les données d'audit
* la remontée des résultats

L'objectif est de garder les valeurs de données séparées des instructions SQL.

---

## Base de sécurité SQLite

La configuration SQLite de production actuelle est :

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

L'application des clés étrangères est explicitement activée par l'application pour les connexions à la base de données.

La configuration actuelle utilise le mode WAL.

La base de données est stockée dans le volume Docker persistant plutôt qu'à l'intérieur du système de fichiers du conteneur applicatif jetable.

---

## Récupération des jobs et points de contrôle

LUMS traite les jobs de mise à jour comme des machines à états persistantes.

Un job multi-paquets peut contenir plusieurs opérations individuelles sur les paquets.

Chaque élément de paquet peut atteindre son propre état de résultat.

Si l'exécution est interrompue, la récupération peut distinguer entre :

```text
already successful
        │
        └── do not unnecessarily repeat

not completed
        │
        └── eligible for recovery
```

Cela réduit le risque de répéter aveuglément les opérations sur les paquets terminées après une interruption.

---

## Exécution contrôlée des mises à jour

LUMS limite délibérément les actions qui peuvent être demandées via l'API des jobs de mise à jour.

Les actions prises en charge sont :

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Le serveur valide l'action et les informations de paquet pertinentes avant de créer le job.

L'agent mappe ensuite l'action structurée à l'opération appropriée du gestionnaire de paquets.

Cela évite de transformer le système de mise à jour en un mécanisme générique d'exécution de commandes à distance.

---

## Opérations sur les paquets

Les opérations sur les paquets sont exécutées via le gestionnaire de paquets natif du client.

### Installation

Un nom de paquet validé est passé à l'abstraction du gestionnaire de paquets pour l'installation.

### Suppression

Un nom de paquet validé est passé à l'abstraction du gestionnaire de paquets pour la suppression.

### Mise à jour de paquet

Un paquet spécifique peut être mis à jour lorsque le client le rapporte comme une mise à jour disponible.

### Mise à jour système

L'opération de mise à jour système délègue le processus de mise à jour au gestionnaire de paquets natif.

Toutes les opérations renvoient des résultats structurés au serveur LUMS.

---

## Sécurité du gestionnaire de paquets

LUMS traite le gestionnaire de paquets comme un composant local privilégié.

L'agent ne cherche donc pas à émuler lui-même le comportement du gestionnaire de paquets.

Au lieu de cela, il :

1. valide l'opération demandée
2. sélectionne l'implémentation appropriée du gestionnaire de paquets
3. exécute l'opération contrôlée
4. capture le résultat
5. rapporte le résultat au serveur

Le comportement spécifique à la distribution reste isolé à l'intérieur de la couche gestionnaire de paquets.

---

## Traitement des redémarrages

Certaines opérations sur les paquets peuvent nécessiter un redémarrage.

LUMS enregistre les exigences de redémarrage dans le cadre des résultats des jobs de mise à jour.

Cela permet aux administrateurs de distinguer entre :

```text
Update completed
```

et :

```text
Update completed
Reboot required
```

L'exigence de redémarrage fait donc partie de l'état opérationnel plutôt que d'être traitée comme une notification non liée.

---

## Journalisation d'audit

LUMS maintient une piste d'audit applicative pour les actions administratives et relatives à la sécurité importantes.

Les exemples incluent :

* événements liés à l'authentification
* gestion des clients
* opérations sur les tokens
* gestion des utilisateurs
* création de jobs de mise à jour
* changements d'état sensibles à la sécurité

La journalisation d'audit est séparée de la journalisation de diagnostic ordinaire.

Les journaux de diagnostic aident à dépanner l'application.

Les enregistrements d'audit fournissent un historique administratif des actions pertinentes.

---

## Durcissement de la sécurité

Le déploiement actuel comprend plusieurs couches de durcissement.

### Durcissement du conteneur

Le conteneur de production utilise :

* exécution applicative non-root
* système de fichiers racine en lecture seule
* capacités Linux abandonnées
* `no-new-privileges`
* systèmes de fichiers temporaires restreints
* montage secret en lecture seule
* volume de données persistant dédié

### Durcissement réseau

Le conteneur applicatif est lié au loopback sur l'hôte :

```text
127.0.0.1:5050
```

Le port applicatif n'est donc pas directement exposé en tant que service LAN.

L'accès externe est géré via le proxy inverse HTTPS.

Le pare-feu n'expose pas le port applicatif interne.

### Sécurité du transport

L'accès administratif est fourni via HTTPS.

Le proxy inverse gère la terminaison TLS externe.

Les requêtes HTTP sont redirigées vers HTTPS.

### Secrets et configuration

Les identifiants d'exécution sensibles sont conservés en dehors de l'arborescence source de l'application.

Le secret de production est monté dans le conteneur sous forme de fichier secret en lecture seule.

Les règles du référentiel et du contexte de build Docker empêchent les artefacts courants de sauvegarde, de secret, de base de données et de certificat d'entrer involontairement dans le contexte de build de l'image.

### Sécurité des dépendances et des builds

Les dépendances Python de production sont épinglées.

L'image de base Python de production est épinglée par condensé.

Le contexte de build Docker est restreint via `.dockerignore`.

Ces contrôles améliorent la reproductibilité des builds et réduisent l'inclusion accidentelle de fichiers sensibles.

---

## État de l'audit de sécurité

La revue de sécurité de LUMS a couvert les domaines suivants :

* application des clés étrangères SQLite
* configuration d'exécution SQLite
* délai d'attente des mises à jour et gestion des processus
* limitation du taux de connexion
* validation des entrées de l'API
* révocation des sessions
* rotation des tokens clients
* gestion hors ligne/IP
* récupération des jobs et points de contrôle
* robustesse d'APT
* détection de redémarrage Arch
* validation unitaire et des résultats de l'API
* tests de simulation
* intégration continue
* journalisation applicative et d'audit
* gestion du versioning et des versions
* RBAC
* sécurité des sessions et CSRF
* sécurité des identifiants
* sécurité des dépendances et des builds
* durcissement Docker/conteneur
* protection des secrets et du contexte de build
* sécurité HTTP/transport
* permissions du système de fichiers/d'exécution
* exposition réseau
* hygiène des artefacts du référentiel

La documentation doit être mise en cohérence avec l'implémentation lorsque le code ou le comportement du déploiement change, afin qu'elle décrive le système réellement présent.

---

## Tests et CI

LUMS comprend des tests automatisés couvrant le comportement principal de l'application et les contrôles de sécurité.

Exécutez la suite de tests complète depuis la racine du référentiel :

```bash
./.venv-test/bin/pytest -q
```

Le nombre de tests change au fil du temps. Le résultat requis est que la suite complète se termine avec succès sans échec. La suite de tests comprend une couverture pour des domaines tels que :

* l'authentification
* RBAC
* la gestion des clients
* la gestion des utilisateurs
* la recherche de paquets
* les jobs de mise à jour
* la validation des résultats des jobs
* le comportement de sécurité
* le comportement de l'API

L'intégration continue exécute la suite de tests automatisés avant que les modifications ne soient considérées comme prêtes.

Une exécution de tests réussie est requise, mais les tests ne sont qu'une partie du processus de version.

Le processus de version nécessite également :

```text
Implementation
    ↓
Security Review
    ↓
Documentation Review
    ↓
Full Test Suite
    ↓
CI
    ↓
Version
    ↓
Git Tag
    ↓
GitHub Release
```

---

## État du développement

LUMS est actuellement en développement actif.

L'architecture de gestion centrale, le modèle d'exécution client, la gestion des paquets, RBAC, le durcissement de la sécurité et les mécanismes de récupération sont implémentés.

Le projet n'est intentionnellement pas considéré comme une version finie simplement parce que l'application est fonctionnelle.

La préparation à la version nécessite également que la documentation environnante et les procédures opérationnelles décrivent le même système actuel.

C'est pourquoi la cohérence de la documentation est traitée comme faisant partie du processus d'ingénierie plutôt que comme une réflexion après coup.

## Systèmes pris en charge

LUMS est conçu pour gérer les systèmes Linux utilisant des gestionnaires de paquets natifs pris en charge.

### Debian / Ubuntu

Pile de gestion des paquets prise en charge :

```text
APT
dpkg
```

Le client utilise les outils natifs de gestion des paquets Debian pour :

* l'inventaire des paquets
* la détection des mises à jour
* la recherche de paquets
* l'installation de paquets
* la suppression de paquets
* les mises à jour de paquets
* les mises à jour système

### Arch Linux

Pile de gestion des paquets prise en charge :

```text
pacman
```

Le client utilise les outils natifs de gestion des paquets Arch pour :

* l'inventaire des paquets
* la détection des mises à jour
* la recherche de paquets
* l'installation de paquets
* la suppression de paquets
* les mises à jour de paquets
* les mises à jour système

---

## Exigences du client

Un client Linux géré nécessite :

* une distribution Linux prise en charge
* l'agent LUMS
* une connectivité réseau au serveur LUMS
* un token client enregistré
* un gestionnaire de paquets natif fonctionnel
* systemd pour les composants d'exécution basés sur timer/service

Le client ne nécessite pas que le serveur LUMS accède directement à sa base de données de paquets.

Le client effectue les opérations locales sur les paquets et rapporte les résultats au serveur.

---

## Pile technologique

### Serveur

* Python
* Flask
* Gunicorn
* SQLite
* HTML
* CSS
* JavaScript
* Nginx
* Docker

### Authentification et sécurité

* hachage des mots de passe Argon2
* sessions côté serveur
* protection CSRF
* modèles de rôles avec permissions par utilisateur
* condensés SHA-256 des tokens clients
* HTTPS
* journalisation d'audit

### Client

* Python
* systemd
* APT / dpkg
* pacman
* `loginctl` où les informations d'état d'inactivité sont disponibles

---

## Structure du projet

Le référentiel est organisé en composants serveur, client, frontend et tests séparés.

Une structure simplifiée est :

```text id="1rq7v7"
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   └── ...
│
├── tests/
│   ├── test_rbac.py
│   ├── test_package_search.py
│   ├── test_job_result.py
│   └── ...
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
└── documentation
```

La disposition exacte du référentiel peut évoluer au fur et à mesure que LUMS se développe.

La séparation architecturale entre le serveur, l'agent, l'abstraction du gestionnaire de paquets, le frontend et les tests est intentionnelle.

---

## Application serveur

L'application Flask fournit l'API LUMS centrale et l'interface web.

Ses responsabilités comprennent :

* l'authentification
* l'autorisation
* la gestion des sessions
* la gestion des clients
* la gestion des utilisateurs
* l'inventaire logiciel
* l'inventaire des mises à jour
* la recherche de paquets
* les jobs de mise à jour
* le traitement des résultats des jobs
* la journalisation d'audit
* la persistance de la base de données

L'application est servie par Gunicorn à l'intérieur du conteneur.

Nginx fournit le point d'entrée HTTPS externe.

---

## Agent

L'agent LUMS est installé directement sur les clients Linux gérés.

Version actuelle de l'agent :

```text id="w8p4wz"
1.7.0
```

L'agent est responsable de la partie côté client de la chaîne d'exécution LUMS.

Ses responsabilités comprennent :

* rapporter l'état du client
* collecter les logiciels installés
* détecter les mises à jour disponibles
* rechercher des paquets
* exécuter des opérations sur les paquets
* rapporter les résultats des jobs
* détecter les exigences de redémarrage
* gérer les informations d'état d'inactivité
* participer à la récupération des jobs

L'agent ne fournit pas de shell distant non restreint.

---

## Couche gestionnaire de paquets

L'implémentation du gestionnaire de paquets isole le comportement spécifique à la distribution du reste de l'agent.

Conceptuellement :

```text id="zq8xq3"
Agent
  │
  ▼
Package Manager Interface
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

Cela permet au système de jobs de mise à jour de niveau supérieur de fonctionner avec des opérations structurées sans avoir besoin de connaître chaque commande spécifique à une distribution.

---

## Watcher

Le watcher d'exécution LUMS surveille les jobs qui doivent s'exécuter sur le client.

Version actuelle du watcher :

```text id="7k6w3s"
1.2.1
```

Le watcher fonctionne avec l'agent et l'état des jobs côté serveur.

Cette architecture permet à LUMS de détecter les situations d'exécution où un job reste en attente ou nécessite autrement une attention.

---

## Intégration systemd

Le client utilise systemd pour l'exécution planifiée et contrôlée.

Les composants pertinents comprennent les unités de service et de timer pour :

* la remontée des clients
* la détection des mises à jour
* l'exécution/surveillance des jobs

Cela fournit une exécution prévisible sans nécessiter un processus de premier plan constamment en cours pour chaque opération périodique.

L'agent client peut également être exécuté manuellement lors de l'installation et du dépannage.

---

## Exécution consciente de l'inactivité

L'exécution consciente de l'inactivité est conçue pour réduire l'interférence avec les utilisateurs actifs.

Le seuil d'inactivité actuel est :

```text id="g8v0lq"
300 seconds
```

Le client détermine l'état d'inactivité à l'aide des informations de session locales disponibles.

Lorsque cela est pris en charge, `loginctl` est utilisé.

L'agent distingue entre :

```text id="6v3m4k"
confirmed idle
active
idle state unavailable
```

Un état d'inactivité indisponible n'est pas silencieusement interprété comme inactif.

Cela rend la décision d'exécution explicite et diagnosticable.

---

## Cycle de vie des jobs de mise à jour

Le cycle de vie complet d'un job de mise à jour peut être représenté comme :

```text id="h4d9kv"
Create
  │
  ▼
Validate
  │
  ▼
Persist
  │
  ▼
Claim
  │
  ▼
Execute
  │
  ├──────────────► SUCCESS
  │
  ├──────────────► FAILED
  │
  └──────────────► RECOVERY
                         │
                         ▼
                      Execute
```

Un job est persisté avant l'exécution.

Cela signifie que le serveur conserve la connaissance de l'opération prévue même si le client ou l'application est interrompu.

---

## Types de jobs

LUMS prend actuellement en charge des actions de mise à jour structurées, notamment :

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Ces actions sont intentionnellement limitées.

LUMS est un système de gestion des mises à jour, pas un framework de commandes distantes à usage général.

---

## État du job au niveau des paquets

Les jobs contenant plusieurs paquets peuvent suivre la progression au niveau des paquets.

Par exemple :

```text id="v9w1sh"
Job #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

La récupération peut donc opérer sur les portions incomplètes du job plutôt que de répéter aveuglément les opérations réussies sur les paquets.

---

## Récupération des jobs

La récupération est conçue autour de points de contrôle persistants.

Le serveur maintient l'état du job.

Le client rapporte les résultats au niveau des paquets.

Si l'exécution est interrompue, le serveur peut déterminer quel travail est déjà terminé et quel travail reste éligible à la récupération.

Le principe de récupération prévu est :

> **Continuer à partir de l'état connu au lieu de supposer que rien ne s'est passé.**

---

## Validation des résultats

Les résultats des jobs clients sont validés avant d'être acceptés dans l'état persistant du serveur.

Cela protège l'état du job contre les soumissions de résultats mal formés ou incomplets.

La validation est appliquée aux champs pertinents tels que :

* l'identité du job
* l'état d'exécution
* les données de résultat des paquets
* les informations d'erreur
* les informations de redémarrage

La couche de traitement des résultats agit donc comme une autre frontière entre un client authentifié et l'état persistant du serveur.

---

## Gestion des utilisateurs

La gestion des utilisateurs nécessite la permission `users.manage`.

Les utilisateurs autorisés peuvent créer des utilisateurs à partir d'un modèle de rôle et personnaliser les permissions individuelles attribuées à chaque compte.

Les rôles actuels sont :

```text id="2xqv79"
Administrator
Operator
Viewer
```

Les actions de gestion des utilisateurs sont authentifiées, vérifiées en termes de permissions, validées, protégées contre CSRF le cas échéant et enregistrées dans la piste d'audit.

---

## Gestion des clients

Les administrateurs peuvent gérer les clients enregistrés.

Les fonctions de gestion des clients comprennent :

* l'enregistrement
* la désactivation
* la rotation des tokens
* l'inspection de l'état des clients

L'authentification des clients est indépendante pour chaque client enregistré.

La désactivation d'un client l'empêche de poursuivre la communication authentifiée normale avec le serveur.

---

## Historique des mises à jour

LUMS maintient l'état persistant des jobs de mise à jour afin que les opérations terminées et échouées restent visibles après l'exécution.

Les utilisateurs autorisés peuvent inspecter l'historique des opérations de mise à jour en fonction de leur rôle.

L'historique est destiné à fournir un contexte opérationnel plutôt que de simplement afficher le dernier inventaire des paquets.

---

## Auditabilité

LUMS maintient deux formes d'informations opérationnelles liées mais distinctes :

### Journaux applicatifs

Utilisés principalement pour :

* les diagnostics
* les erreurs
* le comportement d'exécution
* le dépannage

### Journaux d'audit

Utilisés principalement pour :

* les actions administratives
* les événements relatifs à la sécurité
* les changements d'état importants
* la responsabilité

Garder ces concepts séparés facilite le dépannage et la revue administrative.

---

## Stratégie de test

La suite de tests LUMS couvre plusieurs couches de l'application.

### Authentification

Les tests couvrent le comportement d'authentification, la gestion des sessions et les contrôles de sécurité.

### RBAC

Les tests vérifient que :

* les administrateurs peuvent effectuer des actions administratives
* les opérateurs reçoivent leurs fonctions de gestion autorisées
* les viewers restent en lecture seule

### Gestion des paquets

Les tests couvrent le comportement de recherche de paquets et la gestion de l'API liée à la gestion des paquets.

### Jobs de mise à jour

Les tests couvrent :

* la création de jobs
* la validation
* les transitions d'état
* le traitement des résultats
* le comportement de récupération

### Sécurité

Les tests couvrent le comportement de l'application sensible à la sécurité et les cas de régression.

### Suite complète

Exécutez la suite de tests complète depuis la racine du référentiel :

```bash
./.venv-test/bin/pytest -q
```

Le nombre de tests change au fur et à mesure que le projet évolue ; fiez-vous au résultat de la commande, pas à un nombre fixe imprimé dans ce document.

---

## Intégration continue

Le projet utilise l'intégration continue pour exécuter des vérifications automatisées sur les modifications.

Le pipeline CI aide à détecter les régressions avant que les modifications ne soient considérées comme prêtes pour la version.

Le flux de développement est donc :

```text id="v3n9k8"
Change
  ↓
Test
  ↓
Security Review
  ↓
Documentation Review
  ↓
CI
  ↓
Release Preparation
```

Une exécution CI réussie ne remplace pas la revue manuelle de sécurité ou de documentation.

---

## Documentation

LUMS maintient une documentation séparée pour différentes préoccupations opérationnelles.

### `README.md`

Aperçu du projet, architecture, fonctionnalités, base de sécurité, état du développement et direction du projet.

### `install.md`

Procédures d'installation, de déploiement, de configuration client, de validation, de mise à niveau et de suppression.

### `administration.md`

Administration de routine, maintenance, sauvegardes, mises à niveau, procédures opérationnelles et administration d'urgence.

### `security.md`

Architecture de sécurité, contrôles de sécurité, résultats d'audit, durcissement et informations de sécurité pour la préparation à la version.

### `troubleshooting.md`

Procédures de diagnostic pour les problèmes de serveur, client, jobs, gestion des paquets, authentification, base de données, conteneur et réseau.

### `LUMS_Optional_Theme_System.md`

Architecture et conseils de maintenance pour les thèmes frontend LUMS facultatifs.

La documentation est intentionnellement séparée par responsabilité afin que les instructions opérationnelles ne se mélangent pas avec la conception de sécurité ou la personnalisation visuelle.

---

## Principe de documentation

La documentation est traitée comme faisant partie du système.

Une fonctionnalité n'est pas considérée comme complètement terminée lorsque le code fonctionne mais que la documentation décrit encore une architecture plus ancienne.

La relation prévue est :

```text id="0m1m5u"
Implementation
      │
      ├── Tests
      ├── Security Review
      └── Documentation
               │
               ▼
          Release Ready
```

Ceci est particulièrement important pour les procédures de déploiement et d'administration sensibles à la sécurité.

## État actuel

LUMS est une plateforme de gestion des mises à jour Linux en développement actif.

L'implémentation actuelle comprend :

* la gestion centralisée des clients
* l'inventaire logiciel
* la détection des mises à jour
* la recherche de paquets
* l'installation et la suppression de paquets
* les mises à jour spécifiques aux paquets
* les mises à jour système
* les jobs de mise à jour persistants
* l'état des jobs au niveau des paquets
* la récupération des jobs
* la détection de redémarrage
* l'exécution consciente de l'inactivité
* l'authentification par token client
* la rotation des tokens
* l'authentification administrative
* le contrôle d'accès basé sur les rôles
* la gestion des utilisateurs
* la journalisation d'audit
* le durcissement du conteneur
* le transport HTTPS
* les tests automatisés
* l'intégration continue
* la télémétrie facultative du processeur, de la mémoire, des disques, du réseau, de l'hôte et des événements
* la topologie de l'infrastructure à partir des clients enregistrés et de l'inventaire géré manuellement
* les enregistrements d'alerte persistants et les points de terminaison de gestion des règles, avec les limites décrites dans `docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`

Cette liste est un inventaire de haut niveau, et non une affirmation d'exhaustivité fonctionnelle ou de préparation à une release. Les composants facultatifs peuvent nécessiter une installation et une configuration séparées, et certaines fonctions ont des limites documentées. Pour connaître le comportement d'une release précise, consultez la révision du code source et ses tests.

---

## État de sécurité

Les principaux domaines de revue de sécurité ont été implémentés et examinés.

La base de sécurité actuelle comprend :

```text
Authentication
    ├── Argon2 password hashing
    ├── session handling
    ├── session revocation
    └── login rate limiting

Authorization
    ├── Administrator
    ├── Operator
    └── Viewer

Client Security
    ├── per-client tokens
    ├── SHA-256 token digests
    └── token rotation

API Security
    ├── input validation
    ├── CSRF protection
    ├── RBAC enforcement
    └── parameterized SQL

Runtime Security
    ├── non-root container
    ├── read-only root filesystem
    ├── dropped capabilities
    ├── no-new-privileges
    ├── restricted temporary filesystems
    └── protected secret mount

Network Security
    ├── HTTPS
    ├── reverse proxy
    ├── loopback application binding
    └── firewall restrictions
```

La sécurité est traitée comme une responsabilité d'ingénierie continue plutôt que comme une liste de contrôle ponctuelle.

---

## Processus de release

```text id="f3c4y9"
Implementation
      ↓
Security Review
      ↓
Documentation Review
      ↓
Full Test Suite
      ↓
CI
      ↓
Version Assignment
      ↓
Git Tag
      ↓
GitHub Release
```

La disponibilité des releases et des tags peut évoluer indépendamment de cette documentation ; consultez la page Releases et les tags actuels du dépôt. Une release ne doit être publiée qu'une fois terminés l'implémentation, la revue de sécurité, la documentation et les tests de régression de la révision concernée.

---

## Feuille de route

La feuille de route est intentionnellement axée sur la stabilité et la maintenabilité plutôt que sur l'ajout de fonctionnalités sans compléter la fondation existante.

### Développement futur

Les travaux futurs potentiels peuvent inclure :

* distributions Linux supplémentaires
* backends de gestionnaires de paquets supplémentaires
* améliorations supplémentaires de l'interface utilisateur
* capacités de reporting supplémentaires
* automatisation opérationnelle étendue
* contrôles de sécurité supplémentaires
* couverture de test supplémentaire

Les fonctionnalités futures devraient préserver les frontières architecturales existantes.

---

## Ce que LUMS n'est pas

LUMS n'est intentionnellement pas conçu comme :

* un shell distant à usage général
* un remplacement d'APT, dpkg ou pacman
* une plateforme complète de gestion de configuration
* une suite de gestion des points de terminaison pour tous les systèmes d'exploitation
* un service uniquement cloud
* un framework d'exécution de commandes non contrôlé

LUMS se concentre sur un problème plus étroit :

> **Gestion contrôlée des logiciels et des mises à jour Linux avec état persistant et auditabilité.**

---

## Philosophie de développement

LUMS suit un cycle de développement simple :

```text id="8a0mve"
Build
  ↓
Test
  ↓
Secure
  ↓
Document
```

Une fonctionnalité n'est pas considérée comme terminée simplement parce qu'elle fonctionne dans l'environnement du développeur.

Elle devrait également être :

* testée
* revue en termes de sécurité
* documentée
* reproductible
* compréhensible
* récupérable le cas échéant

---

## Philosophie du changement

Les changements devraient être effectués délibérément.

Un changement typique devrait répondre :

1. Quel problème cela résout-il ?
2. Quel composant devrait posséder le changement ?
3. Le changement affecte-t-il la sécurité ?
4. Affecte-t-il l'état persistant ?
5. Affecte-t-il les clients ?
6. Nécessite-t-il des modifications de documentation ?
7. Quels tests prouvent que la fonctionnalité existante fonctionne toujours ?

Cela réduit le risque de corriger une partie du système tout en cassant silencieusement une autre.

---

## Flux de développement

Le flux de développement préféré est :

```text id="r8u6o1"
Understand
   ↓
Implement
   ↓
Test
   ↓
Inspect
   ↓
Harden
   ↓
Document
   ↓
Regression Test
```

Les changements sensibles à la sécurité reçoivent une vérification supplémentaire avant d'être considérés comme terminés.

---

## Référentiel

Le référentiel du projet est hébergé sur GitHub :

**NovaForgeCtrl/LUMS**

Le référentiel contient le code source de l'application, les composants clients, les tests, la configuration du conteneur et la documentation du projet.

---

## Ensemble de documentation

L'ensemble de documentation actuel se compose de :

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Chaque document a un but défini.

Le README fournit l'aperçu au niveau du projet.

Le guide d'installation explique le déploiement.

Le guide d'administration explique l'opération continue.

Le guide de sécurité documente l'architecture de sécurité et l'état de l'audit.

Le guide de dépannage fournit les procédures de diagnostic.

Le document sur les thèmes facultatifs couvre l'architecture des thèmes frontend.

---

## Licence

LUMS est publié sous la licence MIT.

La licence vise à maintenir le projet ouvert et accessible tout en permettant l'utilisation, la modification et la redistribution selon les termes de la licence.

Voir le fichier de licence du référentiel pour le texte juridique complet.

---

## Communauté et contributions

LUMS est un projet open source et les contributions sont les bienvenues.

Les contributions utiles peuvent inclure :

* rapports de bogues
* rapports de sécurité
* améliorations de la documentation
* tests
* support de gestionnaires de paquets
* améliorations frontend
* améliorations backend
* améliorations de déploiement

Les contributions devraient préserver les principes architecturaux et de sécurité du projet.

---

## Rapports de sécurité

Les problèmes de sécurité ne doivent pas être traités comme des demandes de fonctionnalités ordinaires.

Lors de la signalisation d'un problème de sécurité, fournissez suffisamment d'informations pour reproduire et comprendre le problème sans exposer inutilement des informations sensibles.

Les modifications liées à la sécurité devraient être examinées attentivement avant d'être fusionnées.

---

## Identité du projet

LUMS est construit autour d'une idée simple :

> **Gestion des mises à jour Linux sans le bruit.**

Le projet ne cherche pas à masquer la complexité en prétendant que la gestion des paquets Linux est simple.

Au lieu de cela, il rend l'état pertinent visible :

```text id="q2j5r0"
What is installed?
        ↓
What can be updated?
        ↓
What should change?
        ↓
Who requested it?
        ↓
What actually happened?
        ↓
What state remains?
```

Ces informations constituent la base d'une gestion contrôlée des mises à jour.

---

## Architecture finale

À son niveau le plus élevé, LUMS peut être compris comme cinq couches :

```text id="7b4p6n"
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Human interaction and visibility        │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│    Authentication, authorization, validation  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                  Persistence                   │
│       Jobs, clients, users, results, audit   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agent                      │
│      Local execution and system reporting     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Native Linux Tools               │
│              APT / dpkg / pacman             │
└───────────────────────────────────────────────┘
```

Chaque couche a une responsabilité spécifique.

L'interface utilisateur fournit l'interaction.

L'API applique la politique.

SQLite fournit l'état persistant.

L'agent effectue l'exécution contrôlée côté client.

Le gestionnaire de paquets natif effectue le changement système réel.

---

## Principe final

LUMS est construit autour d'un principe central :

> **Observer le système. Contrôler le changement. Enregistrer le résultat.**

Ce principe s'applique à l'architecture logicielle, à l'exécution des mises à jour, au modèle de sécurité, aux mécanismes de récupération et à la documentation.

**Gestion des mises à jour Linux sans le bruit.**
