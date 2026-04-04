# 🚀 Manabi-Backend (学び — Back-End)

The high-performance, asynchronous FastAPI backend powering the **Manabi** ecosystem. It manages community decks, user synchronization, AI-assisted vocabulary generation, and grammar unit management.

## 🌟 Key Features

### 🏢 Community Deck Hub
- **Database Scaling**: High-speed access to JLPT and official language decks.
- **User Shares**: Publish and discover decks shared by the Manabi community.
- **Versioning**: Automatic synchronization of deck updates between client and server.

### 🤖 AI Proxy & Generation
- **Token Management**: Securely handles API keys for cloud AI providers.
- **Deck Seeding**: Advanced scripts for auto-generating language-accurate vocabulary decks.
- **FastAPI Core**: Minimal latency, high concurrency during AI-intensive tasks.

### 🔄 Data Synchronization
- **Auth Flow**: Secure registration and login for community access.
- **Profile Management**: Stores user progress and statistics in a unified cloud profile.
- **Conflict Resolution**: Smart merging of local and remote learning progress.

## 🛠️ Tech Stack
- **Framework**: [FastAPI](https://fastapi.tiangolo.com) (Python 3.10+)
- **Database**: **[MariaDB](https://mariadb.org/)** (Required for production/community features)
- **Security**: [Jose (JWT)](https://python-jose.readthedocs.io/en/latest/) for authentication
- **Server**: [Uvicorn](https://www.uvicorn.org/) ASGI server

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- **MariaDB Server** (Running and accessible)
- `pip` (Python package manager)

### Installation
1. Clone the repository:
   ```bash
   git clone git@github.com:sumpfel/manabi-backend.git
   ```
2. Set up a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configuration:
   - Create a `.env` file in the root. **This is critical** for database connectivity and security.
   - Use the following template and replace the values in brackets:
     ```env
     DATABASE_URL=mysql+pymysql://<DB_USER>:<DB_PASSWORD>@<DB_HOST>:<DB_PORT>/<DB_NAME>
     SECRET_KEY=<YOUR_SUPER_SECRET_KEY>
     ALGORITHM=HS256
     ACCESS_TOKEN_EXPIRE_MINUTES=30
     ```

5. Run the server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## 📂 Project Structure
- `main.py`: Entry point and application setup
- `api/routers/`: Modular route definitions (Auth, AI, Community, Sync)
- `core/`: Core security and configuration logic
- `create_db.py`: Database schema and migration script
- `seed_*.py`: Data initialization and deck generation scripts

---
Powering the next generation of Japanese language learners.
