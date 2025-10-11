#API and Collection
import requests
import dotenv 
API_KEY = "d8b9c663"
search_key = input("Enter movie name")
movieInfo = requests.get('http://www.omdbapi.com/?apikey='+API_KEY+'&s='+search_key).json()
print(movieInfo)
