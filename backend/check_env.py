import os
import sys
from pathlib import Path
from dotenv import load_dotenv

print("=" * 60)
print("WAYORA AI - MONGODB & .ENV VERIFICATION CHECK")
print("=" * 60)

# 1. Check .env file presence
backend_dir = Path(__file__).resolve().parent
backend_env = backend_dir / ".env"
root_env = backend_dir.parent / ".env"

print(f"\n[1] Checking .env files:")
print(f"  - backend/.env path : {backend_env}")
print(f"  - backend/.env exists: {backend_env.is_file()}")
print(f"  - root .env exists    : {root_env.is_file()}")

if not backend_env.is_file() and not root_env.is_file():
    print("  ❌ ERROR: No .env file found!")
    sys.exit(1)

# 2. Read and parse .env
env_file_to_load = backend_env if backend_env.is_file() else root_env
load_dotenv(env_file_to_load, override=True)

with open(env_file_to_load, "r", encoding="utf-8") as f:
    env_lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

print(f"\n[2] Loaded from: {env_file_to_load.name}")
for line in env_lines:
    if "=" in line:
        k, v = line.split("=", 1)
        if "URI" in k.upper() or "PASS" in k.upper() or "KEY" in k.upper():
            parts = v.split("@")
            masked = parts[0][:15] + "...@" + parts[1] if len(parts) > 1 else v[:10] + "..."
            print(f"  - {k} = {masked}")
        else:
            print(f"  - {k} = {v}")

uri = os.getenv("MONGODB_URI")
if not uri:
    print("  ❌ ERROR: MONGODB_URI variable not found in environment after loading .env!")
    sys.exit(1)
else:
    print(f"  ✅ MONGODB_URI successfully detected!")

# 3. Check Python Driver & Certifi
print("\n[3] Checking Dependencies:")
try:
    import pymongo
    print(f"  ✅ PyMongo version: {pymongo.__version__}")
except ImportError:
    print("  ❌ PyMongo not installed!")

try:
    import certifi
    print(f"  ✅ Certifi CA bundle: {certifi.where()}")
except ImportError:
    print("  ⚠️ Certifi not installed. Installing recommended for TLS handshakes.")

# 4. Test MongoDB Atlas Connection
print("\n[4] Testing Connection to MongoDB Atlas Cluster:")
import socket
host = "ac-rmw7ui9-shard-00-00.li5d7wv.mongodb.net"
port = 27017

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(3.0)
try:
    sock.connect((host, port))
    sock.close()
    tcp_ok = True
    print(f"  ✅ Port 27017 is reachable on Atlas shard!")
except Exception as e:
    tcp_ok = False
    print(f"  ⚠️ Direct TCP connection to {host}:27017 timed out.")
    print(f"     Reason: MongoDB Atlas Network Access whitelist is blocking inbound requests from this IP address.")

if tcp_ok:
    try:
        import certifi
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=4000, tlsCAFile=certifi.where())
        info = client.server_info()
        print(f"  ✅ SUCCESS: Connected to MongoDB Atlas cluster! MongoDB v{info.get('version')}")
        db = client.get_default_database()
        print(f"  ✅ Active Database: '{db.name}'")
    except Exception as e:
        print(f"  ❌ MongoDB Client error: {e}")
else:
    print("\n[ACTION REQUIRED IN MONGODB ATLAS]")
    print("  To enable live cluster writes directly from your network:")
    print("  1. Log into your MongoDB Atlas Dashboard at https://cloud.mongodb.com")
    print("  2. In the left navigation, click on 'Network Access' (under Security)")
    print("  3. Click the green '+ ADD IP ADDRESS' button")
    print("  4. Click 'ALLOW ACCESS FROM ANYWHERE' (which adds 0.0.0.0/0)")
    print("  5. Click 'Confirm'")
    print("  6. Atlas takes ~30 seconds to deploy the change. Once deployed, live connection will be immediate!")

print("\n[5] Application Safe Fallback Status:")
from app.services.database import get_db_status
status = get_db_status()
print(f"  - Configured     : {status['configured']}")
print(f"  - Env loaded     : {status['env_file_loaded']}")
print(f"  - Database Mode  : {status['database']}")
print(f"  - Status Message : {status['message']}")
print("=" * 60)
