# LUMS — Système de thèmes facultatifs

> **Un LUMS · Plusieurs interfaces · Le même backend**

LUMS propose un système de thèmes facultatif côté client qui permet de modifier l'apparence visuelle de l'interface sans changer les fonctionnalités sous-jacentes de LUMS.

Les thèmes ne constituent qu'une couche de présentation. Ils ne remplacent, ne modifient et ne contournent ni le backend LUMS, ni l'authentification, l'autorisation, l'exécution des mises à jour, la gestion des paquets, la gestion des clients, le traitement des jobs ou les contrôles de sécurité.

Le système de thèmes permet d'adapter LUMS à différentes préférences visuelles tout en conservant une application cohérente.

## État de l'implémentation et source de référence

L'implémentation actuelle dans le navigateur se trouve dans `server/static/theme.js`. Elle prend en charge `standard`, `LUMSStadium`, `golf`, `nerd`, `geek` et `admin`, enregistre la sélection dans le `localStorage` du navigateur sous `lums-theme` et utilise `standard` comme solution de repli lorsque l'identifiant enregistré est absent ou invalide. Le thème `nerd` lance l'effet Matrix et le thème `geek`, l'effet réseau. Le choix du thème est une préférence du navigateur, et non un paramètre de compte ni un état d'autorisation côté serveur.

Cette référence contient également des exigences de conception et des exemples conceptuels. Les formulations comme « devrait », « doit » ou « futur » expriment des orientations architecturales ; elles ne prouvent pas qu'une caractéristique visuelle particulière ou un comportement d'accessibilité est implémenté. Vérifiez le comportement actuel dans le code source avant de considérer un concept comme une fonctionnalité livrée.

---

## 1. Vue d'ensemble

Le système de thèmes facultatif permet à l'interface web de LUMS de proposer plusieurs environnements visuels tout en utilisant le même backend applicatif.

Un thème peut modifier :

* les couleurs
* la typographie
* les arrière-plans
* les éléments décoratifs
* la mise en valeur visuelle
* l'apparence de la navigation
* les animations
* les effets visuels facultatifs
* la présentation propre à une page

Un thème ne doit pas modifier :

* les permissions des utilisateurs
* les points de terminaison d'API disponibles
* le comportement d'authentification
* les décisions d'autorisation
* la protection CSRF
* l'authentification des clients
* l'exécution des mises à jour
* les permissions de gestion des paquets
* le traitement de l'état des jobs
* la journalisation d'audit
* le comportement de la base de données
* les frontières de sécurité

Le principe est simple :

> **Les thèmes changent l'apparence de LUMS, pas ce que LUMS a le droit de faire.**

---

## 2. Principes de conception

Le système de thèmes suit plusieurs principes.

### 2.1 Caractère facultatif

Les thèmes sont une fonctionnalité facultative du frontend.

LUMS reste entièrement fonctionnel sans qu'aucun thème supplémentaire ne soit sélectionné.

L'apparence standard de LUMS sert de présentation par défaut.

---

### 2.2 Côté client

Le choix du thème relève du frontend.

Changer de thème ne doit pas nécessiter de modifier l'état de l'application côté serveur.

Le thème sélectionné par un utilisateur est donc une préférence de présentation, et non une permission de compte ni une configuration du backend.

---

### 2.3 Indépendance du backend

Tous les thèmes utilisent le même backend LUMS.

Les éléments suivants restent indépendants du thème sélectionné :

```text
Authentication
Authorization
RBAC
Client Management
Software Inventory
Update Detection
Package Management
Update Jobs
Job Recovery
Audit Logging
Database Operations
```

Le backend reste la source faisant autorité pour toutes les décisions sensibles en matière de sécurité et d'exploitation.

---

### 2.4 Pas de sécurité par le thème

Un thème ne doit jamais servir de mécanisme de sécurité.

Par exemple, masquer une action dans l'interface n'accorde ni ne retire une permission.

Si une opération n'est pas autorisée pour un utilisateur, le serveur doit la rejeter quel que soit le thème actif.

Ainsi, la présentation côté frontend ne peut pas devenir une frontière d'autorisation.

---

### 2.5 Repli gracieux

Le système de thèmes devrait toujours fournir une solution de repli valide.

Dans les cas suivants :

* aucun thème n'a été sélectionné ;
* un thème enregistré n'est plus disponible ;
* l'identifiant du thème est invalide ;
* une ressource du thème ne peut pas être chargée ;

LUMS devrait revenir à la présentation standard au lieu de rendre l'interface inutilisable.

---

## 3. Architecture conceptuelle

Le système de thèmes peut être considéré comme une couche de présentation distincte autour de l'application LUMS existante.

```text
┌──────────────────────────────────────┐
│              LUMS UI                 │
│                                      │
│  ┌────────────────────────────────┐  │
│  │        Theme Presentation      │  │
│  │                                │  │
│  │ Standard / Stadium / Golf /    │  │
│  │ Nerd / Geek / Admin / ...      │  │
│  └────────────────────────────────┘  │
│                  │                   │
│                  ▼                   │
│        Common Frontend Logic        │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             LUMS API                 │
│                                      │
│ Authentication / RBAC / Jobs /       │
│ Clients / Packages / Updates / Logs  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          LUMS Backend                │
│                                      │
│ Flask / SQLite / Job Processing /   │
│ Client Communication                 │
└──────────────────────────────────────┘
```

La frontière importante sépare la **présentation** de la **logique applicative**.

Les thèmes se situent au-dessus de cette frontière.

---

## 4. Cycle de vie d'un thème

Conceptuellement, la sélection d'un thème suit cette séquence :

```text
User selects theme
        │
        ▼
Frontend stores selection
        │
        ▼
Theme initialization
        │
        ▼
Theme applied to UI
        │
        ▼
LUMS continues using
the same backend and permissions
```

La sélection ne crée pas un nouvel environnement LUMS.

Il n'existe toujours qu'une seule application LUMS, un seul backend et un seul modèle de sécurité.

---

## 5. Identifiants de thème

Les thèmes devraient utiliser des identifiants internes stables plutôt que de dépendre de leur nom affiché.

Par exemple :

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

L'identifiant est un détail d'implémentation.

Le nom de thème visible peut être modifié indépendamment, sans devoir changer le backend ni l'architecture de l'application.

Lorsqu'un identifiant de thème est supprimé ou renommé, le système devrait prévoir une solution de repli pour les utilisateurs dont le navigateur contient encore l'ancien identifiant.

---

## 6. Séparation des responsabilités

Le système de thèmes a délibérément un périmètre de responsabilité restreint.

### Couche de thème

Responsable de :

* la présentation visuelle
* la sélection du thème
* le style propre au thème
* les effets visuels facultatifs
* les éléments décoratifs du frontend propres au thème
* le comportement de présentation lié à l'accessibilité

### Frontend commun

Responsable de :

* l'affichage des données de l'application
* l'appel des API LUMS
* l'affichage des jobs et des informations sur les logiciels
* la gestion des interactions utilisateur
* la visibilité au niveau de la présentation

### Backend

Responsable de :

* l'authentification
* l'autorisation
* le RBAC
* la protection CSRF
* l'authentification des clients
* la création des jobs
* l'exécution des jobs
* la gestion des paquets
* les opérations de base de données
* la journalisation d'audit
* les décisions de sécurité

Cette séparation est fondamentale pour la conception.

---

## 7. Frontière de sécurité

Le système de thèmes n'est **pas un code de confiance pour les besoins d'autorisation**.

Même si un thème modifie ou masque un élément de l'interface, le backend reste chargé de valider l'opération demandée.

Conceptuellement :

```text
Frontend visibility
        ≠
Backend permission
```

Par exemple :

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

Le même principe s'applique aux fonctions d'administration, aux jobs de mise à jour, à la gestion des clients et à toute autre opération privilégiée.

---

## 8. Principe opérationnel

Le système de thèmes devrait rester sans effet sur l'architecture opérationnelle de LUMS.

Un changement de thème ne doit pas nécessiter :

* de reconstruire la base de données ;
* de modifier la configuration des clients ;
* de changer les tokens clients ;
* de redémarrer les agents de mise à jour ;
* de modifier les jobs de mise à jour ;
* de modifier le RBAC ;
* de changer la configuration réseau ;
* de modifier le comportement de gestion des paquets.

Le thème est une préférence de présentation, pas une configuration opérationnelle.

---

## 9. Périmètre de la documentation

Ce document décrit le système de thèmes facultatif de LUMS lui-même.

Les sujets généraux de LUMS sont documentés séparément :

* Installation et déploiement → `install.md`
* Administration et maintenance → `administration.md`
* Dépannage → `troubleshooting.md`
* Architecture de sécurité et audits → `security.md`
* Présentation générale du projet → `README.md`

Cette séparation évite que la documentation des thèmes ne devienne un deuxième manuel d'installation ou d'administration.

---

## 10. Principe fondamental

Le système de thèmes facultatif peut donc se résumer ainsi :

> **Un LUMS. Un backend. Un modèle de sécurité. Plusieurs interfaces possibles.**

# LUMS — Système de thèmes facultatifs

## Partie 2 — Structure et sélection des thèmes

## 11. Structure des thèmes

Le système de thèmes facultatif sépare la sélection du thème de sa présentation visuelle réelle.

Un thème se compose conceptuellement de trois couches :

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

L'identifiant détermine le thème sélectionné.

Le mécanisme de sélection détermine le thème qui doit être actif à cet instant.

La couche de présentation applique à l'interface LUMS la configuration visuelle correspondante.

Cette séparation permet d'ajouter ou de supprimer des thèmes sans modifier l'architecture fondamentale de l'application LUMS.

---

## 12. Sélection du thème

La sélection du thème est gérée par le frontend.

Le thème sélectionné est considéré comme une préférence locale de présentation, et non comme une propriété de compte côté serveur.

Conceptuellement :

```text
User
 │
 ▼
Theme Selector
 │
 ▼
Selected Theme Identifier
 │
 ▼
Frontend Theme Initialization
 │
 ▼
Active Theme
```

Le backend n'a pas besoin de connaître le thème visuel actuellement sélectionné.

Cela signifie également qu'un changement de thème n'affecte pas les autres utilisateurs.

Deux utilisateurs peuvent accéder à la même instance LUMS tout en utilisant des thèmes visuels complètement différents.

---

## 13. Préférence locale de thème

Le thème sélectionné peut être enregistré localement par le navigateur.

L'enregistrement local vise à faciliter l'utilisation :

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

La sélection de thème enregistrée doit être considérée comme un état non fiable côté client.

Le serveur ne doit jamais l'interpréter comme :

* un rôle
* une permission
* un état d'authentification
* un paramètre de sécurité
* une préférence administrative

Le navigateur peut choisir l'apparence, mais ne contrôle pas l'autorisation.

---

## 14. Initialisation du thème

Au chargement de l'interface LUMS, le frontend détermine le thème qui doit être actif.

La séquence conceptuelle est la suivante :

```text
Page Load
   │
   ▼
Read Stored Theme
   │
   ▼
Is Theme Valid?
   │
   ├── Yes ──────► Apply Theme
   │
   └── No ───────► Use Standard Theme
```

En l'absence de préférence, la présentation standard de LUMS devrait être utilisée.

Si un identifiant enregistré n'est plus pris en charge, le même mécanisme de repli devrait s'appliquer.

Cela évite qu'une préférence locale obsolète ne rende l'interface inutilisable.

---

## 15. Thème par défaut

Le thème standard de LUMS est la présentation de référence.

Il fournit l'apparence de référence à partir de laquelle les thèmes facultatifs sont définis.

Le thème standard devrait donc rester :

* fonctionnel
* lisible
* accessible
* visuellement complet
* indépendant des ressources décoratives facultatives

Les thèmes facultatifs ne doivent pas devenir des prérequis au fonctionnement normal de LUMS.

---

## 16. Application du thème

Le frontend peut représenter le thème actif au moyen d'un état applicatif partagé ou d'un attribut de thème à la racine.

Conceptuellement :

```html
<html data-theme="theme-id">
```

L'implémentation exacte peut évoluer avec le frontend.

L'exigence architecturale essentielle est que le système de styles du frontend puisse identifier le thème actif de manière cohérente.

Cela permet de séparer les styles propres au thème de la structure applicative commune.

---

## 17. Styles propres au thème

Les styles d'un thème devraient principalement être implémentés en CSS plutôt qu'en dupliquant le balisage de l'application.

Conceptuellement :

```text
Common HTML
     │
     ├── Standard styling
     ├── Stadium styling
     ├── Golf styling
     ├── Nerd styling
     ├── Geek styling
     └── Admin styling
```

Ainsi, les mêmes composants applicatifs restent disponibles dans tous les thèmes.

Par exemple, une table de clients reste une table de clients quel que soit le thème actif.

Seule sa présentation change.

---

## 18. Composants applicatifs partagés

Les thèmes ne devraient pas créer des versions indépendantes des pages LUMS.

Il convient de respecter le principe suivant :

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

Plutôt que :

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

La duplication des pages compliquerait considérablement leur maintenance et pourrait entraîner des différences de comportement entre les thèmes.

Un thème devrait donc décorer l'interface commune au lieu de remplacer l'application elle-même.

---

## 19. Ressources des thèmes

Les thèmes peuvent utiliser des ressources supplémentaires du frontend si cela convient.

Parmi les ressources possibles :

* images d'arrière-plan
* illustrations décoratives
* icônes
* animations
* superpositions visuelles
* illustrations propres au thème

Ces ressources font toujours partie de la couche de présentation du frontend.

Elles ne doivent pas contenir :

* d'identifiants
* de tokens clients
* de clés secrètes
* de fichiers de base de données
* d'informations d'authentification
* de données opérationnelles privées

Les ressources des thèmes doivent être considérées comme des ressources publiques du frontend.

---

## 20. Effets visuels facultatifs

Certains thèmes peuvent proposer des effets visuels supplémentaires.

Par exemple :

* arrière-plans animés
* effets de réseau décoratifs
* mouvement d'ambiance
* éléments d'interface thématiques
* décorations visuelles dynamiques

Ces effets doivent rester facultatifs.

Ils ne doivent jamais être nécessaires au fonctionnement de LUMS.

---

## 21. Réduction des animations

Les effets visuels devraient respecter les utilisateurs qui préfèrent réduire les animations.

Lorsque des éléments animés ou continuellement changeants sont utilisés, le système de thèmes devrait prévoir un comportement adapté à cette préférence.

Conceptuellement :

```text
Normal motion
     │
     ├── animations enabled
     └── visual effects enabled

Reduced motion
     │
     ├── animations reduced or disabled
     └── essential interface remains functional
```

L'accessibilité est prioritaire sur les animations décoratives.

Un thème devrait rester utilisable même lorsque les effets visuels sont désactivés.

---

## 22. Indépendance des thèmes

Changer de thème ne doit entraîner aucun effet secondaire opérationnel.

Par exemple :

```text
Theme change
     │
     ├── No client restart
     ├── No agent restart
     ├── No job cancellation
     ├── No database migration
     ├── No token rotation
     └── No permission change
```

Le système de thèmes est donc délibérément isolé du cycle de vie opérationnel de LUMS.

---

## 23. Gestion des échecs de thème

Un thème devrait échouer de manière sûre.

Si une ressource ou un composant de présentation propre au thème ne peut pas être chargé, l'interface LUMS commune doit rester utilisable.

La voie de récupération à privilégier est :

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

Un problème visuel ne doit pas devenir un problème de disponibilité de l'application.

---

## 24. Ajouter un nouveau thème

Un nouveau thème devrait respecter la séparation existante entre le comportement de l'application et sa présentation.

Conceptuellement :

```text
1. Define theme identifier
2. Define visual design
3. Add theme styling
4. Add optional assets
5. Add theme to selection mechanism
6. Test normal pages
7. Test different RBAC roles
8. Test reduced-motion behavior
9. Test fallback behavior
10. Verify no backend behavior changed
```

Un nouveau thème n'est terminé que si les fonctionnalités LUMS existantes restent inchangées.

---

## 25. Supprimer un thème

La suppression d'un thème devrait également être gérée sans heurt.

Si un utilisateur a encore localement un thème supprimé, le frontend devrait détecter que son identifiant n'est plus disponible et revenir au thème standard.

La suppression d'un thème visuel ne doit donc pas rendre l'interface LUMS de l'utilisateur inutilisable.

---

## 26. Nommage des thèmes

Les noms des thèmes devraient distinguer clairement :

* l'identifiant interne
* le nom affiché
* le concept visuel

Par exemple :

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

Cette séparation permet de faire évoluer le libellé visible sans modifier inutilement l'implémentation interne.

---

## 27. Concept actuel des thèmes

Le système de thèmes facultatif de LUMS repose sur plusieurs identités visuelles partageant une application commune.

Les concepts actuellement documentés sont :

| Identifiant | Concept |
| ------------- | ---------------- |
| `standard` | LUMS standard |
| `LUMSStadium` | Stade LUMS |
| `golf` | Club de golf |
| `nerd` | Mode nerd |
| `geek` | Laboratoire geek |
| `admin` | Administration d'entreprise |

Ces thèmes représentent différentes orientations visuelles, et non différentes éditions de LUMS.

Ils font tous partie de la même application.

---

## 28. Un backend, plusieurs interfaces

La relation peut se résumer ainsi :

```text
                     ┌── Standard
                     ├── Stadium
                     ├── Golf
                     ├── Nerd
                     ├── Geek
                     └── Admin
                           │
                           ▼
                    Common LUMS UI
                           │
                           ▼
                       LUMS API
                           │
                           ▼
                     LUMS Backend
```

La couche de thème s'arrête à la frontière de présentation.

Tout ce qui se trouve en dessous de cette frontière est commun à tous les thèmes.

# LUMS — Système de thèmes facultatifs

## Partie 3 — Concepts de thèmes

## 29. LUMS standard

Le thème LUMS standard est la présentation de référence de l'application.

Son objectif est de proposer une interface claire et fonctionnelle sans imposer de concept visuel particulier.

Le thème standard devrait privilégier :

* la lisibilité
* une hiérarchie claire de l'information
* une navigation prévisible
* l'accessibilité
* un faible niveau de distraction visuelle
* une présentation cohérente des composants

Il s'agit de la présentation de repli du système de thèmes.

Le thème LUMS standard devrait donc rester utilisable même si tous les thèmes visuels facultatifs sont indisponibles.

---

## 30. Stade LUMS

**Stade LUMS** est une interprétation visuelle plus expressive de l'interface LUMS.

Le concept associe l'administration système à une identité visuelle inspirée d'un stade.

Les éléments de conception possibles comprennent :

* des panneaux d'information inspirés des tableaux d'affichage
* des indicateurs d'état visuels plus marqués
* une présentation axée sur les événements
* des arrière-plans thématiques
* une mise en valeur visuelle des états opérationnels
* des éléments décoratifs de stade

Sur le plan fonctionnel, ce thème reste identique au thème LUMS standard.

Une mise à jour réussie reste une mise à jour réussie.

Un job échoué reste un job échoué.

Seule la présentation change.

---

## 31. Club de golf

Le thème **Club de golf** propose une identité visuelle volontairement contrastée.

Au lieu d'une esthétique traditionnelle de serveur ou d'infrastructure, l'interface adopte un concept récréatif plus apaisant.

Cette orientation visuelle peut privilégier :

* des surfaces épurées
* une décoration discrète
* des éléments inspirés du golf
* des métaphores visuelles évoquant un parcours
* une présentation apaisée des états
* des accents thématiques légers

Ce concept montre que LUMS n'a pas besoin de ressembler visuellement à une console d'administration traditionnelle pour rester fonctionnel.

Le backend et le comportement de l'application restent inchangés.

---

## 32. Mode nerd

Le **Mode nerd** s'adresse à une présentation plus technique et ludique.

Le concept peut souligner la nature technique de LUMS au moyen d'éléments tels que :

* un style inspiré du terminal
* une terminologie technique
* des éléments visuels axés sur le système
* une présentation destinée aux développeurs
* une esthétique diagnostique
* une décoration volontairement technique

La hiérarchie de l'information doit néanmoins rester claire.

Une interface ludique ne devrait pas rendre les informations opérationnelles plus difficiles à comprendre.

---

## 33. Laboratoire geek

Le **Laboratoire geek** représente un environnement technique plus expérimental.

Le concept visuel peut associer :

* une esthétique de laboratoire
* l'expérimentation technique
* la visualisation de l'infrastructure
* des diagrammes système
* des éléments inspirés des sciences ou de l'ingénierie
* des effets visuels expérimentaux

Ce thème vise à donner à l'interface l'apparence d'un laboratoire d'infrastructure tout en conservant les mêmes fonctionnalités LUMS sous-jacentes.

L'expérimentation visuelle doit rester isolée de l'application opérationnelle.

---

## 34. Administration d'entreprise

Le thème **Administration d'entreprise** représente une interface administrative plus sobre.

Cette orientation visuelle peut privilégier :

* des informations structurées
* des mises en page compactes
* des tableaux de bord administratifs
* des indicateurs d'état clairs
* une forte densité opérationnelle
* moins d'éléments décoratifs

Ce thème convient particulièrement aux utilisateurs qui préfèrent l'apparence classique d'une console d'administration.

Il n'accorde aucun privilège administratif supplémentaire.

Son nom décrit le concept visuel, pas un niveau d'autorisation.

---

## 35. Comparaison des thèmes

Les thèmes peuvent être considérés comme différentes interprétations visuelles de la même application :

| Thème | Orientation visuelle | Caractère principal |
| ---------------- | --------------------------- | ------------------- |
| LUMS standard | Épuré / fonctionnel | Interface de référence |
| Stade LUMS | Stade / événement | Expressif |
| Club de golf | Récréatif / apaisant | Détendu |
| Mode nerd | Technique / ludique | Orienté développeurs |
| Laboratoire geek | Expérimental / technique | Laboratoire |
| Administration d'entreprise | Structuré / administratif | Sobre |

Ce tableau décrit uniquement des concepts de présentation.

Il ne décrit **aucune** différence concernant :

* les permissions
* les fonctionnalités
* l'accès à l'API
* l'accès aux clients
* l'exécution des jobs
* la gestion des paquets
* la sécurité

---

## 36. Même interface, présentation différente

Un objectif central de conception est que le même composant applicatif reste reconnaissable d'un thème à l'autre.

Par exemple :

```text id="5dhlf7"
Client List
   │
   ├── Standard presentation
   ├── Stadium presentation
   ├── Golf presentation
   ├── Nerd presentation
   ├── Geek presentation
   └── Enterprise presentation
```

Les données sous-jacentes des clients restent identiques.

Seule leur présentation change.

Cela vaut également pour :

* les inventaires logiciels
* les mises à jour disponibles
* les jobs de mise à jour
* l'historique des jobs
* les informations sur les utilisateurs
* l'état du système
* les interfaces de gestion des paquets

---

## 37. États opérationnels

Les thèmes peuvent mettre visuellement en valeur différents états opérationnels.

Par exemple :

```text id="5wyy17"
PENDING
RUNNING
SUCCESS
FAILED
```

Un thème peut représenter ces états de différentes façons, mais leur signification sémantique doit rester cohérente.

Le thème ne doit pas redéfinir les états de l'application.

Par exemple :

```text id="j4i9qd"
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

La représentation visuelle ne fait que restituer l'état du backend.

---

## 38. Présentation des erreurs

Les thèmes peuvent également modifier la présentation visuelle des erreurs.

Toutefois, les informations sur les erreurs doivent rester compréhensibles.

Un thème ne devrait pas :

* masquer des informations d'erreur importantes
* remplacer les informations techniques par du texte décoratif
* rendre les avertissements impossibles à distinguer des états normaux
* supprimer les échecs opérationnels

La mise en forme visuelle peut améliorer la présentation, mais ne doit pas supprimer les informations de diagnostic nécessaires à la compréhension d'un problème.

---

## 39. Cohérence des états

Un même état doit avoir une signification sémantique cohérente dans tous les thèmes.

Par exemple :

| État | Signification |
| ------- | ------------------------- |
| En attente | En attente d'exécution |
| En cours | En cours de traitement |
| Réussi | Terminé avec succès |
| Échec | L'exécution a échoué |

Un thème peut représenter ces états avec des couleurs, icônes, caractères ou mises en page différents.

Leur signification sous-jacente doit rester inchangée.

---

## 40. Décoration propre au thème

Les éléments décoratifs devraient rester secondaires par rapport aux informations opérationnelles.

Par exemple :

* arrière-plans
* motifs
* illustrations
* effets d'ambiance
* icônes thématiques
* ornements visuels

Il convient de respecter l'ordre de priorité suivant :

```text id="3m08d7"
Operational Information
        │
        ▼
Application Usability
        │
        ▼
Accessibility
        │
        ▼
Visual Decoration
```

La décoration ne doit jamais prendre le pas sur les informations nécessaires à l'exploitation de LUMS.

---

## 41. Densité visuelle

Les différents thèmes peuvent utiliser des densités visuelles différentes.

Par exemple :

* Administration d'entreprise peut privilégier la densité d'information.
* LUMS standard peut privilégier un équilibre entre les informations et la lisibilité.
* Club de golf peut offrir davantage d'espace blanc.
* Mode nerd peut utiliser des éléments techniques compacts.
* Stade peut mettre en valeur de grandes zones d'état.
* Laboratoire geek peut fournir davantage de contexte visuel.

Ces différences relèvent uniquement de la présentation.

Elles ne changent ni la quantité ni le caractère faisant autorité des données sous-jacentes.

---

## 42. Accessibilité pour tous les thèmes

Chaque thème doit préserver une utilisabilité fondamentale.

Cela comprend :

* du texte lisible
* une distinction visuelle suffisante
* des commandes utilisables
* des indicateurs d'état compréhensibles
* l'accessibilité au clavier
* des états de focus utilisables
* la compatibilité avec la préférence de réduction des animations

La couleur ne doit pas être le seul moyen de communiquer un état important.

Par exemple, l'échec d'un job ne doit pas être identifiable uniquement à la couleur utilisée pour l'afficher.

---

## 43. Animations propres au thème

Les thèmes peuvent comporter des animations lorsqu'elles renforcent le concept visuel.

Par exemple :

* transitions discrètes
* arrière-plans animés
* effets de réseau
* transitions d'état
* décoration d'ambiance

Les animations devraient rester secondaires par rapport à l'application.

Elles ne devraient pas :

* empêcher les interactions
* masquer les commandes
* détourner continuellement l'attention des données opérationnelles
* nuire à l'accessibilité
* affecter les opérations du backend

---

## 44. Le réseau vivant

Certains thèmes LUMS peuvent utiliser une couche visuelle dynamique inspirée des réseaux.

Le concept représente LUMS comme un environnement d'infrastructure vivant :

```text id="7w1v8b"
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

Une telle visualisation est décorative, sauf si elle est explicitement reliée aux données réelles de l'application.

Un réseau visuel ne doit donc jamais être interprété comme une topologie réseau faisant autorité, à moins que l'application ne fournisse explicitement cette information.

Cette distinction est importante :

> **Une représentation visuelle n'est pas automatiquement une télémétrie opérationnelle.**

---

## 45. Données décoratives et données réelles

Les effets visuels propres à un thème doivent rester clairement distincts des données réelles de LUMS.

Par exemple :

```text id="z6i5j0"
Decorative node
    ≠
Real client

Animated connection
    ≠
Real network connection

Visual status effect
    ≠
Backend job state
```

Cela évite que les utilisateurs confondent une visualisation esthétique avec des informations système réelles.

---

## 46. Identité du thème

Chaque thème devrait avoir une identité reconnaissable sans devenir un produit distinct.

L'objectif est le suivant :

```text id="qv1fbe"
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

Le système de thèmes reste ainsi ludique et flexible tout en préservant l'intégrité technique de l'application.

---

## 47. Règle de conception des thèmes

La règle de conception la plus importante pour tous les thèmes est la suivante :

> **Un thème peut être expressif, inhabituel, technique, ludique ou sobre — mais il doit toujours rester LUMS.**

Quelle que soit la présentation visuelle sélectionnée, l'application doit rester identifiable comme le même système.

# LUMS — Système de thèmes facultatifs

## Partie 4 — Implémentation frontend et accessibilité

## 48. Couche de thèmes du frontend

Le système de thèmes facultatif appartient entièrement au frontend LUMS.

Sa responsabilité se limite à la présentation et à la gestion des préférences utilisateur.

Conceptuellement :

```text
┌─────────────────────────────────┐
│          LUMS Frontend          │
│                                 │
│  Common Application Logic       │
│              │                  │
│              ▼                  │
│       Theme Presentation        │
│              │                  │
│              ▼                  │
│       Browser Rendering         │
└─────────────────────────────────┘
```

La couche de thème ne remplace pas la logique commune du frontend.

Elle lui ajoute plutôt une couche de présentation supplémentaire.

---

## 49. Initialisation du thème

L'initialisation du thème devrait faire partie du processus normal de démarrage du frontend.

La séquence conceptuelle est la suivante :

```text
Frontend starts
      │
      ▼
Theme system initializes
      │
      ▼
Stored preference is evaluated
      │
      ▼
Theme availability is checked
      │
      ├── Valid → selected theme
      │
      └── Invalid → standard theme
      │
      ▼
LUMS interface rendered
```

L'initialisation devrait être légère et ne doit pas dépendre de la disponibilité du backend.

L'utilisateur devrait pouvoir charger la présentation visuelle même si une requête API échoue par la suite.

---

## 50. État du thème

Le thème actif relève de l'état du frontend.

Il doit donc être traité différemment de l'état de l'application.

### État du thème

Exemples :

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### État de l'application

Exemples :

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

L'état du thème ne doit jamais remplacer ni usurper l'état de l'application.

---

## 51. Attribut de thème à la racine

Un attribut à la racine constitue une représentation conceptuelle adaptée du thème actif.

Par exemple :

```html
<html data-theme="standard">
```

ou :

```html
<html data-theme="nerd">
```

Le CSS peut alors utiliser le thème actif comme sélecteur.

L'implémentation exacte peut évoluer, mais l'objectif architectural reste le même :

> **Une structure d'application, plusieurs définitions de présentation.**

---

## 52. Organisation du CSS

Les styles propres aux thèmes devraient rester distincts des styles communs à LUMS.

Conceptuellement :

```text
Common styles
│
├── Layout
├── Forms
├── Tables
├── Navigation
├── Status elements
└── Shared components

Theme styles
│
├── Standard
├── Stadium
├── Golf
├── Nerd
├── Geek
└── Admin
```

Les styles communs devraient définir la structure fonctionnelle.

Les styles des thèmes devraient définir leur identité visuelle.

Cela réduit les duplications et facilite la maintenance future des thèmes.

---

## 53. Variables CSS

Les systèmes de thèmes peuvent utiliser les propriétés personnalisées CSS pour séparer les valeurs sémantiques de leur représentation visuelle.

Par exemple :

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Un thème peut alors fournir ses propres valeurs :

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Le principe essentiel est que les composants utilisent, dans la mesure du possible, des variables sémantiques plutôt que des valeurs codées en dur propres à un thème.

---

## 54. Composants partagés

Le système de thèmes devrait appliquer un style aux composants partagés plutôt que les dupliquer.

Les composants courants comprennent :

* la navigation
* les boutons
* les formulaires
* les tableaux
* les indicateurs d'état
* les cartes
* les boîtes de dialogue
* les éléments de gestion des paquets
* les éléments des jobs de mise à jour
* les informations sur les clients
* les informations système

Le même composant devrait rester fonctionnellement identique quel que soit le thème actif.

---

## 55. Ressources des thèmes

Les thèmes facultatifs peuvent utiliser des ressources dédiées.

Les catégories de ressources possibles comprennent :

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Les ressources des thèmes devraient rester des ressources du frontend.

Elles ne doivent contenir aucune information sensible sur l'application.

En particulier, elles ne doivent jamais contenir :

* de mots de passe
* de clés secrètes
* de tokens clients
* de contenu de base de données
* de certificats privés
* d'informations d'authentification

---

## 56. Chargement des ressources

Les ressources d'un thème ne devraient être chargées que lorsqu'elles sont nécessaires.

La simple existence d'un thème ne devrait pas alourdir inutilement chaque page LUMS.

Dans la mesure du possible :

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

plutôt que :

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

Cela devient d'autant plus important que de nouveaux thèmes et effets visuels sont ajoutés.

---

## 57. Performances des thèmes

La personnalisation visuelle ne doit pas dégrader sensiblement l'utilisabilité de LUMS.

Il convient de prêter une attention particulière aux éléments suivants :

* les grandes images d'arrière-plan
* les éléments animés en continu
* les effets Canvas
* les mises à jour répétées du DOM
* les filtres visuels coûteux
* les requêtes réseau inutiles

Les pages opérationnelles telles que les listes de clients, les inventaires logiciels et les vues des jobs de mise à jour devraient rester réactives.

---

## 58. JavaScript décoratif

Un thème peut utiliser JavaScript pour produire des effets visuels.

Par exemple :

* arrière-plans animés
* visualisations de réseau
* décorations dynamiques
* interactions propres au thème

Ce JavaScript devrait rester isolé de la logique applicative opérationnelle.

Un script décoratif ne doit jamais être responsable :

* de l'autorisation
* de la création de jobs
* de l'installation de paquets
* de la suppression de paquets
* de l'exécution des mises à jour
* de l'authentification des clients
* de la journalisation d'audit

La distinction doit rester claire :

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Visualisation du réseau

Si un thème utilise une visualisation de type réseau, celle-ci doit être traitée comme un composant de présentation.

Par exemple :

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

À moins d'être explicitement reliée à des données LUMS faisant autorité, la visualisation ne devrait pas laisser entendre qu'elle représente l'état réel du réseau.

Cela évite que des graphismes décoratifs soient confondus avec de la surveillance ou de la télémétrie.

---

## 60. Réduction des animations

Les thèmes qui utilisent des animations devraient prendre en charge les préférences de réduction des animations.

Le comportement à privilégier est le suivant :

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

Les fonctionnalités essentielles doivent rester inchangées.

La réduction des animations ne devrait affecter que la présentation.

---

## 61. Focus et navigation au clavier

Les styles des thèmes doivent préserver l'utilisabilité au clavier.

Les éléments interactifs importants devraient conserver des états de focus visibles.

Les thèmes ne devraient pas supprimer les contours de focus sans proposer une alternative tout aussi visible.

Par exemple :

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

Cela s'applique :

* à la navigation
* aux boutons
* aux liens
* aux champs de formulaire
* aux sélecteurs
* aux boîtes de dialogue
* aux commandes de gestion des paquets

---

## 62. Indépendance vis-à-vis des couleurs

Les informations importantes ne doivent pas reposer uniquement sur la couleur.

Par exemple :

```text
FAILED
```

doit rester compréhensible grâce au texte, aux icônes, à la structure ou à un autre indicateur accessible, même si les couleurs du thème ne sont pas disponibles.

C'est particulièrement important, car les palettes de couleurs peuvent varier fortement d'un thème à l'autre.

---

## 63. Contraste

Chaque thème devrait maintenir un contraste suffisant entre :

* le texte et les arrière-plans
* les commandes et les arrière-plans
* les indicateurs d'état et les éléments qui les entourent
* les éléments actifs et leur environnement

Une palette visuellement intéressante ne remplace pas des informations lisibles.

Lorsque les couleurs d'un thème entrent en conflit avec les exigences d'accessibilité, la lisibilité est prioritaire.

---

## 64. Interface de sélection des thèmes

Le sélecteur de thème lui-même fait partie de l'interface LUMS commune.

Il devrait rester compréhensible quel que soit le thème actuellement actif.

Conceptuellement :

```text
Theme selector
      │
      ├── Standard LUMS
      ├── LUMS Stadium
      ├── Golf Club
      ├── Nerd Mode
      ├── Geek Lab
      └── Enterprise Admin
```

La sélection d'un autre thème devrait mettre à jour la présentation sans modifier la session LUMS actuelle ni l'état opérationnel.

---

## 65. Indépendance de la session

Changer de thème ne doit pas déconnecter l'utilisateur.

Cela ne doit pas :

* invalider la session
* modifier le rôle
* faire tourner les tokens clients
* modifier l'état d'authentification côté serveur

La préférence de thème est distincte de l'authentification.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. Indépendance du RBAC

Les thèmes doivent rester indépendants du RBAC.

Par exemple :

```text
Administrator
     │
     └── sees functionality permitted to administrators

Operator
     │
     └── sees functionality permitted to operators

Viewer
     │
     └── sees functionality permitted to viewers
```

Le thème sélectionné ne modifie pas ces permissions.

Un Viewer qui utilise Administration d'entreprise ne devient pas administrateur.

Un Administrator qui utilise le Mode nerd ne perd pas ses privilèges administratifs.

Le backend reste l'autorité dans tous les cas.

---

## 67. Isolation des erreurs

Une défaillance d'une fonctionnalité visuelle facultative ne devrait pas perturber le fonctionnement essentiel de LUMS.

Par exemple, si une animation décorative échoue :

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

Dans la mesure du possible, les fonctions visuelles devraient échouer indépendamment des fonctionnalités applicatives.

C'est particulièrement important pour les effets facultatifs comme les arrière-plans animés ou les visualisations de réseau.

---

## 68. Compatibilité des navigateurs

Le système de thèmes devrait utiliser des fonctionnalités de navigateur prises en charge par les navigateurs ciblés par l'environnement de déploiement de LUMS.

Lorsqu'une fonctionnalité visuelle n'est pas disponible, l'interface devrait se dégrader gracieusement au lieu de devenir inutilisable.

La présentation standard devrait rester la solution de repli de référence.

---

## 69. Principe d'implémentation

L'implémentation peut se résumer ainsi :

```text
Common HTML
     +
Common LUMS JavaScript
     +
Theme selection
     +
Theme-specific CSS/assets
     =
Optional visual layer
```

Les éléments suivants doivent rester hors de la couche de thème :

```text
Authentication
Authorization
Database
Jobs
Package management
Client authentication
Audit logging
Security decisions
```

Cette séparation rend le système de thèmes suffisamment expressif tout en évitant de le coupler au comportement central de LUMS.

# LUMS — Système de thèmes facultatifs

## Partie 5 — Sécurité, tests et développement

## 70. Frontière de sécurité

Le système de thèmes fait partie du frontend et fonctionne donc dans un environnement client non fiable.

Le navigateur contrôle la couche de présentation.

Le navigateur ne contrôle **pas** l'autorisation LUMS.

La frontière de sécurité reste la suivante :

```text id="h8e2ks"
Browser
   │
   │ untrusted presentation
   ▼
LUMS API
   │
   │ authoritative validation
   ▼
LUMS Backend
```

Toutes les décisions sensibles en matière de sécurité doivent donc rester côté serveur.

---

## 71. La sélection du thème n'est pas une autorisation

Un thème sélectionné ne doit jamais être interprété comme un signal d'autorisation.

Par exemple :

```text id="8u3r8v"
data-theme="admin"
```

ne signifie pas que l'utilisateur actuel est administrateur.

Le mot `admin` dans un identifiant de thème est purement descriptif.

Le rôle réel de l'utilisateur doit toujours provenir de la session authentifiée de l'application et de la logique d'autorisation côté serveur.

---

## 72. La visibilité du frontend n'est pas une sécurité

Un thème ou un script frontend peut masquer un élément de l'interface.

C'est utile pour la présentation.

Cela ne suffit pas pour le contrôle d'accès.

Par exemple :

```text id="7m8c6w"
Hidden button
      ≠
Unauthorized operation prevented
```

Le point de terminaison d'API correspondant doit vérifier séparément les permissions de l'utilisateur.

Cela s'applique à toutes les fonctionnalités privilégiées de LUMS.

---

## 73. Les ressources des thèmes sont publiques

Les ressources du frontend doivent être considérées comme accessibles au public pour toute personne pouvant accéder à l'interface web de LUMS.

Par conséquent, les fichiers de thème ne doivent jamais contenir de secrets.

Ne placez jamais les éléments suivants dans les ressources d'un thème :

```text id="1zjz7n"
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

Toute information qui doit rester confidentielle n'a pas sa place dans une ressource de thème.

---

## 74. Aucun secret du backend dans les thèmes

Le JavaScript d'un thème ne doit pas contenir d'identifiants serveur ni de données API privilégiées.

Si nécessaire, un thème devrait communiquer avec la couche applicative existante du frontend.

Il ne doit pas introduire de mécanisme d'authentification alternatif.

Le principe suivant s'applique :

> **Les thèmes consomment des données de présentation ; ils ne créent pas d'identifiants de sécurité.**

---

## 75. Falsification de requête intersites

Les fonctionnalités d'un thème ne doivent pas contourner la protection CSRF existante.

Si un thème propose un élément d'interface qui déclenche une opération nécessitant une requête protégée, cette requête doit respecter les mêmes exigences de sécurité que l'interface LUMS commune.

Le code visuel du thème ne bénéficie d'aucune exemption.

---

## 76. Utilisation de l'API

Un thème devrait éviter d'implémenter directement sa propre logique d'API opérationnelle.

Lorsque des données applicatives sont nécessaires, le thème devrait utiliser les mécanismes établis du frontend et de l'application LUMS.

Cela évite plusieurs implémentations indépendantes des éléments suivants :

* l'authentification
* les requêtes API
* la gestion des erreurs
* les hypothèses d'autorisation
* la gestion des jobs

La logique applicative commune reste la couche d'intégration faisant autorité du frontend.

---

## 77. Isolation des thèmes

Un thème devrait pouvoir être supprimé sans retirer les fonctionnalités essentielles de LUMS.

Conceptuellement :

```text id="3m1o8q"
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

Les thèmes facultatifs sont ainsi réellement facultatifs.

---

## 78. Tests de sécurité

Les tests de sécurité devraient démontrer que les changements de thème ne modifient pas le modèle de sécurité de LUMS.

Les vérifications pertinentes comprennent :

* un Viewer reste un Viewer
* un Operator reste un Operator
* un Administrator reste un Administrator
* les points de terminaison d'API protégés le restent
* la protection CSRF reste active
* l'authentification des clients reste inchangée
* les permissions des jobs de mise à jour restent inchangées
* les permissions de gestion des paquets restent inchangées
* la journalisation d'audit reste inchangée

Le thème lui-même ne doit jamais servir de preuve qu'une opération est sécurisée.

---

## 79. Tests fonctionnels des thèmes

Chaque thème devrait être testé avec l'application commune.

Au minimum :

```text id="9w6h1m"
Login
Client list
Client details
Installed software
Available updates
Update jobs
Job history
Package management
User management
System maintenance
Logout
```

Les fonctions disponibles exactes dépendent du rôle de l'utilisateur authentifié.

Le test vise à garantir que le rendu du thème ne perturbe pas les fonctions normales de l'application.

---

## 80. Tests RBAC des thèmes

Les tests des thèmes devraient inclure tous les rôles pertinents.

Une matrice de base :

| Rôle | Tests du thème |
| ------------- | ------------- |
| Administrator | Obligatoires |
| Operator | Obligatoires |
| Viewer | Obligatoires |

Pour chaque rôle, vérifiez qu'un changement de thème ne modifie pas les fonctionnalités autorisées.

Par exemple :

```text id="3n5p2m"
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

Le thème visuel ne doit pas modifier le résultat.

---

## 81. Tests de changement de thème

Le changement de thème devrait être testé à plusieurs reprises.

Exemple de séquence :

```text id="gk2j7m"
Standard
   ↓
Stadium
   ↓
Golf
   ↓
Nerd
   ↓
Geek
   ↓
Admin
   ↓
Standard
```

L'application devrait rester utilisable tout au long de la séquence.

Une attention particulière devrait être accordée aux éléments suivants :

* les changements de mise en page
* les tableaux
* la navigation
* les boîtes de dialogue
* les formulaires
* les indicateurs d'état
* les textes longs
* le comportement adaptatif

---

## 82. Tests de persistance

Si la préférence de thème est enregistrée localement, testez les étapes suivantes :

1. Sélectionnez un thème.
2. Rechargez la page.
3. Vérifiez que le thème reste sélectionné.
4. Fermez le navigateur.
5. Rouvrez LUMS.
6. Vérifiez que la préférence est toujours correctement prise en compte.
7. Supprimez ou invalidez le thème enregistré.
8. Vérifiez le retour au thème standard.

La valeur enregistrée ne doit jamais être considérée comme un état de sécurité de l'application.

---

## 83. Tests d'identifiant de thème invalide

Un identifiant de thème invalide ne doit pas perturber l'interface.

Par exemple :

```text id="4j5cqn"
unknown-theme
```

doit entraîner une solution de repli sûre, et non rendre la page inutilisable.

Le comportement attendu est le suivant :

```text id="5x9h2f"
Invalid theme
     │
     ▼
Standard theme
     │
     ▼
LUMS remains usable
```

---

## 84. Tests d'échec des ressources

Les scénarios d'échec des ressources facultatives devraient également être testés.

Par exemple :

* image manquante
* animation indisponible
* chemin de ressource invalide
* fonctionnalité visuelle non prise en charge
* erreur JavaScript dans une décoration facultative

Dans la mesure du possible, l'application commune devrait rester utilisable.

---

## 85. Tests de réduction des animations

Pour les thèmes qui comportent des animations, testez les environnements avec mouvement normal et ceux avec mouvement réduit.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Les commandes importantes de l'application doivent rester entièrement fonctionnelles dans les deux cas.

---

## 86. Tests adaptatifs

Les thèmes devraient être testés à différentes tailles de fenêtre d'affichage.

Au minimum :

* ordinateur de bureau
* fenêtre de taille tablette
* fenêtre étroite de taille mobile

L'identité visuelle ne doit pas se faire au détriment de commandes utilisables ou de données applicatives lisibles.

Une attention particulière devrait être accordée aux éléments suivants :

* la navigation
* les tableaux
* les boutons d'action
* les commandes de gestion des paquets
* les informations sur l'état des jobs
* les boîtes de dialogue
* les sélecteurs de thème

---

## 87. Tests de performance

Il convient d'évaluer l'impact des effets visuels sur les performances du navigateur.

Les observations pertinentes comprennent :

* le temps de chargement des pages
* la réactivité du rendu
* l'utilisation du processeur
* l'utilisation de la mémoire
* la fluidité des animations
* les mises à jour répétées du DOM
* les requêtes réseau

Les thèmes devraient améliorer la présentation plutôt que devenir un goulot d'étranglement des performances.

---

## 88. Flux de développement

Dans la mesure du possible, un nouveau thème devrait être développé indépendamment des changements du backend.

Flux recommandé :

```text id="1i8qz6"
Design
   ↓
Frontend implementation
   ↓
Theme selector integration
   ↓
Accessibility review
   ↓
Functional testing
   ↓
RBAC testing
   ↓
Fallback testing
   ↓
Performance review
   ↓
Documentation
```

Les changements du backend ne devraient être introduits qu'en présence d'un véritable besoin applicatif.

Un thème visuel ne devrait normalement pas nécessiter de modifications du backend.

---

## 89. Règles de développement

Lors du développement d'un thème :

1. Réutilisez les composants LUMS existants.
2. Évitez de dupliquer les pages.
3. Isolez les styles propres au thème.
4. Séparez le JavaScript décoratif de la logique opérationnelle.
5. N'introduisez pas de logique d'authentification.
6. N'introduisez pas de logique d'autorisation.
7. N'exposez aucun secret.
8. Préservez l'accessibilité.
9. Préservez le comportement de réduction des animations.
10. Testez tous les rôles pertinents.
11. Testez le repli vers le thème standard.
12. Documentez les nouvelles ressources et leur comportement.

---

## 90. Vérification des modifications

Avant de considérer un changement de thème comme terminé, vérifiez la présentation et les fonctionnalités.

Séquence de validation utile :

```text id="i1v9yb"
Theme changed
      │
      ▼
Visual inspection
      │
      ▼
Page functionality
      │
      ▼
Role behavior
      │
      ▼
API behavior
      │
      ▼
Browser console
      │
      ▼
Regression tests
```

Un thème n'est pas terminé simplement parce qu'il semble correct.

Il doit également laisser le comportement de LUMS inchangé.

---

## 91. Principe de non-régression

Le développement des thèmes devrait suivre le même principe général que les autres changements de LUMS :

> **Modifier → Tester → Vérifier → Documenter**

Un changement visuel peut néanmoins provoquer des régressions fonctionnelles.

Par exemple :

* boutons masqués
* texte illisible
* mise en page défectueuse
* commandes inaccessibles
* conflits JavaScript
* ressources manquantes
* sélecteurs incorrects
* problèmes de mise en page mobile

Les tests font donc partie du développement des thèmes et ne constituent pas une dernière étape facultative.

---

## 92. Dépannage : le thème ne se charge pas

Si le thème sélectionné ne s'affiche pas :

1. Rechargez la page.
2. Vérifiez si le thème standard se charge.
3. Consultez la console du navigateur.
4. Vérifiez si l'identifiant du thème sélectionné est valide.
5. Vérifiez si les ressources nécessaires au thème sont disponibles.
6. Recherchez les erreurs JavaScript.
7. Si nécessaire, effacez la préférence locale du thème.
8. Rechargez la page et vérifiez le retour au thème standard.

Ne modifiez pas la configuration de sécurité du backend pour résoudre un problème de thème frontend.

---

## 93. Dépannage : le thème déforme la mise en page

Si un thème provoque des problèmes de mise en page :

1. Passez au thème LUMS standard.
2. Confirmez que l'interface commune fonctionne.
3. Identifiez le composant touché.
4. Examinez le CSS propre au thème.
5. Vérifiez le comportement adaptatif.
6. Recherchez les erreurs dans la console du navigateur.
7. Corrigez les styles propres au thème.
8. Testez à nouveau les autres thèmes.

Le thème standard fournit une comparaison utile au diagnostic.

---

## 94. Dépannage : le thème provoque des erreurs JavaScript

Si le JavaScript propre au thème provoque des erreurs :

1. Passez au thème standard.
2. Confirmez le fonctionnement normal de LUMS.
3. Identifiez le script du thème en échec.
4. Déterminez si l'erreur est décorative ou liée à l'application.
5. Corrigez le problème propre au thème.
6. Vérifiez que le JavaScript commun de LUMS n'est pas affecté.
7. Testez à nouveau le changement de thème.

Il ne faut pas modifier le JavaScript opérationnel simplement pour compenser une erreur décorative du thème.

---

## 95. Dépannage : la préférence de thème est invalide

Si un ancien thème ou un thème invalide est encore enregistré localement :

```text id="b9n8wq"
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

La solution à privilégier est un repli sûr plutôt qu'une intervention manuelle sur le backend.

---

## 96. Documentation des thèmes

Pour chaque nouveau thème, documentez :

* l'identifiant interne
* le nom affiché
* le concept visuel
* les ressources nécessaires
* les effets visuels facultatifs
* les considérations d'accessibilité
* le comportement de réduction des animations
* les limites connues

La documentation propre à l'implémentation devrait décrire le code réellement présent, et non reposer sur des suppositions quant au fonctionnement possible du thème.

---

## 97. Ensemble actuel de thèmes

Les concepts de thèmes actuellement documentés sont :

```text id="r0w4u5"
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

L'ensemble de thèmes peut être étendu.

D'autres thèmes peuvent être ajoutés sans modifier l'architecture sous-jacente de LUMS, à condition de préserver la séparation entre la présentation et le comportement de l'application.

---

## 98. Principe de développement

Le système de thèmes facultatif devrait rester une extension contrôlée du frontend.

Il vise à rendre LUMS plus expressif et adaptable sans compliquer son exploitation.

L'architecture à privilégier est donc :

```text id="l2e8o9"
Common LUMS
     │
     ├── Common functionality
     ├── Common security
     ├── Common backend
     └── Common application state
              │
              ▼
       Optional Theme Layer
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
    Theme A Theme B Theme C
```

L'application commune reste la fondation.

Les thèmes restent des extensions facultatives.

# LUMS — Système de thèmes facultatifs

## Partie 6 — Maintenance, extension et état final

## 99. Maintenance des thèmes

Dans la mesure du possible, la maintenance des thèmes devrait rester distincte de celle du cœur de LUMS.

Une mise à jour visuelle d'un thème ne devrait normalement concerner que les ressources du frontend.

Les changements habituels comprennent :

* ajustements CSS
* ressources visuelles
* JavaScript propre au thème
* améliorations de l'accessibilité
* corrections de mise en page adaptative
* ajustements des animations
* changements de nom ou de présentation du thème

Une mise à jour de thème ne devrait pas nécessiter de modifications :

* de la configuration des clients
* des tokens clients
* du schéma de base de données
* des jobs de mise à jour
* de la logique de gestion des paquets
* de l'authentification
* du RBAC
* des contrôles de sécurité côté serveur

Si une modification du thème exige de façon inattendue de telles modifications, cette dépendance devrait être examinée avant de poursuivre.

---

## 100. Mises à jour des thèmes

Les mises à jour des thèmes devraient suivre le processus normal de développement de LUMS :

```text id="2p7z9r"
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

Pour les changements plus importants :

```text id="p7l5me"
Design
   ↓
Implementation
   ↓
Functional testing
   ↓
Accessibility testing
   ↓
RBAC regression testing
   ↓
Performance review
   ↓
Documentation
```

Un thème ne devrait pas être considéré comme terminé au seul motif que le résultat visuel semble correct.

---

## 101. Ajouter un nouveau thème

Il est possible d'introduire un nouveau thème sans modifier le backend LUMS.

Processus recommandé :

### Étape 1 — Définir le concept

Décrivez :

* l'identité visuelle
* le style visé
* la typographie
* les couleurs
* les éléments décoratifs
* les animations facultatives

### Étape 2 — Définir l'identifiant

Choisissez un identifiant interne stable.

### Étape 3 — Implémenter la présentation

Ajoutez les styles et les ressources nécessaires.

### Étape 4 — Intégrer la sélection

Rendez le thème disponible dans le sélecteur commun de thèmes.

### Étape 5 — Tester

Vérifiez :

* les pages normales
* les commandes interactives
* les mises en page adaptatives
* l'accessibilité
* la réduction des animations
* tous les rôles RBAC pertinents
* le comportement de repli

### Étape 6 — Documenter

Consignez le thème et les détails pertinents de son implémentation.

---

## 102. Supprimer un thème

La suppression d'un thème doit être traitée comme un changement de compatibilité pour les utilisateurs qui l'ont peut-être encore sélectionné localement.

Le frontend devrait donc traiter sans risque un identifiant obsolète :

```text id="x4e7p1"
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

La suppression d'une préférence côté navigateur ne doit jamais nécessiter une migration de base de données.

---

## 103. Renommer un thème

Le nom affiché peut généralement changer indépendamment de l'identifiant interne.

Par exemple :

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

Si l'identifiant interne lui-même change, une migration ou une correspondance de compatibilité peut être nécessaire pour les préférences locales existantes.

Dans la mesure du possible, il est préférable de conserver des identifiants stables.

---

## 104. Compatibilité des thèmes

Les thèmes devraient rester compatibles avec les changements de l'interface LUMS commune.

Lorsqu'un nouveau composant partagé est introduit, vérifiez que les thèmes existants ne présentent pas :

* de styles manquants
* d'espacements défectueux
* de texte illisible
* de couleurs incorrectes
* de comportement adaptatif manquant
* d'états de focus incorrects
* de commandes inaccessibles

Une nouvelle fonction du backend n'exige pas automatiquement une nouvelle fonctionnalité de thème.

L'application commune reste la source de référence.

---

## 105. Nouvelles fonctionnalités LUMS

Lorsqu'une nouvelle fonctionnalité est ajoutée à LUMS, la prise en charge des thèmes devrait normalement être évaluée après que la fonctionnalité commune est opérationnelle.

Séquence recommandée :

```text id="z4b7jx"
New LUMS feature
       │
       ▼
Common implementation
       │
       ▼
Functional tests
       │
       ▼
Theme compatibility
       │
       ▼
Theme-specific refinement
```

Cela évite que la personnalisation visuelle ne devienne une dépendance du développement des fonctionnalités essentielles.

---

## 106. Stabilité de l'API des thèmes

Le système de thèmes devrait éviter de créer une couche d'API distincte, sauf besoin réel.

Dans la mesure du possible, les thèmes devraient utiliser les mêmes mécanismes d'état applicatif du frontend et d'API que ceux déjà employés par LUMS.

Cela réduit :

* la duplication de la logique des requêtes
* la duplication de la gestion des erreurs
* les incohérences dans les hypothèses d'autorisation
* la maintenance supplémentaire
* la surface d'attaque inutile

Le système de thèmes est donc volontairement léger.

---

## 107. Revue de sécurité des thèmes

Lors de l'ajout ou d'une modification importante d'un thème, vérifiez les points suivants :

```text id="3eq4w6"
[ ] No credentials in assets
[ ] No client tokens in assets
[ ] No private keys
[ ] No authentication bypass
[ ] No authorization logic
[ ] No CSRF bypass
[ ] No direct security decisions
[ ] No unintended API endpoints
[ ] No sensitive information in frontend assets
[ ] Decorative scripts remain isolated
```

Cette revue doit être effectuée même si le changement semble purement visuel.

Le code frontend reste du code exécutable.

---

## 108. Revue d'accessibilité des thèmes

Pour chaque thème, vérifiez :

```text id="1y9xw6"
[ ] Text remains readable
[ ] Contrast remains sufficient
[ ] Focus states are visible
[ ] Keyboard navigation works
[ ] Controls remain usable
[ ] Statuses are not color-only
[ ] Reduced motion is respected
[ ] Responsive layout remains usable
[ ] Decorative effects do not obscure information
```

L'accessibilité devrait faire partie de la qualité d'un thème, et non être considérée comme une amélioration facultative.

---

## 109. Liste de vérification des régressions de thème

Avant d'accepter un changement de thème :

```text id="8j6x4e"
[ ] Standard theme works
[ ] Changed theme works
[ ] Other themes still work
[ ] Theme switching works
[ ] Stored preference works
[ ] Invalid preference falls back safely
[ ] Login works
[ ] Logout works
[ ] Client views work
[ ] Software views work
[ ] Update views work
[ ] Package-management views work
[ ] User-management views work where authorized
[ ] Job information remains readable
[ ] Error messages remain understandable
[ ] RBAC remains unchanged
[ ] Backend behavior remains unchanged
```

L'ensemble exact des fonctionnalités visibles pendant le test dépend du rôle de l'utilisateur.

---

## 110. Indépendance opérationnelle

Le système de thèmes facultatif est délibérément indépendant du cycle de vie opérationnel de LUMS.

Changer de thème ne doit pas nécessiter :

```text id="b2i1k4"
Agent restart
Watcher restart
Database restart
Client re-registration
Token rotation
Job cancellation
Package-manager changes
Network changes
```

La couche de présentation peut ainsi évoluer indépendamment de la couche d'infrastructure.

---

## 111. Indépendance du déploiement

Les ressources des thèmes font partie du frontend de l'application LUMS.

Les procédures générales de déploiement sont documentées dans la documentation principale d'installation et d'administration.

Ce document ne répète volontairement pas :

* les procédures de déploiement Docker
* les commandes de durcissement des conteneurs
* la configuration Nginx
* les procédures de sauvegarde de la base de données
* les procédures de récupération du serveur
* les procédures d'installation des clients

Ces sujets relèvent de la documentation opérationnelle appropriée.

Cette séparation évite que la documentation des thèmes ne devienne obsolète lorsque l'architecture de déploiement évolue.

---

## 112. Séparation entre source et environnement d'exécution

Le système de thèmes doit être considéré comme faisant partie du code source de l'application.

Il faut distinguer :

```text id="b6q7jv"
Source
   │
   ├── Theme definitions
   ├── CSS
   ├── JavaScript
   └── Assets

Runtime
   │
   ├── Built LUMS image
   └── Running LUMS application
```

Une modification d'un thème dans le code source ne signifie pas automatiquement qu'un déploiement déjà en cours d'exécution l'a reçue.

Le processus normal de construction et de déploiement de LUMS reste responsable de la livraison des ressources frontend mises à jour.

---

## 113. Versionnement

Les thèmes n'ont pas besoin d'introduire une version distincte du backend LUMS.

Un thème peut évoluer dans le cadre de la version frontend/de l'application.

Si une modification de thème entraîne des problèmes de compatibilité, ceux-ci devraient être explicitement documentés.

Par exemple :

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

La seconde catégorie nécessite des tests de non-régression supplémentaires.

---

## 114. Préparation à la release

Avant une release LUMS contenant des changements de thème, vérifiez :

```text id="v2h3f7"
Theme rendering
Theme selection
Theme fallback
Accessibility
Reduced motion
Responsive layout
RBAC behavior
API behavior
Security boundaries
Regression tests
Documentation
```

Les changements de thème ne doivent pas masquer les régressions de l'application essentielle.

---

## 115. Ensemble actuel de thèmes

Les concepts de thèmes actuellement documentés sont :

| Identifiant | Nom affiché | Concept |
| ------------- | ---------------- | --------------------------- |
| `standard` | LUMS standard | Interface de référence |
| `LUMSStadium` | Stade LUMS | Stade / événement |
| `golf` | Club de golf | Apaisant / récréatif |
| `nerd` | Mode nerd | Technique / ludique |
| `geek` | Laboratoire geek | Expérimental / technique |
| `admin` | Administration d'entreprise | Structuré / administratif |

Ces thèmes partagent la même application LUMS et le même backend.

Ce sont des variantes visuelles, et non des produits distincts ou des niveaux de permission.

---

## 116. État actuel

Le système de thèmes facultatif est une extension de l'architecture frontend de LUMS.

Ses propriétés prévues sont les suivantes :

```text id="2xq1w8"
[✓] Optional
[✓] Client-side presentation
[✓] Common backend
[✓] Common security model
[✓] Common RBAC model
[✓] Standard fallback
[✓] Theme-specific visual identity
[✓] Reduced-motion consideration
[✓] Accessibility consideration
[✓] No theme-based authorization
```

Les détails propres à l'implémentation devraient toujours être synchronisés avec le code source frontend actuel.

---

## 117. Extensions futures

Le système de thèmes peut évoluer dans plusieurs directions sans modifier l'architecture sous-jacente.

Parmi les ajouts futurs possibles :

* des thèmes supplémentaires
* des aperçus de thèmes améliorés
* des préférences visuelles plus granulaires
* des paramètres d'accessibilité supplémentaires
* un comportement adaptatif amélioré
* des mises en page de tableau de bord propres à chaque thème
* des visualisations facultatives supplémentaires

Ces extensions devraient continuer à respecter la même séparation entre la présentation et le comportement de l'application.

---

## 118. Architecture finale

Le concept complet peut se résumer ainsi :

```text id="x8j7z2"
                    LUMS
                     │
          ┌──────────┴──────────┐
          │                     │
     Application             Theme Layer
          │                     │
          │             ┌───────┼────────┐
          │             │       │        │
          │          Standard Stadium  Golf
          │
          │             Nerd   Geek   Admin
          │
          └──────────────┬──────────────┘
                         │
                         ▼
                  Common Backend
                         │
             ┌───────────┼───────────┐
             │           │           │
          Security      Jobs       Clients
             │           │           │
             └───────────┼───────────┘
                         ▼
                      SQLite
```

La couche visuelle reste facultative.

La couche applicative reste l'autorité.

La couche de sécurité reste indépendante.

---

## 119. Principe final

Le système de thèmes facultatif vise à rendre LUMS plus personnel, expressif et adaptable sans compromettre l'architecture technique.

La règle fondamentale reste :

> **Un LUMS · Plusieurs interfaces · Le même backend**

Un thème peut changer l'atmosphère de LUMS.

Il ne doit jamais changer ce que LUMS est réellement autorisé à faire.
