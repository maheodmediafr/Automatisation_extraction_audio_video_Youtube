import flet as ft
import json
import os
import subprocess
import sys
import shutil
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import xml.etree.ElementTree as ET
import yt_dlp
import requests
import boto3
from botocore.client import Config

# Configuration des dossiers
XML_IN_DOSSIER = "XML_IN"
AUDIO_OUTPUT = "AUDIO_OUT"
XML_EN_COURS = "XML_OUT"

# Configuration PAM
PAM_URL = "https://pam.lpsan-2025.fr/assets"
PAM_TOKEN = "super-secure-token"

# Configuration S3
HOST = "s3.fr-par.scw.cloud"
KEY_ID = "SCWGHGQW6RA7GYG0793C"
KEY_SECRET = "ce8c7900-b8fa-459c-af5a-ce7f7b7d6ef9"
BUCKET = "pam-ina"
REGION = "fr-par"

# Fichier de configuration
CONFIG_FILE = "config.json"
LAST_VIDEOS_FILE = "last_videos.json"

class YouTubeMonitor:
    def __init__(self):
        self.observer = None
        self.running = False
        self.monitor_thread = None
        self.config = self.load_config()
        self.show_all_channels = False

    def load_config(self):
        """Charge la configuration depuis le fichier JSON."""
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "watch_frequency": 3600,
                    "watch_paths": ["XML_IN"],
                    "youtube_channels": [],
                    "max_recent_videos": 10
                }, f, indent=4)
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    def save_config(self):
        """Sauvegarde la configuration dans le fichier JSON."""
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def save_last_videos(self, last_videos):
        """Sauvegarde les dernières vidéos traitées."""
        with open(LAST_VIDEOS_FILE, "w") as f:
            json.dump(last_videos, f, indent=4)

    def load_last_videos(self):
        """Charge les dernières vidéos traitées."""
        if os.path.exists(LAST_VIDEOS_FILE):
            with open(LAST_VIDEOS_FILE, "r") as f:
                return json.load(f)
        return {}

    def get_video_info(self, video_url):
        """Récupère les informations de la vidéo YouTube avec yt-dlp."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            title = info_dict.get('title', 'No Title')
            channel_name = info_dict.get('uploader', 'No Channel')
            description = info_dict.get('description', 'No Description')
            return title, channel_name, description

    def generate_xml_file(self, video_id, video_url, title, channel_name, description):
        """Génère un fichier XML pour le traitement ultérieur."""
        os.makedirs(XML_IN_DOSSIER, exist_ok=True)

        youtube = ET.Element("youtube")

        title_elem = ET.SubElement(youtube, "title")
        title_elem.text = title

        description_elem = ET.SubElement(youtube, "description")
        description_elem.text = channel_name

        uri_elem = ET.SubElement(youtube, "uri")
        uri_elem.text = video_url

        summary_elem = ET.SubElement(youtube, "summary")
        summary_elem.text = description

        xml_str = ET.tostring(youtube, encoding="UTF-8")
        xml_file = os.path.join(XML_IN_DOSSIER, f"{video_id}.xml")

        with open(xml_file, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str)

        return xml_file

    def get_latest_videos(self, channel_id, max_results=50):
        """Récupère les dernières vidéos d'une chaîne YouTube."""
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'playlists_only': False,
            'quiet': True,
            'no_warnings': True,
            'force_generic_extractor': True,
            'playlistend': max_results,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                url = f"https://www.youtube.com/channel/{channel_id}/videos"
                result = ydl.extract_info(url, download=False)
                if 'entries' in result:
                    return result['entries']
                return []
            except Exception as e:
                print(f"Erreur lors de la récupération des vidéos pour la chaîne {channel_id}: {e}")
                return []

    def check_channel_for_new_videos(self, channel_id, channel_name):
        """Vérifie et traite les nouvelles vidéos sur une chaîne YouTube."""
        last_videos = self.load_last_videos()
        if channel_id not in last_videos:
            last_videos[channel_id] = {}

        videos = self.get_latest_videos(channel_id)
        new_videos = False
        videos_processed = 0
        max_recent_videos = self.config.get("max_recent_videos", 10)

        for video in videos:
            if videos_processed >= max_recent_videos:
                break

            video_id = video['id']
            if video_id not in last_videos[channel_id]:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                title = video.get('title', 'No Title')
                channel_name = video.get('uploader', 'No Channel')
                description = video.get('description', 'No Description')

                # Générer un fichier XML pour le traitement ultérieur
                xml_file = self.generate_xml_file(video_id, video_url, title, channel_name, description)
                print(f"Fichier XML généré : {xml_file}")

                # Mettre à jour le dernier ID vidéo traité
                last_videos[channel_id][video_id] = True
                videos_processed += 1
                new_videos = True

        if new_videos:
            self.save_last_videos(last_videos)

        return new_videos

    def monitor_channels(self):
        """Surveille les chaînes YouTube pour détecter les nouvelles vidéos."""
        for channel in self.config["youtube_channels"]:
            self.check_channel_for_new_videos(channel["id"], channel["name"])

    def create_pam_asset(self, title, author, description):
        """Demande un ID au PAM via l'API."""
        payload = {
            "title": title,
            "author": author,
            "body": description
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {PAM_TOKEN}"
        }
        response = requests.post(PAM_URL, json=payload, headers=headers)
        if response.ok:
            return response.json()
        else:
            print(f"Erreur lors de la création de l'asset PAM: {response.text}")
            return None

    def upload_to_s3(self, filepath, bucket, s3_key):
        """Dépose un fichier sur S3."""
        s3 = boto3.client(
            's3',
            endpoint_url=f"https://{HOST}",
            aws_access_key_id=KEY_ID,
            aws_secret_access_key=KEY_SECRET,
            region_name=REGION,
            config=Config(signature_version='s3v4')
        )
        try:
            s3.upload_file(filepath, bucket, s3_key)
            print(f"Fichier {filepath} déposé avec succès sur S3 : {s3_key}")
            return True
        except Exception as e:
            print(f"Erreur lors du dépôt sur S3 : {e}")
            return False

    def process_xml_file(self, xml_file_path):
        """Traite un fichier XML pour extraire l'audio et créer un asset PAM."""
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()

            url = root.find('uri').text

            # Extraire les informations de la vidéo avec yt-dlp
            title, author, description = self.get_video_info(url)

            # Chemin temporaire pour le fichier audio
            temp_audio_base = os.path.join(AUDIO_OUTPUT, f"temp_{title}")

            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': temp_audio_base,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                temp_audio_path = ydl.prepare_filename(info_dict)
                print(f"Fichier audio extrait : {temp_audio_path}")

            # Créer un asset dans le PAM
            pam_response = self.create_pam_asset(title, author, description)
            if pam_response:
                asset_id = pam_response.get("id")
                print(f"Asset PAM créé avec l'ID : {asset_id}")

                # Vérifier et ajouter l'extension .mp3 si nécessaire
                if not temp_audio_path.endswith('.mp3'):
                    temp_audio_path += '.mp3'

                # Renommer le fichier audio avec l'ID de l'asset
                final_audio_path = os.path.join(AUDIO_OUTPUT, f"{asset_id}.mp3")
                if os.path.exists(temp_audio_path):
                    os.rename(temp_audio_path, final_audio_path)
                    print(f"Fichier audio renommé : {final_audio_path}")

                    # Upload vers S3
                    s3_key = f"audio/{asset_id}.mp3"
                    if self.upload_to_s3(final_audio_path, BUCKET, s3_key):
                        print("Upload S3 terminé avec succès !")
                    else:
                        print("Échec de l'upload S3.")

            # Déplacer le fichier XML traité dans le dossier "XML_OUT"
            processed_file = os.path.join(XML_EN_COURS, os.path.basename(xml_file_path))
            shutil.move(xml_file_path, processed_file)
            print(f"Fichier XML déplacé vers : {processed_file}")

            return True
        except Exception as e:
            print(f"Erreur lors du traitement du fichier {xml_file_path} : {e}")
            return False

    def process_existing_xml_files(self):
        """Traite les fichiers XML déjà présents dans le dossier XML_IN."""
        print("\nTraitement des fichiers XML existants dans le dossier XML_IN...")
        xml_files = [f for f in os.listdir(XML_IN_DOSSIER) if f.endswith('.xml')]

        for xml_file in xml_files:
            xml_file_path = os.path.join(XML_IN_DOSSIER, xml_file)
            print(f"Traitement du fichier XML existant : {xml_file}")
            self.process_xml_file(xml_file_path)

    def start_monitoring(self):
        """Démarre la surveillance des chaînes YouTube."""
        if not self.running:
            self.running = True

            # Traiter d'abord les fichiers XML existants
            self.process_existing_xml_files()

            # Initialiser l'observateur pour surveiller les dossiers
            event_handler = XMLHandler(self)
            self.observer = Observer()
            for path in self.config["watch_paths"]:
                os.makedirs(path, exist_ok=True)
                self.observer.schedule(event_handler, path, recursive=False)
            self.observer.start()
            print("Surveillance des dossiers et des chaînes YouTube en cours...")

            # Démarrer le thread de surveillance des chaînes
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            return True
        return False

    def stop_monitoring(self):
        """Arrête la surveillance des chaînes YouTube."""
        if self.running:
            self.running = False
            if self.observer:
                self.observer.stop()
                self.observer.join()
            print("Surveillance arrêtée.")
            return True
        return False

    def monitor_loop(self):
        """Boucle de surveillance des chaînes YouTube."""
        while self.running:
            self.monitor_channels()
            time.sleep(self.config["watch_frequency"])

class XMLHandler(FileSystemEventHandler):
    def __init__(self, monitor):
        self.monitor = monitor

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".xml"):
            print(f"\nNouveau fichier XML détecté : {event.src_path}")
            self.monitor.process_xml_file(event.src_path)

def main(page: ft.Page):
    # Configuration de la page
    page.title = "Configuration des Chaînes YouTube"
    page.bgcolor = "#8B551B"  # Couleur de fond demandée
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO
    page.theme = ft.Theme(font_family="Futura")  # Police Futura

    # Initialisation du moniteur YouTube
    monitor = YouTubeMonitor()
    config = monitor.config

    # Ajout du logo INA Campus
    logo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/INA_logo.svg/1200px-INA_logo.svg.png"
    logo = ft.Image(
        src=logo_url,
        width=150,
        height=50,
        fit=ft.ImageFit.CONTAIN,
    )

    # Boutons de contrôle en haut
    control_row = ft.Row(
        [
            ft.ElevatedButton(
                "Démarrer la Surveillance",
                on_click=lambda e: start_monitoring(e),
                bgcolor="#4CAF50",
                color="white"
            ),
            ft.ElevatedButton(
                "Arrêter la Surveillance",
                on_click=lambda e: stop_monitoring(e),
                bgcolor="#F44336",
                color="white"
            )
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20
    )

    # Titre sous les boutons de contrôle
    title_row = ft.Row(
        [
            ft.Text("Configuration des Chaînes YouTube à Surveiller", size=24, weight=ft.FontWeight.BOLD, color="white"),
        ],
        alignment=ft.MainAxisAlignment.CENTER
    )

    # Placement du logo et des boutons de contrôle
    header_row = ft.Column(
        [
            ft.Row(
                [
                    logo
                ],
                alignment=ft.MainAxisAlignment.CENTER
            ),
            control_row,
            title_row
        ],
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )

    # Champs pour ajouter une nouvelle chaîne avec texte en blanc
    new_channel_id = ft.TextField(
        hint_text="ID de la Chaîne YouTube",
        width=300,
        color="white",
        border_color="#F19837",
        focused_border_color="#F19837"
    )
    new_channel_name = ft.TextField(
        hint_text="Nom de la Chaîne",
        width=300,
        color="white",
        border_color="#F19837",
        focused_border_color="#F19837"
    )

    # Champ pour la fréquence de surveillance
    watch_frequency = ft.TextField(
        hint_text="Fréquence de surveillance (en secondes)",
        value=str(config["watch_frequency"]),
        width=300,
        color="white",
        border_color="#F19837",
        focused_border_color="#F19837"
    )

    # Champ pour le nombre de vidéos récentes à traiter
    max_recent_videos = ft.TextField(
        hint_text="Nombre de vidéos récentes à traiter",
        value=str(config.get("max_recent_videos", 10)),
        width=300,
        color="white",
        border_color="#F19837",
        focused_border_color="#F19837"
    )

    # Liste des chaînes YouTube (3 premières par défaut)
    channels_list = ft.Column()
    show_all_button = ft.ElevatedButton(
        "Voir plus",
        on_click=lambda e: toggle_channels_view(e),
        bgcolor="#F19837",
        color="white"
    )

    # Zone de log sur la partie droite
    log_area = ft.ListView(
        height=500,
        width=350,
        expand=False,
        auto_scroll=True
    )

    def update_channels_list():
        """Met à jour la liste des chaînes YouTube affichées."""
        channels_list.controls.clear()

        # Afficher seulement les 3 premières chaînes si show_all_channels est False
        display_channels = config["youtube_channels"]
        if not monitor.show_all_channels and len(display_channels) > 3:
            display_channels = display_channels[:3]

        for channel in display_channels:
            channels_list.controls.append(
                ft.Row(
                    [
                        ft.Text(f"{channel['name']} ({channel['id']})", color="white"),
                        ft.TextButton(
                            "Supprimer",
                            on_click=lambda e, cid=channel['id']: remove_channel(cid),
                            style=ft.ButtonStyle(color="white")
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )

        # Afficher le bouton "Voir plus" ou "Voir moins" si nécessaire
        if len(config["youtube_channels"]) > 3:
            channels_list.controls.append(
                ft.Row(
                    [
                        show_all_button
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                )
            )

        page.update()

    def toggle_channels_view(e):
        """Basculer entre l'affichage de 3 chaînes et toutes les chaînes."""
        monitor.show_all_channels = not monitor.show_all_channels
        if monitor.show_all_channels:
            show_all_button.text = "Voir moins"
        else:
            show_all_button.text = "Voir plus"
        update_channels_list()

    def add_log(message):
        """Ajoute un message au journal."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_area.controls.append(ft.Text(f"[{timestamp}] {message}", color="white"))
        page.update()

    def add_channel(e):
        """Ajoute une nouvelle chaîne YouTube à la configuration."""
        channel_id = new_channel_id.value
        channel_name = new_channel_name.value

        if channel_id and channel_name:
            config["youtube_channels"].append({
                "id": channel_id,
                "name": channel_name
            })
            monitor.save_config()
            new_channel_id.value = ""
            new_channel_name.value = ""
            update_channels_list()
            add_log(f"Chaîne ajoutée: {channel_name} ({channel_id})")

    def remove_channel(channel_id):
        """Supprime une chaîne YouTube de la configuration."""
        config["youtube_channels"] = [channel for channel in config["youtube_channels"] if channel["id"] != channel_id]
        monitor.save_config()
        update_channels_list()
        add_log(f"Chaîne supprimée: {channel_id}")

    def save_frequency(e):
        """Sauvegarde la fréquence de surveillance."""
        try:
            frequency = int(watch_frequency.value)
            config["watch_frequency"] = frequency
            monitor.save_config()
            page.snack_bar = ft.SnackBar(ft.Text("Fréquence sauvegardée avec succès!", color="white"),
                                         bgcolor="#4CAF50")
            page.snack_bar.open = True
            page.update()
            add_log(f"Fréquence de surveillance mise à jour: {frequency} secondes")
        except ValueError:
            page.snack_bar = ft.SnackBar(ft.Text("Veuillez entrer un nombre valide!", color="white"),
                                         bgcolor="#F44336")
            page.snack_bar.open = True
            page.update()

    def save_max_recent_videos(e):
        """Sauvegarde le nombre de vidéos récentes à traiter."""
        try:
            max_videos = int(max_recent_videos.value)
            config["max_recent_videos"] = max_videos
            monitor.save_config()
            page.snack_bar = ft.SnackBar(ft.Text("Nombre de vidéos récentes sauvegardé avec succès!", color="white"),
                                         bgcolor="#4CAF50")
            page.snack_bar.open = True
            page.update()
            add_log(f"Nombre de vidéos récentes mis à jour: {max_videos}")
        except ValueError:
            page.snack_bar = ft.SnackBar(ft.Text("Veuillez entrer un nombre valide!", color="white"),
                                         bgcolor="#F44336")
            page.snack_bar.open = True
            page.update()

    def start_monitoring(e):
        """Démarre la surveillance."""
        try:
            if monitor.start_monitoring():
                page.snack_bar = ft.SnackBar(ft.Text("Surveillance démarrée avec succès!", color="white"),
                                             bgcolor="#4CAF50")
                page.snack_bar.open = True
                page.update()
                add_log("Surveillance démarrée")
            else:
                page.snack_bar = ft.SnackBar(ft.Text("La surveillance est déjà en cours!", color="white"),
                                             bgcolor="#FF9800")
                page.snack_bar.open = True
                page.update()
        except Exception as e:
            page.snack_bar = ft.SnackBar(ft.Text(f"Erreur lors du démarrage: {e}", color="white"),
                                         bgcolor="#F44336")
            page.snack_bar.open = True
            page.update()
            add_log(f"Erreur lors du démarrage: {e}")

    def stop_monitoring(e):
        """Arrête la surveillance."""
        try:
            if monitor.stop_monitoring():
                page.snack_bar = ft.SnackBar(ft.Text("Surveillance arrêtée avec succès!", color="white"),
                                             bgcolor="#4CAF50")
                page.snack_bar.open = True
                page.update()
                add_log("Surveillance arrêtée")
            else:
                page.snack_bar = ft.SnackBar(ft.Text("La surveillance n'est pas en cours!", color="white"),
                                             bgcolor="#FF9800")
                page.snack_bar.open = True
                page.update()
        except Exception as e:
            page.snack_bar = ft.SnackBar(ft.Text(f"Erreur lors de l'arrêt: {e}", color="white"),
                                         bgcolor="#F44336")
            page.snack_bar.open = True
            page.update()
            add_log(f"Erreur lors de l'arrêt: {e}")

    # Mise à jour initiale de la liste des chaînes
    update_channels_list()

    # Interface principale avec la zone de log à droite
    page.add(
        header_row,
        ft.Divider(color="white"),
        ft.Row(
            [
                # Partie gauche avec les champs de configuration
                ft.Column(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Fréquence de surveillance (en secondes):", color="white"),
                                    ft.Row(
                                        [
                                            watch_frequency,
                                            ft.ElevatedButton("Sauvegarder", on_click=save_frequency, bgcolor="#F19837", color="white")
                                        ],
                                        spacing=10
                                    ),
                                ],
                                spacing=10
                            ),
                            padding=10,
                            border=ft.border.all(1, "#F19837"),
                            border_radius=10
                        ),
                        ft.Divider(color="white"),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Nombre de vidéos récentes à traiter:", color="white"),
                                    ft.Row(
                                        [
                                            max_recent_videos,
                                            ft.ElevatedButton("Sauvegarder", on_click=save_max_recent_videos, bgcolor="#F19837", color="white")
                                        ],
                                        spacing=10
                                    ),
                                ],
                                spacing=10
                            ),
                            padding=10,
                            border=ft.border.all(1, "#F19837"),
                            border_radius=10
                        ),
                        ft.Divider(color="white"),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Ajouter une nouvelle chaîne YouTube:", color="white"),
                                    ft.Row(
                                        [
                                            new_channel_id,
                                            new_channel_name,
                                            ft.ElevatedButton("Ajouter", on_click=add_channel, bgcolor="#F19837", color="white")
                                        ],
                                        spacing=10
                                    ),
                                ],
                                spacing=10
                            ),
                            padding=10,
                            border=ft.border.all(1, "#F19837"),
                            border_radius=10
                        ),
                        ft.Divider(color="white"),
                        ft.Text("Chaînes configurées :", size=16, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(
                            content=channels_list,
                            bgcolor="#9B6B38",
                            border=ft.border.all(1, "#F19837"),
                            border_radius=10,
                            padding=10
                        ),
                    ],
                    spacing=10,
                    expand=True
                ),
                # Partie droite avec le journal d'activités
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Journal des activités :", size=16, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Container(
                                content=log_area,
                                bgcolor="#9B6B38",
                                border=ft.border.all(1, "#F19837"),
                                border_radius=10,
                                padding=10,
                                height=500,
                                width=350
                            ),
                        ],
                        spacing=10
                    ),
                    padding=10
                )
            ],
            spacing=20
        )
    )

ft.app(target=main)
