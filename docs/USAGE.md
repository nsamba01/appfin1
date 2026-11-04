# Guide d'utilisation

Deux rôles, deux espaces. L'interface s'adapte automatiquement au rôle : un financier
ne voit aucun élément d'administration.

---

## 1. Se connecter

1. Ouvrir l'application (`http://localhost:8080` en local).
2. Saisir l'identifiant et le mot de passe.
3. À la **première connexion** (ou après une réinitialisation par l'administrateur),
   l'écran de changement de mot de passe s'impose : 10 caractères minimum, majuscule,
   minuscule, chiffre, caractère spécial, différent de l'ancien.
4. Après validation, se reconnecter avec le nouveau mot de passe.

Sécurité de connexion :
- 5 échecs consécutifs → compte verrouillé 15 minutes ;
- toutes les tentatives (réussies ou non) sont journalisées avec l'adresse IP ;
- la session expire automatiquement (jeton d'accès 15 min, rafraîchissement silencieux,
  refresh 8 h) ; un changement de mot de passe révoque immédiatement toutes les sessions.

---

## 2. Espace financier

### 2.1 Tableau de bord (page d'accueil)

- **Cartes** : solde financier interne, solde Ecobank, total des entrées, total des
  sorties, balance financière, écart financier/bancaire, mouvements non rapprochés.
- **Comparaison** : tableau « indicateurs / situation financière / situation bancaire »
  avec la date de mise à jour de chaque source.
- **Écart** = solde financier interne − solde bancaire Ecobank :
  - `0` → badge vert « soldes identiques » ;
  - `> 0` → badge ambre « solde financier supérieur » ;
  - `< 0` → badge rouge « solde bancaire supérieur » ;
  - pas de solde bancaire réel → « comparaison indisponible ».
- **Graphiques** : soldes comparés, évolution des entrées/sorties, évolution du solde,
  historique des soldes bancaires, graphique des écarts.
- **Filtres de période** en haut à droite.
- **Mouvements non rapprochés** : opérations internes enregistrées après la dernière
  synchronisation bancaire. Ils ne sont **jamais** assimilés au relevé bancaire.

### 2.2 Opérations

- **Nouvelle opération** : date, libellé, montant, type (Entrée/Sortie), référence et
  observation facultatives.
- **Recherche** par libellé, référence, observation ; **filtres** type + période ;
  **pagination**.
- **Modifier** une opération (icône crayon) — chaque champ modifié est historisé.
- **Archiver** (icône corbeille) : confirmation obligatoire, l'opération quitte les
  soldes mais reste dans le journal d'audit.
- **Historique** : cliquer sur le libellé pour voir la chronologie complète.
- **Export** : boutons *Excel* et *PDF* — l'export reprend les filtres actifs.

Règles métier (paramétrables par l'administrateur) : autorisation de modification,
autorisation d'archivage, fenêtre de modification en jours.

### 2.3 Balances

Totaux des entrées/sorties, solde disponible, balance, détail mensuel et graphique
d'évolution. Tous les montants sont calculés par le serveur.

### 2.4 Compte Ecobank (lecture seule)

- Nom de la banque, numéro de compte **masqué**, titulaire, devise.
- Solde disponible, solde comptable (si fourni), statut du compte.
- Date et heure de la dernière synchronisation, état de connexion, dernier message.
- Historique des soldes (90 jours) et tableau des dernières synchronisations.
- Si le mode sandbox est actif : bandeau d'avertissement permanent — le solde est
  **simulé** et exclu du calcul de l'écart.

Le financier ne peut ni modifier la configuration, ni déclencher de synchronisation.

### 2.5 Historique financier

Chronologie de tous les évènements liés aux opérations (création, modification,
archivage, export), avec auteur, date et adresse IP.

---

## 3. Espace administrateur

### 3.1 Utilisateurs

- **Créer** : identifiant, nom complet, email, rôle, mot de passe initial, option
  « forcer le changement ».
- **Modifier** : nom, email, rôle, statut.
- **Réinitialiser le mot de passe** : nouveau mot de passe haché, changement forcé
  possible, sessions existantes révoquées.
- **Désactiver / réactiver** : un compte désactivé perd immédiatement l'accès.
- **Déverrouiller** un compte bloqué par des échecs de connexion.
- **Dernière connexion** et IP affichées pour chaque compte.

Garde-fous : impossible de se désactiver soi-même, impossible de retirer le dernier
administrateur actif, les comptes ne sont jamais supprimés définitivement (conservation
de l'audit).

### 3.2 Configuration Ecobank

Voir [ECOBANK.md](ECOBANK.md). Champs : environnement, URL, chemins, Client ID,
Affiliate Code, Source Code, Public Key, Secret Key, Subscription Key, numéro de compte,
IP déclarée, Service Code, timeouts, fréquence de synchronisation, mode sandbox.

Boutons : **Enregistrer**, **Tester la connexion**, **Synchroniser**, **Supprimer les
identifiants**. Le journal de synchronisation affiche chaque tentative avec son code
HTTP, son message et sa durée.

### 3.3 Journaux & audit

- **Journal d'audit** : toutes les actions sensibles, filtrables par action et par acteur.
- **Connexions** : succès/échecs, IP, motif, agent utilisateur.
- Statistiques rapides (échecs récents, IP distinctes).

### 3.4 Paramètres généraux

Nom de l'organisation, devise, fuseau horaire, règles métier des financiers, fréquence
de synchronisation. Chaque modification est auditée.

---

## 4. Bonnes pratiques

1. Changer immédiatement les mots de passe initiaux.
2. Un compte par personne — jamais de compte partagé (traçabilité).
3. Désactiver un compte plutôt que le laisser inactif.
4. Vérifier régulièrement le journal d'audit et les échecs de connexion.
5. Ne jamais saisir d'identifiants bancaires ailleurs que dans l'espace admin.
6. Contrôler l'écart financier/bancaire : un écart persistant signale des mouvements
   internes non encore constatés en banque.
