# 🌿 FarmAI — Autonomous Micro-Farming & Crop Disease Agent

A production-grade AI agent that helps small-scale farmers diagnose crop diseases and generate 
organic treatment plans using a **fully free** tool stack.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔬 Disease Classifier Node | Pre-classifies issue as fungal / bacterial / pest / nutrient / abiotic before searching |
| 🌤️ 7-Day Weather Intelligence | Open-Meteo free API with risk window detection (rain, heat, wind) |
| 👁️ Visual Diagnosis | Upload a crop photo → Llama 4 Vision analyzes it before the agent runs |
| 🧠 Conditional LangGraph | True branching agent graph, not a linear chain |
| 💾 Session Memory | SQLite stores past sessions; recurring issues are flagged |
| 🚨 Escalation Node | Severe cases automatically trigger expert contact recommendation |
| 🔍 Explainability Panel | See exactly what data the agent used to form its advice |
| 🌍 Multilingual | Responds in Hindi, Marathi, Swahili, Spanish, Tamil, Telugu, Kannada & more |
| 📄 Report Download | Download the full treatment plan as a .txt report |

---

## 🛠️ Tech Stack (100% Free)

- **LangGraph** — agent orchestration with typed state
- **Groq + Llama 3.3 70B** — free LLM inference (no OpenAI needed)
- **Llama 4 Scout Vision** — free image analysis via Groq
- **Open-Meteo API** — free weather + geocoding (no key needed)
- **DuckDuckGo Search** — free web search
- **SQLite** — local persistent memory
- **Streamlit** — UI framework

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone <your-repo>
cd micro-farming-agent
pip install -r requirements.txt
```

### 2. Get a FREE Groq API Key
Go to [console.groq.com](https://console.groq.com) → Sign up → Create API Key.  
No credit card required.

### 3. Set up environment
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 4. Run
```bash
streamlit run app.py
```

---

## 🗂️ Project Structure

```
micro-farming-agent/
├── app.py          # Streamlit UI — main entry point
├── agent.py        # LangGraph agent with all nodes
├── weather.py      # Open-Meteo weather + risk analysis
├── vision.py       # Llama 4 Vision image diagnosis
├── database.py     # SQLite session memory
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔄 Agent Graph Flow

```
START
  │
  ▼
[Classifier] — detects disease category & severity
  │
  ▼
[Planner] — formulates targeted search query based on category
  │
  ▼
[Executor] — fetches 7-day weather + runs DuckDuckGo search in parallel
  │
  ▼
[Synthesizer] — builds 3-step organic plan with weather timing & confidence score
  │
  ▼
END → (Escalation notice if severe)
```

---

## 📊 Disease Categories Detected

- **Fungal** → neem oil, baking soda, copper fungicide timing
- **Bacterial** → copper spray, sterilization, pruning advice  
- **Pest** → organic repellents, trap crops, beneficial insects
- **Nutrient** → soil amendments, compost, foliar feeding
- **Abiotic** → drought/heat stress management, mulching
- **Viral** → vector control, resistant variety suggestions

---

## 🌍 Supported Languages

English, Hindi, Marathi, Swahili, Spanish, French, Tamil, Telugu, Kannada

---

## 📝 Notes

- Weather data via Open-Meteo requires **no API key** and is completely free
- Groq's free tier provides ~14,400 requests/day on Llama 3.3 70B
- Session history is stored locally in `farming_memory.db`
- Image diagnosis uses Llama 4 Scout (free on Groq)

---

## 🤝 Contributing

PRs welcome! Key areas for improvement:
- Add SMS report delivery (Twilio free tier)
- Integrate plant disease image datasets for fine-tuned classification
- Add offline mode with cached responses
