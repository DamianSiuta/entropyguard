import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
# Importujemy nasze nowe narzędzia
from tools import sprawdz_dostepnosc, rezerwuj_wizyte

load_dotenv()

# 1. Konfiguracja modelu + BINDING (Dajemy narzędzia do ręki)
tools = [sprawdz_dostepnosc, rezerwuj_wizyte]
llm = ChatOpenAI(model="gpt-4o", temperature=0.7).bind_tools(tools)

# Słownik: mapuje nazwy funkcji na prawdziwe funkcje (żebyśmy mogli je uruchomić)
tools_map = {
    "sprawdz_dostepnosc": sprawdz_dostepnosc,
    "rezerwuj_wizyte": rezerwuj_wizyte
}

system_prompt = """
Jesteś Anną, recepcjonistką w Estetica Dental.
ZASADY:
1. Sprawdź dostępność (sprawdz_dostepnosc) ZANIM zaproponujesz termin.
2. Nie zmyślaj godzin. Opieraj się tylko na tym, co zwróci narzędzie.
3. Bądź krótka i konkretna.
"""

chat_history = [SystemMessage(content=system_prompt)]

print("✅ Anna z narzędziami gotowa. (Napisz 'koniec' żeby wyjść)")
print("-" * 50)

while True:
    user_input = input("Ty: ")
    if user_input.lower() == "koniec": break

    chat_history.append(HumanMessage(content=user_input))

    # --- PĘTLA WYKONAWCZA (To robi "AI Agent Node" w n8n) ---
    # Model może chcieć użyć narzędzia wiele razy, więc robimy pętlę
    while True:
        response = llm.invoke(chat_history)
        
        # Jeśli model nie chce użyć narzędzi, przerywamy pętlę i wyświetlamy odpowiedź
        if not response.tool_calls:
            print(f"Anna: {response.content}")
            chat_history.append(response) # Dodaj odpowiedź do historii
            print("-" * 50)
            break
        
        # Jeśli model CHCE użyć narzędzi:
        chat_history.append(response) # Dodajemy intencję modelu do historii ("Chcę sprawdzić kalendarz")
        
        for tool_call in response.tool_calls:
            # 1. Zobacz co Anna chce zrobić
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"⚙️ [Anna używa narzędzia]: {tool_name} z danymi {tool_args}")
            
            # 2. Uruchom odpowiednią funkcję z tools.py
            selected_tool = tools_map[tool_name]
            tool_result = selected_tool.invoke(tool_args)
            
            # 3. Dodaj wynik narzędzia do historii (Anna to "zobaczy")
            chat_history.append(ToolMessage(tool_call_id=tool_call["id"], content=str(tool_result)))
    # --- KONIEC PĘTLI ---