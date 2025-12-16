# Automatisation extraction audio video Youtube

**Automatisation extraction audio video Youtube** consiste à extraire l'audio d'une vidéo Youtube à partir d'un fichier XML renseignant le titre, la description de la vidéo et le lien Youtube. Ce fichier XML est créé lorsque une vidéo est publiée sur une chaine que nous avons ajoutée à la liste, à vous de définir le nombre de dernières vidéos Youtube que vous voulez télécharger. Cet audio sera accessible via le PAM LPSAN 2025 grâce à un upload sur AWS S3 qui nous donnera un ID permettant de nommer ce fichier audio.

## 📌 Fonctionnalités

- **Surveillance en temps réel** des chaînes YouTube configurées
- **Génération automatique de fichiers XML** pour les nouvelles vidéos
- **Extraction audio** des vidéos en format MP3
- **Gestion des uploads** vers un stockage AWS S3
- **Interface graphique intuitive** pour la configuration des chaines youtube
- **Journal des activités** pour suivre les opérations
- **Limitation du nombre de dernières vidéos traitées** par chaîne youtube

## 📦 Prérequis

- Python 3.8 ou supérieur
- pip (pour l'installation des dépendances)

## 🛠 Installation

1. Cloner le dépôt

git clone https://github.com/votre-utilisateur/youtube-monitor.git
cd youtube-monitor

2. Installer les dépendances

pip install -r requirements.txt

3. Créer les dossiers nécessaires

mkdir XML_IN XML_OUT AUDIO_OUT

### 🚀 Utilisation

# Lancer l'interface gaphique

python Automatisation_extraction_audio_video_Youtube.py

# Configuration

1. Ajouter des chaînes YouTube :

Entrez l'ID et le nom de la chaîne dans les champs prévus
Cliquez sur "Ajouter"

2. Configurer la fréquence de surveillance :

Définissez l'intervalle (en secondes) entre chaque vérification

3. Définir le nombre de vidéos récentes :

Spécifiez combien de vidéos récentes doivent être traitées

4. Démarrer/Arrêter la surveillance :

Utilisez les boutons "Démarrer la Surveillance" et "Arrêter la Surveillance"

## 📂 Structure du projet

TP_Mahe/
├── AUDIO_OUT/                                        # Dossier pour les fichiers audio extraits
├── Automatisation_extraction_audio_video_Youtube.py  # Point d'entrée principal
├── config.json                                       # Fichier de configuration
├── last_videos.json                                  # Suivi des dernières vidéos traitées
├── README.md                                         # Ce fichier
├── requirements.txt                                  # Dépendances du projet
├── XML_IN/                                           # Dossier pour les fichiers XML entrants
├── XML_OUT/                                          # Dossier pour les fichiers XML traités

## 🔧 Configuration

# Fichier config.json

{
    "watch_frequency": 3600,
    "watch_paths": ["XML_IN"],
    "youtube_channels": [
        {
            "id": "UCj_iGliGCkLcHSZ8eqVNPDQ",
            "name": "Nom de la Chaîne"
        }
    ],
    "max_recent_videos": 10
}

# Configuration S3

HOST = "s3.fr-par.scw.cloud"
KEY_ID = "VOTRE_KEY_ID"
KEY_SECRET = "VOTRE_KEY_SECRET"
BUCKET = "pam-ina"
REGION = "fr-par"

## 📝 Licence
Ce projet est sous licence MIT - voir le fichier [LICENSE] pour plus de détails.

## 📬 Contact
Pour toute question ou suggestion: mahebaize@gmail.com

Automatisation extraction audio video Youtube © 2025. Tous droits réservés.
