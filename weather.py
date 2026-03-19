import requests
from datetime import datetime


def get_weather_full(city_name: str) -> dict:
    """
    Fetches current weather AND 7-day forecast using Open-Meteo (100% free, no API key).
    Returns a structured dict with current conditions and forecast risk windows.
    """
    try:
        # Step 1: Geocoding
        geo_url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?name={city_name}&count=1&language=en&format=json"
        )
        geo_resp = requests.get(geo_url, timeout=10).json()

        if not geo_resp.get("results"):
            return {"error": f"Location '{city_name}' not found."}

        result = geo_resp["results"][0]
        lat = result["latitude"]
        lon = result["longitude"]
        resolved_name = result.get("name", city_name)
        country = result.get("country", "")

        # Step 2: Weather forecast (current + 7 day)
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current_weather=true"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
            f"windspeed_10m_max,weathercode"
            f"&timezone=auto"
            f"&forecast_days=7"
        )
        w = requests.get(weather_url, timeout=10).json()

        current = w.get("current_weather", {})
        daily = w.get("daily", {})

        # Build forecast days
        forecast_days = []
        dates = daily.get("time", [])
        for i, date in enumerate(dates):
            forecast_days.append({
                "date": date,
                "temp_max": daily["temperature_2m_max"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "precipitation_mm": daily["precipitation_sum"][i],
                "windspeed_max": daily["windspeed_10m_max"][i],
                "weathercode": daily["weathercode"][i],
            })

        # Identify risk windows
        risk_windows = _analyze_risks(forecast_days)

        return {
            "location": f"{resolved_name}, {country}",
            "current_temp": current.get("temperature"),
            "current_wind": current.get("windspeed"),
            "current_condition": _decode_wmo(current.get("weathercode", 0)),
            "forecast": forecast_days,
            "risk_windows": risk_windows,
        }

    except Exception as e:
        return {"error": f"Weather service error: {str(e)}"}


def _analyze_risks(forecast: list) -> list:
    """Identify agronomically significant weather risk windows in the 7-day forecast."""
    risks = []
    for day in forecast:
        issues = []
        if day["precipitation_mm"] > 10:
            issues.append(f"Heavy rain ({day['precipitation_mm']}mm) — risk of fungal spread")
        if day["temp_max"] > 38:
            issues.append(f"Heat stress risk ({day['temp_max']}°C max)")
        if day["temp_min"] < 10:
            issues.append(f"Cold stress / frost risk ({day['temp_min']}°C min)")
        if day["windspeed_max"] > 40:
            issues.append(f"High winds ({day['windspeed_max']} km/h) — avoid spraying")
        if issues:
            risks.append({"date": day["date"], "warnings": issues})
    return risks


def _decode_wmo(code: int) -> str:
    """Decode WMO weather code to human-readable string."""
    mapping = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail",
    }
    return mapping.get(code, f"Code {code}")


def format_weather_for_llm(weather: dict) -> str:
    """Format weather data into a clean string for LLM consumption."""
    if "error" in weather:
        return weather["error"]

    lines = [
        f"Location: {weather['location']}",
        f"Current: {weather['current_temp']}°C, {weather['current_condition']}, "
        f"Wind {weather['current_wind']} km/h",
        "",
        "7-Day Forecast:",
    ]
    for day in weather.get("forecast", []):
        lines.append(
            f"  {day['date']}: {day['temp_min']}–{day['temp_max']}°C, "
            f"Rain: {day['precipitation_mm']}mm, Wind: {day['windspeed_max']} km/h"
        )

    if weather.get("risk_windows"):
        lines.append("")
        lines.append("⚠️ Risk Windows Detected:")
        for rw in weather["risk_windows"]:
            for w in rw["warnings"]:
                lines.append(f"  {rw['date']}: {w}")

    return "\n".join(lines)
