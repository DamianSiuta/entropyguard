import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from langchain_core.tools import tool

# --- KONFIGURACJA ---
# Upewnij się, że masz ten plik w folderze!
SERVICE_ACCOUNT_FILE = 'google_key.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']
# PAMIĘTAJ: Tu wpisz swój email (ten sam co w Google Calendar ID)
CALENDAR_ID = 'dami.siuta@gmail.com' 
PLIK_WIEDZY = 'baza_wiedzy.txt'

def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

@tool
def sprawdz_baze_wiedzy(pytanie: str) -> str:
    """
    Przeszukuje bazę wiedzy kliniki (cennik, czas zabiegów, parking, procedury).
    Użyj tego, gdy pacjent pyta o cenę, czas trwania, dojazd lub inne szczegóły.
    """
    try:
        if not os.path.exists(PLIK_WIEDZY):
            return "Brak pliku bazy wiedzy."
        with open(PLIK_WIEDZY, 'r', encoding='utf-8') as f:
            tresc = f.read()
        return f"Oto informacje z bazy wiedzy kliniki:\n{tresc}"
    except Exception as e:
        return "Przepraszam, nie mogę odczytać bazy wiedzy."

@tool
def sprawdz_grafik(dzien_tekst: str) -> str:
    """Sprawdza kalendarz na dany dzień (Format daty: YYYY-MM-DD)."""
    try:
        date_obj = datetime.datetime.strptime(dzien_tekst, "%Y-%m-%d")
        time_min = date_obj.isoformat() + 'Z'
        time_max = (date_obj + datetime.timedelta(days=1)).isoformat() + 'Z'

        service = get_calendar_service()
        events_result = service.events().list(
            calendarId=CALENDAR_ID, timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return f"Kalendarz {dzien_tekst} jest pusty. Godziny pracy: 09:00-18:00."

        raport = f"Zajęte terminy w dniu {dzien_tekst}:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Formatowanie godziny (wycinamy T i sekundy)
            s_h = start[11:16] if 'T' in start else ""
            raport += f"- {s_h} (Zajęte)\n"
        
        return raport
    except Exception as e:
        return f"Błąd: {str(e)}"

@tool
def zapisz_wizyte(imie: str, telefon: str, data: str, godzina: str, opis: str, czas_trwania_minuty: int = 45) -> str:
    """
    Zapisuje wizytę. 
    WAŻNE: 'czas_trwania_minuty' musi być pobrany z bazy wiedzy!
    Np. Konsultacja=30, Wyrwanie=60, Kanałowe=90.
    """
    try:
        service = get_calendar_service()
        
        start_str = f"{data}T{godzina}:00"
        start_dt = datetime.datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S")
        # Obliczamy koniec wizyty na podstawie czasu trwania
        end_dt = start_dt + datetime.timedelta(minutes=int(czas_trwania_minuty))

        event = {
            'summary': f"{imie} ({czas_trwania_minuty}min)",
            'location': 'Klinika Estetica',
            'description': f"Tel: {telefon}\nZabieg: {opis}\nCzas: {czas_trwania_minuty} min.",
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Warsaw'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Europe/Warsaw'},
        }

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return f"SUKCES! Zapisano {imie} na {data} {godzina} (czas: {czas_trwania_minuty} min)."
    except Exception as e:
        return f"Błąd zapisu: {str(e)}"