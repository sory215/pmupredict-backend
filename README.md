# pmupredict — Applications natives (Android, Windows, macOS)

Ce dossier contient de quoi générer une application native de
pmupredict pour trois plateformes, en gardant exactement l'apparence
de votre frontend web déjà déployé sur Vercel.

## Principe

Chaque app native n'est qu'une **fenêtre système sans barre
d'adresse** qui charge votre site déployé (`https://votre-app.vercel.app`).
Aucune réécriture du frontend n'est nécessaire — c'est la solution la
plus rapide pour un usage personnel.

## Contenu

| Dossier | Plateforme | Fichier généré |
|---|---|---|
| `pmupredict-android-capacitor/` | Android | `.apk` |
| `pmupredict-desktop-tauri/` | Windows et macOS | `.exe` / `.dmg` |

Chaque dossier a son propre `README.md` avec les étapes détaillées.

## Avant toute chose

1. Votre frontend doit déjà être déployé et accessible publiquement
   (voir `pmupredict-VERCEL.zip` livré précédemment).
2. Dans **chacun** des deux dossiers, remplacer l'URL de démonstration
   (`REMPLACER-PAR-VOTRE-URL.vercel.app`) par l'URL réelle :
   - `pmupredict-android-capacitor/capacitor.config.json`
   - `pmupredict-desktop-tauri/dist/index.html`

## Ce qu'il faut savoir avant de se lancer

- **Android** : nécessite Android Studio installé (gratuit), génère un `.apk` installable directement sur un téléphone sans passer par le Play Store.
- **Windows (.exe)** : doit être compilé depuis un PC Windows (ou une VM Windows / un runner GitHub Actions `windows-latest`).
- **macOS (.dmg)** : doit être compilé depuis un Mac (ou un runner GitHub Actions `macos-latest`) — Apple ne permet pas de compiler un `.dmg` depuis Windows ou Linux.
- Les trois apps nécessitent une connexion internet pour fonctionner, puisqu'elles chargent votre site en direct plutôt que d'embarquer les données.

## Compiler .exe et .dmg sans PC Windows ni Mac (GitHub Actions)

Le dossier `.github/workflows/build-desktop.yml` compile automatiquement
les deux versions dans le cloud, chacune sur le vrai système
d'exploitation cible (un runner Windows pour le `.exe`, un runner
macOS pour le `.dmg`) — aucun matériel Apple ou licence Windows requis
de votre côté.

### Mise en place

1. Poussez ce dossier (avec `.github/workflows/build-desktop.yml`) sur un dépôt GitHub — le plus simple est de l'ajouter au même dépôt que le reste du projet pmupredict.
2. Vérifiez au préalable que `pmupredict-desktop-tauri/dist/index.html` contient bien l'URL réelle de votre frontend (pas l'URL de démonstration).
3. Allez dans l'onglet **Actions** du dépôt GitHub.
4. Sélectionnez le workflow **"pmupredict - Build desktop (.exe + .dmg)"**.
5. Cliquez **Run workflow** (déclenchement manuel).
6. Une fois terminé (quelques minutes), les fichiers sont disponibles au bas de la page d'exécution, dans la section **Artifacts** :
   - `pmupredict-windows-exe` → contient le `.exe` (et `.msi`)
   - `pmupredict-macos-dmg` → contient le `.dmg`
7. Téléchargez ces artifacts (fichiers `.zip` contenant vos installeurs) directement depuis l'interface GitHub.

> Note : ce workflow génère des fichiers **non signés** (pas de certificat de signature de code Windows/Apple). Sur Windows, l'installeur peut déclencher un avertissement SmartScreen ; sur macOS, Gatekeeper peut bloquer l'ouverture au premier lancement (l'utilisateur doit alors faire clic droit → Ouvrir). Pour un usage personnel, ce n'est qu'un clic supplémentaire ; pour une diffusion plus large, il faudrait un certificat de signature payant (~100 $/an pour Apple, variable pour Windows).

## Configuration native

Avant de construire Android, Windows ou macOS, définir la variable GitHub Actions `PMUPREDICT_APP_URL` (Repository Settings → Secrets and variables → Actions → Variables) avec l'URL HTTPS réelle du frontend PMUPredict sur Vercel. Ne mettez jamais de clé Supabase service-role dans cette application native.
