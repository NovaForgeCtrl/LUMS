# Contexte produit de LUMS

## Plateforme

Application web

## Utilisateurs

Administrateurs système Linux et équipes informatiques chargés de gérer et de maintenir à jour de manière centralisée plusieurs systèmes Linux. Le produit doit également convenir à un administrateur seul, à une petite équipe informatique et aux environnements de services gérés adaptés.

## Objectif du produit

LUMS fournit une vue centrale des clients gérés, des logiciels installés, des mises à jour disponibles et de l'exécution des jobs de mise à jour. Il aide les administrateurs à lancer délibérément des opérations et à en vérifier le résultat, plutôt qu'à appliquer aveuglément des mises à jour sur tous les systèmes.

## Contexte opérationnel

Au quotidien, les administrateurs utilisent LUMS pour examiner l'état du parc, la télémétrie, les logiciels et les mises à jour, lancer des jobs de mise à jour ciblés, consulter l'historique d'exécution et gérer les accès des utilisateurs, les enregistrements d'audit et les sauvegardes de la base de données. La topologie de l'infrastructure peut associer des clients LUMS enregistrés à des systèmes et relations gérés manuellement.

## Capacités et contraintes

- Le contrôle d'accès fondé sur les rôles et les permissions, la journalisation d'audit, la sauvegarde de la base de données, la visibilité des paquets et les jobs de mise à jour des clients font partie des capacités opérationnelles essentielles.
- Les mises à jour système doivent être contrôlées, auditables et signaler honnêtement les échecs ; ne pas laisser entendre qu'une mise à jour a réussi tant que ses vérifications ne sont pas concluantes.
- Les clients enregistrés et les données qu'ils rapportent constituent la source disponible pour l'importation automatique de l'inventaire de l'infrastructure. Toute autre infrastructure et relation doit être ajoutée explicitement et manuellement, sauf si une intégration future est confirmée.
- La modification de l'inventaire de l'infrastructure est réservée aux administrateurs.
- Ne pas prétendre qu'une découverte automatique de machines virtuelles, de conteneurs, de périphériques réseau ou de dépendances quelconques est disponible.

## Engagements de marque

- Conserver le nom LUMS et le logo existant.
- L'utilisateur désigne explicitement le thème du stade par « LUMS-Stadion » et a demandé l'utilisation de son image de fond du stade existante sur le tableau de bord de l'état du système et dans la surveillance en direct.

## Éléments disponibles

- Interface produit et ressources de thème existantes : `server/static/style.css`, `server/static/images/LUMS_Logo.jpg` et `server/static/images/lumsstadium.jpg`.
- Les implémentations existantes pour les clients enregistrés, la télémétrie, les jobs de mise à jour, le RBAC, l'audit et les sauvegardes se trouvent dans le package `server/`.
- Aucune affirmation vérifiée de clients, aucun benchmark produit ni aucune intégration de découverte automatique de l'infrastructure n'ont été fournis.

## Principes du produit

- Laisser aux administrateurs le contrôle des modifications système.
- Rendre l'état opérationnel et les résultats des mises à jour vérifiables.
- Appliquer les règles d'accès côté serveur, pas seulement dans l'interface.
- Distinguer les faits rapportés par les clients de l'inventaire maintenu manuellement.
