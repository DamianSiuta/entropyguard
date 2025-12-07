import chainlit as cl
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from dotenv import load_dotenv
import datetime
import os
from tools import sprawdz_grafik, zapisz_wizyte, sprawdz_baze_wiedzy, PLIK_WIEDZY

# 1. KONFIGURACJA
load_dotenv()

# Konfiguracja narzędzi (Ręce bota)
tools = [sprawdz_grafik, zapisz_wizyte, sprawdz_baze_wiedzy]
tools_map = {t.name: t for t in tools}

# Konfiguracja modelu (Mózg bota)
llm = ChatOpenAI(model="gpt-4o", temperature=0.5).bind_tools(tools)

@cl.on_chat_start
async def start():
    """To uruchamia się, gdy pacjent wchodzi na stronę"""
    
    # Reset historii
    cl.user_session.set("history", [])

    # Definicja osobowości Anny
    system_prompt = SystemMessage(content=f"""
    Jesteś Anną, profesjonalną recepcjonistką w ekskluzywnej klinice 'Estetica Dental'. 
    Dziś jest: {datetime.date.today()}.
    
    TWOJE CELE:
    1. Odpowiadać na pytania o cennik/usługi (użyj `sprawdz_baze_wiedzy`).
    2. Sprawdzać dostępność terminów (użyj `sprawdz_grafik`).
    3. Umawiać wizyty w Google Calendar (użyj `zapisz_wizyte`).
    
    STYL KOMUNIKACJI:
    - Bardzo uprzejmy, ciepły i elegancki ("Dzień dobry", "Zapraszam").
    - Krótki i konkretny (jak na czacie).
    - Daty zawsze konwertuj na format YYYY-MM-DD.
    """)
    
    cl.user_session.set("history", [system_prompt])
    
    # Powitanie (Używa Twoich plików avatarów z folderu public)
    await cl.Message(
        content="**Witamy w Estetica Dental.** 🦷\n\nJestem Twoją osobistą asystentką. Pomogę Ci sprawdzić termin, poznać cennik i zarezerwować wizytę.\n\n*W czym mogę pomóc?*",
        author="Recepcja"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Główna pętla rozmowy z pacjentem"""
    
    # 1. Pobierz historię rozmowy
    history = cl.user_session.get("history")
    history.append(HumanMessage(content=message.content))
    
    # 2. Pokaż, że bot myśli
    msg = cl.Message(content="")
    await msg.send()
    
    # 3. Zapytaj AI
    response = await llm.ainvoke(history)
    
    # 4. Obsługa narzędzi (Pętla)
    while response.tool_calls:
        history.append(response) # Dodaj chęć użycia narzędzia do historii
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            args = tool_call["args"]
            tool_id = tool_call["id"]
            
            # Ładny wizualny "Step" w interfejsie (np. Sprawdzam grafik...)
            async with cl.Step(name="Przetwarzam...", type="process") as step:
                step.input = args
                try:
                    # Uruchomienie prawdziwego narzędzia (Google Calendar / Plik)
                    result = tools_map[tool_name].invoke(args)
                except Exception as e:
                    result = f"Błąd techniczny: {str(e)}"
                
                step.output = result
                
                # Jeśli sukces zapisu -> Wyślij specjalny komunikat
                if tool_name == "zapisz_wizyte" and "SUKCES" in str(result):
                    await cl.Message(
                        content="✅ **Wizyta została potwierdzona w kalendarzu!**", 
                        author="System"
                    ).send()

            # Zapisz wynik narzędzia do historii
            history.append(ToolMessage(tool_call_id=tool_id, content=str(result)))
        
        # Zapytaj AI ponownie, mając już wyniki z narzędzi
        response = await llm.ainvoke(history)

    # 5. Wyświetl ostateczną odpowiedź pacjentowi
    msg.content = response.content
    await msg.update()
    
    # Zapisz zaktualizowaną historię
    history.append(response)
    cl.user_session.set("history", history)