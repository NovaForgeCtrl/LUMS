# Package téléchargeable d’outils de mise à jour

Après la réussite du workflow `Tests` sur `main`, le workflow `Updater package`
crée un artefact `lums-update-tools-<commit>.tar.gz` et une somme de contrôle
SHA-256. Téléchargez-le dans la section **Artifacts** de l’exécution réussie de
ce workflow ; les artefacts de build sont conservés pendant 90 jours.

Lorsqu’une GitHub Release est publiée, le workflow exécute la suite de tests
sur la balise publiée avant de joindre l’archive de mise à jour et une archive
source déterministe. L’archive source comprend sa somme de contrôle SHA-256 et
l’identifiant du commit testé ; l’Update Center ne répertorie les versions
qu’une fois les trois éléments de vérification de la source disponibles.

Le bundle d’outils de mise à jour est un téléchargement pratique, pas un
paquet Debian. L’archive source n’est pas installée directement par le
conteneur web. Ne l’utilisez pas pour mettre à jour la production avant qu’un
outil de mise à jour hôte installé séparément ait réussi les contrôles de
déploiement et vérifié à la fois la sauvegarde de la base de données et le
comportement de retour arrière pour ce déploiement précis.

[Documentation source en anglais](../../update-tools-package.md).
