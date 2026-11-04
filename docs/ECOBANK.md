# Intégration API Ecobank

Ce document décrit **exactement** ce qui est implémenté, ce qui provient de la
documentation officielle et ce qui doit être validé lors de votre onboarding.

> Aucun endpoint, paramètre ou mécanisme d'authentification n'a été inventé. Les URL et
> noms de champs ci-dessous proviennent de la documentation *Account Enquiry Service —
> Get Account Balance* d'Ecobank et du comportement observé de la passerelle UAT.

---

## 1. Endpoints utilisés

| Fonction | Méthode | URL |
|----------|---------|-----|
| Authentification (jeton) | `POST` | `https://apimuat-gateway.ecobank.com/corp-auth/api/v2/integration/auth/app/token` |
| Solde de compte | `POST` | `https://apimuat-gateway.ecobank.com/corp-account-inquiry/api/v2/integration/account/inquiry/balance` |
| *(URL de base alternative documentée)* | — | `https://artxuat.ecobank.com/corp-api/services/...` (même service, autre adresse) |

- `apimuat-developer.ecobank.com` est le **portail** de documentation, pas une API.
- L'URL de base, les chemins, le `ServiceCode`, les `requestType` et le timeout sont
  **configurables** dans l'espace administrateur : les environnements Sandbox et
  Production diffèrent et votre contrat peut préciser d'autres valeurs.
- Le service d'authentification et le service de compte sont deux passerelles distinctes :
  le jeton est demandé avec `ServiceCode = ACCOUNT_SERVICE` (spécification de la
  documentation Account Enquiry).

---

## 2. En-têtes et double authentification

Chaque appel porte **deux** justificatifs indépendants :

```http
Content-Type: application/json
Accept: application/json
Cache-Control: no-cache
Ocp-Apim-Subscription-Key: <clé d'abonnement du portail>
Authorization: Bearer <jeton obtenu pour ACCOUNT_SERVICE>
```

- Une clé d'abonnement erronée renvoie **HTTP 401**.
- Une signature erronée renvoie souvent **HTTP 200** avec un code d'erreur dans le corps :
  la décision se lit dans `headerResponse.responseCode`, pas dans le statut HTTP.

---

## 3. Signature (`requestToken` et `secureHash`)

Algorithme **SHA-512**, hexadécimal minuscule, 128 caractères. Ce n'est **pas** un HMAC :
le secret est concaténé puis l'ensemble est haché.

```text
HEADER       = clientId + affiliateCode + sourceCode + requestId + requestType + ipAddress
requestToken = SHA512(HEADER + secretKey)
secureHash   = SHA512(HEADER + requestToken + <champs de l'endpoint> + secretKey)
```

| Appel | Champs de l'endpoint |
|-------|----------------------|
| Jeton | `publicKey`, `serviceCode` |
| Solde | `accountNo` |

Points sensibles (source d'échecs les plus fréquents) :

1. `requestToken` doit être calculé **avant** `secureHash` puis inséré dedans.
2. L'ordre haché n'est pas l'ordre JSON : le hachage commence par `clientId` alors que
   le corps commence par `affiliateCode`.
3. `affiliateCode` (ex. `ECD` pour la RDC) et `clientId` sont **distincts**.

L'implémentation se trouve dans `backend/apps/banking/ecobank_client.py`
(`build_signatures`, `sha512_hex`) et est couverte par des tests à vecteurs connus.

> ⚠️ **À valider avec Ecobank lors de votre onboarding** : la documentation publique ne
> détaille pas l'algorithme de `secureHash` / `requestToken`. L'implémentation suit le
> protocole documenté du même service (ordre des champs, concaténation du secret) tel
> qu'observé sur la passerelle. Le bouton **Tester la connexion** permet de confirmer
> immédiatement les identifiants et la signature avec vos vraies valeurs : un message
> `Invalid SecureHash or Request Token Provided` indique une signature à revoir.

---

## 4. Corps des requêtes

### 4.1 Jeton

```json
{
  "headerRequest": {
    "affiliateCode": "ECD",
    "clientId": "VOTRE_CLIENT_ID",
    "sourceCode": "VOTRE_SOURCE_CODE",
    "requestId": "A1B2C3D4E5F6",
    "ipAddress": "203.0.113.10",
    "requestType": "GET_API_TOKEN",
    "requestToken": "<128 hex>"
  },
  "publicKey": "corp_pk_...",
  "serviceCode": "ACCOUNT_SERVICE",
  "secureHash": "<128 hex>"
}
```

Réponse : `data.access_token` ; `expires_in` est observé comme un **horodatage absolu en
millisecondes** (durée réelle ~5 h). L'application gère les deux formes et met le jeton en
cache chiffré, par service et par identité.

### 4.2 Solde

```json
{
  "headerRequest": {
    "affiliateCode": "ECD",
    "clientId": "VOTRE_CLIENT_ID",
    "sourceCode": "VOTRE_SOURCE_CODE",
    "requestId": "A1B2C3D4E5F6",
    "ipAddress": "203.0.113.10",
    "requestType": "GET_ACCOUNT_BALANCE",
    "requestToken": "<128 hex>"
  },
  "secureHash": "<128 hex>",
  "accountNo": "1441002006858"
}
```

Réponse exploitable :

```json
{
  "headerResponse": { "responseCode": "000", "responseMessage": "SUCCESS", "responseDesc": "..." },
  "data": {
    "accountNo": "...",
    "accountName": "...",
    "ccy": "USD",
    "availableBalance": 80.17,
    "currentBalance": 80.17,
    "accountStatus": "ACTIVE",
    "branchCode": "H26"
  }
}
```

Champs mappés : `availableBalance` → *solde disponible*, `currentBalance` → *solde
comptable*, `ccy` → devise, `accountName`, `accountStatus`, `branchCode`.
Les valeurs sont converties en `Decimal` (jamais en flottant) via `to_decimal()`.

---

## 5. Codes et messages

| Code | Signification | Traitement applicatif |
|------|---------------|-----------------------|
| `000` | Succès (seul code de succès) | enregistrement du relevé |
| `400` | Requête mal formée | message d'erreur du journal de sync |
| `401` | Authentification échouée (signature) | statut `FAILED`, message explicite |
| `403` | Jeton refusé / expiré | **renouvellement du jeton + un nouvel essai** |
| `404` | Introuvable | statut `FAILED` |
| `999` | Refus (signature, clé, service, affilié…) | `responseDesc` conservé pour diagnostic |

Messages `responseDesc` fréquents : `Invalid SecureHash or Request Token Provided`,
`Invalid Key Provided`, `Client App not Configured for Service`,
`No services has been setup for the client X`, `No app has been setup for the client with code X`.

---

## 6. Configuration dans l'application

Espace **Administrateur → Configuration Ecobank** :

| Champ | Rôle |
|-------|------|
| Environnement | Sandbox (UAT) / Production — une URL UAT est refusée en Production |
| URL de l'API | HTTPS obligatoire |
| Chemin jeton / Chemin solde | valeurs par défaut documentées, modifiables |
| Client ID, Affiliate Code, Source Code | identifiants partenaires |
| Public Key | transmis dans le corps du jeton |
| Secret Key | **chiffré au repos**, jamais renvoyé |
| Subscription Key | **chiffrée au repos**, en-tête `Ocp-Apim-Subscription-Key` |
| Numéro de compte | **chiffré**, affiché masqué |
| IP déclarée | IP publique du serveur (whitelistée par Ecobank) |
| Service Code | `ACCOUNT_SERVICE` par défaut |
| Request types | `GET_API_TOKEN` / `GET_ACCOUNT_BALANCE` |
| Timeout | 5 à 120 s |
| Fréquence | intervalle de synchronisation automatique (minutes) |
| Mode sandbox | démonstration explicite, désactivé par défaut |

Boutons : **Tester la connexion** (jeton uniquement, sans lire le solde),
**Synchroniser** (lecture réelle), **Supprimer les identifiants**.

---

## 7. Synchronisation

- `bank-sync-worker` (conteneur dédié) synchronise à intervalle configurable.
- Synchronisation manuelle réservée à l'administrateur (throttle 6/min).
- Un verrou base (`select_for_update`) empêche deux synchronisations concurrentes.
- L'intervalle est respecté pour les synchronisations planifiées (pas d'appels excessifs).
- Chaque tentative produit une entrée `SyncLog` (déclencheur, statut, HTTP, code, message, durée).
- Chaque succès produit un `BalanceSnapshot` **immuable** (historique et graphiques).
- En cas d'échec : **aucun relevé n'est créé**, le dernier solde connu reste affiché,
  l'erreur est journalisée et notifiée dans l'interface.

---

## 8. Mode sandbox de démonstration

Sans identifiants réels, l'administrateur peut activer *Mode démonstration sandbox*.
Dans ce cas :

- le solde retourné est **simulé**, `source = SANDBOX`, `is_sandbox = true` ;
- un bandeau d'avertissement s'affiche sur le tableau de bord, la page banque et la config ;
- l'écart financier/bancaire est marqué **non calculable** (les données simulées sont
  exclues du calcul) ;
- aucun message ne présente ce solde comme un solde bancaire réel.

Désactivé par défaut : sans configuration, le solde bancaire vaut `—`.

---

## 9. Vérifier l'intégration

1. Saisir les identifiants fournis par Ecobank.
2. **Tester la connexion** → doit afficher « Authentification Ecobank réussie (jeton obtenu) ».
3. **Synchroniser** → le solde réel apparaît avec l'heure de synchronisation.
4. Vérifier la correspondance avec le relevé bancaire.

### Dépannage

| Message | Piste |
|---------|-------|
| `Invalid SecureHash or Request Token Provided` | ordre des champs / secret / public key |
| `Invalid Key Provided` | `publicKey` incorrect |
| `Client App not Configured for Service` | `ServiceCode` non activé pour votre app |
| `No services has been setup for the client X` | couple `clientId` / `affiliateCode` |
| `No app has been setup for the client with code X` | `sourceCode` incorrect |
| `Accès refusé par la passerelle (401)` | clé d'abonnement absente ou invalide |
| `Impossible de joindre l'API` | réseau sortant, URL, DNS, IP non whitelistée |
| `Délai dépassé` | timeout trop court / réseau lent (augmenter, max 120 s) |

Le sandbox UAT peut ne pas valider la signature : un succès en UAT ne prouve pas que la
signature est correcte en production. Validez avec votre environnement réel.

---

## 10. Références

- Portail développeur : `https://apimuat-developer.ecobank.com`
- Documentation : *Account Enquiry Service → Get Account Balance*
- Support sandbox : `EcobankSandboxSupport@ecobank.com`
- Licence API : Apache 2.0
