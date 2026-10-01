import os
import traceback

result = {"env": {}, "imports": {}, "tz": None}
result["env"]["SUPABASE_URL"] = "present" if os.environ.get("SUPABASE_URL") else "MISSING"
result["env"]["SUPABASE_SERVICE_ROLE_KEY"] = "present" if os.environ.get("SUPABASE_SERVICE_ROLE_KEY") else "MISSING"

try:
    import tzdata
    result["imports"]["tzdata"] = "OK " + getattr(tzdata, "__version__", "?")
except Exception as e:
    result["imports"]["tzdata"] = "FAIL: " + str(e)

try:
    from zoneinfo import ZoneInfo
    ZoneInfo("Europe/Paris")
    result["tz"] = "OK"
except Exception as e:
    result["tz"] = "FAIL: " + traceback.format_exc()

try:
    from main import app
    result["imports"]["main"] = "OK"
except Exception as e:
    result["imports"]["main"] = "FAIL: " + traceback.format_exc()

def handler(request):
    return result
