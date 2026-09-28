import requests
from bs4 import BeautifulSoup

def get_weather_by_address(address):
    """
    Get weather using wttr.in API with structured output
    """
    try:
        # Use wttr.in JSON API for structured data
        url = f"https://wttr.in/{address.replace(' ', '+')}?format=j1"
        response = requests.get(url, timeout=10, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            current = data["current_condition"][0]
            location = data["nearest_area"][0]
            
            # Extract location name
            city = location["areaName"][0]["value"]
            region = location["region"][0]["value"]
            country = location["country"][0]["value"]
            
            # Extract weather data
            weather_desc = current["weatherDesc"][0]["value"]
            temp_c = current["temp_C"]
            feels_like = current["FeelsLikeC"]
            humidity = current["humidity"]
            wind_speed = current["windspeedKmph"]
            wind_dir = current["winddir16Point"]
            
            weather_report = (
                f"Location: {city}, {region}, {country}\n"
                f"Weather: {weather_desc}\n"
                f"Temperature: {temp_c}°C\n"
                f"Feels Like: {feels_like}°C\n"
                f"Humidity: {humidity}%\n"
                f"Wind: {wind_speed} km/h {wind_dir}"
            )
            return weather_report
        else:
            return "Could not get weather for that location"
            
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather: {e}"
    except (KeyError, IndexError):
        return "Could not parse weather data"


def get_weather_google(address):
    """
    Backup: Try scraping Google (may not work due to blocking)
    """
    search_url = f"https://www.google.com/search?q=weather+{address.replace(' ', '+')}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Try to find weather elements with error handling
            location_elem = soup.find("div", attrs={"id": "wob_loc"})
            time_elem = soup.find("div", attrs={"id": "wob_dts"})
            weather_elem = soup.find("span", attrs={"id": "wob_dc"})
            temp_elem = soup.find("span", attrs={"id": "wob_tm"})

            # Check if elements were found
            if not all([location_elem, time_elem, weather_elem, temp_elem]):
                return None  # Google blocked or structure changed

            weather_report = (
                f"Location: {location_elem.text}\n"
                f"Time: {time_elem.text}\n"
                f"Weather: {weather_elem.text}\n"
                f"Temperature: {temp_elem.text}°C"
            )
            return weather_report
        else:
            return None
    except Exception:
        return None

    
def weather(address=None):
    if address is None:
        address = input("Enter the address: ")
    
    weather_report = get_weather_by_address(address)
    print(weather_report)
    return weather_report


if __name__ == "__main__":
    weather()
