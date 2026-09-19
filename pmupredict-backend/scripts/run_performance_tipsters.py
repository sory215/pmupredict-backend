import os,sys
sys.path.insert(0,os.path.join(os.path.dirname(__file__),"..","lib"))
from fusion import update_pronostiqueur_performance
from timeutils import today_local
print(update_pronostiqueur_performance(today_local().isoformat()))
