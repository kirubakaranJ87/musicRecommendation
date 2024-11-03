import streamlit as st
from pymongo import MongoClient
from fuzzywuzzy import fuzz
import ast  # To evaluate artist lists if needed
import requests
import base64

# Connect to MongoDB (replace with your own connection details)
client = MongoClient("mongodb://localhost:27017/")
db = client["projectmusic"]
collection = db["spotify"]

# Spotify API credentials (replace with your own)
client_id = "27099b02cf094a70b596586ad2e1ded4"
client_secret = "45857dede68740de973de9c33e52f1f6"

# Function to get Spotify API token
def get_spotify_token(client_id, client_secret):
    auth_url = 'https://accounts.spotify.com/api/token'
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_header}"
    }
    data = {
        "grant_type": "client_credentials"
    }
    
    response = requests.post(auth_url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

# Function to fetch preview URL from Spotify
def get_preview_url(track_id, token):
    url = f"https://api.spotify.com/v1/tracks/{track_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        track_info = response.json()
        return track_info.get("preview_url")
    return None

# Function to find the most related song in MongoDB
def find_most_related_song(input_song_name, input_artist_name, collection, played_songs, threshold=70):
    most_related_song = None
    highest_similarity_score = 0
    
    for doc in collection.find({}):
        song_name = doc.get("name", "")
        artists_str = doc.get("artists", "")
        
        try:
            artists_list = ast.literal_eval(artists_str)
            if not isinstance(artists_list, list):
                artists_list = [artists_list]
        except (ValueError, SyntaxError):
            artists_list = [artists_str]

        # Skip if the song was already played
        if song_name in played_songs:
            continue

        # Calculate name and artist similarity scores
        name_similarity = fuzz.ratio(input_song_name.lower(), song_name.lower())
        artist_similarity = max(fuzz.ratio(input_artist_name.lower(), artist.lower()) for artist in artists_list)
        combined_similarity = (name_similarity + artist_similarity) / 2

        if combined_similarity > highest_similarity_score and combined_similarity >= threshold:
            highest_similarity_score = combined_similarity
            most_related_song = doc
    
    return most_related_song

# Streamlit UI
st.title("Song Recommendation System with Spotify Preview")
st.write("Enter a song name to play it and find related songs.")

# Initialize session state variables
if 'current_song' not in st.session_state:
    st.session_state.current_song = None
if 'current_artist' not in st.session_state:
    st.session_state.current_artist = None
if 'played_songs' not in st.session_state:
    st.session_state.played_songs = []
if 'spotify_token' not in st.session_state:
    st.session_state.spotify_token = get_spotify_token(client_id, client_secret)

# Input form
input_song_name = st.text_input("Enter Song Name", "")

# Function to play the current song and display its details
def play_song(song_doc):
    song_name = song_doc['name']
    artists = song_doc['artists']
    track_id = song_doc.get("id")

    if isinstance(artists, str):
        try:
            artists_list = ast.literal_eval(artists)
            if not isinstance(artists_list, list):
                artists_list = [artists_list]
        except (ValueError, SyntaxError):
            artists_list = [artists]
    else:
        artists_list = artists

    st.session_state.current_song = song_name
    st.session_state.current_artist = artists_list[0]
    st.session_state.played_songs.append(song_name)  # Add the song to the played list

    st.write("### Now Playing:")
    st.write(f"**Song Name:** {song_name}")
    st.write(f"**Artists:** {', '.join(artists_list)}")

    if track_id:
        preview_url = get_preview_url(track_id, st.session_state.spotify_token)
        if preview_url:
            st.audio(preview_url)
        else:
            st.write("Preview not available for this song.")

# Play button
if st.button("Play"):
    if input_song_name:
        song_doc = collection.find_one({"name": {"$regex": input_song_name, "$options": "i"}})
        if song_doc:
            play_song(song_doc)
        else:
            st.write("The song was not found in the database.")
    else:
        st.write("Please enter a song name.")

# Next button
if st.button("Next"):
    if st.session_state.current_song and st.session_state.current_artist:
        related_song = find_most_related_song(st.session_state.current_song, st.session_state.current_artist, collection, st.session_state.played_songs)
        if related_song:
            play_song(related_song)
        else:
            st.write("No further related song found above the similarity threshold.")
    else:
        st.write("Please play a song first by clicking 'Play'.")
