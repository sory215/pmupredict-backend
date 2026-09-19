# pmupredict — Application Android (Capacitor)

Cette configuration crée une application Android qui affiche votre
frontend pmupredict déjà déployé sur Vercel, dans une fenêtre native
sans navigateur visible (barre d'adresse, boutons, etc.).

## Avant de commencer

Votre frontend doit déjà être déployé (voir `pmupredict-VERCEL.zip`).
Vous avez besoin de son URL publique, par exemple
`https://pmupredict.vercel.app`.

## Prérequis à installer sur votre ordinateur

1. **Node.js** (v18 ou plus) — https://nodejs.org
2. **Android Studio** — https://developer.android.com/studio (nécessaire pour compiler l'APK et gérer le SDK Android)

## Étapes

1. Ouvrir ce dossier dans un terminal.

2. Modifier `capacitor.config.json` : remplacer
   `https://REMPLACER-PAR-VOTRE-URL.vercel.app` par l'URL réelle de
   votre frontend déployé.

3. Installer les dépendances :
   ```bash
   npm install
   ```

4. Ajouter la plateforme Android au projet :
   ```bash
   npx cap add android
   ```
   Cela crée un dossier `android/` contenant un projet Android Studio complet.

5. Synchroniser la configuration :
   ```bash
   npm run sync
   ```

6. Ouvrir le projet dans Android Studio :
   ```bash
   npm run open
   ```

## Étapes détaillées dans Android Studio (point par point)

C'est l'étape 7 ci-dessus, développée en détail car c'est là que la
plupart des échecs de compilation surviennent.

1. **Attendre la synchronisation Gradle initiale.** En bas de la
   fenêtre, une barre de progression indique "Gradle sync". Ne rien
   cliquer tant qu'elle tourne — cela peut prendre 5 à 15 minutes la
   première fois (téléchargement de composants).

2. **Vérifier le SDK Manager** avant de compiler :
   `Tools → SDK Manager` → onglet **SDK Platforms** : cocher au moins
   la version Android correspondant à `compileSdkVersion` du projet
   (généralement la plus récente stable, ex. Android 14 / API 34).
   Onglet **SDK Tools** : cocher **Android SDK Build-Tools** et
   **Android SDK Command-line Tools**. Cliquer **Apply** pour
   installer ce qui manque.

3. **Vérifier le JDK utilisé** :
   `File → Settings → Build, Execution, Deployment → Build Tools →
   Gradle` → champ "Gradle JDK" : choisir une version **17** (Android
   Studio en télécharge une automatiquement si besoin via l'option
   "Download JDK").

4. **Relancer une synchronisation propre** si un doute persiste :
   `File → Sync Project with Gradle Files` (icône éléphant dans la
   barre d'outils).

5. **Compiler l'APK** : `Build → Build Bundle(s) / APK(s) → Build
   APK(s)`. Une notification en bas à droite ("APK(s) generated
   successfully") apparaît en fin de compilation, avec un lien
   **locate** pour ouvrir le dossier contenant le fichier.

6. Le fichier se trouve normalement dans :
   `android/app/build/outputs/apk/debug/app-debug.apk`

## Pourquoi la compilation échoue souvent — causes les plus fréquentes

| Symptôme | Cause probable | Solution |
|---|---|---|
| `Gradle sync failed` dès l'ouverture | Pas de connexion internet stable, ou pare-feu/proxy bloquant le téléchargement des dépendances Gradle | Vérifier la connexion ; si proxy d'entreprise, le configurer dans `File → Settings → Appearance & Behavior → System Settings → HTTP Proxy` |
| `SDK location not found` | Le fichier `android/local.properties` ne pointe pas vers le bon chemin du SDK | Le supprimer et relancer Android Studio : il le régénère automatiquement au bon endroit |
| `Unsupported Java version` ou erreurs liées à Gradle/JDK | Mauvaise version de JDK sélectionnée (souvent JDK 8 ou 11 au lieu de 17) | Corriger dans `Gradle JDK` (étape 3 ci-dessus) |
| `Could not resolve com.android.tools.build:gradle:...` | Version de Gradle/Android Gradle Plugin incompatible avec la version d'Android Studio installée | Laisser Android Studio proposer une mise à jour automatique du plugin (bandeau en haut du fichier `build.gradle`) et accepter |
| Le build se lance mais reste bloqué très longtemps | Premier téléchargement des Gradle Wrapper / dépendances, normal la première fois | Patienter (jusqu'à 15-20 min sur une connexion lente) ; les fois suivantes sont bien plus rapides (cache local) |
| `cleartext HTTP traffic not permitted` | L'app tente de charger une URL en `http://` au lieu de `https://` | Vérifier que l'URL dans `capacitor.config.json` commence bien par `https://` |
| Erreur après modification de `capacitor.config.json` non prise en compte | Oubli de resynchroniser Capacitor après une modification | Relancer `npx cap sync android` puis rouvrir/re-synchroniser dans Android Studio |
| Espace disque insuffisant | Android Studio + SDK + Gradle cache peuvent occuper 10-15 Go | Libérer de l'espace disque avant de commencer |

## Conseil pour limiter les échecs

Avant de lancer la première compilation, vérifier dans l'ordre :
1. Node.js installé et à jour (`node -v`)
2. Android Studio à jour (`Help → Check for Updates`)
3. Une connexion internet stable et non bridée par un antivirus/pare-feu strict
4. Au moins 15 Go d'espace disque libre

Si malgré tout la compilation échoue, le message d'erreur complet
s'affiche dans l'onglet **Build** en bas de la fenêtre (icône
marteau) — c'est ce message précis (pas juste "ça ne marche pas")
qui permet de diagnostiquer la cause exacte.

8. Pour installer l'APK sur un téléphone Android : activer le mode
   développeur + "Sources inconnues", transférer le fichier `.apk` et
   l'ouvrir sur l'appareil.

## Personnalisation (icône, nom, splash screen)

- Nom de l'app : champ `appName` dans `capacitor.config.json`
- Icône et splash screen : remplacer les images dans
  `android/app/src/main/res/` (Android Studio propose un assistant
  **Image Asset** via clic droit sur `res` → **New → Image Asset**)

## Publier sur le Google Play Store (optionnel)

Nécessite :
- Un compte développeur Google Play (frais unique ~25 $)
- Une version signée (`Build → Generate Signed Bundle/APK`, format `.aab` recommandé)
- Une fiche de présentation (captures d'écran, description, politique de confidentialité)

Pour un usage strictement personnel, l'APK généré à l'étape 7 suffit
et n'a pas besoin d'être publié.
