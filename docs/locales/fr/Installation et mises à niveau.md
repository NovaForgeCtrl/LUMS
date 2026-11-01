# Guide d'installation de LUMS

## Serveur de gestion des mises à jour Linux

**Projet :** LUMS
**Slogan :** Gestion des mises à jour Linux sans le bruit.
**Dépôt :** `NovaForgeCtrl/LUMS`

---

## Pour commencer : Comprendre l'installation avant de commencer

Ce guide couvre une installation complète du serveur, y compris des procédures avancées de maintenance et de vérification. Ce n'est **pas** un simple script à exécuter sans vérification : le nom du serveur, le certificat TLS, le fichier secret, la destination de sauvegarde, le réseau et la base de données varient d'une installation à l'autre.

### Qu'est-ce qui est installé ?

* **Serveur LUMS :** l'interface web et l'API, exécutés dans un conteneur Docker.
* **Nginx :** accepte les connexions HTTPS externes et les transmet localement au conteneur.
* **Volume de données :** contient la base de données SQLite. Ce volume doit survivre aux mises à niveau et ne doit jamais être supprimé lors d'un remplacement normal de conteneur.
* **Fichier secret :** protège les sessions applicatives, entre autres. Ne le placez jamais dans le dépôt Git, une image Docker ou un message de chat.
* **LUMS Agent et Watcher :** installés séparément sur les clients Linux gérés. Un serveur fonctionnel seul ne met à jour aucun client.

| Terme | Signification |
| --- | --- |
| Terminal / shell | Une fenêtre de texte où vous saisissez des commandes Linux. |
| `sudo` | Exécute la commande qui suit avec les droits d'administrateur. Linux peut demander votre mot de passe. |
| Hôte | L'ordinateur Linux exécutant Docker et le serveur LUMS. |
| Conteneur | Un processus isolé exécutant l'application web LUMS. |
| Image | Un modèle préparé que Docker utilise pour démarrer un conteneur. |
| Volume | Stockage Docker persistant qui reste lorsqu'un conteneur est remplacé. |
| Espace réservé | Texte tel que `LUMS-SERVER` qui doit être remplacé par votre valeur réelle. |

### Exécuter uniquement les tests (cela n'installe pas de serveur)

Ces étapes conviennent à Debian 13 pour extraire la source et exécuter les tests localement. Elles ne créent **pas** de serveur de production accessible sur le réseau et n'installent pas d'agent sur un autre ordinateur. `sudo` n'est nécessaire que pour installer les paquets Debian.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q
```

`apt update` actualise les listes de paquets ; cela ne met pas à niveau tous les logiciels installés. L'environnement virtuel Python `.venv-test` maintient les dépendances de test séparées du reste du système. Une exécution de test réussie se termine avec le code `0` ; le nombre de tests peut changer au fur et à mesure que le projet évolue. Si la création de l'environnement échoue, vérifiez que `python3-venv` est installé. Si un test échoue, enregistrez l'erreur complète et lisez le [guide de dépannage](Dépannage.md) ; ne supprimez pas les données de production.

Pour une installation réelle, continuez avec les sections numérotées et lisez d'abord les instructions de sécurité et de sauvegarde. Si LUMS est déjà en cours d'exécution, utilisez la procédure de mise à niveau dans [`administration.md`](<Administration et sauvegardes.md>), et non la procédure de première installation.

---

# 1. Aperçu

LUMS est une plateforme centralisée de gestion des mises à jour Linux pour la distribution contrôlée des mises à jour, les rapports des clients, la gestion des paquets, l'exécution des jobs de mise à jour, la validation des résultats et l'administration auditable.

L'architecture actuelle sépare le serveur de gestion des clients Linux gérés.

Le serveur fournit :

* Administration basée sur le web
* Gestion des clients
* Authentification des clients
* Inventaire des paquets
* Rapports sur les mises à jour disponibles
* Recherche de paquets
* Installation et suppression de paquets
* Gestion des jobs de mise à jour
* Validation des résultats des jobs
* Historique des mises à jour
* Contrôle d'accès basé sur les rôles
* Journalisation d'audit
* État persistant basé sur SQLite

Les clients Linux fournissent :

* Informations système
* Inventaire des paquets installés
* Détection des mises à jour disponibles
* Opérations sur les paquets
* Exécution des jobs de mise à jour
* Détection de l'état d'inactivité
* Points de contrôle et récupération des jobs
* Détection de redémarrage
* Rapports de résultats

L'implémentation actuelle prend en charge :

```text
Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman
```

---

# 2. Architecture

L'architecture de production est :

```text
                         LUMS Server
                              │
                              │ HTTPS :443
                              ▼
                       ┌──────────────┐
                       │    Nginx     │
                       │  TLS / Proxy │
                       └──────┬───────┘
                              │
                              │ HTTP
                              ▼
                       127.0.0.1:5050
                              │
                              ▼
                    ┌───────────────────┐
                    │   Docker: lums    │
                    │                   │
                    │   Gunicorn        │
                    │   Flask :5000     │
                    │   SQLite          │
                    └─────────┬─────────┘
                              │
                              ▼
                         lums-data
                              │
                              ▼
                   /var/lib/lums/lums.db


        Linux Client
              │
              │ HTTPS + Bearer Token
              ▼
         LUMS API
              │
              ├── Report
              ├── Package Search
              ├── Job Retrieval
              └── Job Result
```

L'application LUMS n'est **pas destinée à être directement exposée au réseau**.

Le conteneur applicatif est lié à :

```text
127.0.0.1:5050 → container:5000
```

Nginx est le point d'entrée HTTPS externe.

Le port `5000` n'est pas publié directement.

Le port `5050` doit rester limité à localhost.

---

# 3. Composants de l'application

Une installation complète de LUMS se compose de plusieurs composants.

## 3.1 Serveur LUMS

Le serveur contient :

```text
Flask
Gunicorn
SQLite
Web UI
REST API
Authentication
RBAC
Audit logging
Job management
Package management
```

L'application s'exécute dans le conteneur Docker :

```text
lums
```

La base de données persistante est stockée en dehors du système de fichiers applicatif inscriptible du conteneur :

```text
lums-data:/var/lib/lums/lums.db
```

---

## 3.2 Nginx

Nginx fournit :

```text
HTTPS termination
TLS certificate handling
HTTP → HTTPS redirect
Reverse proxy
External network entry point
```

Le chemin de requête prévu est :

```text
Browser
   │
   │ HTTPS
   ▼
Nginx
   │
   │ localhost HTTP
   ▼
127.0.0.1:5050
   │
   ▼
LUMS
```

L'application Flask/Gunicorn ne doit pas être directement exposée au LAN.

---

## 3.3 Agent Linux

L'agent LUMS s'exécute sur chaque client Linux géré.

La version actuelle de l'agent est :

```text
1.7.0
```

L'agent est responsable de :

```text
System information
Installed packages
Available updates
Client reporting
Job retrieval
Job claiming
Package operations
Result reporting
Reboot detection
```

L'agent communique avec le serveur LUMS via HTTPS et un token Bearer spécifique au client.

---

## 3.4 Execution Watcher

Le watcher d'exécution est responsable de l'exécution contrôlée des jobs de mise à jour.

La version actuelle du Watcher est :

```text
1.2.1
```

Le Watcher gère :

```text
Pending-job detection
Idle-state checks
Atomic job claiming
Update execution
Checkpoint handling
Interrupted-job recovery
Result processing
```

Le Watcher est intentionnellement séparé des rapports ordinaires des clients.

---

# 4. Modèle de sécurité

L'installation doit préserver la base de sécurité de LUMS.

Le serveur de production utilise :

```text
HTTPS
Bearer-token client authentication
Role-based web authorization
CSRF protection
Audit logging
Read-only container root filesystem
Dropped Linux capabilities
no-new-privileges
Non-root application user
Localhost-only application port
Persistent Docker volume
Read-only secret mount
```

Le conteneur Docker s'exécute en tant qu'utilisateur non privilégié :

```text
lums
```

avec l'UID :

```text
10001
```

Le conteneur ne doit pas s'exécuter en mode privilégié.

Le système de fichiers racine doit rester en lecture seule.

L'application ne doit pas nécessiter d'accès en écriture à son répertoire applicatif.

Les données applicatives persistantes sont stockées via le volume Docker dédié.

---

# 5. Modèle RBAC actuel

LUMS fournit actuellement trois rôles web :

```text
administrator
operator
viewer
```

## Administrator

Les administrateurs peuvent effectuer des opérations administratives, notamment :

```text
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

---

## Operator

Les opérateurs peuvent effectuer la gestion opérationnelle :

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Les opérateurs n'ont pas accès à :

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

---

## Viewer

Les Viewers ont un accès intentionnellement restreint.

Un Viewer peut accéder à :

```text
Clients
Installed software
```

Les domaines de gestion suivants sont masqués dans l'interface Viewer et protégés côté serveur :

```text
Available updates
Update Jobs
Update History
Package Management
System Maintenance
```

Le masquage de l'interface n'est donc pas la frontière de sécurité.

L'autorisation côté serveur reste obligatoire.

---

# 6. Exigences d'installation

## 6.1 Serveur LUMS

Le déploiement actuel nécessite un hôte Linux avec :

```text
Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage
```

Le serveur doit disposer de suffisamment d'espace de stockage pour :

```text
Docker images
SQLite database
Application data
Logs
Backups
```

L'application LUMS elle-même s'exécute dans Docker.

---

## 6.2 Clients Linux

Les clients Linux gérés nécessitent :

```text
Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate
```

Familles de gestion de paquets prises en charge :

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

Le client doit pouvoir atteindre le point de terminaison HTTPS de LUMS.

---

# 7. Disposition de répertoire recommandée

L'emplacement recommandé du référentiel côté serveur est :

```text
/opt/lums-public/
```

Le référentiel contient le code source de l'application, le code source de l'agent et les tests.

Une installation typique utilise :

```text
/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt
```

La configuration côté hôte est conservée en dehors du référentiel :

```text
/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key
```

Les données applicatives persistantes sont stockées dans :

```text
lums-data:/var/lib/lums
```

La base de données SQLite est :

```text
/var/lib/lums/lums.db
```

La base de données ne doit jamais être stockée dans l'arborescence de travail Git.

Les secrets et le matériel TLS privé doivent également rester en dehors du référentiel.

---

# 8. Préparation du référentiel

Clonez le référentiel dans le répertoire d'installation prévu :

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Entrez dans le référentiel :

```bash
cd /opt/lums-public
```

Vérifiez l'arborescence de travail :

```bash
git status
```

Inspectez la révision actuelle :

```bash
git log -1 --oneline --decorate
```

Pour les déploiements contrôlés, le commit exact utilisé pour l'installation doit être enregistré.

Ne construisez pas d'images de production à partir d'une arborescence de travail inconnue ou non vérifiée.

---

# 9. Vérification de sécurité du référentiel

Avant de construire l'image de production, vérifiez que les fichiers sensibles n'ont pas été placés dans le référentiel.

Examinez l'arborescence de travail :

```bash
git status --short
```

Examinez les fichiers ignorés le cas échéant :

```bash
git status --ignored --short
```

Le référentiel ne doit pas contenir :

```text
Production database files
Private TLS keys
Application secrets
Client tokens
Credential dumps
Backup databases
Runtime logs
Temporary backup files
```

Le projet utilise des règles d'ignorance du référentiel pour empêcher les artefacts de sauvegarde courants d'être accidentellement suivis.

Avant de valider les modifications, inspectez soigneusement la liste des fichiers indexés.

---

# 10. Préparer les répertoires de configuration de l'hôte

Créez les répertoires côté hôte requis :

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

Le répertoire secret contient le secret applicatif.

Le répertoire TLS contient le certificat TLS et la clé privée.

La protection de ces répertoires réduit le risque de divulgation accidentelle.

Vérifiez :

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls
```

---

# 11. Créer le secret applicatif

Le secret applicatif LUMS est stocké sur l'hôte plutôt qu'intégré directement dans l'image Docker.

Le chemin du secret de production est :

```text
/etc/lums/secrets/lums_secret
```

Générez un secret aléatoire :

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Protégez le fichier résultant :

```bash
sudo chmod 600 \
    /etc/lums/secrets/lums_secret
```

Vérifiez les permissions sans afficher le secret :

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

Attendu :

```text
600
```

Le secret ne doit jamais être :

```text
Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation
```

Le conteneur reçoit le secret via un montage de liaison en lecture seule.

---

# 12. Préparer le matériel TLS

LUMS utilise HTTPS pour l'accès externe.

Les emplacements recommandés côté hôte sont :

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Installez le certificat et la clé privée appropriés avant de configurer Nginx.

Protégez la clé privée :

```bash
sudo chmod 600 \
    /etc/lums/tls/lums.key
```

Le certificat peut être lisible par le service Nginx :

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

Vérifiez :

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

La clé privée ne doit jamais être validée dans Git ni incluse dans l'image Docker.

---

# 13. Principe d'installation

L'installation doit se dérouler par étapes contrôlées :

```text
Repository
    ↓
Host configuration
    ↓
Application secret
    ↓
TLS material
    ↓
Docker image
    ↓
Persistent volume
    ↓
Hardened container
    ↓
Nginx / HTTPS
    ↓
Administrator
    ↓
Server validation
    ↓
Linux clients
```

Ne connectez pas les clients de production avant que le serveur n'ait passé ses propres contrôles de validation.

Les sections suivantes continuent avec la construction de l'image Docker et le déploiement de production durci.

# 14. Construire l'image Docker LUMS

Avant de construire l'image de production, assurez-vous que le référentiel est dans l'état prévu.

Entrez dans le référentiel :

```bash
cd /opt/lums-public
```

Exécutez la suite de tests avant de créer une image de production :

```bash
./.venv-test/bin/pytest -q
```

Le nombre de tests devrait augmenter au fur et à mesure que le projet évolue.

L'exigence importante est que la suite de tests pertinente se termine avec succès avant le déploiement.

Construisez l'image Docker :

```bash
sudo docker build \
    -t lums:latest \
    .
```

Vérifiez que l'image existe :

```bash
sudo docker image ls lums
```

Inspectez l'image :

```bash
sudo docker image inspect lums:latest
```

L'image de production est basée sur une image de base Python 3.13 slim épinglée.

Le Dockerfile utilise également des dépendances de production épinglées lorsque nécessaire.

---

# 15. Examiner la construction Docker

Avant de déployer l'image, examinez la sortie de construction pour détecter des erreurs ou des avertissements inattendus.

Vérifiez l'image résultante :

```bash
sudo docker inspect \
    lums:latest
```

Vérifiez l'utilisateur applicatif configuré :

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

L'application est destinée à s'exécuter en tant que :

```text
lums
```

L'application ne doit pas nécessiter de privilèges root pendant l'exécution normale.

Examinez le Dockerfile lors de la modification du processus de construction :

```bash
sed -n '1,240p' Dockerfile
```

N'ajoutez pas de secrets, de certificats ou de bases de données de production au contexte de construction Docker.

Le référentiel contient un fichier `.dockerignore` pour réduire le risque d'inclure accidentellement des artefacts d'exécution dans l'image.

---

# 16. Créer le volume Docker persistant

Créez le volume de données persistant LUMS :

```bash
sudo docker volume create lums-data
```

Vérifiez :

```bash
sudo docker volume inspect lums-data
```

Le volume stocke les données applicatives persistantes :

```text
lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db
```

Le système de fichiers du conteneur lui-même ne doit pas être traité comme un stockage applicatif persistant.

La base de données survit donc au remplacement du conteneur tant que le volume `lums-data` est préservé.

> [!IMPORTANT]
> Ne supprimez jamais `lums-data` lors d'une mise à niveau normale de l'application.

La suppression du volume supprime la base de données SQLite stockée à l'intérieur.

---

# 17. Vérifier le volume persistant

Avant de démarrer LUMS, confirmez que le volume existe :

```bash
sudo docker volume inspect \
    lums-data
```

Le volume peut également être vérifié via Docker :

```bash
sudo docker volume ls | grep lums-data
```

Un volume nouvellement créé ne contiendra normalement pas encore de base de données.

La base de données est initialisée par l'application LUMS lors du déploiement.

---

# 18. Configuration du conteneur de production

Le conteneur de production utilise plusieurs contrôles de sécurité simultanément.

La base d'exécution attendue est :

```text
Non-root user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
No privileged mode
Localhost-only application binding
Read-only application-secret mount
Persistent writable data volume
Dedicated /tmp tmpfs
```

Le port applicatif n'est publié que sur localhost :

```text
127.0.0.1:5050 → container:5000
```

Le point de terminaison HTTPS externe est fourni par Nginx.

---

# 19. Démarrer le conteneur LUMS durci

Avant de démarrer un nouveau conteneur de production, assurez-vous qu'aucun autre conteneur nommé `lums` n'est déjà en cours d'exécution :

```bash
sudo docker ps \
    --filter name=lums
```

Si un déploiement existant est remplacé, préservez le conteneur existant jusqu'à ce que la nouvelle image ait été validée.

Démarrez le conteneur durci :

```bash
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
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:latest
```

Le secret applicatif est monté en lecture seule.

La base de données SQLite est stockée dans le volume persistant.

Le système de fichiers racine est en lecture seule.

Toutes les capacités Linux sont abandonnées.

L'option de sécurité `no-new-privileges` empêche les processus à l'intérieur du conteneur d'acquérir des privilèges supplémentaires.

---

# 20. Vérifier l'état du conteneur

Vérifiez le conteneur en cours d'exécution :

```bash
sudo docker ps \
    --filter name=lums
```

État attendu :

```text
Up ...
```

Vérifiez directement l'état du conteneur :

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Attendu :

```text
running
```

Examinez les journaux récents :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Les erreurs de démarrage de l'application doivent être résolues avant de poursuivre l'installation.

---

# 21. Vérifier la sécurité du conteneur

Examinez la configuration de sécurité effective à l'exécution :

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

La base attendue est :

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Le formatage exact de la sortie Docker peut varier.

La configuration effective est ce qui compte.

---

# 22. Vérifier le port applicatif

Vérifiez le port Docker publié :

```bash
sudo docker port lums
```

Attendu :

```text
5000/tcp -> 127.0.0.1:5050
```

Ce qui suit n'est **pas** acceptable pour l'application de production :

```text
0.0.0.0:5050
```

ou :

```text
0.0.0.0:5000
```

L'application est intentionnellement accessible uniquement via le chemin de proxy inverse local.

Vérifiez les sockets en écoute :

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Seule la liaison applicative localhost doit être présente.

---

# 23. Vérifier le montage secret

Confirmez que le secret est monté :

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

Le secret applicatif devrait apparaître similaire à :

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

La sortie exacte peut contenir des informations de montage supplémentaires.

La propriété importante est :

```text
RW=false
```

N'affichez jamais le contenu du secret.

Un test de lisibilité direct est suffisant :

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Attendu :

```text
secret mount: OK
```

---

# 24. Vérifier le montage du volume persistant

Examinez les montages du conteneur :

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'
```

Le volume de données LUMS doit être monté à :

```text
/var/lib/lums
```

et doit être inscriptible :

```text
RW=true
```

La relation attendue est :

```text
lums-data
    ↓
/var/lib/lums
```

Le système de fichiers racine reste en lecture seule tandis que le volume de données dédié fournit l'accès en écriture persistant requis.

---

# 25. Vérifier le système de fichiers racine en lecture seule

Le système de fichiers racine de l'application doit être en lecture seule.

Le runtime du conteneur devrait signaler :

```text
ReadonlyRootfs=true
```

Un test d'écriture contrôlé peut être effectué à l'intérieur du conteneur.

Par exemple :

```bash
sudo docker exec lums \
    sh -c 'touch /app/.write-test'
```

La commande devrait échouer car `/app` fait partie du système de fichiers en lecture seule du conteneur.

Ne désactivez pas le système de fichiers racine en lecture seule simplement parce qu'un composant applicatif tente d'écrire en dehors de ses emplacements inscriptibles désignés.

Si l'application nécessite des données persistantes, utilisez le volume approprié ou le système de fichiers d'exécution.

---

# 26. Vérifier le système de fichiers temporaire inscriptible

Le conteneur fournit un tmpfs `/tmp` dédié.

Vérifiez :

```bash
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'
```

Attendu :

```text
tmpfs: OK
```

Le système de fichiers temporaire est configuré avec :

```text
noexec
nosuid
```

et une limite de taille.

Cela fournit un stockage temporaire inscriptible sans rendre le système de fichiers racine du conteneur inscriptible.

---

# 27. Vérifier le répertoire de données applicatives

L'application LUMS nécessite un accès en écriture à son répertoire de données persistant.

Test :

```bash
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'
```

Attendu :

```text
data volume: OK
```

Cela confirme que le volume inscriptible dédié est disponible tandis que le reste du conteneur reste en lecture seule.

---

# 28. Vérifier l'utilisateur applicatif

Confirmez l'utilisateur effectif à l'exécution :

```bash
sudo docker exec lums \
    id
```

Le processus devrait s'exécuter en tant qu'utilisateur LUMS non privilégié.

L'identité attendue comprend :

```text
uid=10001(lums)
```

Les informations de groupe exactes peuvent varier selon la configuration de l'image.

Le conteneur ne doit pas s'exécuter en tant que :

```text
root
```

pendant le fonctionnement normal.

---

# 29. Initialisation de la base de données

Après le démarrage du conteneur, vérifiez si la base de données existe :

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Si l'application s'est initialisée avec succès, la base de données devrait être présente.

La base de données est située à :

```text
/var/lib/lums/lums.db
```

à l'intérieur du conteneur et persiste physiquement via :

```text
lums-data
```

La base de données ne doit pas être copiée dans :

```text
/opt/lums-public
```

ni validée dans Git.

---

# 30. Vérifier la configuration d'exécution SQLite

La base de production LUMS actuelle utilise :

```text
journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON
```

L'application active explicitement l'application des clés étrangères pour les connexions à la base de données.

La base de données utilise le mode WAL pour le fonctionnement normal de production.

La configuration d'exécution peut être inspectée à partir de la base de données applicative.

Par exemple :

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for pragma in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    print(f"{pragma}={db.execute(f'PRAGMA {pragma}').fetchone()[0]}")

db.close()
PY
```

Les valeurs attendues sont équivalentes à :

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

L'application active explicitement les clés étrangères.

---

# 31. Vérifier l'intégrité de la base de données

Exécutez une vérification d'intégrité SQLite :

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY
```

Attendu :

```text
ok
```

Ne poursuivez pas le déploiement si la vérification d'intégrité signale une corruption de la base de données.

---

# 32. Vérifier les migrations de base de données

LUMS utilise des migrations applicatives pour les modifications de schéma de base de données.

Examinez les fichiers liés aux migrations :

```bash
ls -lh \
    server/*migration*.py
```

L'application effectue les migrations requises lors du démarrage/déploiement selon l'implémentation actuelle.

Après le démarrage, examinez les journaux applicatifs :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Les erreurs de migration doivent être investiguées avant de créer des utilisateurs ou de connecter des clients.

Ne modifiez pas manuellement le schéma SQLite de production, sauf si la documentation du projet l'exige explicitement.

---

# 33. Validation locale de l'application

Avant de configurer Nginx, confirmez que l'application répond localement.

L'application Docker est liée à :

```text
127.0.0.1:5050
```

Une requête locale peut être testée avec :

```bash
curl -I \
    http://127.0.0.1:5050/
```

La réponse HTTP exacte dépend de la route actuelle de l'application et de l'état d'authentification.

L'exigence importante est que la requête atteigne l'application LUMS en cours d'exécution.

Si la connexion échoue, examinez :

```bash
sudo docker ps \
    --filter name=lums
```

et :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

N'exposez pas le port `5050` en externe comme solution de contournement de dépannage.

---

# 34. Point de contrôle initial du serveur

À ce stade, le serveur devrait satisfaire :

```text
[ ] Repository cloned
[ ] Working tree reviewed
[ ] Production tests completed
[ ] Docker image built
[ ] Persistent lums-data volume exists
[ ] Hardened container running
[ ] Container runs as lums
[ ] Root filesystem is read-only
[ ] All capabilities are dropped
[ ] no-new-privileges is enabled
[ ] Privileged mode is disabled
[ ] Secret is mounted read-only
[ ] Persistent data volume is mounted
[ ] Port 5050 is localhost-only
[ ] SQLite database exists
[ ] SQLite integrity check succeeds
[ ] Foreign keys are enabled
[ ] Local application endpoint responds
```

Ne connectez pas encore les clients de production.

L'étape suivante configure Nginx, HTTPS et le point de terminaison LUMS externe.

# 35. Configurer Nginx

Nginx fournit le point d'entrée HTTPS externe pour LUMS.

L'application elle-même reste liée à :

```text
127.0.0.1:5050
```

Le chemin de requête prévu est :

```text
Client
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
LUMS container :5000
```

Créez la configuration du site Nginx :

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name LUMS-SERVER;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name LUMS-SERVER;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    location / {
        proxy_pass http://127.0.0.1:5050;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Remplacez :

```text
LUMS-SERVER
```

par le nom d'hôte ou l'adresse utilisés par l'installation.

N'utilisez pas l'espace réservé littéral dans une configuration de production.

---

# 36. Activer la configuration Nginx de LUMS

Créez le lien de site activé :

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Si le site Nginx par défaut n'est pas requis, supprimez-le :

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/default
```

Ne supprimez pas d'autres configurations Nginx appartenant à des applications non liées.

---

# 37. Valider la configuration Nginx

Testez toujours la configuration avant de recharger Nginx :

```bash
sudo nginx -t
```

Attendu :

```text
syntax is ok
test is successful
```

Ce n'est qu'après un test de configuration réussi que Nginx doit être rechargé :

```bash
sudo systemctl reload nginx
```

Vérifiez le service :

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Nginx doit être en cours d'exécution avant de poursuivre la validation HTTPS.

---

# 38. Vérifier les fichiers de certificat TLS

Confirmez que les fichiers de certificat configurés existent :

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Vérifiez les permissions :

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

La clé privée devrait normalement être :

```text
600
```

Le certificat peut normalement être :

```text
644
```

N'affichez jamais le contenu de la clé privée.

---

# 39. Vérifier le point de terminaison HTTPS

Testez HTTPS localement :

```bash
curl -I \
    https://LUMS-SERVER/
```

Remplacez `LUMS-SERVER` par le nom d'hôte couvert par le certificat TLS du serveur. N'utilisez pas `-k` pour la vérification de routine ; cela contourne la validation du certificat.

Lorsque le certificat est approuvé par le système, utilisez la vérification du certificat :

```bash
curl -I \
    https://LUMS-SERVER/
```

Une réponse réussie confirme que la requête atteint le point de terminaison HTTPS de Nginx.

Le statut HTTP exact dépend de la route demandée et de l'état d'authentification.

L'exigence importante est que la connexion TLS réussisse et que la requête atteigne LUMS.

---

# 40. Vérifier la redirection HTTP vers HTTPS

L'écouteur HTTP doit rediriger les clients vers HTTPS.

Test :

```bash
curl -I \
    http://LUMS-SERVER/
```

Comportement attendu :

```text
HTTP/1.1 301 ...
Location: https://...
```

L'application LUMS ne doit pas être exploitée via une connexion HTTP non chiffrée.

Ne configurez pas de manière permanente les clients avec la vérification du certificat désactivée simplement parce que le certificat initial n'est pas approuvé.

Corrigez plutôt la configuration de confiance.

---

# 41. Vérifier le chemin réseau externe

Examinez les sockets en écoute :

```bash
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

L'architecture prévue est :

```text
80
 │
 └── HTTP redirect
        │
        ▼
443
 │
 └── Nginx
        │
        ▼
127.0.0.1:5050
        │
        ▼
Docker :5000
```

Le port `5050` ne doit pas être exposé au LAN.

Le port `5000` ne doit pas être exposé directement.

Le port applicatif Docker est un point de terminaison de proxy inverse interne.

---

# 42. Vérifier les en-têtes de sécurité

Examinez les en-têtes de réponse HTTPS :

```bash
curl -I \
    https://LUMS-SERVER/
```

Examinez les en-têtes retournés plutôt que de supposer que la configuration de sécurité est active.

Les en-têtes de sécurité pertinents peuvent inclure :

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

Les en-têtes exacts dépendent de l'application LUMS actuelle et de la configuration Nginx.

Si un en-tête requis est manquant, examinez la configuration Nginx effective :

```bash
sudo nginx -T
```

et la configuration applicative :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

N'ajoutez pas d'en-têtes de sécurité à l'aveugle sans vérifier quelle couche en est déjà responsable.

---

# 43. Vérifier la gestion des hôtes

Le déploiement de production ne doit pas exposer l'application via un site Nginx par défaut non intentionnel.

Examinez la configuration active :

```bash
sudo nginx -T
```

Vérifiez les sites activés :

```bash
ls -la \
    /etc/nginx/sites-enabled/
```

L'hôte virtuel LUMS prévu doit être présent.

Le site par défaut ne doit pas servir inopinément l'application LUMS.

Lors de l'utilisation d'une adresse IP comme point de terminaison LUMS, assurez-vous que le `server_name` configuré et le certificat correspondent au modèle de déploiement réel.

---

# 44. Vérifier à nouveau l'exposition Docker

Après la configuration de Nginx, confirmez que l'application reste limitée à localhost :

```bash
sudo docker port lums
```

Attendu :

```text
5000/tcp -> 127.0.0.1:5050
```

Le proxy inverse ne nécessite pas de modifier la liaison Docker.

Ne le changez pas en :

```text
0.0.0.0:5050
```

simplement parce que Nginx écoute sur le réseau.

Nginx et Docker ont délibérément des frontières d'exposition séparées.

---

# 45. Créer l'administrateur initial

L'administrateur initial doit être créé à l'aide du mécanisme d'initialisation d'administrateur du référentiel actuel.

Avant d'exécuter une commande d'initialisation, examinez l'implémentation disponible du référentiel :

```bash
cd /opt/lums-public
```

Examinez les fichiers d'initialisation liés à la sécurité :

```bash
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
```

Examinez ensuite l'implémentation actuelle de migration/initialisation avant de l'exécuter.

Par exemple :

```bash
sed -n '1,260p' \
    server/security_migration.py
```

Utilisez la procédure d'initialisation fournie par la révision exacte du référentiel en cours de déploiement.

> [!IMPORTANT]
> Ne copiez pas un mot de passe administrateur dans l'historique du shell ou la documentation.

L'administrateur initial doit recevoir :

```text
role = administrator
```

Le compte administrateur est requis pour la première connexion web et l'administration ultérieure des clients.

---

# 46. Vérifier le compte administrateur

Après l'initialisation de l'administrateur, vérifiez le compte sans exposer de matériel d'authentification.

Une inspection de la base de données peut être effectuée depuis le conteneur :

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

rows = db.execute(
    """
    SELECT id, username, enabled, role
    FROM users
    ORDER BY id
    """
).fetchall()

for row in rows:
    print(row)

db.close()
PY
```

Les propriétés attendues de l'administrateur comprennent :

```text
enabled = 1
role = administrator
```

N'affichez pas :

```text
password hashes
session data
client tokens
application secrets
```

---

# 47. Mot de passe administrateur

Utilisez un mot de passe administrateur unique.

Le mot de passe ne doit pas être réutilisé à partir de :

```text
other servers
Linux accounts
GitHub accounts
email accounts
network devices
other LUMS installations
```

L'application LUMS stocke les mots de passe à l'aide du mécanisme de hachage de mot de passe configuré.

Ne tentez pas de remplacer manuellement le hachage du mot de passe applicatif dans SQLite.

Si le mot de passe administrateur doit être modifié, utilisez le mécanisme applicatif pris en charge.

---

# 48. Première connexion web

Ouvrez le point de terminaison HTTPS de LUMS :

```text
https://LUMS-SERVER/
```

Connectez-vous avec le compte administrateur.

Après l'authentification, l'administrateur devrait avoir accès à l'interface administrative.

L'interface administrateur devrait fournir l'accès aux domaines autorisés par l'implémentation RBAC actuelle.

Au minimum, l'administrateur devrait pouvoir accéder à :

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

---

# 49. Vérifier le RBAC administrateur

Après la connexion, vérifiez que les fonctions administratives sont disponibles.

L'administrateur devrait pouvoir accéder à la gestion des utilisateurs.

L'administrateur devrait également pouvoir effectuer les opérations de gestion des clients autorisées par l'implémentation actuelle.

L'autorisation côté serveur reste la frontière de sécurité.

L'interface navigateur n'est pas fiable simplement parce qu'un élément est visible ou masqué.

---

# 50. Créer un opérateur

Après la vérification du compte administrateur, créez un compte opérateur via l'interface de gestion des utilisateurs de LUMS.

Le rôle opérateur est destiné à la gestion opérationnelle des mises à jour.

Un opérateur peut accéder à :

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Un opérateur ne doit pas pouvoir effectuer des fonctions réservées aux administrateurs telles que :

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Vérifiez les permissions à l'aide de l'interface applicative et, le cas échéant, du comportement d'autorisation de l'API.

---

# 51. Créer un Viewer

Un compte Viewer peut être créé lorsqu'un accès en lecture seule est requis.

Le rôle Viewer est intentionnellement restreint.

Un Viewer peut accéder à :

```text
Clients
Installed software
```

Les domaines suivants ne doivent pas être disponibles pour un Viewer :

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Ces restrictions sont appliquées côté serveur.

L'interface peut en outre masquer les fonctions non disponibles.

---

# 52. Vérifier l'isolation du Viewer

Connectez-vous avec un compte Viewer et vérifiez l'interface visible.

Le Viewer ne devrait pas recevoir de contrôles de gestion.

Le Viewer ne doit pas pouvoir contourner l'interface et invoquer directement des points de terminaison protégés.

Un échec d'autorisation doit être retourné pour les opérations protégées.

Le principe attendu est :

```text
UI restriction
     +
server-side authorization
     =
RBAC boundary
```

Ne comptez jamais sur JavaScript ou des éléments HTML masqués comme seul mécanisme d'autorisation.

---

# 53. Vérifier la session et la protection CSRF

Après la première connexion réussie, vérifiez que l'application utilise ses protections de session et CSRF configurées.

L'installation ne doit pas désactiver la protection CSRF pour faire fonctionner les requêtes API ou les actions du navigateur.

Si une requête légitime échoue avec une erreur CSRF, examinez le flux applicatif plutôt que de désactiver la protection.

Le comportement lié aux sessions est documenté dans :

```text
docs/security.md
```

---

# 54. Vérifier la limitation du taux de connexion

La protection de connexion actuelle utilise le suivi persistant des échecs.

La progression configurée est :

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Une authentification réussie efface l'état d'échec applicable.

Ne déclenchez pas de manière répétée des authentifications échouées contre une installation de production simplement pour tester le mécanisme.

Utilisez la suite de tests existante pour la validation automatisée répétée.

---

# 55. Point de contrôle de validation du serveur

À ce stade, vérifiez :

```text
[ ] Nginx is running
[ ] Nginx configuration passes nginx -t
[ ] TLS certificate is installed
[ ] TLS private key is protected
[ ] HTTPS works
[ ] HTTP redirects to HTTPS
[ ] Docker remains localhost-only
[ ] Port 5000 is not externally exposed
[ ] Security headers are present as configured
[ ] Default Nginx site is not unintentionally serving LUMS
[ ] Administrator account exists
[ ] Administrator can log in
[ ] Administrator RBAC works
[ ] Operator role can be created
[ ] Viewer role can be created
[ ] Viewer restrictions are enforced server-side
[ ] CSRF protection remains enabled
[ ] Session protection remains enabled
```

Ce n'est qu'après que le serveur a passé ces contrôles que les clients Linux doivent être installés.

La section suivante couvre l'agent Linux, la configuration client, la confiance TLS et l'intégration systemd.

# 56. Installation du client Linux

Les clients LUMS sont des systèmes Linux gérés par le serveur LUMS.

Une installation client se compose de :

```text
Linux system
    ↓
LUMS Agent
    ↓
Client configuration
    ↓
Client token
    ↓
TLS trust
    ↓
systemd service
    ↓
Reporting timer
```

L'exécution des mises à jour est gérée séparément par le watcher d'exécution.

La version actuelle de l'agent est :

```text
1.7.0
```

La version actuelle du Watcher est :

```text
1.2.1
```

---

# 57. Clients Linux pris en charge

Les implémentations actuelles de gestion des paquets prennent en charge :

```text
Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman
```

Vérifiez le système d'exploitation avant d'installer le client :

```bash
cat /etc/os-release
```

Vérifiez l'architecture :

```bash
uname -m
```

Vérifiez systemd :

```bash
systemctl --version
```

Le client nécessite une installation systemd fonctionnelle.

---

# 58. Exigences réseau du client

Le client doit pouvoir atteindre le point de terminaison HTTPS de LUMS.

Testez la connectivité réseau de base :

```bash
ping LUMS-SERVER
```

Un ping réussi n'est pas requis lorsque ICMP est bloqué.

L'exigence importante est la connectivité HTTPS.

Testez le point de terminaison LUMS :

```bash
curl -I \
    https://LUMS-SERVER/
```

Si le serveur utilise une AC privée, le client doit faire confiance à cette AC avant de continuer.

Ne désactivez pas la vérification TLS comme solution de contournement permanente.

---

# 59. Obtenir l'agent LUMS

Le code source de l'agent est inclus dans le référentiel LUMS.

Sur le client, obtenez le référentiel ou transférez autrement les fichiers de l'agent requis via la méthode de déploiement approuvée.

Les fichiers pertinents sont :

```text
agent/agent.py
agent/watcher.py
agent/package_manager.py
```

Le répertoire d'installation recommandé est :

```text
/opt/lums-agent
```

Créez-le :

```bash
sudo install -d -m 755 \
    /opt/lums-agent
```

---

# 60. Installer les fichiers de l'agent

Depuis le référentiel LUMS :

```bash
cd /opt/lums-public
```

Installez l'agent :

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Installez le Watcher :

```bash
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

Installez l'abstraction du gestionnaire de paquets :

```bash
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Vérifiez :

```bash
ls -lh \
    /opt/lums-agent/
```

Le répertoire devrait contenir les composants de l'agent installés.

---

# 61. Vérifier les versions de l'agent

Vérifiez la version de l'agent installée :

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

La version actuelle est :

```text
1.7.0
```

Vérifiez le Watcher :

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

La version actuelle est :

```text
1.2.1
```

Si les versions installées ne correspondent pas à la révision de déploiement prévue, arrêtez et vérifiez que la bonne révision du référentiel est utilisée.

---

# 62. Installer les fichiers de service systemd

L'agent et le Watcher utilisent des services systemd séparés.

Installez le service de l'agent :

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Installez le service du Watcher :

```bash
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Installez le timer de rapport :

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Installez le timer du Watcher :

```bash
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Rechargez systemd :

```bash
sudo systemctl daemon-reload
```

---

# 63. Vérifier les units systemd

Examinez le service de l'agent :

```bash
systemctl cat \
    lums-agent.service
```

Examinez le service du Watcher :

```bash
systemctl cat \
    lums-agent-watcher.service
```

Examinez le timer de l'agent :

```bash
systemctl cat \
    lums-agent.timer
```

Examinez le timer du Watcher :

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Les units devraient référencer les fichiers installés sous :

```text
/opt/lums-agent/
```

N'activez pas les timers avant que la configuration du client et l'authentification soient terminées.

---

# 64. Créer la configuration du client

La configuration du client est stockée en dehors du référentiel Git.

Utilisez :

```text
/etc/default/lums-agent
```

Créez le fichier :

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

La configuration contient le point de terminaison du serveur LUMS et le token du client.

Structure d'exemple :

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Remplacez :

```text
LUMS-SERVER
```

par le point de terminaison réel du serveur LUMS.

Remplacez :

```text
<CLIENT-TOKEN>
```

par le token attribué à ce client.

Protégez la configuration :

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Vérifiez sans afficher son contenu :

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Attendu :

```text
600
```

---

# 65. Tokens clients

Chaque client LUMS possède son propre token d'authentification.

Le token est utilisé comme :

```text
Authorization: Bearer <CLIENT-TOKEN>
```

Le serveur n'a pas besoin de la valeur originale du token après le provisionnement.

Le serveur stocke une représentation cryptographique du token pour validation.

Cela signifie que les identifiants clients doivent être traités comme des mots de passe.

Ne placez jamais un vrai token dans :

```text
Git
documentation
screenshots
issue reports
shell history
public configuration
```

---

# 66. Provisionner le token client

Créez ou provisionnez le client depuis l'interface administrateur de LUMS selon le workflow actuel de gestion des clients.

Le token client résultant doit être transféré au client prévu via un canal sécurisé.

Stockez-le uniquement dans :

```text
/etc/default/lums-agent
```

sur le client.

Ne réutilisez pas un token client sur plusieurs machines.

La relation prévue est :

```text
Client A
    ↓
Token A

Client B
    ↓
Token B

Client C
    ↓
Token C
```

Un token compromis ne devrait donc identifier que son client associé.

---

# 67. Rotation des tokens clients

Les tokens clients peuvent être rotés par un administrateur.

Le flux de rotation est :

```text
Current token
     ↓
Administrator rotates token
     ↓
Old token invalidated
     ↓
New token issued
     ↓
Client configuration updated
```

Après la mise à jour de la configuration du client, exécutez l'agent manuellement pour vérifier que l'authentification réussit.

Un token roté ne doit pas continuer à être accepté indéfiniment.

---

# 68. Confiance TLS

L'agent LUMS communique avec le serveur via HTTPS.

La vérification du certificat doit rester activée.

Pour un certificat approuvé publiquement, le magasin de confiance normal du système d'exploitation est suffisant.

Pour une AC de laboratoire privée, installez le certificat de l'AC sur le client.

Ne résolvez pas les problèmes de certificat en désactivant la vérification.

La solution correcte est de faire confiance à l'autorité de certification prévue.

---

# 69. Confiance TLS Debian / Ubuntu

Sur les systèmes de la famille Debian, une AC privée peut être installée dans le magasin de confiance du système.

Copiez le certificat de l'AC :

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Mettez à jour le magasin de confiance :

```bash
sudo update-ca-certificates
```

Vérifiez que le certificat est accepté :

```bash
curl -I \
    https://LUMS-SERVER/
```

Si la commande réussit sans `-k`, la configuration de confiance du système fonctionne.

---

# 70. Confiance TLS Arch Linux

Sur Arch Linux, installez l'AC privée à l'aide du mécanisme de magasin de confiance configuré du système.

Après l'installation de l'AC, mettez à jour la base de données de confiance selon la configuration active du magasin de confiance.

Vérifiez :

```bash
curl -I \
    https://LUMS-SERVER/
```

La connexion devrait réussir sans :

```text
-k
```

Ne configurez pas de manière permanente l'agent pour ignorer la vérification du certificat.

---

# 71. Vérifier le gestionnaire de paquets

L'agent détecte la famille de gestion de paquets prise en charge.

Pour Debian/Ubuntu :

```bash
command -v apt
```

et :

```bash
command -v dpkg-query
```

Vérifiez les paquets installés :

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head
```

Vérifiez les mises à jour disponibles :

```bash
apt list --upgradable
```

Pour Arch Linux :

```bash
command -v pacman
```

Vérifiez les paquets installés :

```bash
pacman -Q | head
```

Vérifiez les mises à jour disponibles :

```bash
pacman -Qu
```

L'abstraction du gestionnaire de paquets utilise automatiquement l'implémentation appropriée.

---

# 72. Vérifier les permissions de l'agent

Examinez le répertoire d'installation :

```bash
ls -ld \
    /opt/lums-agent
```

Examinez les fichiers installés :

```bash
ls -lh \
    /opt/lums-agent/
```

L'agent n'a pas besoin d'accès en écriture à son propre répertoire source.

La configuration du client reste protégée séparément :

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Attendu :

```text
600
```

L'agent nécessite des privilèges système suffisants pour inspecter l'état des paquets et effectuer des opérations sur les paquets.

Les privilèges d'exécution exacts sont définis par le service systemd installé.

---

# 73. Vérifier la configuration de l'agent

Avant de démarrer le service, vérifiez que le fichier de configuration existe :

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"
```

N'affichez pas le contenu du fichier de configuration.

Vérifiez que les variables requises existent sans exposer le token :

```bash
sudo sh -c '
set -a
. /etc/default/lums-agent
set +a

test -n "$LUMS_BASE" &&
echo "LUMS_BASE: configured"

test -n "$LUMS_TOKEN" &&
echo "LUMS_TOKEN: configured"
'
```

La valeur du token elle-même ne doit pas être affichée.

---

# 74. Tester l'agent manuellement

Avant d'activer le timer, exécutez l'agent une fois manuellement :

```bash
sudo systemctl start \
    lums-agent.service
```

Vérifiez le résultat :

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

L'agent est un service one-shot.

Après un achèvement réussi, il peut afficher :

```text
Active: inactive (dead)
```

C'est normal.

Le résultat important est :

```text
status=0/SUCCESS
```

Examinez le journal :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 75. Vérifier le premier rapport client

Une exécution réussie de l'agent devrait rapporter le client au serveur LUMS.

Le chemin complet est :

```text
Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
Bearer authentication
   ↓
Client lookup
   ↓
Report accepted
```

Examinez les journaux du serveur si nécessaire :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Le client devrait apparaître dans l'interface web LUMS après un rapport réussi.

Le succès du service local n'est pas suffisant en soi.

Le serveur doit accepter le rapport.

---

# 76. Vérifier le client dans l'interface web

Connectez-vous en tant qu'administrateur ou opérateur.

Ouvrez la vue d'ensemble des clients.

Le nouveau client devrait rapporter des informations telles que :

```text
Hostname
IP address
Operating system
Architecture
Agent version
Last report
Installed packages
Available updates
```

Les informations rapportées appartiennent à ce client.

Un client ne doit pas pouvoir accéder aux ressources d'un autre client.

---

# 77. Activer le timer de rapport

Ce n'est qu'après la réussite de l'exécution manuelle de l'agent que le timer de rapport doit être activé :

```bash
sudo systemctl enable --now \
    lums-agent.timer
```

Vérifiez :

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Examinez le calendrier :

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

Le timer démarre périodiquement :

```text
lums-agent.service
```

Le service lui-même reste une unité one-shot.

Par conséquent, il est normal que le service revienne à :

```text
inactive (dead)
```

entre les exécutions du timer.

---

# 78. Vérifier les rapports planifiés

Après avoir activé le timer, examinez la prochaine exécution planifiée :

```bash
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent
```

Après l'exécution du timer, examinez :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Vérifiez le rapport client correspondant dans LUMS.

Un cycle de rapport sain est :

```text
Timer
  ↓
Agent service
  ↓
System inventory
  ↓
Package inventory
  ↓
Update detection
  ↓
HTTPS report
  ↓
LUMS database
```

---

# 79. Point de contrôle de l'installation client

Avant d'installer le watcher d'exécution, vérifiez :

```text
[ ] Supported Linux distribution
[ ] Python 3 available
[ ] systemd available
[ ] Package manager available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher files installed
[ ] Client configuration exists
[ ] Client token protected
[ ] TLS certificate trusted
[ ] Agent service succeeds
[ ] Client report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Scheduled reporting verified
```

Ne passez pas aux tests de jobs de mise à jour tant que le chemin de rapport ne fonctionne pas.

La section suivante installe et valide le watcher d'exécution.

# 80. Installer le watcher d'exécution

Le watcher d'exécution LUMS est responsable de la détection et de l'exécution des jobs de mise à jour en attente sur le client.

L'architecture sépare les rapports de l'exécution :

```text
Reporting
    │
    ▼
lums-agent.service
    │
    └── system inventory / update detection

Execution
    │
    ▼
lums-agent-watcher.service
    │
    └── pending update jobs
```

Cette séparation permet aux rapports ordinaires des clients de continuer indépendamment de l'exécution des mises à jour.

---

# 81. Vérifier l'installation du Watcher

Vérifiez que le Watcher est présent :

```bash
ls -lh \
    /opt/lums-agent/watcher.py
```

Vérifiez la version installée :

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

La version actuelle du Watcher est :

```text
1.2.1
```

---

# 82. Vérifier le service du Watcher

Examinez l'unité systemd :

```bash
systemctl cat \
    lums-agent-watcher.service
```

Le service doit référencer :

```text
/opt/lums-agent/watcher.py
```

Vérifiez que l'unité est connue de systemd :

```bash
systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Le service peut être inactif lorsqu'aucune exécution n'a été déclenchée.

Ce n'est pas en soi une erreur.

---

# 83. Vérifier le timer du Watcher

Avant d'activer le timer du Watcher, vérifiez que :

- `/etc/default/lums-agent` existe et contient la configuration client correcte.
- Le point de terminaison du serveur LUMS et le token client sont configurés correctement.
- Une exécution manuelle de l'agent a réussi et le serveur a accepté le rapport client.
- Les deux fichiers d'unité du Watcher ont été installés depuis le référentiel.

N'activez pas le timer pendant que l'authentification ou les rapports échouent.

Examinez le timer :

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Activez le timer uniquement après avoir vérifié tous les prérequis ci-dessus :

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Vérifiez :

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Examinez la prochaine exécution planifiée :

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

---

# 84. Comprendre l'exécution consciente de l'inactivité

Le Watcher peut utiliser les informations d'inactivité du client avant d'exécuter les jobs de mise à jour.

Le flux prévu est :

```text
Pending job
    │
    ▼
Watcher
    │
    ▼
Idle detection
    │
    ├── idle state available
    │       │
    │       ▼
    │   idle threshold
    │       │
    │       ▼
    │   execute when allowed
    │
    └── idle state unavailable
            │
            ▼
        use configured
        fallback behavior
```

La détection d'inactivité ne doit jamais être interprétée comme une authentification ou une autorisation.

C'est uniquement un mécanisme de planification de l'exécution.

---

# 85. Vérifier la détection d'inactivité

Exécutez manuellement le chemin de détection d'inactivité via l'implémentation installée de l'agent/watcher.

Examinez le journal de service résultant :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Si la plateforme ne fournit pas les informations d'inactivité requises, le client peut rapporter la détection d'inactivité comme non disponible.

Ce n'est pas automatiquement un échec.

La distinction importante est :

```text
idle_supported = available
```

par rapport à :

```text
idle_supported = unavailable
```

Le client ne doit pas être supposé inactif simplement parce qu'aucune information d'inactivité n'a été retournée.

---

# 86. Créer un job de mise à jour de test contrôlé

Ne commencez pas les tests d'installation avec une grande mise à jour système.

Utilisez un petit paquet connu pour le premier test.

Le paquet devrait :

```text
exist in the configured repository
be safe to install
be removable again
not be required by the operating system
```

Exemple de paquet de test :

```text
sl
```

Avant de créer le job, vérifiez s'il est déjà installé :

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Pour Arch Linux, utilisez un paquet disponible dans les référentiels configurés et adapté à un test réversible.

N'utilisez pas aveuglément `sl` sur chaque distribution.

---

# 87. Vérifier la recherche de paquets

Utilisez l'interface de gestion des paquets de LUMS pour rechercher le paquet sélectionné.

Le flux de recherche est :

```text
Browser
   ↓
LUMS API
   ↓
Package Search Request
   ↓
Client
   ↓
APT / pacman
   ↓
Package Search Result
   ↓
LUMS API
   ↓
Browser
```

Vérifiez que le résultat contient les informations attendues :

```text
Package
Version
Description
Status
Action
```

Pour Arch Linux, les informations de référentiel peuvent également être retournées.

---

# 88. Permissions de gestion des paquets

La gestion des paquets est restreinte par RBAC.

Administrator :

```text
Allowed
```

Operator :

```text
Allowed
```

Viewer :

```text
Not allowed
```

Un Viewer ne doit pas pouvoir exécuter l'installation ou la suppression de paquets en appelant directement l'API.

Le masquage de la fonctionnalité dans l'interface navigateur n'est qu'une restriction d'ergonomie supplémentaire.

L'autorisation côté serveur est la véritable frontière de sécurité.

---

# 89. Tester l'installation de paquets

Créez un job d'installation via l'interface LUMS.

L'opération logique est :

```text
INSTALL_PACKAGE
```

Le job est stocké dans la base de données LUMS avant que l'agent ne l'exécute.

Le flux attendu est :

```text
Create job
   ↓
PENDING
   ↓
Watcher detects job
   ↓
RUNNING
   ↓
Package manager
   ↓
SUCCESS
```

Surveillez le job dans l'interface LUMS.

Ne modifiez pas manuellement la base de données pour forcer un état de job.

---

# 90. Vérifier le résultat de l'installation

Après que le job a rapporté un succès, vérifiez le paquet localement.

Sur Debian/Ubuntu :

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl
```

Vérifiez que le gestionnaire de paquets est d'accord :

```bash
apt-cache policy \
    sl
```

Le paquet doit réellement être installé.

Un état `SUCCESS` de LUMS doit correspondre à une opération côté client réussie.

---

# 91. Vérifier le résultat du job

Examinez l'historique des jobs de LUMS.

Vérifiez :

```text
Action
Package
Client
Start time
Completion time
Result
```

Le résultat retourné par le client doit être validé par le serveur.

Les données de résultat invalides ou incomplètes ne doivent pas se transformer silencieusement en job réussi.

Cette validation fait partie du modèle de sécurité et de fiabilité de LUMS.

---

# 92. Tester la suppression de paquets

Après avoir vérifié l'installation, créez un job de suppression :

```text
REMOVE_PACKAGE
```

Surveillez :

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

Après l'achèvement :

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Le paquet ne devrait plus être installé.

Si le paquet n'était pas installé avant le test, ne traitez pas son absence comme preuve d'une suppression réussie.

---

# 93. Tester la mise à jour de paquets

Les mises à jour de paquets utilisent :

```text
UPDATE_PACKAGE
```

Le serveur valide que le paquet demandé est une mise à jour disponible avant de créer le job correspondant.

Le flux général est :

```text
Client reports available updates
       ↓
User selects package
       ↓
Server validates package
       ↓
Update job created
       ↓
Watcher executes
       ↓
Result reported
```

Ne construisez pas manuellement de requêtes de mise à jour contournant le chemin de validation normal.

---

# 94. Tester la mise à jour système

Une mise à jour système complète utilise :

```text
UPDATE_SYSTEM
```

Cette opération affecte l'état du gestionnaire de paquets du client plus largement qu'une opération sur un seul paquet.

Pour le premier test de mise à jour système :

```text
Use a test client
Use a current backup
Monitor the console
Monitor the LUMS job
Do not interrupt the package manager
```

N'utilisez pas le serveur de production lui-même comme première cible de test de mise à jour système.

---

# 95. Verrous du gestionnaire de paquets

APT et pacman peuvent utiliser des verrous de gestionnaire de paquets.

Lorsqu'une opération échoue parce qu'un autre processus de gestion des paquets est actif, examinez les processus en cours avant d'agir.

Debian/Ubuntu :

```bash
ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'
```

Arch Linux :

```bash
ps aux | grep -E \
    '[p]acman|[p]ar'
```

Ne supprimez pas les fichiers de verrou du gestionnaire de paquets pendant que le gestionnaire de paquets est réellement en cours d'exécution.

Un verrou protège normalement contre les opérations concurrentes sur les paquets.

---

# 96. Distinguer les échecs de LUMS des échecs du gestionnaire de paquets

Lorsqu'un job échoue, déterminez quelle couche a échoué.

```text
LUMS API
   │
   ├── Job creation failure
   │
   ▼
LUMS database
   │
   ├── State / persistence problem
   │
   ▼
Watcher
   │
   ├── Execution problem
   │
   ▼
Package manager
   │
   ├── APT / pacman failure
   │
   ▼
Operating system
```

Examinez le journal client :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Examinez le conteneur LUMS :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Ne réessayez pas immédiatement un job échoué sans déterminer pourquoi il a échoué.

---

# 97. Vérifier les points de contrôle des jobs

LUMS suit l'état des jobs et des éléments de paquets.

Pour les jobs basés sur des paquets, les éléments de paquets individuels peuvent être pointés.

Le comportement prévu est :

```text
Package A → SUCCESS
Package B → SUCCESS
Package C → RUNNING
             │
             ▼
          interruption
             │
             ▼
          recovery
             │
             ▼
Package A → not repeated
Package B → not repeated
Package C → resumed / handled
```

Cela empêche les opérations sur les paquets terminées d'être répétées inutilement après une interruption.

---

# 98. Tester la récupération contrôlée des jobs

Utilisez un job de test non critique.

Démarrez le job et observez son état :

```text
PENDING
```

puis :

```text
RUNNING
```

N'interrompez pas délibérément une mise à jour de production.

Pour les tests de récupération, utilisez un client de test dédié et une opération de paquet contrôlée.

Après une interruption ou un échec simulé, redémarrez le Watcher :

```bash
sudo systemctl restart \
    lums-agent-watcher.timer
```

Examinez ensuite :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Vérifiez que les éléments de paquets déjà réussis ne sont pas exécutés à nouveau inutilement.

---

# 99. Vérifier la détection de redémarrage

Certaines opérations sur les paquets peuvent nécessiter un redémarrage.

L'agent/watcher rapporte les exigences de redémarrage à LUMS.

Le flux général est :

```text
Package operation
      ↓
Reboot requirement detected
      ↓
Result reported
      ↓
LUMS records reboot state
```

Après une opération de test qui nécessite légitimement un redémarrage, vérifiez le résultat de job correspondant dans l'interface LUMS.

Ne redémarrez pas un client de production uniquement pour tester le mécanisme, sauf si le système est destiné à ce test.

---

# 100. Vérifier les rapports après redémarrage

Lorsqu'un client de test est redémarré, vérifiez que :

```text
systemd
   ↓
LUMS Agent timer
   ↓
Agent report
   ↓
LUMS server
```

continue de fonctionner.

Vérifiez :

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

et :

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Examinez ensuite le dernier rapport dans l'interface LUMS.

---

# 101. Vérifier la détection des mises à jour

Exécutez l'agent manuellement :

```bash
sudo systemctl start \
    lums-agent.service
```

Examinez :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Le client devrait rapporter :

```text
Installed packages
Available updates
Agent status
```

Le serveur devrait mettre à jour l'état actuel du client.

Ne confondez pas :

```text
available updates
```

avec :

```text
installed packages
```

Ils représentent des ensembles de données différents.

---

# 102. Vérifier les logiciels installés

Ouvrez la section des logiciels installés du client dans LUMS.

La liste des paquets devrait correspondre au gestionnaire de paquets côté client.

Pour Debian/Ubuntu :

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'
```

Pour Arch :

```bash
pacman -Q
```

L'inventaire LUMS est informatif jusqu'à ce qu'un job soit explicitement créé.

Le filtre des paquets installés ne modifie pas lui-même le client.

---

# 103. Vérifier séparément la recherche de paquets

La recherche de gestion des paquets est séparée du filtre des paquets installés.

La distinction est :

```text
Installed Package Filter
    ↓
Searches the package inventory already reported by the client

Package Management Search
    ↓
Requests package information from the client's package manager
```

Ne traitez pas les deux fonctions de recherche comme interchangeables.

Un paquet peut être disponible via APT ou pacman sans être installé.

---

# 104. Vérifier l'isolation des paquets Viewer

Connectez-vous en tant que Viewer.

Vérifiez que l'interface de gestion des paquets n'est pas disponible.

Vérifiez ensuite la restriction côté serveur en tentant une requête de gestion des paquets non autorisée via une méthode de test approuvée.

La requête doit être rejetée.

L'accès Viewer doit rester en lecture seule.

---

# 105. Vérifier la gestion des paquets Operator

Connectez-vous en tant qu'Operator.

Vérifiez l'accès à :

```text
Package Search
Package Installation
Package Removal
Package Updates
Update Jobs
Update History
```

L'Operator ne doit pas obtenir l'accès aux fonctions de gestion des utilisateurs réservées aux administrateurs.

---

# 106. Vérifier la gestion des paquets Administrator

Connectez-vous en tant qu'Administrator.

Vérifiez les mêmes capacités de gestion des paquets que l'Operator.

Vérifiez en outre l'accès à :

```text
User Management
Client Management
Client Token Rotation
```

Les permissions administrateur doivent rester appliquées côté serveur.

---

# 107. Premier test de paquet de bout en bout

Le premier test complet de gestion des paquets devrait suivre cette séquence :

```text
1. Client reports successfully
2. Package search succeeds
3. Package result is displayed
4. Administrator/Operator creates INSTALL_PACKAGE job
5. Job becomes PENDING
6. Watcher detects the job
7. Job becomes RUNNING
8. Package manager executes
9. Client reports result
10. Server validates result
11. Job becomes SUCCESS
12. Installed package is verified locally
13. Package is visible in LUMS inventory
```

Ce n'est qu'après la réussite de cette séquence que des tests de mise à jour plus larges doivent commencer.

---

# 108. Point de contrôle de l'exécution client

Vérifiez :

```text
[ ] Watcher installed
[ ] Watcher version verified
[ ] Watcher timer enabled
[ ] Idle detection works or reports unavailable correctly
[ ] Package search works
[ ] Package installation works
[ ] Package removal works
[ ] Package update works
[ ] System update path is available
[ ] Job states transition correctly
[ ] Job results are validated
[ ] Package checkpointing works
[ ] Reboot detection works
[ ] Reporting continues after reboot
[ ] Viewer cannot mutate package state
[ ] Operator can manage packages
[ ] Administrator can manage packages
```

À ce stade, le chemin d'exécution principal du client LUMS est installé et validé.

La section suivante couvre la validation complète de bout en bout, la vérification RBAC, la sauvegarde/restauration, la maintenance, les mises à niveau et les contrôles finaux d'installation.

# 109. Validation complète de bout en bout

Après la configuration du serveur et d'au moins un client Linux, effectuez une validation complète de bout en bout.

Le chemin complet de LUMS est :

```text
Browser
   │
   ▼
Nginx / HTTPS
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Client Agent
   │
   ▼
Package Manager
   │
   ▼
Update Result
   │
   ▼
SQLite
   │
   ▼
Web Interface
```

Ne considérez pas l'installation comme terminée simplement parce que l'interface web s'ouvre.

Toutes les couches majeures doivent être vérifiées.

---

# 110. Contrôle de santé du serveur

Vérifiez le conteneur LUMS :

```bash
sudo docker ps \
    --filter name=lums
```

Vérifiez l'état du conteneur :

```bash
sudo docker inspect \
    lums \
    --format '{{.State.Status}}'
```

Attendu :

```text
running
```

Examinez les journaux récents :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Les journaux ne doivent pas contenir d'échec de démarrage ou de migration actif.

---

# 111. Contrôle de sécurité du conteneur

Vérifiez la configuration de sécurité à l'exécution :

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Base attendue :

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Vérifiez la liaison réseau :

```bash
sudo docker port \
    lums
```

Attendu :

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 112. Contrôle du stockage persistant

Vérifiez le volume LUMS :

```bash
sudo docker volume inspect \
    lums-data
```

Vérifiez que la base de données applicative existe :

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

La base de données doit résider dans un stockage persistant.

Ne stockez pas la base de données de production uniquement à l'intérieur du système de fichiers du conteneur.

---

# 113. Contrôle de santé SQLite

Examinez la configuration d'exécution SQLite actuelle :

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for name in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    value = db.execute(
        f"PRAGMA {name}"
    ).fetchone()[0]
    print(f"{name}={value}")

db.close()
PY
```

La base actuelle est :

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

L'application active explicitement l'application des clés étrangères.

---

# 114. Contrôle d'intégrité SQLite

Exécutez :

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

result = db.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print(result)

db.close()
PY
```

Attendu :

```text
ok
```

Ne poursuivez pas un nouveau déploiement en production si la vérification d'intégrité signale une corruption.

---

# 115. Vérifier les migrations de base de données

Examinez l'état des migrations :

```bash
sudo docker logs \
    --tail 200 \
    lums | grep -i migration
```

L'application doit terminer ses migrations configurées avant le fonctionnement normal.

Ne modifiez pas manuellement la table d'état des migrations, sauf si la procédure de migration actuelle de LUMS l'exige explicitement.

---

# 116. Exécuter la suite de tests automatisés

Sur l'environnement de développement/test LUMS :

```bash
cd /opt/lums-public
```

Exécutez :

```bash
./.venv-test/bin/pytest -q
```

Le nombre de tests change au fur et à mesure que le projet évolue ; fiez-vous au résultat de la commande, pas à un nombre fixe dans ce document.

L'exigence importante est :

```text
all tests pass
```

N'ignorez pas les tests en échec parce que l'interface web de production semble fonctionnelle.

---

# 117. Vérifier le RBAC

Le modèle de rôle actuel est :

| Fonction                    | Administrator | Operator | Viewer |
| --------------------------- | ------------: | -------: | -----: |
| Afficher les clients        |           Oui |      Oui |    Oui |
| Logiciels installés         |           Oui |      Oui |    Oui |
| Mises à jour disponibles    |           Oui |      Oui |    Non |
| Créer/exécuter des jobs     |           Oui |      Oui |    Non |
| Historique des mises à jour |           Oui |      Oui |    Non |
| Gestion des paquets         |           Oui |      Oui |    Non |
| Maintenance système         |           Oui |      Oui |    Non |
| Créer/désactiver clients    |           Oui |      Non |    Non |
| Rotation tokens clients     |           Oui |      Non |    Non |
| Gestion des utilisateurs    |           Oui |      Non |    Non |
| Gestion des rôles           |           Oui |      Non |    Non |

L'interface devrait refléter ces permissions.

Plus important encore, l'API doit les appliquer indépendamment.

---

# 118. Vérifier l'accès Administrator

Connectez-vous en tant qu'Administrator.

Vérifiez l'accès à :

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

Vérifiez les fonctions de gestion des clients :

```text
Create client
Disable client
Rotate client token
```

L'Administrator devrait pouvoir effectuer ces opérations.

---

# 119. Vérifier l'accès Operator

Connectez-vous en tant qu'Operator.

Vérifiez l'accès à :

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Vérifiez que la fonctionnalité réservée aux administrateurs n'est pas disponible :

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Ne vous fiez pas uniquement aux éléments d'interface masqués.

Les opérations API protégées doivent rejeter les requêtes non autorisées.

---

# 120. Vérifier l'accès Viewer

Connectez-vous en tant que Viewer.

Le Viewer devrait pouvoir accéder à :

```text
Clients
Installed software
```

Ce qui suit ne doit pas être disponible :

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Le Viewer ne doit pas pouvoir modifier l'état du client.

---

# 121. Vérifier l'authentification client

Confirmez que chaque client utilise son propre token Bearer.

Le modèle attendu est :

```text
Client A → Token A
Client B → Token B
Client C → Token C
```

Ne partagez pas de tokens entre clients.

Vérifiez qu'un token roté ou révoqué n'est plus accepté.

Ne placez jamais de vrais tokens dans la sortie de test ou la documentation.

---

# 122. Vérifier la détection des mises à jour

Sur un client de test :

```bash
sudo systemctl start \
    lums-agent.service
```

Examinez :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Vérifiez ensuite le client dans l'interface LUMS.

Les informations rapportées devraient inclure l'inventaire actuel des paquets et les informations de mise à jour lorsqu'elles sont prises en charge.

---

# 123. Vérifier la création de jobs de mise à jour

Créez un job de mise à jour contrôlé via l'interface LUMS.

Le job devrait initialement apparaître comme :

```text
PENDING
```

Le Watcher traite ensuite le job :

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

selon le résultat réel de l'opération.

Ne modifiez pas manuellement l'état de la base de données.

---

# 124. Vérifier l'exécution des jobs

Examinez le Watcher client :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Examinez le serveur LUMS :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Comparez l'état du job côté serveur avec le résultat d'exécution côté client.

Les deux doivent concorder.

---

# 125. Vérifier la validation des résultats de paquets

Un job ne doit pas devenir réussi simplement parce que le client a soumis une réponse syntaxiquement valide.

Le serveur valide le résultat retourné.

Vérifiez cela via les tests automatisés de validation des résultats :

```bash
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Un résultat réussi doit contenir la structure attendue et un contexte de job valide.

Les résultats mal formés ou incohérents doivent être rejetés.

---

# 126. Vérifier la récupération des jobs

Utilisez un client de test dédié pour les tests de récupération.

Le modèle de récupération est :

```text
Job
 │
 ├── package item A → SUCCESS
 ├── package item B → SUCCESS
 └── package item C → interrupted
                       │
                       ▼
                    recovery
                       │
                       ▼
                  resume safely
```

Après la récupération, les éléments de paquets précédemment réussis ne doivent pas être répétés inutilement.

Examinez :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Vérifiez ensuite l'état final du job dans LUMS.

---

# 127. Vérifier la détection de redémarrage

Pour une mise à jour de test contrôlée qui nécessite un redémarrage, vérifiez que le client rapporte l'exigence de redémarrage.

Après le redémarrage :

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

et :

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Le client doit reprendre les rapports normaux après le démarrage.

---

# 128. Vérifier la journalisation d'audit

Effectuez une action administrative contrôlée, puis examinez le journal d'audit de LUMS.

Les opérations pertinentes comprennent :

```text
Login
User creation
Client creation
Client-token rotation
Job creation
Package management
```

Les entrées d'audit devraient fournir suffisamment d'informations pour reconstituer l'action administrative sans exposer de secrets.

Ne journalisez pas :

```text
Passwords
Client tokens
Application secrets
Private keys
Session secrets
```

---

# 129. Vérifier la rédaction des journaux

Examinez les journaux récents :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Examinez les journaux clients :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

et :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Les identifiants d'authentification et les secrets ne doivent pas apparaître dans la sortie de diagnostic normale.

Si une commande de diagnostic devait exposer un secret, ne collez pas sa sortie dans un ticket, un commit ou la documentation.

---

# 130. Vérifier l'exposition réseau

Examinez les ports en écoute :

```bash
sudo ss -lntp
```

Le port applicatif LUMS devrait rester :

```text
127.0.0.1:5050
```

Nginx fournit le service externe :

```text
:80
:443
```

L'application ne doit pas être directement exposée via :

```text
0.0.0.0:5050
```

ou :

```text
0.0.0.0:5000
```

---

# 131. Vérifier la configuration du pare-feu

Si un pare-feu hôte est activé, examinez-le :

```bash
sudo ufw status verbose
```

Le déploiement ne devrait exposer que les services requis par l'hôte.

Ne créez pas de règle de pare-feu pour le port `5050` simplement parce que Docker utilise ce port en interne.

L'architecture prévue est :

```text
LAN
 │
 ▼
443
 │
 ▼
Nginx
 │
 ▼
127.0.0.1:5050
 │
 ▼
LUMS
```

---

# 132. Stratégie de sauvegarde

La base de données SQLite LUMS est un état applicatif persistant.

Au minimum, les sauvegardes devraient protéger :

```text
LUMS database
TLS material
LUMS application secret
Deployment configuration
```

Les sauvegardes doivent être stockées en dehors du conteneur LUMS actif.

Ne stockez pas les sauvegardes dans :

```text
/app
```

et ne vous fiez pas au système de fichiers du conteneur.

Le volume Docker :

```text
lums-data
```

contient les données applicatives persistantes, mais un volume Docker n'est pas en soi une sauvegarde.

---

# 133. Sauvegarde de la base de données

Avant de sauvegarder la base de données, identifiez le fichier de base de données :

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Une sauvegarde de base de données doit être effectuée à l'aide d'un mécanisme de sauvegarde SQLite cohérent.

Ne copiez pas aveuglément une base de données SQLite active pendant qu'elle est modifiée si la procédure de sauvegarde ne peut pas garantir la cohérence.

Après avoir créé une sauvegarde, vérifiez que le fichier de sauvegarde existe et est protégé.

---

# 134. Sauvegarde de la configuration

Protégez le matériel de déploiement suivant :

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Ne publiez pas ces fichiers.

Les fichiers suivants sont particulièrement sensibles :

```text
/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key
```

Protégez les permissions de sauvegarde en conséquence.

---

# 135. Planification de la restauration

Une restauration doit être testée sur un système hors production avant d'être nécessaire pour la reprise après sinistre.

La séquence de restauration est conceptuellement :

```text
Backup
  ↓
Verify backup integrity
  ↓
Prepare clean LUMS host
  ↓
Restore secret/configuration
  ↓
Restore database
  ↓
Restore TLS material
  ↓
Start LUMS
  ↓
Run integrity checks
  ↓
Validate users/clients/jobs
```

Ne remplacez pas une base de données de production sans d'abord préserver l'état existant.

---

# 136. Vérifier une restauration de base de données

Après avoir restauré une base de données, exécutez :

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

print(
    db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

db.close()
PY
```

Attendu :

```text
ok
```

Vérifiez ensuite :

```text
users
clients
update jobs
package data
audit data
```

Ne supposez pas qu'une vérification d'intégrité SQLite réussie prouve que l'état complet de l'application est correct.

---

# 137. Principes de maintenance

La maintenance de routine devrait suivre :

```text
Observe
   ↓
Back up
   ↓
Change
   ↓
Verify
```

N'effectuez pas de maintenance non liée pendant un job de mise à jour actif.

Avant la maintenance :

```bash
sudo docker ps \
    --filter name=lums
```

Vérifiez les jobs actifs dans l'interface LUMS.

Si une mise à jour est en cours, laissez-la se terminer, sauf si l'opération de maintenance nécessite spécifiquement une interruption.

---

# 138. Maintenance du conteneur

Examinez l'image en cours d'exécution :

```bash
sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'
```

Examinez le conteneur :

```bash
sudo docker ps \
    --filter name=lums
```

Examinez les journaux récents :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Ne supprimez pas le volume persistant lors de la maintenance ordinaire du conteneur.

Le volume contient l'état applicatif.

---

# 139. Maintenance de l'image

Avant de remplacer l'image de production :

```bash
cd /opt/lums-public
```

Exécutez les tests automatisés :

```bash
./.venv-test/bin/pytest -q
```

Construisez la nouvelle image :

```bash
sudo docker build \
    -t lums:new \
    .
```

Ne remplacez pas le conteneur en cours d'exécution avant que l'image n'ait passé la validation requise.

Gardez le conteneur actuellement fonctionnel disponible jusqu'à ce que le remplacement ait été vérifié.

---

# 140. Remplacement contrôlé du conteneur

Lors du remplacement du conteneur de production :

```text
Current container
       │
       ▼
Backup / checkpoint
       │
       ▼
Build new image
       │
       ▼
Validate image
       │
       ▼
Stop old container
       │
       ▼
Start new container
       │
       ▼
Validate runtime
       │
       ▼
Validate HTTPS
       │
       ▼
Validate application
```

Le volume persistant doit rester :

```text
lums-data
```

Le montage secret doit rester en lecture seule.

Le port applicatif doit rester limité à localhost.

---

# 141. Vérifier la sécurité à l'exécution après remplacement

Après chaque remplacement de conteneur, répétez :

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Vérifiez :

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Vérifiez également :

```bash
sudo docker port \
    lums
```

Attendu :

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 142. Vérifier les données persistantes après remplacement

Après avoir démarré le conteneur de remplacement :

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Puis :

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Attendu :

```text
ok
```

Enfin, vérifiez que les utilisateurs et clients existants sont toujours présents via l'interface LUMS.

---

# 143. Point de contrôle d'achèvement de la maintenance

Après la maintenance, vérifiez :

```text
[ ] Container running
[ ] Runtime hardening intact
[ ] Persistent volume mounted
[ ] Database accessible
[ ] SQLite integrity check passes
[ ] Nginx running
[ ] HTTPS working
[ ] Login working
[ ] Existing users present
[ ] Existing clients present
[ ] Agent reporting working
[ ] Watcher working
[ ] Update jobs working
[ ] Audit logging working
```

Ce n'est qu'après ces contrôles que l'opération de maintenance est terminée.

---

# 144. État de l'installation à ce stade

Un environnement LUMS correctement installé se compose maintenant de :

```text
                    ┌──────────────────────┐
                    │       Browser        │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │        Nginx         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    LUMS Container    │
                    │                      │
                    │ Flask / Gunicorn     │
                    │ RBAC                 │
                    │ CSRF                 │
                    │ Audit Logging        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       SQLite         │
                    │     lums-data        │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌──────────────┐              ┌──────────────┐
        │ LUMS Agent   │              │ LUMS Watcher │
        │ 1.7.0        │              │ 1.2.1        │
        └──────┬───────┘              └──────┬───────┘
               │                             │
               ▼                             ▼
        Inventory / Report             Update Jobs
               │                             │
               └──────────────┬──────────────┘
                              ▼
                       APT / pacman
```

C'est l'architecture opérationnelle prévue.

La section suivante couvre les mises à niveau, la désinstallation et la liste de contrôle finale d'installation.

# 145. Procédure de mise à niveau

Les mises à niveau de LUMS doivent être effectuées par étapes contrôlées.

La séquence recommandée est :

```text
Review
   ↓
Backup
   ↓
Test
   ↓
Build
   ↓
Deploy
   ↓
Validate
```

Ne mettez pas à niveau l'installation de production simplement parce qu'une nouvelle révision Git existe.

Examinez d'abord les modifications :

```bash
cd /opt/lums-public

git status
git log --oneline -10
```

Examinez les modifications pertinentes de l'application, de l'agent et des migrations avant le déploiement.

---

# 146. Créer une sauvegarde avant mise à niveau

Avant de remplacer le conteneur de production, créez une sauvegarde actuelle de l'état persistant de LUMS.

Vérifiez le volume actif :

```bash
sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'
```

Confirmez que :

```text
lums-data
```

est toujours monté à :

```text
/var/lib/lums
```

Protégez également la configuration externe :

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/
```

Ne poursuivez pas une mise à niveau si la sauvegarde requise ne peut pas être vérifiée.

---

# 147. Arrêter les modifications inutiles pendant une mise à niveau

Avant la mise à niveau, examinez les jobs actifs dans l'interface LUMS.

Évitez de remplacer l'application pendant qu'un job de mise à jour critique est activement en cours d'exécution.

Si nécessaire, attendez que le job atteigne un état final :

```text
SUCCESS
```

ou :

```text
FAILED
```

Ne changez pas manuellement un job de `RUNNING` à `SUCCESS` ou `FAILED` simplement pour rendre une mise à niveau possible.

---

# 148. Mettre à jour le référentiel

Déplacez-vous vers le référentiel :

```bash
cd /opt/lums-public
```

Examinez l'état actuel :

```bash
git status
```

Mettez à jour le référentiel à l'aide du flux de travail normal du projet.

Après la mise à jour :

```bash
git log --oneline -5
```

Vérifiez que la révision prévue est extraite.

Ne déployez pas un référentiel contenant des modifications locales involontaires.

Si des modifications locales sont présentes :

```bash
git status
```

Examinez-les avant de continuer.

---

# 149. Exécuter la suite de tests avant de construire

Exécutez :

```bash
./.venv-test/bin/pytest -q
```

Tous les tests doivent réussir.

Un nombre de tests modifié n'est pas automatiquement un problème. L'exigence est que la suite complète se termine avec succès.

---

# 150. Construire l'image mise à jour

Construisez une nouvelle image sans remplacer immédiatement le conteneur en cours d'exécution :

```bash
sudo docker build \
    -t lums:new \
    .
```

Vérifiez l'image :

```bash
sudo docker image inspect \
    lums:new
```

La construction doit se terminer avec succès.

N'utilisez pas une image échouée ou partiellement construite pour le déploiement de production.

---

# 151. Vérifier l'image mise à jour

Examinez les métadonnées de l'image :

```bash
sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'
```

L'image doit préserver le modèle applicatif non-root attendu.

Le runtime de production doit toujours fournir :

```text
read-only root filesystem
dropped Linux capabilities
no-new-privileges
read-only secret mount
persistent application volume
localhost-only application port
```

---

# 152. Remplacer le conteneur de production

Lorsque la nouvelle image a passé la validation, remplacez le conteneur en cours d'exécution en utilisant la configuration durcie établie.

Arrêtez le conteneur existant :

```bash
sudo docker stop \
    lums
```

Supprimez uniquement le conteneur :

```bash
sudo docker rm \
    lums
```

Ne supprimez **pas** :

```text
lums-data
```

Démarrez le remplacement avec le runtime durci :

```bash
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
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:new
```

---

# 153. Vérifier le conteneur de remplacement

Vérifiez :

```bash
sudo docker ps \
    --filter name=lums
```

Puis :

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Vérifiez le runtime :

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Attendu :

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

---

# 154. Vérifier la disponibilité de l'application

Vérifiez le point de terminaison applicatif local :

```bash
curl -I \
    http://127.0.0.1:5050/
```

Testez ensuite le chemin HTTPS public :

```bash
curl -I \
    https://LUMS-SERVER/
```

Vérifiez la connexion via le navigateur.

Ne considérez pas la mise à niveau comme terminée avant que le chemin HTTPS externe n'ait également été testé.

---

# 155. Vérifier l'état persistant après mise à niveau

Vérifiez la base de données :

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Exécutez :

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Attendu :

```text
ok
```

Vérifiez via l'interface web que :

```text
users
clients
jobs
audit history
package information
```

restent disponibles.

---

# 156. Vérifier la communication client après mise à niveau

Exécutez l'agent sur un client de test :

```bash
sudo systemctl start \
    lums-agent.service
```

Examinez :

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Vérifiez que le serveur accepte le rapport.

Vérifiez ensuite le client dans l'interface LUMS.

---

# 157. Vérifier l'exécution des mises à jour après mise à niveau

Créez un job de test contrôlé.

Vérifiez :

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

ou un état attendu :

```text
FAILED
```

lorsque l'opération échoue réellement.

Examinez le Watcher :

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Cela confirme que la mise à niveau n'a pas cassé le chemin d'exécution.

---

# 158. Vérifier la base de sécurité après mise à niveau

Chaque mise à niveau de production doit préserver la base de sécurité.

Vérifiez :

```text
[ ] HTTPS
[ ] Bearer client authentication
[ ] RBAC
[ ] CSRF protection
[ ] Audit logging
[ ] Non-root container
[ ] Read-only root filesystem
[ ] Capabilities dropped
[ ] no-new-privileges
[ ] Protected secret mount
[ ] Persistent data volume
[ ] Localhost-only Docker port
[ ] Firewall policy
```

Une mise à niveau fonctionnelle qui affaiblit ces propriétés n'est pas considérée comme terminée.

---

# 159. Procédure de retour arrière

Si le nouveau conteneur échoue à la validation, ne détruisez pas immédiatement les informations de déploiement précédentes.

Examinez d'abord :

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Si l'image précédente est toujours disponible :

```bash
sudo docker images
```

restaurez l'image précédemment validée en utilisant la même configuration de conteneur durcie.

Le volume persistant reste :

```text
lums-data
```

Ne restaurez pas une sauvegarde de base de données simplement parce que le conteneur applicatif a été remplacé.

Ne restaurez la base de données que lorsque la base de données elle-même doit être récupérée.

---

# 160. Préparation de la désinstallation

Avant de désinstaller LUMS, décidez si les données applicatives persistantes doivent être conservées.

Les éléments suivants sont des ressources distinctes :

```text
Container
Image
Persistent volume
Configuration
TLS material
Nginx configuration
Client installations
```

La suppression du conteneur ne supprime pas le volume Docker.

Cette distinction est intentionnelle.

---

# 161. Supprimer le conteneur LUMS

Arrêtez le conteneur :

```bash
sudo docker stop \
    lums
```

Supprimez-le :

```bash
sudo docker rm \
    lums
```

Vérifiez :

```bash
sudo docker ps -a \
    --filter name=lums
```

Le volume persistant est toujours présent, sauf s'il a été explicitement supprimé.

---

# 162. Supprimer l'image Docker LUMS

Listez les images :

```bash
sudo docker images \
    'lums*'
```

Supprimez uniquement les images qui ne sont plus nécessaires :

```bash
sudo docker rmi \
    lums:new
```

Répétez pour les autres images LUMS locales obsolètes le cas échéant.

Ne supprimez pas l'image actuellement requise pour un retour arrière avant que l'installation n'ait été entièrement décommissionnée.

---

# 163. Supprimer le volume persistant

N'effectuez cette étape que lorsque la base de données LUMS n'est plus requise.

Vérifiez :

```bash
sudo docker volume inspect \
    lums-data
```

Créez une sauvegarde finale si nécessaire.

Supprimez ensuite :

```bash
sudo docker volume rm \
    lums-data
```

Cela supprime définitivement les données applicatives persistantes stockées dans ce volume.

N'exécutez pas cette commande lors de mises à niveau normales.

---

# 164. Supprimer la configuration du serveur LUMS

Lorsque le serveur est définitivement décommissionné, supprimez la configuration spécifique à LUMS :

```text
/etc/lums/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Supprimez le site Nginx :

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/lums
```

Supprimez la configuration :

```bash
sudo rm -f \
    /etc/nginx/sites-available/lums
```

Validez ensuite Nginx :

```bash
sudo nginx -t
```

Rechargez :

```bash
sudo systemctl reload nginx
```

Ne supprimez `/etc/lums/` qu'après avoir vérifié qu'aucune autre application n'en dépend.

---

# 165. Supprimer les installations clients

Les clients LUMS doivent être décommissionnés séparément.

Désactivez le timer de l'agent :

```bash
sudo systemctl disable --now \
    lums-agent.timer
```

Désactivez le timer du Watcher :

```bash
sudo systemctl disable --now \
    lums-agent-watcher.timer
```

Arrêtez tous les services restants :

```bash
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service
```

Supprimez les unités systemd installées :

```bash
sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Rechargez systemd :

```bash
sudo systemctl daemon-reload
```

Supprimez l'installation de l'agent :

```bash
sudo rm -rf \
    /opt/lums-agent
```

Supprimez la configuration du client :

```bash
sudo rm -f \
    /etc/default/lums-agent
```

N'effectuez ces étapes que lorsque le client est réellement retiré de la gestion LUMS.

---

# 166. Liste de contrôle finale de l'installation serveur

Une installation LUMS terminée devrait satisfaire tous les éléments suivants :

```text
SERVER
[ ] Debian/Linux host prepared
[ ] Docker installed
[ ] Nginx installed
[ ] Repository deployed
[ ] Application secret generated
[ ] TLS material installed
[ ] LUMS image built
[ ] Persistent volume created
[ ] Hardened container deployed
[ ] Container runs as non-root
[ ] Root filesystem is read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Secret mounted read-only
[ ] Persistent data volume mounted
[ ] Application bound to 127.0.0.1:5050
[ ] Nginx HTTPS configured
[ ] HTTP redirects to HTTPS
[ ] TLS verified
[ ] Database initialized
[ ] SQLite integrity check passes
[ ] Migrations complete
```

---

# 167. Liste de contrôle finale de l'installation client

```text
CLIENT
[ ] Supported Linux distribution
[ ] systemd available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher installed
[ ] Watcher version verified
[ ] Client configuration protected
[ ] Unique client token configured
[ ] TLS trust configured
[ ] Agent manual run succeeds
[ ] Initial report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Watcher timer enabled
[ ] Idle detection verified
[ ] Package inventory verified
[ ] Update detection verified
```

---

# 168. Liste de contrôle fonctionnelle finale

```text
FUNCTIONALITY
[ ] Administrator login works
[ ] Operator login works
[ ] Viewer login works
[ ] Administrator RBAC verified
[ ] Operator RBAC verified
[ ] Viewer RBAC verified
[ ] Client authentication verified
[ ] Token rotation verified
[ ] Package search verified
[ ] Package installation verified
[ ] Package removal verified
[ ] Package update verified
[ ] System update path verified
[ ] Update jobs verified
[ ] Job result validation verified
[ ] Job recovery verified
[ ] Reboot detection verified
[ ] Audit logging verified
[ ] Logs contain no secrets
[ ] End-to-end reporting verified
[ ] End-to-end update execution verified
```

---

# 169. Liste de contrôle de sécurité finale

```text
SECURITY
[ ] HTTPS enforced
[ ] Client Bearer authentication enabled
[ ] RBAC enforced server-side
[ ] CSRF protection enabled
[ ] Session protection enabled
[ ] Login rate limiting enabled
[ ] Password hashing enabled
[ ] Client token hashing enabled
[ ] Client token rotation available
[ ] Audit logging enabled
[ ] Secrets outside Git
[ ] Secrets outside Docker image
[ ] TLS private key protected
[ ] Docker root filesystem read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Container runs as non-root
[ ] Persistent data isolated in volume
[ ] Application port localhost-only
[ ] Firewall reviewed
[ ] Default Nginx site removed or controlled
[ ] Backup procedure defined
[ ] Restore procedure tested
```

---

# 170. Liste de contrôle finale des tests

Exécutez la suite de tests automatisés complète :

```bash
cd /opt/lums-public

./.venv-test/bin/pytest -q
```

L'installation ne doit être considérée comme terminée que lorsque la suite de tests complète réussit.

Vérifiez ensuite manuellement le runtime de production :

```bash
sudo docker ps \
    --filter name=lums
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

```bash
curl -I \
    https://LUMS-SERVER/
```

```bash
sudo ss -lntp
```

---

# 171. Vérification finale de la documentation

Avant de déclarer l'installation terminée, vérifiez que la documentation correspond au déploiement réel.

Au minimum, examinez :

```text
install.md
security.md
troubleshooting.md
administration.md
docs/README.md
```

Les guides anglais à la racine constituent la référence technique. Les traductions de `docs/locales/` peuvent ne pas encore inclure tous les détails techniques.

La documentation ne doit pas contenir :

```text
old container commands
obsolete image names
obsolete RBAC rules
obsolete test counts
obsolete service paths
obsolete authentication mechanisms
real secrets
real client tokens
private keys
```

Si le déploiement change, mettez à jour la documentation en même temps que l'implémentation.

---

# 172. Préparation à la version

Une installation réussie ne signifie pas automatiquement que LUMS a une version officielle.

L'état actuel du projet sépare délibérément :

```text
Working implementation
Security audit
Documentation review
Release preparation
Versioning
Git tag
GitHub Release
```

Une version officielle de LUMS ne devrait être créée qu'après que l'implémentation complète, la revue de sécurité, la revue de documentation et la validation finale ont été terminées.

D'ici là, traitez le référentiel comme un projet en développement actif.

---

# 173. Base opérationnelle

La base actuellement documentée est :

```text
LUMS Server
    Docker
    Nginx
    HTTPS
    SQLite
    RBAC
    CSRF
    Audit Logging
    Hardened Container

LUMS Agent
    Version 1.7.0

LUMS Watcher
    Version 1.2.1

Database
    journal_mode=wal
    busy_timeout=5000
    synchronous=2
    foreign_keys=ON (application connections)

Container
    non-root
    read-only root filesystem
    CapDrop=ALL
    no-new-privileges
    localhost-only application port

Roles
    Administrator
    Operator
    Viewer
```

Cette base devrait être traitée comme l'état de référence pour le dépannage et la maintenance future.

---

# 174. Installation terminée

L'installation est terminée lorsque :

```text
Server
  │
  ├── HTTPS works
  ├── Authentication works
  ├── RBAC works
  ├── Database is healthy
  ├── Container is hardened
  └── Persistent storage is verified
       │
       ▼
Client
  │
  ├── Agent reports
  ├── Watcher executes
  ├── Package manager works
  ├── Jobs complete
  ├── Results are validated
  └── Recovery works
       │
       ▼
Operations
  │
  ├── Backup exists
  ├── Restore is understood
  ├── Troubleshooting documentation is available
  └── Security baseline is maintained
```

Le principe opérationnel fondamental de LUMS est :

```text
Observe first.
Change second.
Verify third.
Document last.
```

Pour les changements de production, étendez cela à :

```text
Backup
   ↓
Change
   ↓
Verify
   ↓
Document
```

Une installation LUMS devrait toujours rester reproductible, auditable et récupérable.

---

## Agent de télémétrie CPU et mémoire facultatif

Pour un aperçu des mesures de télémétrie, de la sécurité, de la conservation des données et du dépannage, voir [telemetry.md](telemetrie.md).

L'agent de télémétrie est distinct de l'agent de rapport existant et du watcher. Il envoie des mesures de CPU et de mémoire au point d'accès authentifié `POST /api/telemetry`. Le tableau de bord lit les mesures via l'API de télémétrie client authentifiée.

### Fichiers d'installation

Examinez ces fichiers du dépôt avant l'installation :

- `agent/telemetry.py`
- `agent/lums-telemetry.service`
- `agent/lums-telemetry.timer`
- `scripts/install-telemetry-agent.sh`
- `tests/test_telemetry_agent.py`

Après avoir configuré `/etc/default/lums-agent` comme décrit ci-dessous, mettez à jour le checkout du dépôt sur le client Debian et exécutez depuis sa racine :

```sh
sudo bash scripts/install-telemetry-agent.sh
```

Le programme d'installation vérifie que `LUMS_BASE` et `LUMS_TOKEN` sont présents sans afficher leurs valeurs. Il installe ou met à jour le collecteur et les unités systemd, active le timer de cinq secondes et exécute un échantillon immédiat pour vérifier la connexion. Si le service échoue, il affiche les journaux récents du service de télémétrie. Le jeton reste dans la configuration client existante et n'est copié dans aucun autre fichier.

Installez le script de télémétrie dans `/usr/local/lib/lums-telemetry/telemetry.py`, appartenant à root et non modifiable par le compte de service. Installez le service et le timer sous les noms `/etc/systemd/system/lums-telemetry.service` et `/etc/systemd/system/lums-telemetry.timer`.

Le service utilise `DynamicUser=yes`, s'exécute avec des privilèges restreints et est ajouté au groupe `systemd-journal` pour un accès en lecture seule aux journaux d'événements du système. Cela alimente les synthèses limitées de sécurité et de connexions du tableau de bord ; les messages de journal bruts ne sont pas envoyés au serveur. C'est un service à exécution unique planifié par un timer distinct ; il ne remplace ni l'agent LUMS existant ni le watcher.

Un client LUMS normal en ligne n'implique pas que ce timer de télémétrie distinct soit installé ou activé. La page `/monitoring` indique si le client sélectionné n'a envoyé aucun échantillon, n'envoie que des métriques de base, ou possède des données détaillées périmées.

### Configuration et TLS

Configurez `/etc/default/lums-agent` avec l'URL du serveur et le jeton individuel du client :

```sh
LUMS_BASE=https://lums.example.invalid
LUMS_TOKEN=REPLACE_WITH_THIS_CLIENTS_TOKEN
LUMS_CA_FILE=/etc/ssl/certs/lums-ca.crt
```

Remplacez l'URL d'exemple et le jeton par les valeurs réelles de l'environnement. Protégez le fichier de configuration pour que seul root puisse le lire, par exemple avec le mode `0600`. N'enregistrez jamais un vrai jeton dans le contrôle de version et ne le partagez pas entre clients.

Vous pouvez éventuellement choisir les unités de service systemd à signaler avec une liste d'autorisation séparée par des virgules :

```sh
LUMS_MONITORED_SERVICES=lums-agent.service,lums-telemetry.service,ssh.service,wazuh-agent.service,suricata.service
```

Si elle n'est pas définie, l'agent utilise sa liste intégrée de services LUMS, Docker et SSH. Wazuh et Suricata sont facultatifs : n'ajoutez que les unités de service installées sur le client, puis activez leurs lignes d'état dans le tableau de bord `/health`. Seul l'état systemd est signalé ; aucun identifiant d'API n'est requis ni stocké, et aucun flux d'alertes de sécurité n'est récupéré.

Si une autorité de certification privée est nécessaire, installez son certificat à un emplacement lisible par le processus du service, par exemple `/etc/ssl/certs/lums-ca.crt`, et définissez `LUMS_CA_FILE` en conséquence. Ne désactivez pas la vérification des certificats. Lorsque `LUMS_CA_FILE` n'est pas défini, l'agent utilise le magasin de confiance CA par défaut du système d'exploitation. Si une CA privée est nécessaire, définissez explicitement `LUMS_CA_FILE` sur un fichier de certificat CA existant et lisible par le processus du service. Un fichier CA explicitement configuré mais manquant ou illisible fait échouer l'agent au lieu de se rabattre silencieusement sur un autre magasin de confiance. Ne désactivez pas la vérification des certificats et n'affaiblissez pas les permissions des répertoires pour contourner des problèmes de configuration de certificat.

### Validation avant activation

Exécutez d'abord les tests du projet et vérifiez les fichiers d'unité :

```sh
.venv/bin/python -m pytest -q tests/test_telemetry.py tests/test_telemetry_agent.py
systemd-analyze verify agent/lums-telemetry.service agent/lums-telemetry.timer
```

Sur un client de test, installez les fichiers et la configuration, rechargez systemd et exécutez le service manuellement avant d'activer son timer. Confirmez l'authentification réussie et l'arrivée des échantillons dans le tableau de bord. Activez ensuite seulement le timer sur ce client de test. Ne l'activez pas sur des clients de production avant que la version côté serveur ait été examinée et approuvée.

L'agent envoie un rapport toutes les cinq secondes. Le serveur conserve les mesures pendant sept jours et l'API du tableau de bord renvoie au plus 1 000 échantillons uniformément espacés par fenêtre d'historique demandée, en préservant le premier et le dernier échantillon.
