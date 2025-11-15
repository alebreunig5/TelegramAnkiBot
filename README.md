# TelegramAnkiBot
Python script designed to automate the process of creating flashcards for Anki using the Gemini API model running in a local host to be able to connect with Anki.

## Context 🎯
This script was created to automate the generation of English Cards to extend the vocabulary, but could be potencially used for anything that you want to learn. For example,
- 🏥 Learn specific terminology
- 📚 Summaries
- 💭 Large explanations

## Features ✨
- **🤖 Telegram Bot** - Interactive interface for easy card creation
- **🔗 AnkiConnect Integration** - Seamless connection with Anki
- **🧠 Gemini AI Powered** - Smart content generation using Google's Gemini API
- **🔄 Auto-Restart System** - Self-healing bot that recovers from failures
- **🎴 Multiple Card Types** - Support for basic and reversed cards
- **📁 Deck Management** - Organize cards in different Anki decks

## Workflow
💬 Send English word to Telegram bot

🤖 Wait for Gemini AI to process and return information

📊 Review generated content (definitions, pronunciation, examples)

✅ Confirm card creation in chosen deck

🎴 Card automatically appears in Anki


## Folders Structure✨
```python 
IA-Powered-Anki-Cards-Generator/
├── bot.py                    # Main Telegram bot logic
├── anki_functions.py         # Anki + Gemini integration
├── anki_bot_completo.bat     # Windows auto-start script
└── .env                      # Configuration file (excluded)
```
