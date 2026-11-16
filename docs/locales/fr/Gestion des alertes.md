# Gestion des alertes LUMS : implémentation actuelle

Cette note décrit le code de gestion des alertes actuellement présent dans LUMS. Il s'agit d'une référence au code, et non d'une feuille de route fonctionnelle ni d'une garantie que chaque commande visible est opérationnelle. L'implémentation est principalement située dans `server/alerts.py` et `server/alerts_routes.py`.

## Fonctions implémentées

LUMS conserve dans SQLite les règles d'alerte, les enregistrements d'alerte et l'historique des états d'alerte. Le blueprint Flask crée un `AlertManager` propre à chaque requête à l'aide de la fabrique de connexions à la base de données de l'application. À chaque requête, le gestionnaire charge depuis la base de données les règles et les alertes non résolues.

L'API actuelle permet de :

- répertorier, créer, modifier et supprimer des règles d'alerte ;
- déclencher manuellement une alerte pour une règle existante et activée ;
- consulter les alertes actives et l'historique paginé des alertes ;
- accuser réception d'une alerte active, la résoudre et la faire remonter manuellement.

Les niveaux de gravité des alertes sont `critical`, `warning` et `info`. Les états d'alerte enregistrés sont `triggered`, `acknowledged`, `resolved` et `escalated`. Les changements liés à l'accusé de réception, à la résolution et à l'escalade sont enregistrés dans `alert_history`. Les alertes résolues sont retirées de la collection des alertes actives du gestionnaire, mais restent dans la base de données.

## Limites importantes

Le modèle de règle enregistre une condition, un seuil, un niveau de gravité, un chemin d'escalade ainsi que des indicateurs de regroupement et de déduplication. Le serveur actuel **n'évalue pas les conditions à partir de la télémétrie ni d'autres mesures**. Une règle ne se déclenche pas automatiquement : un appelant authentifié doit invoquer `POST /alerts/trigger`. Lorsqu'une alerte est déclenchée, le gestionnaire tente de l'envoyer aux fournisseurs nommés dans le chemin d'escalade de la règle. Toutefois, l'application web crée chaque gestionnaire avec une table de fournisseurs vide et ses points de terminaison d'intégration ne peuvent pas configurer de fournisseurs ; les alertes déclenchées par l'application ne donnent donc actuellement lieu à aucune livraison de notification. Le regroupement et la déduplication sont uniquement enregistrés, et ne sont pas appliqués.

`AlertManager` définit des classes de fournisseurs pour le courrier électronique, Slack, PagerDuty et les webhooks génériques, mais ces classes ne sont pas configurées par l'application. L'API d'intégration indique explicitement que les intégrations ne sont pas disponibles et renvoie `501 Not Implemented` aux demandes de configuration, de test et de suppression. Aucune livraison de notifications n'est à attendre. `POST /alerts/clear-all` renvoie également `501` afin que l'historique des alertes ne puisse pas être supprimé par ce point de terminaison.

La page `/alerts/` est une vue d'ensemble simple rendue côté serveur. Les commandes des onglets des règles, de l'historique et des intégrations ainsi que les boutons d'action des alertes ne constituent pas une interface de gestion interactive complète. Le comportement documenté de l'API est la référence ; ne pas supposer qu'un bouton visible exécute une action. L'implémentation actuelle ne fournit ni mises à jour en temps réel par push ni mises à jour WebSocket.

## Routes et contrôle d'accès

Toutes les routes exigent une session web authentifiée.

| Méthode | Route | Permission | Comportement actuel |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Affiche la vue simple des alertes |
| `GET` | `/alerts/rules` | `alerts.view` | Répertorie les règles enregistrées |
| `POST` | `/alerts/rules` | `alerts.manage` | Crée une règle validée |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Modifie une règle enregistrée |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Supprime une règle si les contraintes de la base de données le permettent |
| `GET` | `/alerts/current` | `alerts.view` | Renvoie les alertes actives |
| `GET` | `/alerts/history` | `alerts.view` | Renvoie l'historique des alertes |
| `POST` | `/alerts/trigger` | `alerts.manage` | Crée manuellement une alerte pour une règle activée |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Enregistre un accusé de réception |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Résout une alerte active |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Incrémente manuellement son compteur d'escalade |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Désactivé ; renvoie `501` |
| `GET` | `/alerts/integrations` | `alerts.view` | Renvoie une liste vide et `available: false` |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Désactivé ; renvoie `501` |

Les routes qui modifient des données exigent la protection CSRF ainsi que la permission correspondante. Les vérifications de permissions sont appliquées côté serveur. `alerts.manage` dépend de `alerts.view` ; les attributions de rôles sont gérées par la migration de sécurité et la configuration des permissions.

## Tables persistantes

`AlertManager` initialise les tables suivantes lors de sa création :

- `alert_rules` : définitions des règles et valeurs configurées ;
- `alerts` : enregistrements d'alerte et état actuel du cycle de vie ;
- `alert_history` : historique des accusés de réception, résolutions et escalades ;
- `notification_integrations` : schéma réservé à la configuration des intégrations ;
- `alert_notifications_log` : schéma réservé au journal des livraisons.

La présence des deux dernières tables ne signifie pas que les intégrations sont disponibles. Les points de terminaison HTTP des intégrations restent désactivés tant qu'une configuration persistante sécurisée et un mécanisme de livraison ne sont pas implémentés.

## Vérification

Les routes d'alerte, l'application des permissions, la validation des charges utiles, la persistance et le cycle de vie sont couverts par `tests/test_alerts.py`. Relancer les tests pertinents sur la révision à déployer. Une suite de tests réussie ne rend pas disponibles les routes d'intégration désactivées ni les règles non évaluées.

## Code associé

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
