import os
import sys
import io
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langchain.messages import HumanMessage, AIMessage, SystemMessage

# MENGATASI ERROR CHARMAP: Memaksa output terminal menggunakan UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. Memuat file .env
load_dotenv()

# 2. Mengambil API Key (Pastikan di .env namanya MISTRAL_API_KEY)
api_key = os.getenv("MISTRAL_API_KEY")

if not api_key:
    print("Error: MISTRAL_API_KEY tidak ditemukan di file .env")
    sys.exit(1)

# 3. Inisialisasi Model Mistral
model = ChatMistralAI(
    model="mistral-large-latest",
    temperature=0.1,
    api_key=api_key
)

# 4. Struktur Percakapan
conversation = [
    SystemMessage(content='You are a helpful assistant for questions regarding programming'),
    HumanMessage(content='negara mana yang memiliki jumlah penduduk terbanyak?'),
]

# 5. Eksekusi
try:
    response = model.invoke(conversation)
    # Ganti print(response.content) dengan ini:
    print(response.content.encode('ascii', 'ignore').decode('ascii'))
except Exception as e:
    # Menggunakan str(e).encode jika error pesan mengandung karakter aneh
    print(f"Terjadi kesalahan: {e}")
    print(f"Error details: {str(e).encode('ascii', 'ignore').decode('ascii')}")

    #HOW TO RUN
    #env:PYTHONUTF8=1
    #cd "c:\Users\muham\OneDrive\Dokumen\Python\ai_python
    # python test.py"
