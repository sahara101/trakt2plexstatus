import requests
import yaml
import json
from datetime import datetime
import pytz
from plexapi.server import PlexServer
import os
import logging
import time

# Load configuration from file
with open('shows_status.yml', 'r') as config_file:
    config = yaml.safe_load(config_file)

# Assign configuration values
LIBRARIES = config['LIBRARIES']
TZ = config['TZ']
COLORS = config['COLORS']
LOG_FILE = config['LOG_FILE']
TRAKT_TOKEN_FILE = config['TRAKT_TOKEN_FILE']
TRAKT_CLIENT_ID = config['TRAKT_CLIENT_ID']
TRAKT_CLIENT_SECRET = config['TRAKT_CLIENT_SECRET']
TRAKT_USERNAME = config['TRAKT_USERNAME']
REDIRECT_URI = config['REDIRECT_URI']
PLEX_URL = config['PLEX_URL']
PLEX_TOKEN = config['PLEX_TOKEN']
YAML_OUTPUT_DIR = config['YAML_OUTPUT_DIR']
YAML_FILE_TEMPLATE = config['YAML_FILE_TEMPLATE']
FONT_PATH = config['FONT_PATH']
COLLECTIONS_DIR = config['COLLECTIONS_DIR']

# Ensure the YAML output directory exists
if not os.path.exists(YAML_OUTPUT_DIR):
    print(f"Error: YAML output directory does not exist: {YAML_OUTPUT_DIR}")
    exit(1)

if not os.path.exists(COLLECTIONS_DIR):
    print(f"Error: Metadatat directory does not exist: {COLLECTIONS_DIR}")
    exit(1)

# Configure logging to overwrite the log file on each run and set level to DEBUG
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, filemode='w', format='%(asctime)s - %(levelname)s - %(message)s')
logging.debug("Script started.")

airing_shows = []

def get_trakt_token():
    if not os.path.exists(TRAKT_TOKEN_FILE):
        logging.info("Trakt token file not found. Initiating authentication process...")
        auth_url = f'https://trakt.tv/oauth/authorize?response_type=code&client_id={TRAKT_CLIENT_ID}&redirect_uri={REDIRECT_URI}'
        print(f"Please visit this URL to authorize: {auth_url}")
        code = input("Enter the code from the website: ")
        token_url = 'https://api.trakt.tv/oauth/token'
        payload = {
            'code': code,
            'client_id': TRAKT_CLIENT_ID,
            'client_secret': TRAKT_CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        response = requests.post(token_url, json=payload)
        if response.status_code == 200:
            token_data = response.json()
            # Add creation timestamp if not provided by the API
            if 'created_at' not in token_data:
                token_data['created_at'] = int(time.time())
            with open(TRAKT_TOKEN_FILE, 'w') as file:
                json.dump(token_data, file)
            logging.info("Trakt authentication successful.")
            return token_data['access_token']
        else:
            logging.error("Failed to authenticate with Trakt.")
            exit(1)
    else:
        with open(TRAKT_TOKEN_FILE) as file:
            token_data = json.load(file)

        # Check if token is expired or about to expire
        current_time = time.time()
        # Add a buffer of 10 minutes before expiration
        if 'expires_in' in token_data and 'created_at' in token_data:
            expires_at = token_data['created_at'] + token_data['expires_in']
            if current_time > expires_at - 600:  # 10 minutes before expiration
                logging.info("Token is expired or about to expire. Refreshing...")
                refresh_token = token_data.get('refresh_token')
                if refresh_token:
                    token_url = 'https://api.trakt.tv/oauth/token'
                    payload = {
                        'refresh_token': refresh_token,
                        'client_id': TRAKT_CLIENT_ID,
                        'client_secret': TRAKT_CLIENT_SECRET,
                        'redirect_uri': REDIRECT_URI,
                        'grant_type': 'refresh_token'
                    }
                    response = requests.post(token_url, json=payload)
                    if response.status_code == 200:
                        new_token_data = response.json()
                        # Add creation timestamp if not provided by the API
                        if 'created_at' not in new_token_data:
                            new_token_data['created_at'] = int(current_time)
                        with open(TRAKT_TOKEN_FILE, 'w') as file:
                            json.dump(new_token_data, file)
                        logging.info("Token refreshed successfully.")
                        return new_token_data['access_token']
                    else:
                        logging.error(f"Failed to refresh token: {response.status_code} - {response.text}")
                        # If refresh fails, force re-authentication
                        os.remove(TRAKT_TOKEN_FILE)
                        return get_trakt_token()
                else:
                    logging.error("No refresh token available. Re-authentication required.")
                    os.remove(TRAKT_TOKEN_FILE)
                    return get_trakt_token()

        logging.debug("Trakt token loaded successfully.")
        return token_data['access_token']
    print("Trakt authentication successful.")

def get_user_slug(headers):
    """Retrieve the user's slug (username) for list operations."""
    response = requests.get('https://api.trakt.tv/users/me', headers=headers)
    if response.status_code == 200:
        return response.json()['ids']['slug']
    logging.error("Failed to retrieve Trakt user slug.")
    return None

def get_or_create_trakt_list(list_name, headers):
    """Ensure a Trakt list exists and return its slug, creating it if necessary."""
    user_slug = get_user_slug(headers)
    lists_url = f'https://api.trakt.tv/users/{user_slug}/lists'
    response = requests.get(lists_url, headers=headers)
    if response.status_code == 200:
        for lst in response.json():
            if lst['name'].lower() == list_name.lower():
                return lst['ids']['slug']  # List exists
    # Create the list if it doesn't exist
    create_payload = {
        "name": list_name,
        "description": "List of shows with their next airing episodes.",
        "privacy": "public",
        "display_numbers": False,
        "allow_comments": False
    }
    create_resp = requests.post(lists_url, json=create_payload, headers=headers)
    if create_resp.status_code in [200, 201]:
        return get_or_create_trakt_list(list_name, headers)  # Recursively get the newly created list
    logging.error("Failed to create Trakt list.")
    return None
    print(f"List '{list_name}' ensured on Trakt.")

def process_show(show, headers):
    logging.debug(f"Processing show: {show.title}")
    for guid in show.guids:
        if 'tmdb://' in guid.id:
            tmdb_id = guid.id.split('//')[1]
            search_api_url = f'https://api.trakt.tv/search/tmdb/{tmdb_id}?type=show'
            response = requests.get(search_api_url, headers=headers)
            if response.status_code == 200 and response.json():
                trakt_id = response.json()[0]['show']['ids']['trakt']
                status_url = f'https://api.trakt.tv/shows/{trakt_id}?extended=full'
                status_response = requests.get(status_url, headers=headers)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get('status', '').lower()
                    text_content = 'UNKNOWN'
                    back_color = COLORS.get(status.upper(), '#FFFFFF')

                    if status == 'ended':
                        text_content = 'E N D E D'
                        back_color = COLORS['ENDED']
                    elif status == 'canceled':
                        text_content = 'C A N C E L L E D'
                        back_color = COLORS['CANCELLED']
                    elif status == 'returning series':
                        next_episode_url = f'https://api.trakt.tv/shows/{trakt_id}/next_episode?extended=full'
                        next_episode_response = requests.get(next_episode_url, headers=headers)
                        if next_episode_response.status_code == 200 and next_episode_response.json():
                            episode_data = next_episode_response.json()
                            first_aired = episode_data.get('first_aired')
                            episode_type = episode_data.get('episode_type', '').lower()

                            if first_aired:
                                utc_time = datetime.strptime(first_aired, '%Y-%m-%dT%H:%M:%S.000Z')
                                local_time = utc_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TZ))
                                date_str = local_time.strftime('%d/%m')

                                # Handle different episode types
                                if episode_type == 'season_finale':
                                    text_content = f'SEASON FINALE {date_str}'
                                    back_color = COLORS['SEASON_FINALE']
                                elif episode_type == 'mid_season_finale':
                                    text_content = f'MID SEASON FINALE {date_str}'
                                    back_color = COLORS['MID_SEASON_FINALE']
                                elif episode_type == 'series_finale':
                                    text_content = f'FINAL EPISODE {date_str}'
                                    back_color = COLORS['FINAL_EPISODE']
                                elif episode_type == 'season_premiere':
                                    text_content = f'SEASON PREMIERE {date_str}'
                                    back_color = COLORS['SEASON_PREMIERE']
                                else:
                                    text_content = f'AIRING {date_str}'
                                    back_color = COLORS['AIRING']

                                airing_shows.append({
                                    'trakt_id': trakt_id,
                                    'title': show.title,
                                    'first_aired': first_aired,
                                    'episode_type': episode_type
                                })
                        else:
                            text_content = 'R E T U R N I N G'
                            back_color = COLORS['RETURNING']

                    return {
                        'text_content': text_content,
                        'back_color': back_color,
                        'font': FONT_PATH
                    }
    logging.debug(f"Finished processing show: {show.title}")
    return None
    print(f"Processing show: {show.title} - Status: {text_content}")

def create_yaml(library_name, headers):
    logging.info(f"Processing library: {library_name}")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    library = plex.library.section(library_name)
    yaml_data = {'overlays': {}}
    for show in library.all():
        logging.debug(f"Processing {show.title}...")
        show_info = process_show(show, headers)
        if show_info:
            formatted_title = show.title.replace(' ', '_')
            yaml_data['overlays'][f'{library_name}_Status_{formatted_title}'] = {
                'overlay': {
                    'back_color': show_info['back_color'],
                    'back_height': 90,
                    'back_width': 1000,
                    'color': '#FFFFFF',
                    'font': show_info['font'],
                    'font_size': 70,
                    'horizontal_align': 'center',
                    'horizontal_offset': 0,
                    'name': f"text({show_info['text_content']})",
                    'vertical_align': 'top',
                    'vertical_offset': 0,
                },
                'plex_search': {
                    'all': {
                        'title': show.title
                    }
                }
            }
            logging.debug(f"Processed {show.title} with status {show_info['text_content']}.")

    yaml_file_path = os.path.join(YAML_OUTPUT_DIR, YAML_FILE_TEMPLATE.format(library=library_name.lower()))
    with open(yaml_file_path, 'w') as file:
        yaml.dump(yaml_data, file, allow_unicode=True, default_flow_style=False)
    logging.info(f'YAML file created for {library_name}: {yaml_file_path}')

yaml_template = """
collections:
  Next Airing {library_name}:
    trakt_list: https://trakt.tv/users/{config['TRAKT_USERNAME']}/lists/next-airing?sort=rank,asc
    file_poster: 'config/assets/Next Airing/poster.jpg'
    collection_order: custom
    visible_home: true
    visible_shared: true
    sync_mode: sync
"""

def create_yaml_collections_if_missing(libraries, COLLECTIONS_DIR):
    for library_name in libraries:
        # Format the filename
        yaml_filename = f"{library_name.lower().replace(' ', '-')}-next-airing.yml"
        yaml_filepath = os.path.join(COLLECTIONS_DIR, yaml_filename)

        # Check if the file exists
        if not os.path.exists(yaml_filepath):
            print(f"Creating YAML collections file for {library_name}.")
            with open(yaml_filepath, 'w') as file:
                file_content = yaml_template.format(library_name=library_name)
                file.write(file_content)
            print(f"File created: {yaml_filepath}")
        else:
            print(f"YAML collections file for {library_name} already exists.")

def sort_airing_shows_by_date(airing_shows):
    return sorted(airing_shows, key=lambda x: datetime.strptime(x['first_aired'], '%Y-%m-%dT%H:%M:%S.000Z'))

def fetch_current_trakt_list_shows(list_slug, headers):
    user_slug = get_user_slug(headers)
    list_items_url = f'https://api.trakt.tv/users/{user_slug}/lists/{list_slug}/items'
    response = requests.get(list_items_url, headers=headers)
    if response.status_code == 200:
        current_shows = response.json()
        # Extract Trakt IDs of shows currently in the list
        current_trakt_ids = [item['show']['ids']['trakt'] for item in current_shows if item.get('show')]
        return current_trakt_ids
    else:
        logging.error("Failed to fetch current Trakt list shows.")
        return []

def update_trakt_list(list_slug, airing_shows, headers):
    user_slug = get_user_slug(headers)
    current_trakt_ids = fetch_current_trakt_list_shows(list_slug, headers)
    new_trakt_ids = [int(show['trakt_id']) for show in airing_shows]

    # Check if the lists match (including order)
    if current_trakt_ids == new_trakt_ids:
        print("No update necessary for the Trakt list.")
        return

    list_items_url = f'https://api.trakt.tv/users/{user_slug}/lists/{list_slug}/items'
    # Assuming you want to refresh the list
    print("Updating Trakt list with airing shows...")
    # First, remove all existing items
    requests.post(f"{list_items_url}/remove", json={"shows": [{"ids": {"trakt": trakt_id}} for trakt_id in current_trakt_ids]}, headers=headers)
    time.sleep(1)

    # Then, add the new list of shows
    shows_payload = {"shows": [{"ids": {"trakt": trakt_id}} for trakt_id in new_trakt_ids]}
    response = requests.post(list_items_url, json=shows_payload, headers=headers)
    if response.status_code in [200, 201, 204]:
        print(f"Trakt list {list_slug} updated successfully with {len(airing_shows)} shows.")
    else:
        print(f"Failed to update Trakt list {list_slug}. Response: {response.text}")
    time.sleep(1)  # Respect rate limits

# Main execution logic
access_token = get_trakt_token()
headers = {
    'Content-Type': 'application/json',
    'trakt-api-version': '2',
    'Authorization': f'Bearer {access_token}',
    'trakt-api-key': TRAKT_CLIENT_ID
}

for library_name in LIBRARIES:
    print(f"Processing library: {library_name}")
    create_yaml(library_name, headers)

for library_name in LIBRARIES:
    create_yaml_collections_if_missing([library_name], COLLECTIONS_DIR)

list_name = "Next Airing"
list_slug = get_or_create_trakt_list(list_name, headers)
if list_slug:
    sorted_airing_shows = sort_airing_shows_by_date(airing_shows)
    update_trakt_list(list_slug, sorted_airing_shows, headers)
