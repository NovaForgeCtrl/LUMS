# Dépannage de LUMS

Ce guide fournit des procédures de dépannage pour le serveur LUMS, les agents Linux, le watcher d'exécution, les jobs de mise à jour, l'authentification, la gestion des paquets, la base de données et le déploiement Docker.

Le processus de dépannage doit toujours commencer par **l'observation avant la modification**.

L'objectif est d'identifier le premier composant où le comportement attendu s'arrête, sans modifier inutilement la configuration, l'état de la base de données, les identifiants ou les contrôles de sécurité.

---

## Pour commencer : Dépanner en toute sécurité

Si vous êtes nouveau sur Linux, une erreur ne signifie pas automatiquement que des données ont été perdues. Ne modifiez pas plusieurs choses à la fois. Commencez par les vérifications ci-dessous et notez **quand** le problème se produit et **quelle action** s'est produite immédiatement avant.

### Premières vérifications sur le serveur LUMS

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`docker ps -a` affiche également les conteneurs arrêtés. `docker logs` lit les messages applicatifs récents. `systemctl status` indique si Nginx est en cours d'exécution ; `nginx -t` vérifie sa configuration sans la modifier. Si `nginx -t` échoue, ne rechargez **pas** Nginx avant d'avoir corrigé la cause.

### Premières vérifications sur un client géré

```bash
sudo systemctl status lums-agent.service --no-pager
sudo journalctl -u lums-agent.service -n 100 --no-pager
sudo systemctl status lums-agent-watcher.service --no-pager
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

L'agent et le watcher sont des services distincts : un rapport d'agent réussi ne prouve pas que le watcher peut exécuter des jobs de mise à jour. Pour un service `oneshot`, `inactive` peut être normal après une exécution réussie ; vérifiez également le résultat et les messages de journal.

### Avant de partager la sortie d'une commande

Vérifiez les journaux et la configuration pour les mots de passe, les tokens clients, les clés de session ou d'API, les clés privées et les informations personnelles. Ne partagez jamais le contenu d'un fichier secret ou les valeurs complètes de variables d'environnement. Si vous avez besoin d'aide, partagez uniquement les messages d'erreur pertinents après avoir supprimé les informations sensibles.

**Ne commencez pas par** supprimer la base de données ou le volume Docker, exécuter le conteneur en mode privilégié, désactiver les options de sécurité, supprimer les fichiers de verrou du gestionnaire de paquets ou faire tourner les tokens. Ces actions peuvent endommager des données, effacer des preuves ou aggraver le problème. Si une vérification échoue, enregistrez sa sortie et passez à la section pertinente ci-dessous.

---

# 1. Philosophie du dépannage

LUMS se compose de plusieurs composants indépendants.

Un rapport client réussi ne signifie pas automatiquement que l'exécution des mises à jour fonctionne.

Le chemin opérationnel principal est :

```text
Linux Client
    │
    ├── LUMS Agent
    │
    └── Execution Watcher
            │
            ▼
          HTTPS
            │
            ▼
        Nginx
            │
            ▼
        LUMS API
            │
            ▼
         SQLite
```

L'exécution des mises à jour ajoute la couche de gestion des paquets :

```text
Browser
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Update Job
   │
   ▼
Execution Watcher
   │
   ▼
LUMS Agent
   │
   ▼
APT / pacman
   │
   ▼
Result
   │
   ▼
LUMS API
   │
   ▼
SQLite
```

Lors du dépannage, identifiez le **premier composant en échec**.

Par exemple :

```text
Agent report fails
    ↓
Check agent service
    ↓
Check network
    ↓
Check TLS
    ↓
Check client token
    ↓
Check LUMS API
```

Ne faites pas immédiatement :

* modifier la base de données
* supprimer le volume Docker
* réinstaller l'agent
* faire tourner les identifiants
* supprimer les fichiers de verrou du gestionnaire de paquets
* désactiver les contrôles de sécurité
* rendre le conteneur privilégié

Ces actions peuvent détruire des informations de diagnostic utiles ou créer des problèmes supplémentaires.

---

# 2. Base de diagnostic

Avant d'investiguer un problème spécifique, établissez l'état actuel des composants principaux.

Le déploiement LUMS de production utilise :

```text
Application port: 127.0.0.1:5050
External access: HTTPS through Nginx
Database: /var/lib/lums/lums.db
Docker volume: lums-data
Agent: 1.7.0
Watcher: 1.2.1
```

Le conteneur de production est durci avec :

```text
Read-only root filesystem
No Linux capabilities
no-new-privileges
Non-root application user
Protected secret mount
Dedicated persistent data volume
```

Le port applicatif est intentionnellement lié uniquement à l'hôte local.

Le chemin réseau attendu est :

```text
Client / Browser
       │
       ▼
     HTTPS
       │
       ▼
    Nginx :443
       │
       ▼
127.0.0.1:5050
       │
       ▼
 Docker container
       │
       ▼
    LUMS :5000
```

---

# 3. Premières vérifications de diagnostic

## 3.1 Vérifier le conteneur LUMS

Sur le serveur LUMS :

```bash
sudo docker ps
```

Le conteneur `lums` devrait être en cours d'exécution.

Pour une vue d'ensemble complète des conteneurs :

```bash
sudo docker ps -a \
    --filter name=lums
```

Ne supprimez pas les conteneurs arrêtés avant de les avoir examinés.

Les anciens conteneurs de secours peuvent contenir des informations utiles lors de l'investigation d'un problème de déploiement.

---

## 3.2 Vérifier les journaux applicatifs récents

Examinez les journaux LUMS les plus récents :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Pour une sortie en direct :

```bash
sudo docker logs \
    -f \
    lums
```

Lors de l'investigation d'une requête ou d'un job spécifique, commencez l'inspection des journaux avant de reproduire le problème lorsque c'est possible.

Cela facilite la corrélation de l'action client avec l'événement côté serveur correspondant.

---

## 3.3 Vérifier Nginx

Vérifiez le proxy inverse :

```bash
sudo systemctl status nginx \
    --no-pager
```

Validez la configuration :

```bash
sudo nginx -t
```

Un test de configuration réussi devrait rapporter :

```text
syntax is ok
test is successful
```

Si Nginx ne fonctionne pas, l'accès HTTPS à LUMS échouera normalement même si le conteneur Docker lui-même est sain.

---

## 3.4 Vérifier l'agent

Sur un client Linux géré :

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Examinez la sortie récente de l'agent :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Pour un service `Type=oneshot`, un état inactif après une exécution réussie peut être normal.

L'information importante est le résultat d'exécution.

Une exécution réussie devrait se terminer par :

```text
status=0/SUCCESS
```

---

## 3.5 Vérifier le watcher d'exécution

Le watcher est un composant distinct de l'agent de rapport.

Vérifiez-le indépendamment :

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Examinez la sortie récente :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Un rapport d'agent réussi ne prouve donc **pas** que le watcher d'exécution fonctionne correctement.

---

## 3.6 Vérifier les timers LUMS

Vérifiez tous les timers pertinents :

```bash
sudo systemctl list-timers \
    --all | grep lums
```

Les timers attendus comprennent les mécanismes de planification de l'agent et du watcher.

Si un timer est manquant ou inactif, examinez l'unité correspondante avant de modifier quoi que ce soit.

---

# 4. Le conteneur LUMS ne fonctionne pas

Si le conteneur `lums` ne fonctionne pas, ne le recréez pas immédiatement.

Examinez d'abord son état :

```bash
sudo docker ps -a \
    --filter name=lums
```

Examinez ensuite le conteneur :

```bash
sudo docker inspect lums
```

Vérifiez les journaux récents :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Vérifiez l'état de sortie :

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

Le résultat peut aider à distinguer entre :

```text
Normal shutdown
Application failure
Configuration failure
Container runtime failure
Health/startup problem
```

Si le conteneur s'est arrêté de manière inattendue, préservez les journaux et l'état du conteneur avant de le remplacer.

---

# 5. Le conteneur démarre mais LUMS est injoignable

L'application LUMS n'est pas destinée à être accédée directement via le port applicatif Docker depuis le réseau.

L'application de production est liée à :

```text
127.0.0.1:5050
```

Vérifiez la liaison de port :

```bash
sudo docker port lums
```

Vérifiez également les écouteurs de l'hôte :

```bash
sudo ss -lntp | grep -E ':443|:5050'
```

L'architecture attendue est :

```text
HTTPS :443
    │
    ▼
  Nginx
    │
    ▼
127.0.0.1:5050
    │
    ▼
Docker
    │
    ▼
LUMS :5000
```

Si le conteneur fonctionne mais HTTPS échoue, examinez les couches individuellement :

1. Conteneur Docker
2. Port applicatif local
3. Configuration Nginx
4. TLS
5. Chemin pare-feu/réseau

N'exposez pas le port `5050` publiquement comme raccourci de dépannage.

---

# 6. Nginx retourne une erreur

Vérifiez le service :

```bash
sudo systemctl status nginx \
    --no-pager
```

Validez la configuration :

```bash
sudo nginx -t
```

Examinez les messages Nginx récents :

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Vérifiez ensuite que le conteneur LUMS est réellement en cours d'exécution :

```bash
sudo docker ps
```

Une erreur de proxy inverse ne signifie pas automatiquement que l'application LUMS elle-même est cassée.

Les emplacements d'échec possibles comprennent :

```text
Browser
   ↓
TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
LUMS
```

Testez les couches séparément plutôt que de modifier plusieurs composants à la fois.

---

# 7. Problèmes HTTPS / TLS

Testez d'abord le point de terminaison HTTPS :

```bash
curl -I https://LUMS-SERVER/
```

Si la validation du certificat échoue, déterminez si le problème est :

```text
Certificate
Certificate chain
Hostname
Trust store
Nginx configuration
Client CA configuration
```

Validez Nginx :

```bash
sudo nginx -t
```

Si le certificat ou la configuration TLS a été intentionnellement modifié, rechargez Nginx :

```bash
sudo systemctl reload nginx
```

Testez ensuite à nouveau :

```bash
curl -I https://LUMS-SERVER/
```

Les clients utilisant une autorité de certification privée doivent faire confiance au certificat de l'AC approprié.

Ne désactivez pas la vérification du certificat TLS comme solution de contournement permanente.

Un test de connectivité réussi qui contourne la validation du certificat ne prouve pas que la configuration TLS de production est correcte.

---

# 8. Le service de l'agent échoue

Vérifiez le service :

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Lisez le journal récent :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Ne redémarrez le service qu'après avoir examiné le résultat précédent :

```bash
sudo systemctl start \
    lums-agent.service
```

Vérifiez ensuite :

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

et :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Recherchez :

```text
Configuration errors
Missing environment values
TLS errors
Authentication failures
API errors
Python exceptions
Package-manager errors
```

Ne réinstallez pas l'agent simplement parce qu'une seule exécution a échoué.

---

# 9. L'agent signale `LUMS_TOKEN` manquant

L'agent reçoit normalement sa configuration de production via l'environnement de son service systemd.

Si l'agent est démarré manuellement depuis un shell, le `EnvironmentFile` de systemd n'est pas automatiquement chargé dans ce shell.

Par conséquent :

```bash
sudo /opt/lums-agent/agent.py --version
```

peut se comporter différemment de :

```bash
sudo systemctl start \
    lums-agent.service
```

lorsque le token est fourni exclusivement via la configuration systemd.

Lors de l'investigation de problèmes d'authentification, testez d'abord le service réel :

```bash
sudo systemctl start \
    lums-agent.service
```

Examinez ensuite :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Ne copiez pas inutilement les tokens de production dans les commandes shell.

N'affichez jamais un token de production dans un journal de diagnostic.

---

# 10. L'agent ne peut pas atteindre le serveur

Commencez par la connectivité réseau :

```bash
ping LUMS-SERVER
```

Testez ensuite HTTPS :

```bash
curl -I https://LUMS-SERVER/
```

Si HTTPS fonctionne mais que l'agent échoue toujours, examinez :

```text
Client configuration
Client token
TLS trust
API response
Client identity
Agent version
```

Examinez l'agent :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

En même temps, examinez le serveur :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Cela aide à déterminer si la requête atteint LUMS du tout.

Si le client voit un échec de connexion et que le serveur ne montre aucune requête correspondante, examinez le chemin réseau ou TLS avant de modifier la configuration applicative.

---

# 11. Poursuivre le dépannage

Si les couches de base du serveur, de Docker, de Nginx, de TLS et de l'agent fonctionnent, continuez avec :

```text
Client Authentication
Token Rotation
Update Detection
Execution Watcher
Idle Detection
Pending Jobs
```

La section suivante continue avec l'authentification client et les problèmes liés aux tokens.

# 12. Authentification client

LUMS utilise une authentification spécifique au client pour la communication de l'agent.

Lorsqu'un client est enregistré, le client reçoit des identifiants utilisés pour la communication authentifiée avec le serveur LUMS.

Les échecs d'authentification doivent être investigués sans exposer le token client.

---

## 12.1 Le client n'est pas accepté par LUMS

Si un agent signale un échec d'authentification, examinez d'abord le journal de l'agent :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Examinez ensuite les journaux du conteneur LUMS :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Recherchez :

```text
401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure
```

Une réponse `401` indique généralement un problème d'authentification.

Une réponse `403` peut indiquer que l'authentification a réussi mais que l'opération demandée n'est pas autorisée.

Ne faites pas immédiatement tourner le token.

Déterminez d'abord si le problème est :

```text
Wrong token
Wrong client ID
Disabled client
Incorrect server URL
TLS problem
Malformed request
Server-side authentication failure
```

---

## 12.2 Le client existe mais l'authentification échoue

Vérifiez que le client existe toujours dans l'interface d'administration LUMS.

Ne modifiez pas l'enregistrement client uniquement parce qu'une requête d'agent a échoué.

Si le client existe, comparez l'identité client configurée avec l'identité utilisée par l'agent.

Le token de production lui-même ne doit jamais être affiché dans la sortie de diagnostic.

Utilisez les métadonnées de configuration et l'état du service pour le dépannage plutôt que d'exposer les identifiants.

---

# 13. Rotation des tokens clients

La rotation du token client invalide le token précédent et le remplace par un nouvel identifiant.

Si un token a été intentionnellement roté, l'agent affecté doit recevoir le nouveau token avant de pouvoir s'authentifier à nouveau.

La séquence attendue est :

```text
Administrator
    │
    ▼
Rotate client token
    │
    ▼
Old token becomes invalid
    │
    ▼
New token assigned to client
    │
    ▼
Agent configuration updated
    │
    ▼
Agent reports again
```

Si l'agent continue d'utiliser l'ancien token, l'authentification échouera.

---

## 13.1 Après la rotation du token

Vérifiez le service de l'agent :

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Exécutez ensuite l'agent via systemd :

```bash
sudo systemctl start \
    lums-agent.service
```

Examinez le résultat :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Si l'authentification échoue toujours, examinez les journaux du serveur :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Ne faites pas tourner le token de manière répétée.

Une rotation répétée peut rendre plus difficile la détermination de l'identifiant actuellement déployé sur le client.

---

# 14. Le client est désactivé

Un client désactivé ne doit pas être traité comme un client géré actif.

Si un agent appartenant à un client désactivé tente de communiquer, examinez le résultat d'authentification côté serveur.

Vérifiez :

```text
Client identity
Client enabled state
Authentication result
Agent configuration
```

Ne réactivez pas le client simplement pour faire disparaître une erreur.

Déterminez d'abord pourquoi le client a été désactivé.

---

# 15. Détection des mises à jour

La détection des mises à jour se compose de plusieurs étapes indépendantes.

L'agent doit :

1. exécuter la requête du gestionnaire de paquets
2. analyser le résultat
3. envoyer le résultat à LUMS
4. LUMS doit valider le résultat
5. LUMS doit persister le résultat
6. l'UI doit afficher l'état actuel

Un échec à n'importe quelle étape peut faire apparaître les informations de mise à jour comme incorrectes.

Le flux de base est :

```text
APT / pacman
     │
     ▼
Agent
     │
     ▼
HTTPS
     │
     ▼
LUMS API
     │
     ▼
SQLite
     │
     ▼
Web UI
```

---

## 15.1 Aucune mise à jour n'est affichée

Déterminez d'abord si le client a réellement rapporté avec succès.

Vérifiez :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Examinez ensuite le serveur :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Si l'agent s'est terminé avec succès mais qu'aucune mise à jour n'est affichée, examinez l'état de l'API et de la base de données avant de modifier le gestionnaire de paquets.

---

## 15.2 Détection des mises à jour Debian / Ubuntu

Le gestionnaire de paquets Debian utilise APT.

Lors de l'investigation de problèmes liés à APT, vérifiez d'abord qu'APT lui-même fonctionne :

```bash
sudo apt update
```

N'exécutez pas automatiquement de mises à niveau de paquets pendant le dépannage.

Le but de ce test est de déterminer si les métadonnées du référentiel peuvent être actualisées avec succès.

Si APT signale des erreurs de référentiel, DNS, TLS, signature ou verrou, résolvez le problème APT sous-jacent avant d'investiguer LUMS.

---

## 15.3 Détection des mises à jour Arch Linux

Arch Linux utilise `pacman`.

Vérifiez les métadonnées du référentiel :

```bash
sudo pacman -Sy
```

Utilisez ceci uniquement lorsque l'actualisation des métadonnées du référentiel est réellement nécessaire pour le diagnostic.

Ne combinez pas une mise à niveau système inutile avec un test de diagnostic.

Pour les erreurs liées aux paquets, examinez la sortie exacte de `pacman` avant de modifier la configuration.

---

# 16. Les mises à jour disponibles diffèrent entre LUMS et le client

Les informations de mise à jour peuvent changer entre deux observations.

Par exemple :

```text
Client reports updates
        ↓
Repository metadata changes
        ↓
Package is upgraded manually
        ↓
LUMS displays older information
```

Par conséquent, tenez toujours compte de l'horodatage du dernier rapport client réussi.

Une différence n'indique pas automatiquement un problème de base de données.

Vérifiez :

```text
Last Agent execution
Last successful report
Package-manager state
Repository metadata
Displayed update state
```

---

# 17. Gestion des paquets

La gestion des paquets LUMS est séparée du filtre des paquets installés affiché sur la page client.

Le flux de travail de gestion des paquets est :

```text
User
 │
 ▼
Package Search
 │
 ▼
LUMS API
 │
 ▼
Agent
 │
 ▼
APT / pacman
 │
 ▼
Search Result
 │
 ▼
LUMS API
 │
 ▼
Web UI
```

L'installation, la suppression ou la mise à jour d'un paquet utilise le mécanisme de job LUMS normal.

Le chemin d'exécution attendu est :

```text
Package Action
     │
     ▼
Update Job
     │
     ▼
Execution Watcher
     │
     ▼
Agent
     │
     ▼
APT / pacman
```

---

## 17.1 La recherche de paquets ne renvoie aucun résultat

Vérifiez d'abord que l'agent est opérationnel :

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Examinez ensuite le journal de l'agent :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Pour les clients basés sur Debian, vérifiez les métadonnées APT.

Pour les clients basés sur Arch, vérifiez les métadonnées du référentiel pacman.

Ne supposez pas qu'un résultat de recherche vide signifie que la base de données LUMS est vide.

La recherche est effectuée via le gestionnaire de paquets du client.

---

## 17.2 La recherche de paquets fonctionne mais l'installation échoue

Une recherche réussie prouve uniquement que le gestionnaire de paquets a pu localiser le paquet.

Elle ne prouve pas que l'installation réussira.

Les causes possibles comprennent :

```text
Dependency conflicts
Repository changes
Package no longer available
Insufficient privileges
Package-manager lock
Disk-space problems
Network problems
Package-manager errors
```

Examinez le job de mise à jour correspondant.

Le journal de l'agent devrait contenir le résultat du gestionnaire de paquets.

---

# 18. Jobs d'installation de paquets

L'installation de paquets utilise l'infrastructure normale des jobs de mise à jour.

L'action pertinente est :

```text
INSTALL_PACKAGE
```

Lors du dépannage d'une installation :

1. Vérifiez l'état du job dans LUMS.
2. Vérifiez l'exécution de l'agent.
3. Vérifiez la sortie du gestionnaire de paquets.
4. Vérifiez le résultat final rapporté à LUMS.

Ne modifiez pas manuellement l'état du job dans SQLite.

Le cycle de vie attendu est :

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

ou :

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
```

Une installation de paquet échouée devrait rester traçable via les mécanismes normaux de job et d'audit.

---

# 19. Jobs de suppression de paquets

La suppression de paquets suit le même cycle de vie de job.

L'action est :

```text
REMOVE_PACKAGE
```

Lorsqu'une suppression échoue, examinez :

```text
Update job
Agent journal
Package-manager output
Final job result
```

Ne supprimez pas manuellement d'enregistrements de base de données pour masquer une opération sur un paquet échouée.

Un job échoué est une information de diagnostic utile.

---

# 20. Jobs de mise à jour de paquets

Une mise à jour spécifique à un paquet utilise :

```text
UPDATE_PACKAGE
```

Le paquet doit être connu de LUMS comme ayant une mise à jour disponible avant la création du job.

Si l'UI ne propose pas la mise à jour de paquet attendue :

1. actualisez les informations de mise à jour
2. vérifiez l'état du gestionnaire de paquets
3. vérifiez le résultat des mises à jour disponibles
4. examinez les journaux du serveur si l'état est incohérent

N'insérez pas manuellement d'enregistrements de mise à jour dans SQLite.

---

# 21. Jobs de mise à jour système

Une mise à jour système complète utilise :

```text
UPDATE_SYSTEM
```

Ceci est différent de :

```text
UPDATE_PACKAGE
```

La mise à jour système peut affecter plusieurs paquets et peut nécessiter un redémarrage selon le système d'exploitation et l'état résultant des paquets.

Lors du dépannage d'une mise à jour système, déterminez si l'échec s'est produit pendant :

```text
Update preparation
Package-manager execution
Result collection
Reboot detection
Post-reboot reporting
```

---

# 22. Verrous du gestionnaire de paquets

Les gestionnaires de paquets peuvent refuser une opération lorsqu'un autre processus de gestion des paquets est déjà en cours d'exécution.

Les exemples typiques comprennent :

```text
APT is already running
dpkg is locked
pacman is locked
```

Identifiez d'abord le processus détenant le verrou.

Ne supprimez pas aveuglément les fichiers de verrou.

Un fichier de verrou peut indiquer qu'un autre processus de gestion des paquets est légitimement actif.

Le supprimer pendant qu'une opération sur les paquets est en cours peut endommager l'état de gestion des paquets.

La séquence de dépannage correcte est :

```text
Lock error
   ↓
Identify active process
   ↓
Determine whether it is legitimate
   ↓
Wait or resolve the process safely
   ↓
Retry operation
```

---

# 23. Échec du gestionnaire de paquets vs. échec de LUMS

Distinguez toujours entre un échec du gestionnaire de paquets et un échec de LUMS.

Par exemple :

```text
APT fails
    ↓
Agent reports APT failure
    ↓
LUMS stores FAILED result
```

Dans ce cas, LUMS peut fonctionner correctement même si le job a échoué.

Inversement :

```text
APT succeeds
    ↓
Agent cannot report result
    ↓
LUMS never receives SUCCESS
```

Ici, l'opération sur le paquet peut avoir réussi alors que le chemin de rapport LUMS a échoué.

Le résultat du gestionnaire de paquets et le résultat du job LUMS doivent donc être investigués séparément.

---

# 24. Séparation de diagnostic utile

Lorsqu'un job de paquet échoue, classez d'abord l'échec :

```text
A. Package-manager failure
B. Agent execution failure
C. Agent reporting failure
D. Server/API failure
E. Database persistence failure
F. UI display problem
```

Cette classification empêche la modification de composants non liés.

Une erreur du gestionnaire de paquets ne devrait pas automatiquement entraîner une reconstruction Docker.

Un problème d'affichage de l'UI ne devrait pas automatiquement entraîner la suppression de la base de données.

Un échec d'authentification ne devrait pas automatiquement entraîner la réinstallation de l'agent.

---

# 25. Prochain domaine de dépannage

Si l'authentification client, la détection des mises à jour et la gestion des paquets fonctionnent, le prochain domaine de diagnostic est le cycle de vie de l'exécution lui-même :

```text
Update Job
    ↓
Watcher
    ↓
Agent
    ↓
Execution
    ↓
Result
    ↓
Checkpoint / Recovery
    ↓
Final Job State
```

La section suivante couvre **Execution Watcher, Idle Detection, Job State, Recovery et la gestion des redémarrages**.

# 26. Exécution des jobs de mise à jour

Les jobs de mise à jour LUMS sont exécutés de manière asynchrone via l'agent et le watcher d'exécution.

Le chemin d'exécution normal est :

```text
User
 │
 ▼
LUMS API
 │
 ▼
SQLite
 │
 ▼
Pending Job
 │
 ▼
Execution Watcher
 │
 ▼
Agent
 │
 ▼
Package Manager
 │
 ▼
Result
 │
 ▼
LUMS API
 │
 ▼
SQLite
```

Un job visible dans l'UI n'est pas nécessairement déjà en cours d'exécution.

Déterminez toujours d'abord l'état actuel du job.

---

## 26.1 Le job est bloqué en `PENDING`

Si un job reste en `PENDING`, vérifiez le watcher d'exécution avant d'investiguer l'agent.

Vérifiez le watcher :

```bash id="wq5h3v"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Examinez la sortie récente du watcher :

```bash id="8y0v7e"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Vérifiez ensuite l'agent :

```bash id="j8x4qm"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Un job en attente indique normalement que la phase d'exécution n'a pas encore commencé.

Les causes possibles comprennent :

```text
Watcher is not running
Watcher timer is not running
Client is offline
Client is not idle
Client has not reported recently
Job is not eligible for execution yet
```

Ne modifiez pas manuellement l'état du job dans SQLite.

---

# 27. Le job est bloqué en `RUNNING`

Un job `RUNNING` indique que l'exécution a commencé.

Déterminez d'abord si l'agent exécute réellement le job.

Vérifiez :

```bash id="s2z5ek"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Examinez ensuite le watcher :

```bash id="x4f6cb"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Un job en cours d'exécution peut prendre du temps selon :

```text
Package count
Repository speed
Network latency
Package-manager operations
System load
Reboot requirements
```

Ne terminez pas une opération sur les paquets active uniquement parce que l'UI n'a pas encore été actualisée.

Déterminez d'abord si le processus sous-jacent est toujours actif.

---

# 28. Le job est `FAILED`

Un job échoué n'indique pas nécessairement un échec du serveur LUMS.

Déterminez quelle couche a produit l'échec.

Examinez :

```text id="5t9b83"
Job state
Agent execution result
Package-manager result
Server logs
Agent logs
```

Les catégories principales sont :

```text
Package-manager failure
Agent execution failure
Agent reporting failure
Server/API failure
Authentication failure
Recovery failure
```

L'erreur d'origine doit être préservée dans la mesure du possible.

Ne remplacez pas un job échoué par un enregistrement de succès créé manuellement.

---

# 29. Le job est `SUCCESS` mais le paquet n'a pas été modifié

Un job LUMS réussi signifie que l'opération demandée a été terminée selon le résultat de l'agent.

Si l'état attendu du paquet ne correspond pas au résultat du job, vérifiez le client directement.

Pour les systèmes basés sur Debian :

```bash id="gqdbm7"
dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME
```

Pour Arch Linux :

```bash id="2x9f7v"
pacman -Q \
    PACKAGE_NAME
```

Remplacez `PACKAGE_NAME` par le paquet en cours d'investigation.

Comparez ensuite l'état local du paquet avec le résultat LUMS.

Les explications possibles comprennent :

```text
Package was changed after the job
Package name refers to a virtual/provided package
Package-manager output was interpreted differently than expected
The job result was generated before another local change
```

Ne modifiez pas la base de données LUMS avant que la divergence n'ait été identifiée.

---

# 30. Execution Watcher

Le watcher d'exécution est responsable de la découverte des jobs qui sont éligibles à l'exécution.

Le watcher doit être traité comme un composant indépendant.

Vérifiez son service :

```bash id="w5m0c8"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Vérifiez son timer :

```bash id="3v1x7r"
sudo systemctl list-timers \
    --all | grep lums
```

Examinez son journal :

```bash id="d5m0xk"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Si l'agent fonctionne mais que les jobs ne démarrent jamais, le watcher devrait être l'un des premiers composants à investiguer.

---

# 31. Le watcher s'exécute mais n'exécute pas de jobs

Une exécution du watcher ne signifie pas automatiquement qu'un job sera démarré.

Le job doit satisfaire les conditions d'exécution.

Vérifiez :

```text id="m7p2zq"
Client exists
Client is enabled
Client is reachable
Client has recent status
Client is eligible
Job is pending
Job is not already completed
Execution conditions are satisfied
```

Si le client n'est pas éligible, le watcher peut correctement laisser le job en attente.

Ce n'est pas nécessairement une erreur.

---

# 32. Détection d'inactivité

LUMS peut utiliser les informations d'inactivité du client pour décider si un job doit être exécuté.

Le but est d'éviter de démarrer des opérations de maintenance pendant que le client est activement utilisé.

La décision d'inactivité doit donc être traitée comme une condition de planification, et non comme un échec d'exécution.

Un client peut rapporter avec succès tout en étant considéré comme non-inactif.

La séquence de dépannage est :

```text
Agent reports
     ↓
Idle information available?
     ↓
Idle state acceptable?
     ↓
Job eligible?
     ↓
Watcher executes
```

---

## 32.1 Le client rapporte mais n'est pas considéré comme inactif

Vérifiez le journal de l'agent :

```bash id="5r2q1k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Recherchez les informations d'inactivité rapportées.

Examinez ensuite le watcher :

```bash id="2a6v8m"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

La distinction importante est :

```text
Agent communication successful
```

par rapport à :

```text
Client eligible for maintenance execution
```

Ce sont des états distincts.

---

# 33. La détection d'inactivité est indisponible

Certains systèmes peuvent ne pas fournir toutes les informations d'état d'inactivité.

Un mécanisme d'inactivité indisponible ne doit pas être automatiquement interprété comme un agent cassé.

Déterminez d'abord la capacité rapportée.

Les concepts pertinents sont :

```text
Idle supported
Idle source
Idle state
Idle duration
```

Si la plateforme ne peut pas fournir les informations d'inactivité attendues, examinez l'implémentation spécifique à la plateforme de l'agent plutôt que de modifier la base de données du serveur.

---

# 34. Récupération des jobs de mise à jour

LUMS utilise le checkpointing et la récupération pour empêcher que les jobs de mise à jour interrompus ne soient traités comme terminés.

Un job peut être interrompu à cause de :

```text
Agent restart
Client reboot
Network interruption
Package-manager interruption
Server restart
Watcher restart
System failure
```

La récupération doit distinguer entre le travail déjà terminé et le travail qui doit encore être exécuté.

Le principe est :

```text
Le travail terminé reste terminé.
Le travail inachevé reste récupérable.
```

---

# 35. Job interrompu

Si un job a été interrompu, examinez d'abord son état.

Examinez ensuite l'agent :

```bash id="3u8d4k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Examinez le watcher :

```bash id="w4x1b9"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Ne marquez pas manuellement le job comme réussi.

Le mécanisme de récupération devrait déterminer quels éléments de paquets ont déjà été terminés.

---

# 36. La récupération répète une opération sur un paquet

Lorsque la récupération est déclenchée, les éléments de paquets déjà réussis ne doivent pas être exécutés à nouveau inutilement.

Le modèle de récupération est basé sur l'état au niveau de l'élément.

Conceptuellement :

```text
Job
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → FAILED
 └── Package D → PENDING
```

La récupération devrait préserver les éléments réussis et continuer avec le travail restant.

Si ce comportement semble incorrect, examinez l'historique du job et des éléments de paquets avant de modifier la base de données.

---

# 37. Le client redémarre pendant une mise à jour

Un redémarrage peut interrompre le processus de l'agent.

Le chemin de récupération attendu est :

```text
Update starts
    ↓
Package operation
    ↓
Client reboot
    ↓
Agent starts again
    ↓
State is reported
    ↓
LUMS evaluates recovery
```

Un redémarrage ne signifie donc pas automatiquement que le job a échoué définitivement.

Examinez le service de l'agent après le retour du client :

```bash id="jjh3u8"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Examinez ensuite les exécutions récentes :

```bash id="h7y5gk"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

---

# 38. Détection de redémarrage

La détection de redémarrage est utilisée pour déterminer si un redémarrage système s'est produit dans le cadre d'une opération de mise à jour.

Ceci est particulièrement pertinent lorsqu'une mise à jour modifie des paquets qui nécessitent un redémarrage.

Pour Arch Linux, la détection de redémarrage ne doit pas être confondue avec le code de sortie du gestionnaire de paquets.

Une opération sur les paquets peut réussir alors que le système nécessite toujours un redémarrage.

Lors du dépannage de la gestion des redémarrages, comparez :

```text
Package operation result
Reboot requirement
Actual reboot state
Post-reboot Agent report
Final LUMS job state
```

---

# 39. Le résultat du job n'a pas été rapporté

Si l'opération sur le paquet semble s'être terminée mais que LUMS n'affiche pas le résultat final, examinez le chemin de rapport.

Vérifiez l'agent :

```bash id="t0r8kf"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Vérifiez ensuite le serveur :

```bash id="h5n1xv"
sudo docker logs \
    --tail 200 \
    lums
```

Si l'agent signale une erreur alors que l'opération sur le paquet elle-même a réussi, classez le problème comme un échec de rapport plutôt que comme un échec de gestion des paquets.

---

# 40. Redémarrage du serveur pendant l'exécution d'un job

Un redémarrage du serveur ne doit pas automatiquement être traité comme une preuve qu'une opération de mise à jour a échoué.

L'état du job doit être évalué après que le serveur soit redevenu disponible.

Vérifiez :

```text id="j4t7yw"
Container state
Database availability
Job state
Client state
Agent report
Watcher state
```

Le mécanisme de récupération est responsable de déterminer si le travail interrompu peut continuer en toute sécurité.

Ne réécrivez pas manuellement les états des jobs après un redémarrage du serveur.

---

# 41. La base de données est disponible mais l'état du job semble incorrect

Si SQLite est accessible mais que l'état du job semble incohérent, examinez les journaux applicatifs et d'audit avant de modifier la base de données.

Les informations utiles comprennent :

```text
Job ID
Client ID
Job action
Job creation time
Current state
Package-item states
Agent result
Recovery events
Audit events
```

La base de données est un stockage de données applicatives, pas une interface de réparation manuelle.

Les modifications directes peuvent contourner la validation, l'autorisation, l'audit et la logique de récupération.

---

# 42. Modifications manuelles de l'état des jobs

Les modifications SQL manuelles de l'état des jobs de mise à jour ne doivent pas être utilisées comme dépannage normal.

Évitez les opérations telles que :

```sql id="8hbyqv"
UPDATE update_jobs ...
```

ou :

```sql id="n1h7yr"
DELETE FROM update_jobs ...
```

sauf si une procédure de récupération de base de données contrôlée les exige explicitement.

Si une réparation au niveau de la base de données est réellement nécessaire, préservez une sauvegarde et documentez la modification exacte avant de l'appliquer.

Les problèmes opérationnels normaux doivent être résolus via les mécanismes de l'application et de l'agent.

---

# 43. Matrice de diagnostic Watcher et Agent

Utilisez la matrice suivante pour identifier la couche la plus probable :

| Symptôme                                          | Premier composant à inspecter |
| ------------------------------------------------- | ----------------------------- |
| Le client ne peut pas s'authentifier             | Agent + LUMS API              |
| Le client rapporte avec succès mais le job reste en attente | Execution Watcher  |
| Le job passe en running mais ne se termine pas   | Agent + gestionnaire de paquets |
| L'opération sur le paquet échoue                 | Gestionnaire de paquets       |
| L'opération sur le paquet réussit mais le résultat est manquant | Rapport de l'agent |
| Le client a redémarré pendant la mise à jour     | Agent + récupération          |
| Le job reste incohérent après redémarrage        | Récupération + état de la base de données |
| Le job n'est jamais découvert                    | Watcher + timer               |
| Le client n'est pas éligible                     | Idle / état du client         |
| L'UI affiche un état obsolète                    | API + dernier rapport client  |

Cette matrice est un point de départ, pas un substitut à l'inspection des journaux réels et de l'état du job.

---

# 44. Prochain domaine de dépannage

Après vérification de l'exécution des jobs, les domaines suivants sont :

```text
SQLite and database state
RBAC and user management
Authentication sessions
Application and audit logging
Container security
Tests and CI
```

Ces domaines doivent être investigués séparément de l'exécution des paquets.

# 45. Dépannage SQLite et base de données

LUMS utilise SQLite comme base de données applicative.

La base de données de production est stockée à l'intérieur du volume Docker persistant :

```text id="9c6w3e"
/var/lib/lums/lums.db
```

La base de données est gérée par l'application et ne doit normalement pas être modifiée manuellement.

Lors de l'investigation de problèmes liés à la base de données, déterminez d'abord si le problème est :

```text id="4k4z1m"
Database availability
Database locking
Application configuration
Data consistency
Migration state
Application logic
```

---

# 46. La base de données n'est pas disponible

Si LUMS signale une erreur de base de données, vérifiez d'abord si le conteneur fonctionne :

```bash id="0l5q6h"
sudo docker ps
```

Examinez ensuite les journaux applicatifs :

```bash id="6j5p8m"
sudo docker logs \
    --tail 200 \
    lums
```

Ne supprimez pas immédiatement le volume Docker.

Le volume persistant contient les données applicatives de production.

Sa suppression peut supprimer définitivement :

```text id="4bq9rj"
Users
Clients
Client configuration
Update jobs
Audit data
Application state
```

---

# 47. Verrouillage de la base de données SQLite

Les problèmes de verrouillage SQLite doivent être investigués via les journaux applicatifs.

Examinez :

```bash id="l8f6vk"
sudo docker logs \
    --tail 200 \
    lums
```

L'application de production utilise :

```text id="2d3m8x"
journal_mode = wal
busy_timeout = 5000
synchronous = 2
```

L'application active également l'application des clés étrangères SQLite sur ses connexions à la base de données.

Un verrou de base de données ne signifie pas automatiquement que la base de données est corrompue.

Les causes possibles comprennent :

```text id="9w4qcz"
Concurrent writes
Long-running transaction
Application process still using the database
Unexpected process termination
Filesystem problem
```

Ne supprimez pas manuellement les fichiers de journal SQLite.

---

# 48. Clés étrangères SQLite

LUMS active explicitement l'application des clés étrangères SQLite au niveau de l'application.

Cela signifie que les relations entre les enregistrements de la base de données sont validées par SQLite lorsque la connexion applicative est établie.

Si une erreur liée aux clés étrangères se produit, examinez d'abord les journaux applicatifs.

Ne désactivez pas l'application des clés étrangères pour faire réussir une opération.

Un échec de clé étrangère peut indiquer un problème de logique applicative ou d'intégrité des données.

---

# 49. Intégrité de la base de données SQLite

Si une corruption de base de données est suspectée, arrêtez d'abord les modifications inutiles.

Préservez l'état actuel et examinez les journaux applicatifs.

Une vérification d'intégrité contrôlée peut être effectuée sur une copie de la base de données.

N'effectuez pas d'opérations de réparation destructives directement sur la base de données de production, sauf si une procédure de récupération documentée l'exige.

Le principe général est :

```text id="t4d1km"
Preserve
   ↓
Inspect
   ↓
Verify
   ↓
Recover
   ↓
Validate
```

Ne commencez jamais par :

```text id="z1f6rw"
Delete database
Recreate database
Recreate Docker volume
```

---

# 50. Migrations de base de données

LUMS utilise des migrations applicatives pour introduire des modifications de schéma de base de données.

Lorsqu'un problème de migration survient, examinez les journaux du conteneur :

```bash id="x4h9vf"
sudo docker logs \
    --tail 200 \
    lums
```

Recherchez :

```text id="m2x7kc"
Migration failure
SQL error
Duplicate column
Missing table
Constraint error
Migration already applied
```

Ne modifiez pas manuellement les enregistrements de migration, sauf si le système de migration requiert spécifiquement une procédure de récupération contrôlée.

Une migration déjà appliquée ne doit normalement pas être exécutée manuellement à nouveau.

---

# 51. Volume de base de données

La base de données LUMS est stockée dans le volume Docker persistant :

```text id="p6m3jw"
lums-data
```

Examinez le volume :

```bash id="v4c7yq"
sudo docker volume inspect \
    lums-data
```

Le volume doit rester persistant à travers la recréation normale du conteneur.

Le conteneur applicatif lui-même est jetable.

Les données applicatives ne le sont pas.

Par conséquent :

```text id="z9f4ws"
Container
    ≠
Persistent database
```

Recréer le conteneur ne doit pas être confondu avec recréer le volume de données.

---

# 52. Espace disque de la base de données

SQLite nécessite de l'espace de fichiers disponible pour le fonctionnement normal.

Vérifiez le système de fichiers de l'hôte :

```bash id="j6k1pt"
df -h
```

Vérifiez également la disponibilité des inodes :

```bash id="q2c5ra"
df -i
```

Un espace disque faible peut produire des erreurs de base de données qui ressemblent initialement à des problèmes applicatifs.

Si la base de données devient soudainement en lecture seule ou que les écritures commencent à échouer, vérifiez la capacité du système de fichiers avant de modifier la configuration SQLite.

---

# 53. Dépannage RBAC

LUMS utilise le contrôle d'accès basé sur les rôles.

Les rôles actuels sont :

```text id="k8w5j2"
Administrator
Operator
Viewer
```

Les permissions sont intentionnellement différentes.

---

## 53.1 Administrator

Les administrateurs peuvent :

```text id="n4x7pa"
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
Create and disable clients
Rotate client tokens
Manage users
Manage roles
```

Les opérations réservées aux administrateurs comprennent la gestion des utilisateurs et l'administration des rôles.

---

## 53.2 Operator

Les opérateurs peuvent :

```text id="b7c2mz"
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Les opérateurs ne peuvent pas :

```text id="q8v3kd"
Manage users
Manage roles
Create or disable clients
Rotate client tokens
```

---

## 53.3 Viewer

Les Viewers ont un accès délibérément restreint.

Un Viewer peut :

```text id="y5m2rx"
View clients
View installed software
```

Les fonctionnalités suivantes sont masquées dans l'interface Viewer et bloquées côté serveur :

```text id="e8c4nw"
Available Updates
Update Jobs
Update History
Package Management
System Maintenance
```

Il s'agit d'un contrôle de sécurité intentionnel.

Si un Viewer peut accéder à l'une de ces fonctions, traitez le problème comme un problème RBAC plutôt que comme un simple problème d'UI.

---

# 54. Le Viewer voit trop

Si un Viewer voit des fonctionnalités qui ne devraient pas être disponibles, vérifiez les deux couches :

```text id="x5j3mq"
Browser UI
    +
Server-side authorization
```

Masquer un élément en JavaScript ou HTML n'est pas une sécurité suffisante.

L'API doit également rejeter les opérations non autorisées.

Lors de l'investigation :

1. Déterminez le rôle de l'utilisateur authentifié.
2. Identifiez le point de terminaison affecté.
3. Vérifiez la réponse du serveur.
4. Examinez les journaux applicatifs si nécessaire.
5. Vérifiez le test RBAC pertinent.

Ne résolvez pas un problème d'autorisation en masquant uniquement l'élément d'UI.

---

# 55. Le Viewer ne peut pas voir les données attendues

Un Viewer devrait toujours pouvoir accéder aux informations explicitement autorisées par le modèle RBAC actuel.

Si des informations client autorisées sont manquantes :

```text id="3h6q8f"
Verify login
   ↓
Verify role
   ↓
Verify client visibility
   ↓
Inspect API response
   ↓
Inspect browser console if necessary
```

N'accordez pas de permissions supplémentaires simplement parce qu'une page semble actuellement incomplète.

Déterminez d'abord si les informations manquantes sont intentionnellement restreintes.

---

# 56. L'Operator ne peut pas effectuer une opération

Si un Operator reçoit `403 Forbidden`, déterminez d'abord si l'action demandée est réservée aux administrateurs.

L'accès Operator n'inclut pas :

```text id="n5y7cu"
User management
Role administration
Client creation/deactivation
Client token rotation
```

Si l'opération devrait être autorisée pour les Operators, examinez le décorateur d'autorisation du point de terminaison et les tests RBAC correspondants.

Ne promouvez pas temporairement l'utilisateur au rôle Administrator comme raccourci de diagnostic.

---

# 57. L'Administrator ne peut pas effectuer une opération

Un Administrator devrait avoir accès à toutes les opérations administratives actuellement prises en charge.

Si un Administrator reçoit une erreur d'autorisation :

```text id="q7d2nv"
Verify authenticated session
        ↓
Verify current role
        ↓
Verify endpoint authorization
        ↓
Inspect CSRF requirements
        ↓
Inspect application logs
```

Pour les opérations modifiant l'état, une session valide seule peut ne pas être suffisante.

La protection CSRF doit également être satisfaite lorsque nécessaire.

---

# 58. Gestion des utilisateurs

La gestion des utilisateurs est réservée aux Administrators.

Le flux de travail de gestion des utilisateurs est :

```text id="x4j6pw"
Administrator
    │
    ▼
User Management
    │
    ├── Create user
    ├── Assign role
    └── Enable / disable user
```

Lorsqu'un utilisateur ne peut pas être créé, vérifiez :

```text id="b3q9fz"
Current role
Username validation
Role validation
Duplicate username
Password validation
CSRF protection
Application logs
```

Ne créez pas d'utilisateurs directement dans SQLite.

L'insertion directe dans la base de données contourne le hachage des mots de passe, la validation, l'autorisation et la journalisation d'audit.

---

# 59. La création d'utilisateur échoue

Si la création d'utilisateur échoue, examinez la réponse du navigateur et les journaux du serveur.

L'API devrait valider :

```text id="7x3m5n"
Username
Role
Password requirements
Duplicate account
Authenticated administrator
CSRF token
```

Si la requête est rejetée, déterminez quelle règle de validation a été déclenchée.

N'affaiblissez pas la validation simplement pour faire réussir une seule requête de création de compte.

---

# 60. Problèmes de mot de passe

LUMS stocke les mots de passe utilisateur à l'aide d'un mécanisme de hachage de mot de passe plutôt que de mots de passe en clair.

Si un utilisateur ne peut pas se connecter :

```text id="9w3r5b"
Verify username
   ↓
Verify account enabled state
   ↓
Verify password
   ↓
Check login rate limiting
   ↓
Inspect authentication logs
```

Ne stockez ni ne journalisez jamais de mots de passe en clair.

Ne copiez pas les mots de passe dans les commandes de diagnostic ou les fichiers de journal.

---

# 61. Compte utilisateur désactivé

Un compte désactivé ne doit pas être traité comme un compte de connexion actif.

Si un utilisateur désactivé peut toujours s'authentifier, examinez :

```text id="z6t2hx"
Current account state
Authentication lookup
Session state
Session revocation
Browser session
Server-side authorization
```

Ne supprimez pas simplement le compte.

Préserver le compte peut être important pour l'historique d'audit.

---

# 62. Problèmes de session

LUMS utilise la gestion de session côté serveur.

Lorsqu'un utilisateur semble avoir un accès obsolète ou inattendu, déconnectez-vous d'abord et établissez une nouvelle session.

Si le problème persiste, examinez :

```text id="q1y7vm"
Account state
Role
Session state
Session revocation
Cookie configuration
CSRF protection
```

Ne désactivez pas les contrôles de sécurité de session pour contourner un problème de connexion.

---

# 63. Révocation de session

La révocation de session est pertinente lorsque :

```text id="4n8z7p"
A password changes
A user is disabled
A role changes
A session must be invalidated
A security event requires forced logout
```

Si un utilisateur semble conserver l'accès après une modification de compte, déterminez si la session existante a été correctement invalidée.

Testez avec une nouvelle session de navigateur uniquement après avoir confirmé l'état du compte.

Ne supposez pas que la suppression des cookies du navigateur prouve à elle seule que la révocation de session côté serveur fonctionne.

---

# 64. Limitation du taux de connexion

LUMS applique une limitation du taux de connexion aux tentatives d'authentification échouées répétées.

Le comportement actuel utilise des intervalles de verrouillage croissants :

```text id="p7k4xz"
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

L'état d'échec est persisté dans SQLite.

Si les tentatives de connexion sont bloquées de manière inattendue, examinez l'état d'authentification avant de modifier la base de données.

Une réponse de limitation de taux n'est pas automatiquement un échec d'authentification.

Elle peut indiquer que le compte a atteint le seuil configuré de tentatives échouées.

---

# 65. La connexion fonctionne mais l'API retourne `403`

Une connexion réussie prouve l'authentification, pas l'autorisation.

Une réponse `403 Forbidden` peut indiquer :

```text id="m9c2vx"
Insufficient role
Missing CSRF protection
Disallowed operation
Disabled functionality
```

Identifiez le point de terminaison exact avant de modifier quoi que ce soit.

La question de dépannage correcte est :

```text id="0q4g1k"
"Is this user authenticated?"
```

suivie de :

```text id="x8v5md"
"Is this authenticated user authorized for this operation?"
```

Ce sont des vérifications de sécurité distinctes.

---

# 66. Erreurs CSRF

Les requêtes de navigateur modifiant l'état sont protégées contre la falsification de requête intersite.

Si une requête modifiant l'état échoue de manière inattendue :

```text id="6z4qpn"
Verify authenticated session
        ↓
Verify CSRF token
        ↓
Verify request method
        ↓
Verify endpoint
        ↓
Inspect server response
```

Ne désactivez pas la protection CSRF comme solution de contournement de dépannage.

Une vérification CSRF échouée est un contrôle de sécurité fonctionnant comme prévu.

---

# 67. L'UI du navigateur et l'API ne sont pas d'accord

Si l'UI montre qu'une action est disponible mais que l'API la rejette :

```text id="v8n3ty"
Browser UI
   ↓
Displayed role/state
   ↓
API request
   ↓
Server-side authorization
```

Le résultat côté serveur fait autorité.

L'UI peut contenir un état obsolète après :

```text id="4g7m2x"
Role changes
Session changes
Client changes
Page remains open for a long time
```

Rechargez la page et établissez une nouvelle session avant de supposer que l'autorisation côté serveur est incorrecte.

---

# 68. Matrice de diagnostic RBAC

| Symptôme                        | Premier composant à inspecter          |
| ------------------------------- | -------------------------------------- |
| Le Viewer voit l'UI de gestion  | Gestion du rôle de la page client      |
| La requête API du Viewer réussit | RBAC côté serveur                     |
| L'Operator reçoit `403`         | Modèle de permission du point de terminaison |
| L'Administrator reçoit `403`    | Session / CSRF / autorisation du point de terminaison |
| L'utilisateur ne peut pas être créé | Rôle admin + validation           |
| Un utilisateur désactivé peut se connecter | État du compte + gestion de session |
| Connexion temporairement bloquée | Limitation du taux                    |
| Requête modifiant l'état rejetée | CSRF / session                        |
| L'UI et l'API ne sont pas d'accord | État du navigateur + autorisation serveur |

Le résultat de l'autorisation côté serveur est toujours plus important que la visibilité d'un élément d'interface.

---

# 69. Prochain domaine de dépannage

Les prochains domaines de diagnostic sont :

```text id="8r5w2q"
Application and audit logging
Container security
Filesystem permissions
Docker runtime configuration
Tests and CI
Diagnostic snapshots
Final recovery checklist
```

Ces domaines doivent être investigués sans affaiblir la base de sécurité.

# 70. Journalisation applicative

LUMS utilise la journalisation applicative pour fournir des informations de diagnostic sans exposer d'identifiants sensibles.

Lors de l'investigation d'un problème applicatif, commencez par les journaux les plus récents :

```bash id="f6m2qa"
sudo docker logs \
    --tail 200 \
    lums
```

Pour une surveillance continue :

```bash id="x3v8kp"
sudo docker logs \
    -f \
    lums
```

Lorsque c'est possible, reproduisez le problème tout en surveillant les journaux.

Cela facilite la corrélation de :

```text id="p8k4zw"
User action
    ↓
HTTP request
    ↓
Application event
    ↓
Database operation
    ↓
Agent interaction
```

---

# 71. Les journaux applicatifs contiennent une erreur

Identifiez d'abord le composant qui a produit le message.

Les sources typiques comprennent :

```text id="w4c8rn"
Flask application
Gunicorn
Database layer
Authentication
Authorization
Package management
Job execution
Client reporting
```

Ne supposez pas que le dernier message de journal est la cause racine.

Recherchez la première erreur pertinente dans la séquence d'événements.

Lorsque c'est possible, corrélez :

```text id="n6q2vy"
Timestamp
Client
Request
Job ID
Error
Result
```

---

# 72. Journalisation d'audit

LUMS enregistre les actions applicatives relatives à la sécurité dans le journal d'audit.

La journalisation d'audit est utile lors de l'investigation de :

```text id="j8r4px"
User changes
Authentication events
Administrative actions
Client management
Token operations
Update-job creation
Security-relevant state changes
```

Un événement d'audit doit être traité comme une preuve d'un événement applicatif, et non comme un remplacement des journaux système.

Utilisez les journaux applicatifs pour les détails techniques d'exécution et les journaux d'audit pour les actions applicatives relatives à la sécurité.

---

# 73. L'événement d'audit est manquant

Si un événement d'audit attendu est manquant :

1. Identifiez l'action exacte.
2. Identifiez le point de terminaison de l'API.
3. Vérifiez que l'action a réellement atteint le serveur.
4. Examinez les journaux applicatifs.
5. Déterminez si l'action a été rejetée avant que l'événement d'audit n'ait dû être créé.

N'insérez pas manuellement d'enregistrements d'audit simplement pour faire apparaître une piste d'audit complète.

Un enregistrement d'audit doit correspondre à un événement applicatif réel.

---

# 74. Le journal d'audit et le journal applicatif diffèrent

Les deux systèmes de journalisation ont des objectifs différents.

Par exemple :

```text id="7q2m5k"
Application log
→ technical execution information

Audit log
→ security-relevant application event
```

Une erreur du gestionnaire de paquets peut donc apparaître dans le journal applicatif ou de l'agent sans représenter un événement d'audit administratif distinct.

Inversement, une action de gestion des utilisateurs devrait produire un événement applicatif auditable même si l'opération elle-même est techniquement simple.

---

# 75. Informations sensibles dans les journaux

Ne placez jamais intentionnellement ce qui suit dans la sortie de diagnostic :

```text id="3m7v9x"
Client tokens
Application secret keys
Passwords
Session secrets
Private keys
TLS private material
```

Si une commande de diagnostic devait exposer l'une de ces valeurs, utilisez plutôt une vérification rédigée ou basée uniquement sur les métadonnées.

Lors du partage de journaux pour le dépannage, examinez-les pour les secrets avant de les copier dans des tickets, la documentation, des issues GitHub ou un chat.

---

# 76. Sécurité du conteneur Docker

Le conteneur LUMS de production est intentionnellement durci.

Les propriétés de sécurité attendues comprennent :

```text id="z4w6pt"
Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges enabled
No privileged mode
Dedicated writable data volume
Read-only secret mount
Restricted temporary filesystems
```

Si l'une de ces propriétés change de manière inattendue, traitez-la comme une dérive de configuration.

N'affaiblissez pas le conteneur pour résoudre un problème applicatif, sauf si l'impact sur la sécurité a été explicitement évalué.

---

# 77. Vérifier la sécurité d'exécution du conteneur

Examinez le conteneur :

```bash id="b8x5jq"
sudo docker inspect lums
```

Pour une vérification d'exécution ciblée :

```bash id="r3n7cw"
sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums
```

Les valeurs attendues comprennent :

```text id="k5m2zr"
ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]
```

Le formatage exact peut varier entre les versions de Docker.

Ce sont les propriétés de sécurité elles-mêmes qui importent.

---

# 78. Le conteneur fonctionne en tant que root

L'application LUMS devrait fonctionner en tant qu'utilisateur applicatif non privilégié dédié.

Si le conteneur fonctionne de manière inattendue en tant que root, examinez d'abord l'image et la configuration d'exécution :

```bash id="p6x4nz"
sudo docker inspect \
    --format='{{.Config.User}}' \
    lums
```

Examinez ensuite le Dockerfile.

Ne résolvez pas les problèmes de permissions applicatives en faisant passer le conteneur de production en root.

Si un répertoire nécessite un accès en écriture, identifiez le chemin exact et déterminez s'il doit s'agir de données applicatives persistantes ou de données temporaires.

---

# 79. Système de fichiers racine en lecture seule

Le conteneur de production utilise un système de fichiers racine en lecture seule.

Cela protège l'image applicative contre les modifications d'exécution inutiles.

Si l'application signale :

```text id="y5k8mc"
Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data
```

déterminez d'abord **où** l'application tente d'écrire.

Les emplacements inscriptibles attendus sont délibérément limités.

Les données applicatives persistantes appartiennent à :

```text id="q9m3xr"
/var/lib/lums
```

Les données d'exécution temporaires peuvent utiliser les systèmes de fichiers temporaires configurés.

Ne désactivez pas `--read-only` simplement parce qu'un chemin applicatif est devenu inscriptible de manière inattendue.

---

# 80. `/tmp` n'est pas inscriptible

Si l'application nécessite un stockage temporaire, vérifiez le système de fichiers temporaire :

```bash id="a7w4vn"
sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums
```

Le conteneur de production fournit un `/tmp` restreint.

Le système de fichiers temporaire est destiné uniquement aux données transitoires.

Les données persistantes ne doivent pas y être stockées.

---

# 81. Problèmes de montage secret

Le secret applicatif LUMS est fourni via un montage de fichier protégé.

Le secret ne doit pas être intégré directement dans l'image.

Si LUMS signale un secret manquant, examinez d'abord la configuration d'exécution :

```bash id="j4p7zx"
sudo docker inspect \
    lums
```

Vérifiez que le montage secret existe et est en lecture seule.

N'affichez pas le contenu du secret.

Un diagnostic utile consiste à vérifier que le fichier existe et a les permissions attendues sans afficher son contenu.

---

# 82. Le fichier secret est manquant

Si le fichier secret n'existe pas sur l'hôte, le conteneur ne peut pas s'authentifier ou s'initialiser correctement.

Déterminez d'abord si le chemin secret attendu existe.

Ne recréez pas le secret au hasard.

Un secret de remplacement peut invalider les sessions existantes ou d'autres états cryptographiques selon la façon dont l'application l'utilise.

Tout remplacement intentionnel de secret doit donc être traité comme une opération de sécurité contrôlée.

---

# 83. Le volume persistant n'est pas inscriptible

Si LUMS ne peut pas écrire de données applicatives, examinez le volume :

```bash id="y6c2mt"
sudo docker volume inspect \
    lums-data
```

Examinez ensuite les montages du conteneur :

```bash id="e5w8rq"
sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums
```

La base de données applicative doit résider sur le volume persistant inscriptible.

Ne rendez pas l'ensemble du système de fichiers du conteneur inscriptible comme solution de contournement.

La solution correcte est d'identifier le chemin spécifique qui nécessite la persistance.

---

# 84. Le conteneur Docker démarre mais l'application échoue

Si le conteneur démarre et se termine immédiatement :

```bash id="t7x3mp"
sudo docker ps -a \
    --filter name=lums
```

Examinez ensuite :

```bash id="n4q6vz"
sudo docker logs \
    --tail 200 \
    lums
```

Les causes courantes comprennent :

```text id="w3j8kc"
Application startup error
Missing secret
Database initialization error
Migration failure
Invalid environment configuration
Permission problem
Dependency problem
```

Ne reconstruisez pas immédiatement l'image.

Déterminez si le problème se trouve dans l'image, la configuration d'exécution, les données persistantes ou la configuration externe.

---

# 85. Image Docker vs. configuration du conteneur

Une image fonctionnelle peut toujours échouer à cause d'une configuration d'exécution incorrecte.

Distinguez toujours :

```text id="s7q2mj"
Docker image
    +
Container runtime configuration
    +
Persistent volume
    +
Secret/configuration
```

Par exemple :

```text id="m5v9rz"
Image is valid
      +
Wrong volume
      =
Application failure
```

ou :

```text id="r6c3pk"
Image is valid
      +
Missing secret
      =
Application startup failure
```

Ne reconstruisez pas une image par ailleurs valide pour corriger un problème de configuration d'exécution.

---

# 86. Problèmes de construction Docker

Si une nouvelle image ne peut pas être construite, examinez d'abord le Dockerfile.

Vérifiez l'image de base et les définitions de dépendances.

Le Dockerfile de production utilise un digest d'image de base Python épinglé.

Cela offre la reproductibilité et empêche la construction de passer silencieusement à une révision d'image de base non liée.

Si une construction change soudainement de comportement, comparez :

```text id="e3y7pn"
Dockerfile
Base-image digest
Requirements
Application source
Build context
```

---

# 87. Problèmes `.dockerignore`

Le contexte de construction Docker ne doit pas contenir de fichiers locaux inutiles ou de matériel sensible.

Le référentiel utilise `.dockerignore` pour exclure des fichiers tels que :

```text id="k2x8vw"
Local backups
Temporary files
Editor artifacts
Backup copies
Other unnecessary runtime material
```

Si une construction contient de manière inattendue un fichier qui ne devrait pas être présent, examinez :

```bash id="q5m8cz"
cat .dockerignore
```

Ne résolvez pas les problèmes de contexte de construction en copiant des fichiers sensibles dans l'image.

---

# 88. Problèmes de permissions du système de fichiers

Si LUMS signale des erreurs de permission, identifiez d'abord le chemin exact.

Informations utiles :

```bash id="p4r7yn"
sudo docker inspect \
    lums
```

et :

```bash id="n8v2km"
sudo docker logs \
    --tail 200 \
    lums
```

La distinction importante est :

```text id="x6c9pw"
Application data
Temporary data
Application source
Secret material
Host configuration
```

Chacun a des permissions attendues différentes.

Ne modifiez pas récursivement la propriété ou les permissions sur l'ensemble du système de fichiers comme raccourci de dépannage.

---

# 89. Dérive de configuration de production

La dérive de configuration se produit lorsque l'environnement d'exécution ne correspond plus à la base de sécurité prévue.

Les exemples comprennent :

```text id="r5j8tx"
Container runs as root
Port 5050 exposed externally
Read-only filesystem disabled
Capabilities restored
Privileged mode enabled
Secret mounted read-write
Unexpected container running
```

Si une dérive est détectée :

1. Enregistrez l'état actuel.
2. Déterminez quand il a changé.
3. Identifiez la configuration responsable.
4. Corrigez délibérément la configuration.
5. Réexécutez la vérification de sécurité pertinente.

Ne faites pas plusieurs modifications non liées à la fois.

---

# 90. Exposition réseau inattendue

Le port applicatif devrait rester local :

```text id="n7w4cp"
127.0.0.1:5050
```

Vérifiez les écouteurs :

```bash id="y2m6vk"
sudo ss -lntp
```

Si `5050` est exposé sur une adresse non-loopback, examinez immédiatement le mappage de port Docker.

N'exposez pas le port applicatif simplement parce que Nginx semble difficile à diagnostiquer.

L'architecture prévue est :

```text id="h3x8qm"
Network
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS
```

---

# 91. Conteneurs Docker inattendus

Listez tous les conteneurs :

```bash id="c6w9rz"
sudo docker ps -a
```

Les conteneurs inattendus doivent être identifiés avant d'être supprimés.

Vérifiez :

```text id="m8x2kf"
Container name
Image
Creation time
Ports
Volumes
Restart policy
```

Ne supprimez pas un conteneur inconnu sans déterminer s'il fait partie du déploiement LUMS ou d'un environnement de secours requis.

---

# 92. Le volume Docker ne doit pas être supprimé pendant le dépannage normal

L'opération suivante est destructive :

```bash id="q7v3mc"
sudo docker volume rm lums-data
```

Elle ne doit pas être utilisée comme étape de dépannage générale.

La suppression du volume peut supprimer la base de données applicative et l'état persistant associé.

Si une installation propre est intentionnellement requise, traitez-la comme une opération de migration ou de récupération distincte et vérifiez d'abord les sauvegardes.

---

# 93. Base de sécurité après modifications d'exécution

Après avoir modifié la configuration Docker de production, vérifiez à nouveau la base de sécurité.

Vérifiez au minimum :

```text id="z5n8xp"
Container runs as intended user
Root filesystem is read-only
Capabilities are dropped
Privileged mode is disabled
no-new-privileges is enabled
Secret mount is read-only
Database volume is writable
Application port is loopback-only
```

Une configuration qui fait fonctionner l'application mais affaiblit ces propriétés ne doit pas être considérée comme un correctif réussi.

---

# 94. Prochain domaine de dépannage

Les sujets de dépannage restants sont :

```text id="v4m7yx"
Tests and CI
Diagnostic snapshots
Common failure combinations
Recovery principles
Final troubleshooting checklist
```

Les sections finales fournissent une procédure compacte pour collecter suffisamment d'informations pour diagnostiquer un problème sans modifier inutilement l'environnement de production.

# 95. Tests et CI

Les tests automatisés sont une partie importante du dépannage de LUMS.

Avant d'investiguer un problème de production comme un défaut applicatif, vérifiez si le comportement pertinent est déjà couvert par la suite de tests.

La suite de tests complète actuelle devrait réussir avant qu'une version ne soit considérée comme prête.

Exécutez la suite de tests complète depuis le référentiel :

```bash id="m4x8kp"
./.venv-test/bin/pytest -q
```

Une exécution réussie devrait rapporter tous les tests comme réussis.

Le nombre de tests change à mesure que des tests supplémentaires sont ajoutés. La condition importante est que la suite de tests complète réussisse plutôt que de se fier à un nombre de tests fixe.

---

# 96. Un échec de test ne signifie pas automatiquement que la production est cassée

Un test échoué peut être causé par :

```text id="q8r5wy"
Application regression
Test regression
Dependency change
Environment problem
Missing test dependency
Incorrect test configuration
```

Examinez d'abord la sortie d'échec complète.

Ne modifiez pas la configuration de production simplement parce qu'un test local échoue.

La séquence correcte est :

```text id="n4m7tx"
Test failure
    ↓
Read complete error
    ↓
Identify affected component
    ↓
Reproduce locally
    ↓
Determine root cause
    ↓
Apply controlled fix
    ↓
Run relevant tests
    ↓
Run full test suite
```

---

# 97. Échecs des tests RBAC

Lors de l'investigation de problèmes d'autorisation, exécutez d'abord les tests RBAC :

```bash id="k6w2pv"
./.venv-test/bin/pytest -q tests/test_rbac.py
```

Les tests couvrent le comportement spécifique aux rôles et les frontières d'autorisation.

Si le problème concerne la page client, utilisez le sous-ensemble pertinent le cas échéant :

```bash id="z5n8rc"
./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page
```

N'affaiblissez pas l'autorisation pour faire réussir un test.

Un test d'autorisation échoué peut indiquer une régression de sécurité.

---

# 98. Échecs des tests de recherche de paquets

La fonctionnalité de gestion des paquets a une couverture de test dédiée.

Lors de l'investigation du comportement de recherche de paquets :

```bash id="b7x3mf"
./.venv-test/bin/pytest -q \
    tests/test_package_search.py
```

Si l'échec implique l'exécution des paquets ou les résultats des jobs, examinez également les tests pertinents de résultat de job.

La suite de tests doit être utilisée pour distinguer :

```text id="y9r4nk"
Application logic problem
Package-search problem
Agent problem
Integration problem
```

---

# 99. Tests de validation des résultats de jobs

La gestion des résultats de jobs est sensible à la sécurité car le serveur ne doit pas faire aveuglément confiance à une entrée client arbitraire.

Exécutez les tests pertinents lors de l'investigation de la validation des résultats :

```bash id="w6q2vz"
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Un échec ici doit être traité comme un problème de correction applicative et de sécurité.

Ne contournez pas la validation des résultats pour faire réussir un rapport client.

---

# 100. Échecs CI

LUMS utilise l'intégration continue pour vérifier le projet avant que les modifications ne soient acceptées.

Si CI échoue :

1. Identifiez le job échoué.
2. Lisez l'erreur complète.
3. Déterminez si l'échec est lié au code, aux dépendances, aux tests ou à l'environnement.
4. Reproduisez localement lorsque c'est possible.
5. Corrigez la cause racine.
6. Exécutez les tests pertinents.
7. Exécutez la suite de tests complète.

N'ignorez pas les échecs CI simplement parce que l'environnement de production semble actuellement fonctionnel.

---

# 101. Instantané de diagnostic

Lorsque vous demandez de l'aide pour un problème LUMS, collectez un instantané de diagnostic minimal.

L'objectif est de fournir suffisamment d'informations pour identifier le composant en échec sans exposer de secrets.

Un instantané utile comprend :

```bash id="x8p4qn"
sudo docker ps
```

```bash id="c5m7vz"
sudo docker logs --tail 100 lums
```

```bash id="f2w9yk"
sudo systemctl status nginx --no-pager
```

```bash id="n6r3tx"
sudo systemctl status lums-agent.service --no-pager
```

```bash id="q7v4mc"
sudo systemctl status lums-agent-watcher.service --no-pager
```

```bash id="z3k8wp"
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

```bash id="h5m2rx"
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

```bash id="p9x6kc"
sudo ss -lntp
```

Utilisez uniquement les commandes pertinentes au problème.

Ne videz pas l'environnement complet dans une demande de support.

---

# 102. L'instantané de diagnostic ne doit pas contenir de secrets

Avant de partager la sortie de diagnostic, vérifiez :

```text id="r4m8yn"
Passwords
Client tokens
Application secret keys
Session secrets
Private keys
TLS private material
Credentials
```

Rédigez les valeurs sensibles avant de partager.

Ne supposez pas qu'un journal est sûr simplement parce qu'il provient d'un service système.

---

# 103. Matrice de combinaison d'échecs

Certains symptômes deviennent plus faciles à diagnostiquer lorsque plusieurs composants sont considérés ensemble.

| Symptôme                                     | Zone la plus probable à inspecter en premier |
| -------------------------------------------- | -------------------------------------------- |
| Le navigateur ne peut pas se connecter      | Nginx / TLS / réseau                         |
| Nginx fonctionne mais l'application échoue  | Docker / LUMS                                |
| LUMS fonctionne mais le client ne peut pas rapporter | Agent / TLS / token               |
| Le client rapporte mais le job reste en attente | Watcher / éligibilité                    |
| Le job s'exécute mais le paquet échoue      | APT / pacman                                 |
| Le paquet réussit mais le résultat est manquant | Rapport de l'agent                       |
| Le résultat atteint le serveur mais l'UI est obsolète | API / base de données / état du navigateur |
| Le Viewer peut modifier les données         | RBAC côté serveur                            |
| L'utilisateur ne peut pas se connecter      | Compte / mot de passe / limitation du taux   |
| La connexion fonctionne mais l'action est rejetée | RBAC / CSRF                             |
| Les écritures en base de données échouent   | SQLite / disque / permissions                |
| Le conteneur perd des données après recréation | Configuration du volume persistant        |
| L'application écrit sur le système de fichiers racine | Configuration du système de fichiers du conteneur |
| Le port 5050 est accessible de l'extérieur  | Configuration Docker / pare-feu              |

Ce tableau identifie le premier endroit à investiguer, pas nécessairement la cause racine finale.

---

# 104. Erreurs courantes de dépannage

Évitez les raccourcis suivants :

## Ne supprimez pas la base de données

```text id="h7k2px"
Deleting lums.db
Deleting lums-data
```

peut détruire l'état applicatif persistant.

---

## Ne désactivez pas les contrôles de sécurité

Ne désactivez pas de manière permanente :

```text id="j5r9cw"
RBAC
CSRF protection
TLS validation
Container hardening
Read-only filesystem
no-new-privileges
Capability restrictions
```

Un contournement qui supprime un contrôle de sécurité n'est pas un correctif terminé.

---

## N'exécutez pas le conteneur en mode privilégié

Évitez :

```text id="b3x7mz"
--privileged
```

comme solution de dépannage.

Si l'application nécessite un accès supplémentaire, déterminez exactement quel accès est requis.

---

## N'exposez pas le port 5050

Ne changez pas :

```text id="v8n4qr"
127.0.0.1:5050
```

en :

```text id="p2m6wy"
0.0.0.0:5050
```

simplement pour contourner Nginx.

L'application est intentionnellement protégée derrière le proxy inverse.

---

## Ne modifiez pas manuellement les états des jobs

Évitez de modifier directement :

```text id="r7c5xn"
update_jobs
update_job_packages
```

pour masquer un problème opérationnel.

Utilisez les mécanismes de l'application, de l'agent, du watcher et de récupération.

---

## Ne supprimez pas aveuglément les verrous du gestionnaire de paquets

Un verrou peut indiquer un processus de gestionnaire de paquets actif.

Identifiez d'abord le processus.

---

## Ne faites pas tourner les identifiants de manière répétée

Une rotation répétée des tokens ou secrets peut créer des problèmes d'authentification supplémentaires.

Déterminez d'abord quel identifiant est actuellement configuré et quel identifiant le serveur attend.

---

# 105. Principes de récupération

Les principes suivants s'appliquent à tout dépannage LUMS :

### Préserver d'abord

Conservez :

```text id="q3m8vx"
Logs
Job state
Database
Container state
Configuration
Error messages
```

jusqu'à ce que le problème soit compris.

### Changez une chose à la fois

Lorsque plusieurs modifications sont effectuées simultanément, la cause d'origine devient plus difficile à identifier.

### Vérifiez après chaque modification

Après une modification contrôlée :

```text id="z6w2kp"
Re-test
Check logs
Verify state
Confirm security properties
```

### Préférez les modifications réversibles

Lorsque c'est possible, utilisez des modifications qui peuvent être annulées sans détruire l'état applicatif.

### Maintenez les contrôles de sécurité actifs

Un résultat de dépannage réussi ne doit pas introduire de régression de sécurité inutile.

---

# 106. Séquence de dépannage de production

Pour un problème général de production LUMS, utilisez cet ordre :

```text id="f4n8rx"
1. Identify the symptom
        ↓
2. Identify the affected component
        ↓
3. Inspect current state
        ↓
4. Inspect relevant logs
        ↓
5. Reproduce safely
        ↓
6. Determine the first failing layer
        ↓
7. Apply the smallest required change
        ↓
8. Re-test
        ↓
9. Verify security controls
        ↓
10. Document the result
```

Cet ordre empêche la modification inutile de composants non liés.

---

# 107. Chemin de diagnostic système complet

Lorsque le composant affecté est inconnu, suivez le chemin complet :

```text id="u7x3mp"
Browser
  │
  ▼
Nginx / HTTPS
  │
  ▼
Docker
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Update Job
  │
  ▼
Watcher
  │
  ▼
Agent
  │
  ▼
APT / pacman
  │
  ▼
Client state
  │
  ▼
Agent result
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Web UI
```

À chaque étape, demandez :

```text id="k5r2qy"
Did the request reach this component?

Did this component process it?

Did it produce the expected result?

Did the next component receive that result?
```

Le premier `NON` identifie normalement la zone qui nécessite une investigation.

---

# 108. Dépannage de release

Avant de préparer une version, vérifiez :

```text id="m8x4vp"
Full test suite passes
CI passes
Security audit is complete
Documentation is current
Production configuration matches the documented baseline
No unexpected debug configuration remains
No secrets are included in the repository
Docker hardening remains active
RBAC behavior is correct
Package management works
Update-job execution works
Recovery behavior is verified
```

Une version ne doit pas être créée simplement parce que l'application démarre avec succès.

---

# 109. Liste de contrôle de dépannage

Utilisez cette liste avant de déclarer un problème de production résolu :

```text id="y6q3kn"
[ ] Root cause identified
[ ] Relevant logs inspected
[ ] No unnecessary data was deleted
[ ] No credentials were exposed
[ ] No security control was disabled
[ ] Relevant functionality tested
[ ] Full test suite considered where appropriate
[ ] Docker security baseline verified
[ ] Network exposure verified
[ ] Agent state verified
[ ] Watcher state verified
[ ] Job state verified
[ ] Recovery state verified
[ ] Database state verified where relevant
[ ] Documentation updated if behavior changed
```

---

# 110. Quand arrêter le dépannage

Arrêtez de faire des modifications lorsque :

```text id="v9m4xr"
The root cause is identified
    AND
The corrective action is understood
    AND
The system is stable
    AND
Security controls remain intact
```

Si la cause racine n'est pas comprise, préservez l'état actuel plutôt que de modifier l'environnement de manière répétée.

Un échec proprement préservé est plus facile à diagnostiquer qu'un système partiellement modifié.

---

# 111. Principe de récupération final

La règle de dépannage LUMS la plus importante est :

> **Observer d'abord. Modifier ensuite. Vérifier en troisième.**

LUMS contient plusieurs couches indépendantes de sécurité et d'exécution.

Un problème dans une couche ne devrait pas automatiquement entraîner des modifications dans une autre.

L'approche de dépannage préférée est donc :

```text id="c8w5zn"
Observe
   ↓
Classify
   ↓
Isolate
   ↓
Correct
   ↓
Verify
   ↓
Document
```

Cela maintient le dépannage contrôlé, reproductible et compatible avec la base de sécurité LUMS.

---

# 112. Maintenance de la documentation

Ce document devrait être mis à jour chaque fois qu'un comportement opérationnel documenté change.

Les modifications de documentation doivent rester cohérentes avec :

```text id="q7m3vx"
Security documentation
Deployment documentation
Agent behavior
Watcher behavior
RBAC model
Package-management behavior
Docker runtime configuration
Test baseline
```

Les instructions de dépannage obsolètes peuvent être dangereuses lorsqu'elles recommandent des commandes dépréciées ou des contournements affaiblissant la sécurité.

Lorsqu'un comportement de production change, mettez à jour la documentation pertinente avant de considérer la procédure de dépannage comme terminée.

---

# 113. Base actuelle

La base LUMS actuelle documentée par ce guide de dépannage comprend :

```text id="m4x8qp"
Agent version: 1.7.0
Watcher version: 1.2.1

Application port:
127.0.0.1:5050

Database:
SQLite

SQLite journal mode:
delete

SQLite busy timeout:
5000 ms

SQLite synchronous:
2

SQLite foreign keys:
Enabled by the application

Container:
Non-root
Read-only root filesystem
Capabilities dropped
no-new-privileges enabled
Privileged mode disabled

RBAC:
Administrator
Operator
Viewer

Viewer:
Clients + Installed Software only

Full test suite:
Passing baseline
```

Le nombre exact de tests peut changer à mesure que le projet grandit.

Les propriétés de sécurité et d'architecture sont la base importante.

---

# 114. Fin du guide de dépannage

Le dépannage LUMS doit rester fondé sur les preuves et conscient de la sécurité.

En cas de doute :

```text id="r9x4kw"
Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.
```

N'échangez pas la sécurité ou l'intégrité des données contre un contournement rapide.

---

**Fin du guide de dépannage LUMS**
