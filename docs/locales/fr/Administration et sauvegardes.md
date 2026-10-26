# LUMS — Guide d'administration

> **Gestion des mises à jour Linux sans le bruit.**

Ce guide décrit l'administration et l'exploitation quotidiennes de LUMS après l'installation du serveur et des clients.

Il se concentre sur les tâches administratives effectuées via l'interface web de LUMS et sur les tâches opérationnelles contrôlées sur le serveur LUMS et les clients gérés.

Les procédures d'installation sont documentées séparément dans `install.md`.

Les procédures de dépannage sont documentées séparément dans `troubleshooting.md`.

L'architecture de sécurité et les informations d'audit sont documentées séparément dans `security.md`.

---

## Pour commencer : Administration quotidienne

Ce guide est destiné à la personne responsable d'une installation LUMS existante. Les sections techniques détaillées sont maintenues en anglais. Commencez par ces termes :

* **Compte utilisateur :** détermine ce qu'une personne peut faire dans l'interface web LUMS. Ne partagez pas de comptes ; donnez à chaque personne son propre compte.
* **Client :** un ordinateur Linux géré. Son token client est un secret et n'est pas identique à un mot de passe de compte web.
* **Job de mise à jour :** une opération demandée que l'agent récupère et exécute à l'aide d'APT ou de pacman sur l'ordinateur cible. Vérifiez la cible et les paquets avant de le démarrer.
* **Sauvegarde :** une copie séparée et vérifiée de la base de données. Une copie dans le même volume Docker ne protège pas contre la perte de ce volume.
* **Mise à niveau :** remplace la version du conteneur, pas la base de données. Une mise à niveau normale ne doit pas supprimer ni recréer `lums-data`.

### Liste de contrôle sécurisée avant toute modification

1. Vérifiez si des jobs de mise à jour sont en cours et si une fenêtre de maintenance est nécessaire.
2. Confirmez qu'une sauvegarde récente et utilisable de la base de données existe.
3. Enregistrez l'image en cours d'exécution, les paramètres du conteneur et les chemins de données.
4. Construisez et testez la nouvelle image avant d'arrêter le conteneur actif.
5. Remplacez le conteneur avec les mêmes montages de données, de secret et de sauvegarde et les mêmes options de sécurité.
6. Vérifiez l'état du conteneur, les journaux, la connexion HTTPS et les données après le démarrage.
7. Conservez l'ancien conteneur comme option de retour arrière jusqu'à ce que la nouvelle version ait été vérifiée.

**N'exécutez pas** `docker volume rm lums-data`, `docker system prune --volumes` ou d'autres commandes de suppression dans le cadre d'une mise à niveau normale. Elles peuvent supprimer définitivement des données. Si vous n'êtes pas sûr du conteneur ou du chemin actif, arrêtez-vous et inspectez d'abord la configuration actuelle ; ne copiez pas une commande d'exemple sans l'avoir vérifiée.

---

## 1. Aperçu de l'administration

LUMS fournit une administration centralisée de l'inventaire logiciel Linux, des mises à jour disponibles, des opérations sur les paquets, des jobs de mise à jour, des clients gérés, des utilisateurs et de l'historique opérationnel.

L'interface administrative propose trois modèles de rôles :

* **Administrator**
* **Operator**
* **Viewer**

Lorsqu'un compte est créé, le rôle sélectionné remplit un ensemble recommandé de permissions. Les administrateurs peuvent ajuster ces permissions par utilisateur ; les permissions enregistrées, plutôt que l'étiquette de rôle, déterminent l'accès.

LUMS sépare également les opérations administratives côté serveur de l'exécution des paquets côté client.

Le flux opérationnel normal est :

```text
Administrator / Operator
        │
        ▼
   LUMS Web UI
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
   Managed Client
        │
        ▼
 APT / pacman / system
        │
        ▼
      Result
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
    Web Interface
```

Le serveur LUMS n'exécute pas directement les commandes de gestion des paquets sur les clients gérés.

Les opérations sur les paquets sont exécutées par l'agent LUMS installé sur le système géré.

---

## 2. Responsabilités administratives

L'administration de LUMS peut être divisée en plusieurs domaines.

### Administration des utilisateurs

Les administrateurs gèrent :

* les utilisateurs LUMS
* les rôles utilisateur
* l'état des comptes
* l'accès administratif

La gestion des utilisateurs nécessite la permission `users.manage`.

Le modèle Administrator inclut cette permission par défaut.

Les Operators et Viewers ne la reçoivent pas par défaut.

---

### Administration des clients

Les administrateurs gèrent :

* les clients enregistrés
* l'état des clients
* l'authentification des clients
* les tokens clients
* la rotation des tokens
* l'activation et la désactivation des clients

L'administration des clients nécessite la permission `clients.manage` car l'authentification des clients détermine quels systèmes sont autorisés à rapporter à LUMS.

---

### Administration des mises à jour

Les modèles Administrator et Operator accordent des permissions pour :

* afficher les mises à jour disponibles
* créer des jobs de mise à jour
* exécuter des opérations sur les paquets
* consulter l'historique des mises à jour
* gérer des paquets individuels
* effectuer des mises à jour système

Le modèle Viewer est en lecture seule et ne peut pas effectuer d'opérations de mise à jour.

---

### Administration des paquets

LUMS prend en charge les opérations de gestion des paquets via le gestionnaire de paquets natif du client.

Les backends de gestion de paquets actuellement pris en charge comprennent :

* **APT/dpkg** pour les systèmes basés sur Debian
* **pacman** pour Arch Linux

LUMS ne remplace pas le gestionnaire de paquets du système d'exploitation.

Au lieu de cela, LUMS fournit une interface centralisée pour demander et suivre les opérations sur les paquets.

---

### Administration opérationnelle

Les administrateurs et opérateurs peuvent avoir besoin de surveiller :

* les jobs de mise à jour en cours
* les jobs échoués
* les jobs terminés
* la remontée des clients
* les exigences de redémarrage
* les erreurs du gestionnaire de paquets
* l'activité d'audit

Les procédures de dépannage détaillées pour ces conditions sont documentées dans `troubleshooting.md`.

---

## 3. Rôles administratifs

LUMS propose actuellement trois rôles.

| Rôle          | Objectif                                        |
| ------------- | ----------------------------------------------- |
| Administrator | Contrôle administratif complet                  |
| Operator      | Gestion opérationnelle quotidienne              |
| Viewer        | Visibilité en lecture seule sur clients et logiciels |

Chaque rôle est un modèle de permissions. Les permissions enregistrées individuellement du compte sont appliquées côté serveur.

Le masquage d'un élément d'interface n'est donc pas considéré comme un contrôle de sécurité en soi.

Les opérations API non autorisées doivent également être rejetées par le serveur.

---

## 4. Administrator

Le modèle Administrator fournit par défaut l'ensemble complet des permissions de l'application LUMS.

Les administrateurs peuvent :

* afficher les clients gérés
* afficher les logiciels installés
* afficher les mises à jour disponibles
* créer et exécuter des jobs de mise à jour
* consulter l'historique des mises à jour
* effectuer des opérations de gestion des paquets
* effectuer la maintenance système
* créer des clients
* désactiver des clients
* faire tourner les tokens clients
* créer et gérer les utilisateurs LUMS
* attribuer des modèles de rôles et des permissions individuelles

Les permissions complètes du modèle Administrator ne doivent être accordées qu'aux utilisateurs qui en ont besoin.

Les comptes administratifs ne doivent pas être utilisés pour la surveillance en lecture seule de routine lorsqu'un compte Operator ou Viewer suffit.

---

## 5. Operator

Le modèle Operator est destiné à l'administration quotidienne des mises à jour et du système.

Les opérateurs peuvent :

* afficher les clients gérés
* afficher les logiciels installés
* afficher les mises à jour disponibles
* créer et exécuter des jobs de mise à jour
* consulter l'historique des mises à jour
* effectuer des opérations de gestion des paquets
* effectuer la maintenance système

Le modèle Operator n'accorde pas :

* créer ou gérer des utilisateurs LUMS
* attribuer des rôles utilisateur
* créer ou désactiver des clients
* faire tourner les tokens clients

Cette séparation par défaut permet les opérations de mise à jour de routine sans accorder de privilèges de gestion des comptes et des clients. Les attributions individuelles peuvent être modifiées par un utilisateur disposant de `users.manage`.

---

## 6. Viewer

Le modèle Viewer fournit une visibilité en lecture seule.

Les Viewers peuvent :

* afficher les clients gérés
* afficher les logiciels installés

Le modèle Viewer n'accorde pas les fonctions administratives suivantes :

* gestion des mises à jour disponibles
* création de jobs de mise à jour
* exécution de jobs de mise à jour
* historique des mises à jour
* gestion des paquets
* maintenance système
* gestion des utilisateurs
* gestion des clients
* rotation des tokens

Les opérations API mutatives correspondantes sont également protégées côté serveur.

L'accès Viewer est donc destiné aux utilisateurs qui ont besoin de visibilité sans contrôle opérationnel.

---

## 7. Directives de sélection des rôles

Utilisez le plus petit rôle qui fournit la fonctionnalité requise.

### Administrator

À utiliser lorsque l'utilisateur doit gérer :

* utilisateurs
* rôles
* clients
* authentification des clients
* tokens
* mises à jour
* paquets
* opérations système

### Operator

À utiliser lorsque l'utilisateur doit effectuer un travail opérationnel de routine tel que :

* vérifier les mises à jour
* installer des paquets
* supprimer des paquets
* mettre à jour des paquets
* exécuter des jobs de mise à jour
* consulter l'historique des jobs

### Viewer

À utiliser lorsque l'utilisateur a uniquement besoin de visibilité sur :

* clients
* logiciels installés

---

## 8. Principe de sécurité administrative

L'administration de LUMS suit le principe du moindre privilège.

L'accès administratif doit être limité à la fonctionnalité requise pour la tâche de l'utilisateur.

En particulier :

* n'utilisez pas de comptes Administrator pour la consultation de routine
* ne partagez pas de comptes entre administrateurs
* ne partagez pas de tokens clients
* ne placez pas d'identifiants dans la documentation
* n'exposez pas de tokens clients dans des captures d'écran ou des journaux
* ne contournez pas l'interface web LUMS en modifiant directement la base de données, sauf si une procédure de récupération documentée l'exige explicitement

Lorsqu'une opération administrative échoue, investigatez la cause avant de modifier l'état persistant.

Utilisez le principe :

> **Observer d'abord. Modifier ensuite. Vérifier en troisième.**

---

## 9. Flux de travail administratif

Un flux de travail administratif normal doit suivre cette séquence :

```text
1. Authenticate
      │
      ▼
2. Verify role
      │
      ▼
3. Select client / operation
      │
      ▼
4. Review current state
      │
      ▼
5. Perform required operation
      │
      ▼
6. Monitor job
      │
      ▼
7. Verify result
      │
      ▼
8. Review history / audit information
```

Les actions administratives doivent toujours être vérifiées après exécution.

Une requête API réussie ne prouve pas à elle seule que l'opération sur le paquet ou le système a réussi.

L'état final rapporté par le client géré est le résultat opérationnel pertinent.

---

## 10. Séparation de la documentation

L'ensemble de la documentation LUMS est intentionnellement divisé en guides opérationnels distincts.

| Document             | Objectif                                        |
| -------------------- | ----------------------------------------------- |
| `install.md`         | Installation et déploiement initial             |
| `administration.md`  | Administration quotidienne                      |
| `security.md`        | Architecture de sécurité et résultats d'audit   |
| `troubleshooting.md` | Diagnostic et récupération                      |

Ce guide doit donc éviter de dupliquer les procédures détaillées d'installation et de dépannage.

Au lieu de cela, il décrit ce que les administrateurs peuvent gérer, ce que signifie chaque opération et comment les flux de travail administratifs normaux sont effectués.

## 11. Gestion des utilisateurs

La gestion des utilisateurs est disponible pour les utilisateurs disposant de la permission `users.manage`.

Les administrateurs peuvent créer et gérer des comptes applicatifs LUMS via l'interface dédiée de gestion des utilisateurs.

Les comptes utilisateur sont séparés de l'authentification des clients gérés.

Un utilisateur LUMS s'authentifie auprès de l'application web avec un compte applicatif.

Un client géré s'authentifie auprès de l'API LUMS avec un token client.

Ces mécanismes d'authentification ne doivent pas être confondus.

```text
LUMS User
    │
    │ username + password
    ▼
Web Interface
    │
    ▼
LUMS Application

Managed Client
    │
    │ client token
    ▼
LUMS API
```

---

## 12. Création d'utilisateurs

Les utilisateurs disposant de `users.manage` peuvent créer de nouveaux utilisateurs LUMS.

Lors de la création d'un utilisateur, l'Administrator spécifie :

* nom d'utilisateur
* mot de passe
* une étiquette de rôle, avec un modèle de rôle disponible pour l'attribution ultérieure des permissions

Les modèles de rôles disponibles sont :

* `administrator`
* `operator`
* `viewer`

Le serveur valide les valeurs fournies avant de créer le compte.

Les nouveaux comptes démarrent sans permissions. Après la création, les administrateurs peuvent attribuer des cases à cocher individuelles ou appliquer l'un des modèles de rôles. L'application d'un modèle présélectionne ses permissions par défaut, qui peuvent ensuite être personnalisées. Les permissions disponibles sont :

| Permission        | Accès accordé                                       |
| ----------------- | --------------------------------------------------- |
| `clients.view`    | Afficher la liste des clients et les informations système |
| `software.view`   | Afficher les logiciels installés                    |
| `updates.view`    | Afficher les mises à jour, les jobs et l'historique |
| `packages.search` | Rechercher dans les référentiels de paquets         |
| `jobs.manage`     | Créer des opérations sur les paquets et des jobs de mise à jour |
| `clients.manage`  | Enregistrer/supprimer des clients et faire tourner les tokens clients |
| `users.manage`    | Créer des utilisateurs et gérer les rôles, permissions et notes internes |
| `backups.manage`  | Créer et inspecter des sauvegardes de base de données |

Les permissions liées aux clients nécessitent `clients.view` ; `jobs.manage` nécessite également `updates.view`. LUMS empêche la suppression du dernier compte actif disposant de `users.manage`, de sorte que les administrateurs ne peuvent pas se verrouiller accidentellement.

Les mots de passe ne sont pas stockés en clair.

LUMS utilise le hachage de mot de passe basé sur Argon2 pour les identifiants applicatifs.

Après la création, vérifiez que :

* le nom d'utilisateur apparaît dans la liste des utilisateurs
* le modèle de rôle et les permissions individuelles sont corrects
* le compte est activé
* l'utilisateur peut s'authentifier avec succès

Ne transmettez pas les mots de passe via la documentation, les tickets, les captures d'écran ou d'autres canaux non sécurisés.

---

## Interface de sauvegarde de base de données

Les utilisateurs disposant de la permission `backups.manage` peuvent créer des sauvegardes SQLite depuis **Sauvegardes de base de données**. Les comptes administrateurs reçoivent cette permission via la migration `005-backup-permission` ; les nouveaux comptes la reçoivent en appliquant le modèle Administrator ou peuvent la recevoir explicitement.

L'interface prend en charge les fichiers `.db` natifs et `.db.gz` compressés. Elle utilise l'API de sauvegarde en ligne de SQLite, valide la base de données terminée et stocke les fichiers avec des permissions réservées au propriétaire. L'UI liste les dix fichiers les plus récents. Les sauvegardes ne sont ni chiffrées, ni supprimées automatiquement, ni planifiées, ni téléchargées, ni restaurées par LUMS ; les administrateurs disposant de `backups.manage` peuvent supprimer des sauvegardes individuelles de la liste après confirmation. Protégez la destination en conséquence.

Le répertoire cible de base est fixé par le paramètre serveur `LUMS_BACKUP_DIR`. L'interface permet de choisir un sous-répertoire relatif sous cette base et le crée si nécessaire ; les chemins absolus, la traversée parente et les sous-répertoires liés symboliquement sont rejetés. Les chemins hôtes doivent être montés dans Docker par l'administrateur du serveur. Pour un déploiement Docker, créez un répertoire hôte séparé inscriptible par l'UID/GID `10001` du conteneur :

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/lums
```

Ajoutez ces options à la configuration du conteneur LUMS :

```bash
-v /var/backups/lums:/var/backups/lums \
-e LUMS_BACKUP_DIR=/var/backups/lums \
```

Utilisez un disque séparé ou un stockage distant pour la résilience face à une défaillance de l'hôte. Par exemple, montez d'abord un NAS sur l'hôte Debian, puis utilisez ce chemin monté comme côté gauche du montage de liaison Docker. L'UI de sauvegarde affiche le répertoire de base côté conteneur ; le chemin relatif sélectionné se trouve en dessous. La destination de sauvegarde doit être disponible et inscriptible à l'intérieur du conteneur ; sinon l'interface signale que le stockage de sauvegarde est indisponible.

Pour les étapes de restauration, voir [`server/static/backup-restore.md`](../../../server/static/backup-restore.md).

---

## 13. Rôles utilisateur

Sélectionnez un modèle de rôle en fonction du privilège minimum requis, puis examinez les permissions individuelles de chaque compte.

| Modèle de rôle | Gestion des utilisateurs | Gestion des clients | Mises à jour | Gestion des paquets | Accès en lecture seule |
| -------------- | -----------------------: | ------------------: | -----------: | ------------------: | ---------------------: |
| Administrator  |                      Oui |                 Oui |          Oui |                 Oui |                    Oui |
| Operator       |                      Non |                 Non |          Oui |                 Oui |                    Oui |
| Viewer         |                      Non |                 Non |          Non |                 Non |                    Oui |

Ce sont des valeurs par défaut, pas des frontières fixes. Les administrateurs peuvent personnaliser l'ensemble des permissions de chaque utilisateur. L'application des rôles s'effectue côté serveur via les permissions résultantes par utilisateur.

L'interface web reflète le rôle attribué, mais le serveur reste la frontière de sécurité faisant autorité.

---

## 14. Désactivation des comptes utilisateur

Lorsqu'un compte ne doit plus pouvoir accéder à LUMS, désactivez le compte plutôt que de partager ou de réaffecter les identifiants.

Les exemples incluent :

* un administrateur quittant le projet
* un opérateur n'ayant plus besoin d'accès
* suppression temporaire de l'accès administratif
* réponse de sécurité à un compte compromis

Après avoir désactivé un compte, vérifiez que l'authentification est rejetée.

Les sessions authentifiées existantes doivent également être prises en compte lors des investigations de sécurité des comptes.

Ne modifiez pas manuellement la table `users` sauf si une procédure de récupération documentée exige explicitement une intervention au niveau de la base de données.

---

## 15. Administration des mots de passe

Les mots de passe sont des identifiants applicatifs et doivent être traités comme des informations sensibles.

Les administrateurs doivent s'assurer que :

* les mots de passe ne sont pas partagés
* les mots de passe ne sont pas stockés dans Git
* les mots de passe ne sont pas placés dans la documentation
* les mots de passe ne sont pas inclus dans les captures d'écran
* les mots de passe ne sont pas écrits inutilement dans l'historique du shell
* les utilisateurs reçoivent leurs identifiants via un canal sécurisé approprié

LUMS stocke des hachages de mots de passe plutôt que des mots de passe en clair.

Si un mot de passe est suspecté d'être compromis, remplacez-le via la procédure de gestion de compte appropriée plutôt que de tenter de récupérer le mot de passe d'origine.

---

## 16. Sessions

LUMS utilise des sessions applicatives authentifiées pour l'accès web.

La gestion des sessions fait partie de la frontière de sécurité de l'application.

Les administrateurs doivent traiter une session authentifiée inattendue comme un événement de sécurité si le compte associé ne devrait plus avoir accès.

Les situations pertinentes comprennent :

* un compte désactivé apparaissant toujours actif
* un accès administratif inattendu
* une compromission d'identifiants suspectée
* une session de navigateur inattendue
* une investigation de sécurité

Pour le dépannage détaillé des sessions et de l'authentification, voir `troubleshooting.md`.

---

## 17. Limitation du taux de connexion

LUMS applique une limitation du taux aux tentatives de connexion échouées répétées.

La progression actuelle est :

| Tentatives échouées |     Verrouillage |
| ------------------: | ---------------: |
|                   5 |   30 secondes    |
|                   6 |   60 secondes    |
|                   7 |  120 secondes    |
|                 8+ |  300 secondes    |

L'état de limitation du taux est persisté dans SQLite.

Une connexion réussie efface l'état d'échec applicable.

Les échecs d'authentification répétés doivent être investigués plutôt que contourner le limiteur de taux.

Les causes possibles incluent :

* identifiants incorrects
* identifiants enregistrés obsolètes
* un client automatisé utilisant des identifiants incorrects
* tentatives de connexion manuelles répétées
* une possible attaque par identifiants

---

## 18. Gestion des clients

Les clients gérés sont des systèmes Linux exécutant l'agent LUMS.

Un client fournit à LUMS des informations telles que :

* identité du client
* logiciels installés
* mises à jour disponibles
* résultats de gestion des paquets
* résultats des jobs de mise à jour
* état de redémarrage
* état opérationnel

Le serveur LUMS stocke l'état du client et l'expose via l'interface web.

Le client effectue les opérations réelles de gestion des paquets localement.

---

## 19. Authentification des clients

Chaque client géré s'authentifie auprès de LUMS à l'aide d'un token client.

Le token agit comme un identifiant pour le client géré.

Traitez les tokens clients avec le même soin que les mots de passe.

Ne jamais :

* valider les tokens dans Git
* placer les tokens dans la documentation publique
* inclure les tokens dans les captures d'écran
* coller les tokens dans des trackers d'issues
* exposer les tokens dans la sortie de diagnostic
* partager le token d'un client avec un autre client

Un token ne doit être installé que sur le client pour lequel il a été émis.

---

## 20. Enregistrement des clients

Un nouveau client doit d'abord être enregistré auprès de LUMS.

Le processus d'enregistrement établit l'identité du client côté serveur et l'identifiant d'authentification.

Après l'enregistrement :

1. installez l'agent LUMS
2. configurez le token client
3. configurez le point de terminaison du serveur LUMS
4. établissez la confiance TLS
5. effectuez une exécution initiale de l'agent
6. vérifiez que le client rapporte avec succès
7. confirmez que le client apparaît dans l'interface LUMS

Un client ne doit pas être considéré opérationnel simplement parce que le service de l'agent démarre avec succès.

Le serveur doit recevoir et accepter un rapport client valide.

---

## 21. État du client

La vue client doit être utilisée pour distinguer les différents états opérationnels.

Les exemples incluent :

* client enregistré mais ne rapportant pas
* client rapportant normalement
* client rapportant des informations obsolètes
* client désactivé
* échec d'authentification du client
* échec du gestionnaire de paquets côté client

Lorsqu'un client cesse de rapporter, déterminez d'abord si le problème est :

1. la connectivité réseau
2. la confiance TLS
3. l'authentification du client
4. l'exécution de l'agent
5. la disponibilité du serveur
6. le traitement côté serveur

Évitez de modifier les identifiants du client avant d'avoir établi quelle couche échoue réellement.

---

## 22. Rotation des tokens clients

Les tokens clients peuvent être rotés lorsque nécessaire.

Les raisons typiques incluent :

* exposition suspectée du token
* politique de rotation des identifiants
* maintenance administrative
* remplacement d'une configuration client
* réponse à un incident de sécurité

La rotation des tokens modifie l'identifiant accepté pour le client.

Après la rotation :

1. obtenez le nouveau token client
2. mettez à jour la configuration du client
3. exécutez l'agent
4. vérifiez que l'authentification réussit
5. vérifiez le rapport client résultant
6. confirmez que la remontée normale reprend

Ne supprimez pas l'ancienne configuration client avant que le nouveau chemin d'authentification n'ait été vérifié.

---

## 23. Désactivation d'un client

Un client peut être désactivé lorsqu'il ne doit plus participer aux opérations LUMS.

Les exemples incluent :

* décommissionnement du système
* maintenance temporaire
* remplacement du client
* compromission d'identifiants suspectée

Avant de désactiver un client, vérifiez si des jobs de mise à jour actifs y sont associés.

Après la désactivation :

* vérifiez que le client n'est plus traité comme opérationnel
* examinez l'historique pertinent des jobs de mise à jour
* préservez les informations d'audit nécessaires à l'investigation

Ne supprimez pas les données persistantes du client simplement parce qu'un client est temporairement hors ligne.

---

## 24. Liste de contrôle de l'administration des clients

Lors de l'ajout ou de la modification d'un client, vérifiez la chaîne complète :

```text
[ ] Client exists in LUMS
[ ] Client is enabled
[ ] Client token is valid
[ ] TLS trust is valid
[ ] LUMS Agent is installed
[ ] Agent configuration is valid
[ ] Initial report succeeds
[ ] Client appears in the Web UI
[ ] Installed software is reported
[ ] Available updates are reported
[ ] Update jobs can be tracked
[ ] Results are returned correctly
```

Un client n'est opérationnel que lorsque la chaîne complète de remontée et d'authentification fonctionne.

---

## 25. Principe administratif

L'administration des utilisateurs et l'administration des clients doivent rester séparées.

Un compte applicatif LUMS détermine **ce qu'une personne est autorisée à faire**.

Un token client détermine **quel système géré est autorisé à communiquer avec LUMS**.

```text
Application User
      │
      └── Role / Permissions

Managed Client
      │
      └── Client Token / Identity
```

N'utilisez pas un mécanisme comme substitut de l'autre.

## 26. Inventaire logiciel

LUMS maintient les informations logicielles rapportées par les clients gérés.

L'inventaire logiciel permet aux administrateurs et opérateurs de déterminer quels paquets sont installés sur un client.

L'inventaire est collecté par l'agent LUMS et rapporté au serveur.

Le serveur rend ensuite les informations rapportées disponibles via l'interface client.

L'inventaire doit être traité comme un instantané de l'état rapporté par le client.

Il ne remplace pas le gestionnaire de paquets natif.

---

## 27. Logiciels installés

La section **Logiciels installés** affiche les paquets rapportés par le client sélectionné.

Les administrateurs et opérateurs peuvent utiliser le filtre de paquets local pour affiner l'inventaire affiché.

Le filtre des logiciels installés est une fonction d'interface locale.

Il est séparé de la recherche de gestion des paquets.

Cette distinction est importante :

```text
Installed Software
    │
    └── Filter already reported package inventory

Package Management
    │
    └── Search the client's package repositories
```

Un paquet installé peut donc ne pas apparaître dans la recherche de gestion des paquets s'il n'est plus disponible dans un référentiel configuré.

---

## 28. Mises à jour disponibles

LUMS collecte également des informations sur les paquets pour lesquels des mises à jour sont disponibles.

Les informations sur les mises à jour disponibles sont générées sur le client géré à l'aide de son système natif de gestion des paquets.

Les informations rapportées peuvent être utilisées pour identifier les paquets nécessitant une attention.

Avant de créer un job de mise à jour, examinez :

* l'identité du client
* le nom du paquet
* la version actuellement installée
* la version disponible
* l'état du paquet
* si le client est actuellement joignable

Ne supposez pas que chaque mise à jour disponible doit être immédiatement installée.

Les exigences opérationnelles, les fenêtres de maintenance, les dépendances applicatives et l'état du client doivent être pris en compte avant l'exécution.

---

## 29. Gestion des paquets

LUMS fournit des opérations centralisées de gestion des paquets pour les clients Linux pris en charge.

Les actions actuelles de gestion des paquets comprennent :

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

L'opération est demandée via LUMS mais exécutée localement par l'agent LUMS.

L'agent délègue l'opération réelle sur le paquet au gestionnaire de paquets natif.

```text
LUMS Web UI
      │
      ▼
LUMS API
      │
      ▼
Update Job
      │
      ▼
LUMS Agent
      │
      ├── APT / dpkg
      │
      └── pacman
```

LUMS reste donc indépendant de la base de données des paquets et de l'implémentation de gestion des paquets du système d'exploitation.

---

## 30. Recherche de paquets

L'interface **Gestion des paquets** fournit une recherche de paquets séparée du filtre des logiciels installés.

La recherche demande des informations sur les paquets au client géré.

Sur les systèmes basés sur Debian, l'agent utilise les outils de gestion des paquets APT.

Sur Arch Linux, l'agent utilise `pacman`.

Les résultats de recherche peuvent contenir :

* nom du paquet
* version du paquet
* description du paquet
* informations de référentiel lorsque disponibles

La recherche de paquets n'installe rien.

Une recherche est donc une opération en lecture seule.

---

## 31. Installation d'un paquet

Les administrateurs et opérateurs peuvent créer des jobs d'installation de paquets.

Le flux de travail normal est :

1. sélectionner le client géré
2. ouvrir **Gestion des paquets**
3. rechercher le paquet requis
4. examiner le résultat
5. sélectionner l'action d'installation
6. créer le job
7. surveiller l'exécution
8. vérifier le résultat
9. actualiser ou revérifier les logiciels installés

Le paquet est installé par l'agent à l'aide du gestionnaire de paquets natif.

La création réussie du job ne signifie pas que l'installation est déjà terminée.

Le résultat final du job doit être vérifié.

---

## 32. Suppression d'un paquet

La suppression de paquets suit le même flux de job contrôlé.

Avant de supprimer un paquet, vérifiez :

* le bon client
* le bon paquet
* l'opération prévue
* si d'autres logiciels dépendent du paquet

Après l'exécution, vérifiez l'état résultant du job et l'état logiciel rapporté par le client.

LUMS ne contourne pas la gestion des dépendances du gestionnaire de paquets.

Le gestionnaire de paquets natif reste responsable de la résolution de l'opération.

---

## 33. Mise à jour d'un paquet

Un paquet spécifique peut être mis à jour lorsqu'une mise à jour est disponible.

Le flux de travail est :

```text
Available Update
      │
      ▼
Review Package
      │
      ▼
Create UPDATE_PACKAGE Job
      │
      ▼
Agent Execution
      │
      ▼
Result Validation
```

LUMS valide les informations du paquet avant de créer le job de mise à jour correspondant.

Si le paquet n'est plus listé comme pouvant être mis à jour, la demande de job ne doit pas être traitée comme une opération de mise à jour valide.

Cela empêche l'exécution aveugle d'informations de mise à jour obsolètes.

---

## 34. Mise à jour du système

`UPDATE_SYSTEM` effectue une mise à jour système plus large à l'aide du mécanisme natif de gestion des paquets du client.

Cette opération affecte plus d'un paquet et doit donc être traitée comme une opération de maintenance.

Avant de démarrer une mise à jour système, vérifiez :

* la disponibilité du client
* la fenêtre de maintenance
* les jobs en cours d'exécution
* l'état du gestionnaire de paquets
* l'espace disque disponible le cas échéant
* si un redémarrage peut être nécessaire

Après la mise à jour, vérifiez :

* le résultat du job
* le rapport client
* les logiciels installés
* les mises à jour disponibles
* l'état de redémarrage

---

## 35. Jobs de mise à jour

Toutes les opérations mutatives sur les paquets et les mises à jour sont représentées comme des jobs de mise à jour LUMS.

Cela fournit un modèle commun d'exécution et de suivi.

Cycle de vie typique d'un job :

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS
```

Un job peut également nécessiter une gestion supplémentaire lorsque le client devient indisponible ou que l'exécution est interrompue.

L'historique des jobs doit être utilisé comme l'enregistrement opérationnel faisant autorité plutôt que de se fier uniquement à la vue actuelle du client.

---

## 36. Création de job

Avant de créer un job de mise à jour, vérifiez soigneusement l'opération prévue.

Vérifiez :

* client
* action
* paquet
* version cible le cas échéant
* état actuel du paquet
* exigences de maintenance

Les actions prises en charge comprennent :

| Action            | Objectif                     |
| ----------------- | ---------------------------- |
| `INSTALL_PACKAGE` | Installer un paquet          |
| `REMOVE_PACKAGE`  | Supprimer un paquet          |
| `UPDATE_PACKAGE`  | Mettre à jour un paquet spécifique |
| `UPDATE_SYSTEM`   | Effectuer une mise à jour système complète |

La création de jobs de mise à jour est limitée aux rôles **Administrator** et **Operator**.

Les Viewers ne peuvent pas créer de jobs de mise à jour.

---

## 37. Exécution des jobs

Après la création, le job est traité par l'agent LUMS.

L'agent reçoit le job et exécute l'opération demandée localement.

Le serveur suit l'état résultant.

L'agent ne traite pas une requête HTTP réussie comme une preuve que l'opération sur le paquet a réussi.

Au lieu de cela, le résultat réel du gestionnaire de paquets est renvoyé à LUMS.

Cette distinction est importante :

```text
API request accepted
        ≠
Package operation successful
```

Le résultat d'exécution final doit donc toujours être vérifié.

---

## 38. Résultats des jobs

Un job terminé doit contenir un résultat explicite.

Les résultats pertinents comprennent :

* exécution réussie
* exécution échouée
* erreur du gestionnaire de paquets
* exécution interrompue
* état lié à la récupération
* état lié au redémarrage le cas échéant

Les administrateurs et opérateurs doivent examiner le résultat lorsqu'un job échoue plutôt que de répéter immédiatement la même opération.

Une exécution répétée sans comprendre l'échec d'origine peut rendre le diagnostic plus difficile.

---

## 39. Historique des jobs

L'historique des mises à jour fournit un enregistrement opérationnel de l'activité de mise à jour précédente.

Utilisez-le pour répondre à des questions telles que :

* Ce paquet a-t-il déjà été mis à jour ?
* Quel client a exécuté l'opération ?
* Quand le job a-t-il été créé ?
* Quand l'exécution a-t-elle commencé ?
* Quand l'exécution s'est-elle terminée ?
* L'opération a-t-elle réussi ?
* Le gestionnaire de paquets a-t-il signalé une erreur ?

Les informations historiques des jobs sont particulièrement importantes lors de l'investigation d'échecs répétés ou d'opérations de maintenance interrompues.

---

## 40. Jobs échoués

Lorsqu'un job échoue :

1. enregistrez le client et l'ID du job
2. examinez le résultat du job
3. déterminez si l'échec s'est produit sur le serveur ou le client
4. examinez les journaux pertinents de l'agent
5. examinez l'état du gestionnaire de paquets natif
6. corrigez le problème sous-jacent
7. réessayez uniquement après avoir compris la cause

Les causes courantes comprennent :

* référentiels indisponibles
* verrous du gestionnaire de paquets
* problèmes réseau
* demandes de paquets invalides
* conflits de dépendances
* espace disque insuffisant
* opérations sur les paquets interrompues
* problèmes d'authentification ou de communication du client

Les procédures de diagnostic détaillées sont documentées dans `troubleshooting.md`.

---

## 41. Verrous du gestionnaire de paquets

APT et pacman peuvent empêcher les opérations concurrentes sur les paquets.

Si une opération de gestion des paquets échoue parce que le gestionnaire de paquets est déjà utilisé :

* identifiez le processus actif de gestion des paquets
* déterminez quelle opération est en cours
* attendez la fin de l'opération légitime lorsque c'est approprié
* réessayez l'opération LUMS ensuite

Ne supprimez **pas** aveuglément les fichiers de verrou du gestionnaire de paquets pendant que le gestionnaire de paquets est en cours d'exécution.

La suppression d'un fichier de verrou ne résout pas l'opération concurrente sous-jacente et peut endommager l'état de gestion des paquets.

---

## 42. Exécution consciente de l'inactivité

LUMS peut utiliser les informations d'inactivité du client pour déterminer si un job de mise à jour doit s'exécuter.

Ce mécanisme vise à éviter d'interrompre l'utilisation interactive active d'un système géré.

La détection d'inactivité est effectuée par l'agent sur le client.

Si les informations d'inactivité ne sont pas disponibles, l'agent doit signaler cette condition plutôt que d'inventer un état d'inactivité.

Les administrateurs doivent distinguer entre :

* client inactif
* client actif
* détection d'inactivité indisponible
* client injoignable

Ces états ont des significations opérationnelles différentes.

---

## 43. Surveillance de l'exécution des mises à jour

Pendant la maintenance, surveillez :

* l'état du job
* la connectivité du client
* l'activité de l'agent
* le résultat du gestionnaire de paquets
* l'exigence de redémarrage

Ne supposez pas qu'un job restant indéfiniment en `RUNNING` signifie que le gestionnaire de paquets fonctionne encore.

Si l'exécution semble bloquée, examinez l'état du client et de l'agent avant de créer un autre job.

---

## 44. Exigences de redémarrage

Certaines mises à jour de paquets et du système peuvent nécessiter un redémarrage.

LUMS suit l'état lié au redémarrage rapporté par le client géré.

Après une mise à jour système :

1. examinez l'état de redémarrage rapporté
2. déterminez si un redémarrage est nécessaire
3. effectuez le redémarrage pendant une fenêtre de maintenance appropriée
4. laissez l'agent rapporter à nouveau
5. vérifiez que le client revient au fonctionnement normal

Une exigence de redémarrage ne doit pas être automatiquement interprétée comme un échec de mise à jour.

---

## 45. Liste de contrôle opérationnelle des mises à jour

Pour la maintenance de routine des paquets :

```text
[ ] Correct client selected
[ ] Client is reachable
[ ] Current software state reviewed
[ ] Available updates reviewed
[ ] Correct package/action selected
[ ] Maintenance requirements checked
[ ] Update job created
[ ] Job execution monitored
[ ] Job result verified
[ ] Installed software verified
[ ] Available updates rechecked
[ ] Reboot state checked
[ ] Job history reviewed if required
```

L'opération n'est terminée qu'après vérification de l'état résultant du client.

---

## 46. Principe de gestion des paquets

LUMS fournit une orchestration et une visibilité centralisées.

Le système d'exploitation géré reste responsable de la gestion réelle des paquets.

Par conséquent :

> **LUMS demande et suit l'opération. Le gestionnaire de paquets natif l'exécute.**

Cette séparation permet à LUMS de gérer différents systèmes Linux tout en préservant la sémantique de gestion des paquets de chaque système d'exploitation.

## 47. Récupération des jobs

LUMS est conçu pour gérer les jobs de mise à jour interrompus sans répéter aveuglément les opérations déjà terminées avec succès.

L'exécution des mises à jour utilise des informations de point de contrôle pour suivre la progression.

Ceci est particulièrement important lorsque :

* l'agent est interrompu
* le client redémarre
* le serveur redémarre
* la communication réseau est temporairement indisponible
* une opération sur un paquet se termine avant que le résultat ne soit rapporté

Le mécanisme de récupération utilise l'état enregistré du job pour déterminer quel travail reste à effectuer.

---

## 48. Points de contrôle au niveau des paquets

Les jobs contenant plusieurs opérations sur des paquets sont traités individuellement.

Une opération réussie sur un paquet est enregistrée avant que l'agent ne passe à l'opération suivante.

Conceptuellement :

```text
Job
 │
 ├── Package A → SUCCESS
 │
 ├── Package B → SUCCESS
 │
 ├── Package C → interrupted
 │
 └── Package D → PENDING
```

Après récupération, les opérations déjà terminées sur les paquets ne doivent pas être réexécutées inutilement.

Le travail restant peut alors continuer à partir de l'état enregistré.

Cela réduit le risque de répéter les opérations sur les paquets après une interruption.

---

## 49. Jobs interrompus

Lorsqu'un job de mise à jour est interrompu, ne créez pas immédiatement un job de remplacement.

Déterminez d'abord :

1. quel job a été interrompu
2. quelle opération sur un paquet était active
3. quelles opérations sur les paquets ont déjà réussi
4. si le gestionnaire de paquets a terminé l'opération
5. si l'agent a récupéré le job automatiquement
6. si le client nécessite un redémarrage

L'historique existant des jobs et les journaux de l'agent doivent être examinés avant toute intervention manuelle.

---

## 50. Récupération par l'agent

L'agent est responsable de la poursuite du travail récupérable après une interruption.

La récupération doit préserver les résultats réussis des paquets dans la mesure du possible.

Si une opération sur un paquet est déjà enregistrée comme réussie, la récupération ne doit pas exécuter aveuglément cette même opération à nouveau.

Si la récupération ne peut pas déterminer en toute sécurité l'état d'une opération, la condition doit être traitée comme un problème opérationnel et investiguée.

Ne modifiez pas manuellement les états des jobs dans la base de données simplement pour faire apparaître un job comme terminé.

---

## 51. Redémarrage du serveur pendant un job

Un redémarrage du serveur LUMS ne signifie pas nécessairement que l'opération sur le paquet côté client a été interrompue.

Le serveur et le client ont des états d'exécution séparés.

Après un redémarrage du serveur :

1. vérifiez que le conteneur LUMS est en cours d'exécution
2. vérifiez la disponibilité de la base de données
3. vérifiez que le client peut communiquer avec LUMS
4. examinez les jobs de mise à jour affectés
5. vérifiez les rapports de l'agent
6. vérifiez l'état final du paquet

Le résultat d'exécution côté client reste la source de vérité importante pour l'opération sur le paquet.

---

## 52. Redémarrage du client pendant un job

Un redémarrage du client peut interrompre l'exécution de l'agent ou survenir parce que la mise à jour elle-même nécessite un redémarrage.

Ces situations doivent être distinguées.

### Redémarrage attendu

La mise à jour est terminée et le système nécessite un redémarrage.

### Interruption inattendue

Le système a redémarré avant la fin de l'opération ou avant que le résultat ne puisse être rapporté.

Après le retour du client :

1. laissez l'agent démarrer normalement
2. vérifiez la communication avec LUMS
3. examinez le job affecté
4. vérifiez l'état du paquet
5. vérifiez l'état de redémarrage
6. laissez la récupération se poursuivre le cas échéant

---

## 53. Détection de redémarrage

LUMS peut suivre les exigences de redémarrage rapportées par le client géré.

La détection de redémarrage n'est pas identique à la détection de la joignabilité actuelle de la machine.

Ce sont des états distincts :

```text
Client reachable
        │
        ├── reboot not required
        │
        └── reboot required

Client unreachable
        │
        └── current state cannot be confirmed
```

Les administrateurs doivent donc éviter de traiter un client injoignable comme preuve qu'un redémarrage est nécessaire.

---

## 54. Vérification après redémarrage

Après un redémarrage requis :

1. attendez que le système d'exploitation soit disponible
2. vérifiez le service ou le timer de l'agent
3. vérifiez l'authentification du client
4. vérifiez le rapport du client
5. examinez le job de mise à jour affecté
6. vérifiez les versions des paquets installés
7. vérifiez les mises à jour disponibles
8. vérifiez si un autre redémarrage est nécessaire

Un redémarrage ne doit être considéré comme opérationnellement terminé qu'après que le client a de nouveau rapporté avec succès.

---

## 55. Surveillance des jobs de mise à jour

Les administrateurs et opérateurs doivent surveiller les jobs pendant la maintenance planifiée.

Les états importants comprennent :

| État      | Signification                                     |
| --------- | ------------------------------------------------- |
| `PENDING` | Le job existe mais l'exécution n'a pas commencé   |
| `RUNNING` | L'exécution du job est en cours                   |
| `SUCCESS` | L'exécution s'est terminée avec succès            |
| `FAILED`  | L'exécution s'est terminée avec une erreur        |

Un état de job doit toujours être interprété avec ses informations de résultat.

Par exemple, un job `FAILED` doit être investigué à l'aide de son résultat enregistré plutôt que simplement réessayé.

---

## 56. Watcher d'exécution

L'agent LUMS inclut un watcher d'exécution dédié.

Le watcher est responsable de la surveillance de l'exécution des jobs de mise à jour sur le client.

Son objectif est de prendre en charge une gestion fiable de l'exécution indépendamment du flux de travail de rapport.

La version actuelle du watcher est :

**Watcher 1.2.1**

La version de l'agent est :

**Agent 1.7.0**

Ces versions doivent être vérifiées après les mises à niveau des clients.

---

## 57. Surveillance du Watcher

Les administrateurs peuvent inspecter le watcher via systemd sur le client géré.

Les vérifications utiles comprennent :

```bash
systemctl status lums-agent-watcher.service --no-pager
```

et :

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Le timer peut être inspecté avec :

```bash
systemctl status lums-agent-watcher.timer --no-pager
```

L'état actif/inactif exact d'un service oneshot doit être interprété avec son timer et son journal.

Un état `inactive (dead)` n'est pas automatiquement une erreur pour un service oneshot.

---

## 58. Timers de rapport et d'exécution

LUMS sépare la remontée régulière des clients de la surveillance de l'exécution.

Le timer de rapport est responsable de l'exécution planifiée de l'agent.

Le timer du watcher est responsable de l'exécution planifiée du watcher.

Examinez les deux lors du diagnostic de problèmes de planification côté client :

```bash
systemctl list-timers --all | grep lums-agent
```

Les units attendues comprennent :

```text
lums-agent.timer
lums-agent-watcher.timer
```

Si un timer ne fonctionne pas, examinez :

```bash
systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager
```

Examinez ensuite les entrées de journal correspondantes.

---

## 59. Journalisation d'audit

LUMS enregistre les actions applicatives importantes administratives et relatives à la sécurité dans le journal d'audit.

Les informations d'audit peuvent aider à établir :

* quelle opération s'est produite
* quel utilisateur l'a initiée
* quel client a été affecté
* quand l'opération s'est produite
* si l'opération a été acceptée
* quelle action administrative a été effectuée

Les informations d'audit doivent être traitées comme des preuves opérationnelles.

Elles ne doivent pas être supprimées ou modifiées à la légère.

---

## 60. Événements d'audit administratifs

L'activité administrative pertinente comprend des opérations telles que :

* création d'utilisateurs
* attribution de rôles
* gestion des clients
* rotation des tokens
* création de jobs de mise à jour
* opérations de gestion des paquets
* événements de sécurité liés à l'authentification

Les données d'événement exactes dépendent de l'opération.

Les administrateurs doivent utiliser les informations d'audit avec l'historique des jobs lors de l'investigation d'activités inattendues.

---

## 61. Gestion des journaux d'audit

Les journaux d'audit doivent être traités avec soin.

Ne pas :

* modifier les entrées d'audit historiques pour masquer une opération
* exposer des identifiants sensibles dans les journaux exportés
* publier des journaux contenant des tokens clients
* publier des mots de passe ou du matériel d'authentification
* copier une sortie de journal sensible dans des trackers d'issues publics

Si des journaux doivent être partagés pour le dépannage, rédigez d'abord les identifiants et autres informations sensibles.

---

## 62. Journaux applicatifs

Les journaux applicatifs décrivent le fonctionnement interne du serveur LUMS.

Les sources utiles comprennent :

```bash
sudo docker logs --tail 100 lums
```

Pour la surveillance en direct :

```bash
sudo docker logs -f lums
```

Lors de l'investigation d'un problème, réduisez la fenêtre temporelle lorsque c'est possible.

Ne videz pas automatiquement le journal de production entier lorsqu'une section pertinente plus petite suffit.

---

## 63. Journaux de l'agent

L'activité de l'agent côté client peut être inspectée via systemd :

```bash
journalctl -u lums-agent.service --no-pager -n 100
```

Pour l'activité du watcher :

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Pour une fenêtre temporelle spécifique, le filtrage du journal systemd peut être utilisé.

Exemple :

```bash
journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Les journaux doivent être corrélés avec l'ID du job affecté chaque fois que possible.

---

## 64. Corrélation des journaux

Lors de l'investigation d'un problème de mise à jour, corrélez les informations à travers le système :

```text id="jv3j7c"
Web UI
  │
  ├── Job ID
  │
  ▼
LUMS API / Application Log
  │
  ▼
Update Job
  │
  ▼
Agent
  │
  ▼
Native Package Manager
```

Cela évite l'erreur courante consistant à supposer qu'un problème observé dans une couche provient de cette même couche.

---

## 65. Liste de contrôle de la surveillance administrative

Pendant le fonctionnement normal, vérifiez périodiquement :

```text
[ ] LUMS container is running
[ ] HTTPS endpoint is available
[ ] Database is accessible
[ ] Clients are reporting
[ ] No unexpected failed jobs
[ ] No unexplained authentication failures
[ ] Agent timers are active
[ ] Watcher timers are active
[ ] Package-manager operations complete normally
[ ] Audit activity is available
[ ] Logs contain no unexplained recurring errors
```

La fréquence de ces vérifications doit correspondre à l'importance opérationnelle du déploiement LUMS.

---

## 66. Principe de récupération

Lorsqu'un problème de mise à jour survient, l'approche administrative la plus sûre est :

```text
Observe
   │
   ▼
Identify affected job/client
   │
   ▼
Inspect state and logs
   │
   ▼
Determine actual failure point
   │
   ▼
Correct underlying problem
   │
   ▼
Allow recovery or retry
   │
   ▼
Verify final state
   │
   ▼
Document significant incidents
```

Évitez les actions de récupération destructives, sauf si l'état d'échec réel est compris.

En particulier, ne supprimez pas manuellement des jobs, des enregistrements de base de données, des verrous de gestionnaire de paquets ou des données client persistantes uniquement pour restaurer une interface d'apparence propre.

> **Préserver les preuves d'abord. Réparer l'état ensuite. Vérifier le résultat en troisième.**

## 67. Administration de la base de données

LUMS utilise SQLite comme base de données applicative.

La base de données de production est stockée à l'intérieur du volume Docker persistant :

```text
/var/lib/lums/lums.db
```

La base de données est persistante au remplacement du conteneur tant que le volume Docker est préservé.

La base de données contient l'état applicatif tel que :

* utilisateurs
* clients gérés
* jobs de mise à jour
* informations sur les paquets
* informations d'audit
* état lié à l'authentification
* état des migrations

Les administrateurs doivent traiter la base de données comme des données applicatives critiques.

---

## 68. Configuration d'exécution SQLite

La base SQLite de production actuelle est :

| Paramètre      | Valeur                     |
| -------------- | -------------------------- |
| `journal_mode` | `wal`                      |
| `busy_timeout` | `5000`                     |
| `synchronous`  | `2`                        |
| `foreign_keys` | activé par l'application   |

L'application active explicitement l'application des clés étrangères SQLite pour les connexions à la base de données.

Les administrateurs ne doivent pas modifier ces paramètres à la légère.

Les modifications de la configuration d'exécution de la base de données doivent être testées avant d'être introduites en production.

---

## 69. Intégrité de la base de données

L'intégrité de la base de données doit être vérifiée lorsqu'il y a des indications de corruption de la base de données ou de comportement applicatif inattendu.

Une vérification d'intégrité SQLite typique est :

```bash id="f0g8sl"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Une base de données saine devrait retourner :

```text
ok
```

Si la vérification d'intégrité signale des erreurs, ne continuez pas à modifier aveuglément l'état de l'application.

Préservez la base de données affectée et investigatez la cause.

---

## 70. Migrations de base de données

LUMS utilise des migrations applicatives pour introduire des modifications de base de données.

Les migrations doivent être autorisées à s'exécuter via le mécanisme normal de démarrage et de migration de l'application.

Les administrateurs ne doivent pas modifier manuellement l'état des migrations simplement pour contourner une erreur.

Après une mise à jour applicative, vérifiez :

1. le conteneur démarre avec succès
2. les migrations sont terminées
3. l'application est joignable
4. les utilisateurs existants restent disponibles
5. les clients existants restent disponibles
6. l'historique existant des jobs reste disponible

---

## 71. Volume Docker persistant

Le volume Docker contenant les données applicatives LUMS est une ressource persistante critique.

Le volume de production est :

```text
lums-data
```

Inspectez-le avec :

```bash id="f3z2kd"
sudo docker volume inspect lums-data
```

Le volume doit rester attaché lors du remplacement du conteneur LUMS.

La suppression du conteneur ne supprime **pas** automatiquement le volume.

La suppression du volume, en revanche, supprime définitivement les données applicatives persistantes, sauf si une sauvegarde séparée existe.

---

## 72. Administration du conteneur

L'application LUMS s'exécute dans un conteneur Docker durci.

La base de sécurité de production comprend :

* utilisateur applicatif non-root
* système de fichiers racine en lecture seule
* capacités Linux abandonnées
* `no-new-privileges`
* systèmes de fichiers temporaires restreints
* montage secret en lecture seule
* volume de données persistant dédié
* port applicatif limité à localhost

Le conteneur ne doit pas être démarré avec des paramètres de sécurité plus faibles simplement parce que le dépannage devient plus pratique.

---

## 73. État du conteneur

Vérifiez l'état actuel du conteneur avec :

```bash id="4n6p2v"
sudo docker ps --filter name=lums
```

Examinez la configuration d'exécution complète avec :

```bash id="k1q4z8"
sudo docker inspect lums
```

Les propriétés importantes comprennent :

* état d'exécution
* politique de redémarrage
* utilisateur
* système de fichiers racine en lecture seule
* capacités
* options de sécurité
* liaisons de ports
* montages de volumes

---

## 74. Vérification de la sécurité du conteneur

L'exécution durcie devrait continuer à fournir les propriétés attendues.

Par exemple :

```bash id="0u7x3n"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

La base attendue est équivalente à :

```text
lums true false
```

Les capacités devraient rester abandonnées :

```bash id="k5n8ae"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Attendu :

```text
["ALL"]
```

Les options de sécurité devraient inclure :

```text
no-new-privileges:true
```

---

## 75. Port applicatif

L'application LUMS écoute sur l'hôte via l'interface loopback.

Le mappage attendu est :

```text
127.0.0.1:5050 → container:5000
```

Vérifiez avec :

```bash id="b6v2w0"
sudo docker port lums
```

Le port applicatif ne doit pas être exposé directement au LAN.

L'accès externe est fourni via Nginx sur HTTPS.

---

## 76. Nginx et HTTPS

Nginx fournit le point d'entrée HTTPS externe pour LUMS.

Le chemin de requête normal est :

```text
Client Browser
      │
      ▼
HTTPS :443
      │
      ▼
Nginx
      │
      ▼
127.0.0.1:5050
      │
      ▼
LUMS Container
```

Le port applicatif Docker doit rester lié à localhost.

Les administrateurs doivent donc éviter d'exposer le port `5050` directement via le pare-feu ou la configuration Docker.

---

## 77. Vérification HTTPS

Après les modifications Nginx, validez toujours la configuration avant de recharger :

```bash id="7f1h9m"
sudo nginx -t
```

Si la configuration est valide :

```bash id="4g5s2w"
sudo systemctl reload nginx
```

Vérifiez ensuite HTTPS :

```bash id="2w8v6c"
curl -I https://LUMS-SERVER/
```

Remplacez `LUMS-SERVER` par le nom d'hôte couvert par le certificat TLS du serveur. N'utilisez pas `-k` pour la vérification de routine ; cela contourne la validation du certificat.

Une réponse HTTPS réussie confirme que Nginx peut atteindre l'application LUMS.

La validation du certificat doit également être testée en utilisant le nom d'hôte ou l'adresse que les administrateurs utilisent normalement.

Ne désactivez pas de manière permanente la vérification du certificat avec `-k`.

---

## 78. Redirection HTTP

Le point de terminaison HTTP devrait rediriger les clients vers HTTPS.

Vérifiez :

```bash id="w5q0rx"
curl -I http://127.0.0.1/
```

Le comportement attendu est une redirection HTTP vers le point de terminaison HTTPS.

L'accès administratif doit utiliser HTTPS.

---

## 79. Maintenance des certificats TLS

Les certificats TLS et les clés privées sont externes à l'image Docker.

Les emplacements typiques sont :

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Les clés privées doivent rester protégées.

Avant de remplacer un certificat :

1. vérifiez le nouveau certificat
2. vérifiez la clé privée correspondante
3. vérifiez les permissions des fichiers
4. validez la configuration Nginx
5. rechargez Nginx
6. vérifiez HTTPS
7. vérifiez la connexion applicative

Ne placez jamais de clés TLS privées dans le référentiel Git ou l'image Docker.

---

## 80. Gestion des secrets

Le secret applicatif est stocké en dehors de l'image du conteneur.

Le secret de production est monté en lecture seule dans le conteneur :

```text
/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret
```

L'application reçoit le secret via :

```text
LUMS_SECRET_KEY_FILE
```

Les administrateurs ne doivent jamais :

* valider le secret dans Git
* afficher le secret
* inclure le secret dans la documentation
* l'exposer dans des captures d'écran
* le placer dans une couche d'image

Si le secret est suspecté d'être exposé, traitez-le comme compromis et suivez la procédure de rotation des secrets appropriée.

---

## 81. Stratégie de sauvegarde

Les données LUMS doivent être sauvegardées avant des modifications administratives significatives.

Au minimum, envisagez de protéger :

* les données applicatives SQLite
* la configuration applicative
* le matériel TLS
* les secrets applicatifs
* les informations de configuration client
* la documentation opérationnelle pertinente

Les sauvegardes doivent être stockées séparément du conteneur de production et de son volume Docker persistant.

Une sauvegarde qui existe uniquement à l'intérieur du même hôte ou du même volume Docker ne fournit pas une protection adéquate contre la perte de cet hôte ou volume.

---

## 82. Sauvegarde de la base de données

La base de données SQLite doit être sauvegardée à l'aide d'une méthode consciente de SQLite plutôt que de simplement copier un fichier de base de données activement modifié sans tenir compte de son état.

Avant d'effectuer une sauvegarde :

1. identifiez la base de données de production
2. assurez-vous que la destination de sauvegarde est disponible
3. créez la sauvegarde à l'aide d'une méthode sûre pour SQLite
4. vérifiez que la sauvegarde existe
5. enregistrez quand elle a été créée

Ne supposez pas qu'une copie de fichier réussie signifie automatiquement qu'une sauvegarde de base de données valide et récupérable existe.

---

## 83. Vérification des sauvegardes

Une sauvegarde n'est pas considérée comme fiable tant qu'elle n'a pas été testée.

Vérifiez périodiquement qu'une sauvegarde peut être :

* lue
* ouverte en tant que données SQLite
* vérifiée pour son intégrité
* restaurée dans un environnement de test isolé

Par exemple, une copie de test extraite peut être vérifiée avec :

```bash id="p3v7cx"
sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"
```

Résultat attendu :

```text
ok
```

Une sauvegarde de production ne doit jamais être testée en écrasant la base de données de production active.

---

## 84. Principe de restauration

La restauration est une opération administrative contrôlée.

Avant de restaurer :

1. identifiez la bonne sauvegarde
2. vérifiez son intégrité
3. déterminez le point de récupération requis
4. arrêtez ou isolez l'activité applicative le cas échéant
5. préservez l'état de production actuel
6. restaurez la sauvegarde
7. vérifiez l'intégrité de la base de données
8. démarrez l'application
9. vérifiez les migrations
10. vérifiez les utilisateurs et les clients
11. vérifiez l'historique des jobs
12. vérifiez la remontée normale des clients

N'écrasez pas la seule copie de la base de données de production pendant la récupération.

---

## 85. Vérification de la restauration

Après une restauration, vérifiez au minimum :

```text id="q6r2yh"
[ ] Container starts
[ ] Database opens
[ ] SQLite integrity check passes
[ ] Users are present
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is present
[ ] Audit information is available
[ ] HTTPS works
[ ] Clients can report
[ ] New operations can be created
```

Une restauration n'est terminée qu'après vérification de l'application et de ses clients gérés.

---

## 86. Principe de sauvegarde du serveur

La règle administrative la plus importante pour les données LUMS persistantes est :

> **N'effectuez jamais une opération destructive sur la base de données ou le volume sans un chemin de récupération vérifié.**

En particulier, ne supprimez pas `lums-data` simplement parce que le conteneur est reconstruit ou remplacé.

Le remplacement du conteneur et la suppression des données persistantes sont des opérations distinctes.

---

## 87. Liste de contrôle administrative du serveur

Avant d'effectuer une modification significative côté serveur :

```text id="7h3m0p"
[ ] Current container state recorded
[ ] Current image recorded
[ ] Database backup available
[ ] Backup integrity verified
[ ] Active jobs reviewed
[ ] Client reporting state reviewed
[ ] Configuration changes documented
[ ] TLS material available
[ ] Secret handling verified
[ ] Rollback path known
```

Ce n'est qu'après avoir pris en compte ces conditions qu'une modification significative de production doit être entreprise.

---

## 88. Principe d'administration du serveur

LUMS sépare l'état applicatif du conteneur applicatif jetable.

```text
Disposable
└── LUMS Container

Persistent
├── SQLite Database
└── lums-data Volume

External
├── TLS Material
└── Application Secret
```

Cette séparation permet de remplacer le conteneur applicatif sans détruire intentionnellement les données applicatives persistantes.

> **Remplacez l'application lorsque nécessaire. Préservez les données sauf si la suppression des données est explicitement voulue.**

## 89. Maintenance de routine

La maintenance de routine maintient l'installation LUMS fiable et réduit le risque de problèmes opérationnels inattendus.

Les activités de maintenance typiques comprennent :

* l'examen des jobs de mise à jour échoués
* la vérification de la remontée des clients
* l'examen des journaux applicatifs
* l'examen de l'activité d'audit
* la vérification des sauvegardes
* la vérification de l'espace disque disponible
* l'examen de l'état du conteneur Docker
* la vérification de la validité du certificat TLS
* l'examen des mises à jour de sécurité
* la vérification de la version et de l'image LUMS actuelles

La maintenance doit être effectuée pendant une fenêtre de maintenance appropriée lorsque les modifications peuvent affecter les clients de production.

---

## 90. Maintenance avant modifications

Avant d'effectuer une maintenance susceptible d'affecter le serveur LUMS :

1. examinez les jobs de mise à jour actifs
2. vérifiez que les clients ne subissent pas de maintenance inattendue
3. créez ou vérifiez une sauvegarde actuelle
4. enregistrez l'état actuel du conteneur et de l'image
5. documentez la modification prévue
6. assurez-vous qu'un chemin de retour arrière existe

Ne commencez pas la maintenance en arrêtant ou supprimant immédiatement des composants de production.

Établissez d'abord l'état actuel.

---

## 91. Maintenance des images Docker

Les images applicatives LUMS doivent être reconstruites à partir de l'arborescence source examinée.

Avant de construire une nouvelle image :

```bash id="x0m7r4"
cd /opt/lums-public
```

Exécutez la suite de tests automatisés :

```bash id="4gk1dp"
./.venv-test/bin/pytest -q
```

Ne poursuivez que lorsque le résultat des tests est compris.

Construisez la nouvelle image à l'aide d'un tag temporaire distinct :

```bash id="m8q3vz"
sudo docker build -t lums:new .
```

Un tag temporaire permet à l'image actuellement en cours d'exécution de rester identifiable pendant le processus de remplacement.

---

## 92. Vérification de l'image

Après avoir construit une nouvelle image, vérifiez que l'image existe :

```bash id="h6s2we"
sudo docker image inspect lums:new
```

Examinez la configuration de l'image avant le déploiement.

Le cas échéant, vérifiez :

* le digest de l'image
* l'image de base
* les fichiers applicatifs
* les dépendances installées
* la taille de l'image
* les ports exposés
* l'utilisateur configuré

L'image ne doit être déployée qu'après examen des résultats de construction et de test.

---

## 93. Remplacement contrôlé du conteneur

Le remplacement du conteneur doit être effectué délibérément.

Avant de remplacer le conteneur de production :

```text id="m3z8qk"
[ ] Tests passed
[ ] New image exists
[ ] Database backup available
[ ] Active jobs reviewed
[ ] Current image recorded
[ ] Persistent volume confirmed
[ ] Secret available
[ ] TLS configuration available
[ ] Rollback image identified
```

Avant d'exécuter l'exemple, comparez-le au conteneur réellement en cours d'exécution. Les valeurs ci-dessous sont un exemple, pas une commande sûre pour chaque installation. En particulier, les chemins sources des montages de liaison Docker à gauche de `:` doivent correspondre à votre hôte, et l'ancien conteneur peut avoir un nom différent.

Affichez l'image, les montages, les ports publiés, la politique de redémarrage et les paramètres de durcissement sans afficher les valeurs des variables d'environnement :

```bash
sudo docker inspect lums --format 'Image={{.Config.Image}}
Mounts={{json .Mounts}}
Ports={{json .HostConfig.PortBindings}}
Restart={{json .HostConfig.RestartPolicy}}
Readonly={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
Tmpfs={{json .HostConfig.Tmpfs}}'
```

Enregistrez la sortie dans un endroit privé et utilisez-la pour vérifier que le nouveau conteneur conserve le même volume de base de données, le même fichier secret, le même répertoire de sauvegarde, la même liaison de port local uniquement et les mêmes options de sécurité. Ne collez pas le contenu des secrets ni les valeurs d'environnement dans des notes ou des messages.

Arrêtez le conteneur existant seulement après avoir pris en compte ces conditions.

Le conteneur de production doit conserver la configuration d'exécution durcie.

Exemple :

```bash id="n8q2kf"
sudo docker stop lums
sudo docker rename lums lums-before-upgrade
```

Démarrez ensuite la nouvelle image avec la configuration durcie établie :

```bash id="c7w4md"
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -v /var/backups/lums:/var/backups/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -e LUMS_BACKUP_DIR=/var/backups/lums \
    lums:new
```

Ne supprimez pas `lums-before-upgrade` avant que le nouveau déploiement n'ait été validé.

---

## 94. Validation après mise à niveau

Immédiatement après avoir remplacé le conteneur, vérifiez :

```bash id="b4m7tz"
sudo docker ps --filter name=lums
```

Examinez ensuite les journaux :

```bash id="v5n2ra"
sudo docker logs --tail 100 lums
```

Vérifiez HTTPS :

```bash id="w9x1kf"
curl -I https://LUMS-SERVER/
```

Remplacez `LUMS-SERVER` par le nom d'hôte couvert par le certificat TLS du serveur. N'utilisez pas `-k` pour la vérification de routine ; cela contourne la validation du certificat.

Vérifiez ensuite l'application via l'interface administrative normale.

Vérifiez que les utilisateurs, clients et l'historique récent existants sont toujours présents. Examinez les journaux pour les erreurs de démarrage ou de migration. Un conteneur en cours d'exécution seul ne prouve pas que l'application ou sa base de données est saine.

### Revenir en arrière si le nouveau conteneur ne fonctionne pas

Conservez l'ancien conteneur jusqu'à ce que la nouvelle version ait passé la validation. Si le nouveau conteneur est inutilisable et que vous avez confirmé que l'ancien conteneur est nommé `lums-before-upgrade`, arrêtez et supprimez **uniquement le nouveau conteneur**, puis renommez et redémarrez l'ancien :

```bash
sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade lums
sudo docker start lums
```

`docker rm lums` sans `-v` supprime le conteneur, pas le volume `lums-data`. N'ajoutez jamais `-v` à cette commande de retour arrière. Si le nom du conteneur diffère, ou si vous n'êtes pas certain du conteneur ancien et nouveau, n'exécutez pas ces commandes ; inspectez l'état actuel ou demandez de l'aide à un administrateur. Après le retour arrière, examinez les journaux et vérifiez que l'interface web et les données sont disponibles.

---

## 95. Données persistantes après mise à niveau

Le remplacement du conteneur ne doit pas supprimer le volume Docker persistant.

Vérifiez :

```bash id="j4p8sx"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Confirmez que :

```text id="m7z3kc"
/var/lib/lums
```

est soutenu par le volume persistant attendu.

Vérifiez ensuite :

* les utilisateurs existent toujours
* les rôles restent corrects
* les clients restent enregistrés
* l'historique des jobs reste disponible
* les informations d'audit restent disponibles
* les migrations se sont terminées avec succès

---

## 96. Base de sécurité après mise à niveau

Après avoir déployé une nouvelle image, vérifiez à nouveau l'exécution durcie.

Vérifiez :

```bash id="q6c3xv"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Base attendue :

```text id="s0r8jm"
lums true false
```

Vérifiez également :

```text id="g4m2vx"
CapDrop = ALL
SecurityOpt = no-new-privileges:true
```

et que :

```text id="c3p9rw"
127.0.0.1:5050 → container:5000
```

reste l'exposition applicative.

Une mise à niveau applicative réussie ne doit pas affaiblir silencieusement la base de sécurité.

---

## 97. Communication client après mise à niveau

Après une mise à niveau du serveur, vérifiez que les clients gérés peuvent toujours communiquer.

Vérifiez d'abord au moins un client représentatif.

Vérifiez :

```text id="x8h5qk"
[ ] Client authentication succeeds
[ ] Client report is accepted
[ ] Installed software is available
[ ] Available updates are available
[ ] Update jobs can be created
[ ] Agent results are accepted
```

Si plusieurs plateformes clientes sont déployées, vérifiez des systèmes représentatifs de chaque plateforme prise en charge.

---

## 98. Exécution des mises à jour après mise à niveau

N'effectuez pas immédiatement une grande mise à jour de production après avoir remplacé le serveur LUMS.

Effectuez d'abord un test fonctionnel contrôlé.

Un test approprié devrait vérifier le chemin complet :

```text id="y7k2fd"
Web UI
  ↓
API
  ↓
Update Job
  ↓
Agent
  ↓
Package Manager
  ↓
Result
  ↓
Database
  ↓
Web UI
```

Ce n'est qu'après la réussite du test contrôlé que les opérations de maintenance normales doivent reprendre.

---

## 99. Retour arrière

Un retour arrière doit être possible lorsqu'une nouvelle image provoque un problème de production inattendu.

Préservez :

* l'image précédente fonctionnelle
* les données persistantes
* la sauvegarde de la base de données
* la configuration précédente
* le matériel TLS précédent
* les journaux pertinents

Si le nouveau conteneur n'est pas utilisable :

1. arrêtez le nouveau conteneur
2. conservez-le pour investigation lorsque c'est pratique
3. arrêtez les autres modifications administratives
4. restaurez l'image précédemment connue comme fiable
5. réutilisez le volume persistant existant
6. démarrez l'exécution durcie
7. vérifiez l'application
8. vérifiez les clients
9. vérifiez l'état des jobs
10. investigatez l'image échouée séparément

Ne supprimez pas le volume persistant dans le cadre d'un retour arrière normal.

---

## 100. Validation du retour arrière

Après le retour arrière, vérifiez :

```text id="z1j8md"
[ ] LUMS starts
[ ] HTTPS works
[ ] Users can authenticate
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is available
[ ] Audit information is available
[ ] Package inventory is available
[ ] Update jobs can be tracked
[ ] Security baseline is intact
```

Un retour arrière n'est terminé qu'après vérification de l'application et du chemin de communication client.

---

## 101. Administration d'urgence

L'administration d'urgence doit préserver les preuves et l'état persistant chaque fois que possible.

Les exemples incluent :

* plantages applicatifs répétés
* erreurs d'intégrité de la base de données
* échecs d'authentification client généralisés
* comportement inattendu des jobs de paquets
* exposition d'identifiants suspectée
* mises à niveau cassées
* échecs TLS affectant tous les utilisateurs

La séquence préférée est :

```text id="f8k3wz"
Preserve
   ↓
Observe
   ↓
Isolate
   ↓
Recover
   ↓
Verify
   ↓
Document
```

Évitez de supprimer des journaux, bases de données, conteneurs ou enregistrements clients simplement parce qu'ils semblent faire partie du problème.

---

## 102. Principe de modification administrative

Chaque modification significative de production devrait avoir trois états clairement définis :

### Avant

L'état de production actuel est connu et récupérable.

### Pendant

La modification est effectuée à l'aide de la procédure documentée.

### Après

L'état résultant est vérifié par rapport à la base attendue.

Cela rend le travail administratif reproductible et réduit la dérive accidentelle de configuration.

---

## 103. Désinstallation contrôlée

La désinstallation est une opération administrative destructive.

Elle ne doit être effectuée que lorsque le déploiement LUMS est intentionnellement supprimé.

Avant de supprimer LUMS :

```text id="u5r2nc"
[ ] All managed clients identified
[ ] Active update jobs reviewed
[ ] Required job history exported or preserved
[ ] Required audit information preserved
[ ] Database backup created
[ ] Backup verified
[ ] TLS material preserved if required
[ ] Application secret preserved if required
[ ] Documentation preserved
[ ] Reinstallation requirements documented
```

Ne supprimez pas les données persistantes avant d'avoir confirmé qu'elles ne sont plus requises.

---

## 104. Suppression du conteneur

Pour supprimer le conteneur applicatif après la mise hors service du déploiement :

```bash id="n2x7kc"
sudo docker stop lums
sudo docker rm lums
```

Le volume Docker n'est intentionnellement **pas** supprimé par ces commandes.

Cela permet aux données applicatives de rester disponibles pour une inspection ou une récupération ultérieure.

---

## 105. Suppression des données persistantes

La suppression du volume Docker LUMS est une opération destructive distincte.

Ne l'effectuez qu'après avoir confirmé que la base de données et tout l'état applicatif stocké ne sont plus requis.

Exemple :

```bash id="r8w3mz"
sudo docker volume rm lums-data
```

Cela supprime définitivement les données applicatives persistantes stockées dans ce volume.

N'exécutez pas cette commande lors d'une mise à niveau ou d'un retour arrière normal.

---

## 106. Suppression des composants clients

Lorsqu'un client géré est définitivement retiré de LUMS, désinstallez ou désactivez ses composants d'agent conformément à la procédure du système d'exploitation client.

Le client ne doit plus rapporter au serveur LUMS après la mise hors service.

Préservez les informations de job et d'audit pertinentes avant de retirer le client si des enregistrements historiques sont requis.

---

## 107. Liste de contrôle administrative finale

### Administration des utilisateurs

```text id="p5z8cv"
[ ] Users have appropriate roles
[ ] Administrator access is limited
[ ] Disabled accounts are reviewed
[ ] Credentials are protected
```

### Administration des clients

```text id="q2m7xd"
[ ] Clients are correctly registered
[ ] Client tokens are protected
[ ] Disabled clients are reviewed
[ ] Token rotation is performed when required
[ ] Client reporting is healthy
```

### Administration des mises à jour

```text id="h6v9kt"
[ ] Available updates are reviewed
[ ] Update jobs are monitored
[ ] Failed jobs are investigated
[ ] Package operations are verified
[ ] Reboot requirements are checked
[ ] Job history is retained
```

### Administration du serveur

```text id="r3c8wn"
[ ] Container is running
[ ] Persistent volume is attached
[ ] SQLite integrity is healthy
[ ] HTTPS is working
[ ] TLS material is valid
[ ] Application secret is protected
[ ] Backups are available
```

### Sécurité

```text id="v7m4qx"
[ ] RBAC remains enforced
[ ] Viewer restrictions remain intact
[ ] Client authentication works
[ ] Container remains hardened
[ ] Application port remains localhost-only
[ ] No credentials are exposed
[ ] Logs contain no unexplained sensitive information
```

---

## 108. Base opérationnelle

Une installation LUMS saine devrait satisfaire la base suivante :

```text id="d4k9sy"
Application
    ├── HTTPS available
    ├── Authentication available
    └── RBAC enforced

Server
    ├── Hardened container
    ├── Persistent database
    └── Valid migrations

Clients
    ├── Authenticated
    ├── Reporting
    ├── Software inventory available
    └── Update information available

Operations
    ├── Update jobs executable
    ├── Results recorded
    ├── Recovery supported
    └── Reboot state reported

Security
    ├── Secrets protected
    ├── Tokens protected
    ├── Audit information retained
    └── Network exposure restricted

Recovery
    ├── Backups available
    ├── Restore path known
    └── Rollback path known
```

---

## 109. Administration terminée

L'administration de LUMS doit toujours prioriser les modifications contrôlées, observables et réversibles.

Le cycle de vie administratif est :

```text id="w6f1pa"
Plan
  ↓
Observe
  ↓
Change
  ↓
Verify
  ↓
Document
  ↓
Maintain
```

Les principes opérationnels les plus importants sont :

> **Utilisez le moindre privilège nécessaire.**

> **Préservez les données persistantes.**

> **Ne modifiez pas l'état sans comprendre l'état actuel.**

> **Vérifiez le résultat de chaque opération significative.**

> **Maintenez un chemin de récupération testé.**

Pour les procédures d'installation, voir `install.md`.

Pour l'architecture de sécurité et les résultats d'audit, voir `security.md`.

Pour les procédures de diagnostic et de récupération, voir `troubleshooting.md`.

---

## 110. Principe d'administration final

LUMS vise à rendre la gestion des mises à jour Linux prévisible et observable.

Le travail administratif ne doit donc pas être basé sur des suppositions ou une répétition aveugle.

Lorsque quelque chose change :

**Observer d'abord. Modifier ensuite. Vérifier en troisième.**

Lorsque quelque chose casse :

**Préserver les preuves. Identifier la couche défaillante. Récupérer délibérément.**

Lorsque quelque chose fonctionne :

**Enregistrer le résultat et conserver la base connue comme fiable.**
