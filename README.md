# 🏏 IPL Scorecard in Terminal

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Terminal](https://img.shields.io/badge/CLI-Interface-black?style=for-the-badge&logo=gnu-bash&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

## 📌 Overview
**IPL Scorecard in Terminal** is a lightweight, fast, and interactive Command Line Interface (CLI) application built entirely in Python. It brings live match updates, historical match data, and comprehensive scorecards of the Indian Premier League (IPL) straight to your developer environment. 

Say goodbye to browser tabs taking up your system memory. Whether you are tracking a massive Chennai Super Kings (CSK) run chase or just keeping an eye on the current run rate while coding, this tool delivers elegant, real-time cricketing data directly to your terminal screen.

## ✨ Key Features
- **Live Match Tracking:** Fetch real-time ball-by-ball updates and current scorelines.
- **Detailed Scorecards:** View comprehensive batting and bowling statistics for completed and ongoing matches.
- **Clean Terminal UI:** A stylized and structured command-line interface that formats complex JSON data into readable tables.
- **API Integration:** Powered by RapidAPI to ensure fast, reliable, and accurate cricket data delivery.

## 🛠️ Tech Stack & Architecture
- **Language:** Python (100%)
- **Architecture Flow:**
  - `main.py`: The entry point that initializes the application loop.
  - `api.py`: Handles secure HTTP requests and data extraction from RapidAPI.
  - `ui.py`: Manages the terminal presentation layer, ensuring data is formatted cleanly.
  - `config.py`: Centralized configuration for API endpoints and application constants.

## 📁 Repository Structure
```text
├── main.py                          # Core application runner
├── api.py                           # Network requests and API parsing module
├── ui.py                            # Terminal output formatting and display
├── config.py                        # Constants and configuration variables
├── testing.py                       # Unit tests and API response validation
├── requirements.txt                 # Python dependencies
├── rapidapi_config.example.json     # Template for your RapidAPI credentials
├── rapidapi_config.json             # Your active API credentials (ignored in Git)
└── README.md                        # Project documentation
