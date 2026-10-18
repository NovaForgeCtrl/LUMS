# Démarrage rapide de LUMS — Français

Ce guide concis s’adresse aux personnes qui découvrent LUMS ou Linux. Il ne
traduit pas intégralement tous les manuels techniques, maintenus en anglais.
[Index des langues](../../README.md).

## Qu’est-ce que LUMS ?

LUMS gère les ordinateurs Linux de manière centralisée. Le serveur affiche les
clients, les logiciels installés et les mises à jour disponibles. Un agent sur
chaque client exécute les actions approuvées avec le gestionnaire de paquets
du système : APT sur Debian/Ubuntu et pacman sur Arch Linux. LUMS n’installe
pas automatiquement toutes les mises à jour.

## Si vous utilisez seulement LUMS

Ouvrez l’adresse Web fournie par votre administrateur et connectez-vous avec
votre propre compte. Les actions disponibles dépendent de vos permissions. Ne
partagez ni votre compte ni un jeton client. Choisissez une langue en haut à
droite de la page de connexion ; après connexion, LUMS peut enregistrer ce
choix dans votre compte.

## Installation et exploitation

Un test ne constitue pas un serveur de production. Une installation sécurisée
nécessite notamment HTTPS, un secret applicatif protégé, un stockage persistant
de la base de données et des sauvegardes vérifiées. Le serveur et les clients
Linux se configurent séparément. Suivez attentivement le
[guide d’installation](../../../install.md). Remplacez les valeurs fictives,
comme `LUMS-SERVER`, et vérifiez chaque chemin avant d’exécuter une commande.
Si LUMS fonctionne déjà, suivez la procédure de mise à niveau du
[guide d’administration](../../../administration.md), pas celle de première
installation.

Lors d’une mise à niveau normale, ne supprimez jamais le volume Docker
`lums-data` : il contient la base de données. Conservez les montages du secret
et des sauvegardes ainsi que les options de sécurité du conteneur. Les exemples
ne sont pas universels ; comparez-les d’abord au conteneur en cours
d’exécution.

## Premières vérifications en cas de problème

Sur le serveur, ces commandes affichent l’état du conteneur, les journaux
récents de l’application et l’état de Nginx :

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` peut demander votre mot de passe Linux. Ces vérifications ne modifient
pas la configuration. Ne supprimez pas la base de données ou le volume Docker,
ne lancez pas le conteneur en mode privilégié et ne désactivez pas les
protections comme première tentative. Avant de partager des journaux,
supprimez les mots de passe, jetons, clés et données personnelles.

## Documentation détaillée

* [Présentation du projet](Présentation%20du%20projet.md)
* [Installation et mises à niveau](../../../install.md)
* [Administration et sauvegardes](../../../administration.md)
* [Dépannage](../../../troubleshooting.md)
* [Modèle de sécurité](../../../security.md)
